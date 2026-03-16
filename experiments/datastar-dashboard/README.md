# Datastar Dashboard Experiment

**Date:** 2026-03-16
**Status:** Archived — replaced by React v1 dashboard
**Branch:** `feat/datastar-dashboard` (merged to main, then removed)

## What

Attempted to replace the React/Next.js dashboard with a Datastar-powered server-rendered dashboard. Datastar uses SSE to push HTML fragments from the server, morphing them into the DOM without client-side JS frameworks.

## What worked

- **Overview page** rendered instantly with server-side HTML — no JS bundle, no build step
- **Peer cards, sidebar, stats** all rendered correctly via Jinja2 templates
- **~400 lines of templates + ~200 lines Python** vs ~1200 lines of TSX + Next.js build pipeline
- **Eliminated Node.js from Dockerfile** (single-stage Python-only build)

## What didn't work

- **Cloudflare + SSE**: Cloudflare's HTTP/3 (QUIC) killed long-lived SSE connections. Fixed by disabling HTTP/3 via Terraform, but SSE responses from `@post` were still buffered/dropped.
- **Chat real-time updates**: The peer detail chat view needed live updates when new messages arrived. Server-rendering the entire chat HTML on every event is wasteful compared to React appending individual events via JSON.
- **Datastar `@post` response**: After sending a message via the compose bar, Datastar's `@post` successfully sent the request but didn't process the SSE response (`patch_signals` + `patch_elements`). Likely Cloudflare buffering the POST response body.

## Lessons

1. Datastar is excellent for server-rendered dashboards where data changes infrequently
2. Chat-style UIs with real-time updates need client-side state management
3. Cloudflare's proxy layer adds friction to SSE — headers like `X-Accel-Buffering: no`, `no-transform`, and disabling HTTP/3 help but don't fully solve POST response streaming
4. The hybrid approach (Datastar for overview, React for chat) would work but adds complexity

## Files

- `dashboard.py` — Jinja2 template rendering + SSE generator
- `templates/dashboard.html` — Base page with Datastar data-* attributes
- `templates/partials/sidebar.html` — Sidebar component
- `templates/partials/overview.html` — Overview with peer cards + activity
- `templates/partials/peer_detail.html` — Chat view with compose bar
