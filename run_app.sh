#!/usr/bin/env bash
set -e
# Activate venv then run Flask app
if [ -f venv/bin/activate ]; then
  source venv/bin/activate
else
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
fi

python payment_consumer.py
export FLASK_APP=app.py
export FLASK_ENV=development
export FLASK_RUN_PORT=${FLASK_PORT:-8095}
flask run --host=0.0.0.0 --port=${FLASK_RUN_PORT}
