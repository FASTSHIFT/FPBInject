/*========================================
  FPBInject Workbench - Slot Management Module
  ========================================*/

/* ===========================
   SLOT MANAGEMENT
   =========================== */
function updateSlotUI() {
  const state = window.FPBState;
  let activeCount = 0;

  for (let i = 0; i < 6; i++) {
    const slotItem = document.querySelector(`.slot-item[data-slot="${i}"]`);
    const funcSpan = document.getElementById(`slot${i}Func`);
    const slotState = state.slotStates[i];

    if (slotItem) {
      slotItem.classList.toggle('occupied', slotState.occupied);
      slotItem.classList.toggle('active', i === state.selectedSlot);

      const actionsDiv = slotItem.querySelector('.slot-actions');
      if (actionsDiv) {
        actionsDiv.style.display = slotState.occupied ? 'flex' : 'none';
      }
    }

    if (funcSpan) {
      if (slotState.occupied) {
        const funcName = slotState.func ? ` (${slotState.func})` : '';
        const sizeInfo = slotState.code_size
          ? `, ${slotState.code_size} Bytes`
          : '';
        funcSpan.textContent = `${slotState.orig_addr}${funcName} → ${slotState.target_addr}${sizeInfo}`;
        funcSpan.title = `Original: ${slotState.orig_addr}${funcName}\nTarget: ${slotState.target_addr}\nCode size: ${slotState.code_size || 0} Bytes`;
      } else {
        funcSpan.textContent = 'Empty';
        funcSpan.title = '';
      }
    }

    if (slotState.occupied) activeCount++;
  }

  document.getElementById('activeSlotCount').textContent = `${activeCount}/6`;
  document.getElementById('currentSlotDisplay').textContent =
    `Slot: ${state.selectedSlot}`;
  document.getElementById('slotSelect').value = state.selectedSlot;
}

function selectSlot(slotId) {
  const state = window.FPBState;
  state.selectedSlot = parseInt(slotId);
  updateSlotUI();
  writeToOutput(`[INFO] Selected Slot ${slotId}`, 'info');

  const slotState = state.slotStates[slotId];
  if (slotState && slotState.func) {
    const funcName = slotState.func;
    const addr = slotState.addr || '0x00000000';
    openDisassembly(funcName, addr);
  }
}

function onSlotSelectChange() {
  const slotId = parseInt(document.getElementById('slotSelect').value);
  selectSlot(slotId);
}

function initSlotSelectListener() {
  const slotSelect = document.getElementById('slotSelect');
  if (slotSelect) {
    slotSelect.addEventListener('change', onSlotSelectChange);
  }
}

async function fpbUnpatch(slotId) {
  const state = window.FPBState;
  if (!state.isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  try {
    const res = await fetch('/api/fpb/unpatch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comp: slotId }),
    });
    const data = await res.json();

    if (data.success) {
      state.slotStates[slotId] = {
        occupied: false,
        func: '',
        orig_addr: '',
        target_addr: '',
        code_size: 0,
      };
      updateSlotUI();
      writeToOutput(`[SUCCESS] Slot ${slotId} cleared`, 'success');
      fpbInfo();
    } else {
      writeToOutput(
        `[ERROR] Failed to clear slot ${slotId}: ${data.message}`,
        'error',
      );
    }
  } catch (e) {
    writeToOutput(`[ERROR] Unpatch error: ${e}`, 'error');
  }
}

async function fpbReinject(slotId) {
  const state = window.FPBState;
  if (!state.isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  const slotState = state.slotStates[slotId];
  const targetFunc = slotState?.func;

  if (!targetFunc) {
    writeToOutput(
      `[ERROR] Slot ${slotId} is empty, nothing to re-inject`,
      'error',
    );
    return;
  }

  writeToOutput(
    `[INFO] Re-injecting ${targetFunc} to Slot ${slotId}...`,
    'info',
  );

  try {
    const sourceRes = await fetch('/api/patch/source');
    const sourceData = await sourceRes.json();

    if (!sourceData.success || !sourceData.content?.trim()) {
      writeToOutput(
        '[ERROR] No patch source available. Please use Auto Inject on Save first.',
        'error',
      );
      return;
    }

    const patchSource = sourceData.content;
    const patchMode =
      document.getElementById('patchMode')?.value || 'trampoline';

    const res = await fetch('/api/fpb/inject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_content: patchSource,
        target_func: targetFunc,
        patch_mode: patchMode,
        comp: slotId,
      }),
    });
    const data = await res.json();

    if (data.success) {
      writeToOutput(
        `[SUCCESS] Re-injected ${targetFunc} to Slot ${slotId}`,
        'success',
      );
      await fpbInfo();
    } else {
      writeToOutput(
        `[ERROR] Re-inject failed: ${data.error || 'Unknown error'}`,
        'error',
      );
    }
  } catch (e) {
    writeToOutput(`[ERROR] Re-inject error: ${e}`, 'error');
  }
}

async function fpbUnpatchAll() {
  const state = window.FPBState;
  if (!state.isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  if (
    !confirm(
      'Are you sure you want to clear all FPB slots? This will unpatch all injected functions.',
    )
  ) {
    return;
  }

  try {
    const res = await fetch('/api/fpb/unpatch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ all: true }),
    });
    const data = await res.json();

    if (data.success) {
      state.slotStates = Array(6)
        .fill()
        .map(() => ({
          occupied: false,
          func: '',
          orig_addr: '',
          target_addr: '',
          code_size: 0,
        }));
      updateSlotUI();
      writeToOutput('[SUCCESS] All slots cleared and memory freed', 'success');
      fpbInfo();
    } else {
      writeToOutput(`[ERROR] Failed to clear all: ${data.message}`, 'error');
    }
  } catch (e) {
    writeToOutput(`[ERROR] Unpatch all error: ${e}`, 'error');
  }
}

function updateMemoryInfo(memory) {
  const memoryEl = document.getElementById('memoryInfo');
  if (!memoryEl) return;

  const used = memory.used || 0;

  memoryEl.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: center; gap: 8px;">
      <span style="font-size: 10px; color: var(--vscode-descriptionForeground);">Used: ${used} Bytes</span>
    </div>
  `;
}

// Export for global access
window.updateSlotUI = updateSlotUI;
window.selectSlot = selectSlot;
window.onSlotSelectChange = onSlotSelectChange;
window.initSlotSelectListener = initSlotSelectListener;
window.fpbUnpatch = fpbUnpatch;
window.fpbReinject = fpbReinject;
window.fpbUnpatchAll = fpbUnpatchAll;
window.updateMemoryInfo = updateMemoryInfo;
