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


import subprocess  # noqa: E402
from dataclasses import asdict  # noqa: E402
from pathlib import Path  # noqa: E402

from bookieskit.devtools.release import (  # noqa: E402
    GitRunner,
    ReleaseError,
    ReleasePlan,  # noqa: F401
    run_release,
)

_PYPROJECT = (
    "[project]\n"
    'name = "bookieskit"\n'
    'version = "0.15.1"\n'
    "\n"
    "[tool.ruff]\n"
    'target-version = "py311"\n'
)
_INIT = '"""doc"""\n\n__version__ = "0.15.1"\n'
_CL = (
    "# Changelog\n\nIntro.\n\n## [Unreleased]\n\n"
    "### Added\n- New thing.\n\n## [0.15.0] - 2026-05-22\n\n- Old.\n"
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _seed_repo(root: Path, *, subject: str = "feat: add thing") -> None:
    """Create a temp local git repo with the three release files committed."""
    _git(root, "init")
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "T")
    (root / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    (root / "src" / "bookieskit").mkdir(parents=True)
    (root / "src" / "bookieskit" / "__init__.py").write_text(
        _INIT, encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text(_CL, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "chore: seed")
    _git(root, "tag", "-a", "v0.15.1", "-m", "v0.15.1")
    # A release-worthy commit AFTER the tag (so infer_bump sees it).
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", subject)


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def test_run_release_bumps_files_promotes_changelog_commits_and_tags(tmp_path):
    _seed_repo(tmp_path, subject="feat: add thing")
    plan = run_release(root=tmp_path, today="2026-06-23")

    assert plan.current == "0.15.1"
    assert plan.new == "0.16.0"  # feat -> minor
    assert plan.bump == "minor"
    assert plan.tag == "v0.16.0"
    assert plan.pushed is False
    assert "New thing." in plan.changelog_section

    assert 'version = "0.16.0"' in _read(tmp_path, "pyproject.toml")
    assert 'target-version = "py311"' in _read(tmp_path, "pyproject.toml")
    assert '__version__ = "0.16.0"' in _read(
        tmp_path, "src/bookieskit/__init__.py"
    )
    cl = _read(tmp_path, "CHANGELOG.md")
    assert "## [0.16.0] - 2026-06-23" in cl
    assert "## [Unreleased]" in cl

    # A chore(release) commit and a v0.16.0 tag now exist.
    log = subprocess.run(
        ["git", "log", "--format=%s", "-1"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert log == "chore(release): v0.16.0"
    tags = subprocess.run(
        ["git", "tag"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout.split()
    assert "v0.16.0" in tags


def test_run_release_explicit_bump_overrides_inference(tmp_path):
    _seed_repo(tmp_path, subject="fix: small")
    plan = run_release(root=tmp_path, bump="major", today="2026-06-23")
    assert plan.new == "1.0.0"
    assert plan.bump == "major"


def test_run_release_dry_run_mutates_nothing(tmp_path):
    _seed_repo(tmp_path, subject="feat: add thing")
    before_pyproject = _read(tmp_path, "pyproject.toml")
    before_tags = subprocess.run(
        ["git", "tag"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout
    plan = run_release(root=tmp_path, dry_run=True, today="2026-06-23")

    # Plan still reports the computed version + section.
    assert plan.new == "0.16.0"
    assert "New thing." in plan.changelog_section
    assert plan.pushed is False
    # Files and tags untouched.
    assert _read(tmp_path, "pyproject.toml") == before_pyproject
    after_tags = subprocess.run(
        ["git", "tag"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout
    assert after_tags == before_tags


def test_run_release_raises_on_dirty_tree(tmp_path):
    _seed_repo(tmp_path, subject="feat: add thing")
    (tmp_path / "dirty.txt").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "dirty.txt")
    with pytest.raises(ReleaseError):
        run_release(root=tmp_path, today="2026-06-23")


def test_run_release_raises_when_no_bump_inferable(tmp_path):
    _seed_repo(tmp_path, subject="docs: tidy only")
    with pytest.raises(ReleaseError):
        run_release(root=tmp_path, today="2026-06-23")


def test_run_release_raises_on_empty_unreleased(tmp_path):
    _seed_repo(tmp_path, subject="feat: add thing")
    # Wipe the Unreleased body -> promote_changelog must refuse.
    cl = (
        "# Changelog\n\nIntro.\n\n## [Unreleased]\n\n"
        "## [0.15.0] - 2026-05-22\n\n- Old.\n"
    )
    (tmp_path / "CHANGELOG.md").write_text(cl, encoding="utf-8")
    _git(tmp_path, "commit", "-am", "docs: blank unreleased")
    with pytest.raises(ValueError):
        run_release(root=tmp_path, bump="patch", today="2026-06-23")


class _FakeGit:
    """Injected GitRunner fake: clean tree, one feat since tag, records calls."""

    def __init__(self):
        self.pushed_branch = False
        self.pushed_tags: list[str] = []
        self.committed: list[str] = []
        self.tagged: list[str] = []

    def status_porcelain(self):
        return ""

    def last_tag(self):
        return "v0.15.1"

    def subjects_since(self, tag):
        return ["feat: add thing"]

    def add(self, paths):
        pass

    def commit(self, message):
        self.committed.append(message)

    def tag(self, name, message):
        self.tagged.append(name)

    def push_branch(self):
        self.pushed_branch = True

    def push_tag(self, name):
        self.pushed_tags.append(name)


def test_run_release_push_invokes_git_push_via_injected_runner(tmp_path):
    # Files must exist for the on-disk edits; git side effects go to the fake.
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    (tmp_path / "src" / "bookieskit").mkdir(parents=True)
    (tmp_path / "src" / "bookieskit" / "__init__.py").write_text(
        _INIT, encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(_CL, encoding="utf-8")
    fake = _FakeGit()
    plan = run_release(
        root=tmp_path, push=True, today="2026-06-23", git=fake
    )
    assert plan.pushed is True
    assert fake.committed == ["chore(release): v0.16.0"]
    assert fake.tagged == ["v0.16.0"]
    assert fake.pushed_branch is True
    assert fake.pushed_tags == ["v0.16.0"]


def test_run_release_no_push_leaves_pushed_false_via_injected_runner(tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    (tmp_path / "src" / "bookieskit").mkdir(parents=True)
    (tmp_path / "src" / "bookieskit" / "__init__.py").write_text(
        _INIT, encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(_CL, encoding="utf-8")
    fake = _FakeGit()
    plan = run_release(root=tmp_path, today="2026-06-23", git=fake)
    assert plan.pushed is False
    assert fake.pushed_branch is False
    assert fake.pushed_tags == []
    # ReleasePlan serializes cleanly for --json.
    d = asdict(plan)
    assert d["tag"] == "v0.16.0"


def test_gitrunner_status_porcelain_on_temp_repo(tmp_path):
    _seed_repo(tmp_path, subject="feat: add thing")
    git = GitRunner(tmp_path)
    assert git.status_porcelain() == ""  # clean after seed
    (tmp_path / "x.txt").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "x.txt")
    assert git.status_porcelain() != ""  # now dirty
