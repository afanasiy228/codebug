"""Regression tests for H1: the Platega callback must be idempotent and verified.

_activate_paid_subscription stacks the period onto the current expiry, and nothing
recorded that a transaction had already been confirmed - so replaying one CONFIRMED
callback granted another 30 days each time. Payment providers retry callbacks as
normal operation, so this fired without an attacker.
"""
import pytest

MERCHANT = "merchant-test-id"
SECRET = "callback-shared-secret"
TX = "tx-0001"


@pytest.fixture
def pay(srv, monkeypatch):
    monkeypatch.setattr(srv.module, "PLATEGA_MERCHANT_ID", MERCHANT)
    monkeypatch.setattr(srv.module, "PLATEGA_SECRET", SECRET)
    srv.add_user("payer")
    srv.db.data.setdefault("subscriptions", {}).setdefault("payments", {})[TX] = {
        "provider": "platega",
        "login": "payer",
        "tier": "pro",
        "amount": 114.0,
        "currency": "RUB",
        "status": "PENDING",
        "transactionId": TX,
    }
    return srv


def _post(srv, body, merchant=MERCHANT, secret=SECRET):
    return srv.client.post(
        "/payments/platega/callback",
        json=body,
        headers={"X-MerchantId": merchant, "X-Secret": secret},
    )


def _expiry(srv, login="payer"):
    return srv.db.data["users"][login].get("subscription", {}).get("expiresAt")


def test_first_confirmed_callback_activates_the_subscription(pay):
    res = _post(pay, {"id": TX, "status": "CONFIRMED", "amount": 114.0, "currency": "RUB"})
    assert res.status_code == 200, res.get_json()
    assert pay.db.data["users"]["payer"]["subscription"]["status"] == "active"
    assert _expiry(pay) is not None


def test_replayed_confirmed_callback_does_not_extend_the_subscription(pay):
    """The core of H1: a retried webhook must not grant another period."""
    _post(pay, {"id": TX, "status": "CONFIRMED", "amount": 114.0, "currency": "RUB"})
    first_expiry = _expiry(pay)

    for _ in range(5):
        res = _post(pay, {"id": TX, "status": "CONFIRMED", "amount": 114.0, "currency": "RUB"})
        assert res.status_code == 200, res.get_json()

    assert _expiry(pay) == first_expiry, "replayed webhook extended the subscription"


def test_callback_with_wrong_secret_is_rejected(pay):
    res = _post(pay, {"id": TX, "status": "CONFIRMED"}, secret="wrong")
    assert res.status_code == 403
    assert "subscription" not in pay.db.data["users"]["payer"]


def test_callback_with_wrong_merchant_is_rejected(pay):
    res = _post(pay, {"id": TX, "status": "CONFIRMED"}, merchant="wrong")
    assert res.status_code == 403


def test_callback_with_mismatched_amount_is_rejected(pay):
    res = _post(pay, {"id": TX, "status": "CONFIRMED", "amount": 1.0, "currency": "RUB"})
    assert res.status_code == 400, res.get_json()
    assert res.get_json()["code"] == "PAYMENT_AMOUNT_MISMATCH"
    assert "subscription" not in pay.db.data["users"]["payer"]


def test_callback_with_mismatched_currency_is_rejected(pay):
    res = _post(pay, {"id": TX, "status": "CONFIRMED", "amount": 114.0, "currency": "USD"})
    assert res.status_code == 400, res.get_json()
    assert "subscription" not in pay.db.data["users"]["payer"]


def test_confirmed_after_chargeback_is_refused(pay):
    _post(pay, {"id": TX, "status": "CONFIRMED", "amount": 114.0, "currency": "RUB"})
    _post(pay, {"id": TX, "status": "CHARGEBACKED"})
    assert pay.db.data["users"]["payer"]["subscription"]["status"] == "disabled"

    res = _post(pay, {"id": TX, "status": "CONFIRMED", "amount": 114.0, "currency": "RUB"})
    assert res.status_code in (200, 409)
    assert pay.db.data["users"]["payer"]["subscription"]["status"] == "disabled", (
        "a CONFIRMED replay re-enabled a charged-back subscription"
    )


def test_unknown_transaction_is_rejected(pay):
    res = _post(pay, {"id": "tx-does-not-exist", "status": "CONFIRMED"})
    assert res.status_code == 404


def test_transaction_id_with_firebase_path_characters_is_rejected(pay):
    res = _post(pay, {"id": "tx/../../admins/attacker", "status": "CONFIRMED"})
    assert res.status_code == 400, res.get_json()
