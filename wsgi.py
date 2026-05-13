from app import create_app
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
# 💠 Lancement du microservice
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8086)), debug=False)