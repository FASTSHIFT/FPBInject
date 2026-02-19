/*========================================
  FPBInject Workbench - Log Polling Module
  ========================================*/

/* ===========================
   LOG POLLING
   =========================== */
function startLogPolling() {
  const state = window.FPBState;
  stopLogPolling();
  state.toolLogNextId = 0;
  state.rawLogNextId = 0;
  state.slotUpdateId = 0;
  state.logPollInterval = setInterval(fetchLogs, 200);
}

function stopLogPolling() {
  const state = window.FPBState;
  if (state.logPollInterval) {
    clearInterval(state.logPollInterval);
    state.logPollInterval = null;
  }
}

async function fetchLogs() {
  const state = window.FPBState;
  try {
    const res = await fetch(
      `/api/logs?tool_since=${state.toolLogNextId}&raw_since=${state.rawLogNextId}&slot_since=${state.slotUpdateId}`,
    );

    if (!res.ok) return;

    const contentType = res.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) return;

    const text = await res.text();
    if (!text || text.trim() === '') return;

    let data;
    try {
      data = JSON.parse(text);
    } catch (parseError) {
      console.warn(
        'Log parse error:',
        parseError,
        'Response:',
        text.substring(0, 100),
      );
      return;
    }

    if (data.tool_next !== undefined) state.toolLogNextId = data.tool_next;
    if (data.raw_next !== undefined) state.rawLogNextId = data.raw_next;

    if (
      data.tool_logs &&
      Array.isArray(data.tool_logs) &&
      data.tool_logs.length > 0
    ) {
      data.tool_logs.forEach((logMsg) => {
        writeToOutput(logMsg, 'info');
      });
    }

    if (data.raw_data && data.raw_data.length > 0) {
      writeToSerial(data.raw_data);
    }

    if (
      data.slot_update_id !== undefined &&
      data.slot_update_id > state.slotUpdateId
    ) {
      state.slotUpdateId = data.slot_update_id;
      if (data.slot_data && data.slot_data.slots) {
        data.slot_data.slots.forEach((slot, i) => {
          if (i < 6) {
            state.slotStates[i] = {
              occupied: slot.occupied || false,
              func: slot.func || '',
              orig_addr: slot.orig_addr || '',
              target_addr: slot.target_addr || '',
              code_size: slot.code_size || 0,
            };
          }
        });
        updateSlotUI();
        if (data.slot_data.memory) {
          updateMemoryInfo(data.slot_data.memory);
        }
      }
    }
  } catch (e) {
    // Silently fail on polling errors
  }
}

// Export for global access
window.startLogPolling = startLogPolling;
window.stopLogPolling = stopLogPolling;
window.fetchLogs = fetchLogs;
