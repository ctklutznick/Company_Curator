"""Email notification system.

SRP: Only responsible for composing and sending emails.
OCP: New notification channels can be added via the BaseNotifier abstraction.
DIP: Depends on EmailConfig, not hardcoded SMTP settings.
"""

import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from company_curator.config import EmailConfig


class BaseNotifier(ABC):
    """Abstract notifier — allows adding Slack, SMS, etc. without modifying existing code (OCP)."""

    @abstractmethod
    def send(self, subject: str, body: str) -> bool:
        ...


class EmailNotifier(BaseNotifier):
    """Sends daily email reports via SMTP."""

    def __init__(self, config: EmailConfig) -> None:
        self._config = config

    def send(self, subject: str, body: str) -> bool:
        """Send an email with the given subject and body."""
        if not self._config.smtp_user or not self._config.smtp_password:
            print("[Email] SMTP credentials not configured, skipping email.")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._config.smtp_user
        msg["To"] = self._config.email_to

        # Attach both plain text and HTML versions
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(self._markdown_to_html(body), "html"))

        try:
            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
                server.starttls()
                server.login(self._config.smtp_user, self._config.smtp_password)
                server.send_message(msg)
            return True
        except smtplib.SMTPException as e:
            print(f"[Email] Failed to send: {e}")
            return False

    @staticmethod
    def _markdown_to_html(markdown_text: str) -> str:
        """Basic markdown-to-HTML conversion for email readability."""
        html = markdown_text
        html = html.replace("\n\n", "</p><p>")
        html = html.replace("\n", "<br>")

        # Bold
        import re
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)

        # Headers
        html = re.sub(r"^## (.+)", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)", r"<h1>\1</h1>", html, flags=re.MULTILINE)

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <p>{html}</p>
        </body>
        </html>
        """
