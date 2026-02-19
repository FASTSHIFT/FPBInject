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
      '\x1b[36m[INFO] initTerminals: FPBInject Workbench Ready\x1b[0m',
    );
    /* Note: Using direct writeln here because writeToOutput is not yet available during init */
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
    log.info('Terminal cleared');
  } else if (state.currentTerminalTab === 'raw' && state.rawTerminal) {
    state.rawTerminal.clear();
  }
}

function writeToOutput(message, type = 'info') {
  const state = window.FPBState;
  const { toolTerminal } = state;
  if (!toolTerminal) return;

  // If paused, buffer the message
  if (state.terminalPaused) {
    state.pausedToolLogs.push({ message, type });
    return;
  }

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

/**
 * Get caller function name from stack trace
 * @returns {string} Caller function name or 'anonymous'
 */
function _getCallerName() {
  try {
    const stack = new Error().stack;
    const lines = stack.split('\n');
    /* Skip internal functions: Error, _getCallerName, _write, log.xxx */
    const skipPatterns = [
      '_getCallerName',
      '_write',
      'Object.info',
      'Object.success',
      'Object.warn',
      'Object.error',
      'Object.debug',
    ];
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i];
      /* Skip internal log functions */
      if (skipPatterns.some((p) => line.includes(p))) continue;

      /* Match async function: "at async functionName (" */
      let match = line.match(/at\s+async\s+(\w+)\s*\(/);
      if (match && match[1]) return match[1];

      /* Match regular function: "at functionName (" */
      match = line.match(/at\s+(\w+)\s*\(/);
      if (
        match &&
        match[1] &&
        match[1] !== 'Object' &&
        !match[1].startsWith('_')
      ) {
        return match[1];
      }

      /* Match method: "at Object.methodName (" or "at ClassName.methodName (" */
      match = line.match(/at\s+\w+\.(\w+)\s*\(/);
      if (
        match &&
        match[1] &&
        !match[1].startsWith('_') &&
        !['info', 'success', 'warn', 'error', 'debug'].includes(match[1])
      ) {
        return match[1];
      }
    }
  } catch (e) {
    /* Ignore */
  }
  return 'anonymous';
}

/**
 * Structured logging with automatic function name detection
 * Usage: log.info('message'), log.error('message'), etc.
 */
const log = {
  _write(level, message) {
    const funcName = _getCallerName();
    const typeMap = {
      INFO: 'info',
      SUCCESS: 'success',
      WARN: 'warning',
      ERROR: 'error',
      DEBUG: 'system',
    };
    writeToOutput(
      `[${level}] ${funcName}: ${message}`,
      typeMap[level] || 'info',
    );
  },
  info(msg) {
    this._write('INFO', msg);
  },
  success(msg) {
    this._write('SUCCESS', msg);
  },
  warn(msg) {
    this._write('WARN', msg);
  },
  error(msg) {
    this._write('ERROR', msg);
  },
  debug(msg) {
    this._write('DEBUG', msg);
  },
};

function writeToSerial(data) {
  const state = window.FPBState;
  const { rawTerminal } = state;

  // If paused, buffer the data
  if (state.terminalPaused) {
    state.pausedRawData.push(data);
    return;
  }

  if (rawTerminal) {
    const normalizedData = data.replace(/(?<!\r)\n/g, '\r\n');
    rawTerminal.write(normalizedData);
  }
}

function toggleTerminalPause() {
  const state = window.FPBState;
  state.terminalPaused = !state.terminalPaused;

  const btn = document.getElementById('btnTerminalPause');
  if (btn) {
    const icon = btn.querySelector('i');
    if (state.terminalPaused) {
      btn.title = 'Resume';
      btn.classList.add('active');
      if (icon) {
        icon.classList.remove('codicon-debug-pause');
        icon.classList.add('codicon-debug-start');
      }
    } else {
      btn.title = 'Pause';
      btn.classList.remove('active');
      if (icon) {
        icon.classList.remove('codicon-debug-start');
        icon.classList.add('codicon-debug-pause');
      }
      // Flush buffered logs
      flushPausedLogs();
    }
  }
}

function flushPausedLogs() {
  const state = window.FPBState;

  // Flush tool logs
  if (state.pausedToolLogs.length > 0) {
    const logs = state.pausedToolLogs;
    state.pausedToolLogs = [];
    logs.forEach((log) => {
      writeToOutput(log.message, log.type);
    });
  }

  // Flush raw data
  if (state.pausedRawData.length > 0) {
    const data = state.pausedRawData;
    state.pausedRawData = [];
    data.forEach((d) => {
      writeToSerial(d);
    });
  }
}

// Export for global access
window.initTerminals = initTerminals;
window.fitTerminals = fitTerminals;
window.switchTerminalTab = switchTerminalTab;
window.clearCurrentTerminal = clearCurrentTerminal;
window.writeToOutput = writeToOutput;
window.writeToSerial = writeToSerial;
window.toggleTerminalPause = toggleTerminalPause;
window.flushPausedLogs = flushPausedLogs;
window.log = log;
