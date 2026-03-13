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

  log.info('Starting 3-phase serial throughput test...');

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
      state.throughputTested = true;
      writeToOutput('─'.repeat(50), 'info');

      /* Phase 1: Fragment probe */
      const fragNeeded = data.fragment_needed;
      log.info(
        `Phase 1 - TX Fragment: ${fragNeeded ? 'needed' : 'not needed'}`,
      );

      /* Phase 2: Upload probe */
      log.info('Phase 2 - Upload Chunk Probe:');
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

      /* Phase 3: Download probe */
      const dlPhase = data.phases?.download;
      if (dlPhase && !dlPhase.skipped) {
        log.info('Phase 3 - Download Chunk Probe:');
        if (dlPhase.tests && dlPhase.tests.length > 0) {
          dlPhase.tests.forEach((test) => {
            const status = test.passed ? '✓' : '✗';
            const timeStr = test.response_time_ms
              ? ` (${test.response_time_ms}ms)`
              : '';
            const errStr = test.error ? ` - ${test.error}` : '';
            writeToOutput(
              `  ${status} ${test.size} bytes${timeStr}${errStr}`,
              test.passed ? 'success' : 'error',
            );
          });
        }
      } else if (dlPhase?.skipped) {
        log.warn(`Phase 3 skipped: ${dlPhase.skip_reason || 'unknown'}`);
      }

      writeToOutput('─'.repeat(50), 'info');

      if (data.max_working_size !== undefined) {
        log.info(`Max working size: ${data.max_working_size} bytes`);
      }
      if (data.failed_size) {
        log.warn(`Failed at size: ${data.failed_size} bytes`);
      }

      const recUpload = data.recommended_upload_chunk_size;
      const recDownload = data.recommended_download_chunk_size;
      log.success(`Recommended upload chunk: ${recUpload} bytes`);
      log.success(`Recommended download chunk: ${recDownload} bytes`);

      const apply = confirm(
        `✅ ${t('messages.serial_test_complete', 'Test Complete')}\n\n` +
          `Upload: ${recUpload}B, Download: ${recDownload}B\n\n` +
          t('messages.apply_recommended_size', 'Apply recommended parameters?'),
      );

      if (apply) {
        /* Apply both upload and download chunk sizes */
        const uploadInput = document.getElementById('uploadChunkSize');
        const downloadInput = document.getElementById('downloadChunkSize');
        if (uploadInput) uploadInput.value = recUpload;
        if (downloadInput) downloadInput.value = recDownload;
        await saveConfig(true);
        log.success(
          `Parameters applied: upload=${recUpload}B, download=${recDownload}B`,
        );
      } else {
        log.info('Parameters unchanged');
      }
    } else {
      log.error(`Test failed: ${data.error || 'Unknown error'}`);
    }
  } catch (e) {
    log.error(`Serial test failed: ${e}`);
  }
}

async function fpbInfo(showPopup = false) {
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
        // FPB v2 only supports DebugMonitor mode
        const patchModeSelect = document.getElementById('patchMode');
        if (patchModeSelect) {
          if (data.fpb_version >= 2) {
            patchModeSelect.value = 'debugmon';
            Array.from(patchModeSelect.options).forEach((opt) => {
              opt.disabled = opt.value !== 'debugmon';
            });
            log.info('FPB v2: DebugMonitor mode enforced');
          } else {
            Array.from(patchModeSelect.options).forEach((opt) => {
              opt.disabled = false;
            });
          }
        }
      }

      if (data.slots) {
        data.slots.forEach((slot) => {
          const slotId = slot.id !== undefined ? slot.id : 0;
          if (slotId < 8) {
            state.slotStates[slotId] = {
              occupied: slot.occupied || false,
              enabled: slot.enabled !== undefined ? slot.enabled : true,
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

      // Only show success popup when manually triggered
      if (showPopup) {
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
      }
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

  // Reuse global inject progress bar
  const progressEl = document.getElementById('injectProgress');
  const progressText = document.getElementById('injectProgressText');
  const progressFill = document.getElementById('injectProgressFill');
  const hideProgress = (delay = 2000) => {
    setTimeout(() => {
      if (progressEl) progressEl.style.display = 'none';
      if (progressFill) {
        progressFill.style.width = '0%';
        progressFill.style.background = '';
      }
    }, delay);
  };

  if (progressEl) progressEl.style.display = 'flex';
  if (progressText)
    progressText.textContent = t('statusbar.starting', 'Starting...');
  if (progressFill) {
    progressFill.style.width = '5%';
    progressFill.style.background = '';
  }

  try {
    const patchMode =
      document.getElementById('patchMode')?.value || 'trampoline';

    let totalFuncs = 1;
    let currentIndex = 0;

    const data = await consumeSSEStream(
      '/api/fpb/inject/multi/stream',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_content: patchSource,
          patch_mode: patchMode,
        }),
      },
      {
        onStatus(ev) {
          if (ev.stage === 'compiling') {
            if (progressText)
              progressText.textContent = t(
                'statusbar.compiling',
                'Compiling...',
              );
            if (progressFill) progressFill.style.width = '10%';
          } else if (ev.stage === 'injecting') {
            totalFuncs = ev.total || 1;
            currentIndex = ev.index || 0;
            const basePercent = 15 + (currentIndex / totalFuncs) * 80;
            if (progressText)
              progressText.textContent = t(
                'statusbar.injecting_func',
                `Injecting ${ev.name} (${currentIndex + 1}/${totalFuncs})...`,
                { name: ev.name, current: currentIndex + 1, total: totalFuncs },
              );
            if (progressFill) progressFill.style.width = `${basePercent}%`;
          }
        },
        onProgress(ev) {
          // Per-chunk upload progress within current function
          const funcWeight = 80 / totalFuncs;
          const funcBase = 15 + currentIndex * funcWeight;
          const uploadPercent = ev.percent || 0;
          const overall = funcBase + (uploadPercent / 100) * funcWeight;
          if (progressFill) progressFill.style.width = `${overall}%`;
          if (progressText) {
            progressText.textContent = t(
              'statusbar.uploading_func',
              `Uploading (${currentIndex + 1}/${totalFuncs}) ${uploadPercent.toFixed(0)}%`,
              {
                current: currentIndex + 1,
                total: totalFuncs,
                percent: uploadPercent.toFixed(0),
              },
            );
          }
        },
      },
    );

    if (data && data.success) {
      const successCount = data.successful_count || 0;
      const totalCount = data.total_count || 0;
      log.success(`Injected ${successCount}/${totalCount} functions`);
      if (progressText)
        progressText.textContent = t('statusbar.complete', 'Complete!');
      if (progressFill) progressFill.style.width = '100%';
      displayAutoInjectStats(data, 'multi');
      await fpbInfo();
      hideProgress();
    } else {
      log.error(`Multi-inject failed: ${data?.error || 'Unknown error'}`);
      if (progressFill) progressFill.style.background = '#f44336';
      if (progressText) progressText.textContent = data?.error || 'Failed';
      hideProgress(3000);
    }
  } catch (e) {
    log.error(`Multi-inject error: ${e}`);
    if (progressFill) progressFill.style.background = '#f44336';
    hideProgress(3000);
  }
}

// Export for global access
window.fpbPing = fpbPing;
window.fpbTestSerial = fpbTestSerial;
window.fpbInfo = fpbInfo;
window.fpbInjectMulti = fpbInjectMulti;
