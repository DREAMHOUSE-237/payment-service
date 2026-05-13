#!/usr/bin/env bash
set -e
if [ -f venv/bin/activate ]; then
  source venv/bin/activate
else
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
fi

python payment_consumer.py
