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
        max_size: 512,
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
          const trialStr =
            test.trials !== undefined ? ` {${test.passes}/${test.trials}}` : '';
          const errStr = test.error ? ` - ${test.error}` : '';
          writeToOutput(
            `  ${status} ${test.size} bytes${cmdLen}${trialStr}${timeStr}${errStr}`,
            test.passed ? 'success' : 'error',
          );
        });
      }

      /* Phase 1.5: Fragment size probe results */
      const fragProbe = data.phases?.fragment_probe;
      if (fragProbe) {
        log.info('Phase 1.5 - TX Fragment Probe:');
        if (fragProbe.tests) {
          fragProbe.tests.forEach((test) => {
            const status = test.passed ? '✓' : '✗';
            if (test.phase === 'size') {
              writeToOutput(
                `  ${status} fragment_size=${test.fragment_size}B`,
                test.passed ? 'success' : 'error',
              );
            } else if (test.phase === 'delay') {
              writeToOutput(
                `  ${status} fragment_delay=${test.fragment_delay * 1000}ms`,
                test.passed ? 'success' : 'error',
              );
            }
          });
        }
        if (fragProbe.success) {
          log.success(
            `Recommended TX fragment: ${fragProbe.recommended_fragment_size}B, delay=${fragProbe.recommended_fragment_delay * 1000}ms`,
          );
        }
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
            const trialStr =
              test.trials !== undefined
                ? ` {${test.passes}/${test.trials}}`
                : '';
            const errStr = test.error ? ` - ${test.error}` : '';
            writeToOutput(
              `  ${status} ${test.size} bytes${trialStr}${timeStr}${errStr}`,
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
      const recFragSize = data.recommended_fragment_size || 0;
      const recFragDelay = data.recommended_fragment_delay || 0;
      log.success(`Recommended upload chunk: ${recUpload} bytes`);
      log.success(`Recommended download chunk: ${recDownload} bytes`);

      let confirmMsg =
        `✅ ${t('messages.serial_test_complete', 'Test Complete')}\n\n` +
        `Upload: ${recUpload}B, Download: ${recDownload}B`;
      if (recFragSize > 0) {
        confirmMsg += `\nTX Fragment: ${recFragSize}B, Delay: ${recFragDelay * 1000}ms`;
        confirmMsg +=
          `\n\n⚠️ ` +
          t(
            'messages.fragment_detected_hint',
            'Serial TX data loss detected (PC → Device). To maintain reliability, transmissions will be split into {{size}}B segments with {{delay}}ms intervals. Consider optimizing the UART driver for better throughput.',
            { size: recFragSize, delay: recFragDelay * 1000 },
          );
      }
      confirmMsg +=
        `\n\n` +
        t('messages.apply_recommended_size', 'Apply recommended parameters?');

      const apply = confirm(confirmMsg);

      if (apply) {
        /* Apply upload and download chunk sizes */
        const uploadInput = document.getElementById('uploadChunkSize');
        const downloadInput = document.getElementById('downloadChunkSize');
        if (uploadInput) uploadInput.value = recUpload;
        if (downloadInput) downloadInput.value = recDownload;

        /* Apply TX fragment params: set probed values or reset to 0 */
        const fragInput = document.getElementById('serialTxFragmentSize');
        const delayInput = document.getElementById('serialTxFragmentDelay');
        if (recFragSize > 0) {
          if (fragInput) fragInput.value = recFragSize;
          if (delayInput) delayInput.value = recFragDelay * 1000; // display as ms
        } else {
          if (fragInput) fragInput.value = 0;
          if (delayInput) delayInput.value = 2; // default 2ms
        }

        await saveConfig(true);
        let msg = `Parameters applied: upload=${recUpload}B, download=${recDownload}B`;
        if (recFragSize > 0) {
          msg += `, TX fragment=${recFragSize}B, delay=${recFragDelay * 1000}ms`;
        }
        log.success(msg);
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

      if (data.version_mismatch) {
        const devVer = data.device_version || '?';
        const hostVer = data.host_version || '?';

        log.warn(`Version mismatch: device ${devVer}, host ${hostVer}`);

        alert(
          `⚠️ ${t('messages.version_mismatch', 'Version Mismatch')}!\n\n` +
            `${t('messages.version_mismatch_desc', 'The device firmware and host tool have different versions. There may be compatibility issues.')}\n\n` +
            `${t('messages.device_firmware', 'Device firmware')}: v${devVer}\n` +
            `${t('messages.host_tool', 'Host tool')}: v${hostVer}`,
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
        const info = data.info || {};
        const infoLines = [];
        infoLines.push(
          `✅ ${t('messages.device_info_success', 'Device Info Retrieved')}`,
        );
        infoLines.push('');

        if (info.version_string) {
          infoLines.push(
            `${t('messages.firmware_version', 'Firmware')}: ${info.version_string}`,
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
        }

        if (info.file_transfer) {
          infoLines.push(
            `${t('messages.file_transfer', 'File Transfer')}: ${info.file_transfer}`,
          );
        }

        if (info.fpb_detail) {
          infoLines.push(
            `${t('messages.fpb_detail', 'FPB')}: ${info.fpb_detail}`,
          );
        }

        if (data.slots) {
          // List occupied slots
          const occupiedList = data.slots.filter((s) => s.occupied && s.func);
          if (occupiedList.length > 0) {
            infoLines.push('');
            occupiedList.forEach((slot) => {
              infoLines.push(
                `  ${t('device.slot_n', 'Slot {{n}}', { n: slot.id })}: ${slot.func}`,
              );
            });
          }
        }

        alert(infoLines.join('\n'));
      }
    } else {
      const errorMsg =
        data.error || t('messages.unknown_error', 'Unknown error');
      log.error(errorMsg);

      // Build diagnostic hint based on error content
      let hint = '';
      if (errorMsg.toLowerCase().includes('not responding')) {
        hint = `\n\n${t('messages.diag_device_no_response_hint', 'Check if the correct device is connected and the baud rate matches the firmware.')}`;
      }

      alert(
        `${t('messages.device_info_failed', 'Failed to Get Device Info')}\n\n` +
          `${errorMsg}${hint}`,
      );
    }
  } catch (e) {
    log.error(`Info failed: ${e}`);
    alert(
      `${t('messages.device_info_failed', 'Failed to Get Device Info')}\n\n` +
        `${t('messages.error', 'Error')}: ${e}`,
    );
  }
}

/* ===========================
   INJECT CANCEL SUPPORT
   =========================== */

function cancelInject() {
  // Always send cancel to backend (works for auto-inject, manual, and multi)
  fetch('/api/fpb/inject/cancel', { method: 'POST' }).catch(() => {});
  // Also abort SSE stream if active (manual/multi inject)
  if (window._injectAbortController) {
    window._injectAbortController.abort();
  }
}

/**
 * Format speed in human-readable form (B/s, KB/s)
 * Reuses formatSpeed from transfer.js if available, otherwise inline.
 */
function _formatInjectSpeed(bytesPerSec) {
  if (typeof formatSpeed === 'function') return formatSpeed(bytesPerSec);
  if (bytesPerSec >= 1024) return `${(bytesPerSec / 1024).toFixed(1)} KB/s`;
  return `${Math.round(bytesPerSec)} B/s`;
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

  // Show cancel button
  const cancelBtn = document.getElementById('injectCancelBtn');
  if (cancelBtn) cancelBtn.style.display = 'inline-block';
  window._injectAbortController = new AbortController();

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
            const speedStr =
              ev.speed > 0 ? `  ${_formatInjectSpeed(ev.speed)}` : '';
            const etaStr = ev.eta > 0 ? `  ETA ${ev.eta.toFixed(1)}s` : '';
            progressText.textContent = `(${currentIndex + 1}/${totalFuncs}) ${uploadPercent.toFixed(0)}%${speedStr}${etaStr}`;
          }
        },
      },
      window._injectAbortController,
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
    } else if (data && data.cancelled) {
      log.warn('Injection cancelled');
      if (progressFill) progressFill.style.background = '#ff9800';
      if (progressText)
        progressText.textContent = t('statusbar.cancelled', 'Cancelled');
      hideProgress(2000);
    } else {
      log.error(`Multi-inject failed: ${data?.error || 'Unknown error'}`);
      if (progressFill) progressFill.style.background = '#f44336';
      if (progressText) progressText.textContent = data?.error || 'Failed';
      hideProgress(3000);
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      log.warn('Injection cancelled');
      if (progressFill) progressFill.style.background = '#ff9800';
      if (progressText)
        progressText.textContent = t('statusbar.cancelled', 'Cancelled');
      hideProgress(2000);
    } else {
      log.error(`Multi-inject error: ${e}`);
      if (progressFill) progressFill.style.background = '#f44336';
      hideProgress(3000);
    }
  } finally {
    window._injectAbortController = null;
    if (cancelBtn) cancelBtn.style.display = 'none';
  }
}

// Export for global access
window.fpbPing = fpbPing;
window.fpbTestSerial = fpbTestSerial;
window.fpbInfo = fpbInfo;
window.fpbInjectMulti = fpbInjectMulti;
window.cancelInject = cancelInject;
window._formatInjectSpeed = _formatInjectSpeed;
window._injectAbortController = null;
