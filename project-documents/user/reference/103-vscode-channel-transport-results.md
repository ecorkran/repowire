---
docType: reference
project: repowire
title: VS Code Channel Transport — What We Tried, What Worked, What Didn't
dateCreated: 20260331
dateUpdated: 20260331
---

# VS Code Channel Transport Results

## Goal

Make [repowire](https://github.com/prassanna-ravishankar/repowire) work with Claude Code in VS Code — two Claude Code sessions in separate VS Code windows seeing each other, holding ONLINE status, and exchanging messages via `ask_peer`.

Repowire is a mesh network for AI coding agents. Its channel transport (`server.ts`) is an MCP server that connects to a daemon via WebSocket and delivers messages to Claude Code using MCP channel notifications. It works with the Claude Code CLI in tmux. We wanted it to work in VS Code too.

## What We Did (Slices 100-103)

### Slice 100: Hook Cleanup and Ghost Eviction Fix
**Problem:** Every VS Code Claude Code session registered two peers (one from channel transport, one from residual hooks), and ghost eviction didn't deduplicate across circles.
**Fix:** `repowire setup` in channel mode removes legacy hooks. Ghost eviction matches on `(display_name, backend)` regardless of circle.

### Slice 101: Rich Pong and Channel Liveness
**Problem:** Channel peers went offline after 30 seconds. The pong response lacked the `circle` field, so `lazy_repair()` couldn't keep channel peers alive.
**Fix:** One-line change — pong now includes `circle: CIRCLE`. Channel peers stay ONLINE indefinitely.

### Slice 102: Peer Identity and Per-Project Config
**Problem:** All channel peers displayed as `"channel"` — no way to tell them apart.
**Fix:** Display name fallback chain: `.repowire.yaml` `display_name` > `CLAUDE_SESSION_ID[:8]` > project folder name. Added `.repowire.yaml` per-project config (`display_name`, `circle`), a `POST /peers/{name}/rename` endpoint, and `set_display_name` MCP tool.

### Slice 103: End-to-End VS Code Verification
Ran the full E2E scenario. Found and fixed three bugs in the setup flow. Discovered the channel notification limitation.

## What Works

| Capability | CLI (with flag) | VS Code |
|-----------|----------------|---------|
| Peer auto-registration from project folder | Yes | Yes |
| Peer liveness (stays ONLINE) | Yes | Yes |
| `list_peers` — see other peers | Yes | Yes |
| `ask_peer` — send a question | Yes | Yes |
| `notify_peer` — fire-and-forget | Yes | Yes |
| `set_display_name` — rename yourself | Yes | Yes |
| `set_description` — update status | Yes | Yes |
| `.repowire.yaml` config | Yes | Yes |
| **Receive incoming messages** | **Yes** | **No** |

Everything except incoming message delivery works identically in VS Code and CLI.

## What Doesn't Work (and Why)

**Incoming message delivery does not work in VS Code.**

When peer A sends a query to peer B, repowire delivers it by having B's MCP server (`server.ts`) emit a `notifications/claude/channel` notification. Claude Code is supposed to inject this into the conversation as a `<channel>` tag, which Claude then processes and responds to via the `reply` tool.

This mechanism is in **research preview** in Claude Code. It requires:
- CLI: `claude --dangerously-load-development-channels server:repowire-channel`
- VS Code extension: **not supported** — no equivalent flag, notifications are silently dropped

Without this, Claude Code loads the MCP server normally (tools work, WebSocket connects, peer registers) but ignores the channel notifications. The query sits in the daemon until the 300-second timeout.

### CLI Works, VS Code Doesn't

We confirmed CLI ↔ CLI message exchange works with the flag. The full round-trip (query → channel notification → Claude processes → reply tool → response delivered) completes successfully.

The VS Code extension uses a different bridge architecture (`bridge_repl_v2`) and does not implement the experimental `claude/channel` capability. There is no configuration or workaround to enable it.

### MCP Sampling Would Fix This (But Doesn't Exist Yet)

The MCP specification includes `sampling/createMessage` — a mechanism for servers to request responses from the model. If Claude Code supported this, repowire's MCP server could prompt Claude to process incoming messages without relying on channel notifications. This feature is [requested](https://github.com/anthropics/claude-code/issues/1785) but not implemented.

## Bugs Fixed During Verification

1. **`repowire setup` failed for VS Code extension users** — gated on `claude` CLI binary, which VS Code users don't have. Fixed to also detect `bun` as a signal.
2. **MCP tools server not registered** — `list_peers`, `ask_peer` etc. need `repowire-mcp` in `~/.claude.json`, which was only registered via `claude mcp add` (requires CLI). Now registered during `install_channel()`.
3. **Ghost eviction tests leaked live daemon state** — tests loaded `~/.repowire/sessions.json` instead of using isolated temp paths.

## Setup for Anyone Trying This

### CLI (full functionality)
```bash
pip install repowire  # or: uv tool install repowire
repowire setup
repowire serve

# In separate terminals, each in a different project directory:
cd ~/projects/frontend
claude --dangerously-load-development-channels server:repowire-channel

cd ~/projects/backend
claude --dangerously-load-development-channels server:repowire-channel
```

Both peers register automatically. Use `list_peers` to see each other, `ask_peer("backend", "What API endpoints do you expose?")` to communicate.

### VS Code (partial — no incoming messages)
```bash
pip install repowire
repowire setup
repowire serve
# Restart VS Code, open project folders, start Claude Code
```

Peers register and stay online. `list_peers`, `ask_peer` (sending), `notify_peer` work. But the target peer cannot receive the message — it times out after 300 seconds.

### Per-project config (optional)
Add `.repowire.yaml` to any project root:
```yaml
display_name: frontend   # defaults to folder name
circle: myteam           # defaults to "default"
```

## What Would Need to Change

For repowire to fully work in VS Code, one of these needs to happen:

1. **Claude Code VS Code extension supports `notifications/claude/channel`** — the simplest path. Channel notifications work in CLI; extending to VS Code would make repowire work immediately.

2. **Claude Code implements MCP `sampling/createMessage`** — the cleanest long-term solution. Lets MCP servers request model responses. Would work on all platforms.

3. **Repowire adds pull-based message delivery** — a `check_messages` tool in `repowire-mcp` that returns pending queries. Claude would need to be prompted to poll. Works today with no Claude Code changes, but worse UX than push delivery.

## Repository

All fixes are on stacked branches in the local repo:
- `100-hook-cleanup-and-ghost-eviction-fix`
- `101-rich-pong-and-channel-liveness`
- `102-peer-identity-and-per-project-config`
- `103-end-to-end-vscode-verification`

Test suite: 241 tests passing. `ruff check` clean.
