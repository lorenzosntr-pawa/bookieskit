# Slack cockpit — owner setup

The agent company posts a live feed to Slack via the korotovsky
`slack-mcp-server` MCP. This is **best-effort**: until these steps are done, the
loop, canary, and release all run normally — Slack simply stays quiet. Complete
this once to light up the cockpit.

## 1. Workspace + channels

1. Use an existing Slack workspace or create one; invite the people who'll use
   it (owner + teammates).
2. Create three channels:
   - `#agent-activity` — cycle progress (claimed → PR opened → blocked).
   - `#canary-alerts` — canary drift digests.
   - `#releases` — release announcements.

## 2. Slack token

Obtain a token for the korotovsky MCP per its README
(<https://github.com/korotovsky/slack-mcp-server>). A user or bot token is
enough; no workspace-admin rights are required. Add the bot/user to the three
channels above so it can post.

## 3. Register the MCP in Claude Code

Register `slack-mcp-server` as an MCP server (stdio) in Claude Code's MCP
settings. **Crucially, enable the message-post tool** — it is OFF by default:
set the `SLACK_MCP_ADD_MESSAGE_TOOL` environment variable (per the server's
README) so the `post_message`/`conversations_add_message` tool is exposed.
Without it, the agent can format messages but cannot post them.

## 4. Verify (in-region)

Live-bookmaker work runs in-region (the African APIs geo-block US/cloud IPs),
so verify from an in-region session:

1. Run one `/orchestrate` cycle on a queue with at least one open item. Confirm
   a `cycle-started` message lands in `#agent-activity`, and a `cycle-pr`
   message when the PR opens.
2. Run `python -m bookieskit.orchestration sync-canary --sport soccer --json`.
   If it reports drift, confirm the digest lands in `#canary-alerts`. (No drift
   → no post, by design.)

If nothing posts and no error appears, the `post_message` tool is not enabled —
re-check step 3 (`SLACK_MCP_ADD_MESSAGE_TOOL`).

## Channels at a glance

| Channel | Posted by | When |
|---|---|---|
| `#agent-activity` | orchestrate skill | each cycle: claimed → PR opened → blocked |
| `#canary-alerts` | orchestrate/maintenance | a `sync-canary` run reports drift |
| `#releases` | release flow | a release is cut |

## Next slice — ChatOps

A later sub-project adds a `#tickets` channel where you (or a teammate) type a
request — "add bookmaker X" — and the loop files it as a `stream:directed`
issue and builds it, plus `approve`/`status`/`pause` commands. This setup is
the foundation for it.
