/*========================================
  FPBInject Workbench - Slot Management Module
  ========================================*/

/* ===========================
   SLOT MANAGEMENT
   =========================== */
function updateSlotUI() {
  const state = window.FPBState;
  let activeCount = 0;
  const maxSlots = state.fpbVersion >= 2 ? 8 : 6;

  for (let i = 0; i < 8; i++) {
    const slotItem = document.querySelector(`.slot-item[data-slot="${i}"]`);
    const funcSpan = document.getElementById(`slot${i}Func`);
    const slotState = state.slotStates[i];
    const isDisabled = i >= maxSlots;

    if (slotItem) {
      slotItem.classList.toggle('occupied', slotState.occupied && !isDisabled);
      slotItem.classList.toggle(
        'active',
        i === state.selectedSlot && !isDisabled,
      );
      slotItem.classList.toggle('slot-disabled', isDisabled);

      const actionsDiv = slotItem.querySelector('.slot-actions');
      if (actionsDiv) {
        actionsDiv.style.display =
          slotState.occupied && !isDisabled ? 'flex' : 'none';
      }
    }

    if (funcSpan) {
      if (isDisabled) {
        funcSpan.textContent = t('device.fpb_v2_only', 'FPB v2 only');
        funcSpan.title = t(
          'device.fpb_v2_required',
          'This slot requires FPB v2 hardware',
        );
      } else if (slotState.occupied) {
        const funcName = slotState.func ? ` (${slotState.func})` : '';
        const sizeInfo = slotState.code_size
          ? `, ${slotState.code_size} ${t('device.bytes', 'Bytes')}`
          : '';
        funcSpan.textContent = `${slotState.orig_addr}${funcName} → ${slotState.target_addr}${sizeInfo}`;
        funcSpan.title = `${t('tooltips.slot_original', 'Original')}: ${slotState.orig_addr}${funcName}\n${t('tooltips.slot_target', 'Target')}: ${slotState.target_addr}\n${t('tooltips.slot_code_size', 'Code size')}: ${slotState.code_size || 0} ${t('device.bytes', 'Bytes')}`;
      } else {
        funcSpan.textContent = t('panels.slot_empty', 'Empty');
        funcSpan.title = '';
      }
    }

    if (slotState.occupied && !isDisabled) activeCount++;
  }

  document.getElementById('activeSlotCount').textContent =
    `${activeCount}/${maxSlots}`;
  document.getElementById('currentSlotDisplay').textContent =
    `Slot: ${state.selectedSlot}`;

  // Update slotSelect dropdown
  const slotSelect = document.getElementById('slotSelect');
  slotSelect.value = state.selectedSlot;

  // Disable v2-only slots in dropdown
  for (let i = 0; i < slotSelect.options.length; i++) {
    const option = slotSelect.options[i];
    const slotId = parseInt(option.value);
    option.disabled = slotId >= maxSlots;
  }
}

function selectSlot(slotId) {
  const state = window.FPBState;
  const maxSlots = state.fpbVersion >= 2 ? 8 : 6;

  if (slotId >= maxSlots) {
    log.warn(`Slot ${slotId} requires FPB v2 hardware`);
    return;
  }

  state.selectedSlot = parseInt(slotId);
  updateSlotUI();
  log.info(`Selected Slot ${slotId}`);

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
    log.error('Not connected');
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
      log.success(`Slot ${slotId} cleared`);
      fpbInfo();
    } else {
      log.error(`Failed to clear slot ${slotId}: ${data.message}`);
    }
  } catch (e) {
    log.error(`Unpatch error: ${e}`);
  }
}

async function fpbUnpatchAll() {
  const state = window.FPBState;
  if (!state.isConnected) {
    log.error('Not connected');
    return;
  }

  if (
    !confirm(
      `${t('messages.confirm_clear_all_slots', 'Are you sure you want to clear all FPB slots?')}\n\n` +
        t(
          'messages.unpatch_all_warning',
          'This will unpatch all injected functions.',
        ),
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
      state.slotStates = Array(8)
        .fill()
        .map(() => ({
          occupied: false,
          func: '',
          orig_addr: '',
          target_addr: '',
          code_size: 0,
        }));
      updateSlotUI();
      log.success('All slots cleared and memory freed');
      fpbInfo();
    } else {
      log.error(`Failed to clear all: ${data.message}`);
    }
  } catch (e) {
    log.error(`Unpatch all error: ${e}`);
  }
}

function updateMemoryInfo(memory) {
  const memoryEl = document.getElementById('memoryInfo');
  if (!memoryEl) return;

  const used = memory.used || 0;
  const usedLabel = t('device.used', 'Used');
  const bytesLabel = t('device.bytes', 'Bytes');

  memoryEl.innerHTML = `
    <div style="font-size: 10px; color: var(--vscode-descriptionForeground);">${usedLabel}: ${used} ${bytesLabel}</div>
  `;
}

// Export for global access
window.updateSlotUI = updateSlotUI;
window.selectSlot = selectSlot;
window.onSlotSelectChange = onSlotSelectChange;
window.initSlotSelectListener = initSlotSelectListener;
window.fpbUnpatch = fpbUnpatch;
window.fpbUnpatchAll = fpbUnpatchAll;
window.updateMemoryInfo = updateMemoryInfo;
