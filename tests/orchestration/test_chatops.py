import json

from bookieskit.orchestration.chatops import (
    ApproveCommand,
    PauseCommand,
    ResumeCommand,
    build_ticket,
    checks_pass,
    closing_issue_numbers,
    is_authorized,
    load_config,
    merged,
    parse_command,
    paused,
    queued,
    rejected,
    resumed,
    ticket_signature,
)


def test_ticket_signature_is_slack_ts_namespaced():
    assert ticket_signature("1718900000.000100") == "directed:slack:1718900000.000100"


def test_build_ticket_is_directed_with_requester_meta():
    item = build_ticket("U123", "1718900000.000100", "Add Stake", "Support Stake bookmaker")
    assert item.stream == "stream:directed"
    assert item.signature == "directed:slack:1718900000.000100"
    assert item.title == "Add Stake"
    assert item.meta["requester"] == "U123"
    assert item.meta["slack_ts"] == "1718900000.000100"
    assert "U123" in item.summary  # attribution carried into the body


def test_parse_command_recognizes_approve_with_optional_hash():
    assert parse_command("approve 12") == ApproveCommand(pr=12)
    assert parse_command("approve #12") == ApproveCommand(pr=12)
    assert parse_command("  Approve   7 ") == ApproveCommand(pr=7)


def test_parse_command_returns_none_for_non_commands():
    assert parse_command("add Stake bookmaker") is None
    assert parse_command("approve everything please") is None
    assert parse_command("") is None


def test_is_authorized_checks_allowlist():
    assert is_authorized("U123", ("U123", "U456")) is True
    assert is_authorized("U999", ("U123", "U456")) is False


def test_checks_pass_true_only_when_all_ok_and_nonempty():
    assert checks_pass([{"conclusion": "SUCCESS"}, {"state": "SUCCESS"}]) is True
    assert checks_pass([{"conclusion": "SUCCESS"}, {"conclusion": "SKIPPED"}]) is True
    assert checks_pass([{"conclusion": "FAILURE"}]) is False
    assert checks_pass([{"state": "PENDING"}]) is False
    assert checks_pass([]) is False  # no checks -> fail-safe, not green


def test_closing_issue_numbers_extracts_numbers():
    view = {"closingIssuesReferences": [{"number": 8}, {"number": 11}]}
    assert closing_issue_numbers(view) == [8, 11]
    assert closing_issue_numbers({}) == []


def test_load_config_reads_json(tmp_path):
    p = tmp_path / ".chatops.json"
    p.write_text(json.dumps({"approvers": ["U1"], "tickets_channel": "C1"}), encoding="utf-8")
    cfg = load_config(p)
    assert cfg["approvers"] == ["U1"]
    assert cfg["tickets_channel"] == "C1"


def test_reply_formatters():
    assert "#5" in queued(5, "Add Stake") and "Add Stake" in queued(5, "Add Stake")
    assert "#12" in merged(12, 8) and "#8" in merged(12, 8)
    assert "#12" in rejected(12, "CI not green") and "CI not green" in rejected(12, "CI not green")


def test_parse_command_recognizes_pause_with_optional_reason():
    assert parse_command("pause") == PauseCommand(reason="")
    assert parse_command("Pause canary too noisy") == PauseCommand(reason="canary too noisy")


def test_parse_command_recognizes_resume():
    assert parse_command("resume") == ResumeCommand()
    assert parse_command("  RESUME ") == ResumeCommand()


def test_parse_command_still_handles_approve_and_chatter():
    assert parse_command("approve 12") == ApproveCommand(pr=12)
    assert parse_command("add Stake bookmaker") is None
    assert parse_command("pausing the project tomorrow") is None  # not a bare 'pause'


def test_pause_resume_reply_formatters():
    assert "pause" in paused("noisy").lower()
    assert "noisy" in paused("noisy")
    assert "resum" in resumed().lower()


def test_parse_design_ok():
    from bookieskit.orchestration.chatops import DesignOkCommand

    assert parse_command("design ok 42") == DesignOkCommand(issue=42)
    assert parse_command("Design OK #42") == DesignOkCommand(issue=42)


def test_parse_design_no_with_notes():
    from bookieskit.orchestration.chatops import DesignChangesCommand

    cmd = parse_command("design no 42 use a parameterized mapping instead")
    assert cmd == DesignChangesCommand(issue=42, notes="use a parameterized mapping instead")


def test_parse_council():
    from bookieskit.orchestration.chatops import CouncilCommand

    assert parse_command("council 42") == CouncilCommand(issue=42)


def test_design_commands_dont_collide_with_others():
    from bookieskit.orchestration.chatops import ApproveCommand

    assert parse_command("approve 14") == ApproveCommand(pr=14)
    assert parse_command("designing something later") is None
    assert parse_command("design 42") is None  # needs ok/no


def test_design_reply_formatters():
    from bookieskit.orchestration.chatops import design_changes_ack, design_ready

    assert "#42" in design_ready(42) and "ready" in design_ready(42).lower()
    assert "#42" in design_changes_ack(42)
