"""Render the live #status board + gather the loop's current state.

Pure render (offline-testable) + a single gh read. The CLI calls these and
pushes the text to Slack via chat.update; the tick refreshes it each cycle.
"""

_STATUS_BY_LABEL = (
    ("status:claimed", "claimed"),
    ("status:designing", "designing"),
    ("status:ready", "ready"),
    ("status:in-review", "in-review"),
    ("status:blocked", "blocked"),
)


def _status_of(labels: set[str]) -> str:
    for label, name in _STATUS_BY_LABEL:
        if label in labels:
            return name
    return "open"


def gather_state(gh, *, paused: bool) -> dict:
    items, building = [], None
    for issue in gh.list_issues(state="open"):
        labels = {lb["name"] for lb in issue.get("labels", [])}
        if not any(lb.startswith("stream:") for lb in labels):
            continue
        st = _status_of(labels)
        items.append({"number": issue["number"],
                      "title": issue.get("title", ""), "status": st})
        if st == "claimed":
            building = issue["number"]
    items.sort(key=lambda i: i["number"])
    return {"paused": paused, "items": items, "building": building}


def render_board(state: dict, *, now: str) -> str:
    if state["paused"]:
        head = f":double_vertical_bar: *Loop:* paused — last update {now}"
    else:
        head = f":green_circle: *Loop:* active — last update {now}"
    if state["building"] is not None:
        now_line = f"*Now:* building #{state['building']}"
    else:
        now_line = "*Now:* idle"
    if state["items"]:
        queue = " · ".join(f"#{i['number']} {i['status']}" for i in state["items"])
    else:
        queue = "empty"
    return f"{head}\n{now_line}\n*Queue:* {queue}"
