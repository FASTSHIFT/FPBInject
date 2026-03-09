/*========================================
  FPBInject Workbench - Inline Value Edit Module
  ========================================*/

/**
 * Encode a user-input value string to little-endian hex bytes.
 *
 * @param {string} input - User input (decimal, hex with 0x prefix, float, bool)
 * @param {string} typeName - C type name (e.g. "int32_t", "float", "uint8_t")
 * @param {number} size - Field size in bytes
 * @returns {{hex: string}|{error: string}} hex string or error
 */
function encodeValue(input, typeName, size) {
  const s = (input || '').trim();
  if (s === '') return { error: t('inline_edit.empty_value', 'Empty value') };

  const lowerType = (typeName || '').toLowerCase();

  try {
    // Bool
    if (lowerType === 'bool' || lowerType === '_bool') {
      const boolVal =
        s === 'true' || s === '1' ? 1 : s === 'false' || s === '0' ? 0 : -1;
      if (boolVal < 0)
        return { error: t('inline_edit.invalid_bool', 'Expected true/false') };
      return { hex: boolVal.toString(16).padStart(2, '0') };
    }

    // Float
    if (lowerType.includes('float') && size === 4) {
      const fval = parseFloat(s);
      if (isNaN(fval))
        return { error: t('inline_edit.invalid_float', 'Invalid float') };
      const buf = new ArrayBuffer(4);
      new DataView(buf).setFloat32(0, fval, true);
      return { hex: _bufToHex(buf) };
    }

    // Double
    if (lowerType.includes('double') && size === 8) {
      const dval = parseFloat(s);
      if (isNaN(dval))
        return { error: t('inline_edit.invalid_float', 'Invalid float') };
      const buf = new ArrayBuffer(8);
      new DataView(buf).setFloat64(0, dval, true);
      return { hex: _bufToHex(buf) };
    }

    // Pointer — accept hex address
    if (typeName && typeName.includes('*')) {
      return _encodeInteger(s, size, false);
    }

    // Integer types
    const isSigned =
      !lowerType.startsWith('u') &&
      !lowerType.includes('uint') &&
      !lowerType.includes('size_t');
    return _encodeInteger(s, size, isSigned);
  } catch (e) {
    return {
      error: t('inline_edit.encode_error', 'Encode error: {{msg}}', {
        msg: e.message,
      }),
    };
  }
}

/**
 * Encode an integer string to little-endian hex.
 */
function _encodeInteger(s, size, isSigned) {
  let val;
  if (s.startsWith('0x') || s.startsWith('0X')) {
    val = parseInt(s, 16);
  } else {
    val = parseInt(s, 10);
  }
  if (isNaN(val)) {
    return { error: t('inline_edit.invalid_number', 'Invalid number') };
  }

  // Range check
  const bits = size * 8;
  if (isSigned) {
    const min = -(2 ** (bits - 1));
    const max = 2 ** (bits - 1) - 1;
    if (val < min || val > max) {
      return {
        error: t('inline_edit.overflow', 'Overflow: {{min}} ~ {{max}}', {
          min,
          max,
        }),
      };
    }
    // Convert negative to unsigned representation
    if (val < 0) val = val + 2 ** bits;
  } else {
    const max = 2 ** bits - 1;
    if (val < 0 || val > max) {
      return {
        error: t('inline_edit.overflow', 'Overflow: 0 ~ {{max}}', { max }),
      };
    }
  }

  // To little-endian hex
  let hex = '';
  for (let i = 0; i < size; i++) {
    hex += ((val >> (i * 8)) & 0xff).toString(16).padStart(2, '0');
  }
  return { hex };
}

function _bufToHex(buf) {
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Start inline editing on a value element.
 *
 * @param {HTMLElement} valueEl - The .sym-tree-value or .watch-node-value span
 * @param {object} opts
 * @param {string} opts.type - C type name
 * @param {number} opts.size - Field size in bytes
 * @param {function} opts.onCommit - async (hexString) => Response
 * @param {function} [opts.onSuccess] - optional callback after successful write
 */
function startInlineEdit(valueEl, opts) {
  // Prevent double activation
  if (valueEl.querySelector('.inline-value-input')) return;

  const original = valueEl.textContent.trim();
  const input = document.createElement('input');
  input.className = 'inline-value-input';
  input.value = original;
  input.style.width = Math.max(valueEl.offsetWidth + 20, 60) + 'px';

  // Save original HTML for restore
  const originalHtml = valueEl.innerHTML;
  valueEl.textContent = '';
  valueEl.appendChild(input);
  input.focus();
  if (input.select) input.select();

  let committed = false;

  function cancel() {
    if (committed) return;
    valueEl.innerHTML = originalHtml;
  }

  async function commit() {
    if (committed) return;
    committed = true;

    const encoded = encodeValue(input.value.trim(), opts.type, opts.size);
    if (encoded.error) {
      valueEl.innerHTML = originalHtml;
      flashFeedback(valueEl, 'error', encoded.error);
      return;
    }

    try {
      const result = await opts.onCommit(encoded.hex);
      if (result && result.success !== false) {
        flashFeedback(valueEl, 'success');
        if (opts.onSuccess) opts.onSuccess();
      } else {
        valueEl.innerHTML = originalHtml;
        const errMsg =
          result && result.error
            ? result.error
            : t('inline_edit.write_failed', 'Write failed');
        flashFeedback(valueEl, 'error', errMsg);
      }
    } catch (e) {
      valueEl.innerHTML = originalHtml;
      flashFeedback(valueEl, 'error', e.message);
    }
  }

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      e.stopPropagation();
      commit();
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      cancel();
    }
  });

  input.addEventListener('blur', () => {
    // Small delay to allow commit via Enter to fire first
    setTimeout(() => cancel(), 50);
  });
}

/**
 * Flash visual feedback on an element.
 *
 * @param {HTMLElement} el - Target element
 * @param {'success'|'error'} type - Feedback type
 * @param {string} [message] - Optional tooltip message for errors
 */
function flashFeedback(el, type, message) {
  const cls = type === 'success' ? 'flash-write-success' : 'flash-write-error';
  el.classList.add(cls);
  if (message && type === 'error') {
    el.title = message;
    setTimeout(() => {
      el.title = '';
    }, 3000);
  }
  setTimeout(() => el.classList.remove(cls), 800);
}

// Exports
window.encodeValue = encodeValue;
window.startInlineEdit = startInlineEdit;
window.flashFeedback = flashFeedback;
window._encodeInteger = _encodeInteger;
window._bufToHex = _bufToHex;
