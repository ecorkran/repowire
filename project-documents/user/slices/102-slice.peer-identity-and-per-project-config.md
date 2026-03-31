---
docType: slice-design
slice: peer-identity-and-per-project-config
project: repowire
parent: project-documents/user/architecture/100-slices.vscode-channel-fixes.md
dependencies: [100, 101]
interfaces: [103]
dateCreated: 20260330
dateUpdated: 20260331
status: complete
---

# Slice 102: Peer Identity and Per-Project Config

## Overview

Channel transport peers currently display as `CLAUDE_SESSION_ID[:8]` or fall back to the string literal `"channel"` — neither is useful. This slice adds a proper fallback chain (session ID → folder name), a `.repowire.yaml` per-project config for `display_name` and `circle` overrides, and a `set_display_name` MCP tool backed by the daemon's existing `update_peer_display_name` method.

The daemon already has all the business logic needed (`update_peer_display_name`, `set_peer_circle`). This slice is mostly plumbing: read a config file at startup, expose one new HTTP endpoint, and add one new tool to each MCP server.

## Technical Decisions

### 1. Display Name Fallback Chain (`server.ts`)

**Current behavior (line 24-25):**
```ts
const DISPLAY_NAME =
  (process.env.CLAUDE_SESSION_ID ?? "").slice(0, 8) || "channel";
```

The `"channel"` literal is the problem — all unnamed channel peers look the same.

**New fallback chain:**
```
.repowire.yaml display_name → CLAUDE_SESSION_ID[:8] → folder name from cwd
```

**Implementation:**
```ts
// After await loadProjectConfig()
const _sessionPrefix = (process.env.CLAUDE_SESSION_ID ?? "").slice(0, 8);
const _folderName = PROJECT_PATH.split("/").pop() || "repowire";
const DISPLAY_NAME = projectConfig.display_name || _sessionPrefix || _folderName;
```

The folder name is already available in `PROJECT_PATH = process.cwd()`. No additional work needed.

**CIRCLE resolution also updated:**
```ts
// env var takes precedence over config file
const CIRCLE = process.env.REPOWIRE_CIRCLE || projectConfig.circle || "default";
```

### 2. `.repowire.yaml` Config Loading (`server.ts`)

**File:** `.repowire.yaml` in `process.cwd()` (same directory as the project).

**Supported fields:**
```yaml
display_name: my-frontend
circle: teamA
```

Both fields are optional. Absence of the file is not an error.

**Parser — lenient `key: value` line scanning (no new dependency):**
```ts
async function loadProjectConfig(): Promise<{ circle?: string; display_name?: string }> {
  try {
    const text = await Bun.file(`${PROJECT_PATH}/.repowire.yaml`).text();
    const result: { circle?: string; display_name?: string } = {};
    for (const line of text.split("\n")) {
      const m = line.match(/^\s*(circle|display_name)\s*:\s*(.+?)\s*$/);
      if (m) {
        // Strip optional surrounding quotes (single or double)
        result[m[1] as "circle" | "display_name"] = m[2].replace(/^["']|["']$/g, "");
      }
    }
    return result;
  } catch {
    return {};
  }
}
```

This handles:
- Leading/trailing whitespace on lines
- Quoted and unquoted values
- Missing file (caught, returns `{}`)
- Extra fields (ignored)

The regex intentionally does not handle multi-line values, anchors, or nested YAML — these fields are simple strings, and that's all we parse. Per CLAUDE.md: "Parse the semantic content, not the formatting."

**Integration:** Call `loadProjectConfig()` at module startup (before `const DISPLAY_NAME`). The module already uses top-level `await` (for `fetchPeerContext`), so this is a natural addition.

```ts
const projectConfig = await loadProjectConfig();
```

### 3. `POST /peers/{name}/rename` HTTP Endpoint (`daemon/routes/peers.py`)

The daemon's `update_peer_display_name(session_id, new_name)` exists but has no HTTP exposure. A new endpoint bridges this gap.

**Route:**
```
POST /peers/{name}/rename
Body: {"display_name": "new-name"}
```

`name` is the current display_name or peer_id (same identifier accepted by `get_peer`). Optional `?circle=` query param to disambiguate name conflicts.

**Implementation:**
```python
class RenameRequest(BaseModel):
    display_name: str = Field(..., min_length=1)

@router.post("/peers/{name}/rename", response_model=OkResponse)
async def rename_peer(
    name: str,
    request: RenameRequest,
    circle: str | None = Query(None),
    _: str | None = Depends(require_auth),
) -> OkResponse:
    peer_registry = get_peer_registry()
    peer = await peer_registry.get_peer(name, circle=circle)
    if not peer:
        raise HTTPException(status_code=404, detail=f"Peer not found: {name}")
    ok = await peer_registry.update_peer_display_name(peer.peer_id, request.display_name)
    if not ok:
        raise HTTPException(status_code=409, detail="Name conflict with active peer")
    return OkResponse()
```

`update_peer_display_name` returns `False` if a conflicting ONLINE/BUSY peer exists with the target name. Map this to a `409 Conflict`.

### 4. `set_display_name` MCP Tool in `server.ts`

**Tool definition:**
```ts
{
  name: "set_display_name",
  description: "Update your display name in the repowire mesh. Visible to other peers via list_peers.",
  inputSchema: {
    type: "object",
    properties: {
      display_name: { type: "string", description: "New display name" }
    },
    required: ["display_name"],
  },
}
```

**Handler:** Calls `POST /peers/{sessionId}/rename` via HTTP. Uses `sessionId` (the peer_id returned in the "connected" message) — no name lookup needed.

```ts
const httpUrl = DAEMON_URL.replace("ws://", "http://").replace("wss://", "https://");
const resp = await fetch(`${httpUrl}/peers/${sessionId}/rename`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ display_name }),
});
if (!resp.ok) throw new Error(`Rename failed: ${await resp.text()}`);
displayName = display_name;  // Update mutable local copy
return { content: [{ type: "text", text: `Display name updated to: ${display_name}` }] };
```

Since `DISPLAY_NAME` is used in the permission relay handler (`from_peer: DISPLAY_NAME`), it needs to remain mutable after a rename. Change `const DISPLAY_NAME` to `let displayName` (local convention: lowercase to indicate mutability).

### 5. `set_display_name` MCP Tool in `mcp/server.py`

Added alongside the existing tools (`set_description`, `list_peers`, etc.).

```python
@mcp.tool()
async def set_display_name(display_name: str) -> str:
    """Update your display name in the repowire mesh.

    The new name is visible to other peers via list_peers immediately.

    Args:
        display_name: New display name (e.g., "frontend", "api-worker")

    Returns:
        Confirmation message
    """
    name = await _get_my_peer_name()
    await daemon_request("POST", f"/peers/{name}/rename", {"display_name": display_name})
    global _cached_peer_name
    _cached_peer_name = display_name  # Keep cache in sync
    return f"display name updated: {display_name}"
```

### 6. Validation: `display_name` field in rename endpoint

The `RegisterPeerRequest.name` already has `pattern=r"^[a-zA-Z0-9._-]+"`. The rename endpoint should use the same validation. Add it to `RenameRequest.display_name`:

```python
display_name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
```

This keeps display names consistent with existing peer name constraints.

## Data Flow

### Display Name Resolution (startup)

```
.repowire.yaml exists?
    yes → use display_name field (if set)
    no  → skip
CLAUDE_SESSION_ID set?
    yes → use first 8 chars
    no  → skip
→ use folder name from cwd (e.g., "my-frontend")
```

### Rename via MCP Tool (channel transport)

```
Claude calls set_display_name("frontend")
    → server.ts: POST /peers/{sessionId}/rename {"display_name": "frontend"}
    → daemon: get_peer(sessionId) → update_peer_display_name(peer_id, "frontend")
    → peer.display_name updated in-place, mapping synced
    → server.ts: updates local displayName variable
    → other peers: see "frontend" in list_peers
```

## Files Changed

| File | Change |
|------|--------|
| `repowire/channel/server.ts` | Add `loadProjectConfig()`, update `DISPLAY_NAME`/`CIRCLE` resolution, add `set_display_name` tool, change `DISPLAY_NAME` to mutable `displayName` |
| `repowire/daemon/routes/peers.py` | Add `POST /peers/{name}/rename` endpoint |
| `repowire/mcp/server.py` | Add `set_display_name` tool |
| `tests/test_routes.py` | Add rename endpoint tests |

## Scope Boundaries

**In scope:**
- Display name fallback chain in `server.ts`
- `.repowire.yaml` per-project config (`display_name`, `circle`)
- `POST /peers/{name}/rename` HTTP endpoint
- `set_display_name` MCP tool in both `server.ts` and `mcp/server.py`

**Out of scope:**
- Daemon core changes (`peer_registry.py` already has `update_peer_display_name`)
- Global `~/.repowire/config.yaml` changes
- VS Code end-to-end verification (slice 103)
- Rename broadcast/event (peers will see the new name on their next `list_peers`)

## Success Criteria

- Without any config, a VS Code channel peer is named after its project folder (not `"channel"`)
- `.repowire.yaml` with `circle: myteam` and/or `display_name: frontend` is honored at startup
- Absence of `.repowire.yaml` has no effect — sensible defaults apply
- `set_display_name` tool updates the daemon and is immediately reflected in `list_peers`
- Rename returns 409 when an ONLINE/BUSY peer already holds the target name
- `ruff check repowire/` passes
- Full test suite passes (236+ tests from slice 101)
- New tests: rename endpoint (success, conflict, not-found)
