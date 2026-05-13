import pika, json, logging
from config import Config

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


def publish_payment_status(event: dict):
    params = _make_connection_parameters()
    conn = pika.BlockingConnection(params)
    ch = conn.channel()

    q = Config.PAYMENT_STATUS_QUEUE
    ch.queue_declare(queue=q, durable=True)

    ch.basic_publish(
        exchange="",
        routing_key=q,
        body=json.dumps(event),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    conn.close()
    logger.info(f"[publisher] sent to {q}: {event}")
