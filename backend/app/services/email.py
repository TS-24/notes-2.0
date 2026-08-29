"""
Outbound email, over plain SMTP.

Deliberately small and dependency-free: the standard library speaks SMTP, and a
provider SDK would be a pinned dependency plus a vendor lock for what is, today,
one message type. Swapping in Postmark/SES/Resend later is a change to
`send_email` alone.

With `SMTP_HOST` unset the message is logged rather than sent — at WARNING, so
it survives the default log level rather than vanishing at INFO. That is the
state in tests and in a bare `docker compose up`, and it means a missing mail
configuration degrades to "the link is in the logs" instead of a 500 in the
middle of the reset flow.
"""

import logging
import smtplib
from email.message import EmailMessage

from ..core.config import (
    FRONTEND_ORIGIN,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_STARTTLS,
    SMTP_USER,
)

logger = logging.getLogger(__name__)


def send_email(
    to: str, subject: str, body: str, *, raise_on_error: bool = False
) -> None:
    """Send one plain-text email, or log it when SMTP is not configured.

    Called from a background task, so a slow or unreachable server delays
    nothing the caller is waiting on, and a send failure is logged rather than
    raised — there is nowhere useful for it to go. `raise_on_error` is for the
    CLI check, which wants the failure in the foreground.
    """
    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    if not SMTP_HOST:
        # WARNING, not INFO: nothing in this app configures logging, so the root
        # logger sits at its default WARNING and an INFO line here is discarded
        # unseen. The whole point of this branch is that the link stays
        # recoverable when mail is not set up.
        logger.warning(
            "SMTP_HOST is not set; email not sent. Message follows.\n"
            "To: %s\nSubject: %s\n\n%s",
            to,
            subject,
            body,
        )
        return

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_STARTTLS:
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD or "")
            server.send_message(message)
    except (OSError, smtplib.SMTPException):
        if raise_on_error:
            raise
        # A background task, so raising would only reach its own logging. The
        # useful thing is the message itself: logged here, the reset link is
        # still recoverable through an outage or a misconfigured relay.
        logger.warning(
            "SMTP send to %s failed; message follows.\nSubject: %s\n\n%s",
            to,
            subject,
            body,
            exc_info=True,
        )


def send_password_reset(to: str, token: str) -> None:
    """The one message this module exists for.

    Takes the raw token and builds the link here so the URL shape lives in one
    place. Plain text on purpose — one line to read, one link to click, and
    nothing that renders differently in two mail clients.
    """
    link = f"{FRONTEND_ORIGIN}/reset-password?token={token}"
    body = (
        "Someone asked to reset the password for your Restyle account.\n\n"
        f"Open this link to choose a new one:\n{link}\n\n"
        "The link works once and expires in an hour. If this wasn't you, you "
        "can ignore this email — your password has not changed.\n"
    )
    send_email(to, "Reset your Restyle password", body)
