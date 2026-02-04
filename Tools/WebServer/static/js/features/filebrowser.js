/*========================================
  FPBInject Workbench - File Browser Module
  ========================================*/

/* ===========================
   FILE BROWSER
   =========================== */
const HOME_PATH = '~';

function browseFile(inputId, filter = '') {
  const state = window.FPBState;
  state.fileBrowserCallback = (path) => {
    document.getElementById(inputId).value = path;
    saveConfig(true);
    if (inputId === 'elfPath') {
      refreshSymbolsFromELF(path);
    }
  };
  state.fileBrowserFilter = filter;
  state.fileBrowserMode = 'file';
  openFileBrowser(HOME_PATH);
}

async function refreshSymbolsFromELF(elfPath) {
  writeToOutput(`[INFO] Loading symbols from ${elfPath}...`, 'system');
  try {
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ elf_path: elfPath }),
    });
    const list = document.getElementById('symbolList');
    list.innerHTML =
      '<div style="padding: 8px; font-size: 11px; opacity: 0.7;">Symbols ready. Search above...</div>';
    writeToOutput(`[SUCCESS] ELF loaded: ${elfPath}`, 'success');
  } catch (e) {
    writeToOutput(`[ERROR] Failed to load ELF: ${e}`, 'error');
  }
}

function browseDir(inputId) {
  const state = window.FPBState;
  state.fileBrowserCallback = (path) => {
    document.getElementById(inputId).value = path;
    saveConfig(true);
  };
  state.fileBrowserFilter = '';
  state.fileBrowserMode = 'dir';
  openFileBrowser(HOME_PATH);
}

async function openFileBrowser(path) {
  const state = window.FPBState;
  state.currentBrowserPath = path;
  document.getElementById('browserPath').value = path;
  document.getElementById('fileBrowserModal').classList.add('show');
  state.selectedBrowserItem = null;

  try {
    const res = await fetch(`/api/browse?path=${encodeURIComponent(path)}`);
    const data = await res.json();

    const list = document.getElementById('fileList');
    list.innerHTML = '';

    const actualPath = data.current_path || path;
    state.currentBrowserPath = actualPath;
    document.getElementById('browserPath').value = actualPath;

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

      if (
        !isDir &&
        state.fileBrowserMode === 'file' &&
        state.fileBrowserFilter &&
        !item.name.endsWith(state.fileBrowserFilter)
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
          if (state.fileBrowserMode === 'dir') {
            selectFileBrowserItem(div, itemPath);
          } else {
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
  const state = window.FPBState;
  document
    .querySelectorAll('.file-item')
    .forEach((el) => el.classList.remove('selected'));
  element.classList.add('selected');
  state.selectedBrowserItem = path;
}

function selectBrowserItem() {
  const state = window.FPBState;
  if (state.fileBrowserMode === 'dir') {
    const path = state.selectedBrowserItem || state.currentBrowserPath;
    if (state.fileBrowserCallback) state.fileBrowserCallback(path);
  } else if (state.selectedBrowserItem) {
    if (state.fileBrowserCallback)
      state.fileBrowserCallback(state.selectedBrowserItem);
  }
  closeFileBrowser();
}

function closeFileBrowser() {
  const state = window.FPBState;
  document.getElementById('fileBrowserModal').classList.remove('show');
  state.selectedBrowserItem = null;
}

/* ===========================
   SERIAL PORT COMMAND
   =========================== */
async function sendTerminalCommand(data) {
  const state = window.FPBState;
  if (!state.isConnected) return;

  try {
    await fetch('/api/serial/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: data }),
    });
  } catch (e) {
    // Silent fail
  }
}

// Export for global access
window.HOME_PATH = HOME_PATH;
window.browseFile = browseFile;
window.refreshSymbolsFromELF = refreshSymbolsFromELF;
window.browseDir = browseDir;
window.openFileBrowser = openFileBrowser;
window.navigateTo = navigateTo;
window.onBrowserPathKeyup = onBrowserPathKeyup;
window.selectFileBrowserItem = selectFileBrowserItem;
window.selectBrowserItem = selectBrowserItem;
window.closeFileBrowser = closeFileBrowser;
window.sendTerminalCommand = sendTerminalCommand;
