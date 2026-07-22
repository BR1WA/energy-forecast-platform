"""Versioned plain-text and HTML transactional email templates."""
from __future__ import annotations

from html import escape
from urllib.parse import quote

from app.config import Settings, get_settings
from app.models import EmailOutbox
from app.services.account_action_service import unseal_action_token
from app.services.email_providers import RenderedEmail


def _action_url(row: EmailOutbox, route: str, settings: Settings) -> str:
    sealed = str((row.payload or {}).get("sealed_token", ""))
    if not sealed:
        raise ValueError("Action email payload is missing its sealed token")
    raw_token = unseal_action_token(sealed)
    return f"{settings.PUBLIC_FRONTEND_URL.rstrip('/')}/{route}?token={quote(raw_token, safe='')}"


def render_email(row: EmailOutbox, settings: Settings | None = None) -> RenderedEmail:
    settings = settings or get_settings()
    if row.template_version != "v1":
        raise ValueError("Unsupported email template version")

    if row.template == "verify_email":
        url = _action_url(row, "verify-email", settings)
        subject = "Verify your EnergyForecast email"
        text = f"Verify your email: {url}\nThis single-use link expires in one hour."
        html = f"<p>Verify your email:</p><p><a href=\"{escape(url)}\">Verify email</a></p><p>This single-use link expires in one hour.</p>"
    elif row.template == "password_reset":
        url = _action_url(row, "reset-password", settings)
        subject = "Reset your EnergyForecast password"
        text = f"Reset your password: {url}\nThis single-use link expires in one hour."
        html = f"<p>Reset your password:</p><p><a href=\"{escape(url)}\">Reset password</a></p><p>This single-use link expires in one hour.</p>"
    elif row.template == "critical_alert":
        payload = row.payload or {}
        subject = f"Critical energy alert: {payload.get('title', 'Energy threshold exceeded')}"
        text = f"{payload.get('message', '')}\nView alerts: {payload.get('url', '')}"
        html = f"<p>{escape(str(payload.get('message', '')))}</p><p><a href=\"{escape(str(payload.get('url', '')))}\">View alerts</a></p>"
    else:
        raise ValueError("Unknown email template")

    return RenderedEmail(
        recipient=row.recipient,
        subject=subject,
        text_body=text,
        html_body=html,
    )
