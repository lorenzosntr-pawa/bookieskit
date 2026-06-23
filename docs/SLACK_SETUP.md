# Slack cockpit — owner setup

The agent company posts a live feed to Slack via the korotovsky
`slack-mcp-server` MCP. This is **best-effort**: until these steps are done, the
loop, canary, and release all run normally — Slack simply stays quiet. Complete
this once to light up the cockpit.

The one thing you set up is: a Slack token + the `slack-mcp-server` MCP
registered in Claude Code with **posting enabled**. The agent never talks to
Slack directly — it formats text (`notify` / `sync-canary --json`) and calls
the MCP's `conversations_add_message` tool to post. Run it from the same
in-region session as `/orchestrate`.

## 1. Create the Slack app + bot token (recommended path)

Use a **Bot token** (`xoxb-`) so the agent posts under its own identity
("BookiesKit Agent") and you control exactly which channels it can touch.
(Alternatives the server also supports: a User token `xoxp-` posts as *you*; the
browser `xoxc`/`xoxd` session tokens work too but expire with your browser
session — avoid them for an always-on cockpit. Priority if several are set:
`xoxp` > `xoxb` > `xoxc/xoxd`.)

1. Go to <https://api.slack.com/apps> → **Create New App → From manifest**,
   choose your workspace, and paste:

   ```json
   {
     "display_information": { "name": "BookiesKit Agent" },
     "features": { "bot_user": { "display_name": "BookiesKit Agent", "always_online": true } },
     "oauth_config": {
       "scopes": {
         "bot": [
           "chat:write",
           "channels:history", "channels:read",
           "groups:history", "groups:read",
           "users:read"
         ]
       }
     },
     "settings": { "org_deploy_enabled": false, "socket_mode_enabled": false, "token_rotation_enabled": false }
   }
   ```

   `chat:write` is posting (covers this slice); the `*:history`/`*:read` scopes
   let the next (ChatOps) slice read `#tickets` — set once, no rework.
2. **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-…`).
   Keep it secret; **never commit it.**

## 2. Create the channels and invite the bot

Create `#agent-activity`, `#canary-alerts`, `#releases` (and `#tickets` now if
you want — free to pre-make for the ChatOps slice). Then in **each** channel run
`/invite @BookiesKit Agent`. A bot only sees/posts to channels it's invited to.

## 3. Register the MCP in Claude Code (in-region machine)

One command from the repo dir (PowerShell):

```powershell
claude mcp add slack --scope user `
  -e SLACK_MCP_XOXB_TOKEN=xoxb-YOUR-TOKEN `
  -e SLACK_MCP_ADD_MESSAGE_TOOL=true `
  -- npx -y slack-mcp-server@latest --transport stdio
```

- `--scope user` → available in every Claude Code session on this machine, and
  the token stays out of the repo.
- **`SLACK_MCP_ADD_MESSAGE_TOOL=true` is the critical switch** — posting is OFF
  by default; without it the agent can format messages but cannot post them.
  (Tighten later by passing comma-separated channel IDs instead of `true` to
  restrict posting to just these channels.)
- If `npx` misbehaves on Windows, use Docker instead: command `docker`, args
  `run -i --rm -e SLACK_MCP_XOXB_TOKEN ghcr.io/korotovsky/slack-mcp-server --transport stdio`.

Confirm: `claude mcp list` shows `slack`, and the `conversations_add_message`
tool is available in a session.

## 4. Verify (in-region)

Live-bookmaker work runs in-region (the African APIs geo-block US/cloud IPs),
so verify from an in-region session:

1. Run one `/orchestrate` cycle on a queue with at least one open item. Confirm
   a `cycle-started` message lands in `#agent-activity`, and a `cycle-pr`
   message when the PR opens.
2. Run `python -m bookieskit.orchestration sync-canary --sport soccer --json`.
   If it reports drift, confirm the digest lands in `#canary-alerts`. (No drift
   → no post, by design.)

If nothing posts **and no error appears**, the `conversations_add_message` tool
is not enabled — re-check step 3 (`SLACK_MCP_ADD_MESSAGE_TOOL=true`). If you get
an **auth/permission error**, the bot wasn't invited to that channel (step 2).

## Channels at a glance

| Channel | Posted by | When |
|---|---|---|
| `#agent-activity` | orchestrate skill | each cycle: claimed → PR opened → blocked |
| `#canary-alerts` | orchestrate/maintenance | a `sync-canary` run reports drift |
| `#releases` | the agent that cut the release | after `release --push`, manually via `notify release` |

Posting is best-effort and agent-driven, not automatic: the `#releases` note is
the agent running `notify release ...` and posting after a release — `devtools
release` itself does not post (it cannot import the `orchestration` notifier).

## Next slice — ChatOps

A later sub-project adds a `#tickets` channel where you (or a teammate) type a
request — "add bookmaker X" — and the loop files it as a `stream:directed`
issue and builds it, plus `approve`/`status`/`pause` commands. This setup is
the foundation for it.
