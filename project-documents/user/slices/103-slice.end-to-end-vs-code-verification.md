---
docType: slice-design
slice: end-to-end-vs-code-verification
project: repowire
parent: project-documents/user/architecture/100-slices.vscode-channel-fixes.md
dependencies: [100, 101, 102]
interfaces: []
dateCreated: 20260331
dateUpdated: 20260331
status: complete
---

# Slice 103: End-to-End VS Code Verification

## Overview

Slices 100-102 fixed all identified bugs in the channel transport: ghost eviction, rich pong liveness, and peer identity. Slice 103 confirms these fixes work together in the actual VS Code + Claude Code environment, and updates the README to document the VS Code workflow for users.

This slice splits into two distinct tracks:

1. **Code changes (automated):** README updates — VS Code setup section, `.repowire.yaml` docs, `set_display_name` in tools table. These can be written and committed before any manual testing.

2. **Manual verification (human-in-the-loop):** Two live VS Code sessions against a running daemon. Claude cannot run these — they require real Claude Code processes in real VS Code windows. The verification checklist is defined here; results are recorded in a verification report.

No new daemon code. No new routes. No Python test additions unless a bug is discovered during manual testing.

## Technical Decisions

### 1. README: VS Code Setup Section

The current README explains `repowire setup` and mentions channel transport, but gives no VS Code-specific guidance. VS Code users need to know:

- They don't use `repowire peer new` (that spawns tmux sessions)
- Their Claude Code process registers itself automatically via the MCP channel
- They can use `.repowire.yaml` in their project root to set `display_name` and `circle`
- The peer name defaults to the project folder name — no configuration needed for the common case

**Placement:** A new collapsible `<details>` block in the "Claude Code Transport" section, titled "VS Code setup." This keeps the main README concise while making the information discoverable.

**Content of the VS Code section:**
```markdown
<details>
<summary><strong>VS Code setup</strong></summary>

Claude Code in VS Code registers automatically via the channel transport. No tmux or `repowire peer new` required.

1. Start the daemon: `repowire serve`
2. Run `repowire setup` once — this installs the repowire MCP server in `~/.claude.json`
3. Open a project folder in VS Code and start Claude Code
4. The peer registers with the project folder name as its display name

To configure circle or display name per-project, add `.repowire.yaml` to your project root:

```yaml
display_name: frontend   # defaults to project folder name
circle: myteam           # defaults to "default"
```

Multiple VS Code windows register as separate peers. Use `list_peers` in any session to see all connected peers.

</details>
```

### 2. README: `set_display_name` in MCP Tools Table

Slice 102 added `set_display_name` but the README tools table was not updated. Add it:

| `set_display_name` | Mutation | Rename yourself in the mesh — visible to other peers immediately |

### 3. Manual Verification Checklist

The verification runs two Claude Code sessions in separate VS Code windows against the same local daemon. The checklist is ordered from simplest to most complex — stop and debug on first failure.

**Setup:**
- Machine with VS Code, Claude Code v2.1.80+, `repowire serve` running
- Two project directories: `~/projects/alpha` and `~/projects/beta`
- Optional: `.repowire.yaml` in each with distinct `display_name` and same `circle`

**Checklist (to be run by user):**

SC1 — Peer naming
- [ ] Open `~/projects/alpha` in VS Code, start Claude Code
- [ ] In daemon: `GET /peers` — peer appears with `display_name == "alpha"` (folder name)
- [ ] Open `~/projects/beta` in VS Code, start Claude Code
- [ ] `GET /peers` — two peers: `"alpha"` and `"beta"`, both ONLINE

SC2 — `.repowire.yaml` config loading
- [ ] Add `display_name: frontend` and `circle: dev` to `~/projects/alpha/.repowire.yaml`
- [ ] Restart Claude Code in that window
- [ ] `GET /peers` — peer shows `display_name == "frontend"`, `circle == "dev"`

SC3 — Liveness (ONLINE status holds)
- [ ] Start a 5-minute timer after both peers are ONLINE
- [ ] At T+5m: `GET /peers` — both peers still ONLINE (validates rich pong fix from slice 101)

SC4 — `list_peers` cross-visibility
- [ ] In alpha's Claude Code session, call `list_peers`
- [ ] Assert beta appears in the result (and vice versa)

SC5 — `ask_peer` round-trip
- [ ] In alpha's Claude: `ask_peer("beta", "What is 1+1?")`
- [ ] Beta receives the `<channel>` tag, responds via `reply` tool
- [ ] Alpha receives the response (validates full query → reply → resolve path)

SC6 — Circle isolation
- [ ] Register alpha in `circle: dev`, beta in `circle: prod` (via `.repowire.yaml`)
- [ ] In alpha's Claude: `list_peers` — beta is NOT visible (different circle)
- [ ] In alpha's Claude: `ask_peer("beta", "hello")` — returns 404-style error

SC7 — `set_display_name` rename
- [ ] In alpha's Claude: `set_display_name("my-frontend")`
- [ ] In beta's Claude: `list_peers` — sees `"my-frontend"`, not `"alpha"` / `"frontend"`

### 4. GitHub Issue

The slice plan notes mention opening a GitHub issue on the upstream repo describing the VS Code use case before submitting PRs. This is a communication step, not a code step.

**Issue content outline:**
- Describe the VS Code + channel transport use case (two windows, different projects)
- List the bugs that were found and fixed (slices 100-102)
- Reference the branch sequence for PR review
- Note the `.repowire.yaml` config and `set_display_name` as new user-facing features

## Files Changed

| File | Change |
|------|--------|
| `README.md` | Add VS Code setup `<details>` block; add `set_display_name` to tools table |
| `project-documents/user/slices/103-slice.end-to-end-vs-code-verification.md` | This document |
| *(verification report)* | Created after manual run: pass/fail per SC, any bugs found |

## Scope Boundaries

**In scope:**
- README updates (VS Code section, tools table)
- Manual verification checklist execution (by user)
- Verification report documenting results
- GitHub issue draft
- Bug fixes for anything discovered during verification

**Out of scope:**
- Automated integration tests for the VS Code E2E flow (no headless Claude Code test harness exists)
- Changes to daemon, routes, or MCP server (unless a bug is found)
- CI automation for the E2E scenario

## Success Criteria

- Two VS Code Claude Code sessions in different projects are visible via `list_peers`
- Both maintain ONLINE status for >5 minutes
- `ask_peer` successfully delivers a query and receives a response
- Peers show meaningful names (project folder name or `.repowire.yaml` `display_name`)
- Circle isolation works — peers in different circles don't see each other
- `set_display_name` rename is immediately reflected in other peers' `list_peers`
- README VS Code section is present and accurate
- `set_display_name` appears in the MCP tools table
