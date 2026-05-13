import threading
import logging
from flask import Flask, request, jsonify
from models import db, Transaction
from campay_client import request_payment
from webhook_handler import webhook_bp
from config import Config
from flask_mail import Mail
import pymysql
pymysql.install_as_MySQLdb()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

mail = Mail()


def create_app():
    # Charger la config depuis Spring Cloud Config Server
    try:
        from config_loader import load_config
        load_config()
    except Exception:
        logger.warning("Config Server non disponible — utilisation des variables d'env.")

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    mail.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(webhook_bp)

    @app.post("/pay")
    def pay():
        data = request.get_json() or {}
        phone = data.get("phone") or data.get("numeroPaiement")
        description = data.get("description", "Paiement")
        import uuid
        correlation_id = str(uuid.uuid4())

        transaction = Transaction(
            amount=Config.FIXED_AMOUNT,
            phone=phone,
            description=description,
            external_reference=correlation_id,
            status="PENDING"
        )
        db.session.add(transaction)
        db.session.commit()

        campay_resp = request_payment(
            amount=Config.FIXED_AMOUNT,
            phone=phone,
            description=description,
            external_ref=correlation_id
        )

        provider_reference = campay_resp.get("reference") if isinstance(campay_resp, dict) else None
        if provider_reference:
            transaction.provider_reference = provider_reference
            db.session.commit()
            return jsonify({
                "transaction_id": transaction.id,
                "external_reference": transaction.external_reference,
                "reference": transaction.provider_reference,
                "ussd_code": campay_resp.get("ussd_code"),
                "campay_response": campay_resp
            }), 200
        else:
            transaction.status = "FAILED"
            db.session.commit()
            return jsonify({"error": "collect_failed", "campay_response": campay_resp}), 400

    @app.get("/")
    def root():
        return "Microservice Payment is running!"

    @app.get("/health")
    def health():
        return jsonify({"status": "UP"}), 200

    return app


app = create_app()


def start_background_services():
    # Eureka registration
    try:
        from eureka_service import register, start_heartbeat
        register()
        start_heartbeat()
        logger.info("✅ Eureka registration started")
    except Exception:
        logger.exception("Eureka registration failed")

    # RabbitMQ consumer
    try:
        from consumer import run_consumer
        t = threading.Thread(target=run_consumer, args=(app,), daemon=True, name="rabbit-consumer")
        t.start()
        logger.info("✅ Started background consumer thread")
    except Exception:
        logger.exception("Cannot start consumer")


start_background_services()