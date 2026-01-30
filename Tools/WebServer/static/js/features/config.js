/*========================================
  FPBInject Workbench - Configuration Module
  ========================================*/

/* ===========================
   CONFIGURATION
   =========================== */
async function loadConfig() {
  try {
    const res = await fetch('/api/config');

    if (!res.ok) return;

    const contentType = res.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) return;

    const data = await res.json();

    if (data.port) {
      const portSelect = document.getElementById('portSelect');
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
    if (data.tx_chunk_size !== undefined)
      document.getElementById('txChunkSize').value = data.tx_chunk_size;
    if (data.tx_chunk_delay !== undefined)
      document.getElementById('txChunkDelay').value = Math.round(
        data.tx_chunk_delay * 1000,
      );
    if (data.watch_dirs) updateWatchDirsList(data.watch_dirs);
    if (data.auto_compile !== undefined)
      document.getElementById('autoCompile').checked = data.auto_compile;
    if (data.enable_decompile !== undefined)
      document.getElementById('enableDecompile').checked =
        data.enable_decompile;

    const watchDirsSection = document.getElementById('watchDirsSection');
    if (watchDirsSection) {
      watchDirsSection.style.display = data.auto_compile ? 'block' : 'none';
    }

    if (data.auto_compile) {
      startAutoInjectPolling();
    }

    await checkConnectionStatus();
  } catch (e) {
    console.warn('Config load skipped:', e.message);
  }
}

async function saveConfig(silent = false) {
  const config = {
    elf_path: document.getElementById('elfPath').value,
    compile_commands_path: document.getElementById('compileCommandsPath').value,
    toolchain_path: document.getElementById('toolchainPath').value,
    patch_mode: document.getElementById('patchMode').value,
    chunk_size: parseInt(document.getElementById('chunkSize').value) || 128,
    tx_chunk_size: parseInt(document.getElementById('txChunkSize').value) || 0,
    tx_chunk_delay:
      (parseInt(document.getElementById('txChunkDelay').value) || 5) / 1000,
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

function setupAutoSave() {
  const textInputs = ['elfPath', 'compileCommandsPath', 'toolchainPath'];
  textInputs.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => saveConfig(true));
    }
  });

  const selectInputs = [
    'patchMode',
    'chunkSize',
    'txChunkSize',
    'txChunkDelay',
  ];
  selectInputs.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => saveConfig(true));
    }
  });
}

function onEnableDecompileChange() {
  saveConfig(true);
}

/* ===========================
   WATCH DIRS MANAGEMENT
   =========================== */
function updateWatchDirsList(dirs) {
  const list = document.getElementById('watchDirsList');
  list.innerHTML = '';

  if (!dirs || dirs.length === 0) return;

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
  const enabled = document.getElementById('autoCompile').checked;

  const watchDirsSection = document.getElementById('watchDirsSection');
  if (watchDirsSection) {
    watchDirsSection.style.display = enabled ? 'block' : 'none';
  }

  writeToOutput(
    `[INFO] Auto-inject on save: ${enabled ? 'Enabled' : 'Disabled'}`,
    'info',
  );
  fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auto_compile: enabled }),
  });

  if (enabled) {
    startAutoInjectPolling();
  } else {
    stopAutoInjectPolling();
  }
}

// Export for global access
window.loadConfig = loadConfig;
window.saveConfig = saveConfig;
window.setupAutoSave = setupAutoSave;
window.onEnableDecompileChange = onEnableDecompileChange;
window.updateWatchDirsList = updateWatchDirsList;
window.getWatchDirs = getWatchDirs;
window.addWatchDir = addWatchDir;
window.addWatchDirItem = addWatchDirItem;
window.browseWatchDir = browseWatchDir;
window.removeWatchDir = removeWatchDir;
window.onAutoCompileChange = onAutoCompileChange;
