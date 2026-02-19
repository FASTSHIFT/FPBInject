/*========================================
  FPBInject Workbench - Editor/Tab Management Module
  ========================================*/

/* ===========================
   ACE EDITOR MANAGEMENT
   =========================== */
function initAceEditor(tabId, content, mode, readOnly = false) {
  const editorElement = document.getElementById(`editor_${tabId}`);
  if (!editorElement) {
    return null;
  }

  const tabContent = document.getElementById(`tabContent_${tabId}`);
  if (tabContent) {
    const rect = tabContent.getBoundingClientRect();
    if (rect.height > 0) {
      editorElement.style.height = rect.height + 'px';
    } else {
      editorElement.style.height = 'calc(100vh - 200px)';
    }
  }

  if (typeof ace === 'undefined') {
    return null;
  }

  const editor = ace.edit(editorElement);
  const currentTheme = document.documentElement.getAttribute('data-theme');
  const isDarkTheme = currentTheme !== 'light';
  editor.setTheme(
    isDarkTheme ? 'ace/theme/tomorrow_night' : 'ace/theme/tomorrow',
  );

  editor.session.setMode(`ace/mode/${mode}`);

  editor.setOptions({
    fontSize: '13px',
    fontFamily: '"Consolas", "Courier New", monospace',
    showLineNumbers: true,
    showGutter: true,
    highlightActiveLine: true,
    readOnly: readOnly,
    wrap: false,
    tabSize: 4,
    useSoftTabs: true,
    showPrintMargin: false,
  });

  editor.setValue(content, -1);

  const { aceEditors } = window.FPBState;
  aceEditors.set(tabId, editor);

  setTimeout(() => editor.resize(), 0);

  return editor;
}

function getAceEditorContent(tabId) {
  const { aceEditors } = window.FPBState;
  const editor = aceEditors.get(tabId);
  if (editor) {
    return editor.getValue();
  }
  const textarea = document.getElementById(`editor_${tabId}`);
  return textarea ? textarea.value : '';
}

/* ===========================
   TAB MANAGEMENT
   =========================== */
function switchEditorTab(tabId) {
  const state = window.FPBState;
  state.activeEditorTab = tabId;

  document.querySelectorAll('.editor-tabs-header .tab').forEach((tab) => {
    tab.classList.toggle('active', tab.getAttribute('data-tab') === tabId);
  });

  document.querySelectorAll('.tab-content').forEach((content) => {
    if (content.id === 'tabContent_empty') {
      content.classList.toggle('active', state.editorTabs.length === 0);
    } else {
      content.classList.toggle('active', content.id === `tabContent_${tabId}`);
    }
  });

  const { aceEditors } = state;
  const editor = aceEditors.get(tabId);
  if (editor) {
    setTimeout(() => editor.resize(), 0);
  }

  const editorToolbar = document.querySelector('.editor-toolbar');
  if (editorToolbar) {
    const tabInfo = state.editorTabs.find((t) => t.id === tabId);
    const isManualPatchTab = tabInfo && tabInfo.type === 'c';
    editorToolbar.style.display = isManualPatchTab ? 'flex' : 'none';

    if (isManualPatchTab && tabInfo.funcName) {
      state.currentPatchTab = { id: tabId, funcName: tabInfo.funcName };
    }
  }
}

function closeTab(tabId, event) {
  if (event) event.stopPropagation();

  const state = window.FPBState;
  const tabInfo = state.editorTabs.find((t) => t.id === tabId);
  if (!tabInfo || !tabInfo.closable) return;

  const { aceEditors } = state;
  if (aceEditors.has(tabId)) {
    const editor = aceEditors.get(tabId);
    editor.destroy();
    aceEditors.delete(tabId);
  }

  state.editorTabs = state.editorTabs.filter((t) => t.id !== tabId);

  document.querySelector(`.tab[data-tab="${tabId}"]`)?.remove();
  document.getElementById(`tabContent_${tabId}`)?.remove();

  if (state.currentPatchTab && state.currentPatchTab.id === tabId) {
    state.currentPatchTab = null;
  }

  if (state.activeEditorTab === tabId) {
    if (state.editorTabs.length > 0) {
      switchEditorTab(state.editorTabs[0].id);
    } else {
      state.activeEditorTab = null;
      document.getElementById('tabContent_empty')?.classList.add('active');
      document.querySelector('.editor-toolbar').style.display = 'none';
    }
  }
}

/* ===========================
   DISASSEMBLY & PATCH TABS
   =========================== */
async function openDisassembly(funcName, addr) {
  const state = window.FPBState;
  const tabId = `disasm_${funcName}`;

  if (state.editorTabs.find((t) => t.id === tabId)) {
    switchEditorTab(tabId);
    return;
  }

  writeToOutput(`[DISASM] Loading disassembly for ${funcName}...`, 'system');

  try {
    const res = await fetch(
      `/api/symbols/disasm?func=${encodeURIComponent(funcName)}`,
    );
    if (!res.ok) {
      writeToOutput(
        `[ERROR] Failed to load disassembly: HTTP ${res.status}`,
        'error',
      );
      return;
    }
    const data = await res.json();

    state.editorTabs.push({
      id: tabId,
      title: `${funcName}.asm`,
      type: 'asm',
      closable: true,
    });

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
    tabDiv.onmousedown = (e) => {
      if (e.button === 1) {
        e.preventDefault();
        closeTab(tabId, e);
      }
    };
    tabsHeader.appendChild(tabDiv);

    const tabsContent = document.querySelector('.editor-tabs-content');
    const contentDiv = document.createElement('div');
    contentDiv.className = 'tab-content';
    contentDiv.id = `tabContent_${tabId}`;

    const disasmCode =
      data.disasm ||
      `; Disassembly for ${funcName} @ ${addr}\n; (Disassembly data not available)`;

    contentDiv.innerHTML = `
      <div class="editor-main">
        <div id="editor_${tabId}" class="ace-editor-container"></div>
      </div>
    `;
    tabsContent.appendChild(contentDiv);

    switchEditorTab(tabId);
    initAceEditor(tabId, disasmCode, 'assembly_x86', true);
    writeToOutput(`[SUCCESS] Disassembly loaded for ${funcName}`, 'success');
  } catch (e) {
    writeToOutput(`[ERROR] Failed to load disassembly: ${e}`, 'error');
  }
}

async function openManualPatchTab(funcName) {
  const state = window.FPBState;
  const tabId = `patch_${funcName}`;
  const tabTitle = `patch_${funcName}.c`;

  if (state.editorTabs.find((t) => t.id === tabId)) {
    switchEditorTab(tabId);
    return;
  }

  const enableDecompile = document.getElementById('enableDecompile')?.checked;

  writeToOutput(
    `[PATCH] Creating manual patch tab for ${funcName}...`,
    'system',
  );

  const loadingContent = enableDecompile
    ? `/*\n * Loading...\n * \n * Decompiling ${funcName}, please wait...\n * This may take a few seconds.\n */\n`
    : '';

  state.editorTabs.push({
    id: tabId,
    title: tabTitle,
    type: 'c',
    closable: true,
    funcName: funcName,
    content: loadingContent,
  });

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
  tabDiv.onmousedown = (e) => {
    if (e.button === 1) {
      e.preventDefault();
      closeTab(tabId, e);
    }
  };
  tabsHeader.appendChild(tabDiv);

  const tabsContent = document.querySelector('.editor-tabs-content');
  const contentDiv = document.createElement('div');
  contentDiv.className = 'tab-content';
  contentDiv.id = `tabContent_${tabId}`;

  contentDiv.innerHTML = `
    <div class="editor-main">
      <div id="editor_${tabId}" class="ace-editor-container"></div>
    </div>
  `;
  tabsContent.appendChild(contentDiv);

  switchEditorTab(tabId);
  state.currentPatchTab = { id: tabId, funcName: funcName };

  initAceEditor(tabId, loadingContent, 'c_cpp');

  let template = '';
  let decompiled = null;
  let ghidraNotConfigured = false;

  const progressEl = document.getElementById('injectProgress');
  const progressText = document.getElementById('injectProgressText');
  const progressFill = document.getElementById('injectProgressFill');

  /* Helper to show/hide progress */
  const showProgress = (text, percent = 0) => {
    progressEl.style.display = 'flex';
    progressText.textContent = text;
    progressFill.style.width = `${percent}%`;
    progressFill.style.background = '';
  };

  const hideProgress = (delay = 0) => {
    setTimeout(() => {
      progressEl.style.display = 'none';
      progressFill.style.width = '0%';
    }, delay);
  };

  let decompilePromise = Promise.resolve(null);
  if (enableDecompile) {
    writeToOutput(
      `[DECOMPILE] Requesting decompilation for ${funcName}...`,
      'system',
    );

    /* Use streaming API for progress feedback */
    decompilePromise = (async () => {
      try {
        showProgress('Starting decompilation...', 10);

        const response = await fetch(
          `/api/symbols/decompile/stream?func=${encodeURIComponent(funcName)}`,
        );

        if (!response.ok) {
          hideProgress();
          return { decompiled: null, notInstalled: false };
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let result = { decompiled: null, notInstalled: false };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));

                if (data.type === 'status') {
                  if (data.stage === 'analyzing') {
                    showProgress('Analyzing ELF (first time)...', 30);
                  } else if (data.stage === 'decompiling') {
                    showProgress('Decompiling function...', 60);
                  }
                } else if (data.type === 'result') {
                  if (data.success && data.decompiled) {
                    result = {
                      decompiled: data.decompiled,
                      notInstalled: false,
                    };
                  } else if (data.error === 'GHIDRA_NOT_CONFIGURED') {
                    result = { decompiled: null, notInstalled: true };
                  }
                }
              } catch (e) {
                console.warn('Failed to parse SSE data:', e);
              }
            }
          }
        }

        hideProgress();
        return result;
      } catch (e) {
        hideProgress();
        return { decompiled: null, notInstalled: false };
      }
    })();
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

    const decompileResult = await decompilePromise;
    decompiled = decompileResult?.decompiled || null;
    ghidraNotConfigured = decompileResult?.notInstalled || false;

    template = generatePatchTemplate(
      funcName,
      state.selectedSlot,
      signature,
      sourceFile,
      decompiled,
      ghidraNotConfigured,
    );

    if (decompiled) {
      writeToOutput(`[INFO] Decompiled code included as reference`, 'info');
    } else if (ghidraNotConfigured) {
      writeToOutput(
        `[INFO] Ghidra not configured - set Ghidra Path in Settings panel`,
        'info',
      );
    }
  } catch (e) {
    const decompileResult = await decompilePromise;
    decompiled = decompileResult?.decompiled || null;
    ghidraNotConfigured = decompileResult?.notInstalled || false;
    template = generatePatchTemplate(
      funcName,
      state.selectedSlot,
      null,
      null,
      decompiled,
      ghidraNotConfigured,
    );
  }

  const { aceEditors } = state;
  const editor = aceEditors.get(tabId);
  if (editor) {
    editor.setValue(template, -1);
  }

  const tabEntry = state.editorTabs.find((t) => t.id === tabId);
  if (tabEntry) {
    tabEntry.content = template;
  }

  writeToOutput(`[SUCCESS] Created patch tab: ${tabTitle}`, 'success');
}

async function savePatchFile() {
  const state = window.FPBState;
  if (!state.currentPatchTab || !state.currentPatchTab.funcName) {
    writeToOutput('[ERROR] No patch tab selected', 'error');
    return;
  }

  const funcName = state.currentPatchTab.funcName;
  const tabId = state.currentPatchTab.id;

  const content = getAceEditorContent(tabId);
  if (!content) {
    writeToOutput('[ERROR] Editor not found', 'error');
    return;
  }

  const fileName = `patch_${funcName}.c`;

  state.fileBrowserCallback = async (selectedPath) => {
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
  state.fileBrowserFilter = '';
  state.fileBrowserMode = 'dir';
  openFileBrowser(HOME_PATH);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Export for global access
window.initAceEditor = initAceEditor;
window.getAceEditorContent = getAceEditorContent;
window.switchEditorTab = switchEditorTab;
window.closeTab = closeTab;
window.openDisassembly = openDisassembly;
window.openManualPatchTab = openManualPatchTab;
window.savePatchFile = savePatchFile;
window.escapeHtml = escapeHtml;
