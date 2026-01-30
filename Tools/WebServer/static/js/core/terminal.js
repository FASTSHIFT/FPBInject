/*========================================
  FPBInject Workbench - Terminal Module
  ========================================*/

/* ===========================
   TERMINAL MANAGEMENT
   =========================== */
function initTerminals() {
  const termTheme = getTerminalTheme();
  const state = window.FPBState;

  // Get both panels for proper initialization
  const toolPanel = document.getElementById('terminalPanelTool');
  const rawPanel = document.getElementById('terminalPanelRaw');

  // Temporarily show both panels for proper terminal sizing
  const toolDisplay = toolPanel ? toolPanel.style.display : '';
  const rawDisplay = rawPanel ? rawPanel.style.display : '';
  if (toolPanel) toolPanel.style.display = 'block';
  if (rawPanel) rawPanel.style.display = 'block';

  // Tool Terminal (OUTPUT - Python logs)
  const toolContainer = document.getElementById('terminal-container');
  if (toolContainer && typeof Terminal !== 'undefined') {
    state.toolTerminal = new Terminal({
      theme: termTheme,
      fontFamily: 'Consolas, "Courier New", monospace',
      fontSize: 12,
      cursorBlink: false,
      disableStdin: true,
      allowProposedApi: true,
    });
    state.toolFitAddon = new FitAddon.FitAddon();
    state.toolTerminal.loadAddon(state.toolFitAddon);
    state.toolTerminal.open(toolContainer);
    state.toolFitAddon.fit();

    // Enable text selection with mouse
    state.toolTerminal.attachCustomKeyEventHandler((e) => {
      if (e.ctrlKey && e.key === 'c') {
        const selection = state.toolTerminal.getSelection();
        if (selection) {
          navigator.clipboard.writeText(selection);
          return false;
        }
      }
      return true;
    });

    state.toolTerminal.writeln(
      '\x1b[36m[OUTPUT] FPBInject Workbench Ready\x1b[0m',
    );
  }

  // Raw Terminal (SERIAL PORT - interactive)
  const rawContainer = document.getElementById('raw-terminal-container');
  if (rawContainer && typeof Terminal !== 'undefined') {
    state.rawTerminal = new Terminal({
      theme: termTheme,
      fontFamily: 'Consolas, "Courier New", monospace',
      fontSize: 12,
      cursorBlink: true,
      disableStdin: false,
      allowProposedApi: true,
    });
    state.rawFitAddon = new FitAddon.FitAddon();
    state.rawTerminal.loadAddon(state.rawFitAddon);
    state.rawTerminal.open(rawContainer);
    state.rawFitAddon.fit();

    // Enable text selection with mouse + Ctrl+C copy
    state.rawTerminal.attachCustomKeyEventHandler((e) => {
      if (e.ctrlKey && e.key === 'c') {
        const selection = state.rawTerminal.getSelection();
        if (selection) {
          navigator.clipboard.writeText(selection);
          return false;
        }
      }
      return true;
    });

    // Setup input handler for interactive terminal
    state.rawTerminal.onData((data) => {
      if (state.isConnected) {
        sendTerminalCommand(data);
      }
    });
  }

  // Restore original display states
  if (toolPanel) toolPanel.style.display = toolDisplay || 'block';
  if (rawPanel) rawPanel.style.display = rawDisplay || 'none';

  window.addEventListener('resize', fitTerminals);
}

function fitTerminals() {
  const state = window.FPBState;
  setTimeout(() => {
    if (state.toolFitAddon) state.toolFitAddon.fit();
    if (state.rawFitAddon) state.rawFitAddon.fit();
  }, 100);
}

function switchTerminalTab(tab) {
  const state = window.FPBState;
  state.currentTerminalTab = tab;

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
  if (state.toolFitAddon) state.toolFitAddon.fit();
  if (state.rawFitAddon) state.rawFitAddon.fit();

  // Then show only the active tab
  toolPanel.style.display = tab === 'tool' ? 'block' : 'none';
  rawPanel.style.display = tab === 'raw' ? 'block' : 'none';
  toolPanel.style.visibility = 'visible';
  rawPanel.style.visibility = 'visible';
}

function clearCurrentTerminal() {
  const state = window.FPBState;
  if (state.currentTerminalTab === 'tool' && state.toolTerminal) {
    state.toolTerminal.clear();
    state.toolTerminal.writeln('\x1b[36m[OUTPUT] Terminal cleared\x1b[0m');
  } else if (state.currentTerminalTab === 'raw' && state.rawTerminal) {
    state.rawTerminal.clear();
  }
}

function writeToOutput(message, type = 'info') {
  const { toolTerminal } = window.FPBState;
  if (!toolTerminal) return;

  const colors = {
    info: '\x1b[0m',
    success: '\x1b[32m',
    warning: '\x1b[33m',
    error: '\x1b[31m',
    system: '\x1b[36m',
  };
  const color = colors[type] || colors.info;

  const lines = message.split('\n');
  lines.forEach((line) => {
    toolTerminal.writeln(`${color}${line}\x1b[0m`);
  });
}

function writeToSerial(data) {
  const { rawTerminal } = window.FPBState;
  if (rawTerminal) {
    const normalizedData = data.replace(/(?<!\r)\n/g, '\r\n');
    rawTerminal.write(normalizedData);
  }
}

// Export for global access
window.initTerminals = initTerminals;
window.fitTerminals = fitTerminals;
window.switchTerminalTab = switchTerminalTab;
window.clearCurrentTerminal = clearCurrentTerminal;
window.writeToOutput = writeToOutput;
window.writeToSerial = writeToSerial;
