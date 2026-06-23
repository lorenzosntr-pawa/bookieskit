from bookieskit.orchestration.labels import (
    STATUS_LABELS,
    STREAM_LABELS,
    ensure_labels,
)


class _FakeGh:
    """Fake GhRunner exposing just list_labels + create_label."""

    def __init__(self, existing: list[str]):
        self._existing = list(existing)
        self.created: list[tuple[str, str, str]] = []

    def list_labels(self) -> list[str]:
        return list(self._existing)

    def create_label(self, name, *, color, description):
        self._existing.append(name)
        self.created.append((name, color, description))


def test_taxonomy_has_the_four_streams_and_three_statuses():
    assert set(STREAM_LABELS) == {
        "stream:maintenance",
        "stream:expansion",
        "stream:directed",
        "stream:capability",
    }
    assert set(STATUS_LABELS) == {
        "status:claimed", "status:in-review", "status:blocked",
    }


def test_ensure_labels_creates_all_when_none_exist():
    gh = _FakeGh(existing=[])
    created = ensure_labels(gh)
    assert set(created) == set(STREAM_LABELS) | set(STATUS_LABELS)
    assert len(gh.created) == 7  # 4 streams + 3 statuses
    # Color + description are passed through from the taxonomy.
    by_name = {c[0]: c for c in gh.created}
    name, color, desc = by_name["stream:maintenance"]
    assert color == STREAM_LABELS["stream:maintenance"][0]
    assert desc == STREAM_LABELS["stream:maintenance"][1]


def test_ensure_labels_creates_only_missing():
    gh = _FakeGh(existing=["stream:maintenance", "status:claimed", "bug"])
    created = ensure_labels(gh)
    assert "stream:maintenance" not in created
    assert "status:claimed" not in created
    assert "stream:expansion" in created
    assert "status:in-review" in created
    assert "status:blocked" in created
    assert len(created) == 5  # 3 streams + in-review + blocked


def test_ensure_labels_is_idempotent_second_run_is_noop():
    existing = list(STREAM_LABELS) + list(STATUS_LABELS)
    gh = _FakeGh(existing=existing)
    assert ensure_labels(gh) == []
    assert gh.created == []
