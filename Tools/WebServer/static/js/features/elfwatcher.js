/*========================================
  FPBInject Workbench - ELF File Watcher Module
  
  Monitors ELF file changes and prompts user to reload
  when the ELF file is modified (e.g., after recompilation).
  ========================================*/

/* ===========================
   ELF WATCHER STATE
   =========================== */
let elfWatcherPollInterval = null;
let elfChangeDialogShown = false;

const ELF_WATCHER_POLL_INTERVAL = 2000; // 2 seconds

/* ===========================
   ELF WATCHER FUNCTIONS
   =========================== */

/**
 * Start polling for ELF file changes
 */
function startElfWatcherPolling() {
  if (elfWatcherPollInterval) return;

  elfWatcherPollInterval = setInterval(
    pollElfStatus,
    ELF_WATCHER_POLL_INTERVAL,
  );
  writeToOutput('[INFO] ELF file watcher started', 'system');
}

/**
 * Stop polling for ELF file changes
 */
function stopElfWatcherPolling() {
  if (elfWatcherPollInterval) {
    clearInterval(elfWatcherPollInterval);
    elfWatcherPollInterval = null;
    writeToOutput('[INFO] ELF file watcher stopped', 'system');
  }
}

/**
 * Poll ELF file status from backend
 */
async function pollElfStatus() {
  // Don't poll if dialog is already shown
  if (elfChangeDialogShown) return;

  try {
    const res = await fetch('/api/watch/elf_status');
    const data = await res.json();

    if (!data.success) return;

    if (data.changed) {
      showElfChangeDialog(data.elf_path);
    }
  } catch (e) {
    // Silent error - backend may be unavailable
  }
}

/**
 * Show dialog when ELF file has changed
 * @param {string} elfPath - Path to the changed ELF file
 */
function showElfChangeDialog(elfPath) {
  if (elfChangeDialogShown) return;

  elfChangeDialogShown = true;

  const fileName = elfPath ? elfPath.split('/').pop() : 'ELF file';

  writeToOutput(`[WARNING] ELF file changed: ${fileName}`, 'warning');

  const userChoice = confirm(
    `ELF file "${fileName}" has changed.\n\nReload symbols now?`,
  );

  if (userChoice) {
    reloadElfSymbols(elfPath);
  } else {
    acknowledgeElfChange();
  }

  elfChangeDialogShown = false;
}

/**
 * Reload ELF symbols after file change
 * @param {string} elfPath - Path to the ELF file
 */
async function reloadElfSymbols(elfPath) {
  writeToOutput(`[INFO] Reloading symbols from ${elfPath}...`, 'system');

  try {
    // Acknowledge the change first
    await fetch('/api/watch/elf_acknowledge', { method: 'POST' });

    // Reload symbols by updating config
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ elf_path: elfPath }),
    });

    // Refresh symbol list
    const list = document.getElementById('symbolList');
    if (list) {
      list.innerHTML =
        '<div style="padding: 8px; font-size: 11px; opacity: 0.7;">Symbols reloaded. Search above...</div>';
    }

    // Refresh FPB info to check for build time mismatch
    if (typeof fpbInfo === 'function') {
      await fpbInfo();
    }

    writeToOutput(`[SUCCESS] Symbols reloaded from ${elfPath}`, 'success');
  } catch (e) {
    writeToOutput(`[ERROR] Failed to reload symbols: ${e}`, 'error');
  }
}

/**
 * Acknowledge ELF change without reloading
 */
async function acknowledgeElfChange() {
  try {
    await fetch('/api/watch/elf_acknowledge', { method: 'POST' });
    writeToOutput('[INFO] ELF change acknowledged (ignored)', 'system');
  } catch (e) {
    writeToOutput(`[ERROR] Failed to acknowledge ELF change: ${e}`, 'error');
  }
}

/**
 * Reset ELF watcher dialog state (for testing)
 */
function resetElfWatcherState() {
  elfChangeDialogShown = false;
}

/**
 * Check if ELF watcher is running
 * @returns {boolean} True if polling is active
 */
function isElfWatcherRunning() {
  return elfWatcherPollInterval !== null;
}

// Export for global access
window.startElfWatcherPolling = startElfWatcherPolling;
window.stopElfWatcherPolling = stopElfWatcherPolling;
window.pollElfStatus = pollElfStatus;
window.showElfChangeDialog = showElfChangeDialog;
window.reloadElfSymbols = reloadElfSymbols;
window.acknowledgeElfChange = acknowledgeElfChange;
window.resetElfWatcherState = resetElfWatcherState;
window.isElfWatcherRunning = isElfWatcherRunning;
