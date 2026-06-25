"""Mint GitHub App installation tokens so the autonomous loop acts as the App
(an identity the main ruleset bars from merging), not as the owner.

Split for testability: a pure JWT builder, an injectable HTTP exchange seam
(mirrors cli.py's _slack_post urllib seam), and a freshness predicate the token
cache uses. PyJWT is lazy-imported inside build_app_jwt so importing this module
never requires the [orchestration] extra.
"""

import datetime
import json
import urllib.request

_API = "https://api.github.com"


def build_app_jwt(app_id: int, private_key_pem: str, now: int) -> str:
    import jwt  # lazy: only needed when actually minting

    payload = {"iat": now - 60, "exp": now + 540, "iss": str(app_id)}
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


def _http_post(url: str, *, bearer: str) -> dict:
    req = urllib.request.Request(
        url,
        data=b"",
        method="POST",
        headers={
            "Authorization": "Bearer " + bearer,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def exchange_jwt_for_token(
    jwt_token: str, installation_id: int, *, http=_http_post
) -> dict:
    url = f"{_API}/app/installations/{installation_id}/access_tokens"
    return http(url, bearer=jwt_token)


def mint_installation_token(
    *,
    app_id: int,
    private_key_pem: str,
    installation_id: int,
    now: int,
    http=_http_post,
) -> dict:
    jwt_token = build_app_jwt(app_id, private_key_pem, now)
    resp = exchange_jwt_for_token(jwt_token, installation_id, http=http)
    return {"token": resp["token"], "expires_at": resp["expires_at"]}


def token_is_fresh(cached: dict, now: float, *, min_life_s: int = 120) -> bool:
    try:
        exp = (
            datetime.datetime.strptime(cached["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=datetime.timezone.utc)
            .timestamp()
        )
    except (KeyError, ValueError, TypeError):
        return False
    return exp - now > min_life_s
