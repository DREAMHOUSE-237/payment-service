MS_PAYMENT-ready - quick run guide

1) Inspect and edit .env if needed:
   - RABBIT_URL
   - CAMPAY_TOKEN
   - WEBHOOK_SECRET (if used)
   - MAIL_USERNAME / MAIL_PASSWORD

2) Create and activate venv and install:
   ./run_app.sh    # will create venv and install if missing (runs the Flask app)
   # or to only install:
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

3) Start the consumer in a separate terminal:
   ./run_consumer.sh

4) Start the app (if not started by run_app.sh):
   ./run_app.sh

5) Test flow:
   - Publish a message into the payment queue (example using python snippet):
     python - <<'PY'
import pika, json, os
params = pika.URLParameters("$(cat .env | grep RABBIT_URL | cut -d'=' -f2-)")
conn = pika.BlockingConnection(params)
ch = conn.channel()
ch.queue_declare(queue='payment-queue', durable=True)
msg = {"idPublication":42, "prix":1500, "proprietaireEmail":"test@example.com", "description":"Achat test"}
ch.basic_publish('', 'payment-queue', json.dumps(msg), properties=pika.BasicProperties(delivery_mode=2))
print("Message envoyé")
conn.close()
PY

   - The consumer should receive the message, call Campay /collect and store a provider_reference.
   - Simulate webhook (if needed):
     curl -X POST http://localhost:5001/webhook/campay -H "Content-Type: application/json" -d '{"reference":"<REF>","status":"SUCCESSFUL","external_reference":"<correlationId>"}'
   - Check the payment-status queue for published events.

