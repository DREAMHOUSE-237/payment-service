FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    python3-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install mysqlclient gunicorn

COPY . .

EXPOSE 8086

CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:8086", "--workers", "1", "--timeout", "120"]
#