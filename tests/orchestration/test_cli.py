import json

from bookieskit.devtools.canary import BookCheck, CanaryReport
from bookieskit.orchestration import cli


class _FakeGh:
    """In-memory gh fake reused for the CLI (labels pre-populated)."""

    def __init__(self, issues=None):
        self.issues = list(issues or [])
        self._next = len(self.issues) + 1
        self.comments = []
        self.closed = []
        self._labels = [
            "stream:maintenance", "stream:expansion", "stream:directed",
            "stream:capability", "status:claimed", "status:in-review",
        ]

    def list_labels(self):
        return list(self._labels)

    def create_label(self, name, *, color, description):
        self._labels.append(name)

    def list_issues(self, *, labels=(), state="open"):
        out = [i for i in self.issues if i.get("state", "open") == state]
        for label in labels:
            out = [
                i for i in out
                if label in [lb["name"] for lb in i.get("labels", [])]
            ]
        return out

    def create_issue(self, *, title, body, labels):
        number = self._next
        self._next += 1
        self.issues.append({
            "number": number, "title": title, "body": body,
            "labels": [{"name": lb} for lb in labels], "state": "open",
        })
        return number

    def comment_issue(self, number, body):
        self.comments.append((number, body))

    def close_issue(self, number, *, comment=None):
        for i in self.issues:
            if i["number"] == number:
                i["state"] = "closed"
        self.closed.append((number, comment))


async def _runner_drift(sport, *, seed=None, max_candidates=3, clients=None):
    return CanaryReport(
        sport=sport, seed="555", sr_numeric="777",
        checks=[
            BookCheck(
                platform="betika", status="drift", reason="structure",
                expected_canonicals=["1x2_ft"], resolved_canonicals=[],
                missing_canonicals=["1x2_ft"], structure_ok=False,
            ),
            BookCheck(
                platform="msport", status="drift", reason="missing",
                expected_canonicals=["1x2_ft"], resolved_canonicals=[],
                missing_canonicals=["1x2_ft"], structure_ok=True,
            ),
        ],
        drifted=True,
    )


async def _runner_ok(sport, *, seed=None, max_candidates=3, clients=None):
    return CanaryReport(
        sport=sport, seed="555", sr_numeric="777",
        checks=[BookCheck(
            platform="betika", status="ok", reason="",
            expected_canonicals=["1x2_ft"], resolved_canonicals=["1x2_ft"],
            missing_canonicals=[], structure_ok=True,
        )],
        drifted=False,
    )


def test_build_parser_has_three_subcommands():
    p = cli.build_parser()
    assert p.parse_args(["sync-canary"]).cmd == "sync-canary"
    assert p.parse_args(["ensure-labels"]).cmd == "ensure-labels"
    qargs = p.parse_args(["queue", "list"])
    assert qargs.cmd == "queue" and qargs.queue_cmd == "list"


def test_sync_canary_json_opens_issue_and_exits_zero(capsys):
    gh = _FakeGh()
    code = cli.run(
        cli.build_parser().parse_args(["sync-canary", "--json"]),
        runner=_runner_drift, gh=gh,
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert "canary:betika:structure" in out["opened"]
    assert "canary:msport:missing:1x2_ft" in out["opened"]
    # The issue was actually filed on the fake.
    assert any(i["title"] for i in gh.issues)


def test_sync_canary_recovery_closes_issue(capsys):
    from bookieskit.orchestration.workitem import WorkItem, render_body
    body = render_body(WorkItem(
        signature="canary:betika:structure", stream="stream:maintenance",
        title="t", summary="s",
    ))
    gh = _FakeGh(issues=[{
        "number": 1, "title": "t", "body": body,
        "labels": [{"name": "stream:maintenance"}], "state": "open",
    }])
    code = cli.run(
        cli.build_parser().parse_args(["sync-canary", "--json"]),
        runner=_runner_ok, gh=gh,
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert "canary:betika:structure" in out["closed"]


def test_ensure_labels_json_reports_created(capsys):
    gh = _FakeGh()
    gh._labels = ["bug"]  # nothing of ours exists
    code = cli.run(
        cli.build_parser().parse_args(["ensure-labels", "--json"]), gh=gh
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert "stream:maintenance" in out["created"]


def test_queue_list_json_lists_open(capsys):
    from bookieskit.orchestration.workitem import WorkItem, render_body
    body = render_body(WorkItem(
        signature="canary:msport:structure", stream="stream:maintenance",
        title="msport structure drift", summary="s",
    ))
    gh = _FakeGh(issues=[{
        "number": 5, "title": "msport structure drift", "body": body,
        "labels": [{"name": "stream:maintenance"}], "state": "open",
    }])
    code = cli.run(
        cli.build_parser().parse_args(
            ["queue", "list", "--stream", "stream:maintenance", "--json"]
        ),
        gh=gh,
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["items"][0]["number"] == 5
    assert out["items"][0]["signature"] == "canary:msport:structure"


def test_sync_canary_maps_canary_error_to_exit_one(capsys):
    async def _boom(sport, *, seed=None, max_candidates=3, clients=None):
        raise RuntimeError("canary blew up")

    code = cli.run(
        cli.build_parser().parse_args(["sync-canary"]),
        runner=_boom, gh=_FakeGh(),
    )
    assert code == 1
