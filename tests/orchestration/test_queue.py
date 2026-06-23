from bookieskit.orchestration.queue import Queue
from bookieskit.orchestration.workitem import WorkItem, render_body


class _FakeGh:
    """In-memory GhRunner fake: tracks open issues + records mutations."""

    def __init__(self):
        self.issues: list[dict] = []
        self._next = 1
        self.comments: list[tuple[int, str]] = []
        self.closed: list[tuple[int, str | None]] = []
        # Pretend every label already exists so ensure_labels is a no-op.
        self._labels = [
            "stream:maintenance", "stream:expansion", "stream:directed",
            "stream:capability", "status:claimed", "status:in-review",
        ]

    def list_labels(self):
        return list(self._labels)

    def create_label(self, name, *, color, description):
        self._labels.append(name)

    def list_issues(self, *, labels=(), state="open"):
        out = [i for i in self.issues if i["state"] == state]
        for label in labels:
            out = [
                i for i in out
                if label in [lb["name"] for lb in i["labels"]]
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

    def edit_issue(self, number, *, body=None, add_labels=(), remove_labels=()):
        for issue in self.issues:
            if issue["number"] == number:
                names = {lb["name"] for lb in issue.get("labels", [])}
                names -= set(remove_labels)
                names |= set(add_labels)
                issue["labels"] = [{"name": n} for n in names]
                if body is not None:
                    issue["body"] = body
                return


def _item(sig="canary:betika:structure"):
    return WorkItem(
        signature=sig, stream="stream:maintenance",
        title="t", summary="s", meta={"platform": "betika"},
    )


def test_open_or_update_creates_when_absent():
    gh = _FakeGh()
    q = Queue(gh)
    number, action = q.open_or_update(_item(), note="opened")
    assert action == "opened"
    assert number == 1
    assert gh.issues[0]["labels"] == [{"name": "stream:maintenance"}]


def test_open_or_update_comments_when_present():
    gh = _FakeGh()
    q = Queue(gh)
    n1, _ = q.open_or_update(_item(), note="first")
    n2, action = q.open_or_update(_item(), note="still drifting")
    assert action == "updated"
    assert n2 == n1
    assert gh.comments == [(n1, "still drifting")]
    assert len(gh.issues) == 1  # no duplicate


def test_find_open_by_signature_matches_via_parsed_meta():
    gh = _FakeGh()
    gh.create_issue(
        title="t", body=render_body(_item("canary:msport:structure")),
        labels=["stream:maintenance"],
    )
    q = Queue(gh, ensure=False)
    found = q.find_open_by_signature("canary:msport:structure")
    assert found is not None and found["number"] == 1
    assert q.find_open_by_signature("canary:nope:structure") is None


def test_find_open_ignores_issue_without_meta_block():
    gh = _FakeGh()
    gh.create_issue(title="hand-filed", body="no meta here", labels=[])
    q = Queue(gh, ensure=False)
    assert q.find_open_by_signature("canary:betika:structure") is None


def test_close_by_signature_closes_and_returns_number():
    gh = _FakeGh()
    q = Queue(gh)
    n, _ = q.open_or_update(_item(), note="opened")
    closed = q.close_by_signature(_item().signature, reason="recovered")
    assert closed == n
    assert gh.closed == [(n, "recovered")]
    assert gh.issues[0]["state"] == "closed"


def test_close_by_signature_returns_none_when_absent():
    gh = _FakeGh()
    q = Queue(gh)
    assert q.close_by_signature("canary:ghost:structure", reason="x") is None


def test_list_open_filters_by_stream():
    gh = _FakeGh()
    q = Queue(gh)
    q.open_or_update(_item(), note="opened")
    assert len(q.list_open()) == 1
    assert len(q.list_open(stream="stream:maintenance")) == 1
    assert q.list_open(stream="stream:expansion") == []


def test_constructor_ensure_true_creates_missing_labels():
    gh = _FakeGh()
    gh._labels = ["bug"]  # nothing of ours exists yet
    Queue(gh)  # ensure=True by default
    assert "stream:maintenance" in gh._labels
    assert "status:claimed" in gh._labels


def test_claim_adds_status_claimed_label():
    gh = _FakeGh()
    n = gh.create_issue(title="t", body="b", labels=["stream:directed"])
    Queue(gh, ensure=False).claim(n)
    names = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "status:claimed" in names


def test_mark_in_review_swaps_labels_and_comments_pr():
    gh = _FakeGh()
    n = gh.create_issue(
        title="t", body="b", labels=["stream:directed", "status:claimed"]
    )
    Queue(gh, ensure=False).mark_in_review(n, "https://github.com/o/r/pull/9")
    names = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "status:in-review" in names and "status:claimed" not in names
    assert any("pull/9" in body for _, body in gh.comments)


def test_mark_blocked_swaps_labels_and_comments_reason():
    gh = _FakeGh()
    n = gh.create_issue(
        title="t", body="b", labels=["stream:directed", "status:claimed"]
    )
    Queue(gh, ensure=False).mark_blocked(n, reason="needs an API key")
    names = {lb["name"] for lb in gh.issues[0]["labels"]}
    assert "status:blocked" in names and "status:claimed" not in names
    assert any("needs an API key" in body for _, body in gh.comments)
