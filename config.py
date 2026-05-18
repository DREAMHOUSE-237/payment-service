import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

# ----------------------------
# 🔥 MySQL Configuration
# ----------------------------
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "password")
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
MYSQL_DB = os.environ.get("MYSQL_DB", "paymentdb")

MYSQL_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"

# ----------------------------
# 🔄 Fallback: SQLite si MySQL DOWN
# ----------------------------
DB_PATH = os.path.join(INSTANCE_DIR, "app.db")
SQLITE_URI = f"sqlite:////{DB_PATH}"

# ENV var DATABASE_URL > MySQL > SQLite
DB_URI = os.environ.get("DATABASE_URL", MYSQL_URI or SQLITE_URI)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev_key")

    SQLALCHEMY_DATABASE_URI = DB_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # RabbitMQ
    RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", 5672))
    RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
    RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "guest")
    RABBITMQ_VHOST = os.environ.get("RABBITMQ_VHOST", "/")

    # ✅ FIX : aligné avec le nom déclaré dans RabbitMQConfig.java du publication-service
    PAYMENT_INIT_QUEUE = os.environ.get("PAYMENT_INIT_QUEUE", "payment-queue")  # était "payments"
    PAYMENT_STATUS_QUEUE = os.environ.get("PAYMENT_STATUS_QUEUE", "payment-status")

    # Campay
    CAMPAY_BASE_URL = os.environ.get("CAMPAY_BASE_URL", "https://demo.campay.net/api")
    CAMPAY_TOKEN = os.environ.get("CAMPAY_TOKEN", "")
    CAMPAY_USERNAME = os.environ.get("CAMPAY_USERNAME", "")
    CAMPAY_PASSWORD = os.environ.get("CAMPAY_PASSWORD", "")

    # Mail
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", None)
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", None)
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME)

    # Webhook secret
    WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

    # DEMO: force 5 XAF
    FIXED_AMOUNT = 10