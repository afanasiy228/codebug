"""C2 compensating control: paid tiers must carry proof the server granted them.

The Realtime Database rules currently let any authenticated user write their own
users/<login>/subscription node (a .write granted on the parent cascades and cannot
be revoked by the admin-only rule below it), so a client can self-grant PRO+. Until
the rules are fixed, the server marks every subscription it grants with a `source`
and can be told to disregard tiers that carry no such proof.
"""
import pytest


def _sub(tier="pro_plus", status="active", **extra):
    base = {"tier": tier, "status": status, "expiresAt": 4102444800000, "updatedAt": 2_000_000_000_000}
    base.update(extra)
    return base


def test_self_granted_tier_is_detected_as_unbacked(srv):
    srv.add_user("cheater")
    srv.db.data["users"]["cheater"]["subscription"] = _sub()

    assert srv.module._subscription_is_server_backed(_sub()) is False


def test_payment_granted_tier_is_backed(srv):
    assert srv.module._subscription_is_server_backed(_sub(source="payment")) is True
    assert srv.module._subscription_is_server_backed(
        _sub(lastPaymentTransactionId="tx-123")
    ) is True


def test_contest_granted_tier_is_backed(srv):
    assert srv.module._subscription_is_server_backed(_sub(source="contest")) is True


def test_free_tier_is_never_flagged(srv):
    assert srv.module._subscription_is_server_backed(_sub(tier="free")) is True
    assert srv.module._subscription_is_server_backed({}) is True


def test_grants_predating_the_cutoff_are_grandfathered(srv, monkeypatch):
    """Subscriptions granted before the marker existed must not be downgraded."""
    monkeypatch.setattr(srv.module, "SUBSCRIPTION_SOURCE_CUTOFF_MS", 3_000_000_000_000)
    old_grant = _sub(updatedAt=2_000_000_000_000)  # before the cutoff
    assert srv.module._subscription_is_server_backed(old_grant) is True


def test_audit_only_mode_does_not_downgrade(srv, monkeypatch):
    """Default deployment logs but keeps serving the tier - no false-positive damage."""
    monkeypatch.setattr(srv.module, "SUBSCRIPTION_REQUIRE_SOURCE", False)
    srv.add_user("cheater")
    srv.db.data["users"]["cheater"]["subscription"] = _sub()

    assert srv.module._subscription_tier_label("cheater") == "pro_plus"


def test_enforcing_mode_ignores_a_self_granted_tier(srv, monkeypatch):
    monkeypatch.setattr(srv.module, "SUBSCRIPTION_REQUIRE_SOURCE", True)
    srv.add_user("cheater")
    srv.db.data["users"]["cheater"]["subscription"] = _sub()

    assert srv.module._subscription_tier_label("cheater") == "free"
    assert srv.module._is_pro_active("cheater") is False
    assert srv.module._is_pro_plus_active("cheater") is False


def test_enforcing_mode_keeps_a_paid_subscription(srv, monkeypatch):
    monkeypatch.setattr(srv.module, "SUBSCRIPTION_REQUIRE_SOURCE", True)
    srv.add_user("payer")
    srv.db.data["users"]["payer"]["subscription"] = _sub(source="payment")

    assert srv.module._subscription_tier_label("payer") == "pro_plus"
    assert srv.module._is_pro_plus_active("payer") is True


def test_activation_stamps_the_payment_source(srv):
    srv.add_user("payer")
    srv.module._activate_paid_subscription("payer", "pro", "tx-abc", 100)

    stored = srv.db.data["users"]["payer"]["subscription"]
    assert stored["source"] == "payment"
    assert srv.module._subscription_is_server_backed(stored) is True
