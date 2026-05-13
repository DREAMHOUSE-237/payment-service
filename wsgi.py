from app import create_app
from py_eureka_client import eureka_client
from config_loader import load_config
from dotenv import load_dotenv
import os

# ===============================
# 💠 Charger configuration depuis Spring Cloud Config
# ===============================
load_config()
load_dotenv()

# ===============================
# 💠 Créer l'application Flask
# ===============================
app = create_app()

# ===============================
# 💠 Enregistrement Eureka
# ===============================
try:
    eureka_client.init(
        eureka_server="http://192.168.172.81:8761/eureka/",
        app_name="PAYMENT-SERVICE",
        instance_port=int(os.getenv("PORT", 8095))
    )
    print("📡 Eureka Registration OK !")
except Exception as e:
    print("❌ Eureka registration failed:", e)

# ===============================
# 💠 Lancement du microservice
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8095)), debug=False)
