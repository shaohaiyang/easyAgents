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
