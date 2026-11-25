"""
Paystack payment integration for Closer Tech / Joy.
"""
import hashlib
import hmac
import logging
import os
import uuid

import httpx

logger = logging.getLogger(__name__)

PAYSTACK_API = "https://api.paystack.co"


def _secret() -> str:
    key = os.getenv("PAYSTACK_SECRET_KEY", "")
    if not key:
        raise EnvironmentError("PAYSTACK_SECRET_KEY is not set in .env")
    return key


def create_payment_link(
    email: str,
    amount_usd: int,
    reference: str,
    metadata: dict,
    currency: str = "USD",
) -> str:
    """
    Call Paystack to initialise a transaction.
    Returns the hosted checkout URL to send the customer.
    Amount must be in the smallest currency unit (cents for USD, kobo for NGN).
    """
    amount_minor = amount_usd * 100  # cents / kobo

    callback_url = os.getenv("BASE_URL", "https://joy.aicloser.tech") + "/payment/confirm"

    try:
        resp = httpx.post(
            f"{PAYSTACK_API}/transaction/initialize",
            headers={"Authorization": f"Bearer {_secret()}", "Content-Type": "application/json"},
            json={
                "email": email,
                "amount": amount_minor,
                "currency": currency,
                "reference": reference,
                "metadata": metadata,
                "callback_url": callback_url,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status"):
            url = data["data"]["authorization_url"]
            logger.info("Paystack link created: ref=%s", reference)
            return url
        raise RuntimeError(f"Paystack error: {data.get('message', 'Unknown')}")
    except httpx.HTTPError as exc:
        logger.error("Paystack HTTP error: %s", exc)
        raise


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    """Validate that the webhook actually came from Paystack."""
    expected = hmac.new(_secret().encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")


def make_reference(lead_id: int) -> str:
    short = uuid.uuid4().hex[:8].upper()
    return f"JOY-{lead_id}-{short}"
