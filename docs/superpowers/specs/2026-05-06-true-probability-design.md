# True-probability extraction in bookieskit — design

## 1. Goal

Extend `parse_markets` so each `Outcome` can carry the bookmaker's pre-margin
"fair" probability estimate alongside its existing decimal odds. The current
`Outcome` dataclass exposes only `(canonical_name, odds, platform_name)`;
this spec adds two new optional fields and a keyword switch on the parser to
control whether they're populated.

Three platforms expose probability data: **SportyBet** and **MSport**
provide it as plain strings; **BetPawa** obfuscates it (base64 + XOR + IEEE
754 reinterpret). Two platforms do not expose it at all: **Betway**
(confirmed by inspecting their full 400 KB markets response — no
`probability` / `prob` / `impliedOdds` / `margin` / `voidProbability`
keys) and **Bet9ja** (no probability anywhere in their `D.O` odds dict).

This unblocks downstream analytics and arbitrage projects that need both
the price (odds) and the bookmaker's internal estimate of the true
likelihood.

## 2. Public surface

### 2.1 `Outcome` gains two optional fields

```python
@dataclass(frozen=True)
class Outcome:
    canonical_name: str
    odds: float
    platform_name: str
    true_probability: float | None = None
    void_probability: float | None = None
```

Both default `None`. Backward-compatible: existing call sites that read
the first three fields are unaffected.

**Semantics:**

- `true_probability` — the bookmaker's fair / pre-margin estimate of the
  outcome occurring. Across the mutually exclusive outcomes of a single
  market (e.g. 1X2: home, draw, away) these values sum to ≈1, not >1. This
  is **not** the same as `1/odds`, which sums to >1 because of the
  bookmaker's margin.
- `void_probability` — the bookmaker's estimate of the bet being voided /
  refunded (e.g. event abandoned). Independent of `true_probability`.

### 2.2 `parse_markets` gains a keyword switch

```python
from typing import Literal

ProbabilityMode = Literal["off", "true", "with_void"]

def parse_markets(
    response: dict,
    platform: str,
    registry: MarketRegistry | None = None,
    *,
    probability: ProbabilityMode = "off",
) -> list[NormalizedMarket]: ...
```

| `probability` value | Behaviour |
|---|---|
| `"off"` (default) | Current behaviour. `true_probability` and `void_probability` always `None`. No probability parsing happens — zero extra work. |
| `"true"` | Populate `true_probability` where the platform exposes it. `void_probability` stays `None`. |
| `"with_void"` | Populate both fields where the platform exposes them. On MSport, `void_probability` stays `None` (not in API). |

Unsupported platforms (Betway, Bet9ja): both fields stay `None` for every
outcome, regardless of `probability` mode. Never raises.

Invalid `probability` values (anything not in `{"off", "true",
"with_void"}`) are silently treated as `"off"` — matches the
`_normalised_mode` pattern from `bookieskit.event_info`.

`ProbabilityMode` is re-exported from `bookieskit/__init__.py` so callers
can import it for type hints.

## 3. Per-platform extraction paths

Captured fixtures already contain probability data for the three supporting
platforms (verified at `tests/fixtures/event_info/{sportybet,msport,betpawa}/prematch.json`).

### 3.1 SportyBet

Path: each outcome at `data.markets[].outcomes[]` carries:

| Field | JSON key | Notes |
|---|---|---|
| `true_probability` | `probability` | String, e.g. `"0.3952740000"`. `float(s)` cast. |
| `void_probability` | `voidProbability` | String, e.g. `"0E-10"`. `float(s)` cast — `0E-10` parses to `0.0`. |

Treat empty string / `None` / non-numeric → `None`.

### 3.2 MSport

Path: each outcome at `data.markets[].outcomes[]` carries:

| Field | JSON key | Notes |
|---|---|---|
| `true_probability` | `probability` | String, e.g. `"0.3953"`. `float(s)` cast. |
| `void_probability` | n/a | Field is not present in the response. Always `None`. |

### 3.3 BetPawa

Path: each price at `markets[].row[].prices[]` carries:

| Field | JSON key | Notes |
|---|---|---|
| `probability` (obfuscated) | `probability` | Single base64-encoded blob containing both win and refund probabilities + a per-bet XOR key. Decode via the helper described in §4. |

The decoded payload yields `(win, refund)` floats. `win` →
`true_probability`, `refund` → `void_probability`.

### 3.4 Betway

No probability data in the response. Confirmed by inspecting a 402 KB
`get_event_markets` payload: zero matches for `probability`,
`voidProbability`, `prob`, `impliedOdds`, `margin`, `overround`. Both
fields always `None`.

### 3.5 Bet9ja

No probability data in the response. Confirmed for both prematch
(`get_event_detail`) and live (`get_live_event_detail`) shapes. Both
fields always `None`.

## 4. BetPawa deobfuscation helper

New private module: `src/bookieskit/bookmakers/_betpawa_obfuscation.py`.

### 4.1 Public function (within the module)

```python
def decode_betpawa_probability(blob: str | None) -> tuple[float | None, float | None]:
    """Decode a BetPawa price.probability base64 blob to (win, refund).

    Returns (None, None) on any decode failure (bad base64, malformed JSON,
    missing keys, or arithmetic overflow). Never raises.
    """
```

Used internally by `_parse_betpawa` in `markets/parser.py`. Not re-exported
publicly — but the module itself is importable for callers who need
ad-hoc deobfuscation (no leading-underscore re-export from
`bookieskit/__init__.py`).

### 4.2 Algorithm (verbatim from user-supplied formula)

1. Base64-urlsafe-decode the blob string (with `===` padding); the result
   is JSON `{"win": <int>, "refund": <int>, "key": <int>}`. The integers
   may be negative and may exceed 2^53.
2. For each of `win` and `refund`:
   1. Convert `value` to a 64-bit hex string (decimal-string → big int → mod
      2^64 → handle sign → 16-char uppercase hex).
   2. Same for `key`.
   3. XOR the value-hex with `GLOBAL_XOR_KEY_HEX = "9E3779B97F4A7C15"` and
      with the key-hex (three-way 64-bit XOR).
   4. Interpret the resulting 16-hex-character string as a big-endian
      IEEE 754 float64 (`struct.unpack(">d", bytes.fromhex(...))`).

The constant `GLOBAL_XOR_KEY_HEX` is defined at module level. Helper
functions `_decimal_string_to_hex64`, `_hex_xor64`, `_hex64_to_float64`
are private (single underscore prefix).

### 4.3 Error contract

`decode_betpawa_probability` never raises. Every step is guarded:

- Bad base64 padding / non-base64 input → `(None, None)`.
- JSON parse failure → `(None, None)`.
- Missing `win` / `refund` / `key` keys → those fields → `None`
  individually (one missing field doesn't kill the other).
- `int(...)` parse failure on any of the three values → that field
  becomes `None`.
- `struct.unpack` / hex conversion failure → that field becomes `None`.

## 5. Error handling (parser-wide)

All extractors are total, matching the existing library convention:

- Missing / non-string `probability` field on SportyBet/MSport → `None`
  for that outcome's `true_probability`. The outcome's `odds` is still
  populated normally; the missing probability does not invalidate the
  market.
- `float()` cast failure on a non-numeric probability string → `None`.
- BetPawa: see §4.3.
- Unknown platform passed to `parse_markets` → already returns `[]` per
  current behaviour. Unchanged.
- Invalid `probability` mode (e.g. `probability="foo"`) → silently
  treated as `"off"`. No exception, no warning.

## 6. Testing

New file: `tests/test_probability.py`.

### 6.1 BetPawa deobfuscator unit tests

Bind to the user-supplied sample blob:

```python
SAMPLE_BLOB = (
    "eyJ3aW4iOi0yOTA4Nzc4MTkyNTk2MTE5Njc5LCJyZWZ1bmQiOi0xNjk1MzY3MDg2NzY0MDYwNTQ0LCJrZXkiOjg1MjUyMDk3OTc5NTQzOTkzODF9"
)
```

Decoding `SAMPLE_BLOB` yields a known `(win, refund)` tuple. Pin the
expected values to the actual computation output (write the test by
running the algorithm once and capturing the result, then re-running on
every CI tick guarantees no regression). Plus negative tests:

- Bad base64 → `(None, None)`.
- Truncated JSON → `(None, None)`.
- Missing `win` key → `(None, refund_value)`; missing `refund` →
  `(win_value, None)`; missing `key` → `(None, None)` (no XOR possible).
- Empty string → `(None, None)`.
- `None` input → `(None, None)`.

### 6.2 Per-platform `parse_markets` probability tests

Load each prematch fixture from `tests/fixtures/event_info/`, then for
each supporting platform:

1. **Default off:** `parse_markets(d, platform)` → first outcome of the
   first 1X2 market has `true_probability is None` and
   `void_probability is None`.
2. **Mode `"true"`:** `true_probability` populated (a float in `(0, 1)`),
   `void_probability` still `None`.
3. **Mode `"with_void"`:** both populated where available.
4. **1X2 sum sanity:** the three 1X2 outcomes' `true_probability` values
   sum to within `[0.95, 1.05]` — confirms these are fair probs, not
   implied. Skip MSport if its 1X2 lacks all three; otherwise apply
   uniformly.

### 6.3 Unsupported-platform tests

For Betway and Bet9ja prematch fixtures: every mode (`"off"`, `"true"`,
`"with_void"`) yields outcomes with `true_probability is None` and
`void_probability is None`. No exceptions.

### 6.4 Robustness tests

- BetPawa fixture with the `probability` field manually deleted → field
  stays `None`, no exception.
- BetPawa fixture with the `probability` blob set to `"not-base64!"` →
  field stays `None`, no exception.
- SportyBet fixture with `probability` set to empty string / `None` /
  `"abc"` → `true_probability` stays `None`.
- Invalid `probability` mode (e.g. `probability="garbage"`) — currently
  not in the `Literal` type but Python doesn't enforce that at runtime
  — must be silently treated as `"off"`.

## 7. Documentation

Update `docs/markets.md` with a new "Probabilities" section covering:

1. What `true_probability` is (fair / pre-margin estimate, not
   `1/odds`).
2. What `void_probability` is.
3. Which platforms expose what:
   - SportyBet: both
   - MSport: true only
   - BetPawa: both (deobfuscated transparently)
   - Betway: neither (verified absent in their API)
   - Bet9ja: neither (no probability in their API)
4. The `probability` mode switch on `parse_markets` and when to use each
   value.
5. A short worked example showing how to read the new fields.

Add a docstring on `Outcome.true_probability` and
`Outcome.void_probability` explaining the distinction.

## 8. Repository layout

```
src/bookieskit/markets/parser.py                  # modify: add probability extraction per platform
src/bookieskit/markets/types.py                   # modify: add two fields to Outcome
src/bookieskit/bookmakers/_betpawa_obfuscation.py # new: deobfuscation helper
src/bookieskit/__init__.py                        # modify: re-export ProbabilityMode
docs/markets.md                                   # modify: add Probabilities section
tests/test_probability.py                         # new: deobfuscator + parser tests
```

`bookieskit/__init__.py` adds `ProbabilityMode` to the re-exports.

## 9. Out of scope

- No new function `parse_probabilities()` — extending the existing
  parser is enough.
- No `implied_probability` field (`1/odds`) — a one-line computation at
  the call site.
- No per-market overround / margin / book-percentage calculation.
- No re-capture of fixtures — existing prematch fixtures already
  contain the probability fields.
- No live-fixture probability coverage — the captured live fixtures are
  from finished matches with empty `markets`. Adding live coverage
  requires capturing fresh fixtures from a match in progress; deferred
  to a follow-up if/when needed.
- No exposure of `decode_betpawa_probability` from the top-level package
  — it remains importable from `bookieskit.bookmakers._betpawa_obfuscation`
  but is not part of the public surface.
