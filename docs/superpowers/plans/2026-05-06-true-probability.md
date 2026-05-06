# True-Probability Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `parse_markets` so each `Outcome` can carry the bookmaker's pre-margin "fair" probability (and optionally the void/refund probability) for the three platforms that expose it (SportyBet, MSport, BetPawa with deobfuscation). Betway and Bet9ja remain unsupported per their APIs.

**Architecture:** Add two optional fields (`true_probability`, `void_probability`) to the existing frozen `Outcome` dataclass — defaults of `None` keep all existing call sites intact. Add a `probability` keyword to `parse_markets` (`Literal["off", "true", "with_void"]`, default `"off"`) that flows through each platform parser. BetPawa's obfuscated probability blob (base64 → JSON `{win, refund, key}` → 64-bit XOR with a global key + per-bet key → IEEE 754 float64 reinterpret) is decoded by a new private module `bookmakers/_betpawa_obfuscation.py`. All extractors are total: bad input → fields stay `None`, never raise.

**Tech Stack:** Python 3.11, stdlib only (dataclasses, base64, json, struct). pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-06-true-probability-design.md`

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `src/bookieskit/markets/types.py` | modify | Add `true_probability`, `void_probability` fields to `Outcome` |
| `src/bookieskit/markets/parser.py` | modify | Add `probability` keyword to `parse_markets`; thread it to per-platform parsers; populate the new fields where the platform supports it |
| `src/bookieskit/bookmakers/_betpawa_obfuscation.py` | create | BetPawa probability blob decoder (`decode_betpawa_probability` + private XOR helpers) |
| `src/bookieskit/__init__.py` | modify | Re-export `ProbabilityMode` |
| `tests/test_probability.py` | create | Unit tests for the deobfuscator + parser-level probability tests across all 5 platforms |
| `docs/markets.md` | modify | Add "Probabilities" section |

Each task ends with a commit.

---

## Task 1: Extend `Outcome` dataclass + add `ProbabilityMode` + thread the keyword (no behaviour change yet)

**Files:**
- Modify: `src/bookieskit/markets/types.py`
- Modify: `src/bookieskit/markets/parser.py`
- Create: `tests/test_probability.py`

This task is pure plumbing: it adds the two optional fields to `Outcome`, defines `ProbabilityMode`, adds a `probability` keyword arg to `parse_markets` and threads it down through every platform parser as a new keyword. No platform actually populates the new fields yet — that comes in Tasks 3–5. Existing call sites and existing tests stay green.

- [ ] **Step 1: Write the failing test**

Create `tests/test_probability.py`:

```python
"""Tests for true/void probability extraction across all 5 platforms."""

import json
from pathlib import Path

import pytest

from bookieskit.markets import parse_markets
from bookieskit.markets.types import Outcome
from bookieskit.markets.parser import ProbabilityMode  # noqa: F401  (Task 9 re-exports it)

FIXTURES = Path(__file__).parent / "fixtures" / "event_info"


def _load(platform: str, phase: str = "prematch") -> dict:
    with open(FIXTURES / platform / f"{phase}.json", encoding="utf-8") as f:
        return json.load(f)


def test_outcome_has_optional_probability_fields():
    """Outcome gains two optional float|None fields, default None."""
    o = Outcome(canonical_name="home", odds=2.41, platform_name="1")
    assert o.true_probability is None
    assert o.void_probability is None


def test_outcome_accepts_probability_kwargs():
    o = Outcome(
        canonical_name="home",
        odds=2.41,
        platform_name="1",
        true_probability=0.395274,
        void_probability=0.0,
    )
    assert o.true_probability == 0.395274
    assert o.void_probability == 0.0


def test_outcome_is_still_frozen():
    o = Outcome(canonical_name="home", odds=2.41, platform_name="1")
    with pytest.raises(AttributeError):
        o.true_probability = 0.5  # type: ignore[misc]


def test_parse_markets_default_off_leaves_probabilities_none():
    """Default mode must not populate probabilities — backward compatible."""
    d = _load("sportybet")
    markets = parse_markets(d, platform="sportybet")
    # Pick the first 1X2 market. If markets is empty the test is meaningless;
    # assert markets exists, then check first outcome has None probability.
    assert markets, "expected SportyBet prematch fixture to yield markets"
    first_market = next((m for m in markets if m.canonical_id == "1x2_ft"), None)
    assert first_market is not None
    assert first_market.outcomes
    o = first_market.outcomes[0]
    assert o.true_probability is None
    assert o.void_probability is None


def test_parse_markets_accepts_probability_kwarg_without_error():
    """The new keyword must be accepted by all 5 platforms (even ones that
    don't support probability extraction yet — their parsers must silently
    accept the kwarg)."""
    d = _load("sportybet")
    parse_markets(d, platform="sportybet", probability="off")
    parse_markets(d, platform="sportybet", probability="true")
    parse_markets(d, platform="sportybet", probability="with_void")
    # Same for the other 4 platforms — they accept the kwarg.
    parse_markets(_load("msport"), platform="msport", probability="with_void")
    parse_markets(_load("betpawa"), platform="betpawa", probability="with_void")
    parse_markets(_load("betway"), platform="betway", probability="with_void")
    parse_markets(_load("bet9ja"), platform="bet9ja", probability="with_void")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v`
Expected: failure on `test_outcome_has_optional_probability_fields` — `Outcome.__init__()` got an unexpected keyword `true_probability`, AND failure on `test_parse_markets_accepts_probability_kwarg_without_error` — `parse_markets() got an unexpected keyword argument 'probability'`.

- [ ] **Step 3: Modify `Outcome` to add the two optional fields**

Edit `src/bookieskit/markets/types.py`. Replace the `Outcome` dataclass with:

```python
@dataclass(frozen=True)
class Outcome:
    """A single outcome within a market.

    `true_probability` is the bookmaker's fair (pre-margin) probability
    estimate — across mutually exclusive outcomes of one market, these
    sum to ≈1, NOT to 1 + margin like 1/odds would. Populated only when
    the platform exposes it (SportyBet, MSport, BetPawa) AND the caller
    passes `probability="true"` or `probability="with_void"` to
    parse_markets.

    `void_probability` is the bookmaker's estimate of the bet being
    voided/refunded (e.g. event abandoned). Populated only when the
    platform exposes it (SportyBet, BetPawa) AND the caller passes
    `probability="with_void"`. Always None on MSport/Betway/Bet9ja.
    """

    canonical_name: str
    odds: float
    platform_name: str
    true_probability: float | None = None
    void_probability: float | None = None
```

- [ ] **Step 4: Add `ProbabilityMode` and `probability` keyword to `parse_markets`**

Edit `src/bookieskit/markets/parser.py`. At the top with the imports, add:

```python
from typing import Literal

ProbabilityMode = Literal["off", "true", "with_void"]


def _normalised_probability_mode(mode: object) -> ProbabilityMode:
    """Coerce arbitrary user input to a known ProbabilityMode value.

    Invalid mode strings silently become 'off' — matches the total-function
    contract used elsewhere in the lib (e.g. event_info._normalised_mode)."""
    if mode == "true" or mode == "with_void":
        return mode  # type: ignore[return-value]
    return "off"
```

Then change the `parse_markets` signature and dispatcher. The current function is:

```python
def parse_markets(
    response: dict,
    platform: str,
    registry: MarketRegistry | None = None,
) -> list[NormalizedMarket]:
    ...
    parsers = {
        "betpawa": _parse_betpawa,
        "sportybet": _parse_sportybet,
        "bet9ja": _parse_bet9ja,
        "betway": _parse_betway,
        "msport": _parse_msport,
    }
    parser = parsers.get(platform)
    if parser is None:
        return []
    return parser(response, registry)
```

Replace with:

```python
def parse_markets(
    response: dict,
    platform: str,
    registry: MarketRegistry | None = None,
    *,
    probability: ProbabilityMode = "off",
) -> list[NormalizedMarket]:
    """Parse raw event detail response into normalized markets.

    Args:
        response: Raw JSON from get_event_detail()
        platform: "betpawa", "sportybet", "bet9ja", "betway", or "msport"
        registry: Market registry to use (default: built-in 6 markets)
        probability: How much probability data to extract per outcome.
            "off" (default) — no probability parsing; both fields None.
            "true" — populate true_probability where the platform supports it.
            "with_void" — populate true_probability AND void_probability.
            Bet9ja and Betway don't expose probability — both fields stay
            None for them regardless of mode.

    Returns:
        List of NormalizedMarket for all recognized markets.
        Markets not in the registry are skipped.
    """
    if registry is None:
        registry = MarketRegistry()
    mode = _normalised_probability_mode(probability)

    parsers = {
        "betpawa": _parse_betpawa,
        "sportybet": _parse_sportybet,
        "bet9ja": _parse_bet9ja,
        "betway": _parse_betway,
        "msport": _parse_msport,
    }
    parser = parsers.get(platform)
    if parser is None:
        return []
    return parser(response, registry, mode)
```

Now every per-platform parser must accept the new third positional arg. Update each:

For `_parse_betpawa` (line 43): change signature to `(response, registry, mode)`. Mode is unused for now — pass through to internal helpers in Task 3.

```python
def _parse_betpawa(
    response: dict, registry: MarketRegistry, mode: ProbabilityMode = "off"
) -> list[NormalizedMarket]:
    """Parse BetPawa event detail response."""
    results: list[NormalizedMarket] = []
    markets = response.get("markets", [])

    for market_data in markets:
        market_type = market_data.get("marketType", {})
        market_id = str(market_type.get("id", market_data.get("id", "")))
        mapping = registry.get_by_platform_id("betpawa", market_id)
        if mapping is None:
            continue

        if mapping.parameterized:
            results.append(
                _parse_betpawa_parameterized(market_data, mapping, mode)
            )
        else:
            results.append(_parse_betpawa_simple(market_data, mapping, mode))

    return results
```

Then `_parse_betpawa_simple` and `_parse_betpawa_parameterized` each gain a third arg `mode: ProbabilityMode = "off"` that is currently unused in their body — they'll start using it in Task 3.

Apply the same pattern to:
- `_parse_sportybet(response, registry, mode)` and its `_simple` / `_parameterized` helpers (line 167+)
- `_parse_bet9ja(response, registry, mode)` and its `_key` helper (line 304+) — bet9ja never reads `mode`, but the signature must accept it
- `_parse_betway(response, registry, mode)` (line 465+) — betway never reads `mode`
- `_parse_msport(response, registry, mode)` and its `_simple` / `_parameterized` helpers (line 730+)

For Bet9ja and Betway (which won't ever read `mode`), use the `_mode` underscore convention to signal intentional unused parameter:

```python
def _parse_bet9ja(
    response: dict, registry: MarketRegistry, _mode: ProbabilityMode = "off"
) -> list[NormalizedMarket]:
```

The full diff for parser.py is mechanical — every platform-parser function and its `_simple` / `_parameterized` / `_key` sub-helpers gets a third positional arg. The bodies are unchanged.

- [ ] **Step 5: Run all tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v`
Expected: 5 passed.

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: full project suite passes (existing parser tests + event_info tests + new probability tests).

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/markets/parser.py src/bookieskit/markets/types.py tests/test_probability.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/bookieskit/markets/types.py src/bookieskit/markets/parser.py tests/test_probability.py
git commit -m "feat(markets): add probability keyword and Outcome fields (no-op plumbing)"
```

---

## Task 2: BetPawa deobfuscation helper module

**Files:**
- Create: `src/bookieskit/bookmakers/_betpawa_obfuscation.py`
- Modify: `tests/test_probability.py` (append deobfuscator unit tests)

Implements the user-supplied algorithm: base64-decode the blob to JSON `{win, refund, key}`, then for each of `win` and `refund` perform a 3-way 64-bit XOR with a global constant and the per-bet key, then reinterpret the resulting 64 bits as IEEE 754 float64 (big-endian).

Sample blob and expected output (verified via running the user's exact algorithm):

```python
SAMPLE_BLOB = "eyJ3aW4iOi0yOTA4Nzc4MTkyNTk2MTE5Njc5LCJyZWZ1bmQiOi0xNjk1MzY3MDg2NzY0MDYwNTQ0LCJrZXkiOjg1MjUyMDk3OTc5NTQzOTkzODF9"
# decode_betpawa_probability(SAMPLE_BLOB) == (0.393141, 0.0)
```

- [ ] **Step 1: Write failing tests for the deobfuscator**

Append to `tests/test_probability.py`:

```python
from bookieskit.bookmakers._betpawa_obfuscation import decode_betpawa_probability


SAMPLE_BLOB = (
    "eyJ3aW4iOi0yOTA4Nzc4MTkyNTk2MTE5Njc5LCJyZWZ1bmQiOi0xNjk1MzY3MDg2NzY0MDYwNTQ0"
    "LCJrZXkiOjg1MjUyMDk3OTc5NTQzOTkzODF9"
)


def test_decode_sample_blob():
    """User-supplied sample blob decodes to a pinned (win, refund) tuple."""
    win, refund = decode_betpawa_probability(SAMPLE_BLOB)
    assert win == pytest.approx(0.393141)
    assert refund == 0.0


def test_decode_none_input():
    assert decode_betpawa_probability(None) == (None, None)


def test_decode_empty_string():
    assert decode_betpawa_probability("") == (None, None)


def test_decode_bad_base64():
    assert decode_betpawa_probability("not-base64!!!") == (None, None)


def test_decode_truncated_json():
    """Valid base64 but the decoded bytes don't parse as JSON."""
    import base64 as _b64
    truncated = _b64.urlsafe_b64encode(b'{"win":').decode()
    assert decode_betpawa_probability(truncated) == (None, None)


def test_decode_missing_key_field():
    """Without the per-bet key, neither value can be XOR'd to a real float."""
    import base64 as _b64
    payload = _b64.urlsafe_b64encode(
        b'{"win":-2908778192596119679,"refund":-1695367086764060544}'
    ).decode()
    assert decode_betpawa_probability(payload) == (None, None)


def test_decode_missing_win_field_keeps_refund():
    """If only `win` is missing, refund still decodes (per-field independence)."""
    import base64 as _b64
    payload = _b64.urlsafe_b64encode(
        b'{"refund":-1695367086764060544,"key":852520979795439938}'
    ).decode()
    win, refund = decode_betpawa_probability(payload)
    assert win is None
    assert refund == 0.0


def test_decode_missing_refund_field_keeps_win():
    """If only `refund` is missing, win still decodes."""
    import base64 as _b64
    payload = _b64.urlsafe_b64encode(
        b'{"win":-2908778192596119679,"key":852520979795439938}'
    ).decode()
    win, refund = decode_betpawa_probability(payload)
    assert win == pytest.approx(0.393141)
    assert refund is None


def test_decode_non_integer_values():
    """Win/refund/key as non-numeric strings should yield Nones, not raise."""
    import base64 as _b64
    payload = _b64.urlsafe_b64encode(
        b'{"win":"abc","refund":"def","key":"ghi"}'
    ).decode()
    assert decode_betpawa_probability(payload) == (None, None)
```

- [ ] **Step 2: Run, verify all 9 tests fail with import error**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v -k decode_`
Expected: ImportError on `decode_betpawa_probability` (module doesn't exist yet).

- [ ] **Step 3: Create the deobfuscation module**

Create `src/bookieskit/bookmakers/_betpawa_obfuscation.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v -k decode_`
Expected: 9 passed.

Run: `.venv/Scripts/python.exe -m ruff check src/bookieskit/bookmakers/_betpawa_obfuscation.py tests/test_probability.py`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/bookmakers/_betpawa_obfuscation.py tests/test_probability.py
git commit -m "feat(probability): BetPawa deobfuscation helper module"
```

---

## Task 3: BetPawa parser integration

**Files:**
- Modify: `src/bookieskit/markets/parser.py`
- Modify: `tests/test_probability.py`

Wire the deobfuscator into `_parse_betpawa_simple` and `_parse_betpawa_parameterized`. When `mode != "off"`, decode each `price.probability` blob and populate `Outcome.true_probability`. When `mode == "with_void"`, also populate `Outcome.void_probability`.

Fixture facts (BetPawa 1X2-FT prematch, market type id `3743`):
- Outcome `"1"` (home): odds=2.41, win=0.395274, refund=0.0
- Outcome `"X"` (draw): odds=3.29, win=0.289197, refund=0.0
- Outcome `"2"` (away): odds=3.02, win=0.315522, refund=0.0
- Sum win = 0.999993 (confirms fair-prob semantics, not implied)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_probability.py`:

```python
def test_betpawa_probability_off_keeps_outcomes_clean():
    d = _load("betpawa")
    markets = parse_markets(d, platform="betpawa", probability="off")
    m = next(m for m in markets if m.canonical_id == "1x2_ft")
    for o in m.outcomes:
        assert o.true_probability is None
        assert o.void_probability is None


def test_betpawa_probability_true_populates_true_only():
    d = _load("betpawa")
    markets = parse_markets(d, platform="betpawa", probability="true")
    m = next(m for m in markets if m.canonical_id == "1x2_ft")
    by_name = {o.canonical_name: o for o in m.outcomes}
    # canonical names from the registry; assert all three present
    for name in ("home", "draw", "away"):
        assert name in by_name, f"missing {name}"
        o = by_name[name]
        assert o.true_probability is not None and 0 < o.true_probability < 1
        assert o.void_probability is None  # mode='true' must NOT populate void


def test_betpawa_probability_with_void_populates_both():
    d = _load("betpawa")
    markets = parse_markets(d, platform="betpawa", probability="with_void")
    m = next(m for m in markets if m.canonical_id == "1x2_ft")
    by_name = {o.canonical_name: o for o in m.outcomes}
    # Pinned values from the captured fixture (win/refund decoded via the helper)
    assert by_name["home"].true_probability == pytest.approx(0.395274)
    assert by_name["home"].void_probability == 0.0
    assert by_name["draw"].true_probability == pytest.approx(0.289197)
    assert by_name["draw"].void_probability == 0.0
    assert by_name["away"].true_probability == pytest.approx(0.315522)
    assert by_name["away"].void_probability == 0.0


def test_betpawa_probability_parameterized_market():
    """O/U 2.5 — verify probability flows into the parameterized branch too."""
    d = _load("betpawa")
    markets = parse_markets(d, platform="betpawa", probability="with_void")
    ou = next(m for m in markets if m.canonical_id == "over_under_ft")
    assert 2.5 in ou.lines
    for o in ou.lines[2.5]:
        assert o.true_probability is not None
        assert 0 < o.true_probability < 1
        assert o.void_probability == 0.0  # BetPawa refund is 0 across the fixture
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v -k betpawa`
Expected: 4 failures (probabilities are still all None — Task 1 only plumbed the kwarg).

- [ ] **Step 3: Wire the deobfuscator into BetPawa parsers**

At the top of `src/bookieskit/markets/parser.py`, add the import:

```python
from bookieskit.bookmakers._betpawa_obfuscation import decode_betpawa_probability
```

Replace `_parse_betpawa_simple` body. The current Outcome construction is:

```python
outcomes.append(
    Outcome(
        canonical_name=canonical,
        odds=odds,
        platform_name=price_name,
    )
)
```

Replace with:

```python
true_p = void_p = None
if mode != "off":
    win, refund = decode_betpawa_probability(price.get("probability"))
    true_p = win
    if mode == "with_void":
        void_p = refund
outcomes.append(
    Outcome(
        canonical_name=canonical,
        odds=odds,
        platform_name=price_name,
        true_probability=true_p,
        void_probability=void_p,
    )
)
```

Apply the identical pattern inside `_parse_betpawa_parameterized`'s inner `for price in row.get("prices", []):` loop where `Outcome(...)` is constructed.

Both functions already have `mode: ProbabilityMode = "off"` as their third arg from Task 1.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v -k betpawa`
Expected: 4 passed.

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: full suite passes.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_probability.py
git commit -m "feat(probability): BetPawa probability extraction with deobfuscation"
```

---

## Task 4: SportyBet parser integration

**Files:**
- Modify: `src/bookieskit/markets/parser.py`
- Modify: `tests/test_probability.py`

SportyBet exposes both `outcome.probability` and `outcome.voidProbability` as decimal strings. Robust `float()` cast; on failure → `None`.

Fixture facts (SportyBet 1X2 prematch, market id `1`):
- Home: probability="0.3952740000", voidProbability="0E-10"
- Draw: probability="0.2891970000", voidProbability="0E-10"
- Away: probability="0.3155220000", voidProbability="0E-10"
- `0E-10` parses to `0.0` via `float()`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_probability.py`:

```python
def test_sportybet_probability_off_keeps_outcomes_clean():
    d = _load("sportybet")
    markets = parse_markets(d, platform="sportybet", probability="off")
    m = next(m for m in markets if m.canonical_id == "1x2_ft")
    for o in m.outcomes:
        assert o.true_probability is None
        assert o.void_probability is None


def test_sportybet_probability_true_populates_true_only():
    d = _load("sportybet")
    markets = parse_markets(d, platform="sportybet", probability="true")
    m = next(m for m in markets if m.canonical_id == "1x2_ft")
    by_name = {o.canonical_name: o for o in m.outcomes}
    assert by_name["home"].true_probability == pytest.approx(0.395274)
    assert by_name["draw"].true_probability == pytest.approx(0.289197)
    assert by_name["away"].true_probability == pytest.approx(0.315522)
    for o in m.outcomes:
        assert o.void_probability is None


def test_sportybet_probability_with_void_populates_both():
    d = _load("sportybet")
    markets = parse_markets(d, platform="sportybet", probability="with_void")
    m = next(m for m in markets if m.canonical_id == "1x2_ft")
    for o in m.outcomes:
        assert o.true_probability is not None
        # voidProbability '0E-10' parses to 0.0
        assert o.void_probability == 0.0
```

- [ ] **Step 2: Run, verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v -k sportybet`
Expected: 2 failures (the `_off` test should still pass — probabilities are None by default plumbing).

- [ ] **Step 3: Wire SportyBet probability extraction**

The SportyBet helpers iterate `for outcome_data in market_data.get("outcomes", []):` (in `_parse_sportybet_simple` ~line 204+) and `for outcome_data in entry.get("outcomes", []):` inside an outer `for entry in entries:` loop (in `_parse_sportybet_parameterized` ~line 231+). Note the parameterized helper signature is `(entries: list[dict], mapping: MarketMapping)` — already updated in Task 1 to `(entries, mapping, mode)`.

Add a small private helper above `_parse_sportybet`:

```python
def _try_float(v: object) -> float | None:
    """Best-effort float cast; None on failure or empty/invalid string."""
    if v is None:
        return None
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
```

(If a `_try_float` helper already exists in the file, reuse it instead of duplicating.)

Then replace each SportyBet `Outcome(...)` construction with:

```python
true_p = void_p = None
if mode != "off":
    true_p = _try_float(outcome_data.get("probability"))
    if mode == "with_void":
        void_p = _try_float(outcome_data.get("voidProbability"))
outcomes.append(
    Outcome(
        canonical_name=canonical,
        odds=odds,  # already computed earlier in the loop
        platform_name=desc,
        true_probability=true_p,
        void_probability=void_p,
    )
)
```

(For `_parse_sportybet_parameterized`, the `outcomes.append(...)` is actually `line_outcomes.append(...)` — preserve that local variable name. The body of the Outcome(...) call is identical.)

Both `_parse_sportybet_simple` and `_parse_sportybet_parameterized` already accept `mode: ProbabilityMode = "off"` from Task 1.

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v -k sportybet`
Expected: 3 passed.

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: full suite passes.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_probability.py
git commit -m "feat(probability): SportyBet true_probability + void_probability extraction"
```

---

## Task 5: MSport parser integration

**Files:**
- Modify: `src/bookieskit/markets/parser.py`
- Modify: `tests/test_probability.py`

MSport exposes only `outcome.probability` (no void). `void_probability` always stays `None`.

Fixture facts (MSport 1X2 prematch, market id `1`):
- outcomes[0]: probability="0.3953"
- outcomes[1]: probability="0.2892"
- outcomes[2]: probability="0.3155"

Note: MSport outcomes don't carry `desc` reliably; the canonical mapping uses the `outcomes[]` index. The probability extraction itself is index-independent — read `outcome.get("probability")` per item regardless of how `canonical_name` is resolved.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_probability.py`:

```python
def test_msport_probability_off_keeps_outcomes_clean():
    d = _load("msport")
    markets = parse_markets(d, platform="msport", probability="off")
    m = next((m for m in markets if m.canonical_id == "1x2_ft"), None)
    assert m is not None
    for o in m.outcomes:
        assert o.true_probability is None
        assert o.void_probability is None


def test_msport_probability_true_populates_true_only():
    d = _load("msport")
    markets = parse_markets(d, platform="msport", probability="true")
    m = next(m for m in markets if m.canonical_id == "1x2_ft")
    # MSport rounds to 4 decimal places. Use approx with tol.
    probs = sorted([o.true_probability for o in m.outcomes if o.true_probability is not None])
    assert probs == pytest.approx([0.2892, 0.3155, 0.3953], abs=1e-4)
    for o in m.outcomes:
        assert o.void_probability is None


def test_msport_probability_with_void_only_populates_true():
    """MSport doesn't expose voidProbability — with_void mode still
    populates true_probability but leaves void_probability None."""
    d = _load("msport")
    markets = parse_markets(d, platform="msport", probability="with_void")
    m = next(m for m in markets if m.canonical_id == "1x2_ft")
    for o in m.outcomes:
        assert o.true_probability is not None
        assert o.void_probability is None  # NOT exposed by MSport
```

- [ ] **Step 2: Run, verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v -k msport`
Expected: 2 failures (the `_off` test should pass).

- [ ] **Step 3: Wire MSport probability extraction**

The MSport helpers iterate `for outcome_data in market_data.get("outcomes", []):` (in `_parse_msport_simple` ~line 766+) and `for outcome_data in entry.get("outcomes", []):` inside an outer `for entry in entries:` (in `_parse_msport_parameterized` ~line 793+). MSport reads `outcome_data.get("description")` (not `desc`) for the platform name.

Replace each `Outcome(...)` construction with:

```python
true_p = None
if mode != "off":
    true_p = _try_float(outcome_data.get("probability"))
# MSport doesn't expose voidProbability — leave void_probability as None
# even when mode == "with_void".
outcomes.append(
    Outcome(
        canonical_name=canonical,
        odds=odds,  # already computed
        platform_name=desc,  # already computed: str(outcome_data.get("description", ""))
        true_probability=true_p,
    )
)
```

(For the parameterized helper the local list is `line_outcomes` instead of `outcomes` — preserve that.)

`_try_float` should already exist from Task 4 — reuse it.

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v -k msport`
Expected: 3 passed.

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: full suite passes.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/markets/parser.py tests/test_probability.py
git commit -m "feat(probability): MSport true_probability extraction (no void)"
```

---

## Task 6: Unavailable-platform tests (Betway and Bet9ja)

**Files:**
- Modify: `tests/test_probability.py`

No code changes — Bet9ja and Betway parsers already accept the `mode` arg (from Task 1) and never populate the new fields, so this is purely a contract assertion.

- [ ] **Step 1: Write tests**

Append to `tests/test_probability.py`:

```python
@pytest.mark.parametrize("mode", ["off", "true", "with_void"])
def test_betway_never_populates_probabilities(mode):
    """Betway has no probability data in its API; both fields always None."""
    d = _load("betway")
    markets = parse_markets(d, platform="betway", probability=mode)
    # Betway might have markets in the fixture or not — iterate any present.
    for m in markets:
        for o in m.outcomes:
            assert o.true_probability is None
            assert o.void_probability is None
        if m.lines:
            for outcomes in m.lines.values():
                for o in outcomes:
                    assert o.true_probability is None
                    assert o.void_probability is None


@pytest.mark.parametrize("mode", ["off", "true", "with_void"])
def test_bet9ja_never_populates_probabilities(mode):
    """Bet9ja has no probability in its API; both fields always None."""
    d = _load("bet9ja")
    markets = parse_markets(d, platform="bet9ja", probability=mode)
    for m in markets:
        for o in m.outcomes:
            assert o.true_probability is None
            assert o.void_probability is None
        if m.lines:
            for outcomes in m.lines.values():
                for o in outcomes:
                    assert o.true_probability is None
                    assert o.void_probability is None
```

- [ ] **Step 2: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v -k "betway or bet9ja"`
Expected: 6 passed (3 modes × 2 platforms).

- [ ] **Step 3: Commit**

```bash
git add tests/test_probability.py
git commit -m "test(probability): assert Betway and Bet9ja never populate probabilities"
```

---

## Task 7: Cross-platform 1X2 sum-sanity test

**Files:**
- Modify: `tests/test_probability.py`

Across the 3 supporting platforms, the three 1X2 outcome `true_probability` values must sum to ≈1 (within `[0.95, 1.05]`). Confirms these are fair probs, not implied.

- [ ] **Step 1: Write the test**

Append to `tests/test_probability.py`:

```python
@pytest.mark.parametrize("platform", ["betpawa", "sportybet", "msport"])
def test_1x2_true_probabilities_sum_to_about_one(platform):
    """Fair probabilities across mutually exclusive 1X2 outcomes sum to ≈1.
    A bookmaker's implied probabilities (1/odds) would sum to >1 due to
    margin; if this test fails it likely means we're reading the wrong
    field."""
    d = _load(platform)
    markets = parse_markets(d, platform=platform, probability="true")
    m = next(m for m in markets if m.canonical_id == "1x2_ft")
    probs = [o.true_probability for o in m.outcomes if o.true_probability is not None]
    assert len(probs) == 3, f"expected 3 outcomes, got {probs}"
    total = sum(probs)
    assert 0.95 <= total <= 1.05, f"{platform} 1X2 prob sum {total} not in [0.95, 1.05]"
```

- [ ] **Step 2: Run the test**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v -k 1x2_true_probabilities_sum`
Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_probability.py
git commit -m "test(probability): cross-platform 1X2 sum-to-one fair-prob sanity check"
```

---

## Task 8: Robustness tests for malformed inputs and invalid mode

**Files:**
- Modify: `tests/test_probability.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_probability.py`:

```python
import copy


def test_betpawa_missing_probability_field_yields_none():
    """If a BetPawa price has no 'probability' key, fields stay None."""
    d = copy.deepcopy(_load("betpawa"))
    # Strip 'probability' from every price in every market.
    for m in d.get("markets", []):
        rows = m.get("row") or []
        if not isinstance(rows, list):
            rows = [rows]
        for row in rows:
            for price in row.get("prices", []):
                price.pop("probability", None)
    markets = parse_markets(d, platform="betpawa", probability="with_void")
    for m in markets:
        for o in m.outcomes:
            assert o.true_probability is None
            assert o.void_probability is None


def test_betpawa_garbage_probability_blob_yields_none():
    """A non-base64 'probability' string must not raise."""
    d = copy.deepcopy(_load("betpawa"))
    for m in d.get("markets", []):
        rows = m.get("row") or []
        if not isinstance(rows, list):
            rows = [rows]
        for row in rows:
            for price in row.get("prices", []):
                if "probability" in price:
                    price["probability"] = "not-base64!!!"
    markets = parse_markets(d, platform="betpawa", probability="with_void")
    for m in markets:
        for o in m.outcomes:
            assert o.true_probability is None
            assert o.void_probability is None


def test_sportybet_non_numeric_probability_yields_none():
    d = copy.deepcopy(_load("sportybet"))
    for m in (d.get("data") or {}).get("markets", []):
        for o in m.get("outcomes", []):
            if "probability" in o:
                o["probability"] = "abc"
            if "voidProbability" in o:
                o["voidProbability"] = "xyz"
    markets = parse_markets(d, platform="sportybet", probability="with_void")
    for m in markets:
        for o in m.outcomes:
            assert o.true_probability is None
            assert o.void_probability is None


def test_invalid_mode_silently_treated_as_off():
    """A mode value outside the Literal silently becomes 'off' — no raise."""
    d = _load("sportybet")
    markets_default = parse_markets(d, platform="sportybet")
    markets_garbage = parse_markets(d, platform="sportybet", probability="garbage")  # type: ignore[arg-type]
    # Same length, same canonical ids, all outcomes have None probabilities
    assert len(markets_default) == len(markets_garbage)
    for m in markets_garbage:
        for o in m.outcomes:
            assert o.true_probability is None
            assert o.void_probability is None
```

- [ ] **Step 2: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py -v -k "missing_probability or garbage_probability or non_numeric or invalid_mode"`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_probability.py
git commit -m "test(probability): robustness for missing/malformed inputs and invalid mode"
```

---

## Task 9: Re-export `ProbabilityMode` from top-level package

**Files:**
- Modify: `src/bookieskit/__init__.py`
- Modify: `tests/test_probability.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_probability.py`:

```python
def test_probability_mode_is_top_level_reexport():
    import bookieskit
    assert hasattr(bookieskit, "ProbabilityMode")
    # Ensure it's the same symbol as in the parser module
    from bookieskit.markets.parser import ProbabilityMode as _PM
    assert bookieskit.ProbabilityMode is _PM
```

- [ ] **Step 2: Run, verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py::test_probability_mode_is_top_level_reexport -v`
Expected: FAIL — `bookieskit` has no attribute `ProbabilityMode`.

- [ ] **Step 3: Add the re-export**

In `src/bookieskit/__init__.py`, add `ProbabilityMode` to the `event_info` block companion (or in its own line). Read the current file first; the existing imports look like:

```python
from bookieskit.event_info import (
    LiveInfo,
    Mode,
    Participants,
    extract_kickoff,
    extract_live_info,
    extract_participants,
    is_live_now,
)
```

Add a new import line below (or above):

```python
from bookieskit.markets.parser import ProbabilityMode
```

Then add `"ProbabilityMode"` to the `__all__` list (alphabetically near `Mode` / `Participants` is fine; the existing list is grouped roughly by topic).

Final state of `__init__.py` (the relevant additions):

```python
from bookieskit.markets.parser import ProbabilityMode

__all__ = [
    "BetPawa",
    "SportyBet",
    "Bet9ja",
    "Betway",
    "MSport",
    "LiveInfo",
    "Mode",
    "Participants",
    "ProbabilityMode",
    "extract_kickoff",
    "extract_live_info",
    "extract_participants",
    "is_live_now",
    "__version__",
]
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_probability.py::test_probability_mode_is_top_level_reexport -v`
Expected: PASS.

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: full suite passes.

- [ ] **Step 5: Commit**

```bash
git add src/bookieskit/__init__.py tests/test_probability.py
git commit -m "feat(probability): re-export ProbabilityMode from top-level package"
```

---

## Task 10: Update `docs/markets.md` with a Probabilities section

**Files:**
- Modify: `docs/markets.md`

Add a new section near the bottom (before any "Limitations" section, or as the last content section) documenting the new probability surface.

- [ ] **Step 1: Read the existing `docs/markets.md`**

Run: `cat docs/markets.md` (or use the Read tool). Note where the natural insertion point is — typically before any "Limitations" / "Caveats" footer.

- [ ] **Step 2: Insert the new section**

Add this section to `docs/markets.md` (location: after the existing market-list section, before any closing notes):

```markdown
## Probabilities

Each `Outcome` carries `odds` (decimal odds) and optionally
`true_probability` / `void_probability` — the bookmaker's pre-margin fair
estimate and the chance the bet is voided. Off by default; opt in via the
`probability` keyword on `parse_markets`:

```python
from bookieskit.markets import parse_markets

# Default: probabilities not extracted
markets = parse_markets(detail, platform="sportybet")

# Opt in to fair-probability extraction
markets = parse_markets(detail, platform="sportybet", probability="true")

# Opt in to fair + void
markets = parse_markets(detail, platform="sportybet", probability="with_void")

for m in markets:
    for o in m.outcomes:
        print(o.canonical_name, o.odds, o.true_probability, o.void_probability)
```

`true_probability` is the bookmaker's fair (pre-margin) estimate, **not**
`1 / odds`. Across mutually exclusive outcomes of one market, fair
probabilities sum to ≈1; implied probabilities (`1/odds`) sum to >1
because of the bookmaker's margin.

### Per-platform support

| Platform | `true_probability` | `void_probability` | Notes |
|---|---|---|---|
| SportyBet | yes | yes | Plain decimal-string fields |
| MSport | yes | n/a | Only `probability`; `voidProbability` is not in the API |
| BetPawa | yes | yes | Obfuscated client-side; bookieskit decodes transparently |
| Betway | n/a | n/a | Verified absent from `get_event_markets` (no `probability`/`prob`/`impliedOdds`/`margin`/`voidProbability` keys anywhere in their 400 KB markets payload) |
| Bet9ja | n/a | n/a | Not in `D.O` (live) nor in their prematch event-detail response |

For Betway and Bet9ja, both fields are always `None` regardless of the
`probability` mode — `parse_markets` accepts the keyword silently.

### Modes

| `probability` value | Behaviour |
|---|---|
| `"off"` (default) | Both fields `None` for every outcome. Zero parsing cost. |
| `"true"` | `true_probability` populated where supported; `void_probability` always `None`. |
| `"with_void"` | Both fields populated where supported. |

Invalid values (anything outside the literal) are silently treated as
`"off"`.

### BetPawa deobfuscation

BetPawa hides per-outcome probability behind a base64-encoded JSON
payload `{"win": <int>, "refund": <int>, "key": <int>}`; each value is
recovered by 3-way 64-bit XOR with a global constant and the per-bet key,
then reinterpreted as IEEE 754 float64 (big-endian). The library handles
this transparently — callers only see `true_probability` and
`void_probability` as floats. Direct access to the decoder is available
via `bookieskit.bookmakers._betpawa_obfuscation.decode_betpawa_probability`
for ad-hoc analysis (private import, not re-exported).
```

- [ ] **Step 3: Verify markdown renders**

Run: `cat docs/markets.md` to eyeball — make sure the new section sits in a sensible place and existing headings aren't broken.

- [ ] **Step 4: Commit**

```bash
git add docs/markets.md
git commit -m "docs(markets): document true/void probability extraction"
```

---

## Final Verification

After all 10 tasks:

- [ ] `.venv/Scripts/python.exe -m pytest -q` — full project suite passes (target: ~245+ tests, was 215 before this work).
- [ ] `.venv/Scripts/python.exe -m ruff check src/ tests/ examples/` — clean.
- [ ] `.venv/Scripts/python.exe -c "from bookieskit import ProbabilityMode; from bookieskit.markets import parse_markets; print('ok')"` — public surface importable.
- [ ] Manual smoke: `.venv/Scripts/python.exe -c "import json; from bookieskit.markets import parse_markets; d = json.load(open('tests/fixtures/event_info/sportybet/prematch.json', encoding='utf-8')); ms = parse_markets(d, 'sportybet', probability='with_void'); m = next(m for m in ms if m.canonical_id == '1x2_ft'); [print(o.canonical_name, o.odds, o.true_probability, o.void_probability) for o in m.outcomes]"`
