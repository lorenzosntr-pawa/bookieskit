"""Release automation: infer the SemVer bump from conventional commits, bump
the two version files + promote the CHANGELOG, then commit and tag.

Pure text/version functions (offline-tested directly) plus a thin orchestrator
(``run_release``) over an injectable ``GitRunner`` — git is the only side
effect. Invoked as ``python -m bookieskit.devtools release`` (and
``release-notes``). The ReleasePlan JSON is the stable contract the
orchestrator (sub-project 5) turns into a release announcement.
"""

import re

_BUMPS = ("major", "minor", "patch")

# Anchored at line-start with NO prefix so it matches the [project]
# `version = "..."` line but NEVER `target-version = "py311"`.
_PYPROJECT_VERSION_RE = re.compile(r'^version = "[^"]*"', re.MULTILINE)
_INIT_VERSION_RE = re.compile(r'^__version__ = "[^"]*"', re.MULTILINE)


def infer_bump(subjects: list[str], current_major: int) -> str | None:
    """Conventional-commit subjects -> "major"|"minor"|"patch"|None.

    Breaking (a "!" before the colon, e.g. "feat!:"/"fix(x)!:", or a
    "BREAKING CHANGE" token) -> "major", EXCEPT while ``current_major == 0``
    where breaking -> "minor" (SemVer 0.x). Else any "feat" -> "minor". Else
    any "fix" -> "patch". Else None (no release-worthy commit). The highest
    precedence found across all subjects wins.
    """
    saw_feat = False
    saw_fix = False
    for subject in subjects:
        head = subject.split("\n", 1)[0]
        type_token = head.split(":", 1)[0]  # e.g. "feat!", "fix(parser)!"
        breaking = type_token.endswith("!") or "BREAKING CHANGE" in subject
        if breaking:
            return "minor" if current_major == 0 else "major"
        base = type_token.split("(", 1)[0]
        if base == "feat":
            saw_feat = True
        elif base == "fix":
            saw_fix = True
    if saw_feat:
        return "minor"
    if saw_fix:
        return "patch"
    return None


def next_version(current: str, bump: str) -> str:
    """ "0.15.1"+"minor" -> "0.16.0"; "+patch" -> "0.15.2"; "+major" ->
    "1.0.0". Resets all lower components."""
    if bump not in _BUMPS:
        raise ValueError(f"unknown bump {bump!r} (expected one of {_BUMPS})")
    major, minor, patch = (int(p) for p in current.split("."))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _replace_one(pattern: re.Pattern[str], text: str, repl: str, what: str) -> str:
    matches = pattern.findall(text)
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one {what} line, found {len(matches)}"
        )
    return pattern.sub(repl, text, count=1)


def bump_pyproject(text: str, new: str) -> str:
    """Replace the anchored ``version = "..."`` line under [project].

    Raises ValueError if the line is absent or ambiguous. Never matches
    ``target-version = "py311"`` (the regex is anchored with no prefix).
    """
    return _replace_one(
        _PYPROJECT_VERSION_RE, text, f'version = "{new}"', "project version"
    )


def bump_init(text: str, new: str) -> str:
    """Replace the anchored ``__version__ = "..."`` line. Raises if absent."""
    return _replace_one(
        _INIT_VERSION_RE, text, f'__version__ = "{new}"', "__version__"
    )
