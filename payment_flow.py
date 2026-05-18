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
    Priorité :
    1. Token permanent
    2. Username/password
    """

    token = getattr(Config, "CAMPAY_TOKEN", None)

    if token and str(token).strip():
        return token

    username = getattr(Config, "CAMPAY_USERNAME", None)
    password = getattr(Config, "CAMPAY_PASSWORD", None)

    if username and password:

        url = f"{Config.CAMPAY_BASE_URL}/token/"

        payload = {
            "username": username,
            "password": password
        }

        logger.info("[CAMPAY] Requesting temporary token")

        resp = requests.post(
            url,
            json=payload,
            timeout=15
        )

        if resp.status_code != 200:
            raise CampayError(
                f"Unable to get token: "
                f"{resp.status_code} - {resp.text}"
            )

        data = resp.json()

        token = data.get("token")

        if not token:
            raise CampayError("Token missing from Campay response")

        return token

    raise CampayError("No Campay credentials configured")


def initiate_collect(
    amount,
    phone,
    description="",
    external_reference=None
):
    """
    Lance une requête de paiement Campay.
    """

    token = get_campay_token()

    fixed = getattr(Config, "FIXED_AMOUNT", None)

    # Mode démo : montant fixe
    if fixed is not None:
        amount = fixed

    url = f"{Config.CAMPAY_BASE_URL}/collect/"

    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "amount": str(amount),
        "currency": "XAF",
        "from": phone or "",
        "description": description or "",
        "external_reference": external_reference or ""
    }

    logger.info("[CAMPAY] Collect payload -> %s", payload)

    resp = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=30
    )

    logger.info(
        "[CAMPAY] Response -> %s | %s",
        resp.status_code,
        resp.text
    )

    if resp.status_code not in [200, 201]:

        raise CampayError(
            f"Collect failed: "
            f"{resp.status_code} - {resp.text}"
        )

    return resp.json()


def process_payment(
    correlation_id,
    publication_id,
    email,
    amount,
    description,
    phone
):
    """
    Flow principal du paiement.

    IMPORTANT :
    -------------------------
    Cette fonction NE FINALISE PAS
    le paiement.

    Elle :
    ✔ crée la transaction
    ✔ lance le collect Campay
    ✔ sauvegarde la référence provider
    ✔ laisse le statut à PENDING

    Ensuite :
    ✔ le webhook Campay reçoit
      SUCCESS ou FAILED
    ✔ le webhook finalise réellement
      la transaction
    ✔ le webhook publie RabbitMQ
    """

    logger.info(
        "[PAYMENT FLOW] Starting payment "
        "correlation_id=%s",
        correlation_id
    )

    # ----------------------------------------------------
    # Vérifier si transaction existe déjà
    # ----------------------------------------------------

    tx = Transaction.query.filter_by(
        external_reference=correlation_id
    ).first()

    # ----------------------------------------------------
    # Créer transaction si inexistante
    # ----------------------------------------------------

    if not tx:

        tx = Transaction(
            id=correlation_id,
            external_reference=correlation_id,
            publication_id=publication_id,
            email=email,
            phone=phone,
            description=description,
            amount=getattr(
                Config,
                "FIXED_AMOUNT",
                amount
            ),
            status="PENDING"
        )

        try:

            db.session.add(tx)
            db.session.commit()

            logger.info(
                "[DB] Transaction created: %s",
                tx.id
            )

        except Exception:

            db.session.rollback()

            logger.exception(
                "[DB] Failed to create transaction"
            )

            return {
                "status": "FAILED",
                "reason": "database_error"
            }

    else:

        logger.info(
            "[DB] Existing transaction found: %s",
            tx.id
        )

        # Si déjà terminée
        if tx.status in ["SUCCESS", "FAILED"]:

            logger.info(
                "[PAYMENT FLOW] Transaction already finalized"
            )

            return {
                "status": tx.status,
                "message": "transaction already processed"
            }

    # ----------------------------------------------------
    # Lancer collect Campay
    # ----------------------------------------------------

    try:

        resp = initiate_collect(
            amount=amount,
            phone=phone,
            description=description,
            external_reference=correlation_id
        )

    except Exception as e:

        logger.exception(
            "[PAYMENT FLOW] Campay collect failed"
        )

        tx.status = "FAILED"

        try:
            db.session.commit()

        except Exception:
            db.session.rollback()

        return {
            "status": "FAILED",
            "reason": str(e)
        }

    # ----------------------------------------------------
    # Sauvegarder référence provider
    # ----------------------------------------------------

    provider_ref = resp.get("reference")

    if provider_ref:

        tx.provider_reference = provider_ref

    # ----------------------------------------------------
    # IMPORTANT :
    # ON GARDE PENDING
    # ----------------------------------------------------
    #
    # Pourquoi ?
    #
    # Parce que :
    # - l'utilisateur n'a pas encore validé
    #   son code PIN
    #
    # - Campay n'a pas encore confirmé
    #
    # - le vrai statut viendra du WEBHOOK
    #
    # Donc :
    # SUCCESS/FAILED ne doivent JAMAIS
    # être décidés ici.
    #
    # ----------------------------------------------------

    tx.status = "PENDING"

    try:

        db.session.commit()

        logger.info(
            "[DB] Transaction updated -> PENDING"
        )

    except Exception:

        db.session.rollback()

        logger.exception(
            "[DB] Failed updating transaction"
        )

        return {
            "status": "FAILED",
            "reason": "database_update_error"
        }

    # ----------------------------------------------------
    # Retour immédiat
    # ----------------------------------------------------
    #
    # Le frontend affichera :
    #
    # "Paiement en cours..."
    #
    # Puis :
    # - websocket
    # - polling
    # - refresh
    #
    # récupèrera SUCCESS/FAILED
    # plus tard.
    #
    # ----------------------------------------------------

    return {
        "status": "PENDING",
        "payment_reference": provider_ref,
        "correlation_id": correlation_id,
        "campay_response": resp,
        "message": (
            "Payment initiated successfully. "
            "Waiting for Campay confirmation."
        )
    }