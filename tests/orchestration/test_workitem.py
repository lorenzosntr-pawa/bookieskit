from bookieskit.orchestration.workitem import (
    WorkItem,
    parse_meta,
    render_body,
)


def test_render_body_has_yaml_block_with_signature_and_stream():
    item = WorkItem(
        signature="canary:betika:structure",
        stream="stream:maintenance",
        title="betika structure drift",
        summary="The betika payload shape changed.",
    )
    body = render_body(item)
    assert "```yaml" in body
    assert "signature: canary:betika:structure" in body
    assert "stream: stream:maintenance" in body
    assert "The betika payload shape changed." in body
    # The prose sits below the closing fence.
    assert body.index("```yaml") < body.index("The betika payload shape")


def test_render_body_includes_meta_scalars():
    item = WorkItem(
        signature="canary:betika:missing:1x2_ft",
        stream="stream:maintenance",
        title="betika missing 1x2_ft",
        summary="Core market stopped resolving.",
        meta={"platform": "betika", "canonical": "1x2_ft"},
    )
    body = render_body(item)
    assert "platform: betika" in body
    assert "canonical: 1x2_ft" in body


def test_parse_meta_round_trips_signature_stream_and_meta():
    item = WorkItem(
        signature="canary:betika:missing:1x2_ft",
        stream="stream:maintenance",
        title="t",
        summary="s",
        meta={"platform": "betika", "canonical": "1x2_ft"},
    )
    meta = parse_meta(render_body(item))
    assert meta["signature"] == "canary:betika:missing:1x2_ft"
    assert meta["stream"] == "stream:maintenance"
    assert meta["platform"] == "betika"
    assert meta["canonical"] == "1x2_ft"


def test_parse_meta_returns_empty_when_no_yaml_block():
    assert parse_meta("Just a hand-filed issue with no meta block.") == {}


def test_parse_meta_returns_empty_on_malformed_block():
    # A yaml fence with no key: value lines -> {}.
    body = "```yaml\njust prose, no colon pairs\n```\n"
    assert parse_meta(body) == {}


def test_parse_meta_takes_only_the_first_block():
    body = (
        "```yaml\nsignature: a\nstream: stream:maintenance\n```\n"
        "noise\n"
        "```yaml\nsignature: b\n```\n"
    )
    assert parse_meta(body)["signature"] == "a"
