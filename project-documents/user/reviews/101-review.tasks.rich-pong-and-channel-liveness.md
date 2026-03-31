---
docType: review
layer: project
reviewType: tasks
slice: rich-pong-and-channel-liveness
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/101-tasks.rich-pong-and-channel-liveness.md
aiModel: z-ai/glm-5
status: complete
dateCreated: 20260330
dateUpdated: 20260330
---

# Review: tasks — slice 101

**Verdict:** CONCERNS
**Model:** z-ai/glm-5

## Findings

### [PASS] Complete success criteria coverage mapping

All seven success criteria from the slice design are addressed by the tasks:
- Criterion 1 (3 consecutive cycles): Task 3's `test_channel_pong_with_circle_stays_online` tests peer stays ONLINE
- Criterion 2 (pong includes circle): Task 2 directly implements the one-line fix
- Criteria 3-4 (new tests pass): Task 3 implements both required tests with pass verification
- Criterion 5 (existing tests pass): Task 4 verifies full suite passes
- Criterion 6 (ruff check): Task 4 includes lint check
- Criterion 7 (full suite passes): Task 4 explicitly verifies 234+ tests

### [PASS] Correct task sequencing with test-with pattern

Tasks follow proper implementation order: branch creation (Task 1) → implementation (Task 2) → tests (Task 3) → regression verification (Task 4) → documentation (Task 5). Tests immediately follow their implementation task, satisfying the test-with pattern.

### [PASS] Appropriate task granularity

Task 2 is correctly scoped as a single one-line change with verification of constant scope. Task 3 groups two related tests into one task appropriately since they share the same test file and context setup. Neither task is too large or too granular.

### [PASS] Well-distributed commit checkpoints

Commits are distributed throughout: Task 1 (branch creation), Task 2 (implementation), Task 3 (tests), Task 5 (documentation). Task 4 appropriately has no commit since it's verification-only. This avoids batched-at-end anti-pattern.

### [CONCERN] Success criterion #1 test coverage ambiguity

The success criterion states: "Channel peer remains ONLINE across at least 3 consecutive `lazy_repair` cycles (confirmed by test)". However, Task 3's `test_channel_pong_with_circle_stays_online` description specifies calling `lazy_repair()` only once. The slice design's Technical Decisions section notes that "What to verify in slice 103: Manual end-to-end test in VS Code confirming peers hold ONLINE across at least 3 consecutive `lazy_repair` cycles" — suggesting the 3-cycle verification is actually slice 103's E2E test, not this unit test. Either the success criterion wording should clarify this is deferred to slice 103, or the test should call `lazy_repair()` multiple times to match the stated criterion.

### [PASS] No scope creep identified

All tasks trace directly to success criteria. No tasks exist that don't map to requirements. Out-of-scope items (display name improvements, VS Code E2E verification, WebSocket refactoring, daemon changes) are correctly excluded.
