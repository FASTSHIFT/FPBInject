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
let slotStates = Array(6)
  .fill()
  .map(() => ({
    occupied: false,
    func: '',
    orig_addr: '',
    target_addr: '',
    code_size: 0,
  }));

// Tabs state
let editorTabs = [];
let activeEditorTab = null;

// Current patch tab info for manual mode
let currentPatchTab = null;

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
  loadThemePreference(); // Load theme FIRST before terminal init
  initTerminals();
  refreshPorts();
  loadConfig();
  initSashResize();
  loadLayoutPreferences();
  loadSidebarState(); // Load sidebar collapse state
  updateSlotUI();
  initSlotSelectListener();
  updateDisabledState(); // Initial disabled state
  setupAutoSave(); // Setup auto-save for config inputs
  setupSidebarStateListeners(); // Setup listeners for sidebar state persistence
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
  const disableWhenDisconnected = ['slotSelect', 'injectBtn'];
  const opacityElements = ['editorContainer', 'slotContainer'];

  disableWhenDisconnected.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.disabled = !isConnected;
      el.style.opacity = isConnected ? '1' : '0.5';
    }
  });

  // Add visual feedback for disabled sections
  opacityElements.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.style.opacity = isConnected ? '1' : '0.6';
      el.style.pointerEvents = isConnected ? 'auto' : 'none';
    }
  });

  // Device info content - disable all buttons and interactions when not connected
  const deviceInfoContent = document.getElementById('deviceInfoContent');
  if (deviceInfoContent) {
    deviceInfoContent.style.opacity = isConnected ? '1' : '0.5';
    deviceInfoContent.querySelectorAll('button').forEach((btn) => {
      btn.disabled = !isConnected;
    });
    deviceInfoContent.querySelectorAll('.slot-item').forEach((item) => {
      item.style.pointerEvents = isConnected ? 'auto' : 'none';
    });
  }

  // Device info buttons (backup selector)
  document.querySelectorAll('#slotContainer .slot-btn').forEach((btn) => {
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
  selection: '#264f78',
};

const lightTerminalTheme = {
  background: '#f3f3f3',
  foreground: '#333333',
  cursor: '#333333',
  cursorAccent: '#f3f3f3',
  selection: '#add6ff',
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
    themeIcon.className =
      currentTheme === 'light'
        ? 'codicon codicon-lightbulb'
        : 'codicon codicon-lightbulb-autofix';
  }
}

function updateTerminalTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  const termTheme =
    currentTheme === 'light' ? lightTerminalTheme : darkTerminalTheme;

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
function updateCornerSashPosition() {
  const sashCorner = document.getElementById('sashCorner');
  const sidebar = document.getElementById('sidebar');
  const panelContainer = document.getElementById('panelContainer');

  if (sashCorner && sidebar && panelContainer) {
    const sidebarRect = sidebar.getBoundingClientRect();
    const panelRect = panelContainer.getBoundingClientRect();
    // Position at the intersection of sidebar right edge and panel top edge
    sashCorner.style.left = sidebarRect.right - 2 + 'px';
    sashCorner.style.top = panelRect.top - 2 + 'px';
  }
}

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

  // Corner resize (simultaneous sidebar and panel resize)
  const sashCorner = document.getElementById('sashCorner');
  let isResizingCorner = false;

  if (sashCorner) {
    sashCorner.addEventListener('mousedown', (e) => {
      e.preventDefault();
      isResizingCorner = true;
      startX = e.clientX;
      startY = e.clientY;
      startWidth = sidebar.offsetWidth;
      startHeight = panelContainer.offsetHeight;
      document.body.classList.add('resizing-sidebar');
      document.body.classList.add('resizing-panel');
      sashCorner.classList.add('active');
    });
  }

  document.addEventListener('mousemove', (e) => {
    if (isResizingSidebar) {
      const delta = e.clientX - startX;
      const newWidth = startWidth + delta;
      // Minimum width only, no maximum - allow user to resize freely
      if (newWidth >= 150) {
        document.documentElement.style.setProperty(
          '--sidebar-width',
          newWidth + 'px',
        );
      }
    }

    if (isResizingPanel) {
      const delta = startY - e.clientY;
      const newHeight = startHeight + delta;
      // Minimum height only, no maximum - allow user to resize freely
      if (newHeight >= 80) {
        document.documentElement.style.setProperty(
          '--panel-height',
          newHeight + 'px',
        );
      }
    }

    if (isResizingCorner) {
      // Resize both sidebar and panel simultaneously
      const deltaX = e.clientX - startX;
      const deltaY = startY - e.clientY;
      const newWidth = startWidth + deltaX;
      const newHeight = startHeight + deltaY;

      if (newWidth >= 150) {
        document.documentElement.style.setProperty(
          '--sidebar-width',
          newWidth + 'px',
        );
      }
      if (newHeight >= 80) {
        document.documentElement.style.setProperty(
          '--panel-height',
          newHeight + 'px',
        );
      }
    }

    // Update corner sash position during any resize
    if (isResizingSidebar || isResizingPanel || isResizingCorner) {
      updateCornerSashPosition();
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

    if (isResizingCorner) {
      isResizingCorner = false;
      document.body.classList.remove('resizing-sidebar');
      document.body.classList.remove('resizing-panel');
      sashCorner.classList.remove('active');
      saveLayoutPreferences();
      fitTerminals();
    }
  });

  // Initial position update
  updateCornerSashPosition();

  // Update on window resize
  window.addEventListener('resize', updateCornerSashPosition);
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

  // Update corner sash position after layout is loaded
  requestAnimationFrame(updateCornerSashPosition);
}

function saveLayoutPreferences() {
  const sidebarWidth = getComputedStyle(
    document.documentElement,
  ).getPropertyValue('--sidebar-width');
  const panelHeight = getComputedStyle(
    document.documentElement,
  ).getPropertyValue('--panel-height');

  localStorage.setItem('fpbinject-sidebar-width', sidebarWidth.trim());
  localStorage.setItem('fpbinject-panel-height', panelHeight.trim());
}

/* ===========================
   SIDEBAR STATE PERSISTENCE
   =========================== */
const SIDEBAR_STATE_KEY = 'fpbinject-sidebar-state';

function loadSidebarState() {
  try {
    const savedState = localStorage.getItem(SIDEBAR_STATE_KEY);
    if (savedState) {
      const state = JSON.parse(savedState);
      // Apply saved open/closed state to each details element
      for (const [id, isOpen] of Object.entries(state)) {
        const details = document.getElementById(id);
        if (details && details.tagName === 'DETAILS') {
          details.open = isOpen;
        }
      }
    }
  } catch (e) {
    console.warn('Failed to load sidebar state:', e);
  }
}

function saveSidebarState() {
  try {
    const state = {};
    // Find all details elements with IDs that start with 'details-'
    document.querySelectorAll('details[id^="details-"]').forEach((details) => {
      state[details.id] = details.open;
    });
    localStorage.setItem(SIDEBAR_STATE_KEY, JSON.stringify(state));
  } catch (e) {
    console.warn('Failed to save sidebar state:', e);
  }
}

function setupSidebarStateListeners() {
  // Listen for toggle events on all sidebar details elements
  document.querySelectorAll('details[id^="details-"]').forEach((details) => {
    details.addEventListener('toggle', saveSidebarState);
  });
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
      allowProposedApi: true,
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
      allowProposedApi: true,
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
    rawTerminal.onData((data) => {
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

  document
    .getElementById('tabBtnTool')
    .classList.toggle('active', tab === 'tool');
  document
    .getElementById('tabBtnRaw')
    .classList.toggle('active', tab === 'raw');

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
    info: '\x1b[0m', // Default terminal color (works in both light/dark themes)
    success: '\x1b[32m', // Green
    warning: '\x1b[33m', // Yellow
    error: '\x1b[31m', // Red
    system: '\x1b[36m', // Cyan
  };
  const color = colors[type] || colors.info;

  // Split message by newlines and write each line separately
  const lines = message.split('\n');
  lines.forEach((line) => {
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

      // Hide/show action buttons based on occupied state
      const actionsDiv = slotItem.querySelector('.slot-actions');
      if (actionsDiv) {
        actionsDiv.style.display = state.occupied ? 'flex' : 'none';
      }
    }

    if (funcSpan) {
      if (state.occupied) {
        // Format: orig_addr (func_name) -> target_addr, size bytes
        const funcName = state.func ? ` (${state.func})` : '';
        const sizeInfo = state.code_size ? `, ${state.code_size} Bytes` : '';
        funcSpan.textContent = `${state.orig_addr}${funcName} → ${state.target_addr}${sizeInfo}`;
        funcSpan.title = `Original: ${state.orig_addr}${funcName}\nTarget: ${state.target_addr}\nCode size: ${state.code_size || 0} Bytes`;
      } else {
        funcSpan.textContent = 'Empty';
        funcSpan.title = '';
      }
    }

    if (state.occupied) activeCount++;
  }

  document.getElementById('activeSlotCount').textContent = `${activeCount}/6`;
  document.getElementById('currentSlotDisplay').textContent =
    `Slot: ${selectedSlot}`;
  document.getElementById('slotSelect').value = selectedSlot;
}

function selectSlot(slotId) {
  selectedSlot = parseInt(slotId);
  updateSlotUI();
  writeToOutput(`[INFO] Selected Slot ${slotId}`, 'info');

  // If slot has a function, open its disassembly view
  const slotState = slotStates[slotId];
  if (slotState && slotState.func) {
    const funcName = slotState.func;
    const addr = slotState.addr || '0x00000000';
    // Open disassembly tab for this function
    openDisassembly(funcName, addr);
  }
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
      body: JSON.stringify({ comp: slotId }),
    });
    const data = await res.json();

    if (data.success) {
      slotStates[slotId] = {
        occupied: false,
        func: '',
        orig_addr: '',
        target_addr: '',
        code_size: 0,
      };
      updateSlotUI();
      writeToOutput(`[SUCCESS] Slot ${slotId} cleared`, 'success');
      // Refresh device info to get accurate state
      fpbInfo();
    } else {
      writeToOutput(
        `[ERROR] Failed to clear slot ${slotId}: ${data.message}`,
        'error',
      );
    }
  } catch (e) {
    writeToOutput(`[ERROR] Unpatch error: ${e}`, 'error');
  }
}

async function fpbReinject(slotId) {
  // Re-inject using saved patch source from backend
  if (!isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  // Get the function name for this slot
  const slotState = slotStates[slotId];
  const targetFunc = slotState?.func;

  if (!targetFunc) {
    writeToOutput(
      `[ERROR] Slot ${slotId} is empty, nothing to re-inject`,
      'error',
    );
    return;
  }

  writeToOutput(
    `[INFO] Re-injecting ${targetFunc} to Slot ${slotId}...`,
    'info',
  );

  try {
    // Get the patch source from backend (auto-saved from last injection)
    const sourceRes = await fetch('/api/patch/source');
    const sourceData = await sourceRes.json();

    if (!sourceData.success || !sourceData.content?.trim()) {
      writeToOutput(
        '[ERROR] No patch source available. Please use Auto Inject on Save first.',
        'error',
      );
      return;
    }

    const patchSource = sourceData.content;
    const patchMode =
      document.getElementById('patchMode')?.value || 'trampoline';

    const res = await fetch('/api/fpb/inject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_content: patchSource,
        target_func: targetFunc,
        patch_mode: patchMode,
        comp: slotId, // Force specific slot
      }),
    });
    const data = await res.json();

    if (data.success) {
      writeToOutput(
        `[SUCCESS] Re-injected ${targetFunc} to Slot ${slotId}`,
        'success',
      );
      await fpbInfo();
    } else {
      writeToOutput(
        `[ERROR] Re-inject failed: ${data.error || 'Unknown error'}`,
        'error',
      );
    }
  } catch (e) {
    writeToOutput(`[ERROR] Re-inject error: ${e}`, 'error');
  }
}

async function fpbInjectMulti() {
  // Inject all functions in patch source using multi-inject API
  if (!isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  const patchSource = document.getElementById('patchSource')?.value || '';
  if (!patchSource.trim()) {
    writeToOutput('[ERROR] No patch source code available', 'error');
    return;
  }

  writeToOutput('[INFO] Injecting all functions...', 'info');

  try {
    const patchMode =
      document.getElementById('patchMode')?.value || 'trampoline';
    const res = await fetch('/api/fpb/inject/multi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_content: patchSource,
        patch_mode: patchMode,
      }),
    });
    const data = await res.json();

    if (data.success) {
      const successCount = data.successful_count || 0;
      const totalCount = data.total_count || 0;
      writeToOutput(
        `[SUCCESS] Injected ${successCount}/${totalCount} functions`,
        'success',
      );
      displayAutoInjectStats(data, 'multi');
      await fpbInfo();
    } else {
      writeToOutput(
        `[ERROR] Multi-inject failed: ${data.error || 'Unknown error'}`,
        'error',
      );
    }
  } catch (e) {
    writeToOutput(`[ERROR] Multi-inject error: ${e}`, 'error');
  }
}

async function fpbUnpatchAll() {
  if (!isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  // Confirm before clearing all slots
  if (
    !confirm(
      'Are you sure you want to clear all FPB slots? This will unpatch all injected functions.',
    )
  ) {
    return;
  }

  try {
    const res = await fetch('/api/fpb/unpatch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ all: true }),
    });
    const data = await res.json();

    if (data.success) {
      slotStates = Array(6)
        .fill()
        .map(() => ({
          occupied: false,
          func: '',
          orig_addr: '',
          target_addr: '',
          code_size: 0,
        }));
      updateSlotUI();
      writeToOutput('[SUCCESS] All slots cleared and memory freed', 'success');
      // Refresh device info to get accurate state
      fpbInfo();
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
    ports.forEach((p) => {
      const opt = document.createElement('option');
      // Support both string format and object format {port: "xxx", desc: "xxx"}
      const portName =
        typeof p === 'string' ? p : p.port || p.device || String(p);
      opt.value = portName;
      opt.textContent = portName;
      sel.appendChild(opt);
    });

    // Restore previous selection if still available
    const portValues = ports.map((p) =>
      typeof p === 'string' ? p : p.port || p.device || String(p),
    );
    if (portValues.includes(prevValue)) {
      sel.value = prevValue;
    }
  } catch (e) {
    writeToOutput(`[ERROR] Failed to refresh ports: ${e}`, 'error');
  }
}

// Handle successful connection - shared by manual connect and auto-connect
function handleConnected(port, message = null) {
  const btn = document.getElementById('connectBtn');
  const statusEl = document.getElementById('connectionStatus');

  isConnected = true;
  btn.textContent = 'Disconnect';
  btn.classList.add('connected');
  statusEl.textContent = port;
  writeToOutput(message || `[CONNECTED] ${port}`, 'success');
  startLogPolling();
  fpbInfo();
  updateDisabledState();
}

// Handle disconnection
function handleDisconnected() {
  const btn = document.getElementById('connectBtn');
  const statusEl = document.getElementById('connectionStatus');

  isConnected = false;
  btn.textContent = 'Connect';
  btn.classList.remove('connected');
  statusEl.textContent = 'Disconnected';
  writeToOutput('[DISCONNECTED]', 'warning');
  stopLogPolling();
  updateDisabledState();
}

async function toggleConnect() {
  const btn = document.getElementById('connectBtn');

  if (!isConnected) {
    const port = document.getElementById('portSelect').value;
    const baud = document.getElementById('baudrate').value;

    btn.disabled = true;
    btn.textContent = 'Connecting...';

    try {
      const res = await fetch('/api/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ port, baudrate: parseInt(baud) }),
      });
      const data = await res.json();

      if (data.success) {
        handleConnected(port, `[CONNECTED] ${port} @ ${baud} baud`);
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
      handleDisconnected();
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
let slotUpdateId = 0; // Track slot updates for push notification

function startLogPolling() {
  stopLogPolling();
  toolLogNextId = 0;
  rawLogNextId = 0;
  slotUpdateId = 0;
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
    const res = await fetch(
      `/api/logs?tool_since=${toolLogNextId}&raw_since=${rawLogNextId}&slot_since=${slotUpdateId}`,
    );

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
      console.warn(
        'Log parse error:',
        parseError,
        'Response:',
        text.substring(0, 100),
      );
      return;
    }

    // Update next IDs for incremental polling
    if (data.tool_next !== undefined) toolLogNextId = data.tool_next;
    if (data.raw_next !== undefined) rawLogNextId = data.raw_next;

    // Tool logs (Python output) -> OUTPUT terminal
    if (
      data.tool_logs &&
      Array.isArray(data.tool_logs) &&
      data.tool_logs.length > 0
    ) {
      data.tool_logs.forEach((log) => {
        writeToOutput(log, 'info');
      });
    }

    // Raw serial data -> SERIAL PORT terminal
    if (data.raw_data && data.raw_data.length > 0) {
      writeToSerial(data.raw_data);
    }

    // Slot update push notification (decoupled from request logic)
    if (
      data.slot_update_id !== undefined &&
      data.slot_update_id > slotUpdateId
    ) {
      slotUpdateId = data.slot_update_id;
      // Update slot states from pushed data
      if (data.slot_data && data.slot_data.slots) {
        data.slot_data.slots.forEach((slot, i) => {
          if (i < 6) {
            slotStates[i] = {
              occupied: slot.occupied || false,
              func: slot.func || '',
              orig_addr: slot.orig_addr || '',
              target_addr: slot.target_addr || '',
              code_size: slot.code_size || 0,
            };
          }
        });
        updateSlotUI();
        // Update memory info if available
        if (data.slot_data.memory) {
          updateMemoryInfo(data.slot_data.memory);
        }
      }
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
              func: slot.func || '',
              orig_addr: slot.orig_addr || '',
              target_addr: slot.target_addr || '',
              code_size: slot.code_size || 0,
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
      writeToOutput(
        `[ERROR] ${data.error || 'Failed to get device info'}`,
        'error',
      );
    }
  } catch (e) {
    writeToOutput(`[ERROR] Info failed: ${e}`, 'error');
  }
}

function updateMemoryInfo(memory) {
  const memoryEl = document.getElementById('memoryInfo');
  if (!memoryEl) return;

  const isDynamic = memory.is_dynamic || false;
  const base = memory.base || 0;
  const size = memory.size || 0;
  const used = memory.used || 0;

  if (isDynamic) {
    // Dynamic mode: show alloc type and used memory
    memoryEl.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: center; gap: 8px;">
        <span style="font-size: 10px; padding: 2px 6px; background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); border-radius: 3px;">Dynamic</span>
        <span style="font-size: 10px; color: var(--vscode-descriptionForeground);">Used: ${used} Bytes</span>
      </div>
    `;
  } else {
    // Static mode: show base, size, used with progress bar
    const free = size - used;
    const usedPercent = size > 0 ? Math.round((used / size) * 100) : 0;
    memoryEl.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 4px;">
        <div style="display: flex; align-items: center; justify-content: center; gap: 8px;">
          <span style="font-size: 10px; padding: 2px 6px; background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); border-radius: 3px;">Static</span>
          <span style="font-size: 10px; color: var(--vscode-descriptionForeground);">Base: 0x${base.toString(16).toUpperCase().padStart(8, '0')}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 4px;">
          <div style="flex: 1; height: 4px; background: var(--vscode-input-background); border-radius: 2px; overflow: hidden;">
            <div style="width: ${usedPercent}%; height: 100%; background: var(--vscode-progressBar-background);"></div>
          </div>
          <span style="font-size: 9px; color: var(--vscode-descriptionForeground); white-space: nowrap;">${used}/${size} (${usedPercent}%)</span>
        </div>
      </div>
    `;
  }
}

/* ===========================
   PATCH OPERATIONS
   =========================== */

// Unified template generation function
function generatePatchTemplate(
  funcName,
  slot,
  signature = null,
  sourceFile = null,
  decompiled = null,
  angrNotInstalled = false,
) {
  let returnType = 'void';
  let params = '';

  if (signature) {
    const parsed = parseSignature(signature, funcName);
    returnType = parsed.returnType;
    params = parsed.params;
  }

  const injectFuncName = `inject_${funcName}`;
  const paramNames = extractParamNames(params);
  const callParams = paramNames.length > 0 ? paramNames.join(', ') : '';

  // Format decompiled code as comment block
  let decompiledSection = '';
  if (decompiled) {
    const decompiledLines = decompiled
      .split('\n')
      .map((line) => ' * ' + line)
      .join('\n');
    decompiledSection = `
/*
 * ============== DECOMPILED REFERENCE ==============
${decompiledLines}
 * ==================================================
 */

`;
  } else if (angrNotInstalled) {
    decompiledSection = `
/*
 * TIP: Install 'angr' for automatic decompilation reference:
 *   pip install angr
 * Then enable "Enable Decompilation" in Settings panel.
 */

`;
  }

  return `/*
 * Patch for: ${funcName}
 * Slot: ${slot}
${sourceFile ? ` * Source: ${sourceFile}` : ''}
 */

#include <stdint.h>
#include <stdio.h>

${signature ? `// Original function signature:\n// ${signature}` : `// Original function prototype (adjust as needed)\n// extern ${returnType} ${funcName}(${params || 'void'});`}
${decompiledSection}
// Inject function - will replace ${funcName}
${returnType} ${injectFuncName}(${params || 'void'}) {
    printf("Patched ${funcName} executed!\\n");

    // Your patch code here

${returnType !== 'void' ? `    // TODO: return appropriate value\n    return 0;` : `    // Call original if needed:\n    // ${funcName}_original(${callParams});`}
}
`;
}

async function generatePatch() {
  const targetFunc = document.getElementById('targetFunc').value;
  if (!targetFunc) {
    writeToOutput('[ERROR] Please enter target function name', 'error');
    return;
  }

  writeToOutput(
    `[GENERATE] Analyzing function signature for ${targetFunc}...`,
    'system',
  );

  let signature = null;
  let sourceFile = null;

  // Try to get function signature from backend
  try {
    const res = await fetch(
      `/api/symbols/signature?func=${encodeURIComponent(targetFunc)}`,
    );
    const data = await res.json();

    if (data.success && data.signature) {
      signature = data.signature;
      sourceFile = data.source_file;
      writeToOutput(`[INFO] Found signature: ${signature}`, 'info');
      if (sourceFile) {
        writeToOutput(`[INFO] Source file: ${sourceFile}`, 'info');
      }
    } else {
      writeToOutput(
        `[WARN] Could not find function signature, using default template`,
        'warning',
      );
    }
  } catch (e) {
    writeToOutput(`[WARN] Failed to fetch signature: ${e}`, 'warning');
  }

  const template = generatePatchTemplate(
    targetFunc,
    selectedSlot,
    signature,
    sourceFile,
  );
  document.getElementById('patchSource').value = template;
  writeToOutput(
    `[SUCCESS] Patch template generated with ${signature ? 'analyzed' : 'default'} signature`,
    'success',
  );
}

// Parse function signature to extract return type and parameters
function parseSignature(signature, funcName) {
  let returnType = 'void';
  let params = '';

  // Remove leading static/inline/extern keywords (may be multiple)
  let sig = signature
    .replace(
      /^\s*((?:(?:static|inline|extern|const|volatile|__attribute__\s*\([^)]*\))\s+)*)/,
      '',
    )
    .trim();

  // Find function name and opening parenthesis
  // Pattern: return_type func_name(
  const funcPattern = new RegExp(`^(.+?)\\s+${funcName}\\s*\\((.*)\\)\\s*$`);
  const match = sig.match(funcPattern);

  if (match) {
    returnType = match[1].trim() || 'void';
    params = match[2].trim();
    // Normalize void parameters
    if (params.toLowerCase() === 'void') {
      params = '';
    }
  } else {
    // Fallback: try simpler parsing
    const funcNameIdx = sig.indexOf(funcName);
    if (funcNameIdx > 0) {
      returnType = sig.substring(0, funcNameIdx).trim() || 'void';
      const paramsStart = sig.indexOf('(', funcNameIdx);
      const paramsEnd = sig.lastIndexOf(')');
      if (paramsStart !== -1 && paramsEnd !== -1) {
        params = sig.substring(paramsStart + 1, paramsEnd).trim();
        if (params.toLowerCase() === 'void') {
          params = '';
        }
      }
    }
  }

  return { returnType, params };
}

// Extract parameter names from parameter list
function extractParamNames(params) {
  if (!params || params.trim() === '' || params.toLowerCase() === 'void') {
    return [];
  }

  const names = [];
  // Split by comma, handling nested parentheses (for function pointers)
  const parts = [];
  let depth = 0;
  let current = '';

  for (const ch of params) {
    if (ch === '(') depth++;
    else if (ch === ')') depth--;
    else if (ch === ',' && depth === 0) {
      parts.push(current.trim());
      current = '';
      continue;
    }
    current += ch;
  }
  if (current.trim()) {
    parts.push(current.trim());
  }

  for (const part of parts) {
    // Extract the last identifier as parameter name
    // Handle arrays like "int arr[]" or "int arr[10]"
    const arrayMatch = part.match(/(\w+)\s*\[/);
    if (arrayMatch) {
      names.push(arrayMatch[1]);
      continue;
    }

    // Handle function pointers like "void (*callback)(int)"
    const funcPtrMatch = part.match(/\(\s*\*\s*(\w+)\s*\)/);
    if (funcPtrMatch) {
      names.push(funcPtrMatch[1]);
      continue;
    }

    // Handle normal parameters - last word is the name
    const words = part.replace(/[*&]/g, ' ').trim().split(/\s+/);
    if (words.length > 0) {
      const lastWord = words[words.length - 1];
      // Skip if it's a type keyword
      if (
        ![
          'int',
          'char',
          'void',
          'float',
          'double',
          'long',
          'short',
          'unsigned',
          'signed',
          'const',
          'volatile',
          'struct',
          'enum',
          'union',
        ].includes(lastWord)
      ) {
        names.push(lastWord);
      }
    }
  }

  return names;
}

async function performInject() {
  if (!isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  // Check if all slots are occupied
  const occupiedSlots = slotStates.filter((s) => s.occupied).length;
  const totalSlots = slotStates.length;

  if (occupiedSlots >= totalSlots) {
    // All slots are full, show warning dialog
    const shouldContinue = confirm(
      `⚠️ All ${totalSlots} FPB Slots are occupied!\n\n` +
        `Current slots:\n` +
        slotStates
          .map((s, i) => `  Slot ${i}: ${s.func || 'Empty'}`)
          .join('\n') +
        `\n\nPlease clear some slots before injecting.\n` +
        `Use "Clear All" button or click ✕ on individual slots.\n\n` +
        `Click OK to open Device Info panel.`,
    );

    if (shouldContinue) {
      // Expand the Device Info section
      const deviceDetails = document.getElementById('details-device');
      if (deviceDetails) {
        deviceDetails.open = true;
      }
    }

    writeToOutput(
      `[ERROR] All ${totalSlots} slots are occupied. Clear some slots before injecting.`,
      'error',
    );
    return;
  }

  // Check if selected slot is already occupied
  if (slotStates[selectedSlot].occupied) {
    const slotFunc = slotStates[selectedSlot].func;
    const overwrite = confirm(
      `⚠️ Slot ${selectedSlot} is already occupied by "${slotFunc}".\n\n` +
        `Do you want to overwrite it?`,
    );

    if (!overwrite) {
      writeToOutput(
        `[INFO] Injection cancelled - slot ${selectedSlot} is occupied`,
        'info',
      );
      return;
    }
  }

  // Get source from current patch tab
  if (!currentPatchTab || !currentPatchTab.funcName) {
    writeToOutput('[ERROR] No patch tab selected', 'error');
    return;
  }

  const tabId = currentPatchTab.id;
  const targetFunc = currentPatchTab.funcName;
  const textarea = document.getElementById(`editor_${tabId}`);

  if (!textarea) {
    writeToOutput('[ERROR] Editor not found', 'error');
    return;
  }

  const source = textarea.value;

  if (!source.trim()) {
    writeToOutput('[ERROR] No patch source code', 'error');
    return;
  }

  const progressEl = document.getElementById('injectProgress');
  const progressText = document.getElementById('injectProgressText');
  const progressFill = document.getElementById('injectProgressFill');

  progressEl.style.display = 'flex';
  progressText.textContent = 'Starting...';
  progressFill.style.width = '5%';

  writeToOutput(
    `[INJECT] Starting injection of ${targetFunc} to slot ${selectedSlot}...`,
    'system',
  );

  try {
    // Use streaming API for real-time progress
    const response = await fetch('/api/fpb/inject/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_content: source,
        target_func: targetFunc,
        comp: selectedSlot,
        patch_mode: document.getElementById('patchMode').value,
      }),
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
              const overallPercent = 30 + uploadPercent * 0.6;
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

      // Display injection statistics
      displayInjectionStats(finalResult, targetFunc);

      // Refresh device info to get actual slot states from device (await to ensure UI updates)
      await fpbInfo();

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
  const totalTime = data.total_time || compileTime + uploadTime;
  const uploadSpeed = uploadTime > 0 ? Math.round(codeSize / uploadTime) : 0;
  const patchMode =
    data.patch_mode || document.getElementById('patchMode').value;

  writeToOutput(`[SUCCESS] Injection complete!`, 'success');
  writeToOutput(`--- Injection Statistics ---`, 'system');
  writeToOutput(
    `Target:        ${targetFunc} @ ${data.target_addr || 'unknown'}`,
    'info',
  );
  writeToOutput(
    `Inject func:   ${data.inject_func || 'unknown'} @ ${data.inject_addr || 'unknown'}`,
    'info',
  );
  writeToOutput(`Compile time:  ${compileTime.toFixed(2)}s`, 'info');
  writeToOutput(
    `Upload time:   ${uploadTime.toFixed(2)}s (${uploadSpeed} B/s)`,
    'info',
  );
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
    list.innerHTML =
      '<div style="padding: 8px; font-size: 11px; opacity: 0.7;">Enter at least 2 characters</div>';
    return;
  }

  try {
    const res = await fetch(
      `/api/symbols/search?q=${encodeURIComponent(query)}`,
    );
    const data = await res.json();

    if (data.symbols && data.symbols.length > 0) {
      list.innerHTML = data.symbols
        .map(
          (sym) => `
        <div class="symbol-item" onclick="openDisassembly('${sym.name}', '${sym.addr}')" ondblclick="openManualPatchTab('${sym.name}')">
          <i class="codicon codicon-symbol-method symbol-icon"></i>
          <span class="symbol-name">${sym.name}</span>
          <span class="symbol-addr">${sym.addr}</span>
        </div>
      `,
        )
        .join('');
    } else if (data.error) {
      list.innerHTML = `<div style="padding: 8px; font-size: 11px; opacity: 0.7; color: #f44336;">${data.error}</div>`;
    } else {
      list.innerHTML =
        '<div style="padding: 8px; font-size: 11px; opacity: 0.7;">No symbols found</div>';
    }
  } catch (e) {
    list.innerHTML = `<div style="padding: 8px; font-size: 11px; opacity: 0.7; color: #f44336;">Error: ${e.message}</div>`;
  }
}

function selectSymbol(name) {
  writeToOutput(`[INFO] Selected symbol: ${name}`, 'info');
}

// Handler for enable decompile checkbox change
function onEnableDecompileChange() {
  saveConfig(true);
}

// Open a manual patch tab for the given function
async function openManualPatchTab(funcName) {
  const tabId = `patch_${funcName}`;
  const tabTitle = `patch_${funcName}.c`;

  // Check if tab already exists
  if (editorTabs.find((t) => t.id === tabId)) {
    switchEditorTab(tabId);
    return;
  }

  const enableDecompile = document.getElementById('enableDecompile')?.checked;

  writeToOutput(
    `[PATCH] Creating manual patch tab for ${funcName}...`,
    'system',
  );

  // Create tab immediately with loading indicator if decompilation is enabled
  const loadingContent = enableDecompile
    ? `/*\n * Loading...\n * \n * Decompiling ${funcName}, please wait...\n * This may take a few seconds.\n */\n`
    : '';

  // Create new tab entry
  editorTabs.push({
    id: tabId,
    title: tabTitle,
    type: 'c',
    closable: true,
    funcName: funcName,
    content: loadingContent,
  });

  // Add tab button
  const tabsHeader = document.getElementById('editorTabsHeader');
  const tabDiv = document.createElement('div');
  tabDiv.className = 'tab';
  tabDiv.setAttribute('data-tab', tabId);
  tabDiv.innerHTML = `
    <i class="codicon codicon-file-code tab-icon" style="color: #e37933;"></i>
    <span>${tabTitle}</span>
    <div class="tab-close" onclick="closeTab('${tabId}', event)"><i class="codicon codicon-close"></i></div>
  `;
  tabDiv.onclick = () => switchEditorTab(tabId);
  tabsHeader.appendChild(tabDiv);

  // Add tab content
  const tabsContent = document.querySelector('.editor-tabs-content');
  const contentDiv = document.createElement('div');
  contentDiv.className = 'tab-content';
  contentDiv.id = `tabContent_${tabId}`;

  contentDiv.innerHTML = `
    <div class="editor-main" style="height: 100%;">
      <textarea id="editor_${tabId}" class="code-editor" spellcheck="false">${escapeHtml(loadingContent)}</textarea>
    </div>
  `;
  tabsContent.appendChild(contentDiv);

  // Switch to the new tab immediately
  switchEditorTab(tabId);
  currentPatchTab = { id: tabId, funcName: funcName };

  // Now fetch data in background
  let template = '';
  let decompiled = null;
  let angrNotInstalled = false;

  // Conditionally fetch decompiled code
  let decompilePromise = Promise.resolve(null);
  if (enableDecompile) {
    writeToOutput(
      `[DECOMPILE] Requesting decompilation for ${funcName}...`,
      'system',
    );
    decompilePromise = fetch(
      `/api/symbols/decompile?func=${encodeURIComponent(funcName)}`,
    )
      .then((res) => res.json())
      .then((data) => {
        if (data.success && data.decompiled) {
          return { decompiled: data.decompiled, notInstalled: false };
        }
        // Check if angr is not installed
        if (data.error === 'ANGR_NOT_INSTALLED') {
          return { decompiled: null, notInstalled: true };
        }
        return { decompiled: null, notInstalled: false };
      })
      .catch(() => ({ decompiled: null, notInstalled: false }));
  }

  try {
    const res = await fetch(
      `/api/symbols/signature?func=${encodeURIComponent(funcName)}`,
    );
    const data = await res.json();

    let signature = null;
    let sourceFile = null;

    if (data.success && data.signature) {
      signature = data.signature;
      sourceFile = data.source_file;
    }

    // Wait for decompilation result
    const decompileResult = await decompilePromise;
    decompiled = decompileResult?.decompiled || null;
    angrNotInstalled = decompileResult?.notInstalled || false;

    template = generatePatchTemplate(
      funcName,
      selectedSlot,
      signature,
      sourceFile,
      decompiled,
      angrNotInstalled,
    );

    if (decompiled) {
      writeToOutput(`[INFO] Decompiled code included as reference`, 'info');
    } else if (angrNotInstalled) {
      writeToOutput(
        `[INFO] angr not installed - install with: pip install angr`,
        'info',
      );
    }
  } catch (e) {
    const decompileResult = await decompilePromise;
    decompiled = decompileResult?.decompiled || null;
    angrNotInstalled = decompileResult?.notInstalled || false;
    template = generatePatchTemplate(
      funcName,
      selectedSlot,
      null,
      null,
      decompiled,
      angrNotInstalled,
    );
  }

  // Update tab content with final template
  const textarea = document.getElementById(`editor_${tabId}`);
  if (textarea) {
    textarea.value = template;
    textarea.dataset.funcName = funcName;
    textarea.dataset.tabId = tabId;
  }

  // Update stored content
  const tabEntry = editorTabs.find((t) => t.id === tabId);
  if (tabEntry) {
    tabEntry.content = template;
  }

  writeToOutput(`[SUCCESS] Created patch tab: ${tabTitle}`, 'success');
}

async function openDisassembly(funcName, addr) {
  const tabId = `disasm_${funcName}`;

  // Check if tab already exists
  if (editorTabs.find((t) => t.id === tabId)) {
    switchEditorTab(tabId);
    return;
  }

  writeToOutput(`[DISASM] Loading disassembly for ${funcName}...`, 'system');

  try {
    const res = await fetch(
      `/api/symbols/disasm?func=${encodeURIComponent(funcName)}`,
    );
    const data = await res.json();

    // Create new tab
    editorTabs.push({
      id: tabId,
      title: `${funcName}.asm`,
      type: 'asm',
      closable: true,
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

    const disasmCode =
      data.disasm ||
      `; Disassembly for ${funcName} @ ${addr}\n; (Disassembly data not available)`;

    contentDiv.innerHTML = `
      <div class="code-display">
        <pre><code class="language-x86asm">${escapeHtml(disasmCode)}</code></pre>
      </div>
    `;
    tabsContent.appendChild(contentDiv);

    // Apply syntax highlighting (try multiple methods)
    if (typeof hljs !== 'undefined') {
      contentDiv.querySelectorAll('pre code').forEach((block) => {
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
  document.querySelectorAll('.editor-tabs-header .tab').forEach((tab) => {
    tab.classList.toggle('active', tab.getAttribute('data-tab') === tabId);
  });

  // Update tab content - handle empty state
  document.querySelectorAll('.tab-content').forEach((content) => {
    if (content.id === 'tabContent_empty') {
      content.classList.toggle('active', editorTabs.length === 0);
    } else {
      content.classList.toggle('active', content.id === `tabContent_${tabId}`);
    }
  });

  // Show/hide manual inject controls based on tab type
  // Show for manual patch tabs (type 'c'), hide for asm tabs and preview tabs
  const editorToolbar = document.querySelector('.editor-toolbar');
  if (editorToolbar) {
    const tabInfo = editorTabs.find((t) => t.id === tabId);
    // Only show toolbar for manual patch tabs (type 'c'), not preview tabs
    const isManualPatchTab = tabInfo && tabInfo.type === 'c';
    editorToolbar.style.display = isManualPatchTab ? 'flex' : 'none';

    // Update currentPatchTab if switching to a patch tab
    if (isManualPatchTab && tabInfo.funcName) {
      currentPatchTab = { id: tabId, funcName: tabInfo.funcName };
    }
  }
}

// Save patch file
async function savePatchFile() {
  if (!currentPatchTab || !currentPatchTab.funcName) {
    writeToOutput('[ERROR] No patch tab selected', 'error');
    return;
  }

  const funcName = currentPatchTab.funcName;
  const tabId = currentPatchTab.id;
  const textarea = document.getElementById(`editor_${tabId}`);

  if (!textarea) {
    writeToOutput('[ERROR] Editor not found', 'error');
    return;
  }

  const content = textarea.value;
  const fileName = `patch_${funcName}.c`;

  // Open file browser to select save location
  fileBrowserCallback = async (selectedPath) => {
    if (!selectedPath) return;

    const fullPath = selectedPath.endsWith('/')
      ? selectedPath + fileName
      : selectedPath + '/' + fileName;

    try {
      const res = await fetch('/api/file/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: fullPath, content: content }),
      });
      const data = await res.json();

      if (data.success) {
        writeToOutput(`[SUCCESS] Saved patch to: ${fullPath}`, 'success');
      } else {
        writeToOutput(`[ERROR] Failed to save: ${data.error}`, 'error');
      }
    } catch (e) {
      writeToOutput(`[ERROR] Failed to save file: ${e}`, 'error');
    }
  };
  fileBrowserFilter = '';
  fileBrowserMode = 'dir';
  openFileBrowser(HOME_PATH);
}

function closeTab(tabId, event) {
  if (event) event.stopPropagation();

  const tabInfo = editorTabs.find((t) => t.id === tabId);
  if (!tabInfo || !tabInfo.closable) return;

  // Remove from tabs array
  editorTabs = editorTabs.filter((t) => t.id !== tabId);

  // Remove DOM elements
  document.querySelector(`.tab[data-tab="${tabId}"]`)?.remove();
  document.getElementById(`tabContent_${tabId}`)?.remove();

  // Clear currentPatchTab if it was the closed tab
  if (currentPatchTab && currentPatchTab.id === tabId) {
    currentPatchTab = null;
  }

  // Switch to first tab if current was closed, or show empty state
  if (activeEditorTab === tabId) {
    if (editorTabs.length > 0) {
      switchEditorTab(editorTabs[0].id);
    } else {
      // Show empty state
      activeEditorTab = null;
      document.getElementById('tabContent_empty')?.classList.add('active');
      document.querySelector('.editor-toolbar').style.display = 'none';
    }
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
    if (data.baudrate)
      document.getElementById('baudrate').value = data.baudrate;

    if (data.elf_path) document.getElementById('elfPath').value = data.elf_path;
    if (data.compile_commands_path)
      document.getElementById('compileCommandsPath').value =
        data.compile_commands_path;
    if (data.toolchain_path)
      document.getElementById('toolchainPath').value = data.toolchain_path;
    if (data.patch_mode)
      document.getElementById('patchMode').value = data.patch_mode;
    if (data.chunk_size)
      document.getElementById('chunkSize').value = data.chunk_size;
    if (data.watch_dirs) updateWatchDirsList(data.watch_dirs);
    if (data.auto_compile !== undefined)
      document.getElementById('autoCompile').checked = data.auto_compile;
    if (data.enable_decompile !== undefined)
      document.getElementById('enableDecompile').checked =
        data.enable_decompile;

    // Show/hide Watch Directories section based on auto_compile state
    const watchDirsSection = document.getElementById('watchDirsSection');
    if (watchDirsSection) {
      watchDirsSection.style.display = data.auto_compile ? 'block' : 'none';
    }

    // Start auto-inject polling if auto_compile is enabled
    if (data.auto_compile) {
      startAutoInjectPolling();
    }

    // Check connection status (backend may have auto-connected on startup)
    await checkConnectionStatus();
  } catch (e) {
    // Silently ignore config load errors on startup
    console.warn('Config load skipped:', e.message);
  }
}

// Check if backend is already connected (e.g., via auto_connect on startup)
async function checkConnectionStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;

    const data = await res.json();
    if (data.connected) {
      // Backend is already connected, reuse the same connection handling
      handleConnected(
        data.port || 'Connected',
        `[AUTO-CONNECTED] ${data.port}`,
      );
    }
  } catch (e) {
    console.warn('Status check failed:', e.message);
  }
}

async function saveConfig(silent = false) {
  const config = {
    elf_path: document.getElementById('elfPath').value,
    compile_commands_path: document.getElementById('compileCommandsPath').value,
    toolchain_path: document.getElementById('toolchainPath').value,
    patch_mode: document.getElementById('patchMode').value,
    chunk_size: parseInt(document.getElementById('chunkSize').value) || 128,
    watch_dirs: getWatchDirs(),
    auto_compile: document.getElementById('autoCompile').checked,
    enable_decompile: document.getElementById('enableDecompile').checked,
  };

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
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

// Setup auto-save for all config inputs
function setupAutoSave() {
  // Text inputs - save on blur
  const textInputs = ['elfPath', 'compileCommandsPath', 'toolchainPath'];
  textInputs.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => saveConfig(true));
    }
  });

  // Select inputs - save on change
  const selectInputs = ['patchMode', 'chunkSize'];
  selectInputs.forEach((id) => {
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
  const items = document.querySelectorAll(
    '#watchDirsList .watch-dir-item input',
  );
  return Array.from(items)
    .map((input) => input.value.trim())
    .filter((v) => v);
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

function onAutoCompileChange() {
  const enabled = document.getElementById('autoCompile').checked;

  // Show/hide Watch Directories section based on auto-compile state
  const watchDirsSection = document.getElementById('watchDirsSection');
  if (watchDirsSection) {
    watchDirsSection.style.display = enabled ? 'block' : 'none';
  }

  writeToOutput(
    `[INFO] Auto-inject on save: ${enabled ? 'Enabled' : 'Disabled'}`,
    'info',
  );
  // Sync to backend - this will also start/stop the file watcher
  fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auto_compile: enabled }),
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
    const sourceFile = data.source_file || null;

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
          // Create preview tab when patch generation is complete (compiling starts)
          if (modifiedFuncs.length > 0) {
            createPatchPreviewTab(modifiedFuncs[0], sourceFile);
          }
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
          // Refresh preview tab content after successful injection
          if (modifiedFuncs.length > 0) {
            createPatchPreviewTab(modifiedFuncs[0], sourceFile);
          }
          // Refresh slot UI after successful injection
          updateSlotUI();
          fpbInfo(); // Refresh device info to show new slot state
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
  const totalTime = result.total_time || compileTime + uploadTime;
  const uploadSpeed = uploadTime > 0 ? Math.round(codeSize / uploadTime) : 0;
  const patchMode = result.patch_mode || 'unknown';

  writeToOutput(`--- Auto-Injection Statistics ---`, 'system');

  // Check if this is multi-function injection result
  const injections = result.injections || [];
  if (injections.length > 0) {
    // Multi-function injection
    const successCount = result.successful_count || 0;
    const totalCount = result.total_count || injections.length;
    writeToOutput(
      `Functions:     ${successCount}/${totalCount} injected successfully`,
      'info',
    );

    // Collect failed injections
    const failedInjections = [];

    for (const inj of injections) {
      const status = inj.success ? '✓' : '✗';
      const slotInfo = inj.slot >= 0 ? `[Slot ${inj.slot}]` : '';
      writeToOutput(
        `  ${status} ${inj.target_func || 'unknown'} @ ${inj.target_addr || '?'} -> ${inj.inject_func || '?'} @ ${inj.inject_addr || '?'} ${slotInfo}`,
        inj.success ? 'info' : 'error',
      );

      if (!inj.success) {
        failedInjections.push({
          func: inj.target_func || 'unknown',
          error: inj.error || 'Unknown error',
        });
      }
    }

    // Show alert dialog if there are failed injections
    if (failedInjections.length > 0) {
      const isSlotFull =
        failedInjections.some(
          (f) =>
            f.error.toLowerCase().includes('slot') ||
            f.error.toLowerCase().includes('no free') ||
            f.error.toLowerCase().includes('occupied'),
        ) || successCount < totalCount;

      const failedList = failedInjections
        .map((f) => `  • ${f.func}: ${f.error}`)
        .join('\n');

      let message =
        `⚠️ ${failedInjections.length} injection(s) failed!\n\n` +
        `Failed functions:\n${failedList}\n\n`;

      if (isSlotFull) {
        message +=
          `This may be due to FPB Slots being full.\n` +
          `Please clear some Slots in DEVICE INFO panel and try again.`;
      }

      // Use setTimeout to avoid blocking the UI update
      setTimeout(() => {
        alert(message);
        // Expand Device Info section to make it easier to clear slots
        const deviceDetails = document.getElementById('details-device');
        if (deviceDetails) {
          deviceDetails.open = true;
        }
      }, 100);
    }
  } else {
    // Single function injection (legacy format)
    writeToOutput(
      `Target:        ${targetFunc} @ ${result.target_addr || 'unknown'}`,
      'info',
    );
    writeToOutput(
      `Inject func:   ${result.inject_func || 'unknown'} @ ${result.inject_addr || 'unknown'}`,
      'info',
    );
    if (result.slot !== undefined) {
      writeToOutput(`Slot:          ${result.slot}`, 'info');
    }
  }

  writeToOutput(`Compile time:  ${compileTime.toFixed(2)}s`, 'info');
  writeToOutput(
    `Upload time:   ${uploadTime.toFixed(2)}s (${uploadSpeed} B/s)`,
    'info',
  );
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

async function createPatchPreviewTab(funcName, sourceFile = null) {
  // Use source file name if provided, otherwise fall back to function name
  let baseName = funcName;
  if (sourceFile) {
    // Extract filename without path and extension
    baseName = sourceFile
      .split('/')
      .pop()
      .replace(/\.[^.]+$/, '');
  }
  const tabId = `patch_${baseName}`;
  const tabTitle = `patch_${baseName}.c`;

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
  const existingTab = editorTabs.find((t) => t.id === tabId);
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
    type: 'preview', // Mark as auto-generated preview (read-only, no toolbar)
    closable: true,
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
      <div style="padding: 4px 8px; background: var(--vscode-editorWidget-background); border-bottom: 1px solid var(--vscode-panel-border); font-size: 11px; color: var(--vscode-descriptionForeground);">
        <i class="codicon codicon-lock" style="margin-right: 4px;"></i>
        Auto-generated patch (read-only preview)
      </div>
      <pre style="margin: 0; padding: 8px; height: calc(100% - 30px); overflow: auto;"><code class="language-c">${escapeHtml(patchContent)}</code></pre>
    </div>
  `;
  tabsContent.appendChild(contentDiv);

  // Apply syntax highlighting
  if (typeof hljs !== 'undefined') {
    contentDiv.querySelectorAll('pre code').forEach((block) => {
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
  // Get all progress elements (in patch_source and any preview tabs)
  const allProgressEls = document.querySelectorAll('.inject-progress');

  // For idle status, hide all progress bars
  if (status === 'idle') {
    // Don't immediately hide - let any existing timer finish
    return;
  }

  allProgressEls.forEach((progressEl) => {
    const progressText = progressEl.querySelector(
      '#injectProgressText, .progress-text',
    );
    const progressFill = progressEl.querySelector(
      '#injectProgressFill, .progress-fill',
    );

    if (!progressEl || !progressFill) return;

    progressEl.style.display = 'flex';
    progressFill.style.width = `${progress}%`;

    if (status === 'success') {
      if (progressText) progressText.textContent = 'Auto-inject complete!';
      progressFill.style.background = '#4caf50';
    } else if (status === 'failed') {
      if (progressText) progressText.textContent = 'Auto-inject failed!';
      progressFill.style.background = '#f44336';
    } else {
      const statusTexts = {
        detecting: 'Detecting changes...',
        generating: 'Generating patch...',
        compiling: 'Compiling...',
        injecting: 'Injecting...',
      };
      if (progressText)
        progressText.textContent = statusTexts[status] || status;
      progressFill.style.background = '';
    }
  });

  // Handle hide timer
  if (status === 'success' || status === 'failed') {
    if (statusChanged) {
      if (autoInjectProgressHideTimer)
        clearTimeout(autoInjectProgressHideTimer);
      autoInjectProgressHideTimer = setTimeout(() => {
        allProgressEls.forEach((el) => {
          el.style.display = 'none';
          const fill = el.querySelector('#injectProgressFill, .progress-fill');
          if (fill) {
            fill.style.width = '0%';
            fill.style.background = '';
          }
        });
        autoInjectProgressHideTimer = null;
      }, 3000);
    }
  } else {
    if (autoInjectProgressHideTimer) {
      clearTimeout(autoInjectProgressHideTimer);
      autoInjectProgressHideTimer = null;
    }
  }
}

/* ===========================
   FILE BROWSER
   =========================== */
const HOME_PATH = '~'; // Will be expanded by backend

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
      body: JSON.stringify({ elf_path: elfPath }),
    });
    // Clear and show loading
    const list = document.getElementById('symbolList');
    list.innerHTML =
      '<div style="padding: 8px; font-size: 11px; opacity: 0.7;">Symbols ready. Search above...</div>';
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

    data.items.forEach((item) => {
      const itemPath =
        actualPath === '/' ? `/${item.name}` : `${actualPath}/${item.name}`;
      const isDir = item.type === 'dir';

      // Filter files if needed (in file mode)
      if (
        !isDir &&
        fileBrowserMode === 'file' &&
        fileBrowserFilter &&
        !item.name.endsWith(fileBrowserFilter)
      ) {
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
  document
    .querySelectorAll('.file-item')
    .forEach((el) => el.classList.remove('selected'));
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
      body: JSON.stringify({ data: data }),
    });
  } catch (e) {
    // Silent fail for send errors
  }
}
