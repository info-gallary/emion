/* ═══════════════════════════════════════════
   EmION Dashboard JS — BPv7 Mission Control
   Powered by D3.js for Real-Time Analytics
   ═══════════════════════════════════════════ */

const API = '';
let ws = null;
let nodeList = [];
let linkList = [];
let canvas, ctx;
let animBundles = [];
let bundleHistory = [];

// D3 Chart State
const hMax = 60; // 60 seconds of history
let sdrData = []; // [{time, nodes: {id: val}}]
let flowData = []; // [{time, bps}]

// ── Init ─────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    canvas = document.getElementById('topology-canvas');
    ctx = canvas.getContext('2d');
    
    // Resize observer for canvas
    const ro = new ResizeObserver(entries => { resize(); });
    ro.observe(document.getElementById('viz-container'));

    document.getElementById('btn-add-node').addEventListener('click', addNode);
    document.getElementById('btn-start').addEventListener('click', startNetwork);
    document.getElementById('btn-stop').addEventListener('click', stopNetwork);
    document.getElementById('btn-send').addEventListener('click', sendBundle);
    document.getElementById('btn-connect-mod').addEventListener('click', connectModule);

    initCharts();
    connectWS();
    refresh();
    setInterval(refresh, 5000);
    requestAnimationFrame(draw);
});

// ── WebSocket & Events ───────────────────

function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onopen = () => { document.getElementById('ws-status').className = 'status-dot live'; };
    ws.onclose = () => {
        document.getElementById('ws-status').className = 'status-dot';
        setTimeout(connectWS, 3000);
    };
    ws.onmessage = e => onEvent(JSON.parse(e.data));
}

function onEvent(evt) {
    const now = new Date().toLocaleTimeString();
    
    if (evt.type === 'bundle_sent') {
        log('tx', `BPv7: ${evt.src} → ${evt.dst} (${evt.size}B)`);
        animateBundle(evt.from, evt.to);
        addToHistory({
            time: now,
            src: evt.src,
            dst: evt.dst,
            size: evt.size,
            status: 'TRANSIT',
            modules: evt.modules || {}
        });
        updateFlowChart(evt.size);
    } else if (evt.type === 'bundle_received') {
        log('rx', `BPv7 RX on ${evt.eid}: Payload size ${evt.size}B`);
    } else if (evt.type === 'telemetry_update') {
        updateCharts(evt.data);
    } else if (evt.type === 'network_started') {
        log('sys', `Core Active: BPv7 Nodes [${evt.nodes.join(', ')}]`);
        refresh();
    } else if (evt.type === 'network_stopped') {
        log('err', 'ION system shutdown requested');
        refresh();
    }
}

// ── API Actions ──────────────────────────

async function api(method, path) {
    const res = await fetch(`${API}${path}`, { method });
    return res.json();
}

async function addNode() {
    const id = parseInt(document.getElementById('input-node-id').value);
    if (!id) return;
    await api('POST', `/api/nodes?node_id=${id}`);
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
    const r = await api('POST', `/api/send?from_node=${src}&to_node=${dst}&payload=${encodeURIComponent(p)}`);
    if (r.error) log('err', r.error);
}

async function connectModule() {
    const url = document.getElementById('input-mod-url').value;
    const targets = document.getElementById('input-mod-targets').value || 'all';
    if (!url) return;
    const r = await api('POST', `/api/modules/connect?url=${encodeURIComponent(url)}&target_nodes=${encodeURIComponent(targets)}`);
    if (r.error) log('err', r.error);
    else { log('mod', `Attached Module: ${r.name}`); refreshModules(); }
}

// ── UI Refresh ───────────────────────────

async function refresh() {
    nodeList = await api('GET', '/api/nodes');
    linkList = await api('GET', '/api/links');
    
    document.getElementById('node-chips').innerHTML = nodeList.map(n =>
        `<span class="chip ${n.is_running ? 'running' : ''}">N${n.node_id}</span>`
    ).join('');

    refreshModules();
}

async function refreshModules() {
    const mods = await api('GET', '/api/modules');
    document.getElementById('module-list').innerHTML =
        mods.map(m => `<span class="chip" style="border-color:#ddd6fe; color:#8b5cf6">${m.name}</span>`).join('');
}

function addToHistory(item) {
    bundleHistory.unshift(item);
    if (bundleHistory.length > 50) bundleHistory.pop();
    
    const body = document.getElementById('history-body');
    body.innerHTML = bundleHistory.map(h => {
        const modCount = Object.keys(h.modules).length;
        const isAnom = Object.values(h.modules).some(m => m.is_anomaly);
        return `
            <tr>
                <td>${h.time}</td>
                <td>${h.src}</td>
                <td>${h.dst}</td>
                <td>${h.size}B</td>
                <td style="color:${isAnom ? 'red' : 'inherit'}">${isAnom ? '⚠ ANOMALY' : '✓ BPv7_OK'}</td>
                <td>${modCount} Active</td>
            </tr>
        `;
    }).join('');
}

function log(tag, msg) {
    const el = document.getElementById('event-log');
    const d = document.createElement('div');
    d.innerHTML = `<span class="log-${tag}">[${tag}]</span> ${msg}`;
    el.prepend(d);
    if (el.children.length > 100) el.lastChild.remove();
}

// ── D3.js Charts ─────────────────────────

function initCharts() {
    const drawLine = (selector, data, color) => {
        const el = d3.select(selector);
        const w = el.node().clientWidth, h = 120;
        el.selectAll('*').remove();
        const svg = el.append('svg').attr('width', w).attr('height', h);
        
        const x = d3.scaleLinear().domain([0, hMax]).range([0, w]);
        const y = d3.scaleLinear().domain([0, d3.max(data) || 10]).range([h, 0]);
        
        const line = d3.line().x((d, i) => x(i)).y(d => y(d)).curve(d3.curveBasis);
        svg.append('path').datum(data).attr('fill', 'none').attr('stroke', color).attr('stroke-width', 2).attr('d', line);
    };

    window.updateUICharts = () => {
        // Simple aggregate SDR and Flow charts
        const sdrAgg = sdrData.slice(-hMax).map(d => Object.values(d.nodes).reduce((a, b) => a + b, 0));
        drawLine('#chart-sdr', sdrAgg, '#3b82f6');
        
        const flowAgg = flowData.slice(-hMax).map(d => d.bps);
        drawLine('#chart-flow', flowAgg, '#22c55e');
    };
}

function updateCharts(data) {
    const sdrPoint = { time: Date.now(), nodes: {} };
    data.forEach(n => { if (n.sdr) sdrPoint.nodes[n.node_id] = n.sdr.wmSize; });
    sdrData.push(sdrPoint);
    if (sdrData.length > hMax * 2) sdrData.shift();
    
    // Add spacer for flow if no activity
    if (flowData.length === 0 || Date.now() - flowData[flowData.length - 1].time > 1000) {
        flowData.push({ time: Date.now(), bps: 0 });
    }
    if (flowData.length > hMax * 2) flowData.shift();
    
    updateUICharts();
}

function updateFlowChart(bytes) {
    const now = Date.now();
    if (flowData.length > 0 && now - flowData[flowData.length-1].time < 1000) {
        flowData[flowData.length-1].bps += bytes;
    } else {
        flowData.push({ time: now, bps: bytes });
    }
    updateUICharts();
}

// ── Topology Canvas ──

function resize() {
    const container = document.getElementById('viz-container');
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
}

function draw() {
    if (!ctx) return requestAnimationFrame(draw);
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const positions = {};
    const n = nodeList.length;
    const cx = W / 2, cy = H / 2, r = Math.min(cx, cy) * 0.7;

    nodeList.forEach((nd, i) => {
        const a = (i / n) * Math.PI * 2 - Math.PI / 2;
        positions[nd.node_id] = { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a), ...nd };
    });

    // Links
    linkList.forEach(l => {
        const a = positions[l.from], b = positions[l.to];
        if (!a || !b) return;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = '#e2e8f0'; ctx.lineWidth = 2; ctx.stroke();
    });

    // Bundles
    animBundles = animBundles.filter(b => {
        b.p += 0.02;
        if (b.p > 1) return false;
        const a = positions[b.from], target = positions[b.to];
        if (!a || !target) return false;
        const x = a.x + (target.x - a.x) * b.p;
        const y = a.y + (target.y - a.y) * b.p;
        ctx.fillStyle = '#3b82f6'; ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI * 2); ctx.fill();
        return true;
    });

    // Nodes
    Object.values(positions).forEach(nd => {
        ctx.fillStyle = 'white'; ctx.shadowBlur = 10; ctx.shadowColor = 'rgba(0,0,0,0.1)';
        ctx.beginPath(); ctx.arc(nd.x, nd.y, 24, 0, Math.PI * 2); ctx.fill();
        ctx.shadowBlur = 0;
        ctx.strokeStyle = nd.is_running ? '#22c55e' : '#cbd5e1'; ctx.lineWidth = 3; ctx.stroke();
        ctx.fillStyle = '#0f172a'; ctx.font = '700 12px Inter'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(`N${nd.node_id}`, nd.x, nd.y);
    });

    requestAnimationFrame(draw);
}

function animateBundle(from, to) { animBundles.push({ from, to, p: 0 }); }
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
