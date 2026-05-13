from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(5), default="XAF")
    phone = db.Column(db.String(20), nullable=True)
    description = db.Column(db.String(255))
    status = db.Column(db.String(20), default="PENDING")
    provider_reference = db.Column(db.String(100))
    external_reference = db.Column(db.String(100))
    email = db.Column(db.String(255), nullable=True)
    publication_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
