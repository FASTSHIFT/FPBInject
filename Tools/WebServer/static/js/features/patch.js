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
) {
  let returnType = 'void';
  let params = '';

  if (signature) {
    const parsed = parseSignature(signature, funcName);
    returnType = parsed.returnType;
    params = parsed.params;
  }

  const paramNames = extractParamNames(params);
  const hasDecompiled = !!decompiled;

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

  /* Build function body */
  let functionBody = '';
  if (hasDecompiled) {
    functionBody = `/* TODO: Your patch code here */
${decompiledSection}`;
  } else {
    functionBody = `printf("Patched ${funcName} executed!\\n");

/* TODO: Your patch code here */`;
  }

  /* Add return statement for non-void functions */
  if (returnType !== 'void') {
    functionBody += `

/* TODO: return appropriate value */
return 0;`;
  }

  /* Build complete template */
  let template = `/*
 * Patch for: ${funcName}
 * Slot: ${slot}
${sourceFile ? ` * Source: ${sourceFile}` : ''}
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
${ghidraTip}
/* FPB_INJECT */
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

  for (const part of parts) {
    const arrayMatch = part.match(/(\w+)\s*\[/);
    if (arrayMatch) {
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
      if (
        ![
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
        ].includes(lastWord)
      ) {
        names.push(lastWord);
      }
    }
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
      `⚠️ All ${totalSlots} FPB Slots are occupied!\n\n` +
        `Current slots:\n` +
        state.slotStates
          .map((s, i) => `  Slot ${i}: ${s.func || 'Empty'}`)
          .join('\n') +
        `\n\nPlease clear some slots before injecting.\n` +
        `Use "Clear All" button or click ✕ on individual slots.\n\n` +
        `Click OK to open Device Info panel.`,
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

  if (state.slotStates[state.selectedSlot].occupied) {
    const slotFunc = state.slotStates[state.selectedSlot].func;
    const overwrite = confirm(
      `⚠️ Slot ${state.selectedSlot} is already occupied by "${slotFunc}".\n\n` +
        `Do you want to overwrite it?`,
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
  progressText.textContent = 'Starting...';
  progressFill.style.width = '5%';
  progressFill.style.background = '';

  log.info(
    `Starting injection of ${targetFunc} to slot ${state.selectedSlot}...`,
  );

  try {
    const response = await fetch('/api/fpb/inject/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_content: source,
        target_func: targetFunc,
        comp: state.selectedSlot,
        patch_mode: document.getElementById('patchMode').value,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalResult = null;

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
              if (data.stage === 'compiling') {
                progressText.textContent = 'Compiling...';
                progressFill.style.width = '20%';
              }
            } else if (data.type === 'progress') {
              const uploadPercent = data.percent || 0;
              const overallPercent = 30 + uploadPercent * 0.6;
              progressText.textContent = `Uploading... ${data.uploaded}/${data.total} bytes (${uploadPercent}%)`;
              progressFill.style.width = `${overallPercent}%`;
            } else if (data.type === 'result') {
              finalResult = data;
            }
          } catch (e) {
            console.warn('Failed to parse SSE data:', e);
          }
        }
      }
    }

    if (finalResult && finalResult.success) {
      progressText.textContent = 'Complete!';
      progressFill.style.width = '100%';

      displayInjectionStats(finalResult, targetFunc);

      try {
        await fpbInfo();
      } catch (infoErr) {
        console.warn('Failed to refresh FPB info:', infoErr);
      }

      hideProgress();
    } else {
      throw new Error(finalResult?.error || 'Injection failed');
    }
  } catch (e) {
    progressText.textContent = 'Failed!';
    progressFill.style.background = '#f44336';
    log.error(`${e}`);
    hideProgress();
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
  writeToOutput(
    `Upload time:   ${uploadTime.toFixed(2)}s (${uploadSpeed} B/s)`,
    'info',
  );
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
