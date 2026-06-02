"""
Transactional email delivery via the Resend API (https://resend.com).

Configuration (environment variables):
    RESEND_API_KEY   - Resend API key. If unset, emails are logged instead of
                       sent, so local/dev and tests work without credentials.
    EMAIL_FROM       - "From" address. Defaults to Resend's shared sandbox
                       sender, which can only deliver to the account owner.

`send_email` never raises: it returns True on a successful send and False
otherwise (missing key, network error, API error), leaving callers free to
respond with a generic message regardless of delivery outcome.
"""
import logging
from os import getenv

import httpx


logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_FROM = "onboarding@resend.dev"


def send_email(to: str, subject: str, html: str) -> bool:
    """Send an email through Resend. Returns True if it was sent."""
    api_key = getenv("RESEND_API_KEY")
    sender = getenv("EMAIL_FROM", DEFAULT_FROM)

    if not api_key:
        logger.warning(
            "RESEND_API_KEY not set; not sending email to %s (subject: %s)", to, subject
        )
        return False

    try:
        response = httpx.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"from": sender, "to": [to], "subject": subject, "html": html},
            timeout=10.0,
        )
        response.raise_for_status()
        logger.info("Sent email to %s (subject: %s)", to, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False
