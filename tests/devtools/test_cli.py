import json

import pytest

from bookieskit.devtools import cli
from bookieskit.devtools.types import Handle, ResolvedEvent


def test_build_parser_has_four_subcommands():
    parser = cli.build_parser()
    args = parser.parse_args(["resolve", "sr:match:42"])
    assert args.cmd == "resolve"
    assert args.seed == "sr:match:42"
    assert args.sport == "soccer"  # default


def test_discover_requires_exactly_one_of_term_or_unmapped():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        # neither --term nor --unmapped
        parser.parse_args(["discover", "sr:match:42"])


def test_discover_term_and_unmapped_are_mutually_exclusive():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["discover", "sr:match:42", "--term", "x", "--unmapped"]
        )


async def _fake_resolver_ok(seed, sport, books, **kwargs):
    return ResolvedEvent(
        seed=seed, sport=sport, sr_numeric="42", home="A", away="B",
        handles={"sportybet": Handle("sportybet", "sr:match:42")},
        skipped={"bet9ja": "not found"},
    )


async def _fake_resolver_fail(seed, sport, books, **kwargs):
    return ResolvedEvent(
        seed=seed, sport=sport, sr_numeric=None, home="?", away="?",
        handles={}, skipped={"sportybet": "error: boom"},
    )


@pytest.mark.asyncio
async def test_resolve_json_output_and_exit_zero(capsys):
    parser = cli.build_parser()
    args = parser.parse_args(["resolve", "sr:match:42", "--json"])
    code = await cli.run(args, resolver=_fake_resolver_ok)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["sr_numeric"] == "42"
    assert out["handles"]["sportybet"]["event_id"] == "sr:match:42"
    assert out["skipped"]["bet9ja"] == "not found"


@pytest.mark.asyncio
async def test_resolve_nonzero_exit_when_no_book_resolves(capsys):
    parser = cli.build_parser()
    args = parser.parse_args(["resolve", "sr:match:42", "--json"])
    code = await cli.run(args, resolver=_fake_resolver_fail)
    assert code == 1


@pytest.mark.asyncio
async def test_verify_uses_injected_clients_and_fetches_per_book(capsys):
    # Inject a fake fetch via the clients map: the CLI's verify path calls
    # adapter.fetch_raw_markets(client, handle). We stub the client so the
    # SportyBet adapter returns a parseable payload.
    sportybet_payload = {
        "data": {"markets": [
            {"id": "1", "name": "1X2", "outcomes": [
                {"desc": "Home", "odds": 1.5},
                {"desc": "Draw", "odds": 3.2},
                {"desc": "Away", "odds": 2.1},
            ]},
        ]}
    }

    class _FakeSporty:
        async def get_event_detail(self, event_id, live=False):
            return sportybet_payload

    args = cli.build_parser().parse_args(
        ["verify", "sr:match:42", "--book", "sportybet",
         "--canonical", "1x2_ft,btts_ft", "--json"]
    )
    code = await cli.run(
        args,
        resolver=_fake_resolver_ok,
        clients={"sportybet": _FakeSporty()},
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    sb = out["results"]["sportybet"]
    assert "1x2_ft" in sb["resolved"]
    assert sb["missing"] == ["btts_ft"]
