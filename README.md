# payment-service

Service de paiement de la plateforme **DREAMHOUSE237**, développé en **Flask** (Python), intégré à l'agrégateur mobile money **Campay**.

## Rôle

Gère le paiement des frais d'activation des annonces immobilières via Mobile Money (Orange/MTN, Cameroun) :

1. `POST /pay` : initie une collecte Campay (`campay_client.request_payment`) pour un numéro donné, crée une transaction en base (`PENDING`)
2. Campay traite le paiement côté opérateur mobile money et notifie ce service de façon **asynchrone** via un **webhook**
3. Le webhook (`/webhook/campay` ou `/campay/webhook`) met à jour le statut de la transaction et publie le résultat sur la queue `payment-status`, consommée par `publication-service` pour activer/rejeter l'annonce correspondante

⚠️ Le webhook est configuré côté **tableau de bord marchand Campay** (hors de ce repo) et doit pointer vers l'URL publique actuelle du gateway (`https://<domaine-gateway>/payment-service/webhook/campay`). Si l'infrastructure change d'adresse (migration EC2, nouveau domaine), cette URL doit être mise à jour manuellement sur Campay, sinon les paiements restent bloqués en `PENDING` indéfiniment.

## Stack

- Python 3 / Flask / Flask-SQLAlchemy
- MySQL (AWS RDS, TLS) avec repli SQLite en local si `DATABASE_URL` n'est pas configurée
- Gunicorn (port interne `8086`)
- Pika (client RabbitMQ) — consumer sur `payment-queue`, publisher sur `payment-status`

## Architecture & découverte de service

S'enregistre auprès de `registry-service` (Eureka) et récupère sa configuration depuis `config-service`. Exposé via `proxy-service` sous les préfixes `/PAYMENT-SERVICE/` et `/payment-service/` (ce dernier dédié au webhook Campay).

## Variables d'environnement clés

| Variable | Description |
|---|---|
| `DATABASE_URL` | URL MySQL complète (sinon assemblée depuis `MYSQL_*`, sinon repli SQLite) |
| `DB_SSL_CA` | Certificat CA pour la connexion TLS |
| `CAMPAY_BASE_URL` / `CAMPAY_TOKEN` (ou `CAMPAY_USERNAME`/`CAMPAY_PASSWORD`) | Accès à l'API Campay |
| `WEBHOOK_SECRET` | Secret de signature HMAC du webhook (doit correspondre à la valeur configurée côté Campay) |
| `RABBITMQ_USER` / `RABBITMQ_PASSWORD` | Identifiants RabbitMQ |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | Envoi d'email de confirmation de paiement |

## Développement local

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./run_app.sh        # démarre l'API Flask
./run_consumer.sh   # démarre le consumer RabbitMQ (payment-queue)
```

## Déploiement

Via **Docker Swarm** (voir [`infrastructure`](https://github.com/DREAMHOUSE-237/infrastructure)). Un push sur `dev` déclenche automatiquement le pipeline CI/CD (build → merge → redéploiement) — à garder en tête avant de pousser un changement pendant une démo ou un test en direct.
