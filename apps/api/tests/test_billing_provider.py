import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from orqentra.billing.providers import (
    BillingUnavailable,
    DisabledBillingProvider,
    RazorpayTestProvider,
)
from orqentra.core.config import Settings


def test_billing_default_denial_and_reject_live_keys():
    assert Settings().billing_provider == "disabled"
    with pytest.raises(BillingUnavailable):
        DisabledBillingProvider().fetch_subscription("sub_synthetic")
    with pytest.raises(ValidationError):
        Settings(RAZORPAY_KEY_ID="rzp_live_synthetic")
    with pytest.raises(ValidationError):
        Settings(billing_provider="razorpay")


def test_raw_signature_and_rotated_secret():
    config = Settings(
        billing_provider="razorpay",
        RAZORPAY_KEY_ID="rzp_test_synthetic",
        RAZORPAY_KEY_SECRET="synthetic",
        RAZORPAY_WEBHOOK_SECRET="current",
        RAZORPAY_PREVIOUS_WEBHOOK_SECRET="previous",
        RAZORPAY_PREVIOUS_WEBHOOK_SECRET_EXPIRES_AT=datetime.now(UTC) + timedelta(hours=24),
    )
    adapter = RazorpayTestProvider(config)
    raw = b'{"synthetic":true}'
    signature = hmac.new(b"previous", raw, hashlib.sha256).hexdigest()
    assert adapter.verify(raw, signature)
    expired = config.model_copy(
        update={
            "razorpay_previous_webhook_secret_expires_at": datetime.now(UTC) - timedelta(seconds=1)
        }
    )
    assert not RazorpayTestProvider(expired).verify(raw, signature)
    current_signature = hmac.new(b"current", raw, hashlib.sha256).hexdigest()
    assert RazorpayTestProvider(expired).verify(raw, current_signature)
    assert not adapter.verify(raw + b" ", signature)
    assert not adapter.verify(raw, "invalid")
    with pytest.raises(BillingUnavailable):
        adapter.fetch_subscription("../escape")
