"""BetPawa probability deobfuscation.

BetPawa hides the per-outcome probability behind a base64-encoded JSON
payload `{"win": <int>, "refund": <int>, "key": <int>}`. Each of `win`
and `refund` is recovered by 3-way XORing the value with a global
constant and the per-bet `key`, then reinterpreting the 64 bits as an
IEEE 754 float64 (big-endian).

This module is private: it's imported by the BetPawa branch of
`bookieskit.markets.parser`. Callers who need ad-hoc deobfuscation can
import `decode_betpawa_probability` directly, but it's not re-exported
from the top-level package.
"""

import base64
import json
import struct

# 64-bit XOR constant baked into BetPawa's client-side decoder.
_GLOBAL_XOR_KEY_HEX = "9E3779B97F4A7C15"
_TWO_64 = 1 << 64


def decode_betpawa_probability(
    blob: str | None,
) -> tuple[float | None, float | None]:
    """Decode a BetPawa price.probability base64 blob to (win, refund).

    Returns (None, None) on any decode failure (bad base64, malformed
    JSON, missing `key`, etc.). When `key` is present but `win` or
    `refund` is missing/malformed individually, only that field is None.
    Never raises.
    """
    if not blob or not isinstance(blob, str):
        return (None, None)

    try:
        raw = base64.urlsafe_b64decode(blob + "===")
    except Exception:
        return (None, None)

    try:
        decoded = json.loads(raw)
    except Exception:
        return (None, None)
    if not isinstance(decoded, dict):
        return (None, None)

    key = decoded.get("key")
    if key is None:
        return (None, None)

    return (
        _decode_one(decoded.get("win"), key),
        _decode_one(decoded.get("refund"), key),
    )


def _decode_one(value: object, key: object) -> float | None:
    """Decode one obfuscated 64-bit value with the given XOR key. None on
    any failure."""
    if value is None:
        return None
    try:
        v_hex = _decimal_string_to_hex64(str(value))
        k_hex = _decimal_string_to_hex64(str(key))
        result_hex = _hex_xor64(v_hex, _GLOBAL_XOR_KEY_HEX, k_hex)
        return _hex64_to_float64(result_hex)
    except Exception:
        return None


def _decimal_string_to_hex64(dec_string: str) -> str:
    """Convert a (possibly negative, possibly larger than 2^53) decimal
    string into a 16-char uppercase hex string representing the value
    mod 2^64."""
    s = dec_string.strip()
    negative = False
    if s.startswith("-"):
        negative = True
        s = s[1:]
    if s == "":
        s = "0"
    val = int(s, 10) % _TWO_64
    if negative and val != 0:
        val = (_TWO_64 - val) % _TWO_64
    return f"{val:016X}"


def _hex_xor64(hex1: str, hex2: str, hex3: str) -> str:
    """3-way XOR of three 64-bit hex strings."""
    v1 = int(hex1, 16)
    v2 = int(hex2, 16)
    v3 = int(hex3, 16)
    r = (v1 ^ v2 ^ v3) & (_TWO_64 - 1)
    return f"{r:016X}"


def _hex64_to_float64(hex_str: str) -> float:
    """Reinterpret 16 hex chars as a big-endian IEEE 754 float64."""
    return struct.unpack(">d", bytes.fromhex(hex_str))[0]
