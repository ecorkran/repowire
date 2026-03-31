---
docType: slice-design
slice: rich-pong-and-channel-liveness
project: repowire
parent: project-documents/user/architecture/100-slices.vscode-channel-fixes.md
dependencies: [100]
interfaces: [102, 103]
dateCreated: 20260329
dateUpdated: 20260330
status: complete
---

# Slice 101: Rich Pong and Channel Liveness

## Overview

The channel transport (`channel/server.ts`) responds to daemon pings with a bare `{"type": "pong"}`. The daemon's `lazy_repair()` already uses the pong's `circle` field for circle recovery — updating a peer's circle if the pong indicates it has changed. Since channel peers never include `circle` in their pongs, circle recovery never fires for them.

The fix is a one-line change: include `circle: CIRCLE` in the pong. This enables the same circle-recovery path that tmux hook peers already use.

**On the "goes offline" symptom:** After investigation, the basic ping/pong liveness cycle is correct — a bare pong resolves the pending future and keeps the peer ONLINE. The "goes offline in <30 seconds" report was caused by the duplicate-peer bug from slice 100: two peers registered for one session (hook + channel, different circles), ghost eviction failed, then one peer's WebSocket dropped during reconnection while the other became stale. With slice 100 in place, this symptom should be gone. Slice 101 adds the circle field and test coverage to confirm the liveness path works as expected.

## Technical Decisions

### 1. Rich Pong in `channel/server.ts`

**File:** `repowire/channel/server.ts`

**Current behavior (line 69):**
```ts
ws?.send(JSON.stringify({ type: "pong" }));
```

**Fix:**
```ts
ws?.send(JSON.stringify({ type: "pong", circle: CIRCLE }));
```

**Why this is all that's needed:** The daemon's `_do_repair()` already handles pong with circle:
```python
pong = await transport.ping(peer_id, timeout=5.0)
pong_circle = pong.get("circle")
return (peer_id, pong_circle or circle)  # falls back to current if None
```
If `pong_circle` is set and differs from the current peer circle, `set_peer_circle` is called. No daemon changes are required.

**Backward compatibility:** Channel peers that ship this change continue to work with older daemons — the `circle` field is simply ignored if the daemon doesn't look for it.

### 2. WebSocket Stability Investigation

**Finding:** No WebSocket stability bugs found in `server.ts`. The close + error handlers are correct: close fires after error (per WS protocol), so `scheduleReconnect` always fires. The 2-second reconnect timer is sufficient — peer re-registers and returns ONLINE before `lazy_repair` can fire (30s minimum).

**One minor note:** The error handler in `server.ts` (line 101-103) logs the error but does not call `scheduleReconnect`. This is intentional — the `close` event fires after `error`, so reconnect happens via the close handler. No change needed.

**What to verify in slice 103:** Manual end-to-end test in VS Code confirming peers hold ONLINE across at least 3 consecutive `lazy_repair` cycles (90+ seconds with no interaction).

### 3. New Tests in `tests/test_lazy_repair.py`

Two tests added to `TestLazyRepairLiveness`:

**`test_channel_pong_with_circle_stays_online`**
Same as the existing `test_pong_alive_stays_online`, but pong returns `{"type": "pong", "circle": "default"}`. Confirms the richer pong doesn't break anything. Explicitly documents the expected behavior for channel-transport peers.

**`test_circle_recovery_from_rich_pong`**
Peer registered with `circle="old"`, pong returns `{"type": "pong", "circle": "new"}`. After `lazy_repair`, peer's circle should be `"new"`. This verifies the circle-recovery path works end-to-end — previously untested.

## Data Flow

### Before Fix: Circle Recovery Never Fires for Channel Peers

```
lazy_repair → ping(peer_id)
    → daemon sends {"type": "ping"} via WS
    → server.ts receives ping, sends {"type": "pong"}    ← no circle
    → daemon: pong_circle = None → falls back to current circle
    → circle recovery: no-op (current == current)
```

### After Fix: Circle Recovery Available for Channel Peers

```
lazy_repair → ping(peer_id)
    → daemon sends {"type": "ping"} via WS
    → server.ts receives ping, sends {"type": "pong", "circle": "default"}
    → daemon: pong_circle = "default"
    → if peer.circle != "default": set_peer_circle(peer_id, "default")
    → peer stays ONLINE, circle is up-to-date
```

## Scope Boundaries

**In scope:**
- Add `circle` to pong in `server.ts`
- Two new liveness tests covering rich pong and circle recovery

**Out of scope:**
- Display name improvements (slice 102)
- VS Code end-to-end verification (slice 103)
- WebSocket reconnection refactoring (no changes needed)
- Daemon changes (no changes needed)

## Success Criteria

- Channel peer remains ONLINE across at least 3 consecutive `lazy_repair` cycles (confirmed by test)
- Pong includes `circle`, enabling circle recovery for channel peers
- New test `test_channel_pong_with_circle_stays_online` passes
- New test `test_circle_recovery_from_rich_pong` passes
- All existing `test_lazy_repair.py` tests pass unchanged
- `ruff check repowire/` passes
- Full test suite passes (234+ tests from slice 100)
