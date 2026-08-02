# EasyAgents Phase 5 - Web UI

> Date: 2026-07-30
>
> Status: Draft
>
> Depends on: Phase 4 - complete (125 tests passing)

## 1. Overview

Phase 5 adds a web UI frontend served as static files by the existing FastAPI backend. No new dependencies, no build step.

### 1.1 Design

- **Vanilla JS + fetch** - Calls Phase 4 REST API, no frontend framework
- **Single-page app** - Tab navigation, no router
- **Static files** - FastAPI serves HTML/CSS/JS via StaticFiles mount
- **4 tabs** - Agents, Sessions, Patterns, Approvals

### 1.2 Module Structure

```
easyagents/
├── web/
│   ├── __init__.py
│   └── static/
│       ├── index.html        # SPA shell with tab navigation
│       ├── style.css         # Modern minimal styling
│       └── app.js            # Frontend logic (fetch API calls)
├── api/
│   └── app.py                # MODIFY: mount StaticFiles at /web
```

### 1.3 Pages

1. **Agents** - Table of registered agents + registration form
2. **Sessions** - Session list + chat interface (input + message history)
3. **Patterns** - Three forms: Orchestrate, Handoff, Route
4. **Approvals** - Pending list with Approve/Reject buttons

### 1.4 API Integration

All frontend calls go to existing Phase 4 endpoints:
- `GET/POST /api/agents`
- `GET/POST /api/sessions`, `GET/DELETE /api/sessions/{id}`
- `POST /api/patterns/orchestrate|handoff|route`
- `GET/POST /api/approvals/{id}`

### 1.5 Dependencies

None. Pure static files.

### 1.6 Testing

3 tests verifying static file serving and redirect. No frontend JS testing.

### 1.7 Out of Scope

- Authentication
- WebSocket streaming
- Graph visualization
- Mobile responsive design (desktop-first)
- HTMX integration (future enhancement)
