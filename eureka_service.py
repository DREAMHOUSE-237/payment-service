import os
import socket
import requests
import time
import threading
import logging

logger = logging.getLogger(__name__)

EUREKA_URL = os.environ.get("EUREKA_URL", "http://localhost:8761/eureka")
APP_NAME = "PAYMENT-SERVICE"
HOST_IP = os.environ.get("HOST_IP", socket.gethostbyname(socket.gethostname()))
PORT = int(os.environ.get("APP_PORT", "8086"))
INSTANCE_ID = f"{HOST_IP}:{APP_NAME}:{PORT}"


def register():
    payload = {
        "instance": {
            "instanceId": INSTANCE_ID,
            "hostName": HOST_IP,
            "app": APP_NAME,
            "ipAddr": HOST_IP,
            "status": "UP",
            "port": {"$": PORT, "@enabled": "true"},
            "securePort": {"$": 443, "@enabled": "false"},
            "vipAddress": APP_NAME,
            "secureVipAddress": APP_NAME,
            "homePageUrl": f"http://{HOST_IP}:{PORT}/",
            "statusPageUrl": f"http://{HOST_IP}:{PORT}/health",
            "healthCheckUrl": f"http://{HOST_IP}:{PORT}/health",
            "dataCenterInfo": {
                "@class": "com.netflix.appinfo.InstanceInfo$DefaultDataCenterInfo",
                "name": "MyOwn"
            },
            "metadata": {
                "management.port": str(PORT),
                "instanceId": INSTANCE_ID
            },
            "leaseInfo": {
                "renewalIntervalInSecs": 30,
                "durationInSecs": 90
            }
        }
    }
    try:
        r = requests.post(
            f"{EUREKA_URL}/apps/{APP_NAME}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        if r.status_code in [200, 204]:
            logger.info(f"✅ Enregistré sur Eureka: {INSTANCE_ID}")
        else:
            logger.warning(f"⚠️ Eureka registration failed: {r.status_code} - {r.text}")
    except Exception as e:
        logger.error(f"❌ Eureka registration error: {e}")


def _heartbeat_loop():
    url = f"{EUREKA_URL}/apps/{APP_NAME}/{INSTANCE_ID}"
    while True:
        try:
            r = requests.put(url, timeout=5)
            if r.status_code == 200:
                logger.debug("💓 Heartbeat OK")
            elif r.status_code == 404:
                logger.warning("Instance expirée — re-enregistrement...")
                register()
        except Exception as e:
            logger.warning(f"⚠️ Heartbeat failed: {e}")
            try:
                register()
            except Exception:
                pass
        time.sleep(25)


def start_heartbeat():
    t = threading.Thread(target=_heartbeat_loop, daemon=True, name="eureka-heartbeat")
    t.start()