/*========================================
  FPBInject Workbench - Auto-Inject Polling Module
  ========================================*/

/* ===========================
   AUTO-INJECT STATUS POLLING
   =========================== */
function startAutoInjectPolling() {
  const state = window.FPBState;
  if (state.autoInjectPollInterval) return;

  state.autoInjectPollInterval = setInterval(pollAutoInjectStatus, 500);
  log.debug('Auto-inject status monitoring started');
}

function stopAutoInjectPolling() {
  const state = window.FPBState;
  if (state.autoInjectPollInterval) {
    clearInterval(state.autoInjectPollInterval);
    state.autoInjectPollInterval = null;
    log.debug('Auto-inject status monitoring stopped');
  }
}

async function pollAutoInjectStatus() {
  const state = window.FPBState;
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

    const statusChanged = status !== state.lastAutoInjectStatus;

    if (statusChanged) {
      state.lastAutoInjectStatus = status;

      switch (status) {
        case 'detecting':
          writeToOutput(`[AUTO-INJECT] ${message}`, 'system');
          break;
        case 'generating':
          writeToOutput(`[AUTO-INJECT] ${message}`, 'info');
          if (modifiedFuncs.length > 0) {
            document.getElementById('targetFunc').value = modifiedFuncs[0];
          }
          break;
        case 'compiling':
          writeToOutput(`[AUTO-INJECT] ${message}`, 'info');
          if (modifiedFuncs.length > 0) {
            createPatchPreviewTab(modifiedFuncs[0], sourceFile);
          }
          break;
        case 'injecting':
          writeToOutput(`[AUTO-INJECT] ${message}`, 'info');
          break;
        case 'success':
          writeToOutput(`[AUTO-INJECT] ${message}`, 'success');
          if (result && Object.keys(result).length > 0) {
            displayAutoInjectStats(result, modifiedFuncs[0] || 'unknown');
          }
          if (modifiedFuncs.length > 0) {
            createPatchPreviewTab(modifiedFuncs[0], sourceFile);
          }
          updateSlotUI();
          fpbInfo();
          break;
        case 'failed':
          writeToOutput(`[AUTO-INJECT] ${message}`, 'error');
          break;
        case 'idle':
          break;
      }

      if (status === 'generating' || status === 'success') {
        await loadPatchSourceFromBackend();
      }
    }

    updateAutoInjectProgress(progress, status, statusChanged);
  } catch (e) {
    // Silent error
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

  const injections = result.injections || [];
  if (injections.length > 0) {
    const successCount = result.successful_count || 0;
    const totalCount = result.total_count || injections.length;
    writeToOutput(
      `Functions:     ${successCount}/${totalCount} injected successfully`,
      'info',
    );

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
        `⚠️ ${t('messages.injection_failed_count', '{{count}} injection(s) failed!', { count: failedInjections.length })}\n\n` +
        `${t('messages.failed_functions', 'Failed functions')}:\n${failedList}\n\n`;

      if (isSlotFull) {
        message +=
          `${t('messages.slots_full_hint', 'This may be due to FPB Slots being full.')}\n` +
          t(
            'messages.clear_slots_hint',
            'Please clear some Slots in DEVICE INFO panel and try again.',
          );
      }

      setTimeout(() => {
        alert(message);
        const deviceDetails = document.getElementById('details-device');
        if (deviceDetails) {
          deviceDetails.open = true;
        }
      }, 100);
    }
  } else {
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
  const state = window.FPBState;
  let baseName = funcName;
  if (sourceFile) {
    baseName = sourceFile
      .split('/')
      .pop()
      .replace(/\.[^.]+$/, '');
  }
  const tabId = `patch_${baseName}`;
  const tabTitle = `patch_${baseName}.c`;

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

  const existingTab = state.editorTabs.find((t) => t.id === tabId);
  if (existingTab) {
    const existingContent = document.getElementById(`tabContent_${tabId}`);
    if (existingContent) {
      const codeEl = existingContent.querySelector('code');
      if (codeEl) {
        codeEl.textContent = patchContent;
        if (typeof hljs !== 'undefined') {
          hljs.highlightElement(codeEl);
        }
      }
    }
    switchEditorTab(tabId);
    return;
  }

  state.editorTabs.push({
    id: tabId,
    title: tabTitle,
    type: 'preview',
    closable: true,
  });

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
  const state = window.FPBState;
  const allProgressEls = document.querySelectorAll('.inject-progress');

  if (status === 'idle') return;

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

  if (status === 'success' || status === 'failed') {
    if (statusChanged) {
      if (state.autoInjectProgressHideTimer)
        clearTimeout(state.autoInjectProgressHideTimer);
      state.autoInjectProgressHideTimer = setTimeout(() => {
        allProgressEls.forEach((el) => {
          el.style.display = 'none';
          const fill = el.querySelector('#injectProgressFill, .progress-fill');
          if (fill) {
            fill.style.width = '0%';
            fill.style.background = '';
          }
        });
        state.autoInjectProgressHideTimer = null;
      }, 3000);
    }
  } else {
    if (state.autoInjectProgressHideTimer) {
      clearTimeout(state.autoInjectProgressHideTimer);
      state.autoInjectProgressHideTimer = null;
    }
  }
}

// Export for global access
window.startAutoInjectPolling = startAutoInjectPolling;
window.stopAutoInjectPolling = stopAutoInjectPolling;
window.pollAutoInjectStatus = pollAutoInjectStatus;
window.displayAutoInjectStats = displayAutoInjectStats;
window.loadPatchSourceFromBackend = loadPatchSourceFromBackend;
window.createPatchPreviewTab = createPatchPreviewTab;
window.updateAutoInjectProgress = updateAutoInjectProgress;
