# file: payment_flow.py

import requests
from config import Config
from models import db, Transaction
import logging

logger = logging.getLogger(__name__)

class CampayError(Exception):
    pass


def get_campay_token():
    """
    Retourne le token Campay.
    Si un token permanent est dans `.env`, on l'utilise.
    Sinon, on tente username/password.
    """
    token = getattr(Config, "CAMPAY_TOKEN", None)
    if token and token.strip():
        return token

    username = getattr(Config, "CAMPAY_USERNAME", None)
    password = getattr(Config, "CAMPAY_PASSWORD", None)

    if username and password:
        url = f"{Config.CAMPAY_BASE_URL}/token/"
        resp = requests.post(url, json={"username": username, "password": password}, timeout=10)
        if resp.status_code != 200:
            raise CampayError(f"Unable to get token: {resp.status_code} {resp.text}")

        data = resp.json()
        token = data.get("token")
        if not token:
            raise CampayError("Token missing from Campay")

        return token

    raise CampayError("No Campay token configured.")


def initiate_collect(amount, phone, description="", external_reference=None):
    """
    Envoie un collect Campay.
    On force amount à FIXED_AMOUNT pour éviter les erreurs de démo.
    """
    token = get_campay_token()

    fixed = getattr(Config, "FIXED_AMOUNT", None)
    if fixed is not None:
        amount = fixed

    url = f"{Config.CAMPAY_BASE_URL}/collect/"
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}

    payload = {
        "amount": str(amount),
        "currency": "XAF",
        "from": phone or "",
        "description": description or "",
        "external_reference": external_reference or ""
    }

    logger.info("Campay collect -> %s", payload)

    resp = requests.post(url, json=payload, headers=headers, timeout=20)
    if resp.status_code not in (200, 201):
        logger.error("Campay collect failed: %s", resp.text)
        raise CampayError(f"Collect failed: {resp.status_code} - {resp.text}")

    return resp.json()


def process_payment(correlation_id, publication_id, user_id, email, amount, description, phone):
    """
    Lance un collect et enregistre la transaction en base.
    Le webhook finalise le paiement.
    """

    # Vérifier si transaction existe
    tx = Transaction.query.filter_by(external_reference=correlation_id).first()

    if not tx:
        tx = Transaction(
            id=correlation_id,
            external_reference=correlation_id,
            publication_id=publication_id,
            email=email,
            phone=phone,
            description=description,
            amount=getattr(Config, "FIXED_AMOUNT", amount),
            status="PENDING",
        )

        db.session.add(tx)
        db.session.commit()

    try:
        resp = initiate_collect(
            amount=amount,
            phone=phone,
            description=description,
            external_reference=correlation_id
        )
    except Exception as e:
        tx.status = "FAILED"
        db.session.commit()
        logger.exception("Payment initiation failed")
        return {"status": "FAILED", "reason": str(e)}

    provider_ref = resp.get("reference")
    tx.provider_reference = provider_ref
    tx.status = "PENDING"
    db.session.commit()

    return {
        "status": "PENDING",
        "payment_reference": provider_ref,
        "campay_response": resp
    }
