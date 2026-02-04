/*========================================
  FPBInject Workbench - FPB Commands Module
  ========================================*/

/* ===========================
   FPB COMMANDS
   =========================== */
async function fpbPing() {
  const state = window.FPBState;
  if (!state.isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  try {
    const res = await fetch('/api/fpb/ping', { method: 'POST' });
    const data = await res.json();
    writeToOutput(`[PING] ${data.message}`, data.success ? 'success' : 'error');
  } catch (e) {
    writeToOutput(`[ERROR] Ping failed: ${e}`, 'error');
  }
}

async function fpbTestSerial() {
  const state = window.FPBState;
  if (!state.isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  writeToOutput(
    '[TEST] Starting serial throughput test (x2 stepping)...',
    'info',
  );

  try {
    const res = await fetch('/api/fpb/test-serial', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        start_size: 16,
        max_size: 4096,
        timeout: 2.0,
      }),
    });
    const data = await res.json();

    if (data.success) {
      writeToOutput('─'.repeat(50), 'info');
      writeToOutput('[TEST] Serial Throughput Test Results:', 'info');

      if (data.tests && data.tests.length > 0) {
        data.tests.forEach((test) => {
          const status = test.passed ? '✓' : '✗';
          const timeStr = test.response_time_ms
            ? ` (${test.response_time_ms}ms)`
            : '';
          const cmdLen = test.cmd_len ? ` [cmd:${test.cmd_len}B]` : '';
          const errStr = test.error ? ` - ${test.error}` : '';
          writeToOutput(
            `  ${status} ${test.size} bytes${cmdLen}${timeStr}${errStr}`,
            test.passed ? 'success' : 'error',
          );
        });
      }

      writeToOutput('─'.repeat(50), 'info');
      writeToOutput(
        `[RESULT] Max working size: ${data.max_working_size} bytes`,
        'success',
      );
      if (data.failed_size > 0) {
        writeToOutput(
          `[RESULT] Failed at: ${data.failed_size} bytes`,
          'warning',
        );
      }
      writeToOutput(
        `[RESULT] Recommended chunk size: ${data.recommended_chunk_size} bytes`,
        'success',
      );

      // Ask user if they want to apply recommended chunk size
      const recommendedSize = data.recommended_chunk_size;
      const currentSize =
        parseInt(document.getElementById('chunkSize')?.value) || 128;

      const apply = confirm(
        `Serial Throughput Test Complete!\n\n` +
          `Current chunk size: ${currentSize} bytes\n` +
          `Recommended chunk size: ${recommendedSize} bytes\n\n` +
          `Do you want to apply the recommended chunk size?`,
      );

      if (apply) {
        const chunkInput = document.getElementById('chunkSize');
        if (chunkInput) {
          chunkInput.value = recommendedSize;
          await saveConfig(true);
          writeToOutput(
            `[CONFIG] Chunk size updated to ${recommendedSize} bytes`,
            'success',
          );
        }
      } else {
        writeToOutput(
          `[CONFIG] Chunk size unchanged (${currentSize} bytes)`,
          'info',
        );
      }
    } else {
      writeToOutput(
        `[ERROR] Test failed: ${data.error || 'Unknown error'}`,
        'error',
      );
    }
  } catch (e) {
    writeToOutput(`[ERROR] Serial test failed: ${e}`, 'error');
  }
}

async function fpbInfo() {
  const state = window.FPBState;
  if (!state.isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  try {
    const res = await fetch('/api/fpb/info');
    const data = await res.json();

    if (data.success) {
      if (data.build_time_mismatch) {
        const deviceTime = data.device_build_time || 'Unknown';
        const elfTime = data.elf_build_time || 'Unknown';

        writeToOutput(`[WARNING] Build time mismatch detected!`, 'error');
        writeToOutput(`  Device firmware: ${deviceTime}`, 'error');
        writeToOutput(`  ELF file: ${elfTime}`, 'error');

        alert(
          `⚠️ Build Time Mismatch!\n\n` +
            `The device firmware and ELF file have different build times.\n` +
            `This may cause injection to fail or behave unexpectedly.\n\n` +
            `Device firmware: ${deviceTime}\n` +
            `ELF file: ${elfTime}\n\n` +
            `Please ensure the ELF file matches the firmware running on the device.`,
        );
      }

      if (data.slots) {
        data.slots.forEach((slot, i) => {
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
      }
      updateSlotUI();

      if (data.memory) {
        updateMemoryInfo(data.memory);
      }

      if (data.device_build_time) {
        writeToOutput(`[INFO] Device build: ${data.device_build_time}`, 'info');
      }

      writeToOutput('[INFO] Device info updated', 'success');
    } else {
      writeToOutput(
        `[ERROR] ${data.error || 'Failed to get device info'}`,
        'error',
      );
    }
  } catch (e) {
    writeToOutput(`[ERROR] Info failed: ${e}`, 'error');
  }
}

async function fpbInjectMulti() {
  const state = window.FPBState;
  if (!state.isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  const patchSource = document.getElementById('patchSource')?.value || '';
  if (!patchSource.trim()) {
    writeToOutput('[ERROR] No patch source code available', 'error');
    return;
  }

  writeToOutput('[INFO] Injecting all functions...', 'info');

  try {
    const patchMode =
      document.getElementById('patchMode')?.value || 'trampoline';
    const res = await fetch('/api/fpb/inject/multi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_content: patchSource,
        patch_mode: patchMode,
      }),
    });
    const data = await res.json();

    if (data.success) {
      const successCount = data.successful_count || 0;
      const totalCount = data.total_count || 0;
      writeToOutput(
        `[SUCCESS] Injected ${successCount}/${totalCount} functions`,
        'success',
      );
      displayAutoInjectStats(data, 'multi');
      await fpbInfo();
    } else {
      writeToOutput(
        `[ERROR] Multi-inject failed: ${data.error || 'Unknown error'}`,
        'error',
      );
    }
  } catch (e) {
    writeToOutput(`[ERROR] Multi-inject error: ${e}`, 'error');
  }
}

// Export for global access
window.fpbPing = fpbPing;
window.fpbTestSerial = fpbTestSerial;
window.fpbInfo = fpbInfo;
window.fpbInjectMulti = fpbInjectMulti;
