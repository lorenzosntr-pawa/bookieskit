import pytest

from bookieskit.devtools.release import (
    bump_init,
    bump_pyproject,
    infer_bump,
    next_version,
)


def test_infer_bump_feat_is_minor():
    assert infer_bump(["feat: add market", "docs: tidy"], 0) == "minor"


def test_infer_bump_fix_is_patch():
    assert infer_bump(["fix: guard empty id", "chore: bump"], 1) == "patch"


def test_infer_bump_breaking_bang_is_major_when_major_ge_1():
    assert infer_bump(["feat!: drop old api"], 1) == "major"
    assert infer_bump(["fix(parser)!: rename id"], 2) == "major"


def test_infer_bump_breaking_token_is_major_when_major_ge_1():
    assert infer_bump(["feat: x\n\nBREAKING CHANGE: y"], 1) == "major"


def test_infer_bump_breaking_is_minor_while_major_zero():
    # SemVer 0.x: breaking -> minor (not major) while major == 0.
    assert infer_bump(["feat!: drop old api"], 0) == "minor"
    assert infer_bump(["fix!: rename"], 0) == "minor"


def test_infer_bump_highest_precedence_wins():
    assert infer_bump(["fix: a", "feat: b"], 1) == "minor"
    assert infer_bump(["feat: a", "fix!: b"], 2) == "major"


def test_infer_bump_none_when_no_release_worthy_commit():
    assert infer_bump(["docs: a", "chore: b", "ci: c"], 1) is None
    assert infer_bump([], 1) is None


def test_next_version_patch_minor_major_reset_lower():
    assert next_version("0.15.1", "patch") == "0.15.2"
    assert next_version("0.15.1", "minor") == "0.16.0"
    assert next_version("0.15.1", "major") == "1.0.0"
    assert next_version("1.2.3", "minor") == "1.3.0"


def test_next_version_rejects_bad_bump():
    with pytest.raises(ValueError):
        next_version("0.15.1", "nope")


def test_bump_pyproject_replaces_only_the_project_version_line():
    text = (
        '[project]\n'
        'name = "bookieskit"\n'
        'version = "0.15.1"\n'
        '\n'
        '[tool.ruff]\n'
        'target-version = "py311"\n'
    )
    out = bump_pyproject(text, "0.16.0")
    assert 'version = "0.16.0"' in out
    # target-version is NEVER touched.
    assert 'target-version = "py311"' in out
    assert 'version = "0.15.1"' not in out


def test_bump_pyproject_raises_when_absent():
    with pytest.raises(ValueError):
        bump_pyproject('[project]\nname = "x"\n', "0.16.0")


def test_bump_init_replaces_dunder_version():
    text = '"""doc"""\n\n__version__ = "0.15.1"\n__all__ = []\n'
    out = bump_init(text, "0.16.0")
    assert '__version__ = "0.16.0"' in out
    assert '__version__ = "0.15.1"' not in out


def test_bump_init_raises_when_absent():
    with pytest.raises(ValueError):
        bump_init('"""doc"""\n', "0.16.0")


from bookieskit.devtools.release import (  # noqa: E402
    extract_section,
    promote_changelog,
)

_CHANGELOG = (
    "# Changelog\n"
    "\n"
    "Intro paragraph.\n"
    "\n"
    "## [Unreleased]\n"
    "\n"
    "### Added\n"
    "- New market foo.\n"
    "\n"
    "## [0.15.0] - 2026-05-22\n"
    "\n"
    "### Added\n"
    "- Old stuff.\n"
)


def test_promote_changelog_renames_unreleased_and_inserts_fresh():
    out = promote_changelog(_CHANGELOG, "0.16.0", "2026-06-23")
    assert "## [0.16.0] - 2026-06-23" in out
    # A fresh empty Unreleased sits above the promoted section.
    assert "## [Unreleased]" in out
    assert out.index("## [Unreleased]") < out.index("## [0.16.0] - 2026-06-23")
    # The promoted section keeps its curated body.
    assert "- New market foo." in out
    # The old 0.15.0 section is untouched and still below.
    assert out.index("## [0.16.0] - 2026-06-23") < out.index(
        "## [0.15.0] - 2026-05-22"
    )


def test_promote_changelog_raises_when_no_unreleased():
    text = "# Changelog\n\nIntro.\n\n## [0.15.0] - 2026-05-22\n\n- x.\n"
    with pytest.raises(ValueError):
        promote_changelog(text, "0.16.0", "2026-06-23")


def test_promote_changelog_raises_when_unreleased_empty():
    text = (
        "# Changelog\n\nIntro.\n\n## [Unreleased]\n\n"
        "## [0.15.0] - 2026-05-22\n\n- x.\n"
    )
    with pytest.raises(ValueError):
        promote_changelog(text, "0.16.0", "2026-06-23")


def test_extract_section_returns_stripped_body():
    body = extract_section(_CHANGELOG, "0.15.0")
    assert body == "### Added\n- Old stuff."


def test_extract_section_middle_section_stops_at_next_header():
    out = promote_changelog(_CHANGELOG, "0.16.0", "2026-06-23")
    body = extract_section(out, "0.16.0")
    assert body == "### Added\n- New market foo."


def test_extract_section_raises_when_absent():
    with pytest.raises(ValueError):
        extract_section(_CHANGELOG, "9.9.9")
