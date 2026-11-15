import pytest

from pydantic import ValidationError
from stitch.auth.claims import TokenClaims
from stitch.auth.permissions import RESOURCE_READ, SOURCE_READ_WM


class TestTokenClaimsConstruction:
    def test_minimal_claims(self):
        claims = TokenClaims(sub="auth0|abc123")

        assert claims.sub == "auth0|abc123"
        assert claims.email is None
        assert claims.name is None
        assert claims.raw == {}

    def test_full_claims(self):
        claims = TokenClaims(
            sub="auth0|abc123",
            email="user@example.com",
            name="Jane Doe",
            raw={"custom": "value"},
        )

        assert claims.sub == "auth0|abc123"
        assert claims.email == "user@example.com"
        assert claims.name == "Jane Doe"
        assert claims.raw["custom"] == "value"

    def test_sub_is_required(self):
        with pytest.raises(ValidationError):
            TokenClaims()

    def test_raw_defaults_to_empty_dict(self):
        claims1 = TokenClaims(sub="user1")
        claims2 = TokenClaims(sub="user2")

        claims1.raw["key"] = "value"

        assert "key" not in claims2.raw

    def test_uuid_sub(self):
        claims = TokenClaims(sub="550e8400-e29b-41d4-a716-446655440000")
        assert claims.sub == "550e8400-e29b-41d4-a716-446655440000"

    def test_pipe_sub(self):
        claims = TokenClaims(sub="auth0|abc123")
        assert claims.sub == "auth0|abc123"


class TestTokenClaimsPermissions:
    def test_permissions_defaults_to_empty_frozenset(self):
        claims = TokenClaims(sub="auth0|abc")

        assert claims.permissions == frozenset()
        assert isinstance(claims.permissions, frozenset)

    def test_permissions_accepts_list_and_coerces_to_frozenset(self):
        claims = TokenClaims(
            sub="auth0|abc",
            permissions=[RESOURCE_READ, SOURCE_READ_WM],
        )

        assert claims.permissions == frozenset({RESOURCE_READ, SOURCE_READ_WM})
        assert isinstance(claims.permissions, frozenset)

    def test_permissions_accepts_frozenset_directly(self):
        source = frozenset({"a", "b"})
        claims = TokenClaims(sub="auth0|abc", permissions=source)

        assert claims.permissions == source
        assert isinstance(claims.permissions, frozenset)

    def test_permissions_deduplicates(self):
        claims = TokenClaims(sub="auth0|abc", permissions=["a", "a", "b"])

        assert claims.permissions == frozenset({"a", "b"})
        assert len(claims.permissions) == 2

    def test_permissions_is_immutable_after_construction(self):
        claims = TokenClaims(sub="auth0|abc", permissions=["a"])

        with pytest.raises(AttributeError):
            claims.permissions.add("b")
