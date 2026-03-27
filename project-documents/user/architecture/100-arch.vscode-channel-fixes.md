---
docType: architecture
layer: project
project: repowire
archIndex: 100
component: vscode-channel-fixes
relatedSlices: []
riskLevel: low
dateCreated: 20260326
dateUpdated: 20260326
status: not_started
---

# Architecture: VS Code Channel Transport Fixes

## Overview

Repowire is a mesh networking tool that lets AI coding agent sessions communicate in real time via a central WebSocket daemon. It already has two transports: a legacy tmux-based hook transport and a newer MCP channel transport (`channel/server.ts`). The channel transport is architecturally correct for VS Code extension use but ships with several bugs that make it unusable outside tmux environments.

This component addresses the specific bugs preventing repowire from working with Claude Code in the VS Code extension. The goal is targeted fixes to the existing channel transport — not a new abstraction layer.

**Scope:** Fix channel transport bugs, improve peer identity/naming for non-tmux environments, add per-project configuration.

**Motivation:** The channel transport architecture (MCP stdio → WebSocket → daemon) is the right design. The bugs are shallow — circle mismatch in ghost eviction, bare pong responses, fragile display name derivation, missing naming tools. Fixing these makes repowire immediately useful for VS Code users.

## Design Goals

- **Fix duplicate peer registration** when both legacy hooks and channel transport register for the same session, caused by circle mismatch in ghost eviction
- **Fix peer liveness** so channel peers maintain ONLINE status across lazy_repair cycles by sending rich pong responses
- **Enable meaningful peer identity** so VS Code peers have stable, human-recognizable names and can rename themselves
- **Support per-project configuration** via `.repowire.yaml` in project roots for circle and display name

## Architectural Principles

- **Do not break the tmux path.** All existing hook-based transport behavior must be preserved. All 222 tests must pass.
- **Minimal, targeted changes.** Each fix is small and obviously correct. No new abstractions unless required.
- **Upstream-contribution quality.** Each slice maps to a clean PR that the repo author can review independently.
- **Channel transport is the primary path.** Fixes should make channel the reliable default, not a second-class option.

## Current State

The channel transport (`channel/server.ts`) connects to the daemon via WebSocket, delivers messages as MCP channel notifications, and receives responses via a `reply` tool. This is architecturally sound. However:

1. **Duplicate registration:** Hook installer in channel mode installs only the Stop hook, but stale SessionStart hooks from prior installs persist. Even when clean, the HTTP `POST /peers` from hooks and the WebSocket `connect` from channel can create two peers — ghost eviction fails because hooks use `circle = tmux_session_name` while channel uses `circle = "default"`.

2. **Peers go offline in <30s:** `lazy_repair()` pings all ONLINE/BUSY peers every 30s. Channel sends a bare `{"type": "pong"}` missing circle data. More critically, if the WebSocket connection has any instability, the 5-second ping timeout causes OFFLINE marking. OpenCode peers skip pinging entirely (hardcoded exemption) but Claude Code channel peers do not.

3. **No meaningful identity:** Display name derives from `CLAUDE_SESSION_ID[:8]`, falling back to generic `"channel"` if the env var is absent. No MCP tool exists to rename a peer. No per-project config for circle or name.

4. **Circle derivation broken for VS Code:** Everything lands in `"default"` unless the user manually exports `REPOWIRE_CIRCLE`. No `.repowire.yaml` per-project config exists (mentioned in design docs but unimplemented).

## Envisioned State

Multiple Claude Code instances running in VS Code, across different projects, are visible to each other via `list_peers`, hold ONLINE status while active, have meaningful names (derived from project directory or set explicitly), belong to logical circles (configured per-project), and can exchange messages via `ask_peer` — all without tmux.

## Technical Considerations

- **Hook cleanup must be idempotent** — `repowire setup` in channel mode should actively remove stale legacy hooks, not just skip installing them. Users may have run setup multiple times.
- **Ghost eviction needs to match on (display_name, backend) regardless of circle** — the current `same circle OR offline` condition misses the cross-circle duplicate case.
- **Rich pong is trivial but load-bearing** — adding `circle` to channel's pong response fixes both liveness and circle recovery in one change.
- **Display name fallback chain** — `CLAUDE_SESSION_ID[:8]` → project folder name → workspace name. Must be deterministic and stable across session resumes.
- **Per-project config must not break global config** — `.repowire.yaml` in project root overrides defaults; `~/.repowire/config.yaml` remains authoritative for daemon settings.
- **`set_display_name` MCP tool** — `update_peer_display_name()` already exists in the daemon; just needs MCP exposure.

## Anticipated Slices

- **Hook cleanup and ghost eviction fix** — Ensure channel mode removes stale hooks; fix ghost eviction to deduplicate across circles. Foundation work.
- **Rich pong and liveness fix** — Channel sends circle in pong; verify lazy_repair keeps channel peers ONLINE. Core fix.
- **Peer identity and naming** — Display name fallback chain, `set_display_name` MCP tool, per-project `.repowire.yaml` config. User-facing improvement.
- **Integration testing** — End-to-end verification of VS Code channel transport with multiple peers.

## Related Work

- Existing channel transport: `repowire/channel/server.ts`
- Daemon peer registry: `repowire/daemon/peer_registry.py`
- Hook installer: `repowire/installers/claude_code.py`
- MCP server tools: `repowire/mcp/server.py`
- Reference analysis: `project-documents/user/reference/repowire-vscode-context.md`
