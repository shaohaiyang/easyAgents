# EasyAgents Phase 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Add web UI as static HTML/CSS/JS served by FastAPI.

**Architecture:** Vanilla JS SPA with 4 tabs, fetch calls to Phase 4 REST API. No build step, no new dependencies.

## Global Constraints

- Python >= 3.11, existing dependencies only
- Use `.venv/bin/python` and `.venv/bin/python -m pytest`
- Backward compatible: existing 125 tests must pass
- No new dependencies

---

### Task 1: Web UI + Static File Serving

**Files:**
- Create: `src/easyagents/web/__init__.py`
- Create: `src/easyagents/web/static/index.html`
- Create: `src/easyagents/web/static/style.css`
- Create: `src/easyagents/web/static/app.js`
- Modify: `src/easyagents/api/app.py`
- Create: `tests/test_web.py`

- [ ] **Step 1: Write the failing test**

File `tests/test_web.py`:

```python
from fastapi.testclient import TestClient
from easyagents.api.app import app

client = TestClient(app)


def test_root_redirects_to_web():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)


def test_web_index_html():
    response = client.get("/web/index.html")
    assert response.status_code == 200
    assert "EasyAgents" in response.text


def test_web_static_files():
    response = client.get("/web/style.css")
    assert response.status_code == 200
    response = client.get("/web/app.js")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_web.py -v
```

Expected: FAIL

- [ ] **Step 3: Create web package**

```bash
mkdir -p src/easyagents/web/static
touch src/easyagents/web/__init__.py
```

- [ ] **Step 4: Write index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EasyAgents Workbench</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header>
        <h1>EasyAgents Workbench</h1>
    </header>
    <nav>
        <button class="tab-btn active" data-tab="agents">Agents</button>
        <button class="tab-btn" data-tab="sessions">Sessions</button>
        <button class="tab-btn" data-tab="patterns">Patterns</button>
        <button class="tab-btn" data-tab="approvals">Approvals</button>
    </nav>
    <main>
        <div id="agents" class="tab-content active">
            <h2>Registered Agents</h2>
            <table id="agents-table"><thead><tr><th>Name</th><th>Model</th><th>Description</th></tr></thead><tbody></tbody></table>
            <h3>Register New Agent</h3>
            <form id="agent-form">
                <input name="name" placeholder="Agent name" required>
                <input name="instructions" placeholder="Instructions" required>
                <input name="model" placeholder="Model" value="test">
                <input name="description" placeholder="Description">
                <button type="submit">Register</button>
            </form>
        </div>
        <div id="sessions" class="tab-content">
            <div class="split">
                <div class="sidebar">
                    <h2>Sessions</h2>
                    <button id="new-session">New Session</button>
                    <ul id="session-list"></ul>
                </div>
                <div class="chat-area">
                    <div id="messages"></div>
                    <form id="chat-form">
                        <input name="agent" placeholder="Agent name" required>
                        <input name="prompt" placeholder="Message" required>
                        <button type="submit">Run</button>
                    </form>
                </div>
            </div>
        </div>
        <div id="patterns" class="tab-content">
            <h2>Orchestrate</h2>
            <form id="orchestrate-form">
                <input name="task" placeholder="Task" required>
                <button type="submit">Orchestrate</button>
            </form>
            <div id="orchestrate-result"></div>
            <h2>Route</h2>
            <form id="route-form">
                <input name="user_input" placeholder="Query" required>
                <button type="submit">Route</button>
            </form>
            <div id="route-result"></div>
            <h2>Handoff</h2>
            <form id="handoff-form">
                <input name="agents" placeholder="agent1,agent2" required>
                <input name="user_input" placeholder="Input" required>
                <button type="submit">Run Handoff</button>
            </form>
            <div id="handoff-result"></div>
        </div>
        <div id="approvals" class="tab-content">
            <h2>Pending Approvals</h2>
            <div id="approval-list"><p>No pending approvals.</p></div>
        </div>
    </main>
    <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 5: Write style.css**

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: system-ui, sans-serif; background: #f5f5f5; color: #333; }
header { background: #2563eb; color: white; padding: 1rem 2rem; }
header h1 { font-size: 1.25rem; }
nav { display: flex; gap: 0; background: white; border-bottom: 2px solid #e5e7eb; padding: 0 2rem; }
.tab-btn { padding: 0.75rem 1.5rem; border: none; background: none; cursor: pointer; font-size: 0.9rem; color: #666; border-bottom: 3px solid transparent; }
.tab-btn.active { color: #2563eb; border-bottom-color: #2563eb; }
.tab-btn:hover { color: #2563eb; }
main { padding: 2rem; max-width: 1200px; margin: 0 auto; }
.tab-content { display: none; }
.tab-content.active { display: block; }
h2 { margin-bottom: 1rem; color: #1f2937; }
h3 { margin: 1.5rem 0 0.5rem; color: #374151; }
table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #e5e7eb; }
th { background: #f9fafb; font-weight: 600; }
form { display: flex; gap: 0.5rem; margin: 1rem 0; flex-wrap: wrap; }
input { padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; }
input:focus { outline: none; border-color: #2563eb; }
button { padding: 0.5rem 1rem; background: #2563eb; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
button:hover { background: #1d4ed8; }
.split { display: flex; gap: 2rem; }
.sidebar { width: 250px; }
.chat-area { flex: 1; }
#messages { min-height: 300px; background: white; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
#session-list { list-style: none; }
#session-list li { padding: 0.5rem; cursor: pointer; border-radius: 4px; }
#session-list li:hover { background: #e5e7eb; }
#session-list li.active { background: #dbeafe; }
.result-box { background: white; padding: 1rem; border-radius: 8px; margin-top: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); white-space: pre-wrap; }
.approval-item { background: white; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.approval-item button { margin-right: 0.5rem; }
.btn-approve { background: #16a34a; }
.btn-reject { background: #dc2626; }
```

- [ ] **Step 6: Write app.js**

```javascript
const API = '/api';

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
    });
});

async function fetchJSON(url, opts) {
    const res = await fetch(url, opts);
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return res.json();
}

// Agents
async function loadAgents() {
    try {
        const data = await fetchJSON(`${API}/agents`);
        const tbody = document.querySelector('#agents-table tbody');
        tbody.innerHTML = (data.agents || []).map(a => `<tr><td>${a}</td><td>-</td><td>-</td></tr>`).join('');
    } catch (e) { console.error(e); }
}
document.getElementById('agent-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd);
    try {
        await fetchJSON(`${API}/agents`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        e.target.reset();
        loadAgents();
    } catch (e) { alert(e.message); }
});

// Sessions
async function loadSessions() {
    try {
        const data = await fetchJSON(`${API}/sessions`);
        const list = document.getElementById('session-list');
        list.innerHTML = (data.sessions || []).map(id => `<li data-id="${id}">${id.slice(0,8)}...</li>`).join('');
        list.querySelectorAll('li').forEach(li => {
            li.addEventListener('click', () => selectSession(li.dataset.id));
        });
    } catch (e) { console.error(e); }
}
document.getElementById('new-session').addEventListener('click', async () => {
    try {
        const data = await fetchJSON(`${API}/sessions`, { method: 'POST' });
        loadSessions();
    } catch (e) { alert(e.message); }
});
let currentSession = null;
function selectSession(id) {
    currentSession = id;
    document.querySelectorAll('#session-list li').forEach(li => li.classList.toggle('active', li.dataset.id === id));
    loadMessages(id);
}
async function loadMessages(id) {
    try {
        const data = await fetchJSON(`${API}/sessions/${id}`);
        document.getElementById('messages').innerHTML = `<p>Session: ${id.slice(0,8)}... | Messages: ${data.message_count}</p>`;
    } catch (e) { console.error(e); }
}
document.getElementById('chat-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentSession) { alert('Select a session first'); return; }
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd);
    try {
        const data = await fetchJSON(`${API}/sessions/${currentSession}/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        document.getElementById('messages').innerHTML += `<div class="result-box">Output: ${data.output || 'N/A'}</div>`;
    } catch (e) { alert(e.message); }
});

// Patterns
document.getElementById('orchestrate-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = { task: fd.get('task'), params: {}, model: 'test' };
    try {
        const data = await fetchJSON(`${API}/patterns/orchestrate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        document.getElementById('orchestrate-result').innerHTML = `<div class="result-box">${JSON.stringify(data, null, 2)}</div>`;
    } catch (e) { document.getElementById('orchestrate-result').innerHTML = `<div class="result-box">Error: ${e.message}</div>`; }
});
document.getElementById('route-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = { user_input: fd.get('user_input'), model: 'test' };
    try {
        const data = await fetchJSON(`${API}/patterns/route`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        document.getElementById('route-result').innerHTML = `<div class="result-box">Routed to: ${data.agent || 'N/A'}</div>`;
    } catch (e) { document.getElementById('route-result').innerHTML = `<div class="result-box">Error: ${e.message}</div>`; }
});
document.getElementById('handoff-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = { agents: fd.get('agents').split(','), user_input: fd.get('user_input'), model: 'test' };
    try {
        const data = await fetchJSON(`${API}/patterns/handoff`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        document.getElementById('handoff-result').innerHTML = `<div class="result-box">${JSON.stringify(data, null, 2)}</div>`;
    } catch (e) { document.getElementById('handoff-result').innerHTML = `<div class="result-box">Error: ${e.message}</div>`; }
});

// Approvals
async function loadApprovals() {
    document.getElementById('approval-list').innerHTML = '<p>No pending approvals.</p>';
}

// Init
loadAgents();
loadSessions();
loadApprovals();
```

- [ ] **Step 7: Modify api/app.py to serve static files**

Add to `src/easyagents/api/app.py`:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os

# After all router includes, add:
web_dir = os.path.join(os.path.dirname(__file__), "..", "web", "static")
app.mount("/web", StaticFiles(directory=web_dir), name="web")

@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/web/index.html")
```

- [ ] **Step 8: Run tests**

```bash
.venv/bin/python -m pytest tests/test_web.py -v
.venv/bin/python -m pytest tests/ -v
```

Expected: 3 new + 125 existing = 128 passed

- [ ] **Step 9: Commit**

```bash
git add src/easyagents/web/ src/easyagents/api/app.py tests/test_web.py
git commit -m "feat: Phase 5 Web UI - static HTML/CSS/JS with 4 tabs served by FastAPI"
```
