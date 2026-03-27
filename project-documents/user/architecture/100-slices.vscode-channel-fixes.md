---
docType: slice-plan
parent: project-documents/user/architecture/100-arch.vscode-channel-fixes.md
project: repowire
dateCreated: 20260326
dateUpdated: 20260326
status: not_started
---

# Slice Plan: VS Code Channel Transport Fixes

## Parent Document
[100-arch.vscode-channel-fixes.md](100-arch.vscode-channel-fixes.md) — Targeted fixes to make repowire's existing channel transport work reliably with Claude Code in VS Code.

## Overview
Each slice maps to a clean upstream PR branch. Slices are ordered so each is independently mergeable and leaves the system working. The first two slices fix the critical bugs making repowire unusable; the third adds the usability improvements that make it practical for daily use.

## Foundation Work

1. [x] **(100) Hook Cleanup and Ghost Eviction Fix** — Ensure `repowire setup` in channel mode actively removes stale legacy hooks (SessionStart, SessionEnd, UserPromptSubmit, Notification) from `~/.claude/settings.json`, not just skip installing them. Fix ghost eviction in `peer_registry.py` to match on `(display_name, backend)` regardless of circle, preventing duplicate peers when hook and channel register with different circles. Add/update tests for both the installer cleanup and the eviction logic. Dependencies: none. Risk: Low. Effort: 2/5

   **Value:** Eliminates the "2 peers for every 1 session" bug. Foundation for all other fixes — without this, subsequent slices still produce duplicates.

   **Success Criteria:**
   - `repowire setup` in channel mode removes all legacy hooks except Stop from settings.json
   - Running setup twice produces the same clean result (idempotent)
   - Ghost eviction deduplicates peers with same display_name and backend across different circles
   - All existing tests pass; new tests cover cleanup and cross-circle eviction
   - Tmux hook-only path is unaffected (installing without channel mode still sets all hooks)

## Feature Slices

2. [ ] **(101) Rich Pong and Channel Liveness** — Update `channel/server.ts` to send `{"type": "pong", "circle": CIRCLE}` instead of bare `{"type": "pong"}`. Verify that `lazy_repair()` keeps channel peers ONLINE across multiple repair cycles. Investigate and fix any WebSocket stability issues causing connection drops in VS Code. Add integration-style test confirming channel pong satisfies the repair check. Dependencies: [100]. Risk: Low. Effort: 2/5

   **Value:** Fixes the core usability bug — peers no longer go offline after 30 seconds. Makes `list_peers` and `ask_peer` actually work.

   **Success Criteria:**
   - Channel peer remains ONLINE across at least 3 consecutive lazy_repair cycles (90+ seconds)
   - Pong includes circle data, enabling circle recovery for channel peers
   - Existing lazy_repair tests pass unchanged
   - New test verifies channel-style pong (with circle, without pane_alive) keeps peer ONLINE
   - WebSocket reconnection in channel works reliably (peer recovers ONLINE after brief disconnect)

3. [ ] **(102) Peer Identity and Per-Project Config** — Improve display name derivation: fallback chain of `CLAUDE_SESSION_ID[:8]` → project folder name (from `cwd`). Add `set_display_name` MCP tool (expose existing `update_peer_display_name` daemon method). Implement `.repowire.yaml` per-project config file support with `circle` and `display_name` fields, loaded by `channel/server.ts` at startup. Dependencies: [100, 101]. Risk: Med. Effort: 3/5

   **Value:** Peers have meaningful, distinguishable names. Users can configure circle and identity per-project without environment variables. Makes multi-project workflows practical.

   **Success Criteria:**
   - Without any config, a VS Code channel peer is named after its project folder (not "channel")
   - `.repowire.yaml` in project root with `circle: myteam` and/or `display_name: frontend` is honored by channel transport
   - `set_display_name` MCP tool lets Claude rename itself; change is reflected in `list_peers` for other peers
   - Config file is optional — absence produces sensible defaults
   - Per-project config does not affect global `~/.repowire/config.yaml`
   - Tests cover: display name fallback chain, config file loading, MCP tool rename

## Integration Work

4. [ ] **(103) End-to-End VS Code Verification** — Manual and automated verification of the full VS Code workflow: two Claude Code instances in separate VS Code windows, different projects, see each other via `list_peers`, hold ONLINE status, exchange messages via `ask_peer`, belong to configured circles. Update README or docs with VS Code setup instructions. Dependencies: [100, 101, 102]. Risk: Low. Effort: 2/5

   **Value:** Confirms the complete user story works. Produces documentation for other VS Code users and the upstream contribution.

   **Success Criteria:**
   - Two VS Code Claude Code sessions in different projects are visible via `list_peers`
   - Both maintain ONLINE status for extended period (>5 minutes)
   - `ask_peer` successfully delivers a query and receives a response
   - Peers show meaningful names (project folder or configured name)
   - Circle isolation works (peers in different circles don't see each other)
   - Setup instructions are documented

## Notes

- Each slice (100-102) maps to an upstream PR branch. PR sequence: 100 first (prerequisite), then 101 and 102 can be reviewed in parallel, 103 is final verification.
- All changes must preserve the tmux hook path — run full test suite after each slice.
- The reference document (`user/reference/repowire-vscode-context.md`) proposed a PeerTransport abstraction. After investigation, this is unnecessary — the daemon already doesn't care how peers connect. The channel transport is the right architecture; it just has bugs.
- Consider opening a GitHub Issue on the upstream repo describing the VS Code use case before submitting PRs.

## Future Work

1. [ ] **Circle Management UI** — Dashboard and CLI commands for managing circles, moving peers between circles. Effort: 2/5
2. [ ] **Auto-Circle from Git** — Derive circle from git remote or branch name for automatic project grouping. Effort: 2/5
3. [ ] **VS Code Extension** — Native VS Code extension providing UI for peer list, messaging, circle management instead of relying solely on MCP tools. Effort: 4/5
