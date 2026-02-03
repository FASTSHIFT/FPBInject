/*========================================
  FPBInject Workbench - Connection Module
  ========================================*/

/* ===========================
   CONNECTION CONFIGURATION
   =========================== */
const CONNECTION_DEFAULT_MAX_RETRIES = 10;

/**
 * Get max retries from config or use default
 * @returns {number} Max retry count
 */
function getConnectionMaxRetries() {
  const state = window.FPBState;
  if (
    state &&
    state.config &&
    typeof state.config.transferMaxRetries === 'number'
  ) {
    return state.config.transferMaxRetries;
  }
  return CONNECTION_DEFAULT_MAX_RETRIES;
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

    const ports = data.ports || [];
    ports.forEach((p) => {
      const opt = document.createElement('option');
      const portName =
        typeof p === 'string' ? p : p.port || p.device || String(p);
      opt.value = portName;
      opt.textContent = portName;
      sel.appendChild(opt);
    });

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

function handleConnected(port, message = null) {
  const btn = document.getElementById('connectBtn');
  const statusEl = document.getElementById('connectionStatus');
  const state = window.FPBState;

  state.isConnected = true;
  btn.textContent = 'Disconnect';
  btn.classList.add('connected');
  statusEl.textContent = port;
  writeToOutput(message || `[CONNECTED] ${port}`, 'success');
  startLogPolling();
  fpbInfo();
  updateDisabledState();
}

function handleDisconnected() {
  const btn = document.getElementById('connectBtn');
  const statusEl = document.getElementById('connectionStatus');
  const state = window.FPBState;

  state.isConnected = false;
  btn.textContent = 'Connect';
  btn.classList.remove('connected');
  statusEl.textContent = 'Disconnected';
  writeToOutput('[DISCONNECTED]', 'warning');
  stopLogPolling();
  updateDisabledState();
}

async function toggleConnect() {
  const btn = document.getElementById('connectBtn');
  const state = window.FPBState;

  if (!state.isConnected) {
    const port = document.getElementById('portSelect').value;
    const baud = document.getElementById('baudrate').value;
    const maxRetries = getConnectionMaxRetries();

    btn.disabled = true;
    btn.textContent = 'Connecting...';

    let lastError = null;
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        if (attempt > 0) {
          writeToOutput(
            `[CONNECTION] Retry ${attempt}/${maxRetries}...`,
            'warning',
          );
          // Wait before retry
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }

        const res = await fetch('/api/connect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ port, baudrate: parseInt(baud) }),
        });
        const data = await res.json();

        if (data.success) {
          handleConnected(port, `[CONNECTED] ${port} @ ${baud} baud`);
          btn.disabled = false;
          return;
        } else {
          lastError = new Error(data.message || 'Connection failed');
        }
      } catch (e) {
        lastError = e;
      }
    }

    // All retries failed
    writeToOutput(
      `[ERROR] Connection failed after ${maxRetries} retries: ${lastError}`,
      'error',
    );
    btn.textContent = 'Connect';
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

async function checkConnectionStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;

    const data = await res.json();
    if (data.connected) {
      handleConnected(
        data.port || 'Connected',
        `[AUTO-CONNECTED] ${data.port}`,
      );
    }
  } catch (e) {
    console.warn('Status check failed:', e.message);
  }
}

// Export for global access
window.refreshPorts = refreshPorts;
window.handleConnected = handleConnected;
window.handleDisconnected = handleDisconnected;
window.toggleConnect = toggleConnect;
window.checkConnectionStatus = checkConnectionStatus;
window.getConnectionMaxRetries = getConnectionMaxRetries;
