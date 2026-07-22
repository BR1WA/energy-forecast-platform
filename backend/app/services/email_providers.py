"""Provider-neutral transactional email delivery implementations."""
from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
import smtplib
from typing import Protocol

from app.config import Settings, get_settings


@dataclass(frozen=True)
class RenderedEmail:
    recipient: str
    subject: str
    text_body: str
    html_body: str


class MailProvider(Protocol):
    def send(self, message: RenderedEmail) -> str | None:
        """Submit a rendered message and return the provider message identifier."""


class SMTPMailProvider:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def send(self, message: RenderedEmail) -> str:
        email = EmailMessage()
        provider_id = make_msgid(domain=self.settings.EMAIL_FROM_ADDRESS.partition("@")[2] or None)
        email["Message-ID"] = provider_id
        email["Subject"] = message.subject
        email["From"] = formataddr((self.settings.EMAIL_FROM_NAME, self.settings.EMAIL_FROM_ADDRESS))
        email["To"] = message.recipient
        if self.settings.EMAIL_REPLY_TO:
            email["Reply-To"] = self.settings.EMAIL_REPLY_TO
        email.set_content(message.text_body)
        email.add_alternative(message.html_body, subtype="html")

        with smtplib.SMTP(
            self.settings.SMTP_HOST,
            self.settings.SMTP_PORT,
            timeout=self.settings.SMTP_TIMEOUT_SECONDS,
        ) as client:
            if self.settings.SMTP_USE_TLS:
                client.starttls()
            client.login(self.settings.SMTP_USERNAME, self.settings.SMTP_PASSWORD)
            client.send_message(email)
        return provider_id[:255]


class CapturingMailProvider:
    """Deterministic provider used by tests and local capture journeys."""

    def __init__(self, *, failure: Exception | None = None):
        self.messages: list[RenderedEmail] = []
        self.failure = failure

    def send(self, message: RenderedEmail) -> str:
        if self.failure is not None:
            raise self.failure
        self.messages.append(message)
        return f"capture-{len(self.messages)}"
