/**
 * app.js — Frontend logic for Shatter UI
 */

// ── State ──
let wordlistPath = null;
let rulePaths = [];
let hashFilePath = null;
let hcPath = null;
let jtrPath = null;
let isCracking = false;

// ── Navigation ──
function nav(viewId) {
    // Hide all views
    document.getElementById('view-dashboard').classList.add('hidden');
    document.getElementById('view-potfile').classList.add('hidden');
    document.getElementById('view-settings').classList.add('hidden');
    
    // Reset all nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('bg-bgCard', 'border', 'border-borderSubtle', 'text-accent', 'shadow-[0_0_15px_rgba(249,115,22,0.2)]');
        btn.classList.add('text-textDim');
    });

    // Show target view
    document.getElementById(`view-${viewId}`).classList.remove('hidden');
    
    // Highlight target button
    const btn = document.getElementById(`nav-${viewId}`);
    btn.classList.remove('text-textDim');
    btn.classList.add('bg-bgCard', 'border', 'border-borderSubtle', 'text-accent', 'shadow-[0_0_15px_rgba(249,115,22,0.2)]');

    if (viewId === 'potfile') refreshPotfile();
}

// ── Terminal / Logs ──
const terminal = document.getElementById('terminal');
const logsPanel = document.getElementById('logs-panel');

function toggleLogs() {
    logsPanel.classList.toggle('open');
}

function openLogs() {
    logsPanel.classList.add('open');
}

window.onHashcatOutput = function(line) {
    // Filter out useless prompts
    if (line.includes('[s]tatus [p]ause')) return;

    // Check if it's a progress update to parse
    if (line.includes('Progress.')) {
        // Progress.........: 1157190/14344384 (8.07%)
        const match = line.match(/\(([\d.]+)%\)/);
        if (match) updateProgress(parseFloat(match[1]));
    }
    if (line.includes('Time.Estimated...:')) {
        const eta = line.split('Time.Estimated...:')[1].trim();
        document.getElementById('progress-text').children[1].innerText = `ETA: ${eta}`;
    }

    const span = document.createElement('span');
    
    // Check if it's the cracked hash line: <hash>:<password>
    if (line.includes(':') && !/^(Session|Status|Hash|Time|Guess|Speed|Recovered|Progress|\* |hashcat|Initializing|nvml|CUDA|OpenCL|Host|Dictionary|Rules)/i.test(line.trim())) {
        const parts = line.split(':');
        const pwd = parts.pop();
        const h = parts.join(':');
        span.innerHTML = `${h}<span class="text-slate-500 text-xs mx-1 ml-3">PASSWORD:</span><span class="text-orange-500 font-mono underline decoration-orange-500/30 underline-offset-4">${pwd}</span>\n`;
    } else {
        span.textContent = line + '\n';
    }
    
    terminal.appendChild(span);
    
    // Auto-scroll
    if (terminal.scrollHeight - terminal.scrollTop < terminal.clientHeight + 100) {
        terminal.scrollTop = terminal.scrollHeight;
    }
};

window.clearHashcatOutput = function() {
    terminal.innerHTML = '';
    updateProgress(0);
    document.getElementById('progress-text').children[1].innerText = 'ETA: --:--:--';
};

function dismissReveal() {
    document.getElementById('cracked-reveal').classList.add('hidden');
    document.getElementById('btn-crack').style.display = 'flex';
}

window.onCrackDone = async function() {
    isCracking = false;
    document.getElementById('process-controls').classList.add('hidden');
    
    // Check potfile for the big reveal!
    const targetHash = document.getElementById('hash-input').value.trim();
    if (targetHash) {
        const entries = await window.pywebview.api.get_potfile();
        // Simple match: potfile hash is a substring or vice versa
        const found = entries.find(e => e.hash.includes(targetHash) || targetHash.includes(e.hash));
        if (found) {
            document.getElementById('cracked-password-display').innerText = found.password;
            document.getElementById('btn-crack').style.display = 'none';
            document.getElementById('btn-restore').style.display = 'none';
            document.getElementById('cracked-reveal').classList.remove('hidden');
            return;
        }
    }
    
    document.getElementById('btn-crack').style.display = 'flex';
    document.getElementById('btn-restore').style.display = 'none';
};

function updateProgress(percent) {
    document.getElementById('progress-bar').style.width = `${percent}%`;
    document.getElementById('progress-text').children[0].innerText = `${percent.toFixed(2)}%`;
}

// ── Dashboard Actions ──

document.getElementById('hash-input').addEventListener('input', async (e) => {
    const val = e.target.value.trim();
    if (!val) {
        document.getElementById('algo-name').innerText = 'None';
        document.getElementById('algo-name').className = 'text-white';
        return;
    }
    // Auto-detect
    const res = await window.pywebview.api.detect_hash(val);
    document.getElementById('algo-name').innerText = res.algo;
    if (res.algo.includes("Unknown") || res.algo.includes("Failed")) {
        document.getElementById('algo-name').className = 'text-danger';
    } else {
        document.getElementById('algo-name').className = 'text-accent';
    }
    document.getElementById('hash-mode').value = res.m_value;
    
    hashFilePath = null;
    document.getElementById('hashfile-label').classList.add('hidden');
    saveConfig();
});

async function extractHash() {
    const res = await window.pywebview.api.extract_hash();
    if (res.error) {
        alert(res.error);
    } else if (res.hash) {
        document.getElementById('hash-input').value = res.hash;
        document.getElementById('hash-input').dispatchEvent(new Event('input'));
    }
}

async function loadHashFile() {
    const res = await window.pywebview.api.load_hash_file();
    if (res.path) {
        hashFilePath = res.path;
        document.getElementById('hash-input').value = '';
        const name = hashFilePath.split(/[\\/]/).pop();
        const lbl = document.getElementById('hashfile-label');
        lbl.innerText = `📋 Loaded File: ${name}`;
        lbl.classList.remove('hidden');
        document.getElementById('algo-name').innerText = 'File provided (manual mode needed)';
        document.getElementById('algo-name').className = 'text-textDim';
        saveConfig();
    }
}

async function selectWordlist() {
    const res = await window.pywebview.api.select_wordlist();
    if (res.path) {
        wordlistPath = res.path;
        document.getElementById('wordlist-path').innerText = res.path.split(/[\\/]/).pop();
        saveConfig();
    }
}

async function addRule() {
    const res = await window.pywebview.api.add_rule();
    if (res.path) {
        rulePaths.push(res.path);
        updateRuleLabel();
        saveConfig();
    }
}

function clearRules() {
    rulePaths = [];
    updateRuleLabel();
    saveConfig();
}

function updateRuleLabel() {
    const lbl = document.getElementById('rule-paths');
    if (rulePaths.length === 0) {
        lbl.innerText = 'No rules';
    } else if (rulePaths.length === 1) {
        lbl.innerText = rulePaths[0].split(/[\\/]/).pop();
    } else {
        lbl.innerText = `${rulePaths.length} rules loaded`;
    }
}

document.getElementById('set-attack-mode').addEventListener('change', (e) => {
    const mode = e.target.value;
    const wlBtn = document.getElementById('wordlist-path').parentElement;
    const ruleSec = document.getElementById('rule-section');
    const maskInp = document.getElementById('mask-input');
    
    if (mode === '3') {
        wlBtn.style.display = 'none';
        ruleSec.style.display = 'none';
        maskInp.style.display = 'block';
    } else if (mode === '6' || mode === '7') {
        wlBtn.style.display = 'flex';
        ruleSec.style.display = 'none';
        maskInp.style.display = 'block';
    } else {
        wlBtn.style.display = 'flex';
        ruleSec.style.display = 'flex';
        maskInp.style.display = 'none';
    }
    saveConfig();
});

// ── Execution ──

function getSettingsObject() {
    return {
        hash: document.getElementById('hash-input').value.trim(),
        m_value: document.getElementById('hash-mode').value.trim(),
        wordlist: wordlistPath,
        rules: rulePaths,
        hash_file_path: hashFilePath,
        mask: document.getElementById('mask-input').value.trim(),
        device: document.getElementById('device-select').value,
        attack_mode: document.getElementById('set-attack-mode').value,
        workload_profile: document.getElementById('set-workload').value,
        optimized_kernel: document.getElementById('set-opt-kernel').checked,
        session_name: document.getElementById('set-session').value.trim(),
        hwmon_temp_abort: document.getElementById('set-temp').value.trim(),
        disable_potfile: document.getElementById('set-disable-potfile').checked,
        skip: document.getElementById('set-skip').value.trim(),
        limit: document.getElementById('set-limit').value.trim(),
    };
}

async function startCrack() {
    if (!hcPath) {
        alert("Hashcat path not set! Please go to Settings.");
        nav('settings');
        return;
    }
    const settings = getSettingsObject();
    if (!settings.hash && !settings.hash_file_path) {
        alert("Please provide a target hash or hash file.");
        return;
    }
    
    isCracking = true;
    document.getElementById('btn-crack').style.display = 'none';
    document.getElementById('process-controls').classList.remove('hidden');
    openLogs();
    
    // Auto-check if we need restore button based on session name
    if (settings.session_name) {
        document.getElementById('btn-restore').style.display = 'flex';
    }

    await window.pywebview.api.start_crack(settings);
}

async function restoreCrack() {
    const session = document.getElementById('set-session').value.trim();
    if (!session) {
        alert("Please set a Session Name in settings to restore.");
        return;
    }
    isCracking = true;
    document.getElementById('btn-crack').style.display = 'none';
    document.getElementById('process-controls').classList.remove('hidden');
    openLogs();
    
    await window.pywebview.api.restore_crack(session);
}

async function stopCrack() {
    await window.pywebview.api.stop_crack();
}

async function pauseCrack() {
    const btn = document.getElementById('btn-pause');
    const paused = await window.pywebview.api.pause_crack();
    if (paused) {
        btn.innerText = "Resume";
        btn.classList.add('bg-accent/20', 'text-accent', 'border-accent/50');
    } else {
        btn.innerText = "Pause";
        btn.classList.remove('bg-accent/20', 'text-accent', 'border-accent/50');
    }
}

async function checkpointCrack() {
    await window.pywebview.api.checkpoint_crack();
}

async function runBenchmark() {
    if (isCracking) return;
    const device = document.getElementById('device-select').value;
    openLogs();
    await window.pywebview.api.run_benchmark(device);
}

// ── Settings ──

async function browseFolder(type) {
    const res = await window.pywebview.api.browse_folder();
    if (res.path) {
        if (type === 'hc') {
            hcPath = res.path;
            document.getElementById('set-hc-path').value = hcPath;
        } else {
            jtrPath = res.path;
            document.getElementById('set-jtr-path').value = jtrPath;
        }
        await window.pywebview.api.set_tool_paths(hcPath || "", jtrPath || "");
        saveConfig();
        if (type === 'hc') loadDevices();
    }
}

// ── Potfile ──

async function refreshPotfile() {
    const tbody = document.getElementById('potfile-tbody');
    tbody.innerHTML = '<tr><td colspan="2" class="p-6 text-center text-textDim">Loading...</td></tr>';
    
    const entries = await window.pywebview.api.get_potfile();
    tbody.innerHTML = '';
    
    if (entries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="2" class="p-6 text-center text-textDim">No entries found.</td></tr>';
        return;
    }
    
    entries.forEach(e => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-bgCardHover transition-colors";
        
        const tdHash = document.createElement('td');
        tdHash.className = "px-6 py-3 text-textDim truncate max-w-xs";
        tdHash.title = e.hash;
        tdHash.innerText = e.hash;
        
        const tdPass = document.createElement('td');
        tdPass.className = "px-6 py-3";
        tdPass.innerHTML = `<span class="select-text bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1 rounded-md font-mono font-bold tracking-wide">${e.password}</span>`;
        
        tr.appendChild(tdHash);
        tr.appendChild(tdPass);
        tbody.appendChild(tr);
    });
}

async function clearPotfile() {
    if (confirm("Are you sure you want to clear the potfile? This cannot be undone.")) {
        await window.pywebview.api.clear_potfile();
        refreshPotfile();
    }
}

// ── Initialization & Config ──

let saveTimeout = null;
function saveConfig() {
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = setTimeout(async () => {
        const cfg = getSettingsObject();
        cfg.hc_path = hcPath;
        cfg.jtr_path = jtrPath;
        await window.pywebview.api.save_config(cfg);
    }, 500);
}

// Attach auto-save to inputs
document.querySelectorAll('input, select').forEach(el => {
    el.addEventListener('change', saveConfig);
    if(el.type === 'text' || el.type === 'number') {
        el.addEventListener('keyup', saveConfig);
    }
});

async function loadDevices() {
    if (!hcPath) return;
    const devices = await window.pywebview.api.get_devices();
    const sel = document.getElementById('device-select');
    sel.innerHTML = '';
    devices.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.id;
        opt.innerText = d.name;
        sel.appendChild(opt);
    });
}

window.addEventListener('pywebviewready', async function() {
    // Load config
    const cfg = await window.pywebview.api.get_config();
    if (cfg) {
        if (cfg.hash) document.getElementById('hash-input').value = cfg.hash;
        if (cfg.m_value) document.getElementById('hash-mode').value = cfg.m_value;
        if (cfg.wordlist) {
            wordlistPath = cfg.wordlist;
            document.getElementById('wordlist-path').innerText = wordlistPath.split(/[\\/]/).pop();
        }
        if (cfg.rules) {
            rulePaths = cfg.rules;
            updateRuleLabel();
        }
        if (cfg.hash_file_path) {
            hashFilePath = cfg.hash_file_path;
            const name = hashFilePath.split(/[\\/]/).pop();
            const lbl = document.getElementById('hashfile-label');
            lbl.innerText = `📋 Loaded File: ${name}`;
            lbl.classList.remove('hidden');
        }
        if (cfg.mask) document.getElementById('mask-input').value = cfg.mask;
        if (cfg.attack_mode) document.getElementById('set-attack-mode').value = cfg.attack_mode;
        if (cfg.workload_profile) document.getElementById('set-workload').value = cfg.workload_profile;
        if (cfg.optimized_kernel) document.getElementById('set-opt-kernel').checked = cfg.optimized_kernel;
        if (cfg.session_name) document.getElementById('set-session').value = cfg.session_name;
        if (cfg.hwmon_temp_abort) document.getElementById('set-temp').value = cfg.hwmon_temp_abort;
        if (cfg.disable_potfile) document.getElementById('set-disable-potfile').checked = cfg.disable_potfile;
        if (cfg.skip) document.getElementById('set-skip').value = cfg.skip;
        if (cfg.limit) document.getElementById('set-limit').value = cfg.limit;
        
        if (cfg.hc_path) {
            hcPath = cfg.hc_path;
            document.getElementById('set-hc-path').value = hcPath;
        }
        if (cfg.jtr_path) {
            jtrPath = cfg.jtr_path;
            document.getElementById('set-jtr-path').value = jtrPath;
        }
        
        await window.pywebview.api.set_tool_paths(hcPath || "", jtrPath || "");
        
        // Trigger mode UI update
        document.getElementById('set-attack-mode').dispatchEvent(new Event('change'));
        // Trigger hash detect UI update
        if (cfg.hash && !cfg.hash_file_path) {
            document.getElementById('hash-input').dispatchEvent(new Event('input'));
        }

        if (hcPath) loadDevices();
        
        if (cfg.session_name) {
            document.getElementById('btn-restore').style.display = 'flex';
        }
    }
});

// �� Window Resizing ��
function setupResize() {
    let isResizing = false;
    let initialMouseX, initialMouseY;
    let initialWidth, initialHeight;
    let resizeDir = '';
    let resizeReq = null;

    const startResize = async (e, dir) => {
        isResizing = true;
        resizeDir = dir;
        initialMouseX = e.screenX;
        initialMouseY = e.screenY;
        const size = await window.pywebview.api.get_window_size();
        initialWidth = size.width;
        initialHeight = size.height;
        document.body.style.cursor = dir === 'e' ? 'e-resize' : dir === 's' ? 's-resize' : 'se-resize';
        // Prevent text selection during resize
        e.preventDefault();
    };

    document.getElementById('resize-r').addEventListener('mousedown', (e) => startResize(e, 'e'));
    document.getElementById('resize-b').addEventListener('mousedown', (e) => startResize(e, 's'));
    document.getElementById('resize-br').addEventListener('mousedown', (e) => startResize(e, 'se'));

    window.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        const dx = e.screenX - initialMouseX;
        const dy = e.screenY - initialMouseY;
        
        let newW = initialWidth;
        let newH = initialHeight;
        
        if (resizeDir.includes('e')) newW += dx;
        if (resizeDir.includes('s')) newH += dy;
        
        newW = Math.max(900, newW);
        newH = Math.max(650, newH);
        
        if (!resizeReq) {
            resizeReq = requestAnimationFrame(() => {
                window.pywebview.api.resize(newW, newH);
                resizeReq = null;
            });
        }
    });

    window.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            document.body.style.cursor = 'default';
        }
    });
}
window.addEventListener('DOMContentLoaded', setupResize);


