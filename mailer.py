import pika, json
from models import db, Transaction
from config import RABBITMQ_HOST, RABBITMQ_QUEUE
from campay_client import get_transaction_status
from mailer import send_mail

def process_event(data):
    ref = data.get("reference")
    status_data = get_transaction_status(ref)

    status = status_data.get("status")

    transaction = Transaction.query.filter_by(provider_reference=ref).first()
    if not transaction:
        return
    
    transaction.status = status
    db.session.commit()

    if status == "SUCCESSFUL":
        send_mail(
            to="florindandongwou@gmail.com",
            subject="Paiement reçu",
            content=f"Votre paiement de {transaction.amount} XAF est confirmé."
        )

def start_worker():
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE)

    def callback(ch, method, properties, body):
        data = json.loads(body)
        process_event(data)

    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback, auto_ack=True)
    print("Worker started")
    channel.start_consuming()

if __name__ == "__main__":
    start_worker()
