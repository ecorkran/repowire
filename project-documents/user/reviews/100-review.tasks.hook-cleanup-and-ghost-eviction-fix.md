---
docType: review
layer: project
reviewType: tasks
slice: hook-cleanup-and-ghost-eviction-fix
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/100-tasks.hook-cleanup-and-ghost-eviction-fix.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260326
dateUpdated: 20260326
---

# Review: tasks — slice 100

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Missing test for non-repowire hook preservation

**Success Criteria #2 and #10** require that "channel mode install preserves non-repowire hooks" and "preserves any non-repowire hooks in the same events." However, **Task 3** contains no test validating this behavior.

The implementation likely handles this correctly—using `LEGACY_HOOK_EVENTS` with `pop(event, None)` only removes those four specific keys, leaving other tools' hooks untouched. But without an explicit test, this invariant is not verified and could regress.

**Recommendation:** Add `test_channel_mode_preserves_non_repowire_hooks` that mocks `settings["hooks"]["SessionStart"]` with a non-repowire value before calling `install_hooks(channel_mode=True)`, then asserts that non-repowire entry is preserved while repowire entries are removed.

### [PASS] All success criteria map to implementation tasks

Cross-referencing the 11 success criteria against tasks:

| Success Criterion | Task(s) |
|-------------------|---------|
| Remove legacy hooks in channel mode | Task 2 |
| Preserves non-repowire hooks | Task 2 (impl) — no test |
| Full mode path unaffected | Task 2, Task 3 (`test_full_mode_installs_all_hooks`) |
| Idempotent channel mode install | Task 3 (`test_channel_mode_idempotent`) |
| Ghost eviction circle-agnostic | Task 4 |
| Mapping lookup reuses session_id | Task 6 |
| test_register_duplicate_peer passes | Task 5 (explicitly checks) |
| Cross-circle duplicate → 1 peer | Task 5 (`test_evict_ghost_cross_circle`) |
| Pre-existing legacy hooks removed | Task 3 (`test_channel_mode_removes_legacy_hooks`) |
| Non-repowire hooks preserved | Task 2 (impl only — see CONCERN above) |
| All 222 tests pass | Task 8 |

### [PASS] Test-with pattern correctly followed

All test tasks immediately follow their implementation counterparts:
- Task 2 (implement hook cleanup) → Task 3 (test hook cleanup) ✓
- Task 4 (implement ghost eviction) → Task 5 (test ghost eviction) ✓
- Task 6 (implement mapping relaxation) → Task 7 (test mapping relaxation) ✓

### [PASS] Commit checkpoints distributed throughout

Commits are spread across the task sequence:
- Task 1: `chore: create branch...`
- Task 3: `fix: remove stale legacy hooks...`
- Task 5: `fix: ghost eviction matches...`
- Task 7: `fix: reuse session mapping...`
- Task 8: `test: verify full regression suite...`
- Task 9: `docs: mark slice 100...`

No commits are batched at the end.

### [PASS] Sequencing is correct with no circular dependencies

The dependency chain is linear and logical:
1. Branch creation
2. Hook cleanup implementation
3. Hook cleanup tests
4. Ghost eviction implementation  
5. Ghost eviction tests
6. Mapping lookup relaxation
7. Mapping lookup tests
8. Full regression suite
9. Documentation update

### [PASS] All tasks are appropriately scoped

- Task 2 is focused: single function modification with defined behavior
- Task 3 contains 4-5 tests but all address the same feature (installer hook behavior)
- Task 4 is focused: one function, one condition removal + mapping cleanup addition
- Task 8 appropriately encompasses full regression suite

No tasks are too large to split or too granular to merge.
