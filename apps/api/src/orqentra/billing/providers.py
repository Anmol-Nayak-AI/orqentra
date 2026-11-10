"""Billing provider boundary. Razorpay TEST only; no live charges or provider request retries."""

import base64
import hashlib
import hmac
import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any, Protocol

from orqentra.core.config import Settings
from orqentra.execution.provider import NoRedirect


class BillingUnavailable(RuntimeError):
    pass


class BillingRejected(BillingUnavailable):
    pass


class BillingProvider(Protocol):
    def verify(self, body: bytes, signature: str) -> bool: ...
    def fetch_subscription(self, external_id: str) -> dict[str, Any]: ...
    def fetch_plan(self, plan_id: str) -> dict[str, Any]: ...
    def create_subscription(self, plan_id: str, notes: dict[str, str]) -> dict[str, Any]: ...
    def cancel_subscription(self, external_id: str) -> dict[str, Any]: ...
    def invoices(self, external_id: str, offset: int) -> dict[str, Any]: ...


class DisabledBillingProvider:
    def verify(self, body: bytes, signature: str) -> bool:
        raise BillingUnavailable("billing_unavailable")

    def fetch_subscription(self, external_id: str) -> dict[str, Any]:
        raise BillingUnavailable("billing_unavailable")

    def fetch_plan(self, plan_id: str) -> dict[str, Any]:
        raise BillingUnavailable("billing_unavailable")

    def create_subscription(self, plan_id: str, notes: dict[str, str]) -> dict[str, Any]:
        raise BillingUnavailable("billing_unavailable")

    def cancel_subscription(self, external_id: str) -> dict[str, Any]:
        raise BillingUnavailable("billing_unavailable")

    def invoices(self, external_id: str, offset: int) -> dict[str, Any]:
        raise BillingUnavailable("billing_unavailable")


class RazorpayTestProvider:
    def __init__(self, settings: Settings):
        if (
            settings.billing_provider != "razorpay"
            or not settings.razorpay_key_id
            or not settings.razorpay_key_secret
            or not settings.razorpay_webhook_secret
        ):
            raise BillingUnavailable("billing_unavailable")
        self.settings = settings

    def verify(self, body: bytes, signature: str) -> bool:
        if not re.fullmatch(r"[a-f0-9]{64}", signature):
            return False
        secrets = [
            self.settings.razorpay_webhook_secret,
            self.settings.razorpay_previous_webhook_secret
            if self.settings.razorpay_previous_webhook_secret_expires_at
            and self.settings.razorpay_previous_webhook_secret_expires_at > datetime.now(UTC)
            else None,
        ]
        return bool(
            sum(
                hmac.compare_digest(
                    hmac.new(secret.get_secret_value().encode(), body, hashlib.sha256).hexdigest(),
                    signature,
                )
                for secret in secrets
                if secret
            )
        )

    def _request(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        assert self.settings.razorpay_key_id and self.settings.razorpay_key_secret
        credentials = (
            self.settings.razorpay_key_id.get_secret_value()
            + ":"
            + self.settings.razorpay_key_secret.get_secret_value()
        )
        request = urllib.request.Request(
            "https://api.razorpay.com/v1/" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": "Basic " + base64.b64encode(credentials.encode()).decode(),
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST" if body is not None else "GET",
        )
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
                raw = response.read(262145)
            if len(raw) > 262144:
                raise ValueError
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError
            return data
        except urllib.error.HTTPError as error:
            if error.code in {400, 401, 403, 404, 422}:
                raise BillingRejected("billing_provider_rejected") from None
            raise BillingUnavailable("billing_provider_request_uncertain") from None
        except (ValueError, urllib.error.URLError, TimeoutError):
            raise BillingUnavailable("billing_provider_request_uncertain") from None

    def _id(self, value: str, prefix: str) -> str:
        if not re.fullmatch(prefix + r"_[A-Za-z0-9]{1,90}", value):
            raise BillingUnavailable("invalid_provider_reference")
        return value

    def fetch_subscription(self, external_id: str) -> dict[str, Any]:
        data = self._request("subscriptions/" + self._id(external_id, "sub"))
        if data.get("id") != external_id:
            raise BillingUnavailable("provider_binding_mismatch")
        return data

    def fetch_plan(self, plan_id: str) -> dict[str, Any]:
        data = self._request("plans/" + self._id(plan_id, "plan"))
        if data.get("id") != plan_id:
            raise BillingUnavailable("provider_binding_mismatch")
        return data

    def create_subscription(self, plan_id: str, notes: dict[str, str]) -> dict[str, Any]:
        if not self.settings.billing_test_actions_enabled:
            raise BillingUnavailable("billing_test_actions_disabled")
        return self._request(
            "subscriptions",
            {
                "plan_id": self._id(plan_id, "plan"),
                "total_count": self.settings.billing_test_total_cycles,
                "quantity": 1,
                "customer_notify": False,
                "notes": notes,
            },
        )

    def cancel_subscription(self, external_id: str) -> dict[str, Any]:
        if not self.settings.billing_test_actions_enabled:
            raise BillingUnavailable("billing_test_actions_disabled")
        return self._request(
            "subscriptions/" + self._id(external_id, "sub") + "/cancel", {"cancel_at_cycle_end": 1}
        )

    def invoices(self, external_id: str, offset: int) -> dict[str, Any]:
        if not 0 <= offset <= 1000:
            raise BillingUnavailable("invoice_page_limit")
        return self._request(
            "invoices?subscription_id="
            + self._id(external_id, "sub")
            + "&count=50&skip="
            + str(offset)
        )


def provider(settings: Settings) -> BillingProvider:
    return (
        RazorpayTestProvider(settings)
        if settings.billing_provider == "razorpay"
        else DisabledBillingProvider()
    )
