---
docType: review
layer: project
reviewType: slice
slice: hook-cleanup-and-ghost-eviction-fix
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/100-slice.hook-cleanup-and-ghost-eviction-fix.md
aiModel: claude-opus-4-6
status: complete
dateCreated: 20260326
dateUpdated: 20260326
---

# Review: slice — slice 100

**Verdict:** PASS
**Model:** claude-opus-4-6

## Findings

### [PASS] Alignment with Architecture Design Goals

The slice directly addresses the first design goal in the architecture document: "Fix duplicate peer registration when both legacy hooks and channel transport register for the same session, caused by circle mismatch in ghost eviction." The two-pronged approach (installer cleanup + eviction fix) maps cleanly to the architecture's identified problem #1 (Duplicate registration) and the anticipated slice "Hook cleanup and ghost eviction fix — Ensure channel mode removes stale hooks; fix ghost eviction to deduplicate across circles. Foundation work."

### [PASS] Correct Files and Layer Boundaries

All three changes target the files identified in the architecture's "Related Work" section: `repowire/installers/claude_code.py` for hook cleanup, and `repowire/daemon/peer_registry.py` for ghost eviction and mapping lookup. No changes leak into the channel transport (`server.ts`), the MCP server, or any other layer — consistent with the architecture's "minimal, targeted changes" principle.

### [PASS] Tmux Path Preservation

The architecture's first principle is "Do not break the tmux path." The slice explicitly guards this: hook cleanup only triggers when `channel_mode=True`, `install_hooks(channel_mode=False)` is listed as a success criterion to remain unaffected, and the eviction change is strictly more permissive (removing a condition), which makes tmux-path eviction a subset of the new behavior. The success criteria also require all 222 existing tests to pass.

### [PASS] Cross-Slice Dependency Direction

The slice correctly identifies itself as a foundation slice with no upstream dependencies, and correctly states that slices 101 (Rich Pong) and 102 (Peer Identity) depend on it. This matches the architecture's anticipated slice ordering where hook cleanup/ghost eviction is listed first as "Foundation work." The `interfaces: [101, 102, 103]` frontmatter is consistent.

### [PASS] Scope Appropriateness

The slice stays within its defined scope — it does not attempt to fix pong responses (slice 101), display name derivation (slice 102), or per-project config (slice 102/103). The mapping lookup relaxation (Technical Decision #3) is a natural extension of the ghost eviction fix: without it, the eviction would remove the old peer but the stale mapping would cause a new session_id allocation, undermining the fix. This is well-justified rather than scope creep.

### [PASS] Idempotency and Safety Considerations

The architecture calls out "Hook cleanup must be idempotent." The slice addresses this explicitly: `dict.pop(event, None)` is a no-op on missing keys, and the success criteria include a test for running `install_hooks(channel_mode=True)` twice producing identical results. The justification for not calling `uninstall_hooks()` first (avoiding a window with no hooks) is sound.

### [PASS] Mapping Cleanup During Eviction

The slice identifies that evicting a ghost from `_peers` can leave a stale `_mappings` entry and includes cleanup code with `_mappings_dirty = True`. This attention to state consistency prevents a subtle bug the architecture document didn't explicitly call out but that falls naturally within the ghost eviction fix scope.
