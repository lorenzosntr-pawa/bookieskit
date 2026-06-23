import subprocess

import pytest

from bookieskit.orchestration.gh import GhRunner


class _RecordingRun:
    """Captures the argv each gh call would run and returns a canned stdout."""

    def __init__(self, stdout: str = ""):
        self.stdout = stdout
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        assert kwargs.get("check") is True
        assert kwargs.get("capture_output") is True
        assert kwargs.get("text") is True
        return subprocess.CompletedProcess(argv, 0, self.stdout, "")


def _gh(monkeypatch, stdout: str = "") -> tuple[GhRunner, _RecordingRun]:
    rec = _RecordingRun(stdout)
    monkeypatch.setattr(subprocess, "run", rec)
    return GhRunner(), rec


def test_list_issues_builds_json_and_label_args(monkeypatch):
    gh, rec = _gh(
        monkeypatch,
        stdout='[{"number": 7, "title": "t", "body": "b", '
        '"labels": [{"name": "stream:maintenance"}], "state": "open"}]',
    )
    out = gh.list_issues(labels=["stream:maintenance"], state="open")
    assert out[0]["number"] == 7
    argv = rec.calls[0]
    assert argv[:2] == ["gh", "issue"]
    assert "list" in argv
    assert "--state" in argv and "open" in argv
    assert "--label" in argv and "stream:maintenance" in argv
    # The --json fields the queue needs are all requested.
    json_idx = argv.index("--json")
    fields = argv[json_idx + 1]
    for field in ("number", "title", "body", "labels", "state"):
        assert field in fields


def test_create_issue_parses_trailing_number_from_url(monkeypatch):
    gh, rec = _gh(
        monkeypatch, stdout="https://github.com/o/r/issues/42\n"
    )
    n = gh.create_issue(title="T", body="B", labels=["stream:maintenance"])
    assert n == 42
    argv = rec.calls[0]
    assert "create" in argv
    assert "--title" in argv and "T" in argv
    assert "--body" in argv and "B" in argv
    assert "--label" in argv and "stream:maintenance" in argv


def test_create_issue_raises_when_no_number_in_output(monkeypatch):
    gh, _ = _gh(monkeypatch, stdout="something went wrong\n")
    with pytest.raises(ValueError):
        gh.create_issue(title="T", body="B", labels=[])


def test_comment_issue_calls_gh_issue_comment(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.comment_issue(7, "a note")
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "issue", "comment"]
    assert "7" in argv
    assert "--body" in argv and "a note" in argv


def test_edit_issue_adds_and_removes_labels(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.edit_issue(7, add_labels=["status:claimed"], remove_labels=["x"])
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "issue", "edit"]
    assert "--add-label" in argv and "status:claimed" in argv
    assert "--remove-label" in argv and "x" in argv


def test_edit_issue_noop_does_not_call_gh(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.edit_issue(7)  # nothing to change
    assert rec.calls == []


def test_close_issue_with_comment(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.close_issue(7, comment="recovered")
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "issue", "close"]
    assert "7" in argv
    assert "--comment" in argv and "recovered" in argv


def test_list_labels_returns_names(monkeypatch):
    gh, _ = _gh(
        monkeypatch, stdout='[{"name": "stream:maintenance"}, {"name": "bug"}]'
    )
    assert gh.list_labels() == ["stream:maintenance", "bug"]


def test_create_label_passes_color_and_description(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.create_label("stream:maintenance", color="d73a4a", description="drift")
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "label", "create"]
    assert "stream:maintenance" in argv
    assert "--color" in argv and "d73a4a" in argv
    assert "--description" in argv and "drift" in argv


def test_run_raises_on_nonzero_exit(monkeypatch):
    def _boom(argv, **kwargs):
        raise subprocess.CalledProcessError(1, argv, "", "gh: not authed")

    monkeypatch.setattr(subprocess, "run", _boom)
    gh = GhRunner()
    with pytest.raises(subprocess.CalledProcessError):
        gh.list_labels()


def test_pr_view_requests_the_guardrail_fields(monkeypatch):
    gh, rec = _gh(
        monkeypatch,
        stdout='{"state":"OPEN","body":"Closes #8","statusCheckRollup":'
        '[{"conclusion":"SUCCESS"}],"closingIssuesReferences":[{"number":8}]}',
    )
    view = gh.pr_view(11)
    assert view["closingIssuesReferences"][0]["number"] == 8
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "pr", "view"]
    assert "11" in argv
    json_idx = argv.index("--json")
    fields = argv[json_idx + 1]
    for field in ("state", "body", "statusCheckRollup", "closingIssuesReferences"):
        assert field in fields


def test_merge_pr_squashes_by_default(monkeypatch):
    gh, rec = _gh(monkeypatch)
    gh.merge_pr(11)
    argv = rec.calls[0]
    assert argv[:3] == ["gh", "pr", "merge"]
    assert "11" in argv
    assert "--squash" in argv
