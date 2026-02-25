/*========================================
  FPBInject Workbench - FPB Commands Module
  ========================================*/

/* ===========================
   FPB COMMANDS
   =========================== */
async function fpbPing() {
  const state = window.FPBState;
  if (!state.isConnected) {
    log.error('Not connected');
    alert(t('messages.not_connected', 'Not connected to device'));
    return;
  }

  try {
    const res = await fetch('/api/fpb/ping', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      log.success(data.message);
      alert(
        `✅ ${t('messages.ping_success', 'Device Detected')}\n\n` +
          `${data.message || t('messages.device_responding', 'Device is responding')}`,
      );
    } else {
      log.error(data.message);
      alert(
        `❌ ${t('messages.ping_failed', 'Device Detection Failed')}\n\n` +
          `${data.message || t('messages.device_not_responding', 'Device is not responding')}`,
      );
    }
  } catch (e) {
    log.error(`Ping failed: ${e}`);
    alert(
      `❌ ${t('messages.ping_failed', 'Device Detection Failed')}\n\n` +
        `${t('messages.error', 'Error')}: ${e}`,
    );
  }
}

async function fpbTestSerial() {
  const state = window.FPBState;
  if (!state.isConnected) {
    log.error('Not connected');
    return;
  }

  log.info('Starting serial throughput test (x2 stepping)...');

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
      log.info('Serial Throughput Test Results:');

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
      log.success(`Max working size: ${data.max_working_size} bytes`);
      if (data.failed_size > 0) {
        log.warn(`Failed at: ${data.failed_size} bytes`);
      }
      log.success(
        `Recommended chunk size: ${data.recommended_chunk_size} bytes`,
      );

      /* Ask user if they want to apply recommended chunk size */
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
          log.success(`Chunk size updated to ${recommendedSize} bytes`);
        }
      } else {
        log.info(`Chunk size unchanged (${currentSize} bytes)`);
      }
    } else {
      log.error(`Test failed: ${data.error || 'Unknown error'}`);
    }
  } catch (e) {
    log.error(`Serial test failed: ${e}`);
  }
}

async function fpbInfo() {
  const state = window.FPBState;
  if (!state.isConnected) {
    log.error('Not connected');
    alert(t('messages.not_connected', 'Not connected to device'));
    return;
  }

  try {
    const res = await fetch('/api/fpb/info');
    const data = await res.json();

    if (data.success) {
      if (data.build_time_mismatch) {
        const deviceTime = data.device_build_time || 'Unknown';
        const elfTime = data.elf_build_time || 'Unknown';

        log.warn('Build time mismatch detected!');
        writeToOutput(`  Device firmware: ${deviceTime}`, 'error');
        writeToOutput(`  ELF file: ${elfTime}`, 'error');

        alert(
          `⚠️ ${t('messages.build_time_mismatch', 'Build Time Mismatch')}!\n\n` +
            `${t('messages.build_time_mismatch_desc', 'The device firmware and ELF file have different build times.')}\n` +
            `${t('messages.build_time_mismatch_warn', 'This may cause injection to fail or behave unexpectedly.')}\n\n` +
            `${t('messages.device_firmware', 'Device firmware')}: ${deviceTime}\n` +
            `${t('messages.elf_file', 'ELF file')}: ${elfTime}\n\n` +
            `${t('messages.build_time_mismatch_hint', 'Please ensure the ELF file matches the firmware running on the device.')}`,
        );
      }

      if (data.fpb_version !== undefined) {
        state.fpbVersion = data.fpb_version;
      }

      if (data.slots) {
        data.slots.forEach((slot) => {
          const slotId = slot.id !== undefined ? slot.id : 0;
          if (slotId < 8) {
            state.slotStates[slotId] = {
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
        log.info(`Device build: ${data.device_build_time}`);
      }

      log.success('Device info updated');

      // Build device info popup message
      const infoLines = [];
      infoLines.push(
        `✅ ${t('messages.device_info_success', 'Device Info Retrieved')}`,
      );
      infoLines.push('');

      if (data.fpb_version !== undefined) {
        infoLines.push(
          `${t('messages.fpb_version', 'FPB Version')}: ${data.fpb_version}`,
        );
      }

      if (data.device_build_time) {
        infoLines.push(
          `${t('messages.build_time', 'Build Time')}: ${data.device_build_time}`,
        );
      }

      if (data.memory) {
        infoLines.push(
          `${t('messages.memory_used', 'Memory Used')}: ${data.memory.used || 0} ${t('device.bytes', 'Bytes')}`,
        );
      }

      if (data.slots) {
        const occupiedSlots = data.slots.filter((s) => s.occupied).length;
        const totalSlots = data.slots.length;
        infoLines.push(
          `${t('messages.slots_used', 'Slots Used')}: ${occupiedSlots}/${totalSlots}`,
        );

        // List occupied slots
        data.slots.forEach((slot) => {
          if (slot.occupied && slot.func) {
            infoLines.push(
              `  ${t('device.slot_n', 'Slot {{n}}', { n: slot.id })}: ${slot.func}`,
            );
          }
        });
      }

      alert(infoLines.join('\n'));
    } else {
      log.error(data.error || 'Failed to get device info');
      alert(
        `❌ ${t('messages.device_info_failed', 'Failed to Get Device Info')}\n\n` +
          `${data.error || t('messages.unknown_error', 'Unknown error')}`,
      );
    }
  } catch (e) {
    log.error(`Info failed: ${e}`);
    alert(
      `❌ ${t('messages.device_info_failed', 'Failed to Get Device Info')}\n\n` +
        `${t('messages.error', 'Error')}: ${e}`,
    );
  }
}

async function fpbInjectMulti() {
  const state = window.FPBState;
  if (!state.isConnected) {
    log.error('Not connected');
    return;
  }

  const patchSource = document.getElementById('patchSource')?.value || '';
  if (!patchSource.trim()) {
    log.error('No patch source code available');
    return;
  }

  log.info('Injecting all functions...');

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
      log.success(`Injected ${successCount}/${totalCount} functions`);
      displayAutoInjectStats(data, 'multi');
      await fpbInfo();
    } else {
      log.error(`Multi-inject failed: ${data.error || 'Unknown error'}`);
    }
  } catch (e) {
    log.error(`Multi-inject error: ${e}`);
  }
}

// Export for global access
window.fpbPing = fpbPing;
window.fpbTestSerial = fpbTestSerial;
window.fpbInfo = fpbInfo;
window.fpbInjectMulti = fpbInjectMulti;
