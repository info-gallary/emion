/* ═══════════════════════════════════════════════════
   EmION Dashboard — Research Suite Controller
   v0.4 · ION-DTN Simulation · Per-Node ML Modules
   ═══════════════════════════════════════════════════ */

const API = '';
let ws = null;
let nodeList = [];
let linkList = [];
let canvas, ctx;
let targetPositions = {};
let currentPositions = {};
let animBundles = [];
let bundleHistory = [];
let scenarioTelemetry = null;
let simActive = false;
let moduleStatus = {};  // { nodeId: { modName: { status, score } } }

const hMax = 60;
let sdrData = [];
let flowData = [];

// ── Init ────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    canvas = document.getElementById('main-canvas');
    ctx = canvas.getContext('2d');

    // Sidebar & Telemetry toggles
    document.getElementById('btn-toggle-sidebar').addEventListener('click', () => {
        document.getElementById('workspace').classList.toggle('sidebar-collapsed');
        requestAnimationFrame(resize);
    });
    document.getElementById('btn-toggle-telemetry').addEventListener('click', () => {
        document.getElementById('workspace').classList.toggle('telemetry-collapsed');
        requestAnimationFrame(resize);
    });

    const ro = new ResizeObserver(() => requestAnimationFrame(resize));
    ro.observe(document.getElementById('canvas-wrapper'));

    // Node controls
    document.getElementById('btn-add-node').addEventListener('click', addNode);
    document.getElementById('btn-start').addEventListener('click', startNetwork);
    document.getElementById('btn-stop').addEventListener('click', stopNetwork);
    document.getElementById('btn-send').addEventListener('click', sendBundle);

    // Scenario
    document.getElementById('btn-sim-start').addEventListener('click', startScenario);
    document.getElementById('btn-sim-stop').addEventListener('click', stopScenario);
    document.getElementById('scenario-preset').addEventListener('change', loadScenario);

    // CFDP
    document.getElementById('btn-cfdp-send').addEventListener('click', sendCFDP);

    // Module management
    document.getElementById('btn-attach-mod').addEventListener('click', attachModule);

    // XML upload
    setupXMLUpload();

    // Timeline speed
    document.querySelectorAll('.tl-speed-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tl-speed-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });

    initCharts();
    connectWS();
    refresh();
    fetchScenarios();
    setInterval(refresh, 5000);
    requestAnimationFrame(draw);
});

// ── XML Upload ──────────────────────────────────

function setupXMLUpload() {
    const zone = document.getElementById('xml-drop-zone');
    const input = document.getElementById('xml-file-input');
    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', (e) => {
        e.preventDefault(); zone.classList.remove('drag-over');
        if (e.dataTransfer.files.length) uploadXML(e.dataTransfer.files[0]);
    });
    input.addEventListener('change', () => { if (input.files.length) uploadXML(input.files[0]); });
}

async function uploadXML(file) {
    log('sys', `Uploading XML: ${file.name}...`);
    const form = new FormData();
    form.append('file', file);
    try {
        const res = await fetch('/api/scenario/upload-xml', { method: 'POST', body: form });
        const data = await res.json();
        if (data.error) { log('err', data.error); return; }
        log('sys', `Parsed ${data.name}: ${data.events} events`);
        if (data.briefing) displayBriefing(data.briefing);
        fetchScenarios();
    } catch (e) { log('err', `Upload failed: ${e.message}`); }
}

// ── Briefing Display ────────────────────────────

function displayBriefing(briefing) {
    const card = document.getElementById('briefing-card');
    const content = document.getElementById('briefing-content');
    if (!briefing || !briefing.summary_lines) { card.style.display = 'none'; return; }
    card.style.display = 'block';
    content.innerHTML = briefing.summary_lines.map(line => {
        const isIndent = line.startsWith('  ');
        const isMovement = line.includes('moves') || line.includes('↗');
        let cls = 'briefing-line';
        if (isIndent) cls += ' indent';
        if (isMovement) cls += ' movement';
        return `<div class="${cls}">${line}</div>`;
    }).join('');
}

// ── Per-Node Module Management ──────────────────

async function attachModule() {
    const nodeId = parseInt(document.getElementById('mod-node-select').value);
    const modType = document.getElementById('mod-type-select').value;
    const url = document.getElementById('input-mod-url').value;
    if (!nodeId || !url) return;
    log('sys', `Attaching ${modType} module to N${nodeId}...`);
    try {
        const res = await fetch(`/api/nodes/${nodeId}/modules?url=${encodeURIComponent(url)}&module_type=${modType}`, { method: 'POST' });
        const data = await res.json();
        if (data.error) { log('err', data.error); return; }
        log('mod', `Attached: ${data.name} → N${nodeId}`);
        refreshModules();
    } catch (e) { log('err', `Attach failed: ${e.message}`); }
}

async function detachModule(nodeId, modName) {
    await fetch(`/api/nodes/${nodeId}/modules/${encodeURIComponent(modName)}`, { method: 'DELETE' });
    log('sys', `Detached ${modName} from N${nodeId}`);
    refreshModules();
}

async function refreshModules() {
    const mods = await api('GET', '/api/modules');
    const list = document.getElementById('module-list');
    list.innerHTML = mods.map(m => {
        const st = moduleStatus[m.node_id]?.[m.name] || {};
        const dotCls = st.status === 'anomaly' ? 'anomaly' : st.status === 'error' ? 'error' : 'normal';
        return `<div class="mod-attach-item">
            <span class="mod-attach-dot ${dotCls}"></span>
            <span class="mod-attach-name">N${m.node_id}: ${m.name}</span>
            <button class="mod-attach-del" onclick="detachModule(${m.node_id}, '${m.name}')">×</button>
        </div>`;
    }).join('');

    // Update module count
    const el = document.getElementById('ops-module-count');
    if (el) el.textContent = String(mods.length);
}

function updateModuleInsights(status) {
    moduleStatus = status || {};
    const card = document.getElementById('module-insights-card');
    const container = document.getElementById('module-insights');
    const entries = [];
    for (const [nid, mods] of Object.entries(moduleStatus)) {
        for (const [name, info] of Object.entries(mods)) {
            entries.push({ nid, name, ...info });
        }
    }
    if (entries.length === 0) { card.style.display = 'none'; return; }
    card.style.display = 'block';
    container.innerHTML = entries.map(e => {
        const scoreCls = e.status === 'anomaly' ? 'anomaly' : e.status === 'error' ? 'error' : 'normal';
        const scoreText = e.status === 'error' ? 'ERR' : (e.score * 100).toFixed(0) + '%';
        return `<div class="mod-insight-row">
            <span class="mod-insight-dot" style="background:${e.status === 'error' ? 'var(--danger)' : e.status === 'anomaly' ? 'var(--warn)' : 'var(--success)'}"></span>
            <span class="mod-insight-node">N${e.nid}</span>
            <span class="mod-insight-name">${e.name}</span>
            <span class="mod-insight-score ${scoreCls}">${scoreText}</span>
        </div>`;
    }).join('');
}

// ── Mode Detection ──────────────────────────────

function updateModeBadge() {
    const badge = document.getElementById('sim-mode-badge');
    const text = document.getElementById('badge-text');
    if (simActive) {
        text.textContent = 'SIMULATING';
        badge.className = 'mode-badge running';
    } else if (nodeList.some(n => n.is_running)) {
        text.textContent = 'CORE ACTIVE';
        badge.className = 'mode-badge running';
    } else {
        text.textContent = 'IDLE';
        badge.className = 'mode-badge idle';
    }
}

// ── Scenario UI ─────────────────────────────────

function updateScenarioUI(status) {
    const bar = document.querySelector('.progress-fill');
    const text = document.getElementById('sim-status-text');
    simActive = status.is_running;
    updateModeBadge();
    if (!status.is_running && status.executed_events === 0) {
        bar.style.width = '0%'; text.innerText = 'Ready'; return;
    }
    const p = status.total_events ? (status.executed_events / status.total_events) * 100 : 0;
    bar.style.width = `${p}%`;
    text.innerText = status.is_running ? `RUNNING ${p.toFixed(0)}%` : 'COMPLETE';
}

function fmt(v) { return (v === null || v === undefined || Number.isNaN(v)) ? '—' : `T+${Number(v).toFixed(1)}s`; }
function fmtAction(a) { return a ? a.replaceAll('_', ' ') : '—'; }

function updateScenarioTelemetry(t) {
    scenarioTelemetry = t || null;
    const patch = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    const phase = !t ? 'Idle' : t.is_running ? 'Simulating' : t.executed_events > 0 ? 'Complete' : 'Ready';
    const nextEvt = t?.next_event_action ? `${fmt(t.next_event_time)} ${fmtAction(t.next_event_action)}` : '—';
    patch('hud-scenario', t?.name || 'No scenario loaded');
    patch('hud-phase', `${phase} | ${t?.progress_pct || 0}%`);
    patch('intel-next-event', nextEvt);
    patch('intel-tracked-nodes', String(t?.tracked_node_count || 0));
    patch('intel-moving-count', String(t?.moving_node_count || 0));
    patch('intel-wlan-range', String(t?.wlan_range || 0));
    patch('intel-link-count', String(t?.active_link_count || 0));
    patch('intel-sched-count', String(t?.wired_link_count || 0));
    patch('intel-wlan-count', String(t?.wlan_link_count || 0));
    patch('tl-elapsed', fmt(t?.elapsed || 0));
    const scrubber = document.getElementById('tl-scrubber');
    if (t && t.total_events > 0 && t.is_running) scrubber.value = t.progress_pct || 0;
}

function updateOps() {
    const patch = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    patch('ops-node-count', String(nodeList.length));
    patch('ops-link-count', String(linkList.length));
    patch('ops-bundle-count', String(bundleHistory.length));
}

// ── WebSocket ───────────────────────────────────

function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onopen = () => {
        document.getElementById('ws-status').className = 'ws-dot live';
        document.getElementById('ws-label').textContent = 'Live';
    };
    ws.onclose = () => {
        document.getElementById('ws-status').className = 'ws-dot';
        document.getElementById('ws-label').textContent = 'Offline';
        setTimeout(connectWS, 3000);
    };
    ws.onmessage = e => onEvent(JSON.parse(e.data));
}

function onEvent(evt) {
    const now = new Date().toLocaleTimeString();
    if (evt.type === 'bundle_sent') {
        log('tx', `BPv7: ${evt.src} → ${evt.dst} (${evt.size}B)`);
        animateBundle(evt.from, evt.to);
        // Check module results for anomalies
        let status = 'OK';
        if (evt.modules) {
            for (const [key, result] of Object.entries(evt.modules)) {
                if (result.is_anomaly) { status = 'ANOMALY'; log('mod', `⚠ ${key}: anomaly score ${(result.score * 100).toFixed(0)}%`); }
            }
        }
        addToHistory({ time: now, src: evt.src, dst: evt.dst, size: evt.size, status });
        updateFlowChart(evt.size);
    } else if (evt.type === 'telemetry_update') {
        updateCharts(evt.data);
        if (evt.scenario) updateScenarioUI(evt.scenario);
        if (evt.scenario_telemetry) updateScenarioTelemetry(evt.scenario_telemetry);
        if (evt.scenario_links) linkList = evt.scenario_links;
        if (evt.node_positions) targetPositions = evt.node_positions;
        if (evt.module_status) updateModuleInsights(evt.module_status);
        if (evt.briefing) displayBriefing(evt.briefing);
        updateOps();
        updateModeBadge();
    } else if (evt.type === 'network_started') {
        log('sys', `Core Active: Nodes [${evt.nodes.join(', ')}]`);
        refresh();
    } else if (evt.type === 'network_stopped') {
        log('err', 'ION shutdown'); refresh();
    } else if (evt.type === 'scenario_started') {
        log('sys', 'Simulation started'); simActive = true; updateModeBadge();
    } else if (evt.type === 'scenario_stopped') {
        log('sys', 'Simulation stopped'); simActive = false; updateModeBadge();
    } else if (evt.type === 'scenario_loaded') {
        log('sys', `Scenario loaded: ${evt.count} events`);
        if (evt.briefing) displayBriefing(evt.briefing);
    } else if (evt.type === 'module_attached') {
        log('mod', `Module ${evt.name} attached to N${evt.node_id}`); refreshModules();
    } else if (evt.type === 'module_detached') {
        log('sys', `Module ${evt.name} detached from N${evt.node_id}`); refreshModules();
    } else if (evt.type === 'log') {
        log(evt.tag, evt.msg);
    }
}

// ── Scenario Presets ────────────────────────────

let SCENARIOS = {};
async function fetchScenarios() {
    const list = await api('GET', '/api/scenario/list');
    const sel = document.getElementById('scenario-preset');
    sel.innerHTML = '<option value="">— Load Scenario —</option>';
    list.forEach(s => {
        SCENARIOS[s.id] = s;
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.name;
        sel.appendChild(opt);
    });
}

// ── API ─────────────────────────────────────────

async function api(method, path) {
    const res = await fetch(`${API}${path}`, { method });
    return res.json();
}

async function addNode() {
    const id = parseInt(document.getElementById('input-node-id').value);
    if (!id) return;
    const r = await api('POST', `/api/nodes?node_id=${id}`);
    if (r.error) log('err', r.error); else log('sys', `Node N${id} registered`);
    document.getElementById('input-node-id').value = '';
    refresh();
}

async function startNetwork() {
    log('sys', 'Initializing ION C-Core...');
    await api('POST', '/api/start');
    refresh();
}

async function stopNetwork() {
    await api('POST', '/api/stop');
    refresh();
}

async function sendBundle() {
    const src = parseInt(document.getElementById('input-src').value);
    const dst = parseInt(document.getElementById('input-dst').value);
    const p = document.getElementById('input-payload').value;
    if (!src || !dst) return;
    await api('POST', `/api/send?from_node=${src}&to_node=${dst}&payload=${encodeURIComponent(p)}`);
}

async function startScenario() { await api('POST', '/api/scenario/start'); }
async function stopScenario() { await api('POST', '/api/scenario/stop'); }

async function loadScenario() {
    const key = document.getElementById('scenario-preset').value;
    if (!key) return;
    const scenario = SCENARIOS[key];
    const res = await fetch('/api/scenario/load', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(scenario)
    });
    const data = await res.json();
    if (data.briefing) displayBriefing(data.briefing);
    log('sys', `Loaded: ${scenario.name || key}`);

    // Auto-register nodes from scenario
    const nodes = new Set();
    const events = scenario.events || [];
    if (Array.isArray(events)) {
        events.forEach(e => {
            if (!e.action) return;
            if (e.action.includes('contact')) {
                const offset = e.args.length === 8 ? 1 : 0;
                nodes.add(e.args[offset]); nodes.add(e.args[offset + 1]);
            } else if (e.action.includes('range')) { nodes.add(e.args[0]); nodes.add(e.args[1]); }
            else if (e.action === 'set_position' || e.action === 'move_linear') { nodes.add(e.args[0]); }
        });
    }
    if (scenario.wlan_nodes) scenario.wlan_nodes.forEach(n => nodes.add(n));
    let needsStart = false;
    for (let id of nodes) {
        if (!nodeList.find(n => n.node_id === id)) {
            await api('POST', `/api/nodes?node_id=${id}`);
            needsStart = true;
        }
    }
    await refresh();
    if (needsStart || !nodeList.some(n => n.is_running)) await startNetwork();
}

async function sendCFDP() {
    const src = parseInt(document.getElementById('cfdp-src').value);
    const dst = parseInt(document.getElementById('cfdp-dst').value);
    const file = document.getElementById('cfdp-file').value;
    if (!src || !dst || !file) return;
    log('tx', `CFDP: ${file} → N${dst}`);
    await api('POST', `/api/cfdp/send?from_node=${src}&to_node=${dst}&file=${encodeURIComponent(file)}`);
}

// ── Refresh ─────────────────────────────────────

async function refresh() {
    nodeList = await api('GET', '/api/nodes');
    linkList = await api('GET', '/api/links');
    // Node chips
    document.getElementById('node-chips').innerHTML = nodeList.map(n =>
        `<span class="chip ${n.is_running ? 'running' : ''}">N${n.node_id}</span>`
    ).join('');
    // Module node selector
    const modSel = document.getElementById('mod-node-select');
    const curVal = modSel.value;
    modSel.innerHTML = '<option value="">— Select Node —</option>' +
        nodeList.map(n => `<option value="${n.node_id}"${n.node_id == curVal ? ' selected' : ''}>N${n.node_id}${n.is_running ? ' (active)' : ''}</option>`).join('');
    refreshModules();
    updateOps();
    updateModeBadge();
}

function addToHistory(item) {
    bundleHistory.unshift(item);
    if (bundleHistory.length > 50) bundleHistory.pop();
    const body = document.getElementById('history-body');
    body.innerHTML = bundleHistory.map(h => `
        <tr>
            <td>${h.time}</td><td>${h.src}</td><td>${h.dst}</td><td>${h.size}B</td>
            <td style="color:${h.status === 'ANOMALY' ? '#ff978f' : '#82eab2'}">${h.status === 'ANOMALY' ? '⚠ ANOM' : '✓ OK'}</td>
        </tr>
    `).join('');
    updateOps();
}

function log(tag, msg) {
    const el = document.getElementById('event-log');
    const d = document.createElement('div');
    d.innerHTML = `<span class="log-${tag}">[${tag.toUpperCase()}]</span> ${msg}`;
    el.prepend(d);
    if (el.children.length > 100) el.lastChild.remove();
}

// ── D3 Charts ───────────────────────────────────

function initCharts() {
    const drawLine = (selector, data, color) => {
        const el = d3.select(selector);
        const w = el.node()?.clientWidth, h = 80;
        if (!w || w === 0) return;
        el.selectAll('*').remove();
        const svg = el.append('svg').attr('width', w).attr('height', h);
        const x = d3.scaleLinear().domain([0, hMax]).range([0, w]);
        const y = d3.scaleLinear().domain([0, d3.max(data) || 10]).range([h, 0]);
        const line = d3.line().x((d, i) => x(i)).y(d => y(d)).curve(d3.curveBasis);
        // Area fill
        const area = d3.area().x((d, i) => x(i)).y0(h).y1(d => y(d)).curve(d3.curveBasis);
        svg.append('path').datum(data).attr('fill', color).attr('fill-opacity', 0.08).attr('d', area);
        svg.append('path').datum(data).attr('fill', 'none').attr('stroke', color).attr('stroke-width', 1.5).attr('d', line);
    };
    window.updateUICharts = () => {
        drawLine('#chart-sdr', sdrData.slice(-hMax).map(d => Object.values(d.nodes).reduce((a, b) => a + b, 0)), '#3db9ff');
        drawLine('#chart-flow', flowData.slice(-hMax).map(d => d.bps), '#2ecc71');
    };
}

function updateCharts(data) {
    const sdrPoint = { time: Date.now(), nodes: {} };
    data.forEach(n => { if (n.sdr) sdrPoint.nodes[n.node_id] = n.sdr.wmSize; });
    sdrData.push(sdrPoint);
    if (sdrData.length > hMax * 2) sdrData.shift();
    if (flowData.length === 0 || Date.now() - flowData[flowData.length - 1].time > 1000) flowData.push({ time: Date.now(), bps: 0 });
    if (flowData.length > hMax * 2) flowData.shift();
    updateUICharts();
}

function updateFlowChart(bytes) {
    if (flowData.length > 0 && Date.now() - flowData[flowData.length - 1].time < 1000) flowData[flowData.length - 1].bps += bytes;
    else flowData.push({ time: Date.now(), bps: bytes });
    updateUICharts();
}

// ── Canvas Drawing ──────────────────────────────

function resize() {
    const wrapper = document.getElementById('canvas-wrapper');
    if (wrapper && canvas) { canvas.width = wrapper.clientWidth; canvas.height = wrapper.clientHeight; }
}

function draw() {
    if (!ctx) return requestAnimationFrame(draw);
    const W = canvas.width, H = canvas.height;
    if (W === 0 || H === 0) { requestAnimationFrame(draw); return; }
    ctx.clearRect(0, 0, W, H);

    const isSim = simActive || Object.keys(targetPositions).length > 0;

    // Background
    if (isSim) {
        drawGrid(ctx, W, H);
    } else {
        ctx.fillStyle = '#060e17';
        ctx.fillRect(0, 0, W, H);
        const grad = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, Math.max(W, H) * 0.55);
        grad.addColorStop(0, 'rgba(61, 185, 255, 0.03)');
        grad.addColorStop(1, 'transparent');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, W, H);
    }

    // Position each node
    const positions = {};
    const n = nodeList.length;
    const cx = W / 2, cy = H / 2, r = Math.min(cx, cy) * 0.6;
    const simBounds = isSim ? getSimBounds() : null;
    nodeList.forEach((nd, i) => {
        let tx, ty;
        if (isSim && targetPositions[nd.node_id]) {
            const proj = projectPos(targetPositions[nd.node_id], simBounds, W, H);
            tx = proj.x; ty = proj.y;
        } else {
            const a = (i / n) * Math.PI * 2 - Math.PI / 2;
            tx = cx + r * Math.cos(a); ty = cy + r * Math.sin(a);
        }
        if (!currentPositions[nd.node_id]) currentPositions[nd.node_id] = { x: tx, y: ty };
        else {
            const f = isSim ? 0.04 : 1.0;
            currentPositions[nd.node_id].x += (tx - currentPositions[nd.node_id].x) * f;
            currentPositions[nd.node_id].y += (ty - currentPositions[nd.node_id].y) * f;
        }
        positions[nd.node_id] = { x: currentPositions[nd.node_id].x, y: currentPositions[nd.node_id].y, ...nd };
    });

    // Movement vectors
    if (isSim && scenarioTelemetry?.moving_nodes?.length) {
        scenarioTelemetry.moving_nodes.forEach(item => {
            const from = positions[item.node_id];
            if (!from || !item.destination) return;
            const target = projectPos(item.destination, simBounds, W, H);
            ctx.beginPath(); ctx.moveTo(from.x, from.y); ctx.lineTo(target.x, target.y);
            ctx.setLineDash([5, 6]); ctx.strokeStyle = 'rgba(241,196,15,0.45)'; ctx.lineWidth = 1.2; ctx.stroke();
            ctx.setLineDash([]);
        });
    }

    // Links
    linkList.forEach(l => {
        const a = positions[l.from], b = positions[l.to];
        if (!a || !b) return;
        const isWlan = l.kind === 'wlan';
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = isWlan ? 'rgba(241,196,15,0.65)' : 'rgba(61,185,255,0.4)';
        ctx.lineWidth = isWlan ? 1.8 : 1.3;
        ctx.setLineDash(isWlan ? [4, 4] : [2, 5]);
        ctx.shadowBlur = 5; ctx.shadowColor = isWlan ? 'rgba(241,196,15,0.3)' : 'rgba(61,185,255,0.15)';
        ctx.stroke(); ctx.shadowBlur = 0; ctx.setLineDash([]);
    });

    // Bundle animations
    animBundles = animBundles.filter(b => {
        b.p += 0.02;
        if (b.p > 1) return false;
        const a = positions[b.from], t = positions[b.to];
        if (!a || !t) return false;
        const x = a.x + (t.x - a.x) * b.p, y = a.y + (t.y - a.y) * b.p;
        ctx.fillStyle = '#3db9ff'; ctx.shadowBlur = 8; ctx.shadowColor = 'rgba(61,185,255,0.5)';
        ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
        return true;
    });

    // Nodes
    const nodeR = isSim ? 16 : 20;
    Object.values(positions).forEach(nd => {
        const isMoving = scenarioTelemetry?.moving_nodes?.some(m => m.node_id === nd.node_id);
        const nodeMods = moduleStatus[nd.node_id];
        const hasModule = nodeMods && Object.keys(nodeMods).length > 0;
        const hasAnomaly = hasModule && Object.values(nodeMods).some(m => m.status === 'anomaly');
        const hasError = hasModule && Object.values(nodeMods).some(m => m.status === 'error');

        // Outer halo
        ctx.beginPath();
        ctx.fillStyle = hasAnomaly ? 'rgba(241,196,15,0.1)' : isMoving ? 'rgba(241,196,15,0.08)' : 'rgba(61,185,255,0.06)';
        ctx.arc(nd.x, nd.y, nodeR + 7, 0, Math.PI * 2); ctx.fill();

        // Body
        ctx.beginPath(); ctx.fillStyle = '#0a1a2a';
        ctx.shadowBlur = 10; ctx.shadowColor = 'rgba(61,185,255,0.12)';
        ctx.arc(nd.x, nd.y, nodeR, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
        ctx.strokeStyle = hasAnomaly ? '#f1c40f' : hasError ? '#e74c3c' : isMoving ? '#f1c40f' : nd.is_running ? '#2ecc71' : '#3db9ff';
        ctx.lineWidth = 2.2; ctx.stroke();

        // Label
        ctx.fillStyle = '#e8f1f8'; ctx.font = '700 10px "IBM Plex Mono"';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(`N${nd.node_id}`, nd.x, nd.y);

        // Module LED badge (top-right of node)
        if (hasModule) {
            const lx = nd.x + nodeR * 0.7, ly = nd.y - nodeR * 0.7;
            const ledColor = hasError ? '#e74c3c' : hasAnomaly ? '#f1c40f' : '#2ecc71';
            ctx.beginPath();
            ctx.fillStyle = ledColor;
            ctx.shadowBlur = 6; ctx.shadowColor = ledColor;
            ctx.arc(lx, ly, 4, 0, Math.PI * 2); ctx.fill();
            ctx.shadowBlur = 0;
        }

        // Coords in sim mode
        if (isSim && targetPositions[nd.node_id]) {
            ctx.fillStyle = 'rgba(139,164,184,0.7)'; ctx.font = '500 8px "IBM Plex Mono"';
            ctx.fillText(`${targetPositions[nd.node_id].x.toFixed(0)},${targetPositions[nd.node_id].y.toFixed(0)}`, nd.x, nd.y + nodeR + 11);
        }
    });

    // Footer stats (sim mode)
    if (isSim && scenarioTelemetry) {
        const t = scenarioTelemetry;
        ctx.fillStyle = 'rgba(139,164,184,0.65)'; ctx.font = '500 9px "IBM Plex Mono"';
        ctx.textAlign = 'left';
        ctx.fillText(`TRACKED ${t.tracked_node_count || 0} | EV ${t.executed_events || 0}/${t.total_events || 0} | LNK ${t.active_link_count || 0}`, 14, H - 12);
        ctx.textAlign = 'right';
        ctx.fillText(`NEXT: ${t.next_event_action ? fmtAction(t.next_event_action).toUpperCase() : 'NONE'}`, W - 14, H - 12);
    }

    // Empty state
    if (nodeList.length === 0) {
        ctx.fillStyle = '#4e6878'; ctx.font = '500 13px "Space Grotesk"';
        ctx.textAlign = 'center'; ctx.fillText('Register nodes to begin simulation', W / 2, H / 2);
    }

    requestAnimationFrame(draw);
}

function animateBundle(from, to) { animBundles.push({ from, to, p: 0 }); }

// ── Spatial Helpers ─────────────────────────────

function getSimBounds() {
    const pos = Object.values(targetPositions);
    if (!pos.length) return { minX: 0, maxX: 1000, minY: 0, maxY: 750 };
    const xs = pos.map(p => p.x), ys = pos.map(p => p.y);
    const margin = scenarioTelemetry?.wlan_range ? Math.max(40, scenarioTelemetry.wlan_range * 0.3) : 80;
    return { minX: Math.min(...xs) - margin, maxX: Math.max(...xs) + margin, minY: Math.min(...ys) - margin, maxY: Math.max(...ys) + margin };
}

function projectPos(pos, bounds, W, H) {
    const pad = 45;
    const uW = Math.max(W - pad * 2, 1), uH = Math.max(H - pad * 2, 1);
    const sX = Math.max(bounds.maxX - bounds.minX, 1), sY = Math.max(bounds.maxY - bounds.minY, 1);
    return { x: pad + ((pos.x - bounds.minX) / sX) * uW, y: pad + ((pos.y - bounds.minY) / sY) * uH };
}

function drawGrid(ctx, W, H) {
    const step = 44;
    ctx.fillStyle = '#060e17'; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(50,120,170,0.06)'; ctx.lineWidth = 1;
    for (let x = 0; x <= W; x += step) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = 0; y <= H; y += step) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
}

// ── System Clock ────────────────────────────────

setInterval(() => {
    const el = document.getElementById('sys-time-display');
    if (!el) return;
    const d = new Date();
    const yr = d.getUTCFullYear();
    const start = new Date(d.getUTCFullYear(), 0, 0);
    const diff = d - start;
    const day = Math.floor(diff / 86400000).toString().padStart(3, '0');
    const hr = d.getUTCHours().toString().padStart(2, '0');
    const min = d.getUTCMinutes().toString().padStart(2, '0');
    const sec = d.getUTCSeconds().toString().padStart(2, '0');
    el.innerText = `${yr}.${day}.${hr}:${min}:${sec}`;
}, 1000);
