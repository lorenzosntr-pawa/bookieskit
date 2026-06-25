from bookieskit.orchestration import status


class _FakeGh:
    def __init__(self, issues): self.issues = issues
    def list_issues(self, *, labels=(), state="open"):
        return [i for i in self.issues if state == "all" or i.get("state","open") == state]


def _issue(n, title, *labels):
    return {"number": n, "title": title, "labels": [{"name": x} for x in labels], "state": "open"}


def test_gather_state_classifies_by_status_label():
    gh = _FakeGh([
        _issue(19, "corners", "stream:directed", "status:claimed"),
        _issue(20, "ht/ft", "stream:directed", "status:designing"),
        _issue(21, "cards", "stream:directed", "status:ready"),
    ])
    st = status.gather_state(gh, paused=False)
    assert st["paused"] is False
    assert st["building"] == 19
    byn = {i["number"]: i["status"] for i in st["items"]}
    assert byn == {19: "claimed", 20: "designing", 21: "ready"}


def test_render_board_active_shows_now_and_queue():
    st = {"paused": False, "building": 19,
          "items": [{"number": 19, "title": "corners", "status": "claimed"},
                    {"number": 20, "title": "ht/ft", "status": "designing"}]}
    out = status.render_board(st, now="15:31")
    assert "active" in out.lower() and "15:31" in out
    assert "#19" in out  # now-building
    assert "#20" in out and "designing" in out  # queue


def test_render_board_paused_and_idle():
    out_p = status.render_board({"paused": True, "building": None, "items": []}, now="15:31")
    assert "pause" in out_p.lower()
    out_i = status.render_board({"paused": False, "building": None, "items": []}, now="15:31")
    assert "idle" in out_i.lower()
