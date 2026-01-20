/*========================================
  FPBInject Workbench - Main Application JS
  ========================================*/

/* ===========================
   GLOBAL STATE
   =========================== */
let isConnected = false;
let toolTerminal = null;
let rawTerminal = null;
let toolFitAddon = null;
let rawFitAddon = null;
let currentTerminalTab = 'tool';
let logPollInterval = null;
let autoInjectPollInterval = null;
let lastAutoInjectStatus = 'idle';
let autoInjectProgressHideTimer = null;
let selectedSlot = 0;
let slotStates = Array(6).fill().map(() => ({ occupied: false, func: 'Empty', addr: '' }));

// Tabs state
let editorTabs = [{ id: 'patch_source', title: 'patch_source.c', type: 'c', closable: false }];
let activeEditorTab = 'patch_source';

// File browser state
let fileBrowserCallback = null;
let fileBrowserFilter = '';
let fileBrowserMode = 'file';
let currentBrowserPath = '/';
let selectedBrowserItem = null;

/* ===========================
   INITIALIZATION
   =========================== */
document.addEventListener('DOMContentLoaded', () => {
  loadThemePreference();  // Load theme FIRST before terminal init
  initTerminals();
  refreshPorts();
  loadConfig();
  initSashResize();
  loadLayoutPreferences();
  updateSlotUI();
  initSlotSelectListener();
  updateDisabledState(); // Initial disabled state
  setupAutoSave(); // Setup auto-save for config inputs
});

// Initialize slot select dropdown listener
function initSlotSelectListener() {
  const slotSelect = document.getElementById('slotSelect');
  if (slotSelect) {
    slotSelect.addEventListener('change', onSlotSelectChange);
  }
}

// Update UI disabled state based on connection
function updateDisabledState() {
  const disableWhenDisconnected = [
    'targetFunc', 'slotSelect', 'patchSource', 'injectBtn'
  ];
  const opacityElements = [
    'editorContainer', 'slotContainer'
  ];
  
  disableWhenDisconnected.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.disabled = !isConnected;
      el.style.opacity = isConnected ? '1' : '0.5';
    }
  });
  
  // Add visual feedback for disabled sections
  opacityElements.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.style.opacity = isConnected ? '1' : '0.6';
      el.style.pointerEvents = isConnected ? 'auto' : 'none';
    }
  });
  
  // Device info buttons
  document.querySelectorAll('#slotContainer .slot-btn').forEach(btn => {
    btn.disabled = !isConnected;
  });
}

/* ===========================
   THEME TOGGLE
   =========================== */
const darkTerminalTheme = {
  background: '#1e1e1e',
  foreground: '#cccccc',
  cursor: '#ffffff',
  cursorAccent: '#1e1e1e',
  selection: '#264f78'
};

const lightTerminalTheme = {
  background: '#f3f3f3',
  foreground: '#333333',
  cursor: '#333333',
  cursorAccent: '#f3f3f3',
  selection: '#add6ff'
};

function toggleTheme() {
  const html = document.documentElement;
  const currentTheme = html.getAttribute('data-theme');
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  html.setAttribute('data-theme', newTheme);
  localStorage.setItem('fpbinject-theme', newTheme);
  updateThemeIcon();
  updateTerminalTheme();
}

function loadThemePreference() {
  const savedTheme = localStorage.getItem('fpbinject-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeIcon();
  // Terminal theme will be set during initTerminals
}

function updateThemeIcon() {
  const themeIcon = document.getElementById('themeIcon');
  const currentTheme = document.documentElement.getAttribute('data-theme');
  if (themeIcon) {
    // Use existing codicons: lightbulb for light, lightbulb-autofix for dark
    themeIcon.className = currentTheme === 'light' ? 'codicon codicon-lightbulb' : 'codicon codicon-lightbulb-autofix';
  }
}

function updateTerminalTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  const termTheme = currentTheme === 'light' ? lightTerminalTheme : darkTerminalTheme;
  
  if (toolTerminal) {
    toolTerminal.options.theme = termTheme;
  }
  if (rawTerminal) {
    rawTerminal.options.theme = termTheme;
  }
}

/* ===========================
   SASH RESIZE FUNCTIONALITY
   =========================== */
function initSashResize() {
  const sashSidebar = document.getElementById('sashSidebar');
  const sashPanel = document.getElementById('sashPanel');
  const sidebar = document.getElementById('sidebar');
  const panelContainer = document.getElementById('panelContainer');

  let isResizingSidebar = false;
  let isResizingPanel = false;
  let startX = 0;
  let startY = 0;
  let startWidth = 0;
  let startHeight = 0;

  // Sidebar resize
  if (sashSidebar) {
    sashSidebar.addEventListener('mousedown', (e) => {
      e.preventDefault();
      isResizingSidebar = true;
      startX = e.clientX;
      startWidth = sidebar.offsetWidth;
      document.body.classList.add('resizing-sidebar');
      sashSidebar.classList.add('active');
    });
  }

  // Panel resize
  if (sashPanel) {
    sashPanel.addEventListener('mousedown', (e) => {
      e.preventDefault();
      isResizingPanel = true;
      startY = e.clientY;
      startHeight = panelContainer.offsetHeight;
      document.body.classList.add('resizing-panel');
      sashPanel.classList.add('active');
    });
  }

  document.addEventListener('mousemove', (e) => {
    if (isResizingSidebar) {
      const delta = e.clientX - startX;
      const newWidth = Math.max(180, Math.min(600, startWidth + delta));
      document.documentElement.style.setProperty('--sidebar-width', newWidth + 'px');
    }

    if (isResizingPanel) {
      const delta = startY - e.clientY;
      const newHeight = Math.max(100, Math.min(500, startHeight + delta));
      document.documentElement.style.setProperty('--panel-height', newHeight + 'px');
    }
  });

  document.addEventListener('mouseup', () => {
    if (isResizingSidebar) {
      isResizingSidebar = false;
      document.body.classList.remove('resizing-sidebar');
      sashSidebar.classList.remove('active');
      saveLayoutPreferences();
      fitTerminals();
    }

    if (isResizingPanel) {
      isResizingPanel = false;
      document.body.classList.remove('resizing-panel');
      sashPanel.classList.remove('active');
      saveLayoutPreferences();
      fitTerminals();
    }
  });
}

function loadLayoutPreferences() {
  const sidebarWidth = localStorage.getItem('fpbinject-sidebar-width');
  const panelHeight = localStorage.getItem('fpbinject-panel-height');

  if (sidebarWidth) {
    document.documentElement.style.setProperty('--sidebar-width', sidebarWidth);
  }
  if (panelHeight) {
    document.documentElement.style.setProperty('--panel-height', panelHeight);
  }
}

function saveLayoutPreferences() {
  const sidebarWidth = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width');
  const panelHeight = getComputedStyle(document.documentElement).getPropertyValue('--panel-height');

  localStorage.setItem('fpbinject-sidebar-width', sidebarWidth.trim());
  localStorage.setItem('fpbinject-panel-height', panelHeight.trim());
}

/* ===========================
   TERMINAL MANAGEMENT
   =========================== */
function getTerminalTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  return currentTheme === 'light' ? lightTerminalTheme : darkTerminalTheme;
}

function initTerminals() {
  const termTheme = getTerminalTheme();
  
  // Tool Terminal (OUTPUT - Python logs)
  const toolContainer = document.getElementById('terminal-container');
  if (toolContainer && typeof Terminal !== 'undefined') {
    toolTerminal = new Terminal({
      theme: termTheme,
      fontFamily: 'Consolas, "Courier New", monospace',
      fontSize: 12,
      cursorBlink: false,
      disableStdin: true,
      // Enable mouse selection
      allowProposedApi: true
    });
    toolFitAddon = new FitAddon.FitAddon();
    toolTerminal.loadAddon(toolFitAddon);
    toolTerminal.open(toolContainer);
    toolFitAddon.fit();
    
    // Enable text selection with mouse
    toolTerminal.attachCustomKeyEventHandler((e) => {
      // Allow Ctrl+C for copy
      if (e.ctrlKey && e.key === 'c') {
        const selection = toolTerminal.getSelection();
        if (selection) {
          navigator.clipboard.writeText(selection);
          return false;
        }
      }
      return true;
    });
    
    toolTerminal.writeln('\x1b[36m[OUTPUT] FPBInject Workbench Ready\x1b[0m');
  }

  // Raw Terminal (SERIAL PORT - interactive)
  const rawContainer = document.getElementById('raw-terminal-container');
  if (rawContainer && typeof Terminal !== 'undefined') {
    rawTerminal = new Terminal({
      theme: termTheme,
      fontFamily: 'Consolas, "Courier New", monospace',
      fontSize: 12,
      cursorBlink: true,
      disableStdin: false,
      allowProposedApi: true
    });
    rawFitAddon = new FitAddon.FitAddon();
    rawTerminal.loadAddon(rawFitAddon);
    rawTerminal.open(rawContainer);
    rawFitAddon.fit();

    // Enable text selection with mouse + Ctrl+C copy
    rawTerminal.attachCustomKeyEventHandler((e) => {
      if (e.ctrlKey && e.key === 'c') {
        const selection = rawTerminal.getSelection();
        if (selection) {
          navigator.clipboard.writeText(selection);
          return false;
        }
      }
      return true;
    });

    // Setup input handler for interactive terminal
    rawTerminal.onData(data => {
      if (isConnected) {
        sendTerminalCommand(data);
      }
    });
  }

  window.addEventListener('resize', fitTerminals);
}

function fitTerminals() {
  setTimeout(() => {
    if (toolFitAddon) toolFitAddon.fit();
    if (rawFitAddon) rawFitAddon.fit();
  }, 100);
}

function switchTerminalTab(tab) {
  currentTerminalTab = tab;

  document.getElementById('tabBtnTool').classList.toggle('active', tab === 'tool');
  document.getElementById('tabBtnRaw').classList.toggle('active', tab === 'raw');

  const toolPanel = document.getElementById('terminalPanelTool');
  const rawPanel = document.getElementById('terminalPanelRaw');

  // Show both panels temporarily to allow proper fitting
  toolPanel.style.visibility = 'hidden';
  rawPanel.style.visibility = 'hidden';
  toolPanel.style.display = 'block';
  rawPanel.style.display = 'block';

  // Fit terminals while both are displayed
  if (toolFitAddon) toolFitAddon.fit();
  if (rawFitAddon) rawFitAddon.fit();

  // Then show only the active tab
  toolPanel.style.display = tab === 'tool' ? 'block' : 'none';
  rawPanel.style.display = tab === 'raw' ? 'block' : 'none';
  toolPanel.style.visibility = 'visible';
  rawPanel.style.visibility = 'visible';
}

function clearCurrentTerminal() {
  if (currentTerminalTab === 'tool' && toolTerminal) {
    toolTerminal.clear();
    toolTerminal.writeln('\x1b[36m[OUTPUT] Terminal cleared\x1b[0m');
  } else if (currentTerminalTab === 'raw' && rawTerminal) {
    rawTerminal.clear();
  }
}

function writeToOutput(message, type = 'info') {
  if (!toolTerminal) return;
  const colors = {
    info: '\x1b[37m',
    success: '\x1b[32m',
    warning: '\x1b[33m',
    error: '\x1b[31m',
    system: '\x1b[36m'
  };
  const color = colors[type] || colors.info;
  
  // Split message by newlines and write each line separately
  const lines = message.split('\n');
  lines.forEach(line => {
    toolTerminal.writeln(`${color}${line}\x1b[0m`);
  });
}

function writeToSerial(data) {
  if (rawTerminal) {
    rawTerminal.write(data);
  }
}

/* ===========================
   SLOT MANAGEMENT
   =========================== */
function updateSlotUI() {
  let activeCount = 0;

  for (let i = 0; i < 6; i++) {
    const slotItem = document.querySelector(`.slot-item[data-slot="${i}"]`);
    const funcSpan = document.getElementById(`slot${i}Func`);
    const state = slotStates[i];

    if (slotItem) {
      slotItem.classList.toggle('occupied', state.occupied);
      slotItem.classList.toggle('active', i === selectedSlot);
    }

    if (funcSpan) {
      if (state.occupied) {
        const injectInfo = state.inject_func ? ` → ${state.inject_func}` : '';
        const sizeInfo = state.code_size ? ` (${state.code_size}B)` : '';
        funcSpan.textContent = `${state.func}${injectInfo}${sizeInfo}`;
        funcSpan.title = `Original: ${state.func} @ ${state.addr}\nInjected: ${state.inject_func || 'N/A'}\nCode size: ${state.code_size || 0} bytes`;
      } else {
        funcSpan.textContent = 'Empty';
        funcSpan.title = '';
      }
    }

    if (state.occupied) activeCount++;
  }

  document.getElementById('activeSlotCount').textContent = `${activeCount}/6`;
  document.getElementById('currentSlotDisplay').textContent = `Slot: ${selectedSlot}`;
  document.getElementById('slotSelect').value = selectedSlot;
}

function selectSlot(slotId) {
  selectedSlot = parseInt(slotId);
  updateSlotUI();
  writeToOutput(`[INFO] Selected Slot ${slotId}`, 'info');
}

// Handle slot selection from dropdown
function onSlotSelectChange() {
  const slotId = parseInt(document.getElementById('slotSelect').value);
  selectSlot(slotId);
}

async function fpbUnpatch(slotId) {
  if (!isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  try {
    const res = await fetch('/api/fpb/unpatch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comp: slotId })
    });
    const data = await res.json();

    if (data.success) {
      slotStates[slotId] = { occupied: false, func: 'Empty', addr: '' };
      updateSlotUI();
      writeToOutput(`[SUCCESS] Slot ${slotId} cleared`, 'success');
    } else {
      writeToOutput(`[ERROR] Failed to clear slot ${slotId}: ${data.message}`, 'error');
    }
  } catch (e) {
    writeToOutput(`[ERROR] Unpatch error: ${e}`, 'error');
  }
}

async function fpbUnpatchAll() {
  if (!isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  try {
    const res = await fetch('/api/fpb/unpatch', { method: 'POST' });
    const data = await res.json();

    if (data.success) {
      slotStates = Array(6).fill().map(() => ({ occupied: false, func: 'Empty', addr: '' }));
      updateSlotUI();
      writeToOutput('[SUCCESS] All slots cleared', 'success');
    } else {
      writeToOutput(`[ERROR] Failed to clear all: ${data.message}`, 'error');
    }
  } catch (e) {
    writeToOutput(`[ERROR] Unpatch all error: ${e}`, 'error');
  }
}

/* ===========================
   CONNECTION MANAGEMENT
   =========================== */
async function refreshPorts() {
  try {
    const res = await fetch('/api/ports');
    const data = await res.json();
    const sel = document.getElementById('portSelect');
    const prevValue = sel.value;
    sel.innerHTML = '';

    // Handle both array of strings and array of objects
    const ports = data.ports || [];
    ports.forEach(p => {
      const opt = document.createElement('option');
      // Support both string format and object format {port: "xxx", desc: "xxx"}
      const portName = (typeof p === 'string') ? p : (p.port || p.device || String(p));
      opt.value = portName;
      opt.textContent = portName;
      sel.appendChild(opt);
    });

    // Restore previous selection if still available
    const portValues = ports.map(p => (typeof p === 'string') ? p : (p.port || p.device || String(p)));
    if (portValues.includes(prevValue)) {
      sel.value = prevValue;
    }
  } catch (e) {
    writeToOutput(`[ERROR] Failed to refresh ports: ${e}`, 'error');
  }
}

async function toggleConnect() {
  const btn = document.getElementById('connectBtn');
  const statusEl = document.getElementById('connectionStatus');

  if (!isConnected) {
    const port = document.getElementById('portSelect').value;
    const baud = document.getElementById('baudrate').value;

    btn.disabled = true;
    btn.textContent = 'Connecting...';

    try {
      const res = await fetch('/api/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ port, baudrate: parseInt(baud) })
      });
      const data = await res.json();

      if (data.success) {
        isConnected = true;
        btn.textContent = 'Disconnect';
        btn.classList.add('connected');
        statusEl.textContent = `${port}`;
        writeToOutput(`[CONNECTED] ${port} @ ${baud} baud`, 'success');
        startLogPolling();
        fpbInfo();
        updateDisabledState(); // Enable UI
      } else {
        throw new Error(data.message || 'Connection failed');
      }
    } catch (e) {
      writeToOutput(`[ERROR] ${e}`, 'error');
      btn.textContent = 'Connect';
    }

    btn.disabled = false;
  } else {
    try {
      await fetch('/api/disconnect', { method: 'POST' });
      isConnected = false;
      btn.textContent = 'Connect';
      btn.classList.remove('connected');
      statusEl.textContent = 'Disconnected';
      writeToOutput('[DISCONNECTED]', 'warning');
      stopLogPolling();
      updateDisabledState(); // Disable UI
    } catch (e) {
      writeToOutput(`[ERROR] Disconnect failed: ${e}`, 'error');
    }
  }
}

/* ===========================
   LOG POLLING
   =========================== */
let toolLogNextId = 0;
let rawLogNextId = 0;

function startLogPolling() {
  stopLogPolling();
  toolLogNextId = 0;
  rawLogNextId = 0;
  logPollInterval = setInterval(fetchLogs, 200);
}

function stopLogPolling() {
  if (logPollInterval) {
    clearInterval(logPollInterval);
    logPollInterval = null;
  }
}

async function fetchLogs() {
  try {
    const res = await fetch(`/api/logs?tool_since=${toolLogNextId}&raw_since=${rawLogNextId}`);
    
    // Check if response is ok
    if (!res.ok) {
      return; // Silently ignore non-200 responses
    }
    
    // Check content type before parsing
    const contentType = res.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      return; // Not JSON, skip
    }
    
    const text = await res.text();
    if (!text || text.trim() === '') {
      return; // Empty response, skip
    }
    
    let data;
    try {
      data = JSON.parse(text);
    } catch (parseError) {
      console.warn('Log parse error:', parseError, 'Response:', text.substring(0, 100));
      return;
    }

    // Update next IDs for incremental polling
    if (data.tool_next !== undefined) toolLogNextId = data.tool_next;
    if (data.raw_next !== undefined) rawLogNextId = data.raw_next;

    // Tool logs (Python output) -> OUTPUT terminal
    if (data.tool_logs && Array.isArray(data.tool_logs) && data.tool_logs.length > 0) {
      data.tool_logs.forEach(log => {
        writeToOutput(log, 'info');
      });
    }

    // Raw serial data -> SERIAL PORT terminal
    if (data.raw_data && data.raw_data.length > 0) {
      writeToSerial(data.raw_data);
    }
  } catch (e) {
    // Silently fail on polling errors (network issues, etc.)
  }
}

/* ===========================
   FPB COMMANDS
   =========================== */
async function fpbPing() {
  if (!isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  try {
    const res = await fetch('/api/fpb/ping', { method: 'POST' });
    const data = await res.json();
    writeToOutput(`[PING] ${data.message}`, data.success ? 'success' : 'error');
  } catch (e) {
    writeToOutput(`[ERROR] Ping failed: ${e}`, 'error');
  }
}

async function fpbInfo() {
  if (!isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  try {
    const res = await fetch('/api/fpb/info');
    const data = await res.json();

    if (data.success) {
      // Update slot states from device
      if (data.slots) {
        data.slots.forEach((slot, i) => {
          if (i < 6) {
            slotStates[i] = {
              occupied: slot.occupied || false,
              func: slot.func || 'Empty',
              addr: slot.addr || '',
              inject_func: slot.inject_func || '',
              code_size: slot.code_size || 0
            };
          }
        });
      }
      updateSlotUI();

      // Update memory info display
      if (data.memory) {
        updateMemoryInfo(data.memory);
      }

      writeToOutput('[INFO] Device info updated', 'success');
    } else {
      writeToOutput(`[ERROR] ${data.error || 'Failed to get device info'}`, 'error');
    }
  } catch (e) {
    writeToOutput(`[ERROR] Info failed: ${e}`, 'error');
  }
}

function updateMemoryInfo(memory) {
  const memoryEl = document.getElementById('memoryInfo');
  if (!memoryEl) return;

  const base = memory.base || 0;
  const size = memory.size || 0;
  const used = memory.used || 0;
  const free = size - used;
  const usedPercent = size > 0 ? Math.round((used / size) * 100) : 0;

  memoryEl.innerHTML = `
    <div style="font-size: 10px; color: var(--vscode-descriptionForeground);">
      Base: 0x${base.toString(16).toUpperCase().padStart(8, '0')} | 
      Used: ${used}/${size} bytes (${usedPercent}%)
    </div>
  `;
}

/* ===========================
   PATCH OPERATIONS
   =========================== */
async function generatePatch() {
  const targetFunc = document.getElementById('targetFunc').value;
  if (!targetFunc) {
    writeToOutput('[ERROR] Please enter target function name', 'error');
    return;
  }

  writeToOutput(`[GENERATE] Creating patch template for ${targetFunc}...`, 'system');

  const template = `// Auto-generated patch for: ${targetFunc}
// Slot: ${selectedSlot}

#include <stdint.h>
#include <stdio.h>

// Original function prototype (adjust as needed)
// extern int ${targetFunc}(void);

// Inject function - will replace ${targetFunc}
int inject_${targetFunc}(void) {
    // Your patch code here
    printf("Patched ${targetFunc} executed!\\n");
    
    // Call original if needed:
    // return ${targetFunc}_original();
    
    return 0;
}
`;

  document.getElementById('patchSource').value = template;
  writeToOutput(`[SUCCESS] Patch template generated`, 'success');
}

async function performInject() {
  if (!isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  const source = document.getElementById('patchSource').value;
  const targetFunc = document.getElementById('targetFunc').value;

  if (!source.trim()) {
    writeToOutput('[ERROR] No patch source code', 'error');
    return;
  }

  if (!targetFunc) {
    writeToOutput('[ERROR] Please specify target function', 'error');
    return;
  }

  const progressEl = document.getElementById('injectProgress');
  const progressText = document.getElementById('injectProgressText');
  const progressFill = document.getElementById('injectProgressFill');

  progressEl.style.display = 'flex';
  progressText.textContent = 'Starting...';
  progressFill.style.width = '5%';

  writeToOutput(`[INJECT] Starting injection to slot ${selectedSlot}...`, 'system');

  try {
    // Use streaming API for real-time progress
    const response = await fetch('/api/fpb/inject/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_content: source,
        target_func: targetFunc,
        comp: selectedSlot,
        patch_mode: document.getElementById('patchMode').value
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalResult = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'status') {
              if (data.stage === 'compiling') {
                progressText.textContent = 'Compiling...';
                progressFill.style.width = '20%';
              }
            } else if (data.type === 'progress') {
              const uploadPercent = data.percent || 0;
              // Map upload progress (0-100) to overall progress (30-90)
              const overallPercent = 30 + (uploadPercent * 0.6);
              progressText.textContent = `Uploading... ${data.uploaded}/${data.total} bytes (${uploadPercent}%)`;
              progressFill.style.width = `${overallPercent}%`;
            } else if (data.type === 'result') {
              finalResult = data;
            }
          } catch (e) {
            console.warn('Failed to parse SSE data:', e);
          }
        }
      }
    }

    if (finalResult && finalResult.success) {
      progressText.textContent = 'Complete!';
      progressFill.style.width = '100%';

      slotStates[selectedSlot] = {
        occupied: true,
        func: targetFunc,
        addr: finalResult.target_addr || '0x????',
        inject_func: finalResult.inject_func || '',
        code_size: finalResult.code_size || 0
      };
      updateSlotUI();

      // Display injection statistics
      displayInjectionStats(finalResult, targetFunc);

      setTimeout(() => {
        progressEl.style.display = 'none';
        progressFill.style.width = '0%';
      }, 2000);
    } else {
      throw new Error(finalResult?.error || 'Injection failed');
    }
  } catch (e) {
    progressText.textContent = 'Failed!';
    progressFill.style.background = '#f44336';
    writeToOutput(`[ERROR] ${e}`, 'error');

    setTimeout(() => {
      progressEl.style.display = 'none';
      progressFill.style.width = '0%';
      progressFill.style.background = '';
    }, 2000);
  }
}

function displayInjectionStats(data, targetFunc) {
  const compileTime = data.compile_time || 0;
  const uploadTime = data.upload_time || 0;
  const codeSize = data.code_size || 0;
  const totalTime = data.total_time || (compileTime + uploadTime);
  const uploadSpeed = uploadTime > 0 ? Math.round(codeSize / uploadTime) : 0;
  const patchMode = data.patch_mode || document.getElementById('patchMode').value;
  
  writeToOutput(`[SUCCESS] Injection complete!`, 'success');
  writeToOutput(`--- Injection Statistics ---`, 'system');
  writeToOutput(`Target:        ${targetFunc} @ ${data.target_addr || 'unknown'}`, 'info');
  writeToOutput(`Inject func:   ${data.inject_func || 'unknown'} @ ${data.inject_addr || 'unknown'}`, 'info');
  writeToOutput(`Compile time:  ${compileTime.toFixed(2)}s`, 'info');
  writeToOutput(`Upload time:   ${uploadTime.toFixed(2)}s (${uploadSpeed} B/s)`, 'info');
  writeToOutput(`Code size:     ${codeSize} bytes`, 'info');
  writeToOutput(`Total time:    ${totalTime.toFixed(2)}s`, 'info');
  writeToOutput(`Injection active! (mode: ${patchMode})`, 'success');
}

/* ===========================
   SYMBOL SEARCH
   =========================== */
async function searchSymbols() {
  const query = document.getElementById('symbolSearch').value;
  const list = document.getElementById('symbolList');

  if (query.length < 2) {
    list.innerHTML = '<div style="padding: 8px; font-size: 11px; opacity: 0.7;">Enter at least 2 characters</div>';
    return;
  }

  try {
    const res = await fetch(`/api/symbols/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();

    if (data.symbols && data.symbols.length > 0) {
      list.innerHTML = data.symbols.map(sym => `
        <div class="symbol-item" onclick="selectSymbol('${sym.name}')" ondblclick="openDisassembly('${sym.name}', '${sym.addr}')">
          <i class="codicon codicon-symbol-method symbol-icon"></i>
          <span class="symbol-name">${sym.name}</span>
          <span class="symbol-addr">${sym.addr}</span>
        </div>
      `).join('');
    } else if (data.error) {
      list.innerHTML = `<div style="padding: 8px; font-size: 11px; opacity: 0.7; color: #f44336;">${data.error}</div>`;
    } else {
      list.innerHTML = '<div style="padding: 8px; font-size: 11px; opacity: 0.7;">No symbols found</div>';
    }
  } catch (e) {
    list.innerHTML = `<div style="padding: 8px; font-size: 11px; opacity: 0.7; color: #f44336;">Error: ${e.message}</div>`;
  }
}

function selectSymbol(name) {
  document.getElementById('targetFunc').value = name;
  writeToOutput(`[INFO] Selected symbol: ${name}`, 'info');
}

async function openDisassembly(funcName, addr) {
  const tabId = `disasm_${funcName}`;

  // Check if tab already exists
  if (editorTabs.find(t => t.id === tabId)) {
    switchEditorTab(tabId);
    return;
  }

  writeToOutput(`[DISASM] Loading disassembly for ${funcName}...`, 'system');

  try {
    const res = await fetch(`/api/symbols/disasm?func=${encodeURIComponent(funcName)}`);
    const data = await res.json();

    // Create new tab
    editorTabs.push({
      id: tabId,
      title: `${funcName}.asm`,
      type: 'asm',
      closable: true
    });

    // Add tab button
    const tabsHeader = document.getElementById('editorTabsHeader');
    const tabDiv = document.createElement('div');
    tabDiv.className = 'tab';
    tabDiv.setAttribute('data-tab', tabId);
    tabDiv.innerHTML = `
      <i class="codicon codicon-file-binary tab-icon" style="color: #75beff;"></i>
      <span>${funcName}.asm</span>
      <div class="tab-close" onclick="closeTab('${tabId}', event)"><i class="codicon codicon-close"></i></div>
    `;
    tabDiv.onclick = () => switchEditorTab(tabId);
    tabsHeader.appendChild(tabDiv);

    // Add tab content
    const tabsContent = document.querySelector('.editor-tabs-content');
    const contentDiv = document.createElement('div');
    contentDiv.className = 'tab-content';
    contentDiv.id = `tabContent_${tabId}`;

    const disasmCode = data.disasm || `; Disassembly for ${funcName} @ ${addr}\n; (Disassembly data not available)`;

    contentDiv.innerHTML = `
      <div class="code-display">
        <pre><code class="language-x86asm">${escapeHtml(disasmCode)}</code></pre>
      </div>
    `;
    tabsContent.appendChild(contentDiv);

    // Apply syntax highlighting (try multiple methods)
    if (typeof hljs !== 'undefined') {
      contentDiv.querySelectorAll('pre code').forEach(block => {
        // Try auto-detection if language not recognized
        try {
          hljs.highlightElement(block);
        } catch (e) {
          // Fallback: highlight as plain text with assembly-like coloring
          block.classList.add('hljs');
        }
      });
    }

    switchEditorTab(tabId);
    writeToOutput(`[SUCCESS] Disassembly loaded for ${funcName}`, 'success');

  } catch (e) {
    writeToOutput(`[ERROR] Failed to load disassembly: ${e}`, 'error');
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function switchEditorTab(tabId) {
  activeEditorTab = tabId;

  // Update tab buttons
  document.querySelectorAll('.editor-tabs-header .tab').forEach(tab => {
    tab.classList.toggle('active', tab.getAttribute('data-tab') === tabId);
  });

  // Update tab content
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.toggle('active', content.id === `tabContent_${tabId}`);
  });
}

function closeTab(tabId, event) {
  if (event) event.stopPropagation();

  const tabInfo = editorTabs.find(t => t.id === tabId);
  if (!tabInfo || !tabInfo.closable) return;

  // Remove from tabs array
  editorTabs = editorTabs.filter(t => t.id !== tabId);

  // Remove DOM elements
  document.querySelector(`.tab[data-tab="${tabId}"]`)?.remove();
  document.getElementById(`tabContent_${tabId}`)?.remove();

  // Switch to first tab if current was closed
  if (activeEditorTab === tabId && editorTabs.length > 0) {
    switchEditorTab(editorTabs[0].id);
  }
}

/* ===========================
   CONFIGURATION
   =========================== */
async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    
    // Check if response is OK
    if (!res.ok) {
      // Config endpoint not available, use defaults
      return;
    }
    
    // Check content type to ensure it's JSON
    const contentType = res.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      // Not a JSON response, skip config loading
      return;
    }
    
    const data = await res.json();

    // Load serial port settings
    if (data.port) {
      const portSelect = document.getElementById('portSelect');
      // Check if port exists in options, if not add it
      let portExists = false;
      for (let opt of portSelect.options) {
        if (opt.value === data.port) {
          portExists = true;
          break;
        }
      }
      if (!portExists && data.port) {
        const opt = document.createElement('option');
        opt.value = data.port;
        opt.textContent = data.port;
        portSelect.appendChild(opt);
      }
      portSelect.value = data.port;
    }
    if (data.baudrate) document.getElementById('baudrate').value = data.baudrate;

    if (data.elf_path) document.getElementById('elfPath').value = data.elf_path;
    if (data.compile_commands_path) document.getElementById('compileCommandsPath').value = data.compile_commands_path;
    if (data.toolchain_path) document.getElementById('toolchainPath').value = data.toolchain_path;
    if (data.patch_mode) document.getElementById('patchMode').value = data.patch_mode;
    if (data.watcher_enabled) document.getElementById('watcherEnable').checked = data.watcher_enabled;
    if (data.watch_dirs) updateWatchDirsList(data.watch_dirs);
    if (data.auto_compile !== undefined) document.getElementById('autoCompile').checked = data.auto_compile;
    if (data.nuttx_mode !== undefined) document.getElementById('nuttxMode').checked = data.nuttx_mode;

    updateWatcherStatus(data.watcher_enabled);
    
    // Start auto-inject polling if auto_compile is enabled
    if (data.auto_compile) {
      startAutoInjectPolling();
    }
  } catch (e) {
    // Silently ignore config load errors on startup
    console.warn('Config load skipped:', e.message);
  }
}

async function saveConfig(silent = false) {
  const config = {
    elf_path: document.getElementById('elfPath').value,
    compile_commands_path: document.getElementById('compileCommandsPath').value,
    toolchain_path: document.getElementById('toolchainPath').value,
    patch_mode: document.getElementById('patchMode').value,
    watcher_enabled: document.getElementById('watcherEnable').checked,
    watch_dirs: getWatchDirs(),
    auto_compile: document.getElementById('autoCompile').checked,
    nuttx_mode: document.getElementById('nuttxMode').checked
  };

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    const data = await res.json();

    if (data.success) {
      if (!silent) writeToOutput('[SUCCESS] Configuration saved', 'success');
    } else {
      throw new Error(data.message || 'Save failed');
    }
  } catch (e) {
    writeToOutput(`[ERROR] Save failed: ${e}`, 'error');
  }
}

function onNuttxModeChange() {
  saveConfig(true);
}

// Setup auto-save for all config inputs
function setupAutoSave() {
  // Text inputs - save on blur
  const textInputs = ['elfPath', 'compileCommandsPath', 'toolchainPath'];
  textInputs.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => saveConfig(true));
    }
  });

  // Select inputs - save on change
  const selectInputs = ['patchMode'];
  selectInputs.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => saveConfig(true));
    }
  });
}

/* ===========================
   WATCH DIRS MANAGEMENT
   =========================== */
function updateWatchDirsList(dirs) {
  const list = document.getElementById('watchDirsList');
  list.innerHTML = '';
  
  if (!dirs || dirs.length === 0) {
    return;
  }
  
  dirs.forEach((dir, index) => {
    addWatchDirItem(dir, index);
  });
}

function getWatchDirs() {
  const items = document.querySelectorAll('#watchDirsList .watch-dir-item input');
  return Array.from(items).map(input => input.value.trim()).filter(v => v);
}

function addWatchDir() {
  // Open file browser to select directory
  fileBrowserCallback = (path) => {
    addWatchDirItem(path);
    saveConfig(true); // Auto-save after adding
  };
  fileBrowserFilter = '';
  fileBrowserMode = 'dir';
  openFileBrowser(HOME_PATH);
}

function addWatchDirItem(path, index = null) {
  const list = document.getElementById('watchDirsList');
  const itemIndex = index !== null ? index : list.children.length;
  
  const item = document.createElement('div');
  item.className = 'watch-dir-item';
  item.innerHTML = `
    <input type="text" value="${path}" placeholder="/path/to/dir" onchange="saveConfig(true)" />
    <div class="dir-actions">
      <button class="dir-btn" onclick="browseWatchDir(this)" title="Browse">
        <i class="codicon codicon-folder-opened" style="font-size: 12px;"></i>
      </button>
      <button class="dir-btn" onclick="removeWatchDir(this)" title="Remove">
        <i class="codicon codicon-close" style="font-size: 12px;"></i>
      </button>
    </div>
  `;
  list.appendChild(item);
}

function browseWatchDir(btn) {
  const input = btn.closest('.watch-dir-item').querySelector('input');
  fileBrowserCallback = (path) => {
    input.value = path;
    saveConfig(true); // Auto-save after browse
  };
  fileBrowserFilter = '';
  fileBrowserMode = 'dir';
  openFileBrowser(input.value || HOME_PATH);
}

function removeWatchDir(btn) {
  btn.closest('.watch-dir-item').remove();
  saveConfig(true); // Auto-save after removing
}

function toggleWatcher() {
  const enabled = document.getElementById('watcherEnable').checked;
  updateWatcherStatus(enabled);
  // Sync to backend
  fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ watcher_enabled: enabled })
  });
}

function updateWatcherStatus(enabled) {
  const statusEl = document.getElementById('watcherStatus');
  statusEl.textContent = `Watcher: ${enabled ? 'On' : 'Off'}`;
}

function onAutoCompileChange() {
  const enabled = document.getElementById('autoCompile').checked;
  writeToOutput(`[INFO] Auto-inject on save: ${enabled ? 'Enabled' : 'Disabled'}`, 'info');
  // Sync to backend
  fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auto_compile: enabled })
  });
  
  // Start or stop auto-inject status polling
  if (enabled) {
    startAutoInjectPolling();
  } else {
    stopAutoInjectPolling();
  }
}

/* ===========================
   AUTO-INJECT STATUS POLLING
   =========================== */
function startAutoInjectPolling() {
  if (autoInjectPollInterval) return; // Already polling
  
  autoInjectPollInterval = setInterval(pollAutoInjectStatus, 500);
  writeToOutput('[INFO] Auto-inject status monitoring started', 'system');
}

function stopAutoInjectPolling() {
  if (autoInjectPollInterval) {
    clearInterval(autoInjectPollInterval);
    autoInjectPollInterval = null;
    writeToOutput('[INFO] Auto-inject status monitoring stopped', 'system');
  }
}

async function pollAutoInjectStatus() {
  try {
    const res = await fetch('/api/watch/auto_inject_status');
    const data = await res.json();
    
    if (!data.success) return;
    
    const status = data.status;
    const message = data.message;
    const progress = data.progress || 0;
    const modifiedFuncs = data.modified_funcs || [];
    const result = data.result || {};
    
    // Check if status changed
    const statusChanged = status !== lastAutoInjectStatus;
    
    // Only output if status changed
    if (statusChanged) {
      lastAutoInjectStatus = status;
      
      // Log status changes
      switch (status) {
        case 'detecting':
          writeToOutput(`[AUTO-INJECT] ${message}`, 'system');
          break;
        case 'generating':
          writeToOutput(`[AUTO-INJECT] ${message}`, 'info');
          // Update target function when modified functions are detected
          if (modifiedFuncs.length > 0) {
            document.getElementById('targetFunc').value = modifiedFuncs[0];
          }
          break;
        case 'compiling':
          writeToOutput(`[AUTO-INJECT] ${message}`, 'info');
          break;
        case 'injecting':
          writeToOutput(`[AUTO-INJECT] ${message}`, 'info');
          break;
        case 'success':
          writeToOutput(`[AUTO-INJECT] ${message}`, 'success');
          // Display injection statistics if available
          if (result && Object.keys(result).length > 0) {
            displayAutoInjectStats(result, modifiedFuncs[0] || 'unknown');
          }
          // Create preview tab for the patch
          if (modifiedFuncs.length > 0) {
            createPatchPreviewTab(modifiedFuncs[0]);
          }
          // Refresh slot UI after successful injection
          updateSlotUI();
          fetchFPBInfo(); // Refresh device info to show new slot state
          break;
        case 'failed':
          writeToOutput(`[AUTO-INJECT] ${message}`, 'error');
          break;
        case 'idle':
          // Silent for idle status changes
          break;
      }
      
      // Load patch source when generating or success
      if (status === 'generating' || status === 'success') {
        await loadPatchSourceFromBackend();
      }
    }
    
    // Update progress bar (always update progress, pass statusChanged for hide logic)
    updateAutoInjectProgress(progress, status, statusChanged);
    
  } catch (e) {
    // Silent error - don't spam console
  }
}

function displayAutoInjectStats(result, targetFunc) {
  const compileTime = result.compile_time || 0;
  const uploadTime = result.upload_time || 0;
  const codeSize = result.code_size || 0;
  const totalTime = result.total_time || (compileTime + uploadTime);
  const uploadSpeed = uploadTime > 0 ? Math.round(codeSize / uploadTime) : 0;
  const patchMode = result.patch_mode || 'unknown';
  
  writeToOutput(`--- Auto-Injection Statistics ---`, 'system');
  writeToOutput(`Target:        ${targetFunc} @ ${result.target_addr || 'unknown'}`, 'info');
  writeToOutput(`Inject func:   ${result.inject_func || 'unknown'} @ ${result.inject_addr || 'unknown'}`, 'info');
  writeToOutput(`Compile time:  ${compileTime.toFixed(2)}s`, 'info');
  writeToOutput(`Upload time:   ${uploadTime.toFixed(2)}s (${uploadSpeed} B/s)`, 'info');
  writeToOutput(`Code size:     ${codeSize} bytes`, 'info');
  writeToOutput(`Total time:    ${totalTime.toFixed(2)}s`, 'info');
  writeToOutput(`Injection mode: ${patchMode}`, 'success');
}

async function loadPatchSourceFromBackend() {
  try {
    const res = await fetch('/api/patch/source');
    const data = await res.json();
    if (data.success && data.content) {
      const patchSourceEl = document.getElementById('patchSource');
      if (patchSourceEl && patchSourceEl.value !== data.content) {
        patchSourceEl.value = data.content;
        writeToOutput('[AUTO-INJECT] Patch source updated in editor', 'info');
      }
      return data.content;
    }
  } catch (e) {
    // Silent error
  }
  return null;
}

async function createPatchPreviewTab(funcName) {
  const tabId = `patch_${funcName}`;
  const tabTitle = `patch_${funcName}.c`;
  
  // Load patch content from backend
  let patchContent = '';
  try {
    const res = await fetch('/api/patch/source');
    const data = await res.json();
    if (data.success && data.content) {
      patchContent = data.content;
    }
  } catch (e) {
    patchContent = `// Failed to load patch content for ${funcName}`;
  }
  
  // Check if tab already exists - update content if so
  const existingTab = editorTabs.find(t => t.id === tabId);
  if (existingTab) {
    // Update existing tab content
    const existingContent = document.getElementById(`tabContent_${tabId}`);
    if (existingContent) {
      const codeEl = existingContent.querySelector('code');
      if (codeEl) {
        codeEl.textContent = patchContent;
        // Re-apply syntax highlighting
        if (typeof hljs !== 'undefined') {
          hljs.highlightElement(codeEl);
        }
      }
    }
    switchEditorTab(tabId);
    return;
  }
  
  // Create new tab
  editorTabs.push({
    id: tabId,
    title: tabTitle,
    type: 'c',
    closable: true
  });
  
  // Add tab button
  const tabsHeader = document.getElementById('editorTabsHeader');
  const tabDiv = document.createElement('div');
  tabDiv.className = 'tab';
  tabDiv.setAttribute('data-tab', tabId);
  tabDiv.innerHTML = `
    <i class="codicon codicon-file-code tab-icon" style="color: #519aba;"></i>
    <span>${tabTitle}</span>
    <span class="tab-badge" style="background: #4caf50; color: white; font-size: 9px; padding: 1px 4px; border-radius: 3px; margin-left: 4px;">Preview</span>
    <div class="tab-close" onclick="closeTab('${tabId}', event)"><i class="codicon codicon-close"></i></div>
  `;
  tabDiv.onclick = () => switchEditorTab(tabId);
  tabsHeader.appendChild(tabDiv);
  
  // Add tab content (read-only code display)
  const tabsContent = document.querySelector('.editor-tabs-content');
  const contentDiv = document.createElement('div');
  contentDiv.className = 'tab-content';
  contentDiv.id = `tabContent_${tabId}`;
  
  contentDiv.innerHTML = `
    <div class="code-display" style="height: 100%; overflow: auto;">
      <div style="padding: 4px 8px; background: #2d2d2d; border-bottom: 1px solid #3c3c3c; font-size: 11px; color: #888;">
        <i class="codicon codicon-lock" style="margin-right: 4px;"></i>
        Auto-generated patch (read-only preview)
      </div>
      <pre style="margin: 0; padding: 8px; height: calc(100% - 30px); overflow: auto;"><code class="language-c">${escapeHtml(patchContent)}</code></pre>
    </div>
  `;
  tabsContent.appendChild(contentDiv);
  
  // Apply syntax highlighting
  if (typeof hljs !== 'undefined') {
    contentDiv.querySelectorAll('pre code').forEach(block => {
      try {
        hljs.highlightElement(block);
      } catch (e) {
        block.classList.add('hljs');
      }
    });
  }
  
  switchEditorTab(tabId);
  writeToOutput(`[AUTO-INJECT] Created preview tab: ${tabTitle}`, 'info');
}

function updateAutoInjectProgress(progress, status, statusChanged = false) {
  const progressEl = document.getElementById('injectProgress');
  const progressText = document.getElementById('injectProgressText');
  const progressFill = document.getElementById('injectProgressFill');
  
  if (!progressEl) return;
  
  // For idle status, hide progress bar
  if (status === 'idle') {
    // Don't immediately hide - let any existing timer finish
    return;
  }
  
  progressEl.style.display = 'flex';
  progressFill.style.width = `${progress}%`;
  
  if (status === 'success') {
    progressText.textContent = 'Auto-inject complete!';
    progressFill.style.background = '#4caf50';
    // Only set timeout when status just changed to success
    if (statusChanged) {
      if (autoInjectProgressHideTimer) clearTimeout(autoInjectProgressHideTimer);
      autoInjectProgressHideTimer = setTimeout(() => {
        progressEl.style.display = 'none';
        progressFill.style.width = '0%';
        progressFill.style.background = '';
        autoInjectProgressHideTimer = null;
      }, 3000);
    }
  } else if (status === 'failed') {
    progressText.textContent = 'Auto-inject failed!';
    progressFill.style.background = '#f44336';
    // Only set timeout when status just changed to failed
    if (statusChanged) {
      if (autoInjectProgressHideTimer) clearTimeout(autoInjectProgressHideTimer);
      autoInjectProgressHideTimer = setTimeout(() => {
        progressEl.style.display = 'none';
        progressFill.style.width = '0%';
        progressFill.style.background = '';
        autoInjectProgressHideTimer = null;
      }, 3000);
    }
  } else {
    // Clear any existing hide timer for ongoing operations
    if (autoInjectProgressHideTimer) {
      clearTimeout(autoInjectProgressHideTimer);
      autoInjectProgressHideTimer = null;
    }
    // Map status to display text
    const statusTexts = {
      'detecting': 'Detecting changes...',
      'generating': 'Generating patch...',
      'compiling': 'Compiling...',
      'injecting': 'Injecting...'
    };
    progressText.textContent = statusTexts[status] || status;
    progressFill.style.background = '';
  }
}

/* ===========================
   FILE BROWSER
   =========================== */
const HOME_PATH = '~';  // Will be expanded by backend

function browseFile(inputId, filter = '') {
  fileBrowserCallback = (path) => {
    document.getElementById(inputId).value = path;
    // Auto-save config after file selection
    saveConfig(true);
    // Auto-refresh symbols when ELF is selected
    if (inputId === 'elfPath' && path.endsWith('.elf')) {
      refreshSymbolsFromELF(path);
    }
  };
  fileBrowserFilter = filter;
  fileBrowserMode = 'file';
  openFileBrowser(HOME_PATH);
}

// Refresh symbols after ELF is loaded
async function refreshSymbolsFromELF(elfPath) {
  writeToOutput(`[INFO] Loading symbols from ${elfPath}...`, 'system');
  try {
    // Notify backend about the new ELF
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ elf_path: elfPath })
    });
    // Clear and show loading
    const list = document.getElementById('symbolList');
    list.innerHTML = '<div style="padding: 8px; font-size: 11px; opacity: 0.7;">Symbols ready. Search above...</div>';
    writeToOutput(`[SUCCESS] ELF loaded: ${elfPath}`, 'success');
  } catch (e) {
    writeToOutput(`[ERROR] Failed to load ELF: ${e}`, 'error');
  }
}

function browseDir(inputId) {
  fileBrowserCallback = (path) => {
    document.getElementById(inputId).value = path;
    // Auto-save config after directory selection
    saveConfig(true);
  };
  fileBrowserFilter = '';
  fileBrowserMode = 'dir';
  openFileBrowser(HOME_PATH);
}

async function openFileBrowser(path) {
  currentBrowserPath = path;
  document.getElementById('browserPath').value = path;
  document.getElementById('fileBrowserModal').classList.add('show');
  selectedBrowserItem = null;

  try {
    const res = await fetch(`/api/browse?path=${encodeURIComponent(path)}`);
    const data = await res.json();

    const list = document.getElementById('fileList');
    list.innerHTML = '';

    // Get actual path from response (backend expands ~)
    const actualPath = data.current_path || path;
    currentBrowserPath = actualPath;
    document.getElementById('browserPath').value = actualPath;

    // Parent directory navigation
    if (actualPath !== '/') {
      const parentPath = actualPath.split('/').slice(0, -1).join('/') || '/';
      const parentDiv = document.createElement('div');
      parentDiv.className = 'file-item folder';
      parentDiv.innerHTML = `<i class="codicon codicon-folder"></i><span>..</span>`;
      parentDiv.onclick = () => navigateTo(parentPath);
      list.appendChild(parentDiv);
    }

    data.items.forEach(item => {
      const itemPath = actualPath === '/' ? `/${item.name}` : `${actualPath}/${item.name}`;
      const isDir = item.type === 'dir';

      // Filter files if needed (in file mode)
      if (!isDir && fileBrowserMode === 'file' && fileBrowserFilter && !item.name.endsWith(fileBrowserFilter)) {
        return;
      }

      const div = document.createElement('div');
      div.className = `file-item ${isDir ? 'folder' : 'file'}`;
      div.innerHTML = `
        <i class="codicon codicon-${isDir ? 'folder' : 'file'}"></i>
        <span>${item.name}</span>
      `;

      div.onclick = () => {
        if (isDir) {
          if (fileBrowserMode === 'dir') {
            // In dir mode, single click selects, double click enters
            selectFileBrowserItem(div, itemPath);
          } else {
            // In file mode, click enters directory
            navigateTo(itemPath);
          }
        } else {
          selectFileBrowserItem(div, itemPath);
        }
      };

      div.ondblclick = () => {
        if (isDir) {
          navigateTo(itemPath);
        } else {
          // Double click on file selects and closes
          selectFileBrowserItem(div, itemPath);
          selectBrowserItem();
        }
      };

      list.appendChild(div);
    });
  } catch (e) {
    writeToOutput(`[ERROR] Browse failed: ${e}`, 'error');
  }
}

function navigateTo(path) {
  openFileBrowser(path);
}

function onBrowserPathKeyup(e) {
  if (e.key === 'Enter') {
    navigateTo(document.getElementById('browserPath').value);
  }
}

function selectFileBrowserItem(element, path) {
  document.querySelectorAll('.file-item').forEach(el => el.classList.remove('selected'));
  element.classList.add('selected');
  selectedBrowserItem = path;
}

function selectBrowserItem() {
  if (fileBrowserMode === 'dir') {
    // In dir mode, use selected dir if any, otherwise current path
    const path = selectedBrowserItem || currentBrowserPath;
    if (fileBrowserCallback) fileBrowserCallback(path);
  } else if (selectedBrowserItem) {
    if (fileBrowserCallback) fileBrowserCallback(selectedBrowserItem);
  }
  closeFileBrowser();
}

function closeFileBrowser() {
  document.getElementById('fileBrowserModal').classList.remove('show');
  selectedBrowserItem = null;
}

/* ===========================
   SERIAL PORT COMMAND
   =========================== */
async function sendTerminalCommand(data) {
  if (!isConnected) return;

  try {
    await fetch('/api/serial/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: data })
    });
  } catch (e) {
    // Silent fail for send errors
  }
}
