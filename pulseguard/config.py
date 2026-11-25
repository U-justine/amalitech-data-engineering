# All PulseGuard settings in one place.
# Each one can be changed with an environment variable (see .env.example).
import os

CLINIC_NAME = os.getenv("CLINIC_NAME", "PulseGuard Clinic")

# Kafka: where the messages travel
KAFKA_SERVER = os.getenv("KAFKA_SERVER", "localhost:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "heartbeats")                        # heart rate readings
ALERT_TOPIC = os.getenv("KAFKA_ALERT_TOPIC", "heartbeat-alerts")      # health alerts
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "heartbeat-savers")             # used by consumer.py
ALERT_GROUP_ID = os.getenv("KAFKA_ALERT_GROUP_ID", "alert-emailers")  # used by alert_service.py

# PostgreSQL: where the data is saved (port 5433 on your computer)
DB_SETTINGS = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5433")),
    "dbname": os.getenv("DB_NAME", "heartbeat"),
    "user": os.getenv("DB_USER", "heartbeat"),
    "password": os.getenv("DB_PASSWORD", "heartbeat"),
}

# Heart rate limits (beats per minute).
# Each patient has their own limits; these are only for unknown patients.
NORMAL_MIN = 50      # below -> "low"
NORMAL_MAX = 120     # above -> "high"
POSSIBLE_MIN = 25    # below -> sensor error, rejected
POSSIBLE_MAX = 230   # above -> sensor error, rejected

# Health alerts
EPISODE_MIN_SECONDS = int(os.getenv("EPISODE_MIN_SECONDS", "30"))  # out of range this long -> alert
CRITICAL_ABOVE = 20  # 20+ bpm above the high limit -> "critical"
CRITICAL_BELOW = 10  # 10+ bpm below the low limit  -> "critical"

# Emails. Default: Mailpit test inbox at http://localhost:8025
# For Gmail: SMTP_HOST=smtp.gmail.com, SMTP_PORT=587, SMTP_TLS=yes, plus an app password.
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "yes") == "yes"
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_TLS = os.getenv("SMTP_TLS", "no") == "yes"
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_FROM = os.getenv("ALERT_FROM", "pulseguard@example.com")
ALERT_TO = os.getenv("ALERT_TO", "oncall@example.com")                 # health alerts -> doctors
SYSTEM_ALERT_TO = os.getenv("SYSTEM_ALERT_TO", "it-team@example.com")  # system problems -> IT team

# Folder where a service notes "I am down", so it can email "back online" later
STATE_DIR = os.getenv("STATE_DIR", ".pulseguard_state")
