# file: consumer.py
import pika, json, time, logging, uuid
from config import Config
from payment_flow import process_payment
from flask_mail import Message
from app import create_app, mail
from models import db, Transaction
from payment_publisher import publish_payment_status

logger = logging.getLogger(__name__)

def _make_connection_parameters():
    creds = pika.PlainCredentials(Config.RABBITMQ_USER, Config.RABBITMQ_PASSWORD)
    return pika.ConnectionParameters(
        host=Config.RABBITMQ_HOST,
        port=Config.RABBITMQ_PORT,
        virtual_host=Config.RABBITMQ_VHOST,
        credentials=creds,
        heartbeat=60,
        blocked_connection_timeout=30
    )

def send_mail_with_retry(app, to_email, correlation_id, amount, retries=3, delay=2):
    msg = Message(
        subject="Payment requested",
        sender=app.config.get("MAIL_DEFAULT_SENDER"),
        recipients=[to_email],
        body=f"Votre paiement de {amount} XAF a été initialisé (ref: {correlation_id}). Vous recevrez la confirmation via webhook."
    )
    for attempt in range(1, retries + 1):
        try:
            with app.app_context():
                mail.send(msg)
            logger.info("[consumer] Email sent to %s", to_email)
            return True
        except Exception:
            logger.exception("[consumer] Send email failed (attempt %s/%s)", attempt, retries)
            time.sleep(delay * attempt)
    return False

def run_consumer(app):
    queue_name = Config.PAYMENT_INIT_QUEUE
    params = _make_connection_parameters()
    while True:
        try:
            conn = pika.BlockingConnection(params)
            channel = conn.channel()
            channel.queue_declare(queue=queue_name, durable=True)
            channel.basic_qos(prefetch_count=1)

            def callback(ch, method, properties, body):
                try:
                    data = json.loads(body)
                except Exception:
                    logger.exception("Invalid JSON in message")
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return

                amount = data.get("prix") or data.get("amount")
                email = data.get("proprietaireEmail") or data.get("email")
                description = data.get("description")
                publication_id = data.get("idPublication") or data.get("publicationId")
                correlation_id = data.get("correlation_id") or str(uuid.uuid4())
                phone = data.get("numeroPaiement") or data.get("phone") or ""

                logger.info("[consumer] received %s", data)

                with app.app_context():
                    # process payment (this will create tx if missing)
                    result = process_payment(
                        correlation_id=correlation_id,
                        publication_id=publication_id,
                        user_id=None,
                        email=email,
                        amount=amount,
                        description=description,
                        phone=phone
                    )

                    # ---- SAVE or UPDATE transaction in DB using fields the model expects ----
                    try:
                        # Use id and external_reference (fields expected by the model)
                        tx = Transaction.query.filter_by(external_reference=correlation_id).first()
                        if not tx:
                            tx = Transaction(
                                id=correlation_id,
                                external_reference=correlation_id,
                                publication_id=publication_id,
                                amount=getattr(Config, "FIXED_AMOUNT", amount),
                                description=description,
                                email=email,
                                status=result.get("status"),
                                phone=phone
                            )
                            db.session.add(tx)
                        else:
                            tx.status = result.get("status")
                            tx.amount = getattr(Config, "FIXED_AMOUNT", amount)
                        db.session.commit()
                        logger.info("[consumer] Transaction saved/updated in DB: %s", correlation_id)
                    except Exception:
                        db.session.rollback()
                        logger.exception("[consumer] Failed to save transaction in DB")

                    # ---- publish payment status to queue ----
                    try:
                        publish_payment_status({
                            "correlation_id": correlation_id,
                            "status": result.get("status"),
                            "amount": getattr(Config, "FIXED_AMOUNT", amount),
                            "email": email,
                            "publication_id": publication_id,
                        })
                        logger.info("[consumer] Published payment status for %s", correlation_id)
                    except Exception:
                        logger.exception("[consumer] Failed to publish payment status")

                    # ---- send email with retry ----
                    if result.get("status") == "PENDING" and email:
                        send_mail_with_retry(app, email, correlation_id, getattr(Config, "FIXED_AMOUNT", amount), retries=3)

                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=queue_name, on_message_callback=callback)
            logger.info("[consumer] Waiting for messages on queue %s", queue_name)
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            logger.exception("RabbitMQ connection failed, will retry in 5s")
            time.sleep(5)
            continue
        except Exception:
            logger.exception("Consumer unexpected error, retrying in 5s")
            time.sleep(5)
            continue
