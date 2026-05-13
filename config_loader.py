import os
import requests
import logging

logger = logging.getLogger(__name__)

CONFIG_SERVER_URL = os.environ.get(
    "CONFIG_SERVER_URL",
    "http://ec2-16-171-142-15.eu-north-1.compute.amazonaws.com:8888"
)


def load_config():
    url = f"{CONFIG_SERVER_URL}/payment-service/default"
    logger.info(f"🔄 Chargement config depuis {url}...")
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()

        for source in data.get("propertySources", []):
            props = source.get("source", {})
            for key, value in props.items():
                env_key = key.upper().replace(".", "_").replace("-", "_")
                if env_key not in os.environ:
                    os.environ[env_key] = str(value)

        logger.info("✅ Configuration Spring Cloud chargée avec succès.")
    except Exception as e:
        logger.warning(f"⚠️ Config Server inaccessible: {e} — utilisation des variables d'env locales.")