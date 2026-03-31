---
docType: tasks
slice: end-to-end-vs-code-verification
project: repowire
lld: project-documents/user/slices/103-slice.end-to-end-vs-code-verification.md
dependencies: [100, 101, 102]
projectState: Slices 100-102 complete; ghost eviction fixed, rich pong liveness fixed, display name fallback chain + .repowire.yaml + set_display_name tool all implemented
dateCreated: 20260331
dateUpdated: 20260331
status: not_started
---

## Context Summary

- Slice 103: End-to-End VS Code Verification
- All channel transport bugs from slices 100-102 are fixed; this slice confirms they work together in a real VS Code environment
- Two tracks: (A) README code changes — automated; (B) manual verification — requires user with two VS Code windows
- No new daemon code unless a bug is discovered during verification
- Branch `103-end-to-end-vscode-verification` already exists, stacked on 102

## Tasks

### Task 1: Create slice branch

- [x] **Branch `103-end-to-end-vscode-verification` already created from `102-peer-identity-and-per-project-config`**
  - [x] Verify: `git branch --show-current` → `103-end-to-end-vscode-verification`
  - [x] Confirm stacked on 102 tip: `git log --oneline -1` → slice 102 completion commit

**No commit needed — branch already exists.**

### Task 2: Update README — VS Code setup section

- [ ] **Add VS Code `<details>` block to the "Claude Code Transport" section of `README.md`**

  - [ ] In the `### Claude Code Transport` section, after the existing paragraph ending with `"not available for API/Console key auth"`, add:
    ```markdown
    <details>
    <summary><strong>VS Code setup</strong></summary>

    Claude Code in VS Code registers automatically via the channel transport — no tmux or `repowire peer new` required.

    1. Start the daemon: `repowire serve`
    2. Run `repowire setup` once — installs the repowire MCP server in `~/.claude.json`
    3. Open a project folder in VS Code and start Claude Code
    4. The peer registers with the project folder name as its display name

    To configure circle or display name per-project, add `.repowire.yaml` to the project root:

    ```yaml
    display_name: frontend   # defaults to project folder name
    circle: myteam           # defaults to "default"
    ```

    Multiple VS Code windows register as separate peers. Use `list_peers` in any session to see all connected peers.

    </details>
    ```

  - [ ] Verify the block renders correctly (no broken markdown nesting)

**Commit:** `docs: add VS Code setup section to README`

### Task 3: Update README — MCP tools table

- [ ] **Add `set_display_name` row to the MCP Tools table**

  - [ ] In the `## MCP Tools` table, add after the `set_description` row:
    ```markdown
    | `set_display_name` | Mutation | Rename yourself in the mesh — change is immediately reflected in other peers' `list_peers` |
    ```
  - [ ] Verify table alignment is not broken

**Commit:** `docs: add set_display_name to MCP tools table in README`

### Task 4: Manual verification — HAND OFF TO USER

> **Claude stops here. The following checklist requires two live VS Code sessions.**
> **Run tasks 4a–4g in order. Stop and report any failure before continuing.**

**Prerequisites:**
- `repowire serve` running locally
- Two project directories: `~/projects/alpha` and `~/projects/beta` (or any two real project folders)
- Claude Code v2.1.80+ in VS Code (channel transport active)
- `repowire setup` already run (MCP server registered in `~/.claude.json`)

---

#### 4a — SC1: Peer naming defaults to folder name

- [ ] Open `~/projects/alpha` in VS Code, start Claude Code
- [ ] Run: `curl -s http://localhost:8377/peers | python3 -m json.tool | grep display_name`
- [ ] Assert: peer appears with `display_name == "alpha"` (the folder name, not `"channel"`)
- [ ] Open `~/projects/beta` in VS Code, start Claude Code
- [ ] Assert: two peers visible — `"alpha"` and `"beta"`, both `status: online`

#### 4b — SC2: `.repowire.yaml` config loading

- [ ] Create `~/projects/alpha/.repowire.yaml`:
  ```yaml
  display_name: frontend
  circle: dev
  ```
- [ ] Restart Claude Code in the alpha window (close and reopen)
- [ ] Assert: peer shows `display_name == "frontend"`, `circle == "dev"`

#### 4c — SC3: Liveness — ONLINE status holds for >5 minutes

- [ ] Ensure both peers are ONLINE
- [ ] Wait 5 minutes without interacting with either session
- [ ] Run: `curl -s http://localhost:8377/peers | python3 -m json.tool | grep status`
- [ ] Assert: both peers still `"online"` (validates rich pong fix from slice 101)

#### 4d — SC4: Cross-visibility via `list_peers`

- [ ] In alpha's Claude Code session, call: `list_peers`
- [ ] Assert: beta (or its `.repowire.yaml` name) appears in the output
- [ ] In beta's Claude Code session, call: `list_peers`
- [ ] Assert: alpha / `"frontend"` appears in the output

#### 4e — SC5: `ask_peer` round-trip

- [ ] In alpha's Claude: ask it to call `ask_peer` targeting beta with a simple question (e.g., "What is 1+1?")
- [ ] Beta receives the `<channel>` tag with `msg_type="query"` and responds via the `reply` tool
- [ ] Alpha receives the response and displays it
- [ ] Assert: full query → reply → resolve cycle completes successfully

#### 4f — SC6: Circle isolation

- [ ] Set `circle: prod` in `~/projects/beta/.repowire.yaml`, restart beta's Claude Code
- [ ] alpha is in `circle: dev`, beta is now in `circle: prod`
- [ ] In alpha's Claude: call `list_peers` — assert beta is NOT visible
- [ ] In alpha's Claude: attempt `ask_peer("beta", "hello")` — assert error (peer not found)

#### 4g — SC7: `set_display_name` rename

- [ ] First restore both peers to the same circle (e.g., both `circle: dev`) so they can see each other
- [ ] In alpha's Claude: call `set_display_name("my-frontend")`
- [ ] Assert: tool returns `"Display name updated to: my-frontend"`
- [ ] In beta's Claude: call `list_peers` — assert `"my-frontend"` appears, `"frontend"` does not

---

**After manual verification:** Report pass/fail for each SC to Claude so Task 5 can proceed.

### Task 5: Write verification report

- [ ] **Create `project-documents/user/reviews/103-verification.end-to-end-vs-code.md`**

  Based on manual test results, record:
  - Pass/fail for each SC (4a–4g)
  - Exact commands run and observed output for any failures
  - Any bugs found (if a bug is found, open a sub-task and fix before marking complete)
  - Overall verdict: PASS or FAIL WITH ISSUES

**Commit:** `docs: add E2E verification report for slice 103`

### Task 6: Draft GitHub issue

- [ ] **Draft `project-documents/user/reference/103-github-issue-draft.md`**

  The issue targets the upstream repowire repo and describes the VS Code use case + PRs:

  - Title: `feat: VS Code channel transport fixes (ghost eviction, liveness, peer identity)`
  - Body sections:
    - Problem: VS Code Claude Code sessions register as duplicates, go offline after 30s, display as `"channel"`
    - Root causes found and fixed (one bullet per slice: 100, 101, 102)
    - New features: `.repowire.yaml` per-project config, `set_display_name` MCP tool
    - Branch/PR plan: three branches ready for review
    - Ask: review in order (100 first, then 101+102 parallel, 103 is verification)

**Commit:** `docs: add GitHub issue draft for upstream VS Code fix contribution`

### Task 7: Update slice status

- [ ] **Mark slice 103 as complete**
  - [ ] Update `status: complete` and `dateUpdated: 20260331` in `project-documents/user/slices/103-slice.end-to-end-vs-code-verification.md`
  - [ ] Update `status: complete` in this tasks file frontmatter
  - [ ] Check off slice 103 in `project-documents/user/architecture/100-slices.vscode-channel-fixes.md`

**Commit:** `docs: mark slice 103 end-to-end VS Code verification complete`
