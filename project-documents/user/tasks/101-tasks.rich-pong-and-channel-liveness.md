---
docType: tasks
slice: rich-pong-and-channel-liveness
project: repowire
lld: project-documents/user/slices/101-slice.rich-pong-and-channel-liveness.md
dependencies: [100]
projectState: Slice 100 complete; channel transport produces 1 peer per session, liveness mechanism is correct but pong lacks circle field
dateCreated: 20260330
dateUpdated: 20260330
status: complete
---

## Context Summary

- Working on slice 101: Rich Pong and Channel Liveness
- `channel/server.ts` responds to daemon pings with bare `{"type": "pong"}` — no `circle` field
- `lazy_repair()` in `peer_registry.py` already reads `circle` from pong for circle recovery; channel peers never trigger this path
- Fix is a one-line change in `server.ts`; no daemon changes needed
- "Goes offline in <30s" symptom traced to slice 100's duplicate-peer bug, not liveness mechanism
- Two new tests in `tests/test_lazy_repair.py`: rich pong stays ONLINE, circle recovery from pong

## Tasks

### Task 1: Create slice branch

- [x] **Create branch `101-rich-pong-and-channel-liveness` from main**
  - [x] Verify on main: `git branch --show-current`
  - [x] Create branch: `git checkout -b 101-rich-pong-and-channel-liveness`
  - [x] Confirm all existing tests pass: `uv run pytest tests/`

**Commit:** `chore: create branch for slice 101 rich pong and channel liveness`

### Task 2: Add circle to pong in channel/server.ts

- [x] **Modify `repowire/channel/server.ts` line 69**
  - [x] Change `{ type: "pong" }` to `{ type: "pong", circle: CIRCLE }`
  - [x] Verify `CIRCLE` constant is in scope at the ping handler (it is — defined at module top-level as `const CIRCLE = process.env.REPOWIRE_CIRCLE ?? "default"`)

**Commit:** `fix: include circle in channel transport pong for circle recovery`

### Task 3: Add liveness tests

- [x] **Add two tests to `TestLazyRepairLiveness` in `tests/test_lazy_repair.py`**

  - [x] `test_channel_pong_with_circle_stays_online`:
    - Set up transport mock with `ping` returning `{"type": "pong", "circle": "dev"}`
    - Register peer with `circle="dev"`, call `lazy_repair()`
    - Assert peer status is ONLINE
    - (Mirrors `test_pong_alive_stays_online` but with rich pong — documents channel peer behavior explicitly)

  - [x] `test_circle_recovery_from_rich_pong`:
    - Register peer with `circle="old-circle"` via `register_peer()`
    - Set transport mock with `ping` returning `{"type": "pong", "circle": "new-circle"}`
    - Call `lazy_repair()`
    - Assert peer status is ONLINE
    - Assert `peer.circle == "new-circle"` (circle updated by lazy_repair's recovery path)

  - [x] All tests pass: `uv run pytest tests/test_lazy_repair.py -v`

**Commit:** `test: add rich pong and circle recovery tests to lazy_repair suite`

### Task 4: Run full regression suite

- [x] **Verify all tests pass with no regressions**
  - [x] Run: `uv run pytest tests/ -v`
  - [x] All 234+ tests pass (236 passed)
  - [x] Run: `ruff check repowire/`
  - [x] No lint errors

### Task 5: Update slice status

- [x] **Mark slice 101 as complete in project documents**
  - [x] Update `status: complete` in `project-documents/user/slices/101-slice.rich-pong-and-channel-liveness.md` frontmatter
  - [x] Update `dateUpdated` to today
  - [x] Check off slice 101 in `project-documents/user/architecture/100-slices.vscode-channel-fixes.md`

**Commit:** `docs: mark slice 101 rich pong and channel liveness complete`
