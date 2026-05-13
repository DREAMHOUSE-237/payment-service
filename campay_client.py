import requests
import time
from config import Config
import logging

logger = logging.getLogger(__name__)

_cached_token = None
_cached_token_expiry = 0

class CampayError(Exception):
    pass

def get_campay_token():
    """
    Use static token if provided, otherwise request one using username/password.
    Token is cached until expiry.
    """
    global _cached_token, _cached_token_expiry

    # 1) Static token set in env -> use it
    if Config.CAMPAY_TOKEN and Config.CAMPAY_TOKEN.strip() != "":
        return Config.CAMPAY_TOKEN.strip()

    # 2) Cached token still valid?
    if _cached_token and time.time() < _cached_token_expiry:
        return _cached_token

    # 3) Request token using credentials
    username = Config.CAMPAY_USERNAME
    password = Config.CAMPAY_PASSWORD

    if not username or not password:
        raise CampayError("No Campay token or credentials configured (CAMPAY_TOKEN or CAMPAY_USERNAME/CAMPAY_PASSWORD required)")

    url = f"{Config.CAMPAY_BASE_URL}/token/"
    payload = {"username": username, "password": password}
    try:
        r = requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.exception("Failed request to Campay token endpoint")
        raise CampayError(f"Token request failed: {e}")

    if r.status_code != 200:
        logger.error("Campay token request failed: %s %s", r.status_code, r.text)
        raise CampayError(f"Token request failed: HTTP {r.status_code} - {r.text}")

    data = r.json()
    token = data.get("token")
    ttl = data.get("expires_in", 3600)

    if not token:
        logger.error("No token returned from Campay: %s", data)
        raise CampayError("No token returned from Campay")

    _cached_token = token
    _cached_token_expiry = time.time() + max(55 * 60, ttl - 60)  # cache ~55min by default
    logger.info("Obtained Campay token (cached)")
    return token

def request_payment(amount, phone, description, external_ref=""):
    """
    Call Campay /collect/ and return JSON response.
    """
    token = get_campay_token()
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": str(amount),
        "currency": "XAF",
        "from": str(phone),
        "description": description,
        "external_reference": external_ref,
        "external_user": ""
    }

    url = f"{Config.CAMPAY_BASE_URL}/collect/"
    logger.info("Campay collect -> %s", payload)
    r = requests.post(url, json=payload, headers=headers, timeout=20)
    # Campay returns non-200 for many error cases; we pass full response back
    try:
        j = r.json()
    except Exception:
        j = {"error": "invalid json", "status_code": r.status_code, "text": r.text}

    if r.status_code >= 400:
        logger.error("Campay collect failed: %s", j)
        # return j so caller can inspect; don't raise here unless you want
        return j

    return j

def get_transaction_status(reference):
    token = get_campay_token()
    headers = {"Authorization": f"Token {token}"}
    url = f"{Config.CAMPAY_BASE_URL}/transaction/{reference}/"
    r = requests.get(url, headers=headers, timeout=10)
    try:
        return r.json()
    except Exception:
        return {"status_code": r.status_code, "text": r.text}
