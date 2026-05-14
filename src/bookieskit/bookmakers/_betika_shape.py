"""Shared shape helpers for Betika ``/v1/uo/matches`` responses.

The Betika match endpoints return either ``{"data": [<match>, ...], "meta":
{...}}`` (the documented shape) or a bare list when callers pass the inner
``data`` array directly. Three modules need to walk to ``data[0]``: the
event-info extractors, the markets parser, and the SR-id extractor. This
helper consolidates that walk so a future shape change is a one-line fix.
"""


def betika_first_match(response: object) -> dict | None:
    """Return the first match dict from a Betika response, or None.

    Accepts both the dict-wrapped shape ``{"data": [<match>], "meta": ...}``
    and a bare list of matches. Returns None if the response is the wrong
    type, the data list is empty, or the first element is not a dict.
    """
    if isinstance(response, list):
        data = response
    elif isinstance(response, dict):
        data = response.get("data") or []
    else:
        return None
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    return first if isinstance(first, dict) else None
