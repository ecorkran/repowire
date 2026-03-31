---
docType: review
layer: project
reviewType: tasks
slice: peer-identity-and-per-project-config
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/102-tasks.peer-identity-and-per-project-config.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260331
dateUpdated: 20260331
---

# Review: tasks — slice 102

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Missing tests for display name fallback chain (SC 1)

**Success Criterion 1** states: *"Without any config, a VS Code channel peer is named after its project folder (not `"channel"`)"*

**Gap:** Task 2 implements the fallback chain (`.repowire.yaml` → `CLAUDE_SESSION_ID[:8]` → folder name) but Task 6 contains no tests verifying the folder name is used when no config exists. The tests focus solely on the rename endpoint, not the initial display name resolution at startup.

**Recommendation:** Add test(s) in `tests/test_channel.py` or `tests/test_server.py` to verify that when `loadProjectConfig()` returns `{}` and no `CLAUDE_SESSION_ID` is set, the peer's display name matches the folder name from `cwd`.

---

### [CONCERN] Missing tests for `.repowire.yaml` config loading (SC 2)

**Success Criterion 2** states: *".repowire.yaml` with `circle: myteam` and/or `display_name: frontend` is honored at startup"*

**Gap:** The config file parser and integration are implemented in Task 2, but no tests verify that:
- A `.repowire.yaml` with `display_name: frontend` is correctly parsed
- A `.repowire.yaml` with `circle: myteam` is correctly parsed
- Config file values take precedence over missing env vars

**Recommendation:** Add unit tests for `loadProjectConfig()` behavior with various YAML contents, and integration tests confirming the parsed values flow into `displayName` and `CIRCLE`.

---

### [CONCERN] Missing test for `list_peers` reflecting renamed peer (SC 4)

**Success Criterion 4** states: *"`set_display_name` tool updates the daemon and is immediately reflected in `list_peers`"*

**Gap:** Task 6 tests the rename endpoint directly but does not test that `list_peers` returns the updated display name after a rename. The test `test_rename_peer_success` verifies `GET /peers/frontend` returns the renamed peer, but this is a direct lookup, not `list_peers`.

**Recommendation:** Add a test that calls `POST /peers/{name}/rename`, then calls `GET /peers` (or `list_peers`) and asserts the peer's `display_name` in the list matches the new name.

---

### [PASS] Task 8's not-found test satisfies SC 8 requirement

Task 6 includes `test_rename_peer_not_found` which tests `POST /peers/nonexistent/rename` → 404. This satisfies the "not-found" requirement in Success Criterion 8. The CONCERN above about missing this test was in error—SC 8 is satisfied.

---

### [PASS] Inconsistency between slice design and task implementation is acceptable

**Slice design** (Section 1) uses `PROJECT_PATH.split("/").pop()` while **Task 2** uses `process.cwd().split("/").pop()`. These should be equivalent if `PROJECT_PATH = process.cwd()`. The task uses the actual `process.cwd()` call which is more direct and avoids dependency on a variable. This is not a gap—just a minor documentation inconsistency.

---

### [PASS] All other success criteria have corresponding tasks

| Success Criterion | Task(s) | Status |
|-------------------|---------|--------|
| SC 3 (absence of config = no effect) | Task 2 (try/catch returns `{}`) | Covered |
| SC 5 (409 on conflict) | Task 3 + Task 6 `test_rename_peer_conflict` | Covered |
| SC 6 (ruff check passes) | Task 7 | Covered |
| SC 7 (full test suite passes) | Task 7 | Covered |
| SC 8 (success, conflict, not-found tests) | Task 6 (all three test cases present) | Covered |

---

### [PASS] Task sequencing is correct

The dependency order is sound:
1. Task 1: Branch creation
2. Task 2: Core config/display name changes in `server.ts`
3. Task 3: Daemon endpoint (backed by existing `update_peer_display_name`)
4. Tasks 4-5: MCP tools on both servers (depend on Task 3)
5. Task 6: Tests (depend on Task 3)
6. Task 7: Regression suite
7. Task 8: Documentation

No circular dependencies. Tests immediately follow implementation (Tasks 3→6, 4-5→6).

---

### [PASS] Commits are appropriately distributed

Commits are spread across: branch creation, feature implementation (Task 2, 3, 4, 5), tests, and documentation. Not batched at end.

---

### [PASS] Tasks are appropriately sized and independently completable

Each task modifies one file and has clear, testable outcomes. Tasks 4 and 5 are parallel (adding the same tool to two different servers) which is appropriate.
