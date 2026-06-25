# Always-on orchestrator — owner setup

Runs the one-cycle `/orchestrate` loop unattended every 15 minutes on your
in-region machine, so `#tickets` is drained and PRs are built without the
console. Merge still requires your Slack `approve` (the gate never relaxes).

## Prerequisites
1. Slack cockpit wired (`docs/SLACK_SETUP.md`) — the tick reads/posts Slack via the MCP.
2. `.chatops.json` filled with real approver IDs + `#tickets` channel.
3. `gh auth status` is authenticated on this machine.
4. **Branch protection on `main`** (strongly recommended structural backstop):
   GitHub → repo → Settings → Branches → protect `main`: require a PR before
   merging + require CI to pass. Then no unattended process can land on `main`
   without a reviewed, approved PR — defense in depth behind the permission profile.

## Install
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-orchestrator.ps1
```
This registers a Task Scheduler job `BookieskitOrchestrator` firing every 15 min.

## Operate (from Slack `#tickets`)
- Post work requests → filed as `stream:directed` Issues and built.
- `approve <pr>` → merges a green loop PR (allowlist-gated).
- `pause` (optionally `pause <reason>`) → halts autonomous building (a `control:paused` marker Issue opens).
- `resume` → clears the pause; building resumes next tick.

## Observe / troubleshoot
- Logs: `.orchestrator/logs/tick-YYYYMMDD.log` (each tick's outcome; gitignored).
- A tick that fires mid-build logs "busy … skipping" and exits — by design.
- Check the task: `Get-ScheduledTask -TaskName BookieskitOrchestrator`.
- Stop it entirely: `Unregister-ScheduledTask -TaskName BookieskitOrchestrator -Confirm:$false`.

## Limits (current)
- Runs only while this machine is **on** (Task Scheduler `-StartWhenAvailable`
  catches up a missed tick, but a sleeping machine doesn't run). For true 24/7,
  relocate the same tick to an always-on in-region host (future upgrade).
- The tick uses a **constrained permission profile** (`.claude/orchestrator-settings.json`):
  it cannot `gh pr merge` directly or push to `main`; merge flows only through
  the human-gated `chatops approve`.

## Tuning the permission profile (first runs)

`.claude/orchestrator-settings.json` is a **starting point**. On the first real
unattended builds, watch the tick logs: if a build stalls because a legitimate
command (e.g. running tests, `git status`, a tool a subagent needs) isn't in the
`allow` list, add it. Confirm `--settings` is the right flag for your `claude`
version with `claude --help` (it is `--settings <file-or-json>` as of v2.1.x).

**The permission allow-list is convenience, not the safety boundary.** The two
guarantees that actually keep an unattended agent safe are structural and hold
regardless of how the allow-list is tuned:
1. **Branch protection on `main`** (set it up — prerequisite #4 above): no push
   can land on `main` without a reviewed, approved PR.
2. **`gh pr merge` is denied to the agent**, and the only merge route is the
   `chatops approve` CLI, which merges only on a verified human Slack `approve`.

So tune the allow-list freely to unblock builds; never remove the `deny` entries
or the branch protection.
