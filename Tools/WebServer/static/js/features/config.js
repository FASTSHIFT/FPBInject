/*========================================
  FPBInject Workbench - Configuration Module
  
  This module integrates with config-schema.js for schema-driven
  configuration management.
  ========================================*/

/* ===========================
   CONFIGURATION
   =========================== */
async function loadConfig() {
  try {
    // Render config panel from schema
    await renderConfigPanel('configContainer');

    const res = await fetch('/api/config');

    if (!res.ok) return;

    const contentType = res.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) return;

    const data = await res.json();

    // Load port/baudrate (connection section, not in schema UI)
    if (data.port) {
      const portSelect = document.getElementById('portSelect');
      if (portSelect) {
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
    }
    if (data.baudrate) {
      const baudrateEl = document.getElementById('baudrate');
      if (baudrateEl) baudrateEl.value = data.baudrate;
    }

    // Load all config values using schema
    await loadConfigValuesFromData(data);

    // Sync language from server config if different from localStorage
    if (data.ui_language && typeof changeLanguage === 'function') {
      const currentLang = localStorage.getItem('fpbinject_ui_language') || 'en';
      if (data.ui_language !== currentLang) {
        changeLanguage(data.ui_language);
      }
    }

    // Sync theme from server config if different from localStorage
    if (data.ui_theme && typeof setTheme === 'function') {
      const currentTheme = localStorage.getItem('fpbinject-theme') || 'dark';
      if (data.ui_theme !== currentTheme) {
        setTheme(data.ui_theme);
      }
    }

    // Update path input state based on recording status
    updateLogFilePathState(data.log_file_enabled || false);

    updateWatcherStatus(data.auto_compile);

    if (data.auto_compile) {
      startAutoInjectPolling();
    }

    await checkConnectionStatus();
  } catch (e) {
    console.warn('Config load skipped:', e.message);
  }
}

/**
 * Load config values from data object into form elements.
 * Uses schema for proper type handling.
 */
async function loadConfigValuesFromData(data) {
  const schema = await loadConfigSchema();
  if (!schema) return;

  for (const item of schema.schema) {
    const elementId = keyToElementId(item.key);

    // Handle path_list separately (no direct element with elementId)
    if (item.config_type === 'path_list') {
      let value = data[item.key];
      if (value === undefined || value === null) {
        value = item.default;
      }
      updatePathList(item.key, value || []);
      continue;
    }

    const el = document.getElementById(elementId);
    if (!el) continue;

    let value = data[item.key];
    if (value === undefined || value === null) {
      value = item.default;
    }

    if (item.config_type === 'boolean') {
      el.checked = value;
    } else if (item.config_type === 'number' && item.ui_multiplier !== 1) {
      // Apply UI multiplier (e.g., seconds to ms)
      el.value = Math.round(value * item.ui_multiplier);
    } else {
      el.value = value || '';
    }
  }

  // Setup dependency visibility
  setupDependenciesFromSchema(schema);
}

/**
 * Setup visibility dependencies between config items.
 */
function setupDependenciesFromSchema(schema) {
  for (const item of schema.schema) {
    if (item.depends_on) {
      const dependsOnId = keyToElementId(item.depends_on);
      const dependsOnEl = document.getElementById(dependsOnId);
      const sectionId = keyToElementId(item.key) + 'Section';
      const sectionEl = document.getElementById(sectionId);

      if (dependsOnEl && sectionEl) {
        // Set initial visibility
        sectionEl.style.display = dependsOnEl.checked ? 'block' : 'none';
      }
    }
  }
}

async function saveConfig(silent = false) {
  const schema = getConfigSchema();
  if (!schema) {
    // Fallback to legacy save if schema not loaded
    return saveConfigLegacy(silent);
  }

  const config = {};

  for (const item of schema.schema) {
    const elementId = keyToElementId(item.key);

    // path_list type doesn't have a direct element with elementId
    if (item.config_type === 'path_list') {
      config[item.key] = getPathListValues(item.key);
      continue;
    }

    const el = document.getElementById(elementId);
    if (!el) continue;

    if (item.config_type === 'boolean') {
      config[item.key] = el.checked;
    } else if (item.config_type === 'number') {
      let value = parseFloat(el.value);
      // Use default only if value is NaN (not for 0)
      if (isNaN(value)) {
        value = item.default;
      }
      // Reverse UI multiplier
      if (item.ui_multiplier !== 1) {
        value = value / item.ui_multiplier;
      }
      config[item.key] = value;
    } else {
      config[item.key] = el.value;
    }
  }

  // Handle language change
  if (config.ui_language && typeof changeLanguage === 'function') {
    const currentLang = localStorage.getItem('fpbinject_ui_language') || 'en';
    if (config.ui_language !== currentLang) {
      changeLanguage(config.ui_language);
    }
  }

  // Handle theme change
  if (config.ui_theme && typeof setTheme === 'function') {
    const currentTheme = localStorage.getItem('fpbinject-theme') || 'dark';
    if (config.ui_theme !== currentTheme) {
      setTheme(config.ui_theme);
    }
  }

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    const data = await res.json();

    if (data.success) {
      if (!silent) log.success('Configuration saved');
    } else {
      throw new Error(data.message || 'Save failed');
    }
  } catch (e) {
    log.error(`Save failed: ${e}`);
  }
}

/**
 * Legacy save function for backward compatibility.
 */
async function saveConfigLegacy(silent = false) {
  const config = {
    elf_path: document.getElementById('elfPath')?.value || '',
    compile_commands_path:
      document.getElementById('compileCommandsPath')?.value || '',
    toolchain_path: document.getElementById('toolchainPath')?.value || '',
    patch_mode: document.getElementById('patchMode')?.value || 'trampoline',
    chunk_size: parseInt(document.getElementById('chunkSize')?.value) || 128,
    tx_chunk_size: parseInt(document.getElementById('txChunkSize')?.value) || 0,
    tx_chunk_delay:
      (parseInt(document.getElementById('txChunkDelay')?.value) || 5) / 1000,
    transfer_max_retries:
      parseInt(document.getElementById('transferMaxRetries')?.value) || 3,
    watch_dirs: getWatchDirs(),
    auto_compile: document.getElementById('autoCompile')?.checked || false,
    enable_decompile:
      document.getElementById('enableDecompile')?.checked || false,
    ghidra_path: document.getElementById('ghidraPath')?.value || '',
    verify_crc: document.getElementById('verifyCrc')?.checked ?? true,
  };

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    const data = await res.json();

    if (data.success) {
      if (!silent) log.success('Configuration saved');
    } else {
      throw new Error(data.message || 'Save failed');
    }
  } catch (e) {
    log.error(`Save failed: ${e}`);
  }
}

function setupAutoSave() {
  // Auto-save is now handled by onConfigItemChange in config-schema.js
  // This function is kept for backward compatibility
}

function onEnableDecompileChange() {
  saveConfig(true);
}

function onGhidraPathChange() {
  saveConfig(true);
}

/* ===========================
   WATCH DIRS MANAGEMENT
   =========================== */
function updateWatchDirsList(dirs) {
  // Use schema-based path list if available
  if (typeof updatePathList === 'function') {
    updatePathList('watch_dirs', dirs || []);
    return;
  }

  // Legacy fallback
  const list = document.getElementById('watchDirsList');
  if (!list) return;
  list.innerHTML = '';

  if (!dirs || dirs.length === 0) return;

  dirs.forEach((dir, index) => {
    addWatchDirItem(dir, index);
  });
}

function getWatchDirs() {
  // Use schema-based path list if available
  if (typeof getPathListValues === 'function') {
    return getPathListValues('watch_dirs');
  }

  // Legacy fallback
  const items = document.querySelectorAll(
    '#watchDirsList .watch-dir-item input',
  );
  return Array.from(items)
    .map((input) => input.value.trim())
    .filter((v) => v);
}

function addWatchDir() {
  // Use schema-based function if available
  if (typeof addPathListItem === 'function') {
    addPathListItem('watch_dirs');
    return;
  }

  // Legacy fallback
  const state = window.FPBState;
  state.fileBrowserCallback = (path) => {
    addWatchDirItem(path);
    saveConfig(true);
  };
  state.fileBrowserFilter = '';
  state.fileBrowserMode = 'dir';
  openFileBrowser(HOME_PATH);
}

function addWatchDirItem(path, index = null) {
  // Use schema-based function if available
  if (typeof addPathListItemElement === 'function') {
    addPathListItemElement('watch_dirs', path);
    return;
  }

  // Legacy fallback
  const list = document.getElementById('watchDirsList');
  if (!list) return;

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
  const state = window.FPBState;
  const input = btn.closest('.watch-dir-item').querySelector('input');
  state.fileBrowserCallback = (path) => {
    input.value = path;
    saveConfig(true);
  };
  state.fileBrowserFilter = '';
  state.fileBrowserMode = 'dir';
  openFileBrowser(input.value || HOME_PATH);
}

function removeWatchDir(btn) {
  btn.closest('.watch-dir-item').remove();
  saveConfig(true);
}

function onAutoCompileChange() {
  const enabled = document.getElementById('autoCompile')?.checked || false;

  updateWatcherStatus(enabled);

  log.info(`Auto-inject on save: ${enabled ? 'Enabled' : 'Disabled'}`);

  saveConfig(true);

  if (enabled) {
    startAutoInjectPolling();
  } else {
    stopAutoInjectPolling();
  }
}

function onVerifyCrcChange() {
  const enabled = document.getElementById('verifyCrc')?.checked ?? true;
  log.info(`Verify CRC after transfer: ${enabled ? 'Enabled' : 'Disabled'}`);
  saveConfig(true);
}

async function onLogFileEnabledChange() {
  const enabled = document.getElementById('logFileEnabled')?.checked || false;
  const pathInput = document.getElementById('logFilePath');

  if (enabled) {
    let path = pathInput?.value?.trim() || '';
    if (!path) {
      path = '~/fpb_console.log';
      if (pathInput) pathInput.value = path;
    }

    try {
      // Check current status first
      const statusRes = await fetch('/api/log_file/status');
      const statusData = await statusRes.json();

      if (statusData.enabled && statusData.path === path) {
        updateLogFilePathState(true);
        return;
      }

      if (statusData.enabled) {
        await fetch('/api/log_file/stop', { method: 'POST' });
      }

      const res = await fetch('/api/log_file/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      });
      const data = await res.json();

      if (data.success) {
        log.success(`Log recording started: ${path}`);
        updateLogFilePathState(true);
      } else {
        log.error(data.error);
        const checkbox = document.getElementById('logFileEnabled');
        if (checkbox) checkbox.checked = false;
      }
    } catch (e) {
      log.error(`Failed to start log recording: ${e}`);
      const checkbox = document.getElementById('logFileEnabled');
      if (checkbox) checkbox.checked = false;
    }
  } else {
    try {
      const res = await fetch('/api/log_file/stop', { method: 'POST' });
      const data = await res.json();

      if (data.success) {
        log.success('Log recording stopped');
        updateLogFilePathState(false);
      } else {
        log.error(data.error);
      }
    } catch (e) {
      log.error(`Failed to stop log recording: ${e}`);
    }
  }
}

function updateLogFilePathState(recording) {
  const pathInput = document.getElementById('logFilePath');
  const browseBtn = document.getElementById('browseLogFileBtn');

  if (recording) {
    if (pathInput) {
      pathInput.disabled = true;
      pathInput.style.opacity = '0.5';
    }
    if (browseBtn) {
      browseBtn.disabled = true;
      browseBtn.style.opacity = '0.5';
      browseBtn.style.cursor = 'not-allowed';
    }
  } else {
    if (pathInput) {
      pathInput.disabled = false;
      pathInput.style.opacity = '1';
    }
    if (browseBtn) {
      browseBtn.disabled = false;
      browseBtn.style.opacity = '1';
      browseBtn.style.cursor = 'pointer';
    }
  }
}

async function onLogFilePathChange() {
  // Only save path when not recording
  const enabled = document.getElementById('logFileEnabled')?.checked || false;
  if (!enabled) {
    saveConfig(true);
  }
}

function browseLogFile() {
  const state = window.FPBState;
  const input = document.getElementById('logFilePath');

  // Don't allow browsing while recording
  if (document.getElementById('logFileEnabled')?.checked) {
    return;
  }

  state.fileBrowserCallback = (path) => {
    if (!path.endsWith('.log')) {
      path = path + (path.endsWith('/') ? '' : '/') + 'console.log';
    }
    if (input) input.value = path;
    onLogFilePathChange();
  };
  state.fileBrowserFilter = '';
  state.fileBrowserMode = 'dir';

  const currentPath = input?.value || HOME_PATH;
  const startPath = currentPath.includes('/')
    ? currentPath.substring(0, currentPath.lastIndexOf('/'))
    : HOME_PATH;

  openFileBrowser(startPath);
}

function updateWatcherStatus(enabled) {
  const watcherStatusEl = document.getElementById('watcherStatus');
  if (watcherStatusEl) {
    watcherStatusEl.textContent = enabled ? 'Watcher: On' : 'Watcher: Off';
  }

  const watcherIconEl = document.getElementById('watcherIcon');
  if (watcherIconEl) {
    watcherIconEl.className = enabled
      ? 'codicon codicon-eye'
      : 'codicon codicon-eye-closed';
  }
}

// Export for global access
window.loadConfig = loadConfig;
window.saveConfig = saveConfig;
window.setupAutoSave = setupAutoSave;
window.onEnableDecompileChange = onEnableDecompileChange;
window.onGhidraPathChange = onGhidraPathChange;
window.updateWatchDirsList = updateWatchDirsList;
window.getWatchDirs = getWatchDirs;
window.addWatchDir = addWatchDir;
window.addWatchDirItem = addWatchDirItem;
window.browseWatchDir = browseWatchDir;
window.removeWatchDir = removeWatchDir;
window.onAutoCompileChange = onAutoCompileChange;
window.onVerifyCrcChange = onVerifyCrcChange;
window.onLogFileEnabledChange = onLogFileEnabledChange;
window.onLogFilePathChange = onLogFilePathChange;
window.updateLogFilePathState = updateLogFilePathState;
window.browseLogFile = browseLogFile;
window.updateWatcherStatus = updateWatcherStatus;
