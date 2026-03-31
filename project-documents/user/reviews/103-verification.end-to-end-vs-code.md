---
docType: review
layer: project
reviewType: verification
slice: end-to-end-vs-code-verification
project: repowire
verdict: PARTIAL_PASS
sourceDocument: project-documents/user/tasks/103-tasks.end-to-end-vs-code-verification.md
dateCreated: 20260331
dateUpdated: 20260331
status: complete
---

# Verification Report: Slice 103 — End-to-End VS Code

**Verdict:** PARTIAL PASS
**Environment:** Ubuntu Linux, Claude Code VS Code extension + CLI, bun 1.x, Python 3.12

## Results by Success Criterion

| SC | Scenario | Result | Notes |
|----|----------|--------|-------|
| SC1 | Peer naming defaults to folder name | PASS | `process.cwd()` returns project folder when VS Code opens the correct directory |
| SC2 | `.repowire.yaml` config loading | PASS | Tested informally — `display_name` and `circle` overrides worked correctly |
| SC3 | Liveness — ONLINE >5 min | PASS | Both peers stayed ONLINE across multiple lazy_repair cycles |
| SC4 | Cross-visibility via `list_peers` | PASS | Both peers visible in `list_peers` from either side |
| SC5 | `ask_peer` round-trip | PARTIAL | **Fails in VS Code.** Works in CLI ↔ CLI with `--dangerously-load-development-channels` flag |
| SC6 | Circle isolation | NOT TESTED | Requires SC5 setup; deferred |
| SC7 | `set_display_name` rename | NOT TESTED | Tool works (HTTP endpoint confirmed in slice 102 tests); E2E deferred |

## Bugs Found and Fixed During Verification

### 1. `repowire setup` fails without `claude` CLI (VS Code extension users)

**Root cause:** `setup` command gated on `shutil.which("claude")` — VS Code extension users don't have the CLI binary.
**Fix:** Also check `shutil.which("bun")` as a signal that channel transport should be attempted. Guard `claude mcp add/remove` calls behind CLI availability check.
**Commits:** `072569e`, `c868741`

### 2. `repowire-mcp` not registered in `~/.claude.json`

**Root cause:** `install_channel()` only registered `repowire-channel` (the WebSocket transport). The MCP tools server (`list_peers`, `ask_peer`, etc.) was registered via `claude mcp add` — which was skipped for non-CLI users.
**Fix:** `install_channel()` now registers both `repowire-channel` and `repowire-mcp` in `~/.claude.json` using `sys.argv[0]` for the repowire binary path.
**Commit:** `30701b9`

### 3. Ghost eviction tests leak live daemon state

**Root cause:** `_make_manager()` in `test_ghost_eviction.py` created a `PeerRegistry` without a `persistence_path`, defaulting to `~/.repowire/sessions.json`. When the daemon is running with real peers, the test loads those peers.
**Fix:** Pass `tmp_path` to `PeerRegistry` for test isolation.
**Commit:** `30701b9`

## Key Architecture Finding: Channel Push Delivery

### The Problem

The channel transport (`server.ts`) delivers incoming messages to Claude via `notifications/claude/channel` — an experimental MCP notification. This notification is processed differently depending on the runtime:

- **CLI with `--dangerously-load-development-channels server:repowire-channel`**: Works. Messages appear as `<channel>` tags in Claude's conversation.
- **CLI without the flag**: Silently dropped. The MCP server loads normally (tools work) but channel notifications are ignored.
- **VS Code extension**: Silently dropped. No equivalent flag exists.

### Why It Happens

The `claude/channel` capability is in **research preview**. Non-allowlisted MCP servers must be loaded with `--dangerously-load-development-channels` for their channel notifications to be processed. The VS Code extension does not support this flag or the channel notification mechanism.

### Impact

| Capability | CLI (with flag) | CLI (no flag) | VS Code |
|-----------|----------------|---------------|---------|
| Peer registration & liveness | Yes | Yes | Yes |
| `list_peers`, `whoami` | Yes | Yes | Yes |
| `ask_peer` (sending) | Yes | Yes | Yes |
| `notify_peer` (sending) | Yes | Yes | Yes |
| `set_display_name` | Yes | Yes | Yes |
| **Receiving messages (push)** | **Yes** | **No** | **No** |
| `reply` to incoming queries | Yes | N/A | N/A |

### Recommended Fix

Add a pull-based `check_messages` tool to `repowire-mcp` that returns pending queries for the current peer. This works on all platforms without requiring channel notification support.
