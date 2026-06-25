import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from bookieskit.orchestration import appauth


@pytest.fixture
def keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv, pub


def test_build_app_jwt_has_expected_claims(keypair):
    priv, pub = keypair
    tok = appauth.build_app_jwt(123, priv, now=1000)
    decoded = jwt.decode(
        tok, pub, algorithms=["RS256"], options={"verify_exp": False}
    )
    assert decoded["iss"] == "123"
    assert decoded["iat"] == 940      # now - 60 (clock-skew slack)
    assert decoded["exp"] == 1540     # now + 540 (under GitHub's 10-min cap)


def test_exchange_posts_bearer_jwt_to_installation_endpoint():
    calls = {}

    def fake_http(url, *, bearer):
        calls["url"] = url
        calls["bearer"] = bearer
        return {"token": "ghs_abc", "expires_at": "2026-06-25T16:00:00Z"}

    out = appauth.exchange_jwt_for_token("JWT", 999, http=fake_http)
    assert out["token"] == "ghs_abc"
    assert calls["url"].endswith("/app/installations/999/access_tokens")
    assert calls["bearer"] == "JWT"


def test_mint_composes_jwt_and_exchange(keypair):
    priv, _ = keypair
    seen = {}

    def fake_http(url, *, bearer):
        seen["bearer_is_jwt"] = bearer.count(".") == 2  # header.payload.sig
        return {"token": "ghs_xyz", "expires_at": "2026-06-25T16:00:00Z"}

    out = appauth.mint_installation_token(
        app_id=1, private_key_pem=priv, installation_id=2, now=1000,
        http=fake_http,
    )
    assert out == {"token": "ghs_xyz", "expires_at": "2026-06-25T16:00:00Z"}
    assert seen["bearer_is_jwt"]


def test_token_is_fresh_true_when_far_from_expiry():
    cached = {"token": "t", "expires_at": "2026-06-25T16:00:00Z"}
    # expiry = 2026-06-25T16:00:00Z = 1782403200; now well before it
    assert appauth.token_is_fresh(cached, now=1782403200 - 600) is True
    assert appauth.token_is_fresh(cached, now=1782403200 - 60) is False  # <120s
    assert appauth.token_is_fresh({"expires_at": "bad"}, now=0) is False
