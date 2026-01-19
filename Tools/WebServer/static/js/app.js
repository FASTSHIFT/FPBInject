// FPBInject Hub JavaScript

let isConnected = false;
let logInterval = null;
let lastLogIndex = 0;

// xterm.js terminal instance
let term = null;
let fitAddon = null;
let currentLine = '';
let sendingCommand = false;

// Raw terminal instance
let rawTerm = null;
let rawFitAddon = null;
let lastRawLogIndex = 0;
let currentTerminalTab = 'tool';

// File browser state
let browserCallback = null;
let browserFilter = '';
let browserSelectedPath = '';

// ===================== Utility Functions =====================

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ===================== Section Toggle =====================

function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.classList.toggle('collapsed');
        const collapsed = section.classList.contains('collapsed');
        localStorage.setItem('section_' + sectionId, collapsed ? 'collapsed' : 'expanded');
    }
}

function loadSectionStates() {
    const sections = document.querySelectorAll('.section-collapsible');
    sections.forEach(section => {
        const state = localStorage.getItem('section_' + section.id);
        if (state === 'collapsed') {
            section.classList.add('collapsed');
        }
    });
}

// ===================== API Helper =====================

async function api(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };
    if (method !== 'GET') {
        options.body = JSON.stringify(data || {});
    }

    try {
        const response = await fetch('/api' + endpoint, options);
        return await response.json();
    } catch (e) {
        return { success: false, error: e.message };
    }
}

// ===================== Initialization =====================

document.addEventListener('DOMContentLoaded', async () => {
    loadSectionStates();
    refreshPorts();
    await refreshStatus();
    initTerminal();
    initRawTerminal();
    startLogPolling();
    loadPatchSource();
    setupConfigAutoSave();
});

// ===================== Terminal Functions (xterm.js) =====================

function initTerminal() {
    const container = document.getElementById('terminal-container');
    if (!container || term) return;

    term = new Terminal({
        theme: {
            background: '#1e1e1e',
            foreground: '#d4d4d4',
            cursor: '#00d4ff',
            cursorAccent: '#1e1e1e',
            cyan: '#00d4ff',
            green: '#2ed573',
            red: '#ff4757',
            yellow: '#ffa502',
        },
        fontFamily: "'Consolas', 'Monaco', monospace",
        fontSize: 14,
        cursorBlink: true,
        cursorStyle: 'bar',
        scrollback: 5000,
    });

    fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(container);
    fitAddon.fit();

    window.addEventListener('resize', () => {
        if (fitAddon) fitAddon.fit();
    });

    term.onData(data => {
        if (data === '\r') {
            term.write('\r\n');
            if (currentLine.trim()) {
                sendTerminalCommand(currentLine);
            }
            currentLine = '';
        } else if (data === '\x7f' || data === '\b') {
            if (currentLine.length > 0) {
                currentLine = currentLine.slice(0, -1);
                term.write('\b \b');
            }
        } else if (data === '\x03') {
            currentLine = '';
            term.write('^C\r\n');
        } else if (data >= ' ' || data === '\t') {
            currentLine += data;
            term.write(data);
        }
    });

    term.writeln('\x1b[36m[FPBInject Terminal]\x1b[0m Ready.');
    term.writeln('');
}

function initRawTerminal() {
    const container = document.getElementById('raw-terminal-container');
    if (!container || rawTerm) return;

    rawTerm = new Terminal({
        theme: {
            background: '#0d1117',
            foreground: '#c9d1d9',
            cursor: '#58a6ff',
            cursorAccent: '#0d1117',
            cyan: '#58a6ff',
            green: '#3fb950',
            red: '#f85149',
            yellow: '#d29922',
        },
        fontFamily: "'Consolas', 'Monaco', monospace",
        fontSize: 13,
        cursorBlink: false,
        disableStdin: true,
        scrollback: 10000,
    });

    rawFitAddon = new FitAddon.FitAddon();
    rawTerm.loadAddon(rawFitAddon);
    rawTerm.open(container);
    rawFitAddon.fit();

    window.addEventListener('resize', () => {
        if (rawFitAddon) rawFitAddon.fit();
    });

    rawTerm.writeln('\x1b[36m[Raw Serial Log]\x1b[0m TX/RX communication log.');
    rawTerm.writeln('');
}

function switchTerminalTab(tab) {
    currentTerminalTab = tab;
    
    const toolPanel = document.getElementById('terminalPanelTool');
    const rawPanel = document.getElementById('terminalPanelRaw');
    const tabBtnTool = document.getElementById('tabBtnTool');
    const tabBtnRaw = document.getElementById('tabBtnRaw');

    if (tab === 'tool') {
        toolPanel.style.display = 'block';
        rawPanel.style.display = 'none';
        tabBtnTool.classList.add('active');
        tabBtnRaw.classList.remove('active');
        if (fitAddon) fitAddon.fit();
    } else {
        toolPanel.style.display = 'none';
        rawPanel.style.display = 'block';
        tabBtnTool.classList.remove('active');
        tabBtnRaw.classList.add('active');
        if (rawFitAddon) rawFitAddon.fit();
    }
}

function clearCurrentTerminal() {
    if (currentTerminalTab === 'tool') {
        clearTerminal();
    } else {
        clearRawTerminal();
    }
}

async function sendTerminalCommand(command) {
    if (!command || sendingCommand) return;
    sendingCommand = true;
    try {
        await api('/command', 'POST', { command });
    } finally {
        setTimeout(() => { sendingCommand = false; }, 50);
    }
}

function clearTerminal() {
    if (term) {
        term.clear();
        api('/log/clear', 'POST');
        lastLogIndex = 0;
    }
}

function clearRawTerminal() {
    if (rawTerm) {
        rawTerm.clear();
        api('/raw_log/clear', 'POST');
        lastRawLogIndex = 0;
    }
}

// ===================== Log Functions =====================

let fetchingLogs = false;

function startLogPolling() {
    if (logInterval) clearInterval(logInterval);
    logInterval = setInterval(fetchLogs, 50);
}

async function fetchLogs() {
    if (fetchingLogs) return;
    fetchingLogs = true;

    try {
        // Fetch tool logs
        const result = await api('/log?since=' + lastLogIndex);
        if (result.success) {
            if (result.logs && result.logs.length > 0) {
                result.logs.forEach(entry => {
                    if (term && entry.dir === 'RX') {
                        let text = entry.data;
                        if (text && text.trim()) {
                            term.write(text);
                        }
                    }
                });
            }
            lastLogIndex = result.next_index;
        }

        // Fetch raw serial logs (TX/RX)
        const rawResult = await api('/raw_log?since=' + lastRawLogIndex);
        if (rawResult.success) {
            if (rawResult.logs && rawResult.logs.length > 0) {
                rawResult.logs.forEach(entry => {
                    if (rawTerm) {
                        const timestamp = new Date(entry.time * 1000).toLocaleTimeString();
                        if (entry.dir === 'TX') {
                            rawTerm.writeln(`\x1b[33m[${timestamp}] TX:\x1b[0m ${entry.data}`);
                        } else {
                            // RX can be multiline, display each line
                            const lines = entry.data.split('\n');
                            lines.forEach((line, idx) => {
                                if (line.trim() || idx === 0) {
                                    if (idx === 0) {
                                        rawTerm.writeln(`\x1b[36m[${timestamp}] RX:\x1b[0m ${line}`);
                                    } else {
                                        rawTerm.writeln(`           ${line}`);
                                    }
                                }
                            });
                        }
                    }
                });
            }
            lastRawLogIndex = rawResult.next_index;
        }
    } finally {
        fetchingLogs = false;
    }
}

// ===================== Connection Functions =====================

async function refreshPorts() {
    const result = await api('/ports');
    const select = document.getElementById('portSelect');
    select.innerHTML = '<option value="">选择串口...</option>';

    if (result.success && result.ports) {
        result.ports.forEach(port => {
            const opt = document.createElement('option');
            opt.value = port.device;
            opt.textContent = `${port.device} - ${port.description}`;
            select.appendChild(opt);
        });
    }
}

async function toggleConnect() {
    if (isConnected) {
        await disconnect();
    } else {
        await connect();
    }
}

async function connect() {
    const port = document.getElementById('portSelect').value;
    const baudrate = parseInt(document.getElementById('baudrate').value) || 115200;

    if (!port) {
        alert('请选择串口');
        return;
    }

    const btn = document.getElementById('connectBtn');
    btn.disabled = true;
    btn.textContent = '连接中...';

    const result = await api('/connect', 'POST', { port, baudrate });

    if (result.success) {
        isConnected = true;
        updateConnectionUI(true);
        if (term) {
            term.writeln(`\x1b[32m[Connected to ${port}]\x1b[0m`);
        }
    } else {
        alert('连接失败: ' + result.error);
    }

    btn.disabled = false;
    btn.innerHTML = isConnected ? '<span class="btn-icon-left">🔌</span> 断开' : '<span class="btn-icon-left">⚡</span> 连接';
}

async function disconnect() {
    const result = await api('/disconnect', 'POST');

    if (result.success) {
        isConnected = false;
        nuttxModeActive = false;
        updateConnectionUI(false);
        updateNuttxModeUI();
        if (term) {
            term.writeln('\x1b[33m[Disconnected]\x1b[0m');
        }
    }

    document.getElementById('connectBtn').innerHTML = '<span class="btn-icon-left">⚡</span> 连接';
}

function updateConnectionUI(connected) {
    const indicator = document.getElementById('connectionIndicator');
    const status = document.getElementById('connectionStatus');
    const btn = document.getElementById('connectBtn');

    if (connected) {
        indicator.className = 'status-indicator connected';
        status.className = 'status-text connected';
        status.textContent = '已连接';
        btn.innerHTML = '<span class="btn-icon-left">🔌</span> 断开';
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-danger');
    } else {
        indicator.className = 'status-indicator disconnected';
        status.className = 'status-text disconnected';
        status.textContent = '未连接';
        btn.innerHTML = '<span class="btn-icon-left">⚡</span> 连接';
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-primary');
    }
}

async function refreshStatus() {
    const result = await api('/status');
    if (result.success) {
        isConnected = result.connected;
        updateConnectionUI(result.connected);

        // Update form fields
        if (result.port) {
            document.getElementById('portSelect').value = result.port;
        }
        if (result.baudrate) {
            document.getElementById('baudrate').value = result.baudrate;
        }
        if (result.elf_path) {
            document.getElementById('elfPath').value = result.elf_path;
        }
        if (result.compile_commands_path) {
            document.getElementById('compileCommandsPath').value = result.compile_commands_path;
        }
        if (result.toolchain_path) {
            document.getElementById('toolchainPath').value = result.toolchain_path;
        }
        if (result.patch_mode) {
            document.getElementById('patchMode').value = result.patch_mode;
        }
        if (result.watch_dirs) {
            document.getElementById('watchDirs').value = result.watch_dirs.join('\n');
        }
        if (result.auto_compile !== undefined) {
            document.getElementById('autoCompile').checked = result.auto_compile;
            // Show auto inject panel if auto_compile is enabled
            if (result.auto_compile) {
                document.getElementById('autoInjectPanel').style.display = 'block';
            }
        }

        // Update injection status
        updateInjectStatus(result);

        // Load symbols if ELF path is set
        if (result.elf_path) {
            loadSymbols();
        }
    }
}

function updateInjectStatus(status) {
    const badge = document.getElementById('injectBadge');
    const targetDisplay = document.getElementById('targetFuncDisplay');
    const funcDisplay = document.getElementById('injectFuncDisplay');
    const timeDisplay = document.getElementById('injectTimeDisplay');

    if (status.inject_active) {
        badge.textContent = '已激活';
        badge.className = 'panel-badge active';
        targetDisplay.textContent = status.last_inject_target || '-';
        funcDisplay.textContent = status.last_inject_func || '-';
        if (status.last_inject_time) {
            const date = new Date(status.last_inject_time * 1000);
            timeDisplay.textContent = date.toLocaleTimeString();
        }
    } else {
        badge.textContent = '未激活';
        badge.className = 'panel-badge';
        targetDisplay.textContent = '-';
        funcDisplay.textContent = '-';
        timeDisplay.textContent = '-';
    }
}

// ===================== Configuration Functions =====================

function setupConfigAutoSave() {
    // 串口选择改变时自动保存
    document.getElementById('portSelect').addEventListener('change', function() {
        if (this.value) {
            api('/config', 'POST', { port: this.value });
        }
    });

    // 波特率改变时自动保存
    document.getElementById('baudrate').addEventListener('change', function() {
        const baudrate = parseInt(this.value);
        if (baudrate) {
            api('/config', 'POST', { baudrate: baudrate });
        }
    });
}

async function saveConfig() {
    const config = {
        elf_path: document.getElementById('elfPath').value,
        compile_commands_path: document.getElementById('compileCommandsPath').value,
        toolchain_path: document.getElementById('toolchainPath').value,
        patch_mode: document.getElementById('patchMode').value,
        watch_dirs: document.getElementById('watchDirs').value.split('\n').filter(d => d.trim()),
        auto_compile: document.getElementById('autoCompile').checked,
    };

    const result = await api('/config', 'POST', config);
    if (result.success) {
        if (term) {
            term.writeln('\x1b[32m[Config saved]\x1b[0m');
        }
        // Reload symbols
        loadSymbols();
    } else {
        alert('保存配置失败: ' + result.error);
    }
}

// ===================== FPB Operations =====================

async function fpbPing() {
    if (!isConnected) {
        alert('请先连接设备');
        return;
    }

    const result = await api('/fpb/ping', 'POST');
    if (result.success) {
        if (term) {
            term.writeln('\x1b[32m[Ping OK]\x1b[0m ' + (result.message || ''));
        }
    } else {
        if (term) {
            term.writeln('\x1b[31m[Ping Failed]\x1b[0m ' + (result.message || result.error || ''));
        }
    }
}

async function fpbInfo() {
    if (!isConnected) {
        alert('请先连接设备');
        return;
    }

    const result = await api('/fpb/info');
    if (result.success && result.info) {
        const info = result.info;
        if (term) {
            term.writeln('\x1b[36m[Device Info]\x1b[0m');
            if (info.base !== undefined) {
                term.writeln(`  Base: 0x${info.base.toString(16).toUpperCase()}`);
            }
            if (info.size !== undefined) {
                term.writeln(`  Size: ${info.size} bytes`);
            }
            if (info.used !== undefined) {
                term.writeln(`  Used: ${info.used} bytes`);
            }
        }
    } else {
        if (term) {
            term.writeln('\x1b[31m[Info Failed]\x1b[0m ' + (result.error || ''));
        }
    }
}

async function fpbUnpatch() {
    if (!isConnected) {
        alert('请先连接设备');
        return;
    }

    const result = await api('/fpb/unpatch', 'POST', { comp: 0 });
    if (result.success) {
        if (term) {
            term.writeln('\x1b[33m[Patch Cleared]\x1b[0m');
        }
        updateInjectStatus({ inject_active: false });
    } else {
        if (term) {
            term.writeln('\x1b[31m[Unpatch Failed]\x1b[0m ' + (result.message || result.error || ''));
        }
    }
}

// NuttX Interactive Mode state - 简单开关，控制是否在命令前加 -ni 参数
let nuttxModeActive = false;

function toggleNuttxMode() {
    nuttxModeActive = !nuttxModeActive;
    updateNuttxModeUI();
    if (term) {
        if (nuttxModeActive) {
            term.writeln('\x1b[36m[NuttX Mode]\x1b[0m 已启用 NuttX 交互模式 (-ni)');
        } else {
            term.writeln('\x1b[33m[NuttX Mode]\x1b[0m 已禁用 NuttX 交互模式');
        }
    }
}

function updateNuttxModeUI() {
    const btn = document.getElementById('nuttxModeBtn');
    if (btn) {
        if (nuttxModeActive) {
            btn.textContent = 'NuttX 模式 ✓';
            btn.classList.remove('btn-secondary');
            btn.classList.add('btn-success');
        } else {
            btn.textContent = 'NuttX 交互模式';
            btn.classList.remove('btn-success');
            btn.classList.add('btn-secondary');
        }
    }
}

// ===================== Symbol Functions =====================

async function loadSymbols() {
    const result = await api('/symbols?limit=50');
    if (result.success) {
        renderSymbolList(result.symbols);
    }
}

async function reloadSymbols() {
    const result = await api('/symbols/reload', 'POST');
    if (result.success) {
        if (term) {
            term.writeln(`\x1b[32m[Loaded ${result.count} symbols]\x1b[0m`);
        }
        loadSymbols();
    } else {
        alert('加载符号失败: ' + result.error);
    }
}

async function searchSymbols() {
    const query = document.getElementById('symbolSearch').value;
    const result = await api('/symbols?q=' + encodeURIComponent(query) + '&limit=50');
    if (result.success) {
        renderSymbolList(result.symbols);
    }
}

function renderSymbolList(symbols) {
    const list = document.getElementById('symbolList');
    if (!symbols || symbols.length === 0) {
        list.innerHTML = '<div class="symbol-hint">未找到匹配的符号</div>';
        return;
    }

    list.innerHTML = '';
    symbols.forEach(sym => {
        const item = document.createElement('div');
        item.className = 'symbol-item';
        item.onclick = () => selectSymbol(sym.name);
        item.innerHTML = `<span class="symbol-name">${sym.name}</span><span class="symbol-addr">${sym.addr}</span>`;
        list.appendChild(item);
    });
}

function selectSymbol(name) {
    document.getElementById('targetFunc').value = name;
    // Highlight selected
    document.querySelectorAll('.symbol-item').forEach(item => {
        item.classList.remove('selected');
        if (item.querySelector('.symbol-name').textContent === name) {
            item.classList.add('selected');
        }
    });
}

// ===================== Patch Source Functions =====================

async function loadPatchSource() {
    const result = await api('/patch/source');
    if (result.success) {
        document.getElementById('patchSource').value = result.content || '';
    }
}

async function generatePatch() {
    const targetFunc = document.getElementById('targetFunc').value;
    if (!targetFunc) {
        alert('请先选择目标函数');
        return;
    }

    const result = await api('/patch/generate', 'POST', { target_func: targetFunc });
    if (result.success) {
        document.getElementById('patchSource').value = result.content;
    } else {
        alert('生成模板失败: ' + result.error);
    }
}

async function loadPatchFromFile() {
    browseFile('patchSourcePath', '.cpp,.c', async (path) => {
        const result = await api('/config', 'POST', { patch_source_path: path });
        if (result.success) {
            const sourceResult = await api('/patch/source');
            if (sourceResult.success) {
                document.getElementById('patchSource').value = sourceResult.content;
            }
        }
    });
}

async function savePatchToFile() {
    const content = document.getElementById('patchSource').value;
    const result = await api('/patch/source', 'POST', { content, save_to_file: true });
    if (result.success) {
        if (term) {
            term.writeln('\x1b[32m[Patch saved to file]\x1b[0m');
        }
    } else {
        alert('保存失败: ' + result.error);
    }
}

// ===================== Injection Functions =====================

async function performInject() {
    const targetFunc = document.getElementById('targetFunc').value;
    const sourceContent = document.getElementById('patchSource').value;
    const patchMode = document.getElementById('patchMode').value;

    if (!targetFunc) {
        alert('请选择目标函数');
        return;
    }
    if (!sourceContent.trim()) {
        alert('请输入 patch 源代码');
        return;
    }
    if (!isConnected) {
        alert('请先连接设备');
        return;
    }

    const btn = document.getElementById('injectBtn');
    const progress = document.getElementById('injectProgress');
    const progressFill = document.getElementById('injectProgressFill');
    const progressText = document.getElementById('injectProgressText');

    btn.disabled = true;
    progress.style.display = 'flex';
    progressText.textContent = '编译中...';
    progressFill.style.width = '30%';

    const result = await api('/fpb/inject', 'POST', {
        source_content: sourceContent,
        target_func: targetFunc,
        patch_mode: patchMode,
        nuttx_mode: nuttxModeActive,
    });

    if (result.success) {
        progressFill.style.width = '100%';
        progressText.textContent = '注入成功!';

        if (term) {
            term.writeln('\x1b[32m[Injection Successful]\x1b[0m');
            term.writeln(`  Target: ${targetFunc} @ ${result.target_addr}`);
            term.writeln(`  Inject: ${result.inject_func} @ ${result.inject_addr}`);
            term.writeln(`  Size: ${result.code_size} bytes`);
            term.writeln(`  Compile: ${result.compile_time}s, Upload: ${result.upload_time}s`);
            term.writeln(`  Mode: ${result.patch_mode}${nuttxModeActive ? ' (NuttX)' : ''}`);
        }

        // 更新 Patch 预览
        refreshPatchPreview();

        updateInjectStatus({
            inject_active: true,
            last_inject_target: targetFunc,
            last_inject_func: result.inject_func,
            last_inject_time: Date.now() / 1000,
        });

        setTimeout(() => {
            progress.style.display = 'none';
        }, 2000);
    } else {
        progressText.textContent = '注入失败';
        progressFill.style.width = '0%';

        if (term) {
            term.writeln('\x1b[31m[Injection Failed]\x1b[0m');
            term.writeln('  ' + (result.error || 'Unknown error'));
        }

        alert('注入失败: ' + (result.error || 'Unknown error'));

        setTimeout(() => {
            progress.style.display = 'none';
        }, 3000);
    }

    btn.disabled = false;
}

// ===================== Patch Preview Functions =====================

async function refreshPatchPreview() {
    const sourceContent = document.getElementById('patchSource').value;
    const previewEl = document.getElementById('patchPreviewContent');

    if (!sourceContent.trim()) {
        previewEl.textContent = '请先输入 patch 源代码...';
        return;
    }

    previewEl.textContent = '编译中...';

    const result = await api('/patch/preview', 'POST', {
        source_content: sourceContent,
    });

    if (result.success) {
        previewEl.textContent = result.preview;
    } else {
        previewEl.textContent = `编译错误:\n${result.error || 'Unknown error'}`;
    }
}

function copyPatchContent() {
    const previewEl = document.getElementById('patchPreviewContent');
    const content = previewEl.textContent;

    navigator.clipboard.writeText(content).then(() => {
        if (term) {
            term.writeln('\x1b[32m[Copied]\x1b[0m Patch 内容已复制到剪贴板');
        }
    }).catch(err => {
        console.error('Copy failed:', err);
        alert('复制失败');
    });
}

// ===================== File Watcher Functions =====================

async function toggleWatcher() {
    const enabled = document.getElementById('watcherEnable').checked;

    if (enabled) {
        const dirs = document.getElementById('watchDirs').value.split('\n').filter(d => d.trim());
        if (dirs.length === 0) {
            alert('请先设置监控目录');
            document.getElementById('watcherEnable').checked = false;
            return;
        }

        const result = await api('/watch/start', 'POST', { dirs });
        if (!result.success) {
            alert('启动文件监控失败: ' + result.error);
            document.getElementById('watcherEnable').checked = false;
        }
    } else {
        await api('/watch/stop', 'POST');
    }

    refreshWatchStatus();
}

async function refreshWatchStatus() {
    const result = await api('/watch/status');
    if (result.success) {
        document.getElementById('watcherEnable').checked = result.watching;
        renderChangeList(result.pending_changes);
    }
}

async function refreshAutoInjectStatus() {
    // This function is now only called from onAutoCompileChange and init
    // The main polling is done by refreshAutoInjectStatusWithLogging
    const autoCompileEnabled = document.getElementById('autoCompile').checked;
    const panel = document.getElementById('autoInjectPanel');
    
    if (!autoCompileEnabled) {
        panel.style.display = 'none';
    }
}

async function resetAutoInjectStatus() {
    await api('/watch/auto_inject_reset', 'POST');
    document.getElementById('autoInjectPanel').style.display = 'none';
}

function renderChangeList(changes) {
    const list = document.getElementById('changeList');
    if (!changes || changes.length === 0) {
        list.innerHTML = '<div class="change-hint">无待处理的文件变化</div>';
        return;
    }

    list.innerHTML = '';
    changes.forEach(change => {
        const item = document.createElement('div');
        item.className = 'change-item';
        item.innerHTML = `
            <span class="change-type ${change.type}">${change.type}</span>
            <span class="change-path">${change.path}</span>
        `;
        list.appendChild(item);
    });
}

async function clearChanges() {
    await api('/watch/clear', 'POST');
    refreshWatchStatus();
}

async function applyChanges() {
    // Reload patch source if it's being watched
    await loadPatchSource();
    // Re-inject
    await performInject();
    // Clear changes
    await clearChanges();
}

function onAutoCompileChange() {
    const enabled = document.getElementById('autoCompile').checked;
    api('/config', 'POST', { auto_compile: enabled });
    
    // Show/hide auto inject panel
    const panel = document.getElementById('autoInjectPanel');
    if (enabled) {
        panel.style.display = 'block';
        if (term) {
            term.writeln('\x1b[36m[Auto Inject]\x1b[0m 已启用自动编译注入');
        }
    } else {
        panel.style.display = 'none';
        resetAutoInjectStatus();
        if (term) {
            term.writeln('\x1b[36m[Auto Inject]\x1b[0m 已禁用自动编译注入');
        }
    }
}

// ===================== File Browser Functions =====================

function browseFile(inputId, filter, callback) {
    browserCallback = callback || ((path) => {
        document.getElementById(inputId).value = path;
    });
    browserFilter = filter || '';
    browserSelectedPath = '';

    // Get current value as starting path
    const currentValue = document.getElementById(inputId).value;
    const startPath = currentValue ? getDirectory(currentValue) : '/';

    openFileBrowser(startPath);
}

function browseDir(inputId) {
    browserCallback = (path) => {
        document.getElementById(inputId).value = path;
    };
    browserFilter = '';
    browserSelectedPath = '';

    const currentValue = document.getElementById(inputId).value;
    const startPath = currentValue || '/';

    openFileBrowser(startPath);
}

function getDirectory(path) {
    const lastSlash = path.lastIndexOf('/');
    if (lastSlash > 0) {
        return path.substring(0, lastSlash);
    }
    return '/';
}

async function openFileBrowser(path) {
    const modal = document.getElementById('fileBrowserModal');
    modal.style.display = 'flex';
    await navigateTo(path);
}

function closeFileBrowser() {
    const modal = document.getElementById('fileBrowserModal');
    modal.style.display = 'none';
    browserCallback = null;
}

async function navigateTo(path) {
    const filterParam = browserFilter ? `&filter=${encodeURIComponent(browserFilter)}` : '';
    const result = await api(`/browse?path=${encodeURIComponent(path)}${filterParam}`);

    if (!result.success) {
        alert('无法访问路径: ' + result.error);
        return;
    }

    document.getElementById('browserPath').value = result.path;

    const list = document.getElementById('fileList');
    list.innerHTML = '';

    // Add parent directory link
    if (result.parent && result.parent !== result.path) {
        const parent = document.createElement('div');
        parent.className = 'file-item directory';
        parent.onclick = () => navigateTo(result.parent);
        parent.innerHTML = '<span class="file-icon">📁</span><span class="file-name">..</span>';
        list.appendChild(parent);
    }

    // Add items
    if (result.items) {
        result.items.forEach(item => {
            const el = document.createElement('div');
            el.className = 'file-item' + (item.is_dir ? ' directory' : ' file');
            el.onclick = () => {
                if (item.is_dir) {
                    navigateTo(item.path);
                } else {
                    selectBrowserPath(item.path);
                }
            };
            el.innerHTML = `
                <span class="file-icon">${item.is_dir ? '📁' : '📄'}</span>
                <span class="file-name">${item.name}</span>
            `;
            list.appendChild(el);
        });
    }
}

function selectBrowserPath(path) {
    browserSelectedPath = path;
    // Highlight selected
    document.querySelectorAll('.file-item').forEach(item => {
        item.classList.remove('selected');
    });
    event.currentTarget.classList.add('selected');
}

function selectBrowserItem() {
    const path = browserSelectedPath || document.getElementById('browserPath').value;
    if (path && browserCallback) {
        browserCallback(path);
    }
    closeFileBrowser();
}

function onBrowserPathKeyup(event) {
    if (event.key === 'Enter') {
        navigateTo(document.getElementById('browserPath').value);
    }
}

// ===================== Auto Patch Generator Functions =====================

let lastDetectedModifiedFuncs = [];
let lastGeneratedPatchContent = '';

async function detectModifiedFunctions() {
    const filePath = document.getElementById('autoPatchSource').value;
    if (!filePath) {
        alert('请先选择源文件');
        return;
    }

    const listEl = document.getElementById('modifiedFuncList');
    listEl.innerHTML = '<span class="hint-text">检测中...</span>';

    const result = await api('/patch/detect_changes', 'POST', { file_path: filePath });
    
    if (result.success) {
        lastDetectedModifiedFuncs = result.modified_functions || [];
        
        if (lastDetectedModifiedFuncs.length === 0) {
            listEl.innerHTML = '<span class="hint-text">未检测到修改的函数 (与 git HEAD 相同)</span>';
        } else {
            listEl.innerHTML = lastDetectedModifiedFuncs.map(func => 
                `<span class="func-tag modified">${func}</span>`
            ).join(' ');
        }
        
        if (term) {
            term.writeln(`\x1b[36m[Detect]\x1b[0m Found ${lastDetectedModifiedFuncs.length} modified functions: ${lastDetectedModifiedFuncs.join(', ') || 'none'}`);
        }
    } else {
        listEl.innerHTML = `<span class="hint-text error">检测失败: ${result.error}</span>`;
        if (term) {
            term.writeln(`\x1b[31m[Error]\x1b[0m ${result.error}`);
        }
    }
}

async function autoGeneratePatch() {
    const filePath = document.getElementById('autoPatchSource').value;
    if (!filePath) {
        alert('请先选择源文件');
        return;
    }

    const contentEl = document.getElementById('autoPatchContent');
    contentEl.textContent = '生成中...';

    const result = await api('/patch/auto_generate', 'POST', { file_path: filePath });
    
    if (result.success) {
        lastDetectedModifiedFuncs = result.modified_functions || [];
        lastGeneratedPatchContent = result.patch_content || '';
        
        // Update modified functions display
        const listEl = document.getElementById('modifiedFuncList');
        if (lastDetectedModifiedFuncs.length === 0) {
            listEl.innerHTML = '<span class="hint-text">未检测到修改的函数</span>';
            contentEl.textContent = '无需生成 patch (文件未修改)';
        } else {
            listEl.innerHTML = lastDetectedModifiedFuncs.map(func => 
                `<span class="func-tag modified">${func}</span> → <span class="func-tag injected">inject_${func}</span>`
            ).join('<br>');
            
            contentEl.textContent = lastGeneratedPatchContent;
        }
        
        if (term) {
            term.writeln(`\x1b[32m[Patch Generated]\x1b[0m ${lastDetectedModifiedFuncs.length} functions: ${result.injected_functions?.join(', ') || 'none'}`);
        }
    } else {
        contentEl.textContent = `生成失败: ${result.error}`;
        if (term) {
            term.writeln(`\x1b[31m[Error]\x1b[0m ${result.error}`);
        }
    }
}

function copyAutoPatchContent() {
    const content = document.getElementById('autoPatchContent').textContent;
    if (content && content !== '点击 "生成 Patch" 查看结果...' && !content.startsWith('生成')) {
        navigator.clipboard.writeText(content).then(() => {
            if (term) {
                term.writeln('\x1b[32m[Copied]\x1b[0m Patch content copied to clipboard');
            }
        });
    }
}

function useAutoPatchAsSource() {
    if (!lastGeneratedPatchContent) {
        alert('请先生成 patch');
        return;
    }
    
    // Copy to patch source editor
    const patchSourceEditor = document.getElementById('patchSource');
    if (patchSourceEditor) {
        patchSourceEditor.value = lastGeneratedPatchContent;
    }
    
    // Also set the first modified function as target
    if (lastDetectedModifiedFuncs.length > 0) {
        const targetInput = document.getElementById('targetFunc');
        if (targetInput) {
            targetInput.value = lastDetectedModifiedFuncs[0];
        }
        const injectInput = document.getElementById('injectFunc');
        if (injectInput) {
            injectInput.value = `inject_${lastDetectedModifiedFuncs[0]}`;
        }
    }
    
    if (term) {
        term.writeln('\x1b[32m[Applied]\x1b[0m Patch content applied to source editor');
    }
}

// Start polling for file watcher changes
let watchStatusInterval = null;
let lastLoggedStatus = '';

function startAutoInjectPolling() {
    if (watchStatusInterval) return;
    
    watchStatusInterval = setInterval(async () => {
        const autoCompileEnabled = document.getElementById('autoCompile').checked;
        const result = await api('/watch/status');
        if (result.success) {
            document.getElementById('watcherEnable').checked = result.watching;
            renderChangeList(result.pending_changes);
        }
        
        // Only poll auto inject status if enabled
        if (autoCompileEnabled) {
            await refreshAutoInjectStatusWithLogging();
        }
    }, 1000); // Poll every 1 second for faster response
}

async function refreshAutoInjectStatusWithLogging() {
    const panel = document.getElementById('autoInjectPanel');
    const result = await api('/watch/auto_inject_status');
    if (!result.success) return;
    
    const status = result.status;
    const message = result.message;
    const progress = result.progress;
    const modifiedFuncs = result.modified_funcs || [];
    
    // Show panel when there's activity
    panel.style.display = 'block';
    
    // Update panel class for styling
    panel.className = 'auto-inject-panel status-' + status;
    
    // Update icon based on status
    const iconEl = document.getElementById('autoInjectIcon');
    const iconMap = {
        'idle': '⏸️',
        'detecting': '🔍',
        'generating': '⚙️',
        'compiling': '🔨',
        'injecting': '💉',
        'success': '✅',
        'failed': '❌'
    };
    iconEl.textContent = iconMap[status] || '⏳';
    
    // Update progress bar
    document.getElementById('autoInjectProgressBar').style.width = progress + '%';
    
    // Update message
    document.getElementById('autoInjectMessage').textContent = message || '等待文件变化...';
    
    // Update modified functions display
    const funcsEl = document.getElementById('autoInjectFuncs');
    if (modifiedFuncs.length > 0) {
        funcsEl.innerHTML = modifiedFuncs.map(func => 
            `<span class="func-tag modified">${func}</span>`
        ).join(' ');
    } else {
        funcsEl.innerHTML = '';
    }
    
    // Log to terminal on status changes (avoid duplicate logs)
    const statusKey = `${status}:${message}`;
    if (statusKey !== lastLoggedStatus && term) {
        lastLoggedStatus = statusKey;
        
        if (status === 'detecting') {
            term.writeln(`\x1b[36m[Auto Inject]\x1b[0m ${message}`);
        } else if (status === 'generating') {
            term.writeln(`\x1b[33m[Auto Inject]\x1b[0m ${message}`);
        } else if (status === 'compiling') {
            term.writeln(`\x1b[33m[Auto Inject]\x1b[0m ${message}`);
        } else if (status === 'injecting') {
            term.writeln(`\x1b[35m[Auto Inject]\x1b[0m ${message}`);
        } else if (status === 'success') {
            term.writeln(`\x1b[32m[Auto Inject]\x1b[0m ${message}`);
            // Refresh inject status in UI
            refreshStatus();
        } else if (status === 'failed') {
            term.writeln(`\x1b[31m[Auto Inject]\x1b[0m ${message}`);
        }
    }
}

// Start polling on page load
document.addEventListener('DOMContentLoaded', () => {
    startAutoInjectPolling();
});
