# Markets — registry, builtins, parser

The `bookieskit.markets` package normalizes per-bookmaker market formats into a small set of canonical markets. Three pieces:

- **Types** (`markets/types.py`) — `MarketMapping`, `OutcomeMapping`, `NormalizedMarket`, `Outcome`.
- **Registry** (`markets/registry.py`) — `MarketRegistry` holds `MarketMapping` entries, indexed by canonical id and by each platform's id.
- **Parser** (`markets/parser.py`) — `parse_markets(response, platform, registry=None)` dispatches to a per-platform parser and returns `list[NormalizedMarket]`.

## Built-in mappings

Six markets ship in the default `MarketRegistry`:

| Canonical id | Name | Parameterized? | BetPawa | SportyBet | Bet9ja | Betway | MSport |
|---|---|---|---|---|---|---|---|
| `1x2_ft` | 1X2 — Full Time | no | ✅ | ✅ | ✅ | ✅ | ✅ |
| `over_under_ft` | Over/Under — Full Time | yes (line=goals) | ✅ | ✅ | ✅ | ✅ | ✅ |
| `btts_ft` | Both Teams To Score — Full Time | no | ✅ | ✅ | ✅ | ✅ | ✅ |
| `double_chance_ft` | Double Chance — Full Time | no | ✅ | ✅ | ✅ | ✅ | ✅ |
| `1x2_1up_ft` | 1X2 1Up — Full Time | no | — | ✅ | ✅ | ✅ | — |
| `1x2_2up_ft` | 1X2 2Up — Full Time | no | — | ✅ | ✅ | ✅ | — |

The 1Up / 2Up markets pay as a 1X2 if your team gets to a 1- or 2-goal lead at any point. BetPawa and MSport are intentionally unmapped (BetPawa to be added at production cutover; MSport doesn't expose this market).

## Types

### `MarketMapping`

Frozen dataclass. Fields:
- `canonical_id: str` — unique short id (e.g. `"over_under_ft"`).
- `name: str` — human-readable name.
- `betpawa_id: str | None`
- `sportybet_id: str | None`
- `bet9ja_key: str | None` — the key prefix in Bet9ja's flat odds dict (e.g. `"S_OU"`).
- `betway_id: str | None` — the literal market name as Betway returns it (e.g. `"[Total Goals]"`, `"1X2 (1Up)"`).
- `msport_id: str | None`
- `outcomes: dict[str, OutcomeMapping]` — keyed by canonical outcome name (`"home"`, `"over"`, etc.).
- `parameterized: bool` — `True` for markets with line variants (Over/Under, handicaps).

### `OutcomeMapping`

Frozen dataclass. One per canonical outcome:
- `canonical_name: str` — e.g. `"home"`, `"draw"`, `"over"`.
- `betpawa: str` — the platform's outcome string (e.g. `"1"`, `"1X"`).
- `sportybet: str` — e.g. `"Home"`, `"Home or Draw"`.
- `bet9ja: str` — the suffix in the flat odds dict (e.g. `"O"` for over, `"X1"` for the 1X2 1Up draw).
- `betway: str` — either the literal name (`"Over"`) or a position sentinel (see below).
- `msport: str` — e.g. `"Home"`, `"1 X"` for DC.

### `NormalizedMarket`

The output of `parse_markets`. Has `canonical_id`, `name`, `outcomes` (a flat list for non-parameterized markets), and `lines` (a `dict[float, list[Outcome]]` for parameterized markets like Over/Under). Exactly one of `outcomes` / `lines` is populated per market.

### `Outcome`

A normalized outcome inside a `NormalizedMarket`. Has `canonical_name`, `odds: float`, `platform_name` (the original string from the bookmaker, useful for debugging).

### Position sentinels (Betway)

Betway returns the 1X2-shaped markets (1X2, DC, 1X2 1Up, 1X2 2Up) with team names as outcomes (`"Aston Villa"`, `"Draw"`, `"Nottingham Forest"`) — not standardized labels. The parser resolves them by index using these sentinels in the `betway` field of `OutcomeMapping`:

| Sentinel | Index | Meaning |
|---|---|---|
| `__HOME__` | 0 | Home team (used by 1X2-shaped markets). |
| `__AWAY__` | 2 | Away team (used by 1X2-shaped markets). |
| `__POS_1__` | 0 | First outcome positionally. |
| `__POS_2__` | 1 | Second outcome positionally. |
| `__POS_3__` | 2 | Third outcome positionally. |

Use `__HOME__` / `__AWAY__` on 1X2 (clearest intent) and `__POS_N__` for Double Chance where the meaning is purely positional (Betway returns DC as 1X / 12 / X2 in that order).

## Parser dispatcher

`parse_markets(response, platform, registry=None)` looks up `platform` in the dispatcher dict and calls the right `_parse_<platform>` function. Currently registered: `"betpawa"`, `"sportybet"`, `"bet9ja"`, `"betway"`, `"msport"`. Returns `[]` if `platform` is unknown.

The Bet9ja parser handles BOTH the prematch `S_*` keys AND the live `LIVES_*` keys. It also unwraps the `{"v": <float>}` odds shape used in live responses (vs bare strings prematch).

## Custom mappings

Add a market to the default registry at runtime:

```python
from bookieskit.markets import MarketRegistry, OutcomeMapping

registry = MarketRegistry()  # ships with the 6 builtins
registry.add(
    canonical_id="draw_no_bet_ft",
    name="Draw No Bet — Full Time",
    betpawa_id="4703",
    sportybet_id="11",
    bet9ja_key="S_DNB",
    betway_id="Draw No Bet",
    msport_id="11",
    outcomes={
        "home": OutcomeMapping(
            canonical_name="home",
            betpawa="1", sportybet="Home", bet9ja="1",
            betway="__HOME__", msport="Home",
        ),
        "away": OutcomeMapping(
            canonical_name="away",
            betpawa="2", sportybet="Away", bet9ja="2",
            betway="__AWAY__", msport="Away",
        ),
    },
)
```

Pass the registry into `parse_markets(raw, platform=..., registry=registry)` or `client.get_markets(event_id, registry=registry)`.

## Adding a new platform

To wire a new bookmaker into the parser:
1. Add a `<platform>_id` field to `MarketMapping` and a `<platform>` field to `OutcomeMapping` in `markets/types.py`.
2. Add a `_by_<platform>` index to `MarketRegistry` in `markets/registry.py` and update `_register` and `get_by_platform_id`.
3. Write `_parse_<platform>(response, registry)` in `markets/parser.py`.
4. Add a `"<platform>": _parse_<platform>` entry to the dispatcher in `parse_markets`.
5. Update the 6 builtins in `markets/builtin_mappings.py` (or leave entries unmapped via `None` if the platform doesn't expose those markets).

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
| Betway | n/a | n/a | Verified absent from `get_event_markets` (no `probability` / `prob` / `impliedOdds` / `margin` / `voidProbability` keys anywhere in their 400 KB markets payload) |
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
for ad-hoc analysis (private import, not re-exported from the top-level package).

## See also

- [docs/matching.md](matching.md) — pairing events across platforms by SR id.
- [docs/examples.md](examples.md) — example scripts that use the registry end-to-end.
