# file: webhook_handler.py
from flask import Blueprint, request, jsonify, current_app
from models import db, Transaction
from payment_publisher import publish_payment_status
import hmac, hashlib, os

webhook_bp = Blueprint("webhook_bp", __name__)


def verify_signature(req):
    secret = os.environ.get("WEBHOOK_SECRET") or current_app.config.get("WEBHOOK_SECRET", "")
    if not secret:
        return True  # mode dev

    signature = req.headers.get("x-campay-signature") or req.headers.get("x-signature")
    if not signature:
        return False

    computed = hmac.new(secret.encode(), req.get_data(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


@webhook_bp.route("/webhook/campay", methods=["POST"])
@webhook_bp.route("/campay/webhook", methods=["POST"])
def campay_webhook():
    if not verify_signature(request):
        return jsonify({"error": "invalid signature"}), 403

    data = request.get_json() or {}
    current_app.logger.info("[webhook] payload: %s", data)

    reference = data.get("reference")
    status = (data.get("status") or data.get("transaction_status") or "").upper()
    external_reference = (
        data.get("external_reference")
        or data.get("externalReference")
        or data.get("correlationId")
    )

    # Trouver transaction
    tx = None
    if reference:
        tx = Transaction.query.filter_by(provider_reference=reference).first()

    if not tx and external_reference:
        tx = Transaction.query.filter_by(external_reference=external_reference).first()

    if not tx:
        current_app.logger.warning("[webhook] unknown tx %s / %s", external_reference, reference)
        return jsonify({"error": "not found"}), 404

    # Idempotence
    if tx.status == "SUCCESS":
        return jsonify({"message": "already processed"}), 204

    try:
        tx.provider_reference = reference or tx.provider_reference
        tx.status = "SUCCESS" if status.startswith("SUCCESS") else "FAILED"
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("db update error")
        return jsonify({"error": "internal"}), 500

    # Construire event à envoyer dans la queue
    event = {
        "publicationId": tx.publication_id,
        "userId": tx.user_id or tx.external_reference,
        "email": tx.email,
        "amount": tx.amount,
        "status": tx.status,
        "transactionId": tx.provider_reference or tx.external_reference,
        "correlationId": tx.external_reference,
    }

    try:
        publish_payment_status(event)
    except Exception:
        current_app.logger.exception("publish failed")

    current_app.logger.info("[webhook] updated %s -> %s", tx.id, tx.status)
    return jsonify({"message": "ok"}), 200
