"""Versioned plain-text and HTML transactional email templates."""
from __future__ import annotations

from datetime import datetime
from html import escape
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


def _critical_alert_content(payload: dict) -> tuple[str, str]:
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("Critical-alert email payload is missing persisted evidence")
    required = ("observed_at", "observed_kw", "threshold_kw", "source")
    if any(evidence.get(key) in (None, "") for key in required):
        raise ValueError("Critical-alert email evidence is incomplete")

    timezone_name = str(payload.get("timezone") or "")
    try:
        observed_at = datetime.fromisoformat(str(evidence["observed_at"]).replace("Z", "+00:00"))
        if observed_at.tzinfo is None:
            raise ValueError("Observed time must include an offset")
        observed_label = observed_at.astimezone(ZoneInfo(timezone_name)).isoformat()
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("Critical-alert email timezone evidence is invalid") from exc

    source_labels = {
        "push": "Meter push API",
        "simulation": "Demo simulator",
        "csv": "CSV import",
    }
    source = str(evidence["source"])
    source_label = source_labels.get(source, f"Recorded source ({source})")
    observed_kw = float(evidence["observed_kw"])
    threshold_kw = float(evidence["threshold_kw"])
    meter_name = str(evidence.get("meter_name") or "Primary meter")
    message = str(payload.get("message") or "")
    url = str(payload.get("url") or "")
    if not message or not url:
        raise ValueError("Critical-alert email payload is incomplete")

    text = (
        f"{message}\n\n"
        "Persisted evidence:\n"
        f"- Meter: {meter_name}\n"
        f"- Observed load: {observed_kw:.3f} kW\n"
        f"- Configured threshold: {threshold_kw:.3f} kW\n"
        f"- Observed time: {observed_label} ({timezone_name})\n"
        f"- Source: {source_label}\n\n"
        f"View this alert: {url}"
    )
    html = (
        f"<p>{escape(message)}</p>"
        "<p>Persisted evidence:</p><ul>"
        f"<li>Meter: {escape(meter_name)}</li>"
        f"<li>Observed load: {observed_kw:.3f} kW</li>"
        f"<li>Configured threshold: {threshold_kw:.3f} kW</li>"
        f"<li>Observed time: {escape(observed_label)} ({escape(timezone_name)})</li>"
        f"<li>Source: {escape(source_label)}</li>"
        "</ul>"
        f"<p><a href=\"{escape(url)}\">View this alert</a></p>"
    )
    return text, html


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
        text, html = _critical_alert_content(payload)
    else:
        raise ValueError("Unknown email template")

    return RenderedEmail(
        recipient=row.recipient,
        subject=subject,
        text_body=text,
        html_body=html,
    )
