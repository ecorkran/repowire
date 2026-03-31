---
docType: tasks
slice: peer-identity-and-per-project-config
project: repowire
lld: project-documents/user/slices/102-slice.peer-identity-and-per-project-config.md
dependencies: [100, 101]
projectState: Slices 100 and 101 complete; channel peers have correct liveness and pong circle; display name still falls back to "channel"
dateCreated: 20260331
dateUpdated: 20260331
status: complete
---

## Context Summary

- Slice 102: Peer Identity and Per-Project Config
- Channel peers currently display as `CLAUDE_SESSION_ID[:8]` or `"channel"` — neither is useful
- Fix: fallback chain `display_name` from `.repowire.yaml` → `CLAUDE_SESSION_ID[:8]` → folder name from cwd
- Also add `.repowire.yaml` `circle` field support (env var takes precedence)
- Expose existing `update_peer_display_name` daemon method via new HTTP endpoint + MCP tool
- `const DISPLAY_NAME` → `let displayName` so `set_display_name` tool can update in-place
- No daemon core changes needed

## Tasks

### Task 1: Create slice branch

- [x] **Create branch `102-peer-identity-and-per-project-config` from main**
  - [x] Verify on main: `git branch --show-current`
  - [x] Create branch: `git checkout -b 102-peer-identity-and-per-project-config`
  - [x] Confirm all existing tests pass: `uv run pytest tests/`

**Commit:** `chore: create branch for slice 102 peer identity and per-project config`

### Task 2: Update display name resolution in `channel/server.ts`

- [x] **Add `loadProjectConfig()` and update `DISPLAY_NAME`/`CIRCLE` constants**

  - [x] Add `loadProjectConfig()` function (before the `// -- Config --` section or inline):
    ```ts
    async function loadProjectConfig(): Promise<{ circle?: string; display_name?: string }> {
      try {
        const text = await Bun.file(`${process.cwd()}/.repowire.yaml`).text();
        const result: { circle?: string; display_name?: string } = {};
        for (const line of text.split("\n")) {
          const m = line.match(/^\s*(circle|display_name)\s*:\s*(.+?)\s*$/);
          if (m) result[m[1] as "circle" | "display_name"] = m[2].replace(/^["']|["']$/g, "");
        }
        return result;
      } catch {
        return {};
      }
    }
    ```
  - [x] Add top-level await call near other startup awaits:
    ```ts
    const projectConfig = await loadProjectConfig();
    ```
  - [x] Replace the `DISPLAY_NAME` constant (lines 24-25) with:
    ```ts
    const _sessionPrefix = (process.env.CLAUDE_SESSION_ID ?? "").slice(0, 8);
    const _folderName = process.cwd().split("/").pop() || "repowire";
    let displayName = projectConfig.display_name || _sessionPrefix || _folderName;
    ```
  - [x] Replace the `CIRCLE` constant (line 26) with:
    ```ts
    const CIRCLE = process.env.REPOWIRE_CIRCLE || projectConfig.circle || "default";
    ```
  - [x] Update all references to `DISPLAY_NAME` → `displayName` throughout the file:
    - `connectDaemon`: `display_name: DISPLAY_NAME` → `display_name: displayName`
    - `fetchPeerContext`: `.filter((p) => p.display_name !== DISPLAY_NAME)` → `!== displayName`
    - Permission relay handler: `from_peer: DISPLAY_NAME` → `from_peer: displayName`
  - [x] Verify `PROJECT_PATH` is no longer needed for DISPLAY_NAME (it's used elsewhere in connect — keep it)

  > **Note on test coverage:** `loadProjectConfig()` and the `displayName` fallback chain are TypeScript/Bun code. No Bun test framework exists in this project; these code paths have no automated tests here. The fallback chain (folder name, config file parsing) will be verified manually during slice 103's end-to-end pass. The rename endpoint (Task 6) exercises the daemon side of the name update.

**Commit:** `feat: update display name fallback chain and add .repowire.yaml config support`

### Task 3: Add `POST /peers/{name}/rename` endpoint to `daemon/routes/peers.py`

- [x] **Add `RenameRequest` model and rename endpoint after `set_peer_description` endpoint**

  - [x] Add request model:
    ```python
    class RenameRequest(BaseModel):
        """Request to rename a peer's display name."""
        display_name: str = Field(
            ..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$",
            description="New display name"
        )
    ```
  - [x] Add endpoint:
    ```python
    @router.post("/peers/{name}/rename", response_model=OkResponse)
    async def rename_peer(
        name: str,
        request: RenameRequest,
        circle: str | None = Query(None),
        _: str | None = Depends(require_auth),
    ) -> OkResponse:
        """Rename a peer's display name in-place."""
        peer_registry = get_peer_registry()
        peer = await peer_registry.get_peer(name, circle=circle)
        if not peer:
            raise HTTPException(status_code=404, detail=f"Peer not found: {name}")
        ok = await peer_registry.update_peer_display_name(peer.peer_id, request.display_name)
        if not ok:
            raise HTTPException(status_code=409, detail="Name conflict with active peer")
        return OkResponse()
    ```

**Commit:** `feat: add POST /peers/{name}/rename endpoint for display name updates`

### Task 4: Add `set_display_name` MCP tool in `repowire/mcp/server.py`

- [x] **Add tool after `set_description` tool**

  - [x] Add `set_display_name` tool:
    ```python
    @mcp.tool()
    async def set_display_name(display_name: str) -> str:
        """Update your display name in the repowire mesh.

        The new name is visible to other peers via list_peers immediately.
        Also updates whoami and ask_peer routing for subsequent calls.

        Args:
            display_name: New display name (e.g., "frontend", "api-worker")

        Returns:
            Confirmation message
        """
        name = await _get_my_peer_name()
        await daemon_request("POST", f"/peers/{name}/rename", {"display_name": display_name})
        global _cached_peer_name
        _cached_peer_name = display_name
        return f"display name updated: {display_name}"
    ```

**Commit:** `feat: add set_display_name MCP tool to mcp/server.py`

### Task 5: Add `set_display_name` tool to `channel/server.ts`

- [x] **Add tool definition and handler alongside `reply` tool**

  - [x] Add `set_display_name` to the `tools` array in `ListToolsRequestSchema` handler:
    ```ts
    {
      name: "set_display_name",
      description: "Update your display name in the repowire mesh. Visible to other peers via list_peers.",
      inputSchema: {
        type: "object" as const,
        properties: {
          display_name: {
            type: "string",
            description: "New display name (e.g., 'frontend', 'api-worker')",
          },
        },
        required: ["display_name"],
      },
    },
    ```
  - [x] Add schema and handler in `CallToolRequestSchema` handler:
    ```ts
    const SetDisplayNameArgs = z.object({ display_name: z.string().min(1) });

    // Inside the request handler:
    if (req.params.name === "set_display_name") {
      const { display_name } = SetDisplayNameArgs.parse(req.params.arguments);
      if (!sessionId) {
        return { content: [{ type: "text" as const, text: "Error: not connected to daemon." }] };
      }
      const httpUrl = DAEMON_URL.replace("ws://", "http://").replace("wss://", "https://");
      const resp = await fetch(`${httpUrl}/peers/${sessionId}/rename`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name }),
      });
      if (!resp.ok) {
        return { content: [{ type: "text" as const, text: `Error: ${await resp.text()}` }] };
      }
      displayName = display_name;
      return { content: [{ type: "text" as const, text: `Display name updated to: ${display_name}` }] };
    }
    ```

**Commit:** `feat: add set_display_name MCP tool to channel/server.ts`

### Task 6: Add tests for rename endpoint

- [x] **Add `TestRenameEndpoint` class to `tests/test_routes.py`**

  - [x] `test_rename_peer_success`:
    - Register a peer named `"agent1"`
    - `POST /peers/agent1/rename` with `{"display_name": "frontend"}`
    - Assert 200 OK
    - `GET /peers/frontend` returns peer with `display_name == "frontend"`
    - `GET /peers/agent1` returns 404

  - [x] `test_rename_peer_not_found`:
    - `POST /peers/nonexistent/rename` with `{"display_name": "frontend"}`
    - Assert 404

  - [x] `test_rename_peer_conflict`:
    - Register two peers: `"agent1"` and `"agent2"`
    - `POST /peers/agent1/rename` with `{"display_name": "agent2"}`
    - Assert 409

  - [x] `test_rename_peer_invalid_name`:
    - Register `"agent1"`
    - `POST /peers/agent1/rename` with `{"display_name": "bad name!"}` (spaces/special chars)
    - Assert 422 (validation error)

  - [x] `test_rename_peer_reflected_in_list_peers`:
    - Register `"agent1"`
    - `POST /peers/agent1/rename` with `{"display_name": "frontend"}`
    - `GET /peers` — assert `"frontend"` appears in the returned peer list, `"agent1"` does not

  - [x] Run: `uv run pytest tests/test_routes.py -v -k rename`

**Commit:** `test: add rename endpoint tests`

### Task 7: Full regression suite

- [x] **Verify all tests pass with no regressions**
  - [x] Run: `uv run pytest tests/ -v`
  - [x] All 236+ tests pass
  - [x] Run: `uv run ruff check repowire/`
  - [x] No lint errors

### Task 8: Update slice status

- [x] **Mark slice 102 as complete in project documents**
  - [x] Update `status: complete` in `project-documents/user/slices/102-slice.peer-identity-and-per-project-config.md` frontmatter
  - [x] Update `dateUpdated` to today
  - [x] Check off slice 102 in `project-documents/user/architecture/100-slices.vscode-channel-fixes.md`

**Commit:** `docs: mark slice 102 peer identity and per-project config complete`
