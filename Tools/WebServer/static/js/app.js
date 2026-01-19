// FPBInject Workbench JavaScript

let isConnected = false;
let logInterval = null;
let lastLogIndex = 0;

// xterm.js terminal instance
let term = null;
let fitAddon = null;
let currentLine = '';
let sendingCommand = false;

// Raw terminal instance (Serial Log)
let rawTerm = null;
let rawFitAddon = null;
let lastRawLogIndex = 0;
let currentTerminalTab = 'tool';

// File browser state
let browserCallback = null;
let browserFilter = '';

// ===================== Utility Functions =====================

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function api(endpoint, method = 'GET', data = null) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
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
  // Restore sidebar state optional - <details> handles it natively

  await refreshPorts();
  await refreshStatus();

  // Initialize terminals
  initTerminal();
  initRawTerminal();

  // Start polling
  startLogPolling();

  // Load editor content
  loadPatchSource();

  // Auto-save configs
  setupConfigListeners();

  // Handle specific VS Code-like behaviors
  setupSidebarInteractions();

  // Load symbols initially if possible
  searchSymbols();
});

function setupSidebarInteractions() {
  // Activity bar switching (basic implementation)
  const items = document.querySelectorAll('.activity-item:not(.spacer)');
  items.forEach(item => {
    item.addEventListener('click', () => {
      // Remove active from all
      items.forEach(i => i.classList.remove('active'));
      // Add to clicked
      item.classList.add('active');

      // In a real app, this would switch sidebar content
      const title = item.getAttribute('title');
      if (title === 'Explorer') {
        document.querySelector('.sidebar').style.display = 'flex';
        // Trigger resize for editor if needed
      } else {
        // Placeholder for other views
        console.log(`Switched to ${title}`);
      }
    });
  });
}

function setupConfigListeners() {
  // Auto-save config on changes
  const ids = ['elfPath', 'compileCommandsPath', 'toolchainPath', 'patchMode', 'watchDirs', 'baudrate'];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', saveConfig);
    }
  });

  const targetFuncEl = document.getElementById('targetFunc');
  if (targetFuncEl) {
    targetFuncEl.addEventListener('change', savePatchSource);
  }

  document.getElementById('patchSource')?.addEventListener('input', savePatchSource);
}

// ===================== Terminal Functions =====================

function initTerminal() {
  const container = document.getElementById('terminal-container');
  if (!container || term) return;

  // VS Code Dark Theme Colors
  term = new Terminal({
    theme: {
      background: '#1e1e1e', // --vscode-panel-background
      foreground: '#cccccc', // --vscode-panel-foreground
      cursor: '#cccccc',
      selectionBackground: '#264f78',
      black: '#000000',
      red: '#cd3131',
      green: '#0dbc79',
      yellow: '#e5e510',
      blue: '#2472c8',
      magenta: '#bc3fbc',
      cyan: '#11a8cd',
      white: '#e5e5e5',
      brightBlack: '#666666',
      brightRed: '#f14c4c',
      brightGreen: '#23d18b',
      brightYellow: '#f5f543',
      brightBlue: '#3b8eea',
      brightMagenta: '#d670d6',
      brightCyan: '#29b8db',
      brightWhite: '#e5e5e5'
    },
    fontFamily: "'Consolas', 'Monaco', monospace",
    fontSize: 13,
    cursorBlink: true,
    cursorStyle: 'block',
    scrollback: 5000,
    convertEol: true
  });

  fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open(container);
  fitAddon.fit();

  // Handle input
  term.onData((data) => {
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
    } else if (data === '\x03') { // Ctrl+C
      currentLine = '';
      term.write('^C\r\n');
    } else {
      currentLine += data;
      term.write(data);
    }
  });

  term.writeln('\x1b[38;2;63;185;80m[FPBInject Workbench]\x1b[0m Ready.');
}

function initRawTerminal() {
  const container = document.getElementById('raw-terminal-container');
  if (!container || rawTerm) return;

  rawTerm = new Terminal({
    theme: {
      background: '#1e1e1e',
      foreground: '#cccccc',
      cursor: '#cccccc'
    },
    fontFamily: "'Consolas', 'Monaco', monospace",
    fontSize: 12,
    cursorBlink: false,
    disableStdin: true,
    scrollback: 10000
  });

  rawFitAddon = new FitAddon.FitAddon();
  rawTerm.loadAddon(rawFitAddon);
  rawTerm.open(container);
  rawFitAddon.fit();
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
    if (term) {
      term.clear();
      api('/log/clear', 'POST');
      lastLogIndex = 0;
    }
  } else {
    if (rawTerm) {
      rawTerm.clear();
      api('/raw_log/clear', 'POST');
      lastRawLogIndex = 0;
    }
  }
}

async function sendTerminalCommand(command) {
  if (!command || sendingCommand) return;
  sendingCommand = true;
  try {
    await api('/command', 'POST', { command });
  } finally {
    setTimeout(() => sendingCommand = false, 50);
  }
}

// ===================== Log Polling =====================

let fetchingLogs = false;
function startLogPolling() {
  if (logInterval) clearInterval(logInterval);
  logInterval = setInterval(fetchLogs, 100);
}

async function fetchLogs() {
  if (fetchingLogs) return;
  fetchingLogs = true;

  try {
    // Tool logs
    const result = await api('/log?since=' + lastLogIndex);
    if (result.success && result.logs && result.logs.length > 0) {
      result.logs.forEach(entry => {
        // In tool terminal, we mostly care about stdout (RX from backend)
        if (term && entry.dir === 'RX') {
          term.write(entry.data);
        }
      });
      lastLogIndex = result.next_index;
    }

    // Raw logs
    const rawResult = await api('/raw_log?since=' + lastRawLogIndex);
    if (rawResult.success && rawResult.logs && rawResult.logs.length > 0) {
      rawResult.logs.forEach(entry => {
        if (rawTerm) {
          const color = entry.dir === 'TX' ? '\x1b[32m' : '\x1b[34m';
          const data = entry.data.replace(/\r/g, '').replace(/\n/g, '\r\n');
          rawTerm.write(`${color}[${entry.dir}]\x1b[0m ${data}`);
        }
      });
      lastRawLogIndex = rawResult.next_index;
    }
  } catch (e) {
    console.error(e);
  } finally {
    fetchingLogs = false;
  }
}


// ===================== Connection & Config =====================

async function refreshPorts() {
  const result = await api('/ports');
  const select = document.getElementById('portSelect');
  if (!select) return;

  const current = select.value;
  select.innerHTML = '';

  if (result.success && result.ports) {
    result.ports.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.device;
      opt.innerText = `${p.device} (${p.description})`;
      select.appendChild(opt);
    });
    if (current) select.value = current;
  }
}

async function refreshStatus() {
  const status = await api('/status');
  if (!status.success) return;

  isConnected = status.connected;
  const btn = document.getElementById('connectBtn');
  const ind = document.getElementById('connectionIndicatorBase');
  const txt = document.getElementById('connectionStatus');
  const portSelect = document.getElementById('portSelect');
  const baudInput = document.getElementById('baudrate');

  if (isConnected) {
    btn.innerText = 'Disconnect';
    btn.classList.add('destructive');
    ind.style.color = 'var(--success-color)';
    txt.innerText = `Connected: ${status.port}`;
    portSelect.value = status.port;
    portSelect.disabled = true;
    baudInput.disabled = true;
  } else {
    btn.innerText = 'Connect';
    btn.classList.remove('destructive');
    ind.style.color = 'var(--vscode-disabledForeground)';
    txt.innerText = 'Disconnected';
    portSelect.disabled = false;
    baudInput.disabled = false;
    if (status.port && portSelect.querySelector(`option[value="${status.port}"]`)) {
      portSelect.value = status.port;
    }
  }

  // Config fields
  if (status.config) {
    setInputVal('elfPath', status.config.elf_path);
    setInputVal('compileCommandsPath', status.config.compile_commands_path);
    setInputVal('toolchainPath', status.config.toolchain_path);
    setInputVal('patchMode', status.config.patch_mode || 'trampoline');
    setInputVal('watchDirs', (status.config.watch_dirs || []).join('\n'));
    setInputVal('baudrate', status.config.baudrate || 115200);

    document.getElementById('watcherEnable').checked = status.watcher_enabled;

    // Also update display
    const display = document.getElementById('targetFuncDisplay');
    if (display && status.config.last_inject_target) {
      display.innerText = status.config.last_inject_target;
    }
  }

  // Watcher Status Label
  const watchStat = document.getElementById('watcherStatus');
  if (watchStat) {
    watchStat.innerText = status.watcher_enabled ? 'Watcher: On' : 'Watcher: Off';
  }
}

function setInputVal(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val || '';
}

async function toggleConnect() {
  if (isConnected) {
    await api('/disconnect', 'POST');
  } else {
    const port = document.getElementById('portSelect').value;
    const baud = parseInt(document.getElementById('baudrate').value);
    if (!port) return alert('No port selected');
    await api('/connect', 'POST', { port, baudrate: baud });
  }
  await refreshStatus();
}

async function saveConfig() {
  const config = {
    elf_path: document.getElementById('elfPath').value,
    compile_commands_path: document.getElementById('compileCommandsPath').value,
    toolchain_path: document.getElementById('toolchainPath').value,
    patch_mode: document.getElementById('patchMode').value,
    watch_dirs: document.getElementById('watchDirs').value.split('\n').filter(s => s.trim()),
    baudrate: parseInt(document.getElementById('baudrate').value),
  };

  await api('/config', 'POST', config);
}

// ===================== Editor & Patching =====================

async function loadPatchSource() {
  const result = await api('/patch/source');
  if (result.success) {
    const ed = document.getElementById('patchSource');
    if (ed) {
      ed.value = result.content || '';
    }
  }
}

async function savePatchSource() {
  const ed = document.getElementById('patchSource');
  if (ed) {
    await api('/patch/source', 'POST', { content: ed.value, save_to_file: true });
  }
}

async function generatePatch() {
  const targetFunc = document.getElementById('targetFunc').value;
  if (!targetFunc) return alert('Target function required');

  const result = await api('/patch/generate', 'POST', { target_func: targetFunc });
  if (result.success) {
    const ed = document.getElementById('patchSource');
    if (ed) {
      ed.value = result.content;
      savePatchSource();
    }
  } else {
    alert('Generate failed: ' + result.error);
  }
}

async function autoGeneratePatch() {
  // Note: Python needs file_path. We'll try to guess it from config or use a dedicated endpoint if available
  // For now we assume we don't have the source file path easily unless it's in config
  alert('Feature requires server-side file path context. Please use "Generate Template" for now.');
}

async function performInject() {
  const source = document.getElementById('patchSource').value;
  const targetFunc = document.getElementById('targetFunc').value;

  if (!source) return alert('No patch source code');
  if (!targetFunc) return alert('No target function specified');

  // Show progress
  const progress = document.getElementById('injectProgress');
  const bar = document.getElementById('injectProgressFill');
  const text = document.getElementById('injectProgressText');

  if (progress) {
    progress.style.display = 'block';
    bar.style.width = '10%';
    text.innerText = 'Compiling...';
  }

  try {
    const result = await api('/fpb/inject', 'POST', {
      source_content: source,
      target_func: targetFunc
    });

    if (progress) bar.style.width = '100%';

    if (result.success) {
      if (text) text.innerText = 'Success!';
      // Update injected func display
      const disp = document.getElementById('injectFuncDisplay');
      if (disp) disp.innerText = targetFunc;

      // Switch to terminal to see output
      switchTerminalTab('tool');
    } else {
      if (text) text.innerText = 'Failed';
      alert('Injection Failed:\n' + result.error || result.message);
    }
  } catch (e) {
    console.error(e);
    alert('Error: ' + e);
  } finally {
    setTimeout(() => {
      if (progress) progress.style.display = 'none';
    }, 2000);
  }
}

async function fpbPing() {
  const res = await api('/fpb/ping', 'POST');
  if (res.success) {
    term.writeln('\r\n[Ping] Pong from device.');
  } else {
    term.writeln('\r\n[Ping] Failed: ' + res.message);
  }
}

async function fpbInfo() {
  const res = await api('/fpb/info');
  if (res.success) {
    term.write('\r\n' + JSON.stringify(res.info, null, 2) + '\r\n');
  }
}

async function fpbUnpatch() {
  await api('/fpb/unpatch', 'POST');
  document.getElementById('injectFuncDisplay').innerText = '-';
  term.writeln('\r\n[Unpatch] Request sent.');
}

function toggleWatcher() {
  // We don't have a direct watcher toggle endpoint in mapped routes
  // But saving config triggers it if watch_dirs is set.
  // For now, we will toggle the UI and save config
  saveConfig();
}

// ===================== File Browser =====================

function browseFile(targetId, filter) {
  browserCallback = (path) => {
    document.getElementById(targetId).value = path;
    saveConfig();
    closeFileBrowser();
  };
  browserFilter = filter || '';
  openFileBrowser();
}

function browseDir(targetId) {
  browserCallback = (path) => {
    document.getElementById(targetId).value = path;
    saveConfig();
    closeFileBrowser();
  };
  browserFilter = 'DIR';
  openFileBrowser();
}

function openFileBrowser() {
  document.getElementById('fileBrowserModal').style.display = 'flex';
  navigateTo('/');
}

function closeFileBrowser() {
  document.getElementById('fileBrowserModal').style.display = 'none';
}

async function navigateTo(path) {
  // Use /api/browse
  let endpoint = '/browse?path=' + encodeURIComponent(path || '');
  if (browserFilter && browserFilter !== 'DIR') {
    endpoint += '&filter=' + encodeURIComponent(browserFilter);
  }

  const result = await api(endpoint);

  if (!result || !result.success) {
    console.warn('File browser listing failed');
    return;
  }

  const list = document.getElementById('fileList');
  const pathInput = document.getElementById('browserPath');
  pathInput.value = result.path;
  list.innerHTML = '';

  // Parent
  if (result.parent) {
    const parent = document.createElement('div');
    parent.className = 'file-item';
    parent.innerHTML = '<i class="codicon codicon-folder"></i> <span>..</span>';
    parent.onclick = () => navigateTo(result.parent);
    list.appendChild(parent);
  }

  if (result.items) {
    result.items.forEach(item => {
      const el = document.createElement('div');
      el.className = 'file-item';

      if (item.is_dir) {
        el.innerHTML = `<i class="codicon codicon-folder" style="color: #c69b6d;"></i> <span>${item.name}</span>`;
        el.onclick = () => navigateTo(item.path);
      } else {
        if (browserFilter === 'DIR') {
          // Dim files if selecting dir
          el.style.opacity = '0.5';
          el.innerHTML = `<i class="codicon codicon-file"></i> <span>${item.name}</span>`;
        } else {
          el.innerHTML = `<i class="codicon codicon-file"></i> <span>${item.name}</span>`;
          el.onclick = () => selectFileItem(el, item.path);
        }
      }
      list.appendChild(el);
    });
  }
}
function selectFileItem(el, path) {
  document.querySelectorAll('.file-item').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  browserSelectedPath = path;
}
function selectBrowserItem() {
  if (browserSelectedPath && browserCallback) browserCallback(browserSelectedPath);
  // if dir, handle current path
}

// ===================== Symbols =====================

async function searchSymbols() {
  const query = document.getElementById('symbolSearch').value;
  const list = document.getElementById('symbolList');

  try {
    const res = await api(`/symbols?q=${encodeURIComponent(query)}&limit=50`);
    list.innerHTML = '';
    if (res.success && res.symbols) {
      res.symbols.forEach(sym => {
        const div = document.createElement('div');
        div.style.padding = '4px 8px';
        div.style.cursor = 'pointer';
        div.style.fontSize = '11px';
        div.className = 'symbol-item';
        div.innerHTML = `<i class="codicon codicon-symbol-method" style="margin-right:4px;"></i> ${sym.name}`;
        div.addEventListener('click', () => {
          document.getElementById('targetFunc').value = sym.name;
        });
        list.appendChild(div);
      });
    }
  } catch (e) { }
}
