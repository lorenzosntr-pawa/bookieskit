# tests/orchestration/test_control.py
from bookieskit.orchestration import control


class _FakeGh:
    def __init__(self, issues=None):
        self.issues = list(issues or [])
        self._next = max((i["number"] for i in self.issues), default=0) + 1
        self.comments = []
        self.closed = []

    def list_issues(self, *, labels=(), state="open"):
        out = [i for i in self.issues if state == "all" or i.get("state", "open") == state]
        for lb in labels:
            out = [i for i in out if lb in [x["name"] for x in i.get("labels", [])]]
        return out

    def create_issue(self, *, title, body, labels):
        n = self._next
        self._next += 1
        self.issues.append({"number": n, "title": title, "body": body,
                            "labels": [{"name": x} for x in labels], "state": "open"})
        return n

    def comment_issue(self, number, body):
        self.comments.append((number, body))

    def close_issue(self, number, *, comment=None):
        for i in self.issues:
            if i["number"] == number:
                i["state"] = "closed"
        self.closed.append((number, comment))


def test_not_paused_when_no_marker():
    assert control.is_paused(_FakeGh()) is False


def test_set_paused_creates_marker_then_is_paused():
    gh = _FakeGh()
    n = control.set_paused(gh, reason="canary noisy", author="U1")
    assert n >= 1
    assert control.is_paused(gh) is True
    # The marker carries the control:paused label.
    assert any("control:paused" in [x["name"] for x in i["labels"]]
               for i in gh.issues if i["number"] == n)


def test_set_paused_twice_comments_not_duplicates():
    gh = _FakeGh()
    n1 = control.set_paused(gh, reason="a", author="U1")
    n2 = control.set_paused(gh, reason="b", author="U1")
    assert n1 == n2  # same marker reused
    assert len([i for i in gh.issues if i["state"] == "open"]) == 1
    assert gh.comments  # second pause left a comment


def test_clear_paused_closes_marker():
    gh = _FakeGh()
    control.set_paused(gh, reason="a", author="U1")
    closed = control.clear_paused(gh, author="U1")
    assert closed and control.is_paused(gh) is False
