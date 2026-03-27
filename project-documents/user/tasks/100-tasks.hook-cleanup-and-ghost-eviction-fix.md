---
docType: tasks
slice: hook-cleanup-and-ghost-eviction-fix
project: repowire
lld: project-documents/user/slices/100-slice.hook-cleanup-and-ghost-eviction-fix.md
dependencies: []
projectState: Channel transport exists but produces duplicate peers and stale hooks persist across mode switches
dateCreated: 20260326
dateUpdated: 20260327
status: complete
---

## Context Summary

- Working on slice 100: Hook Cleanup and Ghost Eviction Fix
- Repowire has a channel transport (server.ts) and legacy hook transport; both can register peers simultaneously
- `install_hooks(channel_mode=True)` does not remove pre-existing legacy hooks, causing duplicate registration
- Ghost eviction in `_evict_ghosts()` requires circle match, failing when hook and channel use different circles
- `_find_or_allocate_mapping()` requires circle match, creating duplicate session mappings
- This slice delivers: clean single-peer registration for channel mode, no duplicates
- Next slice: 101 (Rich Pong and Channel Liveness)

## Tasks

### Task 1: Create slice branch

- [x] **Create branch `100-hook-cleanup-and-ghost-eviction-fix` from main**
  - [x] Verify on main: `git branch --show-current`
  - [x] Create branch: `git checkout -b 100-hook-cleanup-and-ghost-eviction-fix`
  - [x] Confirm all existing tests pass: `pytest tests/`

**Commit:** `chore: create branch for slice 100 hook cleanup and ghost eviction fix`

### Task 2: Fix installer hook cleanup in channel mode

- [x] **Modify `install_hooks()` in `repowire/installers/claude_code.py` to remove legacy hooks when `channel_mode=True`**
  - [x] Define `LEGACY_HOOK_EVENTS` list: `["SessionStart", "SessionEnd", "UserPromptSubmit", "Notification"]`
  - [x] In the `install_hooks()` function, after setting the Stop hook, add a block: when `channel_mode` is True, iterate `LEGACY_HOOK_EVENTS` and for each event, filter the hook list to remove only entries whose `command` starts with `"repowire"`. If the filtered list is empty, remove the event key entirely. This preserves non-repowire hooks that other tools may have registered on the same event.
  - [x] Verify `install_hooks(channel_mode=False)` path is unchanged — the `if not channel_mode:` block still installs all hooks

### Task 3: Test installer hook cleanup

- [x] **Add tests in `tests/test_hooks_installer.py`** (new file, or add to existing test file if one covers the installer)
  - [x] Test: `test_channel_mode_removes_legacy_hooks` — call `install_hooks(channel_mode=False)` then `install_hooks(channel_mode=True)`, assert only `Stop` key remains in `settings["hooks"]`
  - [x] Test: `test_channel_mode_idempotent` — call `install_hooks(channel_mode=True)` twice, assert settings.json is identical both times
  - [x] Test: `test_channel_mode_no_legacy_hooks_present` — call `install_hooks(channel_mode=True)` on a clean settings.json (no prior hooks), assert only `Stop` is present
  - [x] Test: `test_full_mode_installs_all_hooks` — call `install_hooks(channel_mode=False)`, assert all 5 hook events are present (regression guard)
  - [x] Test: `test_channel_mode_preserves_non_repowire_hooks` — pre-populate `settings["hooks"]["SessionStart"]` with a non-repowire entry (e.g., `{"type": "command", "command": "other-tool hook"}`), call `install_hooks(channel_mode=True)`, assert the non-repowire entry survives while any repowire entry is removed
  - [x] Mock `CLAUDE_SETTINGS` to use a temp file (do not write to real `~/.claude/settings.json` during tests)
  - [x] All new tests pass: `pytest tests/test_hooks_installer.py -v`

**Commit:** `fix: remove stale legacy hooks when installing in channel mode`

### Task 4: Fix ghost eviction to be circle-agnostic

- [x] **Modify `_evict_ghosts()` in `repowire/daemon/peer_registry.py`**
  - [x] Remove the circle condition from the eviction check (line 281: remove `and (old_peer.circle == circle or old_peer.status == PeerStatus.OFFLINE)`)
  - [x] The match should be: `old_peer.display_name == display_name and old_peer.backend == backend and old_sid != new_peer_id`
  - [x] Add mapping cleanup: when evicting a ghost from `_peers`, also delete its entry from `_mappings` if present, and set `self._mappings_dirty = True`

### Task 5: Test ghost eviction fix

- [x] **Add tests for cross-circle ghost eviction**
  - [x] Test: `test_evict_ghost_cross_circle` — register peer with circle="tmux-session", then register same (display_name, backend) with circle="default". Assert only 1 peer exists with circle="default"
  - [x] Test: `test_evict_ghost_same_circle` — register peer twice with same circle. Assert only 1 peer exists (existing behavior preserved)
  - [x] Test: `test_evict_ghost_cleans_mapping` — register peer, register again with different circle. Assert old mapping is removed from `_mappings`
  - [x] Verify existing test `test_register_duplicate_peer` in `tests/test_routes.py` still passes
  - [x] All new tests pass

**Commit:** `fix: ghost eviction matches on display_name and backend regardless of circle`

### Task 6: Relax mapping lookup to ignore circle

- [x] **Modify `_find_or_allocate_mapping()` in `repowire/daemon/peer_registry.py`**
  - [x] Change the matching condition from `(display_name, circle, backend)` to `(display_name, backend)`
  - [x] When a match is found, update the mapping's `circle` field to the new value: `mapping.circle = circle`
  - [x] Keep existing updates to `path` and `updated_at`

### Task 7: Test mapping lookup relaxation

- [x] **Add tests for circle-agnostic mapping reuse**
  - [x] Test: `test_mapping_reused_across_circles` — register peer with circle="old", then register same (display_name, backend) with circle="new". Assert same session_id is reused and mapping's circle is updated to "new"
  - [x] Test: `test_mapping_different_backend_not_reused` — register peer with backend="claude-code", then register same display_name with backend="opencode". Assert different session_ids are allocated
  - [x] All new tests pass

**Commit:** `fix: reuse session mapping across circle changes for same peer identity`

### Task 8: Run full regression suite

- [x] **Verify all existing tests pass with no regressions**
  - [x] Run: `pytest tests/ -v`
  - [x] All 222+ tests pass (original count plus new tests)
  - [x] Run: `ruff check repowire/`
  - [x] No lint errors

**Commit:** `test: verify full regression suite passes after eviction and installer fixes`

### Task 9: Update slice status

- [x] **Mark slice 100 as complete in project documents**
  - [x] Update `status: complete` in `project-documents/user/slices/100-slice.hook-cleanup-and-ghost-eviction-fix.md` frontmatter
  - [x] Update `dateUpdated` to today
  - [x] Check off slice 100 in `project-documents/user/architecture/100-slices.vscode-channel-fixes.md`

**Commit:** `docs: mark slice 100 hook cleanup and ghost eviction fix complete`
