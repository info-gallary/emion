/* ═══════════════════════════════════════════
   EmION Dashboard JS — Real ION-DTN Frontend
   ═══════════════════════════════════════════ */

const API = '';
let ws = null;
let nodeList = [];    // [{node_id, is_running, peers, ...}]
let linkList = [];    // [{from, to}]
let canvas, ctx;
let sentCount = 0, recvCount = 0;
let animBundles = [];

// ── Init ─────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    canvas = document.getElementById('topology-canvas');
    ctx = canvas.getContext('2d');
    resize();
    window.addEventListener('resize', resize);

    document.getElementById('btn-add-node').addEventListener('click', addNode);
    document.getElementById('btn-start').addEventListener('click', startNetwork);
    document.getElementById('btn-stop').addEventListener('click', stopNetwork);
    document.getElementById('btn-send').addEventListener('click', sendBundle);
    document.getElementById('btn-recv').addEventListener('click', recvBundle);
    document.getElementById('btn-connect-mod').addEventListener('click', connectModule);

    connectWS();
    refresh();
    setInterval(refresh, 4000);
    requestAnimationFrame(draw);
});

// ── WebSocket ────────────────────────────

function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onopen = () => {
        document.getElementById('ws-status').textContent = '● Live';
        document.getElementById('ws-status').className = 'status-badge live';
    };
    ws.onclose = () => {
        document.getElementById('ws-status').textContent = '⚠ Disconnected';
        document.getElementById('ws-status').className = 'status-badge off';
        setTimeout(connectWS, 3000);
    };
    ws.onmessage = e => onEvent(JSON.parse(e.data));
}

function onEvent(evt) {
    if (evt.type === 'bundle_sent') {
        sentCount++;
        log('tx', `${evt.src} → ${evt.dst} (${evt.size}B)`);
        animateBundle(evt.from, evt.to);
        if (evt.modules) {
            Object.entries(evt.modules).forEach(([n, r]) => addModuleResult(n, r));
        }
    } else if (evt.type === 'bundle_received') {
        recvCount++;
        log('rx', `Received ${evt.size}B on ${evt.eid}: ${evt.payload}`);
    } else if (evt.type === 'telemetry_update') {
        updateTelemetry(evt.data);
    } else if (evt.type === 'network_started') {
        log('sys', `ION network started: nodes ${evt.nodes.join(', ')}`);
        refresh();
    } else if (evt.type === 'network_stopped') {
        log('sys', 'ION network stopped');
        refresh();
    } else if (evt.type === 'module_connected') {
        log('mod', `Module connected: ${evt.name}`);
        refreshModules();
    }
}

// ── API ──────────────────────────────────

async function api(method, path) {
    const res = await fetch(`${API}${path}`, { method });
    return res.json();
}

async function addNode() {
    const id = parseInt(document.getElementById('input-node-id').value);
    if (!id) return;
    const r = await api('POST', `/api/nodes?node_id=${id}`);
    if (r.error) { log('err', r.error); return; }
    log('sys', `Node ${id} registered`);
    document.getElementById('input-node-id').value = '';
    refresh();
}

async function startNetwork() {
    log('sys', 'Starting ION network...');
    const r = await api('POST', '/api/start');
    if (r.error) { log('err', r.error); return; }
    log('sys', 'Network started');
    refresh();
}

async function stopNetwork() {
    await api('POST', '/api/stop');
    refresh();
}

async function sendBundle() {
    const src = parseInt(document.getElementById('input-src').value);
    const dst = parseInt(document.getElementById('input-dst').value);
    const payload = document.getElementById('input-payload').value || 'EMION_TEST';
    if (!src || !dst) return;
    const r = await api('POST', `/api/send?from_node=${src}&to_node=${dst}&payload=${encodeURIComponent(payload)}`);
    if (r.error) log('err', r.error);
}

async function recvBundle() {
    const nid = parseInt(document.getElementById('input-recv-node').value);
    if (!nid) return;
    log('sys', `Listening on Node ${nid}...`);
    const r = await api('POST', `/api/receive?node_id=${nid}&timeout=10`);
    if (r.error) log('err', r.error);
    else if (r.status === 'timeout') log('sys', `Timeout on Node ${nid}`);
}

async function connectModule() {
    const url = document.getElementById('input-mod-url').value;
    const targets = document.getElementById('input-mod-targets').value || 'all';
    if (!url) return;
    const r = await api('POST', `/api/modules/connect?url=${encodeURIComponent(url)}&target_nodes=${encodeURIComponent(targets)}`);
    if (r.error) log('err', r.error);
    else { log('mod', `Connected: ${r.name} (Monitoring: ${targets})`); refreshModules(); }
    document.getElementById('input-mod-url').value = '';
    document.getElementById('input-mod-targets').value = '';
}

// ── Refresh ──────────────────────────────

async function refresh() {
    nodeList = await api('GET', '/api/nodes');
    linkList = await api('GET', '/api/links');
    updateChips();
    updateStats();
}

async function refreshModules() {
    const mods = await api('GET', '/api/modules');
    document.getElementById('module-list').innerHTML =
        mods.map(m => `<span class="plugin-chip">${m.name}</span>`).join('');
}

function updateChips() {
    document.getElementById('node-chips').innerHTML = nodeList.map(n =>
        `<span class="chip ${n.is_running ? 'running' : ''}">` +
        `<span class="dot"></span>N${n.node_id} (${n.is_running ? 'LIVE' : 'idle'})` +
        `</span>`
    ).join('');
}

function updateStats() {
    document.getElementById('s-nodes').textContent = nodeList.length;
    document.getElementById('s-links').textContent = linkList.length;
    document.getElementById('s-sent').textContent = sentCount;
    document.getElementById('s-recv').textContent = recvCount;
}

function updateTelemetry(data) {
    const el = document.getElementById('telemetry-panels');
    el.innerHTML = data.map(nodeTel => {
        if (!nodeTel || !nodeTel.sdr) return '';
        return `
            <div class="tel-item">
                <span class="tel-label">N${nodeTel.node_id} SDR Memory</span>
                <span class="tel-val">${nodeTel.sdr.wmSize || '?'} Bytes</span>
            </div>
            <div class="tel-item" style="border-top:none; border-radius:0 0 8px 8px; margin-top:-2px; background:#f8fafc">
                 <span class="tel-label">SDR Key</span>
                 <span class="tel-val">${nodeTel.sdr.wmKey || '?'}</span>
            </div>
        `;
    }).join('');
}

// ── Event Log ────────────────────────────

function log(tag, msg) {
    const el = document.getElementById('event-log');
    const d = document.createElement('div');
    d.className = 'event-entry';
    d.innerHTML = `<span class="event-tag tag-${tag}">${tag}</span><span class="event-msg">${msg}</span>`;
    el.prepend(d);
    if (el.children.length > 150) el.lastChild.remove();
}

function addModuleResult(name, result) {
    const el = document.getElementById('module-results');
    const d = document.createElement('div');
    d.className = `anom-entry ${result.is_anomaly ? 'bad' : ''}`;
    d.innerHTML = `<b>${name}</b>: ${result.is_anomaly ? '⚠ ANOMALY' : '✓ OK'} ` +
        `(score: ${result.score || '?'}) <span style="color:var(--text-3)">${JSON.stringify(result.details||{})}</span>`;
    el.prepend(d);
    if (el.children.length > 30) el.lastChild.remove();
}

// ── Topology Canvas ──────────────────────

function resize() {
    if (!canvas) return;
    canvas.width = canvas.parentElement.clientWidth - 40;
    canvas.height = 420;
}

function draw() {
    if (!ctx) { requestAnimationFrame(draw); return; }
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // Grid - subtle light theme
    ctx.strokeStyle = '#f1f5f9'; ctx.lineWidth = 1;
    for (let x = 0; x < W; x += 60) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = 0; y < H; y += 60) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }

    // Position nodes - interactive area
    const positions = {};
    const n = nodeList.length || 1;
    const cx = W / 2, cy = H / 2, r = Math.min(cx, cy) * 0.6;
    nodeList.forEach((nd, i) => {
        const a = (i / n) * Math.PI * 2 - Math.PI / 2;
        positions[nd.node_id] = { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a), ...nd };
    });

    // Draw links
    linkList.forEach(l => {
        const a = positions[l.from], b = positions[l.to];
        if (!a || !b) return;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = '#cbd5e1'; ctx.lineWidth = 3; ctx.stroke();
        
        // Label on link
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        ctx.fillStyle = '#94a3b8'; ctx.font = '700 10px Inter'; ctx.textAlign = 'center';
        ctx.fillText('IPN/UDP', mx, my - 8);
    });

    // Animate bundles (Light theme colors)
    animBundles = animBundles.filter(b => {
        b.p += 0.012;
        if (b.p > 1) return false;
        const a = positions[b.from], bn = positions[b.to];
        if (!a || !bn) return false;
        const x = a.x + (bn.x - a.x) * b.p;
        const y = a.y + (bn.y - a.y) * b.p;
        
        ctx.fillStyle = '#3b82f6'; ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();
        return true;
    });

    // Draw nodes
    Object.values(positions).forEach(nd => {
        // Shadow/Glow
        ctx.shadowBlur = 10; ctx.shadowColor = 'rgba(0,0,0,0.05)';
        ctx.beginPath(); ctx.arc(nd.x, nd.y, 28, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff'; ctx.fill();
        ctx.shadowBlur = 0;
        
        ctx.strokeStyle = nd.is_running ? '#22c55e' : '#e2e8f0'; ctx.lineWidth = 3; ctx.stroke();
        
        // Icon/Label
        ctx.fillStyle = '#0f172a'; ctx.font = '700 14px Inter'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(`N${nd.node_id}`, nd.x, nd.y);
        
        // IPN tag
        ctx.fillStyle = '#64748b'; ctx.font = '600 9px JetBrains Mono';
        ctx.fillText(`ipn:${nd.node_id}`, nd.x, nd.y + 40);
    });

    // Empty state
    if (nodeList.length === 0) {
        ctx.fillStyle = '#94a3b8'; ctx.font = '500 16px Inter'; ctx.textAlign = 'center';
        ctx.fillText('Orchestrate nodes to begin mission simulation', W / 2, H / 2);
    }

    requestAnimationFrame(draw);
}

function animateBundle(from, to) {
    animBundles.push({ from, to, p: 0 });
}
