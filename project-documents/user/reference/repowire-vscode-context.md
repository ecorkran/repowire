# repowire — VS Code Extension Support: Project Context

## What You're Working On

You are extending [repowire](https://github.com/prassanna-ravishankar/repowire), a mesh networking tool that lets AI coding agent sessions communicate with each other in real time. The original repo works well for Claude Code running in tmux terminals. The goal of this work is to make it work with **Claude Code running inside the VS Code extension** — without requiring tmux at all.

This work is intended to eventually be contributed back upstream as a clean PR sequence.

---

## Repo Overview

repowire is a Python project (managed with `uv`). Key components:

| Component | Purpose |
|---|---|
| **Daemon** | Central WebSocket hub at `127.0.0.1:8377`. Routes messages between peers. Installed as a system service (launchd/systemd). |
| **Hooks** | Shell scripts registered in `~/.claude/settings.json`. Fire on Claude Code lifecycle events: `SessionStart`, `UserPromptSubmit`, `Stop`, `SessionEnd`, `Notification`. |
| **websocket_hook.py** | Background process spawned at `SessionStart`. Maintains the WebSocket connection to the daemon on behalf of a peer. Currently uses tmux pane existence as its liveness signal. |
| **MCP Server** | Exposes tools to Claude: `ask_peer`, `list_peers`, `notify_peer`, `broadcast`, `whoami`, `set_description`, `spawn_peer`, `kill_peer`. |
| **Config** | `~/.repowire/config.yaml`. Peers auto-register via WebSocket on session start. |

Directory layout (top-level of the repo):
```
repowire/          # main Python package
tests/
web/               # dashboard frontend
charts/            # helm charts
deploy/
.github/workflows/
```

---

## The Bugs We're Fixing

When Claude runs in the **VS Code extension** (not a tmux pane), three things break:

### 1. Duplicate peer registration
Each Claude session registers a peer using the first 8 chars of `session_id`. In VS Code, hooks may fire in ways that cause double registration. The daemon appends rather than upserts, producing two entries for one instance.

**Fix:** Make daemon registration idempotent — upsert by `session_id`, never append.

### 2. Peers won't hold ONLINE status
`websocket_hook.py` maintains liveness by checking whether the tmux pane it was spawned from still exists (~30s polling loop). In VS Code, there is no tmux pane, so liveness fails immediately and the peer goes offline or gets pruned.

**Fix:** Replace the tmux pane existence check with WebSocket connection presence as the liveness signal. If the WebSocket is connected to the daemon, the peer is alive. This is strictly more correct anyway.

### 3. Message delivery requires tmux
When the daemon delivers an inbound message to a Claude Code peer (e.g., an `ask_peer` query), it currently uses `tmux send-keys` to inject text into the pane. No tmux = no delivery.

**Fix:** For VS Code peers, write the inbound message to a watched file or named pipe (e.g., `~/.repowire/inbox/{peer_id}.txt`), and have a background watcher or hook trigger the injection into Claude's context. The exact mechanism needs investigation — see "First Tasks" below.

---

## The Architecture We're Building

### PeerTransport abstraction

Introduce an abstract base class:

```python
class PeerTransport(ABC):
    async def deliver_message(self, message: str) -> None: ...
    async def is_alive(self) -> bool: ...
    def peer_id(self) -> str: ...  # stable across session resumes
```

Two implementations:
- `TmuxTransport` — wraps existing behavior, no changes to current functionality
- `VSCodeTransport` — new, headless, file/pipe-based delivery, WS-based liveness

This abstraction is the contribution-worthy piece. It makes the project extensible to other IDEs (Cursor, Zed, etc.) without touching core routing logic.

### Circles as logical tags

Currently "circles" (the grouping/isolation mechanism for peers) are derived from tmux session names. For VS Code peers, circles should just be a string tag declared in the hook environment or in a `.repowire.yaml` in the project root. No tmux session name required.

---

## Planned PR Sequence (contribution strategy)

| PR | Scope | Notes |
|---|---|---|
| **PR 1** | Idempotent registration | Daemon upserts peers by session_id. Tiny, obviously correct, fixes duplicate bug. |
| **PR 2** | PeerTransport abstraction | Refactor existing tmux code behind the interface. All tests should still pass. No behavior change. |
| **PR 3** | VSCodeTransport + headless liveness | New transport, WS-based liveness, VS Code-specific message delivery. |
| **PR 4** | Circles as logical tags | Decouple circle identity from tmux session naming. |

Work in this order. Each PR should be reviewable and mergeable independently.

---

## First Tasks When You Open the Repo

Before writing any new code, read and annotate the following files:

1. **`websocket_hook.py`** (or wherever the background liveness process is defined)
   - How does it detect that the tmux pane is alive?
   - How does it deliver inbound messages to Claude?
   - What's the reconnection logic?

2. **The hooks directory** (scripts registered in `~/.claude/settings.json`)
   - How is `session_id` extracted and used?
   - What data gets posted to the daemon at `SessionStart`?
   - Is there a race condition that could cause double-registration?

3. **The daemon's peer registration handler**
   - Is it an upsert or an append?
   - What's the peer state machine? (`OFFLINE → ONLINE ↔ BUSY`)

4. **The peer config structure in `~/.repowire/config.yaml`**
   - What fields does a peer record have?
   - Which fields are tmux-specific vs. generic?

Document your findings as inline comments as you go. This will be the map for the transport abstraction.

---

## Key Design Decisions to Validate

- **Stable peer identity in VS Code:** Confirm that `session_id` from Claude Code hooks is stable across session resumes in the VS Code extension. If not, fall back to writing a UUID to `.repowire-peer-id` in the project root at first `SessionStart`.

- **Inbound message injection:** The biggest open question. Claude Code in VS Code may support programmatic prompt injection, stdin piping, or a file-watch mechanism. Research whether `claude --resume <session_id>` or any `--print` / stdin flag exists that `VSCodeTransport` can exploit. The fallback is a file in `~/.repowire/inbox/` that a background hook monitors and re-injects.

- **WS-as-liveness:** The WebSocket connection to the daemon is the cleanest liveness signal. When the connection drops, mark the peer offline. When it reconnects, mark online. This removes the need for any polling loop.

---

## Constraints

- **Do not break the tmux path.** Existing `TmuxTransport` behavior must be preserved exactly. All current tests must continue to pass.
- **Keep tmux optional, not required.** The daemon, MCP server, and hooks should all work without tmux present.
- **Prefer clean abstractions over clever hacks.** This is going upstream — the author needs to be able to read and maintain it.
- **Python 3.10+, managed with `uv`.**

---

## Upstream Contribution Notes

- Repo: https://github.com/prassanna-ravishankar/repowire
- Author has indicated openness to contribution (active development, relay feature just shipped)
- Open a GitHub Issue first describing the VS Code extension use case before opening PRs — gives the author context and avoids wasted work if he has opinions on the approach
- Each PR should reference the issue

---

## What Success Looks Like

Multiple Claude Code instances running in VS Code extension windows, across different project directories, are visible to each other via `list_peers`, hold ONLINE status while active, transition to BUSY during task execution, and can exchange messages via `ask_peer` — all without tmux running anywhere.
