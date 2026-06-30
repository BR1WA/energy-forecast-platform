"""
Alert service — handles alert creation, verification, and email notifications.
"""
import smtplib
from email.mime.text import MIMEText
from app.config import get_settings
from sqlalchemy.orm import Session
from app.models.models import Alert

settings = get_settings()

class AlertService:
    def get_recent_alerts(self, db: Session, user_id: int, limit: int = 5):
        alerts = db.query(Alert).filter(Alert.user_id == user_id).order_by(Alert.created_at.desc()).limit(limit).all()
        return [
            {
                "id": a.id,
                "type": a.alert_type,
                "severity": a.severity,
                "message": a.message,
                "timestamp": a.created_at.isoformat() if a.created_at else None
            }
            for a in alerts
        ]

alert_service = AlertService()


def send_alert_email(email_to: str, alert_type: str, severity: str, message: str):
    """
    Dispatches email notifications when energy anomalies or peak demands are forecasted.
    If SMTP_USER or SMTP_PASSWORD is not configured, falls back to mock console output.
    """
    subject = f"Energy Forecast Platform — {severity.upper()} Alert: {alert_type.replace('_', ' ').capitalize()}"
    
    body = (
        f"Hello,\n\n"
        f"The Energy Forecast Platform has generated an active alert:\n\n"
        f"============================================================\n"
        f"  Alert Type:   {alert_type.replace('_', ' ').capitalize()}\n"
        f"  Severity:     {severity.upper()}\n"
        f"  Description:  {message}\n"
        f"============================================================\n\n"
        f"Please check your dashboard for cost-saving recommendations and mitigation pathways.\n\n"
        f"Best regards,\n"
        f"Energy Management Team"
    )

    # If SMTP is not configured, fall back to console mock logging
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print("=" * 70)
        print(f"[SMTP MOCK] Dispatching Alert Notification to: {email_to}")
        print(f"Subject: {subject}")
        print("-" * 70)
        print(body)
        print("=" * 70)
        return

    # If SMTP is configured, attempt sending email
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = email_to

    try:
        # Establish connection
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        
        # Configure TLS if enabled
        if settings.SMTP_TLS:
            server.starttls()
            
        # Authenticate and send
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, [email_to], msg.as_string())
        server.quit()
        
        print(f"[SMTP] Successfully dispatched alert email to {email_to}")
    except Exception as e:
        print(f"[SMTP ERROR] Failed to send alert email to {email_to}: {str(e)}")
        # Print mock email to console as fallback so the alert is still visible in logs
        print("=" * 70)
        print(f"[SMTP MOCK FALLBACK] Target: {email_to}")
        print(f"Subject: {subject}")
        print("-" * 70)
        print(body)
        print("=" * 70)
