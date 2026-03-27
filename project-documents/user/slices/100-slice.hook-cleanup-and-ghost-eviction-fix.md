---
docType: slice-design
slice: hook-cleanup-and-ghost-eviction-fix
project: repowire
parent: project-documents/user/architecture/100-slices.vscode-channel-fixes.md
dependencies: []
interfaces: [101, 102, 103]
dateCreated: 20260326
dateUpdated: 20260327
status: complete
---

# Slice 100: Hook Cleanup and Ghost Eviction Fix

## Overview

When `repowire setup` runs in channel mode, it installs only the Stop hook — but it does not remove legacy hooks (SessionStart, SessionEnd, UserPromptSubmit, Notification) that may exist from a prior full install. These stale hooks cause duplicate peer registration because the SessionStart hook registers via HTTP `POST /peers` with `circle = tmux_session_name`, while the channel transport registers via WebSocket `connect` with `circle = "default"`. The daemon's ghost eviction logic fails to deduplicate because it requires matching circles.

This slice fixes both problems: the installer actively cleans stale hooks, and ghost eviction matches on `(display_name, backend)` regardless of circle.

## Technical Decisions

### 1. Installer Hook Cleanup

**File:** `repowire/installers/claude_code.py`

**Current behavior (line 59-78):** `install_hooks(channel_mode=True)` sets the Stop hook but does not touch other hook events. If SessionStart/SessionEnd/UserPromptSubmit/Notification entries exist from a prior install, they remain.

**Fix:** When `channel_mode=True`, explicitly remove the four non-Stop hook events from `settings["hooks"]`. This is the same delete logic already in `uninstall_hooks()` (lines 81-99) but scoped to only the legacy events.

```python
# In install_hooks(), after setting Stop hook, when channel_mode=True:
LEGACY_HOOK_EVENTS = ["SessionStart", "SessionEnd", "UserPromptSubmit", "Notification"]
if channel_mode:
    for event in LEGACY_HOOK_EVENTS:
        settings["hooks"].pop(event, None)
```

**Why not call `uninstall_hooks()` first:** That would remove the Stop hook too, creating a window where no hooks exist. The targeted removal is simpler and atomic within a single settings write.

**Idempotency:** `dict.pop(event, None)` is a no-op if the key doesn't exist. Running setup twice produces identical results.

### 2. Ghost Eviction Circle-Agnostic Matching

**File:** `repowire/daemon/peer_registry.py`

**Current behavior (lines 272-283):** `_evict_ghosts()` evicts peers matching `(display_name, backend)` only if `old_peer.circle == circle OR old_peer.status == PeerStatus.OFFLINE`. This means an ONLINE peer with the same name but different circle survives eviction — creating the duplicate.

**Fix:** Remove the circle condition from eviction. A peer with the same `(display_name, backend)` is the same logical agent regardless of which circle it registered under. The new peer's circle is authoritative.

```python
def _evict_ghosts(
    self, display_name: str, backend: AgentType, new_peer_id: str, circle: str,
) -> None:
    for old_sid, old_peer in list(self._peers.items()):
        if (
            old_peer.display_name == display_name
            and old_peer.backend == backend
            and old_sid != new_peer_id
        ):
            del self._peers[old_sid]
```

**Why this is safe:** The `circle` parameter is still passed (for logging or future use), but the match no longer requires it. The scenario where the same `(display_name, backend)` legitimately exists in two circles is not valid — a single Claude Code session produces one agent, not one per circle. If a user intentionally wants two identically-named peers in different circles, they'd use different display names.

**Mapping cleanup:** When a ghost is evicted from `_peers`, its `_mappings` entry may remain stale. The eviction should also clean up the mapping:

```python
if old_sid in self._mappings:
    del self._mappings[old_sid]
    self._mappings_dirty = True
```

### 3. Mapping Lookup Relaxation

**File:** `repowire/daemon/peer_registry.py`

**Current behavior (lines 237-270):** `_find_or_allocate_mapping()` matches on `(display_name, circle, backend)`. When the channel registers with `circle="default"` and a stale mapping exists from the hook path with `circle="dev"`, a new mapping is allocated instead of reusing the existing one.

**Fix:** Change the mapping lookup to match on `(display_name, backend)` only, ignoring circle. If found, update the mapping's circle to the new value. This ensures a reconnecting peer reuses its session_id even if the circle changed.

```python
for sid, mapping in self._mappings.items():
    if (
        mapping.display_name == display_name
        and mapping.backend == backend
    ):
        mapping.circle = circle  # Update to current circle
        mapping.path = path
        mapping.updated_at = datetime.now(timezone.utc).isoformat()
        self._mappings_dirty = True
        return sid
```

**Risk consideration:** This means two peers with the same name but intentionally different circles would collide. This is acceptable — display names should be unique per backend. The per-project config in slice 102 will make unique naming easy.

## Data Flow

### Before Fix (Duplicate Registration)

```
VS Code starts Claude Code session
    ↓
SessionStart hook fires (stale from prior install)
    → HTTP POST /peers {display_name: "abc12345", circle: "dev-tmux"}
    → Daemon creates Peer A: repow-dev-tmux-xxxx
    ↓
Channel server.ts connects via WebSocket
    → WS connect {display_name: "abc12345", circle: "default"}
    → Daemon: ghost eviction checks circle match → NO MATCH → keeps Peer A
    → Daemon creates Peer B: repow-default-yyyy
    ↓
Result: 2 peers for 1 session
```

### After Fix (Clean Registration)

```
VS Code starts Claude Code session
    ↓
SessionStart hook: removed by setup → does not fire
    ↓
Channel server.ts connects via WebSocket
    → WS connect {display_name: "abc12345", circle: "default"}
    → Daemon: ghost eviction matches on (display_name, backend) → evicts any stale peer
    → Daemon creates/reuses Peer: repow-default-xxxx
    ↓
Result: 1 peer for 1 session
```

## Cross-Slice Dependencies

- **Slice 101 (Rich Pong)** depends on this: without deduplication, fixing pong would keep two peers online instead of one.
- **Slice 102 (Peer Identity)** depends on this: naming improvements assume a single peer per session.
- This slice has **no upstream dependencies**.

## Success Criteria

- `install_hooks(channel_mode=True)` removes SessionStart, SessionEnd, UserPromptSubmit, and Notification entries from settings.json
- `install_hooks(channel_mode=True)` preserves any non-repowire hooks in the same events (if the user has other tools hooking the same events)
- `install_hooks(channel_mode=False)` still installs all hooks (tmux path unaffected)
- Running `install_hooks(channel_mode=True)` twice produces identical settings.json
- `_evict_ghosts()` removes peers with same `(display_name, backend)` regardless of circle
- `_find_or_allocate_mapping()` reuses session_id when `(display_name, backend)` matches, updating circle
- Existing test `test_register_duplicate_peer` continues to pass
- New test: cross-circle duplicate registration produces exactly 1 peer
- New test: channel mode install with pre-existing legacy hooks removes them
- New test: channel mode install preserves non-repowire hooks
- All 222 existing tests pass

## Verification Walkthrough

*Draft — to be refined after implementation.*

### 1. Verify hook cleanup

```bash
# Start with a full hook install (simulating prior setup)
python -c "from repowire.installers.claude_code import install_hooks; install_hooks(channel_mode=False)"

# Confirm all hooks present
python -c "
import json
settings = json.load(open('~/.claude/settings.json'.replace('~', __import__('os').path.expanduser('~'))))
hooks = settings.get('hooks', {})
print('Before:', sorted(hooks.keys()))
"
# Expected: ['Notification', 'SessionEnd', 'SessionStart', 'Stop', 'UserPromptSubmit']

# Now run channel mode install
python -c "from repowire.installers.claude_code import install_hooks; install_hooks(channel_mode=True)"

# Confirm only Stop remains
python -c "
import json
settings = json.load(open('~/.claude/settings.json'.replace('~', __import__('os').path.expanduser('~'))))
hooks = settings.get('hooks', {})
print('After:', sorted(hooks.keys()))
"
# Expected: ['Stop']
```

### 2. Verify ghost eviction

```bash
# Run the test suite
pytest tests/ -v -k "ghost or evict or duplicate"

# Run full suite to confirm no regressions
pytest tests/
```

### 3. Verify end-to-end deduplication

```bash
# Start daemon
repowire daemon start

# Register a peer via HTTP (simulating stale hook)
curl -X POST http://127.0.0.1:8377/peers \
  -H "Content-Type: application/json" \
  -d '{"name":"test","display_name":"test","path":"/tmp","circle":"tmux-circle","backend":"claude-code"}'

# Register same peer via different circle (simulating channel)
curl -X POST http://127.0.0.1:8377/peers \
  -H "Content-Type: application/json" \
  -d '{"name":"test","display_name":"test","path":"/tmp","circle":"default","backend":"claude-code"}'

# List peers — should show exactly 1 peer named "test"
curl http://127.0.0.1:8377/peers | python -m json.tool
# Expected: 1 peer with circle="default"
```
