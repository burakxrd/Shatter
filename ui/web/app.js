/**
 * app.js — Frontend logic for Shatter UI
 *
 * Architecture (code_review_v2):
 *   TerminalManager — Log display, auto-scroll, DOM limit, log colorization
 *   HashcatBridge   — Async wrapper over window.pywebview.api with central error handling
 *   SettingsStore   — Config save/restore, debounced auto-save, form ↔ state sync
 *   Main            — Orchestration, navigation, event listeners
 */

// ═══════════════════════════════════════════════
//  TerminalManager
// ═══════════════════════════════════════════════

class TerminalManager {
    constructor(logsPanelEl, options = {}) {
        this._events = document.getElementById('log-events');
        this._sessionInfo = document.getElementById('log-session-info');
        this._liveStats = document.getElementById('log-live-stats');
        this._logsPanel = logsPanelEl;
        this._userScrolledUp = false;
        this._lastStatus = null;
        this._crackedPasswords = new Set();
        this.MAX_EVENTS = 500;
        this.MAX_TRACKED = 10000;

        // Callback'ler — dışarıdan enjekte edilir
        this._onProgress = options.onProgress || (() => {});
        this._onExtractDone = options.onExtractDone || (() => {});

        this._events.addEventListener('scroll', () => {
            const atBottom =
                this._events.scrollHeight - this._events.scrollTop <=
                this._events.clientHeight + 50;
            this._userScrolledUp = !atBottom;
        });
    }

    // ── Main Dispatcher ──

    /** Dispatch a structured event to the appropriate renderer. */
    renderEvent(event) {
        const type = event.type;
        const d = event.data || {};

        switch (type) {
            case 'session_start':
                this._addEventCard('🚀', `Session started — Hashcat v${d.version}`, 'info');
                break;

            case 'device_info': {
                const mem = d.memory_total ? ` • ${d.memory_total} MB` : '';
                const currentName = document.getElementById('log-device-name').textContent;
                // Append if multiple devices are used
                if (currentName && !currentName.includes(d.name)) {
                    this._showSessionField('log-device-row', 'log-device-name', currentName + ', ' + d.name, 'log-device-detail', '');
                } else {
                    this._showSessionField('log-device-row', 'log-device-name', d.name, 'log-device-detail', mem);
                }
                break;
            }

            case 'hash_mode':
                this._showSessionField('log-hashmode-row', 'log-hashmode-name', d.name, 'log-hashmode-code', `m=${d.mode}`);
                break;

            case 'wordlist_file':
                this._showSessionField('log-wordlist-row', 'log-wordlist-name', d.name, null, null);
                break;

            case 'wordlist_count': {
                const el = document.getElementById('log-wordlist-detail');
                if (el) el.textContent = `${this._formatCount(d.count)} passwords`;
                document.getElementById('log-wordlist-row')?.classList.remove('hidden');
                this._sessionInfo.classList.remove('hidden');
                break;
            }

            case 'status':
                // Only add an event card when status actually changes
                if (d.status !== this._lastStatus) {
                    this._lastStatus = d.status;
                    const icon = d.status === 'Cracked' ? '✅' : d.status === 'Exhausted' ? '❌' : 'ℹ️';
                    const cls = d.status === 'Cracked' ? 'success' : d.status === 'Exhausted' ? 'error' : 'info';
                    this._addEventCard(icon, `Status: ${d.status}`, cls);
                }
                break;

            case 'speed':
                this._updateStat('log-speed', d.speed);
                break;

            case 'progress':
                this._onProgress(parseFloat(d.percent));
                break;

            case 'eta':
                this._updateStat('log-eta', d.eta);
                document.getElementById('progress-text').children[1].innerText = `ETA: ${d.eta}`;
                break;

            case 'recovered':
                this._updateStat('log-recovered', `${d.found}/${d.total}`);
                break;

            case 'hash_cracked':
                if (this._crackedPasswords.has(d.password)) {
                    break; // deduplicate
                }
                this._addCrackedPassword(d.password);
                this._addCrackedCard(d.hash, d.password);
                break;

            case 'error':
                this._addEventCard('❌', d.message, 'error');
                break;

            case 'success':
                this._addEventCard('✅', d.message, 'success');
                break;

            case 'info':
                this._addEventCard('ℹ️', d.message, 'info');
                break;

            case 'extract_done':
                this._onExtractDone(d);
                break;

            case 'separator': {
                const sep = document.createElement('div');
                sep.className = 'log-separator';
                this._events.appendChild(sep);
                break;
            }
        }

        this._trimEvents();
        this._autoScroll();
    }

    // ── Session Info ──

    _showSessionField(rowId, nameId, nameVal, detailId, detailVal) {
        const row = document.getElementById(rowId);
        if (!row) return;
        row.classList.remove('hidden');
        const nameEl = document.getElementById(nameId);
        if (nameEl) nameEl.textContent = nameVal;
        if (detailId) {
            const detailEl = document.getElementById(detailId);
            if (detailEl) detailEl.textContent = detailVal || '';
        }
        this._sessionInfo.classList.remove('hidden');
    }

    // ── Live Stats ──

    _updateStat(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
        this._liveStats.classList.remove('hidden');
    }

    // ── Event Cards ──

    _addEventCard(icon, message, level) {
        const card = document.createElement('div');
        card.className = `log-event log-event-${level}`;

        const time = document.createElement('span');
        time.className = 'log-event-time';
        time.textContent = this._getTimestamp();

        const iconEl = document.createElement('span');
        iconEl.className = 'log-event-icon';
        iconEl.textContent = icon;

        const text = document.createElement('span');
        text.className = 'log-event-text';
        text.textContent = message;

        card.appendChild(time);
        card.appendChild(iconEl);
        card.appendChild(text);
        this._events.appendChild(card);
    }

    _addCrackedCard(hash, password) {
        const card = document.createElement('div');
        card.className = 'log-event-cracked';

        const header = document.createElement('div');
        header.className = 'log-cracked-header';

        const time = document.createElement('span');
        time.className = 'log-event-time';
        time.textContent = this._getTimestamp();

        const label = document.createElement('span');
        label.className = 'log-cracked-label';
        label.textContent = '🔓 PASSWORD FOUND';

        header.appendChild(time);
        header.appendChild(label);

        const body = document.createElement('div');
        body.className = 'log-cracked-body';

        const hashEl = document.createElement('div');
        hashEl.className = 'log-cracked-hash';
        hashEl.textContent = hash;
        hashEl.title = hash;

        const pwEl = document.createElement('div');
        pwEl.className = 'log-cracked-password';
        pwEl.textContent = password;

        body.appendChild(hashEl);
        body.appendChild(pwEl);

        card.appendChild(header);
        card.appendChild(body);
        this._events.appendChild(card);
    }

    // ── Utilities ──

    _trimEvents() {
        while (this._events.childElementCount > this.MAX_EVENTS) {
            this._events.removeChild(this._events.firstChild);
        }
    }

    _autoScroll() {
        if (!this._userScrolledUp) {
            this._events.scrollTop = this._events.scrollHeight;
        }
    }

    _getTimestamp() {
        const now = new Date();
        return (
            String(now.getHours()).padStart(2, '0') + ':' +
            String(now.getMinutes()).padStart(2, '0') + ':' +
            String(now.getSeconds()).padStart(2, '0')
        );
    }

    _formatCount(n) {
        const num = parseInt(n);
        if (isNaN(num)) return n;
        if (num >= 1_000_000_000) return (num / 1_000_000_000).toFixed(1) + 'B';
        if (num >= 1_000_000) return (num / 1_000_000).toFixed(1) + 'M';
        if (num >= 1_000) return (num / 1_000).toFixed(1) + 'K';
        return num.toLocaleString();
    }

    /** Clear all events, session info, and live stats. */
    clear(resetState = false) {
        this._events.innerHTML = '';
        this._sessionInfo.classList.add('hidden');
        this._liveStats.classList.add('hidden');
        ['log-device-row', 'log-hashmode-row', 'log-wordlist-row'].forEach((id) => {
            document.getElementById(id)?.classList.add('hidden');
        });
        ['log-device-name', 'log-device-detail'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.textContent = '';
        });
        ['log-speed', 'log-eta', 'log-recovered'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.textContent = '--';
        });
        this._lastStatus = null;
        this._userScrolledUp = false;
        
        if (resetState) {
            this._crackedPasswords.clear();
        }
        
        this._onProgress(0);
        document.getElementById('progress-text').children[1].innerText = 'ETA: --:--:--';
    }

    _addCrackedPassword(key) {
        if (this._crackedPasswords.size >= this.MAX_TRACKED) {
            // En eski %10'unu sil (Set insertion order korunur)
            const toDelete = Math.floor(this.MAX_TRACKED * 0.1);
            const iter = this._crackedPasswords.values();
            for (let i = 0; i < toDelete; i++) {
                this._crackedPasswords.delete(iter.next().value);
            }
        }
        this._crackedPasswords.add(key);
    }

    /** Toggle the slide-over logs panel. */
    toggle() {
        this._logsPanel.classList.toggle('open');
    }

    /** Open the logs panel. */
    open() {
        this._logsPanel.classList.add('open');
    }
}

// ═══════════════════════════════════════════════
//  HashcatBridge
// ═══════════════════════════════════════════════

class HashcatBridge {
    /**
     * Central API call wrapper — handles the standard response envelope.
     * @returns {Promise<*>} The `data` field on success, or null on error.
     */
    async _call(method, ...args) {
        try {
            const res = await window.pywebview.api[method](...args);
            // Standard envelope: { success, data, error }
            if (res && typeof res.success !== 'undefined') {
                if (!res.success) {
                    if (res.error) showToast(res.error, 'error');
                    return null;
                }
                return res.data;
            }
            // Fallback for methods that don't return the envelope (minimize, close)
            return res;
        } catch (e) {
            console.error(`API call failed: ${method}`, e);
            showToast(`API Error: ${e.message || e}`, 'error');
            return null;
        }
    }

    detectHash(val) { return this._call('detect_hash', val); }
    extractHash() { return this._call('extract_hash'); }
    loadHashFile() { return this._call('load_hash_file'); }
    selectWordlist() { return this._call('select_wordlist'); }
    addRule() { return this._call('add_rule'); }
    startCrack(settings) { return this._call('start_crack', settings); }
    restoreCrack(session) { return this._call('restore_crack', session); }
    stopCrack() { return this._call('stop_crack'); }
    pauseCrack() { return this._call('pause_crack'); }
    checkpointCrack() { return this._call('checkpoint_crack'); }
    isRunning() { return this._call('is_running'); }
    getDevices() { return this._call('get_devices'); }
    runBenchmark(deviceId) { return this._call('run_benchmark', deviceId); }
    browseFolder() { return this._call('browse_folder'); }
    getConfig() { return this._call('get_config'); }
    saveConfig(cfg) { return this._call('save_config', cfg); }
    setToolPaths(hc, jtr) { return this._call('set_tool_paths', hc, jtr); }
    getPotfile() { return this._call('get_potfile'); }
    clearPotfile() { return this._call('clear_potfile'); }
    getWindowSize() { return this._call('get_window_size'); }
    resize(w, h) { return this._call('resize', w, h); }
    downloadHashcat() { return this._call('download_hashcat'); }
    downloadJtr() { return this._call('download_jtr'); }
    cancelDownload() { return this._call('cancel_download'); }
}

// ═══════════════════════════════════════════════
//  SettingsStore
// ═══════════════════════════════════════════════

class SettingsStore {
    constructor(bridge) {
        this._bridge = bridge;
        this._saveTimeout = null;

        // Persistent state
        this.wordlistPath = null;
        this.rulePaths = [];
        this.hashFilePath = null;
        this.hcPath = null;
        this.jtrPath = null;
    }

    /** Collect current form state into a settings object. */
    getSettingsObject() {
        return {
            hash: document.getElementById('hash-input').value.trim(),
            m_value: document.getElementById('hash-mode').value.trim(),
            wordlist: this.wordlistPath,
            rules: this.rulePaths,
            hash_file_path: this.hashFilePath,
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

    /** Debounced save — persists config 500ms after last change. */
    save() {
        const cfg = this.getSettingsObject();
        cfg.hc_path = this.hcPath;
        cfg.jtr_path = this.jtrPath;
        localStorage.setItem('shatter_settings_backup', JSON.stringify(cfg));

        if (this._saveTimeout) clearTimeout(this._saveTimeout);
        this._saveTimeout = setTimeout(async () => {
            await this._bridge.saveConfig(cfg);
            localStorage.removeItem('shatter_settings_backup');
            this._saveTimeout = null;
        }, 500);
    }

    /** Restore config from backend and populate all form fields. */
    async restore() {
        const cfg = await this._bridge.getConfig();
        if (!cfg) return null;

        if (cfg.hash) document.getElementById('hash-input').value = cfg.hash;
        if (cfg.m_value) document.getElementById('hash-mode').value = cfg.m_value;
        if (cfg.wordlist) {
            this.wordlistPath = cfg.wordlist;
            document.getElementById('wordlist-path').innerText = this.wordlistPath.split(/[\\/]/).pop();
        }
        if (cfg.rules) {
            this.rulePaths = cfg.rules;
            this.updateRuleLabel();
        }
        if (cfg.hash_file_path) {
            this.hashFilePath = cfg.hash_file_path;
            const name = this.hashFilePath.split(/[\\/]/).pop();
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
            this.hcPath = cfg.hc_path;
            document.getElementById('set-hc-path').value = this.hcPath;
            const hcBtn = document.getElementById('btn-dl-hashcat');
            if (hcBtn) hcBtn.innerHTML = hcBtn.innerHTML.replace('Download', 'Reinstall');
        }
        if (cfg.jtr_path) {
            this.jtrPath = cfg.jtr_path;
            document.getElementById('set-jtr-path').value = this.jtrPath;
            const jtrBtn = document.getElementById('btn-dl-jtr');
            if (jtrBtn) jtrBtn.innerHTML = jtrBtn.innerHTML.replace('Download', 'Reinstall');
        }

        return cfg;
    }

    /** Update the rule count/name label. */
    updateRuleLabel() {
        const lbl = document.getElementById('rule-paths');
        if (this.rulePaths.length === 0) {
            lbl.innerText = 'No rules';
        } else if (this.rulePaths.length === 1) {
            lbl.innerText = this.rulePaths[0].split(/[\\/]/).pop();
        } else {
            lbl.innerText = `${this.rulePaths.length} rules loaded`;
        }
    }

    /** Attach auto-save listeners to all form elements. */
    attachAutoSave() {
        document.querySelectorAll('input, select').forEach((el) => {
            if (el.id === 'hash-input') return; // has its own handler
            el.addEventListener('change', () => this.save());
            if (el.type === 'text' || el.type === 'number') {
                el.addEventListener('keyup', () => this.save());
            }
        });
    }
}

// ═══════════════════════════════════════════════
//  Globals & Initialization
// ═══════════════════════════════════════════════

const terminal = new TerminalManager(
    document.getElementById('logs-panel'),
    {
        onProgress: (percent) => updateProgress(percent),
        onExtractDone: (d) => {
            setButtonLoading(document.getElementById('btn-extract'), false);
            if (d.error) {
                showToast(d.error, 'error');
            } else if (d.hash) {
                document.getElementById('hash-input').value = d.hash;
                document.getElementById('hash-input').dispatchEvent(new Event('input'));
            }
        }
    }
);
const bridge = new HashcatBridge();
const store = new SettingsStore(bridge);

let isCracking = false;

// ── Expose callbacks for backend → JS ──

window.onHashcatEvent = function (event) {
    terminal.renderEvent(event);
};

window.clearHashcatOutput = function () {
    terminal.clear(true);
};

// ── Toast Notifications ──

function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.pointerEvents = 'auto';

    const iconSpan = document.createElement('span');
    iconSpan.textContent = icons[type] || 'ℹ️';

    const msgSpan = document.createElement('span');
    msgSpan.style.flex = '1';
    msgSpan.textContent = message;

    const closeBtn = document.createElement('button');
    closeBtn.className = 'toast-close';
    closeBtn.textContent = '×';
    closeBtn.onclick = () => toast.remove();

    toast.appendChild(iconSpan);
    toast.appendChild(msgSpan);
    toast.appendChild(closeBtn);
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'toastOut 0.3s ease-in forwards';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function showConfirm(message, onConfirm) {
    // Remove any existing modal
    const existing = document.getElementById('confirm-modal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'confirm-modal';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:10000;backdrop-filter:blur(4px);';

    const modal = document.createElement('div');
    modal.style.cssText = 'background:#171717;border:1px solid rgba(255,255,255,0.1);border-radius:0.75rem;padding:1.5rem;min-width:340px;max-width:420px;box-shadow:0 25px 50px rgba(0,0,0,0.5);';

    const icon = document.createElement('div');
    icon.style.cssText = 'font-size:1.5rem;margin-bottom:0.75rem;';
    icon.textContent = '\u26A0\uFE0F';

    const msg = document.createElement('p');
    msg.style.cssText = 'color:#e2e8f0;font-size:0.875rem;margin-bottom:1.25rem;line-height:1.5;';
    msg.textContent = message;

    const btnRow = document.createElement('div');
    btnRow.style.cssText = 'display:flex;gap:0.75rem;justify-content:flex-end;';

    const cancelBtn = document.createElement('button');
    cancelBtn.textContent = 'Cancel';
    cancelBtn.style.cssText = 'padding:0.5rem 1.25rem;border-radius:0.5rem;font-size:0.8rem;font-weight:500;background:#262626;border:1px solid rgba(255,255,255,0.1);color:#a1a1aa;cursor:pointer;transition:all 0.15s;';
    cancelBtn.onmouseenter = () => { cancelBtn.style.borderColor = '#737373'; cancelBtn.style.color = '#e2e8f0'; };
    cancelBtn.onmouseleave = () => { cancelBtn.style.borderColor = 'rgba(255,255,255,0.1)'; cancelBtn.style.color = '#a1a1aa'; };
    cancelBtn.onclick = () => overlay.remove();

    const confirmBtn = document.createElement('button');
    confirmBtn.textContent = 'Confirm';
    confirmBtn.style.cssText = 'padding:0.5rem 1.25rem;border-radius:0.5rem;font-size:0.8rem;font-weight:600;background:rgba(239,68,68,0.2);border:1px solid rgba(239,68,68,0.5);color:#ef4444;cursor:pointer;transition:all 0.15s;';
    confirmBtn.onmouseenter = () => { confirmBtn.style.background = 'rgba(239,68,68,0.3)'; };
    confirmBtn.onmouseleave = () => { confirmBtn.style.background = 'rgba(239,68,68,0.2)'; };
    confirmBtn.onclick = () => { overlay.remove(); onConfirm(); };

    btnRow.appendChild(cancelBtn);
    btnRow.appendChild(confirmBtn);
    modal.appendChild(icon);
    modal.appendChild(msg);
    modal.appendChild(btnRow);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Close on overlay click (outside modal)
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    // Close on Escape
    const onKey = (e) => { if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', onKey); } };
    document.addEventListener('keydown', onKey);
}

// ── Download Callbacks (called from Python backend) ──

window.onDownloadProgress = function (tool, percent, downloaded, total) {
    const bar = document.getElementById(`dl-bar-${tool}`);
    const status = document.getElementById(`dl-status-${tool}`);
    const container = document.getElementById(`dl-progress-${tool}`);

    if (container) container.classList.remove('hidden');
    if (bar) bar.style.width = `${percent}%`;

    if (status) {
        const dlMB = (downloaded / 1024 / 1024).toFixed(1);
        const totalMB = (total / 1024 / 1024).toFixed(1);
        status.textContent = `Downloading... ${dlMB} / ${totalMB} MB (${percent}%)`;
    }
};

window.onDownloadDone = function (tool, success, detail) {
    const container = document.getElementById(`dl-progress-${tool}`);
    const btn = document.getElementById(`btn-dl-${tool}`);

    if (btn) {
        btn.disabled = false;
        if (btn.dataset.originalHtml) {
            btn.innerHTML = btn.dataset.originalHtml;
            delete btn.dataset.originalHtml;
        }
    }

    if (success) {
        if (tool === 'hashcat') {
            store.hcPath = detail;
            document.getElementById('set-hc-path').value = detail;
            loadDevices();
            if (btn) btn.innerHTML = btn.innerHTML.replace('Download', 'Reinstall');
        } else {
            store.jtrPath = detail;
            document.getElementById('set-jtr-path').value = detail;
            if (btn) btn.innerHTML = btn.innerHTML.replace('Download', 'Reinstall');
        }
        store.save();
        showToast(`${tool === 'hashcat' ? 'Hashcat' : 'John the Ripper'} installed successfully!`, 'success', 5000);
        if (container) container.classList.add('hidden');
    } else {
        if (detail === 'Download cancelled.') {
            if (container) container.classList.add('hidden');
            return;
        }
        showToast(`Download failed: ${detail}`, 'error', 6000);
        if (container) {
            const status = document.getElementById(`dl-status-${tool}`);
            if (status) {
                status.textContent = 'Download failed. Check your internet connection.';
                status.style.color = '#ef4444';
            }
        }
    }
};

// ── Navigation ──

function nav(viewId) {
    document.getElementById('view-dashboard').classList.add('hidden');
    document.getElementById('view-potfile').classList.add('hidden');
    document.getElementById('view-settings').classList.add('hidden');

    document.querySelectorAll('.nav-btn').forEach((btn) => {
        btn.classList.remove(
            'bg-bgCard', 'border', 'border-borderSubtle', 'text-accent',
            'shadow-[0_0_15px_rgba(249,115,22,0.2)]'
        );
        btn.classList.add('text-textDim');
    });

    document.getElementById(`view-${viewId}`).classList.remove('hidden');

    const btn = document.getElementById(`nav-${viewId}`);
    btn.classList.remove('text-textDim');
    btn.classList.add(
        'bg-bgCard', 'border', 'border-borderSubtle', 'text-accent',
        'shadow-[0_0_15px_rgba(249,115,22,0.2)]'
    );

    if (viewId === 'potfile') refreshPotfile();
}

// ── Progress ──

function updateProgress(percent) {
    document.getElementById('progress-bar').style.width = `${percent}%`;
    document.getElementById('progress-text').children[0].innerText = `${percent.toFixed(2)}%`;
}

// ── Form Locking (Disabled State during crack) ──

const _LOCKABLE_IDS = [
    'hash-input', 'hash-mode', 'mask-input',
    'device-select', 'set-attack-mode',
];

function setFormLocked(locked) {
    // Disable/enable individual inputs
    _LOCKABLE_IDS.forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.disabled = locked;
    });

    // Lock interactive button groups
    const lockTargets = document.querySelectorAll('[data-lock-group]');
    lockTargets.forEach((el) => {
        if (locked) {
            el.classList.add('form-locked');
        } else {
            el.classList.remove('form-locked');
        }
    });
}

// ── Loading State Helpers ──

function setButtonLoading(btn, isLoading) {
    if (!btn) return;
    if (isLoading) {
        btn.disabled = true;
        btn.dataset.originalHtml = btn.innerHTML;
        // Replace content with spinner
        const text = btn.textContent.trim();
        btn.innerHTML = `<svg class="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-dasharray="31.4 31.4" stroke-linecap="round"/>
        </svg> ${text}`;
    } else {
        btn.disabled = false;
        if (btn.dataset.originalHtml) {
            btn.innerHTML = btn.dataset.originalHtml;
            delete btn.dataset.originalHtml;
        }
    }
}

// ── Dashboard Actions ──

document.getElementById('hash-input').addEventListener('input', async (e) => {
    const val = e.target.value.trim();
    if (!val) {
        document.getElementById('algo-name').innerText = 'None';
        document.getElementById('algo-name').className = 'text-white';
        return;
    }
    const res = await bridge.detectHash(val);
    if (!res) return;
    
    if (res.needs_manual_selection) {
        document.getElementById('algo-name').innerText = 'Unknown - Manual Selection Required';
        document.getElementById('algo-name').className = 'text-danger';
        document.getElementById('hash-mode').value = '';
        showToast('Hash type could not be detected. Please select or enter the mode manually.', 'warning');
    } else {
        document.getElementById('algo-name').innerText = res.algo;
        if (res.algo.includes('Unknown') || res.algo.includes('Failed')) {
            document.getElementById('algo-name').className = 'text-danger';
        } else {
            document.getElementById('algo-name').className = 'text-accent';
        }
        document.getElementById('hash-mode').value = res.m_value || '0';
    }

    store.hashFilePath = null;
    document.getElementById('hashfile-label').classList.add('hidden');
    store.save();
});

function clearHash() {
    document.getElementById('hash-input').value = '';
    document.getElementById('algo-name').innerText = 'None';
    document.getElementById('algo-name').className = 'text-white';
    document.getElementById('hash-mode').value = '0';
    store.hashFilePath = null;
    document.getElementById('hashfile-label').classList.add('hidden');
    store.save();
}

async function extractHash() {
    const btn = document.getElementById('btn-extract');
    setButtonLoading(btn, true);
    const res = await bridge.extractHash();
    if (!res || res.cancelled || res.error) {
        setButtonLoading(btn, false);
    }
    // Success path waits for "extract_done" event.
}

async function loadHashFile() {
    const btn = document.getElementById('btn-load-hashfile');
    setButtonLoading(btn, true);
    const res = await bridge.loadHashFile();
    setButtonLoading(btn, false);
    if (res && res.path) {
        store.hashFilePath = res.path;
        document.getElementById('hash-input').value = '';
        const name = store.hashFilePath.split(/[\\/]/).pop();
        const lbl = document.getElementById('hashfile-label');
        lbl.innerText = `📋 Loaded File: ${name}`;
        lbl.classList.remove('hidden');
        document.getElementById('algo-name').innerText = 'File provided (manual mode needed)';
        document.getElementById('algo-name').className = 'text-textDim';
        store.save();
    }
}

async function selectWordlist() {
    const btn = document.getElementById('btn-wordlist');
    setButtonLoading(btn, true);
    const res = await bridge.selectWordlist();
    setButtonLoading(btn, false);
    if (res && res.path) {
        store.wordlistPath = res.path;
        document.getElementById('wordlist-path').innerText = res.path.split(/[\\/]/).pop();
        store.save();
    }
}

async function addRule() {
    const btn = document.getElementById('btn-add-rule');
    setButtonLoading(btn, true);
    const res = await bridge.addRule();
    setButtonLoading(btn, false);
    if (res && res.path) {
        store.rulePaths.push(res.path);
        store.updateRuleLabel();
        store.save();
    }
}

function clearRules() {
    store.rulePaths = [];
    store.updateRuleLabel();
    store.save();
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
    store.save();
});

// ── Cracked Reveal ──

function dismissReveal() {
    document.getElementById('cracked-reveal').classList.add('hidden');
    document.getElementById('btn-crack').style.display = 'flex';
}

window.onCrackDone = async function () {
    isCracking = false;
    setFormLocked(false);
    document.getElementById('process-controls').style.display = 'none';

    // Check potfile for the big reveal!
    const targetHash = document.getElementById('hash-input').value.trim();
    if (targetHash) {
        const entries = await bridge.getPotfile();
        if (entries) {
            const found = entries.find(
                (e) => e.hash.includes(targetHash) || targetHash.includes(e.hash)
            );
            if (found) {
                document.getElementById('cracked-password-display').innerText = found.password;
                document.getElementById('btn-crack').style.display = 'none';
                document.getElementById('btn-restore').style.display = 'none';
                document.getElementById('cracked-reveal').classList.remove('hidden');
                return;
            }
        }
    }

    document.getElementById('btn-crack').style.display = 'flex';
    document.getElementById('btn-restore').style.display = 'none';
};

// ── Execution ──

async function startCrack() {
    if (!store.hcPath) {
        showToast('Hashcat path not set! Please configure it in Settings.', 'warning');
        nav('settings');
        return;
    }
    const settings = store.getSettingsObject();
    if (!settings.hash && !settings.hash_file_path) {
        showToast('Please provide a target hash or hash file.', 'warning');
        return;
    }

    isCracking = true;
    setFormLocked(true);
    document.getElementById('btn-crack').style.display = 'none';
    document.getElementById('process-controls').style.display = 'flex';
    terminal.open();

    if (settings.session_name) {
        document.getElementById('btn-restore').style.display = 'flex';
    }

    const res = await bridge.startCrack(settings);
    if (!res) {
        window.onCrackDone();
        return;
    }
}

async function restoreCrack() {
    const session = document.getElementById('set-session').value.trim();
    if (!session) {
        showToast('Please set a Session Name in settings to restore.', 'warning');
        return;
    }
    isCracking = true;
    setFormLocked(true);
    document.getElementById('btn-crack').style.display = 'none';
    document.getElementById('process-controls').style.display = 'flex';
    terminal.open();

    const res = await bridge.restoreCrack(session);
    if (!res) {
        window.onCrackDone();
        return;
    }
}

async function stopCrack() {
    try {
        await bridge.stopCrack();
    } catch (e) {
        console.error('stopCrack failed:', e);
    }

    const POLL_INTERVAL = 2000;
    const MAX_WAIT = 15000;
    let waited = 0;

    const watchdog = setInterval(async () => {
        waited += POLL_INTERVAL;
        
        try {
            const status = await bridge.isRunning();
            if (!status) {
                clearInterval(watchdog);
                if (isCracking) window.onCrackDone();
                return;
            }
        } catch (e) {}

        if (waited >= MAX_WAIT) {
            clearInterval(watchdog);
            console.warn('Backend unresponsive after 15s — forcing UI reset');
            if (isCracking) window.onCrackDone();
        }
    }, POLL_INTERVAL);
}

async function pauseCrack() {
    const btn = document.getElementById('btn-pause');
    const res = await bridge.pauseCrack();
    if (res && res.paused) {
        btn.innerText = 'Resume';
        btn.classList.add('bg-accent/20', 'text-accent', 'border-accent/50');
    } else {
        btn.innerText = 'Pause';
        btn.classList.remove('bg-accent/20', 'text-accent', 'border-accent/50');
    }
}

async function checkpointCrack() {
    await bridge.checkpointCrack();
}

async function runBenchmark() {
    if (isCracking) return;
    const device = document.getElementById('device-select').value;
    terminal.open();
    await bridge.runBenchmark(device);
}

// ── Settings ──

async function browseFolder(type) {
    const res = await bridge.browseFolder();
    if (res && res.path) {
        if (type === 'hc') {
            store.hcPath = res.path;
            document.getElementById('set-hc-path').value = store.hcPath;
        } else {
            store.jtrPath = res.path;
            document.getElementById('set-jtr-path').value = store.jtrPath;
        }
        await bridge.setToolPaths(store.hcPath || '', store.jtrPath || '');
        store.save();
        if (type === 'hc') loadDevices();
    }
}

async function downloadTool(tool) {
    const btn = document.getElementById(`btn-dl-${tool}`);
    setButtonLoading(btn, true);

    if (tool === 'hashcat') {
        await bridge.downloadHashcat();
    } else {
        await bridge.downloadJtr();
    }
    // Button stays in loading state until onDownloadDone callback fires
}

async function cancelDownload(tool) {
    const btn = document.getElementById(`btn-dl-${tool}`);
    const status = document.getElementById(`dl-status-${tool}`);
    if (status) status.textContent = 'Cancelling...';
    await bridge.cancelDownload();
}

// ── Potfile ──

async function refreshPotfile() {
    const tbody = document.getElementById('potfile-tbody');
    const emptyState = document.getElementById('potfile-empty-state');

    tbody.innerHTML =
        '<tr><td colspan="2" class="p-6 text-center text-textDim">Loading...</td></tr>';
    if (emptyState) emptyState.classList.add('hidden');

    const entries = await bridge.getPotfile();
    tbody.innerHTML = '';

    if (!entries || entries.length === 0) {
        // Show empty state
        if (emptyState) emptyState.classList.remove('hidden');
        return;
    }

    if (emptyState) emptyState.classList.add('hidden');

    entries.forEach((e) => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-bgCardHover transition-colors';

        const tdHash = document.createElement('td');
        tdHash.className = 'px-6 py-3 text-textDim truncate max-w-xs';
        tdHash.title = e.hash;
        tdHash.textContent = e.hash;

        const tdPass = document.createElement('td');
        tdPass.className = 'px-6 py-3';
        const pwSpan = document.createElement('span');
        pwSpan.className =
            'select-text bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1 rounded-md font-mono font-bold tracking-wide';
        pwSpan.textContent = e.password;
        tdPass.appendChild(pwSpan);

        tr.appendChild(tdHash);
        tr.appendChild(tdPass);
        tbody.appendChild(tr);
    });
}

async function clearPotfile() {
    showConfirm('Are you sure you want to clear the potfile? This cannot be undone.', async () => {
        await bridge.clearPotfile();
        refreshPotfile();
        showToast('Potfile cleared.', 'success');
    });
}

// ── Terminal Shortcuts ──

function toggleLogs() {
    terminal.toggle();
}

function clearTerminal() {
    terminal.clear(false);
}

// ── Device Loading ──

async function loadDevices() {
    const sel = document.getElementById('device-select');
    if (!store.hcPath) return;

    try {
        const devices = await bridge.getDevices();

        if (!devices || devices.length === 0) {
            sel.innerHTML = '<option value="" disabled selected>No devices detected</option>';
            sel.disabled = true;
            return;
        }

        sel.disabled = false;
        sel.innerHTML = devices
            .map(d => `<option value="${d.id}">${d.name}</option>`)
            .join('');
    } catch (e) {
        console.error('Failed to load devices:', e);
        sel.innerHTML = '<option value="" disabled selected>Failed to load devices</option>';
        sel.disabled = true;
    }
}

// ── Initialization ──

window.addEventListener('pywebviewready', async function () {
    const backup = localStorage.getItem('shatter_settings_backup');
    if (backup) {
        try {
            await bridge.saveConfig(JSON.parse(backup));
            localStorage.removeItem('shatter_settings_backup');
        } catch (e) {
            console.warn('Failed to recover settings backup:', e);
        }
    }

    const cfg = await store.restore();
    if (cfg) {
        await bridge.setToolPaths(store.hcPath || '', store.jtrPath || '');

        // Trigger mode UI update
        document.getElementById('set-attack-mode').dispatchEvent(new Event('change'));
        // Trigger hash detect UI update
        if (cfg.hash && !cfg.hash_file_path) {
            document.getElementById('hash-input').dispatchEvent(new Event('input'));
        }

        if (store.hcPath) loadDevices();

        if (cfg.session_name) {
            document.getElementById('btn-restore').style.display = 'flex';
        }
    }

    store.attachAutoSave();

    // Auto-redirect to settings if Hashcat not configured
    if (!store.hcPath) {
        setTimeout(() => {
            nav('settings');
            showToast('Welcome to Shatter! Please configure Hashcat to get started.', 'warning', 6000);
        }, 300);
    }
});

// ── Window Resizing ──

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
        const size = await bridge.getWindowSize();
        if (!size) return;
        initialWidth = size.width;
        initialHeight = size.height;
        document.body.style.cursor =
            dir === 'e' ? 'e-resize' : dir === 's' ? 's-resize' : 'se-resize';
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
                bridge.resize(newW, newH);
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
