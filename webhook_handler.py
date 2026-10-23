# file: webhook_handler.py

from flask import Blueprint, request, jsonify, current_app
from models import db, Transaction
from payment_publisher import publish_payment_status
from campay_client import get_transaction_status
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
    # Ce endpoint est public : on ne fait pas confiance au statut du
    # payload, on redemande le vrai statut à Campay avec notre token,
    # pour la référence enregistrée à l'initiation du paiement.
    # ----------------------------

    if not tx.provider_reference:
        return jsonify({"error": "transaction has no provider reference"}), 409

    try:
        campay_tx = get_transaction_status(tx.provider_reference)
    except Exception:
        current_app.logger.exception("Campay status check failed")
        return jsonify({"error": "status check failed"}), 502

    campay_external_reference = campay_tx.get("external_reference")
    if campay_external_reference and campay_external_reference != tx.external_reference:
        current_app.logger.warning(
            "[WEBHOOK] external_reference mismatch for tx %s: %s != %s",
            tx.id, campay_external_reference, tx.external_reference
        )
        return jsonify({"error": "reference mismatch"}), 409

    raw_status = (campay_tx.get("status") or "").upper()

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