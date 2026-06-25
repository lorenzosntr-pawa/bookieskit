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
        self.pr_views = {}
        self.reviewed = []
        self.merged = []
        self._open_prs = []
        self._pr_comments = {}
        self._pr_reviews = {}
        self.pr_comments_posted = []

    def list_labels(self):
        return list(self._labels)

    def create_label(self, name, *, color, description):
        self._labels.append(name)

    def list_issues(self, *, labels=(), state="open"):
        out = [i for i in self.issues if state == "all" or i.get("state", "open") == state]
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

    def edit_issue(
        self,
        number,
        *,
        body=None,
        add_labels=(),
        remove_labels=(),
    ):
        for i in self.issues:
            if i["number"] == number:
                for lb in add_labels:
                    if lb not in {lbl["name"] for lbl in i["labels"]}:
                        i["labels"].append({"name": lb})
                i["labels"] = [
                    lbl for lbl in i["labels"]
                    if lbl["name"] not in remove_labels
                ]

    def close_issue(self, number, *, comment=None):
        for i in self.issues:
            if i["number"] == number:
                i["state"] = "closed"
        self.closed.append((number, comment))

    def pr_view(self, pr):
        return self.pr_views[pr]

    def review_approve(self, pr, *, token):
        self.reviewed.append((pr, token))

    def merge_pr(self, pr, *, method="squash", token=None):
        self.merged.append((pr, method, token))

    def list_open_prs(self):
        return list(self._open_prs)

    def pr_comments(self, pr):
        return list(self._pr_comments.get(pr, []))

    def pr_reviews(self, pr):
        return list(self._pr_reviews.get(pr, []))

    def comment_pr(self, pr, body):
        self.pr_comments_posted.append((pr, body))


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


from bookieskit.orchestration.workitem import WorkItem, render_body  # noqa: E402


def test_next_returns_top_item_json(capsys):
    gh = _FakeGh()
    gh.create_issue(title="fix betika", body=render_body(WorkItem(
        signature="canary:betika:structure", stream="stream:maintenance",
        title="fix betika", summary="s")), labels=["stream:maintenance"])
    gh.create_issue(title="add stake", body=render_body(WorkItem(
        signature="directed:add-stake", stream="stream:directed",
        title="add stake", summary="s")), labels=["stream:directed"])
    args = cli.build_parser().parse_args(["next", "--json"])
    code = cli.run(args, gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["stream"] == "stream:directed"  # directed beats maintenance
    assert out["title"] == "add stake"


def test_next_emits_null_when_queue_empty(capsys):
    args = cli.build_parser().parse_args(["next", "--json"])
    code = cli.run(args, gh=_FakeGh())
    assert code == 0
    assert json.loads(capsys.readouterr().out) is None


def test_claim_adds_label(capsys):
    gh = _FakeGh()
    n = gh.create_issue(title="t", body="b", labels=["stream:directed"])
    code = cli.run(cli.build_parser().parse_args(["claim", str(n)]), gh=gh)
    assert code == 0
    assert "status:claimed" in {lb["name"] for lb in gh.issues[0]["labels"]}


def test_mark_in_review_requires_pr_and_transitions(capsys):
    gh = _FakeGh()
    n = gh.create_issue(
        title="t", body="b", labels=["stream:directed", "status:claimed"])
    code = cli.run(cli.build_parser().parse_args(
        ["mark-in-review", str(n), "--pr", "https://x/pull/3"]), gh=gh)
    assert code == 0
    names = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "status:in-review" in names and "status:claimed" not in names


def test_mark_blocked_requires_reason(capsys):
    gh = _FakeGh()
    n = gh.create_issue(
        title="t", body="b", labels=["stream:directed", "status:claimed"])
    code = cli.run(cli.build_parser().parse_args(
        ["mark-blocked", str(n), "--reason", "no key"]), gh=gh)
    assert code == 0
    assert "status:blocked" in {lb["name"] for lb in gh.issues[0]["labels"]}


def test_sync_canary_json_includes_slack_text(capsys):
    from bookieskit.orchestration.notify import canary_digest
    gh = _FakeGh()
    code = cli.run(
        cli.build_parser().parse_args(["sync-canary", "--sport", "soccer", "--json"]),
        runner=_runner_drift, gh=gh,
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "slack_text" in payload
    assert payload["slack_text"] == canary_digest(
        payload["opened"], payload["updated"], payload["closed"], "soccer"
    )
    assert payload["slack_text"]  # non-empty: there was drift


def test_chatops_intake_opens_then_is_idempotent(capsys):
    gh = _FakeGh()
    code = cli.run(
        cli.build_parser().parse_args([
            "chatops", "intake", "--author", "U1", "--ts", "1.0001",
            "--title", "Add Stake", "--summary", "Support Stake", "--json",
        ]),
        gh=gh,
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "opened"
    first = out["number"]
    assert "Add Stake" in out["slack_text"]
    # Filed as status:designing so it is NOT buildable until `design ok`.
    labels = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "stream:directed" in labels and "status:designing" in labels

    # Re-running with the same ts must NOT open a second issue.
    code = cli.run(
        cli.build_parser().parse_args([
            "chatops", "intake", "--author", "U1", "--ts", "1.0001",
            "--title", "Add Stake", "--summary", "Support Stake", "--json",
        ]),
        gh=gh,
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "duplicate"
    assert out["number"] == first
    assert out["slack_text"] == ""
    assert len(gh.issues) == 1  # no second issue was filed


def _approve_args(pr, author, config):
    return cli.build_parser().parse_args([
        "chatops", "approve", "--pr", str(pr), "--author", author,
        "--config", str(config), "--json",
    ])


def _chatops_config(tmp_path, approvers=("U1",)):
    import json as _json
    p = tmp_path / ".chatops.json"
    p.write_text(_json.dumps({"approvers": list(approvers), "tickets_channel": "C1"}))
    return p


def test_chatops_approve_rejects_unauthorized(capsys, tmp_path):
    gh = _FakeGh()  # no pr_view/merge needed; auth fails first
    code = cli.run(_approve_args(11, "U999", _chatops_config(tmp_path)), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "rejected" and "authorized" in out["reason"]
    assert gh.merged == []  # never merged


def test_chatops_approve_rejects_when_ci_not_green(capsys, tmp_path):
    gh = _FakeGh()
    gh.pr_views = {11: {
        "state": "OPEN",
        "statusCheckRollup": [{"conclusion": "FAILURE"}],
        "closingIssuesReferences": [{"number": 8}],
    }}
    code = cli.run(_approve_args(11, "U1", _chatops_config(tmp_path)), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "rejected" and "CI" in out["reason"]
    assert gh.merged == []


def test_chatops_approve_rejects_pr_not_open(capsys, tmp_path):
    gh = _FakeGh()  # an already-merged PR -> clean rejection, not a gh error
    gh.pr_views = {11: {
        "state": "MERGED",
        "statusCheckRollup": [{"conclusion": "SUCCESS"}],
        "closingIssuesReferences": [{"number": 8}],
    }}
    code = cli.run(_approve_args(11, "U1", _chatops_config(tmp_path)), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "rejected" and "not open" in out["reason"]
    assert gh.merged == []


def test_chatops_approve_rejects_non_loop_pr(capsys, tmp_path):
    gh = _FakeGh()  # closes #8, but no in-review issue exists
    gh.pr_views = {11: {
        "state": "OPEN",
        "statusCheckRollup": [{"conclusion": "SUCCESS"}],
        "closingIssuesReferences": [{"number": 8}],
    }}
    code = cli.run(_approve_args(11, "U1", _chatops_config(tmp_path)), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "rejected" and "loop" in out["reason"]
    assert gh.merged == []


def test_chatops_approve_merges_green_loop_pr(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_read_owner_token", lambda: "ghp_owner")
    gh = _FakeGh(issues=[{
        "number": 8, "title": "Add Stake", "body": "b",
        "labels": [{"name": "stream:directed"}, {"name": "status:in-review"}],
        "state": "open",
    }])
    gh.pr_views = {11: {
        "state": "OPEN",
        "statusCheckRollup": [{"conclusion": "SUCCESS"}],
        "closingIssuesReferences": [{"number": 8}],
    }}
    code = cli.run(_approve_args(11, "U1", _chatops_config(tmp_path)), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "merged" and out["issue"] == 8
    assert gh.merged == [(11, "squash", "ghp_owner")]  # merged once, squash, with owner token
    assert "#11" in out["slack_text"]


def test_chatops_pause_authorized_sets_marker(capsys, tmp_path):
    gh = _FakeGh()
    code = cli.run(cli.build_parser().parse_args(
        ["chatops", "pause", "--author", "U1", "--reason", "noisy",
         "--config", str(_chatops_config(tmp_path)), "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "paused"
    from bookieskit.orchestration import control
    assert control.is_paused(gh) is True


def test_chatops_pause_unauthorized_does_nothing(capsys, tmp_path):
    gh = _FakeGh()
    code = cli.run(cli.build_parser().parse_args(
        ["chatops", "pause", "--author", "U999",
         "--config", str(_chatops_config(tmp_path)), "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "rejected"
    from bookieskit.orchestration import control
    assert control.is_paused(gh) is False  # not paused by a non-approver


def test_chatops_resume_clears_marker(capsys, tmp_path):
    from bookieskit.orchestration import control
    gh = _FakeGh()
    control.set_paused(gh, reason="x", author="U1")
    code = cli.run(cli.build_parser().parse_args(
        ["chatops", "resume", "--author", "U1",
         "--config", str(_chatops_config(tmp_path)), "--json"]), gh=gh)
    assert code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "resumed"
    assert control.is_paused(gh) is False


def test_chatops_paused_reports_state(capsys):
    from bookieskit.orchestration import control
    gh = _FakeGh()
    control.set_paused(gh, reason="x", author="U1")
    code = cli.run(cli.build_parser().parse_args(["chatops", "paused", "--json"]), gh=gh)
    assert code == 0
    assert json.loads(capsys.readouterr().out)["paused"] is True


def test_lock_acquire_then_busy_then_release(tmp_path, capsys):
    p = str(tmp_path / "tick.lock")
    assert cli.run(cli.build_parser().parse_args(
        ["lock", "acquire", "--path", p, "--json"])) == 0
    capsys.readouterr()
    # second acquire while held -> exit 3 (busy)
    assert cli.run(cli.build_parser().parse_args(
        ["lock", "acquire", "--path", p, "--json"])) == 3
    capsys.readouterr()
    # release, then acquire succeeds again
    assert cli.run(cli.build_parser().parse_args(
        ["lock", "release", "--path", p, "--json"])) == 0
    capsys.readouterr()
    assert cli.run(cli.build_parser().parse_args(
        ["lock", "acquire", "--path", p, "--json"])) == 0


def test_chatops_resume_unauthorized_does_nothing(capsys, tmp_path):
    # Symmetric to the pause guard: a non-approver must NOT be able to resume
    # (clear the pause marker) — the kill-switch authz protects both directions.
    from bookieskit.orchestration import control
    gh = _FakeGh()
    control.set_paused(gh, reason="x", author="U1")  # paused by an approver
    code = cli.run(cli.build_parser().parse_args(
        ["chatops", "resume", "--author", "U999",
         "--config", str(_chatops_config(tmp_path)), "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "rejected"
    assert control.is_paused(gh) is True  # marker NOT cleared by a non-approver


def test_gate_runs_when_queue_actionable(tmp_path, capsys, monkeypatch):
    # A ready directed issue -> actionable -> run=true even with no Slack signal.
    gh = _FakeGh(issues=[{"number": 5, "title": "t",
        "body": "```yaml\nsignature: s\nstream: stream:directed\n```",
        "labels": [{"name": "stream:directed"}, {"name": "status:ready"}],
        "state": "open"}])
    # Fake the Slack reader so no network happens.
    monkeypatch.setattr(cli, "_slack_get", lambda method, **kw: {"messages": [], "ok": True})
    code = cli.run(cli.build_parser().parse_args(
        ["gate", "--watermark", str(tmp_path / "wm"), "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["run"] is True


def test_gate_quiet_when_nothing_to_do(tmp_path, capsys, monkeypatch):
    gh = _FakeGh()  # empty queue
    monkeypatch.setattr(cli, "_slack_get", lambda method, **kw: {"messages": [], "ok": True})
    code = cli.run(cli.build_parser().parse_args(
        ["gate", "--watermark", str(tmp_path / "wm"), "--json"]), gh=gh)
    assert code == 0
    assert json.loads(capsys.readouterr().out)["run"] is False


def test_gate_runs_on_designing_thread_reply(tmp_path, capsys, monkeypatch):
    # A status:designing directed issue whose thread's last message is human
    # -> the agent owes a reply -> gate runs (reason: design-reply).
    from bookieskit.orchestration.workitem import WorkItem, render_body
    body = render_body(WorkItem(
        signature="directed:slack:1.0", stream="stream:directed",
        title="add X", summary="s", meta={"slack_ts": "1.0"}))
    gh = _FakeGh(issues=[{"number": 9, "title": "add X", "body": body,
        "labels": [{"name": "stream:directed"}, {"name": "status:designing"}],
        "state": "open"}])

    def fake_slack(method, **kw):
        if method == "conversations.replies":
            return {"messages": [{"type": "message"}]}  # last is human -> waiting
        return {"messages": []}  # history: no new top-level ticket

    monkeypatch.setattr(cli, "_read_token", lambda: "xoxb-test")  # CI has no .mcp.json
    monkeypatch.setattr(cli, "_slack_get", fake_slack)
    code = cli.run(cli.build_parser().parse_args(
        ["gate", "--config", str(_chatops_config(tmp_path)),
         "--watermark", str(tmp_path / "wm"), "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["run"] is True
    assert out["reason"] == "design-reply"  # not actionable-queue / new-ticket


def test_design_ok_flips_designing_to_ready(capsys, tmp_path):
    gh = _FakeGh(issues=[{"number": 7, "title": "t", "body": "b",
        "labels": [{"name": "stream:directed"}, {"name": "status:designing"}],
        "state": "open"}])
    code = cli.run(cli.build_parser().parse_args(
        ["chatops", "design-ok", "--issue", "7", "--author", "U1",
         "--config", str(_chatops_config(tmp_path)), "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ready"
    labels = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "status:ready" in labels and "status:designing" not in labels


def test_design_ok_unauthorized_no_change(capsys, tmp_path):
    gh = _FakeGh(issues=[{"number": 7, "title": "t", "body": "b",
        "labels": [{"name": "stream:directed"}, {"name": "status:designing"}],
        "state": "open"}])
    code = cli.run(cli.build_parser().parse_args(
        ["chatops", "design-ok", "--issue", "7", "--author", "U999",
         "--config", str(_chatops_config(tmp_path)), "--json"]), gh=gh)
    assert code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "rejected"
    labels = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "status:designing" in labels  # unchanged


def test_chatops_status_emits_snapshot(capsys):
    gh = _FakeGh(issues=[{"number": 21, "title": "cards", "state": "open",
        "labels": [{"name": "stream:directed"}, {"name": "status:ready"}]}])
    code = cli.run(cli.build_parser().parse_args(["chatops", "status", "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert "#21" in out["slack_text"] and "ready" in out["slack_text"]


def test_status_board_posts_then_updates(tmp_path, capsys, monkeypatch):
    gh = _FakeGh()
    calls = []
    def fake_post(method, **kw):
        calls.append(method)
        return {"ok": True, "ts": "111.0", "channel": "C_STATUS"}
    monkeypatch.setattr(cli, "_read_token", lambda: "xoxb-test")
    monkeypatch.setattr(cli, "_slack_post", fake_post)
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"approvers": ["U1"], "tickets_channel": "C1",
                               "status_channel": "C_STATUS"}))
    sf = tmp_path / "board.json"
    args = ["status", "board", "--config", str(cfg), "--state-file", str(sf)]
    # first run -> postMessage (no stored id)
    assert cli.run(cli.build_parser().parse_args(args), gh=gh) == 0
    assert calls == ["chat.postMessage"]
    # second run -> chat.update (id now stored)
    assert cli.run(cli.build_parser().parse_args(args), gh=gh) == 0
    assert calls[-1] == "chat.update"


def test_token_reuses_fresh_cache(tmp_path, monkeypatch, capsys):
    cache = tmp_path / "app-token.json"
    cache.write_text(
        json.dumps({"token": "ghs_fresh", "expires_at": "2999-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    ident = tmp_path / "identity.json"
    ident.write_text(json.dumps({"app_id": 1, "installation_id": 2}), encoding="utf-8")

    def boom(**kwargs):  # mint must NOT be called when cache is fresh
        raise AssertionError("should not mint")

    monkeypatch.setattr(cli.appauth, "mint_installation_token", boom)
    rc = cli.main(["token", "--identity", str(ident), "--cache", str(cache)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "ghs_fresh"


def test_token_mints_when_cache_stale(tmp_path, monkeypatch, capsys):
    cache = tmp_path / "app-token.json"  # absent -> stale
    ident = tmp_path / "identity.json"
    ident.write_text(json.dumps({"app_id": 1, "installation_id": 2}), encoding="utf-8")
    pem = tmp_path / "app.pem"
    pem.write_text("KEY", encoding="utf-8")

    monkeypatch.setattr(
        cli.appauth, "mint_installation_token",
        lambda **kw: {"token": "ghs_new", "expires_at": "2999-01-01T00:00:00Z"},
    )
    rc = cli.main(
        ["token", "--identity", str(ident), "--cache", str(cache), "--key", str(pem)]
    )
    assert rc == 0
    assert capsys.readouterr().out.strip() == "ghs_new"
    assert json.loads(cache.read_text())["token"] == "ghs_new"


def test_token_exit1_when_unprovisioned(tmp_path, capsys):
    # Point --cache at a tmp path so the test never reads a real, freshly-minted
    # .orchestrator/app-token.json on the dev machine (hermetic isolation).
    rc = cli.main(["token", "--identity", str(tmp_path / "missing.json"),
                   "--cache", str(tmp_path / "c.json")])
    assert rc == 1
    assert "not provisioned" in capsys.readouterr().err


def test_token_exit1_when_identity_malformed(tmp_path, capsys):
    # present but missing required keys -> still "unprovisioned", not a traceback
    ident = tmp_path / "identity.json"
    ident.write_text('{"app_id": 1}', encoding="utf-8")  # no installation_id
    key = tmp_path / "app.pem"
    key.write_text("KEY", encoding="utf-8")
    rc = cli.main(
        ["token", "--identity", str(ident), "--key", str(key),
         "--cache", str(tmp_path / "c.json")]
    )
    assert rc == 1
    assert "not provisioned" in capsys.readouterr().err


def test_approve_uses_owner_token_for_review_and_merge(tmp_path, monkeypatch):
    # owner token on disk
    monkeypatch.setattr(cli, "_read_owner_token", lambda: "ghp_owner")

    class FakeGh:
        def __init__(self):
            self.review = None
            self.merge = None

        def pr_view(self, pr):
            return {"state": "OPEN", "statusCheckRollup": [],
                    "closingIssuesReferences": [{"number": 8}]}

        def list_issues(self, *, state, labels=()):
            return [{"number": 8}]

        def review_approve(self, pr, *, token):
            self.review = (pr, token)

        def merge_pr(self, pr, *, method="squash", token=None):
            self.merge = (pr, method, token)

    fake = FakeGh()
    monkeypatch.setattr(cli.chatops, "checks_pass", lambda rollup: True)
    monkeypatch.setattr(cli.chatops, "is_authorized", lambda a, allow: True)
    monkeypatch.setattr(cli.chatops, "load_config", lambda cfg: {"approvers": ["U"]})
    monkeypatch.setattr(cli.chatops, "closing_issue_numbers", lambda v: [8])

    import argparse
    args = argparse.Namespace(pr=11, author="U", config="x", as_json=True)
    rc = cli._chatops_approve(args, fake)
    assert rc == 0
    assert fake.review == (11, "ghp_owner")
    assert fake.merge == (11, "squash", "ghp_owner")


def test_approve_rejects_when_no_owner_token(monkeypatch):
    monkeypatch.setattr(cli, "_read_owner_token", lambda: None)
    monkeypatch.setattr(cli.chatops, "is_authorized", lambda a, allow: True)
    monkeypatch.setattr(cli.chatops, "load_config", lambda cfg: {"approvers": ["U"]})

    class FakeGh:
        def pr_view(self, pr):
            return {"state": "OPEN", "statusCheckRollup": [],
                    "closingIssuesReferences": [{"number": 8}]}

        def list_issues(self, *, state, labels=()):
            return [{"number": 8}]

    import argparse
    monkeypatch.setattr(cli.chatops, "checks_pass", lambda rollup: True)
    monkeypatch.setattr(cli.chatops, "closing_issue_numbers", lambda v: [8])
    args = argparse.Namespace(pr=11, author="U", config="x", as_json=True)
    rc = cli._chatops_approve(args, FakeGh())
    assert rc == 0  # a rejection is a handled outcome


# ---------------------------------------------------------------------------
# Task 3: pr-review pending + gate pr_awaiting
# ---------------------------------------------------------------------------

def _in_review_issue(n):
    from bookieskit.orchestration.workitem import WorkItem, render_body
    return {"number": n, "title": "t",
            "body": render_body(WorkItem(signature="directed:x",
                stream="stream:directed", title="t", summary="s")),
            "labels": [{"name": "stream:directed"}, {"name": "status:in-review"}],
            "state": "open"}


def test_pr_review_pending_returns_pr_with_human_comment(capsys):
    gh = _FakeGh(issues=[_in_review_issue(8)])
    gh._open_prs = [{"number": 11, "headRefName": "feat/x",
                     "closingIssuesReferences": [{"number": 8}]}]
    gh._pr_comments = {11: [{"created_at": "2026-06-25T10:00:00Z",
                             "user": {"type": "User"}, "body": "why?"}]}
    code = cli.run(cli.build_parser().parse_args(["pr-review", "pending", "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pr"] == 11 and out["issue"] == 8 and out["head"] == "feat/x"


def test_pr_review_pending_null_when_newest_is_bot(capsys):
    gh = _FakeGh(issues=[_in_review_issue(8)])
    gh._open_prs = [{"number": 11, "headRefName": "feat/x",
                     "closingIssuesReferences": [{"number": 8}]}]
    gh._pr_comments = {11: [{"created_at": "2026-06-25T10:00:00Z",
                             "user": {"type": "Bot"}, "body": "done"}]}
    code = cli.run(cli.build_parser().parse_args(["pr-review", "pending", "--json"]), gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out is None


def test_gate_reports_pr_reply(monkeypatch, capsys, tmp_path):
    gh = _FakeGh(issues=[_in_review_issue(8)])
    gh._open_prs = [{"number": 11, "headRefName": "feat/x",
                     "closingIssuesReferences": [{"number": 8}]}]
    gh._pr_comments = {11: [{"created_at": "2026-06-25T10:00:00Z",
                             "user": {"type": "User"}, "body": "why?"}]}
    # No Slack token -> new_ticket/designing skipped; queue has only an in-review
    # item (not actionable). Point --config/--watermark at empty tmp paths.
    args = cli.build_parser().parse_args(
        ["gate", "--json", "--config", str(tmp_path / "c.json"),
         "--watermark", str(tmp_path / "wm")])
    code = cli.run(args, gh=gh)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["run"] is True
    assert out["reason"] == "pr-reply"
    assert out["pr_awaiting"] == 11
