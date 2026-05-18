# file: webhook_handler.py

from flask import Blueprint, request, jsonify, current_app
from models import db, Transaction
from payment_publisher import publish_payment_status
import hmac
import hashlib
import os

webhook_bp = Blueprint("webhook_bp", __name__)


def verify_signature(req):
    secret = os.environ.get("WEBHOOK_SECRET") or current_app.config.get("WEBHOOK_SECRET", "")

    if not secret:
        return True

    signature = req.headers.get("x-campay-signature") or req.headers.get("x-signature")

    if not signature:
        return False

    computed = hmac.new(
        secret.encode(),
        req.get_data(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed, signature)


@webhook_bp.route("/webhook/campay", methods=["POST"])
@webhook_bp.route("/campay/webhook", methods=["POST"])
def campay_webhook():

    if not verify_signature(request):
        return jsonify({"error": "invalid signature"}), 403

    data = request.get_json() or {}

    current_app.logger.info("[WEBHOOK] payload: %s", data)

    reference = data.get("reference")

    raw_status = (
        data.get("status")
        or data.get("transaction_status")
        or ""
    ).upper()

    external_reference = (
        data.get("external_reference")
        or data.get("externalReference")
        or data.get("correlationId")
    )

    tx = None

    if reference:
        tx = Transaction.query.filter_by(
            provider_reference=reference
        ).first()

    if not tx and external_reference:
        tx = Transaction.query.filter_by(
            external_reference=external_reference
        ).first()

    if not tx:
        return jsonify({"error": "transaction not found"}), 404

    # ----------------------------
    # Mapping propre des statuts
    # ----------------------------

    if raw_status in ["SUCCESS", "SUCCESSFUL"]:
        final_status = "SUCCESS"

    elif raw_status in ["FAILED", "FAIL", "ERROR"]:
        final_status = "FAILED"

    else:
        final_status = "PENDING"

    # ----------------------------
    # Eviter double traitement
    # ----------------------------

    if tx.status == final_status:
        return jsonify({"message": "already processed"}), 200

    try:

        tx.provider_reference = (
            reference or tx.provider_reference
        )

        tx.status = final_status

        db.session.commit()

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Database update error"
        )

        return jsonify({"error": "internal"}), 500

    # ------------------------------------------------
    # IMPORTANT :
    # On publie SEULEMENT SUCCESS ou FAILED
    # ------------------------------------------------

    if final_status in ["SUCCESS", "FAILED"]:

        event = {
            "publicationId": tx.publication_id,
            "email": tx.email,
            "amount": tx.amount,
            "status": final_status,
            "transactionId": tx.provider_reference,
            "correlationId": tx.external_reference,
        }

        try:
            publish_payment_status(event)

        except Exception:
            current_app.logger.exception(
                "RabbitMQ publish failed"
            )

    current_app.logger.info(
        "[WEBHOOK] Transaction %s -> %s",
        tx.id,
        final_status
    )

    return jsonify({
        "message": "ok",
        "status": final_status
    }), 200