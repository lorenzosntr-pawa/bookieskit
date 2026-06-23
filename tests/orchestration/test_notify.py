from bookieskit.orchestration.cli import main
from bookieskit.orchestration.notify import (
    canary_digest,
    cycle_blocked,
    cycle_empty,
    cycle_pr,
    cycle_started,
    release_announcement,
)


def test_cycle_started_humanizes_stream_and_includes_number_title():
    msg = cycle_started(42, "add Stake bookmaker", "stream:directed")
    assert "#42" in msg
    assert "add Stake bookmaker" in msg
    assert "directed" in msg
    assert "stream:" not in msg  # humanized
    assert "*Cycle started*" in msg


def test_cycle_pr_includes_pr_url_and_awaiting_review():
    msg = cycle_pr(42, "add Stake", "https://github.com/o/r/pull/12")
    assert "#42" in msg
    assert "https://github.com/o/r/pull/12" in msg
    assert "awaiting review" in msg.lower()
    assert "*PR opened*" in msg


def test_cycle_blocked_includes_reason():
    msg = cycle_blocked(42, "add Stake", "missing API credential")
    assert "#42" in msg
    assert "blocked" in msg.lower()
    assert "missing API credential" in msg


def test_cycle_empty_is_nonempty_text():
    msg = cycle_empty()
    assert msg.strip()
    assert "empty" in msg.lower()


def test_canary_digest_lists_each_signature_and_counts():
    msg = canary_digest(
        opened=["canary:betika:structure"],
        updated=[],
        closed=["canary:msport:structure", "canary:sporty:structure"],
        sport="soccer",
    )
    assert "soccer" in msg
    assert "canary:betika:structure" in msg
    assert "canary:msport:structure" in msg
    assert "canary:sporty:structure" in msg
    # counts reflect 1 opened / 0 updated / 2 closed — assert the exact header
    # so a multi-digit count can't satisfy a bare substring check
    assert "*Canary (soccer)* — 1 new, 0 persisting, 2 recovered" in msg


def test_canary_digest_empty_when_no_change():
    assert canary_digest([], [], [], "soccer") == ""


def test_release_announcement_shows_tag_and_transition():
    msg = release_announcement("v0.17.0", "0.16.0", "0.17.0")
    assert "v0.17.0" in msg
    assert "0.16.0" in msg
    assert "0.17.0" in msg
    assert "*Released" in msg


# --- CLI tests ---


def test_cli_notify_cycle_started(capsys):
    rc = main([
        "notify", "cycle-started",
        "--number", "42", "--title", "add Stake", "--stream", "stream:directed",
    ])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert "#42" in out and "directed" in out and "add Stake" in out
    assert "stream:" not in out


def test_cli_notify_cycle_pr(capsys):
    rc = main([
        "notify", "cycle-pr",
        "--number", "42", "--title", "add Stake",
        "--pr", "https://github.com/o/r/pull/12",
    ])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert "https://github.com/o/r/pull/12" in out
    assert "awaiting review" in out.lower()


def test_cli_notify_cycle_blocked(capsys):
    rc = main([
        "notify", "cycle-blocked",
        "--number", "42", "--title", "add Stake", "--reason", "no creds",
    ])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert "blocked" in out.lower() and "no creds" in out


def test_cli_notify_release(capsys):
    rc = main([
        "notify", "release",
        "--tag", "v0.17.0", "--current", "0.16.0", "--new", "0.17.0",
    ])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert "v0.17.0" in out and "0.16.0" in out and "0.17.0" in out
