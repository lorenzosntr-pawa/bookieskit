import json

from bookieskit.devtools.fixtures import FIXTURES_ROOT, capture


def test_capture_writes_pretty_json_and_returns_path(tmp_path):
    payload = {"marketsInGroup": [{"marketId": "1", "name": "X"}]}
    path = capture(payload, "betway", "my_market", root=tmp_path)
    assert path == tmp_path / "betway" / "my_market.json"
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == payload
    # pretty-printed (indented), not a single line
    assert "\n" in path.read_text(encoding="utf-8")


def test_capture_creates_platform_subdir(tmp_path):
    capture({"a": 1}, "sportybet", "foo", root=tmp_path)
    assert (tmp_path / "sportybet").is_dir()


def test_fixtures_root_points_at_event_info():
    assert FIXTURES_ROOT.name == "event_info"
    assert FIXTURES_ROOT.parent.name == "fixtures"
