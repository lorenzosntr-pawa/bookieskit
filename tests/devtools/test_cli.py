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
async def test_discover_term_returns_candidates_and_exit_zero(capsys):
    """discover --term drives the full run() path; matching candidates returned."""
    sportybet_payload = {
        "data": {"markets": [
            {"id": "1", "name": "Asian Handicap FT", "outcomes": [
                {"desc": "Home -0.5", "odds": 1.8},
                {"desc": "Away +0.5", "odds": 2.0},
            ]},
            {"id": "2", "name": "1X2", "outcomes": [
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
        ["discover", "sr:match:42", "--book", "sportybet",
         "--term", "handicap", "--json"]
    )
    code = await cli.run(
        args,
        resolver=_fake_resolver_ok,
        clients={"sportybet": _FakeSporty()},
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    candidates = out["results"]["sportybet"]
    assert isinstance(candidates, list)
    assert len(candidates) == 1
    assert candidates[0]["name"] == "Asian Handicap FT"


@pytest.mark.asyncio
async def test_discover_all_fetch_failures_returns_exit_one(capsys):
    """Fix 1: when every per-book fetch raises, run() returns exit code 1."""

    class _BoomSporty:
        async def get_event_detail(self, event_id, live=False):
            raise RuntimeError("network error")

    args = cli.build_parser().parse_args(
        ["discover", "sr:match:42", "--book", "sportybet",
         "--term", "handicap", "--json"]
    )
    code = await cli.run(
        args,
        resolver=_fake_resolver_ok,
        clients={"sportybet": _BoomSporty()},
    )
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["results"] == {}
    assert "sportybet" in out["skipped"]


@pytest.mark.asyncio
async def test_check_docs_sync_fails_on_src_without_docs(capsys):
    args = cli.build_parser().parse_args(
        ["check-docs-sync", "--changed", "src/bookieskit/foo.py", "--json"]
    )
    code = await cli.run(args)
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["src_changed"] == ["src/bookieskit/foo.py"]


@pytest.mark.asyncio
async def test_check_docs_sync_passes_with_docs(capsys):
    args = cli.build_parser().parse_args(
        ["check-docs-sync", "--changed",
         "src/bookieskit/foo.py,docs/markets.md", "--json"]
    )
    code = await cli.run(args)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_check_docs_sync_docs_na_body_token_exempts(capsys):
    args = cli.build_parser().parse_args(
        ["check-docs-sync", "--changed", "src/bookieskit/foo.py",
         "--pr-body", "internal refactor only\ndocs:n/a", "--json"]
    )
    code = await cli.run(args)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["docs_na"] is True


@pytest.mark.asyncio
async def test_check_docs_sync_label_exempts(capsys):
    args = cli.build_parser().parse_args(
        ["check-docs-sync", "--changed", "src/bookieskit/foo.py",
         "--labels", "bug,docs:n/a", "--json"]
    )
    code = await cli.run(args)
    assert code == 0


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


# ---- audit subcommand -----------------------------------------------------


def test_audit_requires_a_mode():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["audit", "123"])  # neither --prematch nor --live


def test_audit_prematch_and_live_are_mutually_exclusive():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["audit", "--prematch", "--live"])


@pytest.mark.asyncio
async def test_audit_prematch_writes_report_and_sidecar(tmp_path, monkeypatch):
    from bookieskit.devtools.audit import (
        AuditReport,
        BookAudit,
        FixtureAudit,
        MarketAudit,
    )

    async def fake_run_audit(mode, **kw):
        assert mode == "prematch"
        assert kw["seeds"] == ["123"]
        fa = FixtureAudit(
            "Arsenal vs Atletico",
            "68995116",
            [
                BookAudit(
                    "betway",
                    "ok",
                    "",
                    [
                        MarketAudit(
                            "1x2_ft", "mapped_priced",
                            {"outcomes": {"home": 1.63}},
                        )
                    ],
                    [],
                )
            ],
        )
        return AuditReport(
            "soccer", mode, [fa], {"mapped_priced": 1, "not_offered": 0}
        )

    monkeypatch.setattr(cli, "run_audit", fake_run_audit)
    out = tmp_path / "audit.md"
    parser = cli.build_parser()
    args = parser.parse_args(["audit", "--prematch", "123", "--out", str(out)])
    code = await cli.run(args)
    assert code == 0
    assert out.exists()
    assert "Arsenal vs Atletico" in out.read_text(encoding="utf-8")
    sidecar = out.with_suffix(".json")
    assert sidecar.exists()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["mode"] == "prematch"


@pytest.mark.asyncio
async def test_audit_prematch_no_seeds_exits_clean(capsys):
    parser = cli.build_parser()
    args = parser.parse_args(["audit", "--prematch"])  # no seeds
    code = await cli.run(args)
    assert code == 1
    assert "audit failed" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_audit_nonzero_exit_when_no_fixtures(tmp_path, monkeypatch):
    from bookieskit.devtools.audit import AuditReport

    async def fake_run_audit(mode, **kw):
        return AuditReport("soccer", mode, [], {})

    monkeypatch.setattr(cli, "run_audit", fake_run_audit)
    out = tmp_path / "empty.md"
    parser = cli.build_parser()
    args = parser.parse_args(["audit", "--live", "--out", str(out)])
    code = await cli.run(args)
    assert code == 1
