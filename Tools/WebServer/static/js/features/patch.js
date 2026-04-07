/*========================================
  FPBInject Workbench - Patch Operations Module
  ========================================*/

/* ===========================
   CODE FORMATTING
   =========================== */

/**
 * Format C code using js-beautify (WebKit style)
 * @param {string} code - C code to format
 * @returns {string} Formatted code
 */
function formatCCode(code) {
  if (!code) return '';

  /* Use js-beautify if available */
  if (typeof js_beautify === 'function') {
    return js_beautify(code, {
      indent_size: 4,
      indent_char: ' ',
      max_preserve_newlines: 2,
      preserve_newlines: true,
      keep_array_indentation: false,
      break_chained_methods: false,
      brace_style: 'collapse,preserve-inline',
      space_before_conditional: true,
      unescape_strings: false,
      jslint_happy: false,
      end_with_newline: true,
      wrap_line_length: 0,
      indent_empty_lines: false,
    });
  }

  /* Fallback: return as-is */
  return code;
}

/* ===========================
   PATCH TEMPLATE GENERATION
   =========================== */

/**
 * Process decompiled code from Ghidra
 * @param {string} decompiled - Raw decompiled code from Ghidra
 * @param {string[]} paramNames - Original parameter names from signature
 * @returns {string} Processed function body
 */
function processDecompiledCode(decompiled, paramNames = []) {
  if (!decompiled) return '';

  let code = decompiled;

  /* Remove header comments (lines starting with //) */
  code = code
    .split('\n')
    .filter((line) => !line.startsWith('//'))
    .join('\n')
    .trim();

  /* Replace param_N with actual parameter names from signature */
  if (paramNames && paramNames.length > 0) {
    paramNames.forEach((name, index) => {
      const paramPattern = new RegExp(`\\bparam_${index + 1}\\b`, 'g');
      code = code.replace(paramPattern, name);
    });
  }

  /* Extract function body only (content between first { and last }) */
  const funcBodyMatch = code.match(/\{([\s\S]*)\}/);
  if (funcBodyMatch) {
    return funcBodyMatch[1].trim();
  }

  return code;
}

function generatePatchTemplate(
  funcName,
  slot,
  signature = null,
  sourceFile = null,
  decompiled = null,
  ghidraNotConfigured = false,
  origAddr = null,
) {
  let returnType = 'void';
  let params = '';

  if (signature) {
    const parsed = parseSignature(signature, funcName);
    returnType = parsed.returnType;
    params = parsed.params;
  }

  const paramNames = extractParamNames(params);
  /* Ensure params have names for function definition */
  params = addParamNamesToSignature(params, paramNames);
  const hasDecompiled = !!decompiled;
  const hasOrigAddr = !!origAddr;

  let ghidraTip = '';
  if (ghidraNotConfigured) {
    ghidraTip = `
/*
 * TIP: Configure Ghidra for automatic decompilation reference:
 *   1. Download Ghidra from https://ghidra-sre.org/
 *   2. Set "Ghidra Path" in Settings panel to your Ghidra installation directory
 *   3. Enable "Enable Decompilation" checkbox
 */
`;
  }

  /* Build decompiled reference section */
  let decompiledSection = '';
  if (hasDecompiled) {
    const processedBody = processDecompiledCode(decompiled, paramNames);
    decompiledSection = `
/* ============== DECOMPILED REFERENCE ==============
 * Original function body decompiled by Ghidra.
 * This is for reference only, may not be accurate.
 * ================================================== */
#if 0
${processedBody}
#endif
`;
  }

  /* Build call-original section when origAddr is available */
  let callOrigSection = '';
  let origFuncDef = '';
  if (hasOrigAddr) {
    const argList = paramNames.join(', ');
    const macroName = `ORIG_${funcName.toUpperCase()}`;
    origFuncDef = `/* Original function pointer - call via ${macroName}() to avoid recursion */
/* NOTE: | 1 sets Thumb bit for ARM Cortex-M */
typedef ${returnType} (*${funcName}_fn_t)(${params || 'void'});
static ${funcName}_fn_t const ${macroName} = (${funcName}_fn_t)(${origAddr} | 1);

`;
    if (returnType === 'void') {
      callOrigSection = `
    /* Disable patch -> call original -> re-enable patch */
    fpb_enable_patch(FPB_PATCH_COMP_ID, false);
    ORIG_${funcName.toUpperCase()}(${argList});
    fpb_enable_patch(FPB_PATCH_COMP_ID, true);`;
    } else {
      callOrigSection = `
    /* Disable patch -> call original -> re-enable patch */
    fpb_enable_patch(FPB_PATCH_COMP_ID, false);
    ${returnType} result = ORIG_${funcName.toUpperCase()}(${argList});
    fpb_enable_patch(FPB_PATCH_COMP_ID, true);

    return result;`;
    }
  }

  /* Build function body */
  let functionBody = '';
  if (hasOrigAddr) {
    /* Generate call-original pattern */
    functionBody = `fl_println("### HOOKED: ${funcName} ###");

    /* TODO: Add your pre-call logic here */
${callOrigSection}`;
    if (hasDecompiled) {
      functionBody += `
${decompiledSection}`;
    }
  } else if (hasDecompiled) {
    functionBody = `/* TODO: Your patch code here */
${decompiledSection}`;
  } else {
    functionBody = `fl_println("Patched ${funcName} executed!");

    /* TODO: Your patch code here */`;
    /* Add return statement for non-void functions */
    if (returnType !== 'void') {
      functionBody += `

    /* TODO: return appropriate value */
    return 0;`;
    }
  }

  /* Build complete template */
  let template = `/*
 * Patch for: ${funcName}
${sourceFile ? ` * Source: ${sourceFile}\n` : ''}${hasOrigAddr ? ` * Original: ${origAddr}\n` : ''} */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
${ghidraTip}
${origFuncDef}/* FPB_INJECT */
__attribute__((section(".fpb.text"), used))
${returnType} ${funcName}(${params || 'void'})
{
${functionBody}
}
`;

  /* Format the complete template */
  return formatCCode(template);
}

function parseSignature(signature, funcName) {
  let returnType = 'void';
  let params = '';

  let sig = signature
    .replace(
      /^\s*((?:(?:static|inline|extern|const|volatile|__attribute__\s*\([^)]*\))\s+)*)/,
      '',
    )
    .trim();

  const funcPattern = new RegExp(`^(.+?)\\s+${funcName}\\s*\\((.*)\\)\\s*`);
  const match = sig.match(funcPattern);

  if (match) {
    returnType = match[1].trim() || 'void';
    params = match[2].trim();
    if (params.toLowerCase() === 'void') {
      params = '';
    }
  } else {
    const funcNameIdx = sig.indexOf(funcName);
    if (funcNameIdx > 0) {
      returnType = sig.substring(0, funcNameIdx).trim() || 'void';
      const paramsStart = sig.indexOf('(', funcNameIdx);
      const paramsEnd = sig.lastIndexOf(')');
      if (paramsStart !== -1 && paramsEnd !== -1) {
        params = sig.substring(paramsStart + 1, paramsEnd).trim();
        if (params.toLowerCase() === 'void') {
          params = '';
        }
      }
    }
  }

  return { returnType, params };
}

/**
 * Add parameter names to a signature that may only have types.
 * E.g., "uint8_t, uint8_t" -> "uint8_t arg0, uint8_t arg1"
 * @param {string} params - Parameter string (may be types only)
 * @param {string[]} paramNames - Generated parameter names
 * @returns {string} Parameters with names
 */
function addParamNamesToSignature(params, paramNames) {
  if (!params || params.trim() === '' || params.toLowerCase() === 'void') {
    return params;
  }

  const parts = [];
  let depth = 0;
  let current = '';

  for (const ch of params) {
    if (ch === '(') depth++;
    else if (ch === ')') depth--;
    else if (ch === ',' && depth === 0) {
      parts.push(current.trim());
      current = '';
      continue;
    }
    current += ch;
  }
  if (current.trim()) {
    parts.push(current.trim());
  }

  const result = parts.map((part, i) => {
    const name = paramNames[i] || `arg${i}`;
    /* Check if part already has a name (not just a type) */
    const words = part.replace(/[*&]/g, ' ').trim().split(/\s+/);
    const lastWord = words[words.length - 1];

    /* If last word is a type keyword or stdint type, add name */
    const typeKeywords = [
      'int',
      'char',
      'void',
      'float',
      'double',
      'long',
      'short',
      'unsigned',
      'signed',
      'const',
      'volatile',
      'struct',
      'enum',
      'union',
      'bool',
      'size_t',
      'ssize_t',
      'ptrdiff_t',
      'intptr_t',
      'uintptr_t',
    ];
    const isType =
      typeKeywords.includes(lastWord) ||
      /^u?int\d+_t$/.test(lastWord) ||
      (/_t$/.test(lastWord) && lastWord.length > 2);

    if (isType) {
      return `${part} ${name}`;
    }
    return part;
  });

  return result.join(', ');
}

function extractParamNames(params) {
  if (!params || params.trim() === '' || params.toLowerCase() === 'void') {
    return [];
  }

  const names = [];
  const parts = [];
  let depth = 0;
  let current = '';

  for (const ch of params) {
    if (ch === '(') depth++;
    else if (ch === ')') depth--;
    else if (ch === ',' && depth === 0) {
      parts.push(current.trim());
      current = '';
      continue;
    }
    current += ch;
  }
  if (current.trim()) {
    parts.push(current.trim());
  }

  /* Common C type keywords and patterns */
  const typeKeywords = [
    'int',
    'char',
    'void',
    'float',
    'double',
    'long',
    'short',
    'unsigned',
    'signed',
    'const',
    'volatile',
    'struct',
    'enum',
    'union',
    'bool',
    'size_t',
    'ssize_t',
    'ptrdiff_t',
    'intptr_t',
    'uintptr_t',
  ];

  /* Check if a word looks like a type name */
  const isTypeName = (word) => {
    if (typeKeywords.includes(word)) return true;
    /* Match stdint types: uint8_t, int32_t, etc. */
    if (/^u?int\d+_t$/.test(word)) return true;
    /* Match _t suffix types (common convention) */
    if (/_t$/.test(word) && word.length > 2) return true;
    return false;
  };

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];

    const arrayMatch = part.match(/(\w+)\s*\[/);
    if (arrayMatch && !isTypeName(arrayMatch[1])) {
      names.push(arrayMatch[1]);
      continue;
    }

    const funcPtrMatch = part.match(/\(\s*\*\s*(\w+)\s*\)/);
    if (funcPtrMatch) {
      names.push(funcPtrMatch[1]);
      continue;
    }

    const words = part.replace(/[*&]/g, ' ').trim().split(/\s+/);
    if (words.length > 0) {
      const lastWord = words[words.length - 1];
      if (!isTypeName(lastWord)) {
        names.push(lastWord);
        continue;
      }
    }

    /* No valid name found - generate synthetic name */
    names.push(`arg${i}`);
  }

  return names;
}

/* ===========================
   INJECT OPERATIONS
   =========================== */
async function performInject() {
  const state = window.FPBState;
  if (!state.isConnected) {
    log.error('Not connected');
    return;
  }

  const occupiedSlots = state.slotStates.filter((s) => s.occupied).length;
  const totalSlots = state.slotStates.length;

  if (occupiedSlots >= totalSlots) {
    const shouldContinue = confirm(
      `⚠️ ${t('messages.all_slots_occupied', 'All {{count}} FPB Slots are occupied!', { count: totalSlots })}\n\n` +
        `${t('messages.current_slots', 'Current slots')}:\n` +
        state.slotStates
          .map(
            (s, i) =>
              `  ${t('device.slot_n', 'Slot {{n}}', { n: i })}: ${s.func || t('panels.slot_empty', 'Empty')}`,
          )
          .join('\n') +
        `\n\n${t('messages.clear_slots_before_inject', 'Please clear some slots before injecting.')}\n` +
        `${t('messages.use_clear_all_hint', 'Use "Clear All" button or click ✕ on individual slots.')}\n\n` +
        t(
          'messages.click_ok_to_open_device',
          'Click OK to open Device Info panel.',
        ),
    );

    if (shouldContinue) {
      const deviceDetails = document.getElementById('details-device');
      if (deviceDetails) {
        deviceDetails.open = true;
      }
    }

    writeToOutput(
      `[ERROR] All ${totalSlots} slots are occupied. Clear some slots before injecting.`,
      'error',
    );
    return;
  }

  if (
    state.selectedSlot >= 0 &&
    state.slotStates[state.selectedSlot].occupied
  ) {
    const slotFunc = state.slotStates[state.selectedSlot].func;
    const overwrite = confirm(
      `⚠️ ${t('messages.slot_occupied_by', 'Slot {{slot}} is already occupied by "{{func}}".', { slot: state.selectedSlot, func: slotFunc })}\n\n` +
        t('messages.overwrite_slot', 'Do you want to overwrite it?'),
    );

    if (!overwrite) {
      writeToOutput(
        `[INFO] Injection cancelled - slot ${state.selectedSlot} is occupied`,
        'info',
      );
      return;
    }
  }

  if (!state.currentPatchTab || !state.currentPatchTab.funcName) {
    log.error('No patch tab selected');
    return;
  }

  const tabId = state.currentPatchTab.id;
  const targetFunc = state.currentPatchTab.funcName;

  const source = getAceEditorContent(tabId);
  if (!source) {
    log.error('Editor not found');
    return;
  }

  if (!source.trim()) {
    log.error('No patch source code');
    return;
  }

  const progressEl = document.getElementById('injectProgress');
  const progressText = document.getElementById('injectProgressText');
  const progressFill = document.getElementById('injectProgressFill');

  /* Helper to hide progress bar */
  const hideProgress = (delay = 2000) => {
    setTimeout(() => {
      progressEl.style.display = 'none';
      progressFill.style.width = '0%';
      progressFill.style.background = '';
    }, delay);
  };

  progressEl.style.display = 'flex';
  progressText.textContent = t('statusbar.starting');
  progressFill.style.width = '5%';
  progressFill.style.background = '';

  // Show cancel button
  const cancelBtn = document.getElementById('injectCancelBtn');
  if (cancelBtn) cancelBtn.style.display = 'inline-block';
  window._injectAbortController = new AbortController();

  log.info(
    `Starting injection of ${targetFunc} to slot ${state.selectedSlot}...`,
  );

  try {
    const finalResult = await consumeSSEStream(
      '/api/fpb/inject/stream',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_content: source,
          target_func: targetFunc,
          comp: state.selectedSlot,
          patch_mode: document.getElementById('patchMode').value,
        }),
      },
      {
        onStatus(data) {
          if (data.stage === 'compiling') {
            progressText.textContent = t('statusbar.compiling');
            progressFill.style.width = '20%';
          }
        },
        onProgress(data) {
          const uploadPercent = data.percent || 0;
          const overallPercent = 30 + uploadPercent * 0.6;
          const speedStr =
            data.speed > 0 ? `  ${window._formatInjectSpeed(data.speed)}` : '';
          const etaStr = data.eta > 0 ? `  ETA ${data.eta.toFixed(1)}s` : '';
          progressText.textContent = `${uploadPercent.toFixed(0)}%${speedStr}${etaStr}`;
          progressFill.style.width = `${overallPercent}%`;
        },
      },
      window._injectAbortController,
    );

    if (finalResult && finalResult.success) {
      progressText.textContent = t('statusbar.complete', 'Complete!');
      progressFill.style.width = '100%';

      displayInjectionStats(finalResult, targetFunc);

      try {
        await fpbInfo();
      } catch (infoErr) {
        console.warn('Failed to refresh FPB info:', infoErr);
      }

      hideProgress();
    } else if (finalResult && finalResult.cancelled) {
      progressText.textContent = t('statusbar.cancelled', 'Cancelled');
      progressFill.style.background = '#ff9800';
      log.warn('Injection cancelled');
      hideProgress(2000);
    } else {
      throw new Error(finalResult?.error || 'Injection failed');
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      await fetch('/api/fpb/inject/cancel', { method: 'POST' }).catch(() => {});
      progressText.textContent = t('statusbar.cancelled', 'Cancelled');
      progressFill.style.background = '#ff9800';
      log.warn('Injection cancelled');
      hideProgress(2000);
    } else {
      progressText.textContent = t('statusbar.failed', 'Failed!');
      progressFill.style.background = '#f44336';
      log.error(`${e}`);
      hideProgress();
    }
  } finally {
    window._injectAbortController = null;
    if (cancelBtn) cancelBtn.style.display = 'none';
  }
}

function displayInjectionStats(data, targetFunc) {
  const compileTime = data.compile_time || 0;
  const uploadTime = data.upload_time || 0;
  const codeSize = data.code_size || 0;
  const totalTime = data.total_time || compileTime + uploadTime;
  const uploadSpeed = uploadTime > 0 ? Math.round(codeSize / uploadTime) : 0;
  const patchMode =
    data.patch_mode || document.getElementById('patchMode').value;

  log.success('Injection complete!');
  writeToOutput(`--- Injection Statistics ---`, 'system');
  writeToOutput(
    `Target:        ${targetFunc} @ ${data.target_addr || 'unknown'}`,
    'info',
  );
  writeToOutput(
    `Inject func:   ${data.inject_func || 'unknown'} @ ${data.inject_addr || 'unknown'}`,
    'info',
  );
  writeToOutput(`Compile time:  ${compileTime.toFixed(2)}s`, 'info');
  const allocTime = data.alloc_time || 0;
  if (allocTime > 0) {
    writeToOutput(`Alloc time:    ${allocTime.toFixed(2)}s`, 'info');
  }
  writeToOutput(
    `Upload time:   ${uploadTime.toFixed(2)}s (${typeof window._formatInjectSpeed === 'function' ? window._formatInjectSpeed(uploadSpeed) : uploadSpeed + ' B/s'})`,
    'info',
  );
  const patchTime = data.patch_time || 0;
  if (patchTime > 0) {
    writeToOutput(`Patch time:    ${patchTime.toFixed(2)}s`, 'info');
  }
  const overheadTime = data.overhead_time || 0;
  if (overheadTime > 0) {
    writeToOutput(`Overhead:      ${overheadTime.toFixed(2)}s`, 'info');
  }
  writeToOutput(`Code size:     ${codeSize} bytes`, 'info');
  writeToOutput(`Total time:    ${totalTime.toFixed(2)}s`, 'info');
  writeToOutput(`Injection active! (mode: ${patchMode})`, 'success');
}

/* Export for global access */
window.formatCCode = formatCCode;
window.processDecompiledCode = processDecompiledCode;
window.generatePatchTemplate = generatePatchTemplate;
window.parseSignature = parseSignature;
window.extractParamNames = extractParamNames;
window.performInject = performInject;
window.displayInjectionStats = displayInjectionStats;
