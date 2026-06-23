"""GhRunner: a thin injectable wrapper over the ``gh`` CLI calls the queue
needs. Mirrors ``devtools/release.py``'s ``GitRunner``: every method runs ``gh``
with ``check=True`` so a non-zero exit raises ``CalledProcessError`` (its stderr
propagates). Tests inject a fake instead of touching a real ``gh`` process.
"""

import json
import re
import subprocess

_ISSUE_NUMBER_RE = re.compile(r"/(\d+)\s*$")


class GhRunner:
    """Injectable wrapper over the ``gh`` subprocess calls the queue needs."""

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["gh", *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def list_issues(
        self, *, labels: tuple[str, ...] = (), state: str = "open"
    ) -> list[dict]:
        args = [
            "issue",
            "list",
            "--json",
            "number,title,body,labels,state",
            "--state",
            state,
        ]
        for label in labels:
            args += ["--label", label]
        return json.loads(self._run(*args))

    def create_issue(
        self, *, title: str, body: str, labels: tuple[str, ...]
    ) -> int:
        args = ["issue", "create", "--title", title, "--body", body]
        for label in labels:
            args += ["--label", label]
        out = self._run(*args).strip()
        match = _ISSUE_NUMBER_RE.search(out)
        if match is None:
            raise ValueError(f"could not parse issue number from {out!r}")
        return int(match.group(1))

    def comment_issue(self, number: int, body: str) -> None:
        self._run("issue", "comment", str(number), "--body", body)

    def edit_issue(
        self,
        number: int,
        *,
        body: str | None = None,
        add_labels: tuple[str, ...] = (),
        remove_labels: tuple[str, ...] = (),
    ) -> None:
        args = ["issue", "edit", str(number)]
        if body is not None:
            args += ["--body", body]
        for label in add_labels:
            args += ["--add-label", label]
        for label in remove_labels:
            args += ["--remove-label", label]
        if len(args) == 3:  # nothing to change beyond the number
            return
        self._run(*args)

    def close_issue(self, number: int, *, comment: str | None = None) -> None:
        args = ["issue", "close", str(number)]
        if comment is not None:
            args += ["--comment", comment]
        self._run(*args)

    def list_labels(self) -> list[str]:
        out = self._run("label", "list", "--json", "name")
        return [d["name"] for d in json.loads(out)]

    def create_label(
        self, name: str, *, color: str, description: str
    ) -> None:
        self._run(
            "label",
            "create",
            name,
            "--color",
            color,
            "--description",
            description,
        )
