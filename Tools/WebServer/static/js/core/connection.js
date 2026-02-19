/*========================================
  FPBInject Workbench - Connection Module
  ========================================*/

/* ===========================
   CONNECTION CONFIGURATION
   =========================== */
const CONNECTION_DEFAULT_MAX_RETRIES = 10;
const BACKEND_HEALTH_CHECK_INTERVAL = 5000; // 5 seconds

let backendHealthCheckTimer = null;
let backendDisconnectAlertShown = false;

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
    log.error(`Failed to refresh ports: ${e}`);
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
  log.success(message || `Connected to ${port}`);
  startLogPolling();
  fpbInfo();
  updateDisabledState();

  // Start ELF file watcher
  if (typeof startElfWatcherPolling === 'function') {
    startElfWatcherPolling();
  }
}

function handleDisconnected() {
  const btn = document.getElementById('connectBtn');
  const statusEl = document.getElementById('connectionStatus');
  const state = window.FPBState;

  state.isConnected = false;
  btn.textContent = 'Connect';
  btn.classList.remove('connected');
  statusEl.textContent = 'Disconnected';
  log.warn('Disconnected');
  stopLogPolling();
  updateDisabledState();

  // Stop ELF file watcher
  if (typeof stopElfWatcherPolling === 'function') {
    stopElfWatcherPolling();
  }
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
          log.warn(`Retry ${attempt}/${maxRetries}...`);
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
          handleConnected(port, `Connected to ${port} @ ${baud} baud`);
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
    log.error(`Connection failed after ${maxRetries} retries: ${lastError}`);
    btn.textContent = 'Connect';
    btn.disabled = false;
  } else {
    try {
      await fetch('/api/disconnect', { method: 'POST' });
      handleDisconnected();
    } catch (e) {
      log.error(`Disconnect failed: ${e}`);
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
        `Auto-connected to ${data.port}`,
      );
    }
  } catch (e) {
    console.warn('Status check failed:', e.message);
  }
}

/**
 * Check if backend server is alive
 * Shows alert if backend becomes unavailable
 */
async function checkBackendHealth() {
  try {
    const res = await fetch('/api/status', {
      method: 'GET',
      signal: AbortSignal.timeout(3000), // 3 second timeout
    });
    if (res.ok) {
      // Backend is alive, reset alert flag
      backendDisconnectAlertShown = false;
    }
  } catch (e) {
    // Backend is not responding
    if (!backendDisconnectAlertShown) {
      backendDisconnectAlertShown = true;
      stopBackendHealthCheck();
      stopLogPolling();

      // Update UI to show disconnected state
      const state = window.FPBState;
      if (state.isConnected) {
        state.isConnected = false;
        const btn = document.getElementById('connectBtn');
        const statusEl = document.getElementById('connectionStatus');
        if (btn) {
          btn.textContent = 'Connect';
          btn.classList.remove('connected');
        }
        if (statusEl) {
          statusEl.textContent = 'Disconnected';
        }
        updateDisabledState();
      }

      // Show alert to user
      alert(
        'Backend server has disconnected.\n\nPlease restart the server and refresh the page.',
      );
    }
  }
}

/**
 * Start periodic backend health check
 */
function startBackendHealthCheck() {
  if (backendHealthCheckTimer) return;
  backendHealthCheckTimer = setInterval(
    checkBackendHealth,
    BACKEND_HEALTH_CHECK_INTERVAL,
  );
}

/**
 * Stop backend health check
 */
function stopBackendHealthCheck() {
  if (backendHealthCheckTimer) {
    clearInterval(backendHealthCheckTimer);
    backendHealthCheckTimer = null;
  }
}

/**
 * Reset backend alert state (for testing)
 */
function resetBackendAlertState() {
  backendDisconnectAlertShown = false;
}

// Export for global access
window.refreshPorts = refreshPorts;
window.handleConnected = handleConnected;
window.handleDisconnected = handleDisconnected;
window.toggleConnect = toggleConnect;
window.checkConnectionStatus = checkConnectionStatus;
window.getConnectionMaxRetries = getConnectionMaxRetries;
window.checkBackendHealth = checkBackendHealth;
window.startBackendHealthCheck = startBackendHealthCheck;
window.stopBackendHealthCheck = stopBackendHealthCheck;
window.resetBackendAlertState = resetBackendAlertState;
