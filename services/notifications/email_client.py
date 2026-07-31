"""Email client (P-04.2).

Tres modos según env vars:
- sendgrid: si SENDGRID_API_KEY está, usamos su REST API.
- smtp: si SMTP_HOST está (sin SendGrid), usamos SMTP plano.
- mock: ningún env configurado → loguea el envío con structlog para demo.

API pública: send_email(to, subject, html, text=None) → dict con status.
"""

import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

EmailMode = Literal["sendgrid", "smtp", "mock"]


def current_mode() -> EmailMode:
    if os.getenv("SENDGRID_API_KEY"):
        return "sendgrid"
    if os.getenv("SMTP_HOST"):
        return "smtp"
    return "mock"


def _from_address() -> str:
    return os.getenv("EMAIL_FROM", "noreply@xtask.local")


async def send_email(
    *, to: str, subject: str, html: str, text: str | None = None,
) -> dict:
    """Envía un email. Retorna dict con status, mode y detail."""
    mode = current_mode()
    text_body = text or _html_to_text_fallback(html)

    if mode == "sendgrid":
        return await _send_sendgrid(to=to, subject=subject, html=html, text=text_body)
    if mode == "smtp":
        return await _send_smtp(to=to, subject=subject, html=html, text=text_body)
    return _send_mock(to=to, subject=subject, html=html)


def _send_mock(*, to: str, subject: str, html: str) -> dict:
    """Solo logea. Útil para demo local."""
    logger.info(
        "email_mock_sent",
        to=to, subject=subject, body_preview=html[:120].replace("\n", " "),
    )
    return {"status": "sent", "mode": "mock", "detail": "logged"}


async def _send_sendgrid(*, to: str, subject: str, html: str, text: str) -> dict:
    api_key = os.environ["SENDGRID_API_KEY"]
    payload = {
        "personalizations": [{"to": [{"email": to}], "subject": subject}],
        "from": {"email": _from_address(), "name": "XTask"},
        "content": [
            {"type": "text/plain", "value": text},
            {"type": "text/html", "value": html},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if 200 <= r.status_code < 300:
                return {"status": "sent", "mode": "sendgrid", "detail": str(r.status_code)}
            logger.warning("sendgrid_failed", status=r.status_code, body=r.text[:200])
            return {"status": "failed", "mode": "sendgrid", "detail": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:  # noqa: BLE001
        logger.warning("sendgrid_exception", exc_info=e)
        return {"status": "failed", "mode": "sendgrid", "detail": str(e)[:200]}


async def _send_smtp(*, to: str, subject: str, html: str, text: str) -> dict:
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")

    msg = MIMEMultipart("alternative")
    msg["From"] = _from_address()
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    def _send_blocking():
        with smtplib.SMTP(host, port, timeout=15) as s:
            if use_tls:
                s.starttls()
            if user and password:
                s.login(user, password)
            s.send_message(msg)

    try:
        await asyncio.get_event_loop().run_in_executor(None, _send_blocking)
        return {"status": "sent", "mode": "smtp", "detail": f"{host}:{port}"}
    except Exception as e:  # noqa: BLE001
        logger.warning("smtp_exception", exc_info=e)
        return {"status": "failed", "mode": "smtp", "detail": str(e)[:200]}


def _html_to_text_fallback(html: str) -> str:
    """Strip naive de tags HTML cuando el caller no pasó text."""
    import re
    txt = re.sub(r"<br\s*/?>", "\n", html)
    txt = re.sub(r"</?p\b[^>]*>", "\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", "", txt)
    return re.sub(r"\n{3,}", "\n\n", txt).strip()
