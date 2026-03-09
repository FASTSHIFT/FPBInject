/*========================================
  FPBInject Workbench - Symbol Search Module
  ========================================*/

/* ===========================
   SYMBOL CLICK DEBOUNCE
   =========================== */

// Prevent single-click (disassembly) from firing on double-click (patch).
// Single-click is delayed 250ms; double-click cancels it.
let _symbolClickTimer = null;

/* ===========================
   AUTO-READ TIMER
   =========================== */
const _autoReadTimers = new Map();

/* ===========================
   CACHED TAB DATA (for language re-render)
   =========================== */
const _symTabDataCache = new Map();

/* ===========================
   DEREF STATE PERSISTENCE
   =========================== */
const _symDerefState = new Map();

/* ===========================
   SYMBOL TYPE HELPERS
   =========================== */
const SYMBOL_TYPE_CONFIG = {
  function: {
    icon: 'codicon-symbol-method',
    color: '',
  },
  variable: {
    icon: 'codicon-symbol-variable',
    color: 'var(--vscode-symbolIcon-variableForeground, #75beff)',
  },
  const: {
    icon: 'codicon-symbol-constant',
    color: 'var(--vscode-symbolIcon-constantForeground, #4fc1ff)',
  },
  other: {
    icon: 'codicon-symbol-misc',
    color: '',
  },
};

function _getSymbolTypeConfig(type) {
  return SYMBOL_TYPE_CONFIG[type] || SYMBOL_TYPE_CONFIG.other;
}

function onSymbolClick(name, addr, type) {
  clearTimeout(_symbolClickTimer);
  _symbolClickTimer = setTimeout(() => {
    if (type === 'const' || type === 'variable') {
      openSymbolValueTab(name, type);
    } else {
      openDisassembly(name, addr);
    }
  }, 250);
}

function onSymbolDblClick(name, type) {
  clearTimeout(_symbolClickTimer);
  if (type === 'function') {
    openManualPatchTab(name);
  } else {
    // For const/variable, double-click same as single-click
    openSymbolValueTab(name, type);
  }
}

/* ===========================
   SYMBOL VALUE TAB
   =========================== */
async function openSymbolValueTab(symName, symType) {
  const state = window.FPBState;
  const tabId = `symval_${symName}`;

  if (state.editorTabs.find((t) => t.id === tabId)) {
    switchEditorTab(tabId);
    return;
  }

  log.debug(`Loading value for ${symName}...`);

  const isConst = symType === 'const';
  const tabTitle = `${symName} [${isConst ? 'const' : 'var'}]`;
  const tabIcon = isConst
    ? 'codicon-symbol-constant'
    : 'codicon-symbol-variable';
  const tabColor = isConst ? '#4fc1ff' : '#75beff';

  // Create tab immediately with loading placeholder
  state.editorTabs.push({
    id: tabId,
    title: tabTitle,
    type: isConst ? 'const-viewer' : 'var-viewer',
    closable: true,
    symName: symName,
    symType: symType,
  });

  const tabsHeader = document.getElementById('editorTabsHeader');
  const tabDiv = document.createElement('div');
  tabDiv.className = 'tab';
  tabDiv.setAttribute('data-tab', tabId);
  tabDiv.innerHTML = `
    <i class="codicon ${tabIcon} tab-icon" style="color: ${tabColor};"></i>
    <span>${tabTitle}</span>
    <div class="tab-close" onclick="closeTab('${tabId}', event)"><i class="codicon codicon-close"></i></div>
  `;
  tabDiv.onclick = () => switchEditorTab(tabId);
  tabDiv.onmousedown = (e) => {
    if (e.button === 1) {
      e.preventDefault();
      closeTab(tabId, e);
    }
  };
  tabsHeader.appendChild(tabDiv);

  const tabsContent = document.querySelector('.editor-tabs-content');
  const contentDiv = document.createElement('div');
  contentDiv.className = 'tab-content';
  contentDiv.id = `tabContent_${tabId}`;
  contentDiv.innerHTML = `<div class="sym-loading-container">
    <div class="sym-loading-spinner"></div>
    <div class="sym-loading-text">${t('symbols.loading_symbol', 'Loading {{name}}...', { name: symName })}</div>
  </div>`;
  tabsContent.appendChild(contentDiv);

  switchEditorTab(tabId);

  try {
    const res = await fetch(
      `/api/symbols/value?name=${encodeURIComponent(symName)}`,
    );
    const data = await res.json();

    if (!data.success) {
      log.error(`Failed to load symbol value: ${data.error}`);
      contentDiv.innerHTML = `<div class="sym-loading-container">
        <i class="codicon codicon-error" style="font-size: 2rem; color: var(--vscode-errorForeground, #f44336); margin-bottom: 12px;"></i>
        <div class="sym-loading-text">${_escapeHtml(data.error)}</div>
      </div>`;
      return;
    }

    contentDiv.innerHTML = _renderSymbolValueContent(data, isConst);

    // Cache data for language re-render
    _symTabDataCache.set(symName, { data, isConst });

    log.success(
      `Opened ${isConst ? 'const' : 'variable'} viewer for ${symName}`,
    );
  } catch (e) {
    log.error(`Failed to load symbol value: ${e}`);
    contentDiv.innerHTML = `<div class="sym-loading-container">
      <i class="codicon codicon-error" style="font-size: 2rem; color: var(--vscode-errorForeground, #f44336); margin-bottom: 12px;"></i>
      <div class="sym-loading-text">${_escapeHtml(e.message)}</div>
    </div>`;
  }
}

function _renderSymbolValueContent(data, isConst) {
  const sectionLabel = isConst
    ? t('symbols.read_only', 'Read-Only')
    : t('symbols.read_write', 'Read-Write');
  const isBss = data.section && data.section.startsWith('.bss');

  // For pointer types, show the pointer type in the header
  const typeDisplay = data.is_pointer
    ? `${_escapeHtml(data.pointer_target || '?')} *`
    : '';

  let headerHtml = `
    <div class="sym-viewer-header">
      <div class="sym-viewer-title">
        <i class="codicon ${isConst ? 'codicon-lock' : data.is_pointer ? 'codicon-references' : 'codicon-symbol-variable'} sym-viewer-icon"></i>
        <strong>${_escapeHtml(data.name)}</strong>
        ${typeDisplay ? `<span class="sym-viewer-type-badge">${typeDisplay}</span>` : ''}
      </div>
      <div class="sym-viewer-meta">
        ${t('symbols.address', 'Address')}: ${data.addr} &nbsp;
        ${t('symbols.size', 'Size')}: ${data.size} ${t('symbols.bytes', 'bytes')} &nbsp;
        ${t('symbols.section', 'Section')}: ${_escapeHtml(data.section)} (${sectionLabel})
      </div>
    </div>
  `;

  let toolbarHtml = '';
  if (!isConst) {
    const escapedName = _escapeHtml(data.name);
    const derefChecked =
      _symDerefState.get(data.name) || data.deref_data ? 'checked' : '';
    const derefCheckbox = data.is_pointer
      ? `<label class="sym-deref-toggle">
          <input type="checkbox" id="symDerefToggle_${escapedName}" ${derefChecked}
            onchange="_onDerefToggle('${escapedName}', this.checked)" />
          <i class="codicon codicon-type-hierarchy-sub"></i>
          ${t('symbols.deref_pointer', 'Dereference')}
        </label>`
      : '';
    toolbarHtml = `
      <div class="sym-viewer-toolbar">
        <button class="vscode-btn" onclick="readSymbolFromDevice('${escapedName}')">
          <i class="codicon codicon-refresh"></i> ${t('symbols.read_from_device', 'Read from Device')}
        </button>
        <button class="vscode-btn secondary" onclick="writeSymbolToDevice('${escapedName}')">
          <i class="codicon codicon-cloud-upload"></i> ${t('symbols.write_to_device', 'Write to Device')}
        </button>
        <button class="vscode-btn secondary" onclick="saveSymbolData('${escapedName}')">
          <i class="codicon codicon-save"></i> ${t('symbols.save_to_file', 'Save')}
        </button>
        ${derefCheckbox}
        <div class="sym-auto-read">
          <button class="vscode-btn secondary sym-auto-read-toggle" id="symAutoReadBtn_${escapedName}"
            onclick="toggleAutoRead('${escapedName}')"
            title="${t('symbols.auto_read_hint', 'Toggle periodic auto-read')}">
            <i class="codicon codicon-sync"></i> ${t('symbols.auto_read', 'Auto')}
          </button>
          <input type="number" class="vscode-input sym-auto-read-interval"
            id="symAutoReadInterval_${escapedName}"
            value="1000" min="100" step="100"
            title="${t('symbols.auto_read_interval_hint', 'Auto-read interval (ms)')}" />
          <span class="sym-auto-read-unit">ms</span>
        </div>
        <span class="sym-viewer-status" id="symStatus_${escapedName}"></span>
      </div>
    `;
  }

  let bodyHtml = '';

  // For pointer types, show the pointer value prominently
  if (data.is_pointer && data.hex_data) {
    const ptrValue = _decodeLittleEndianHex(data.hex_data, data.size);
    bodyHtml += `<div class="sym-pointer-value">
      <span class="sym-pointer-label">${t('symbols.pointer_value', 'Points to')}:</span>
      <code class="sym-pointer-addr">${ptrValue}</code>
      ${ptrValue === '0x00000000' ? `<span class="sym-pointer-null">NULL</span>` : ''}
    </div>`;
  }

  // Struct tree view (for non-pointer structs, or for deref data)
  if (data.struct_layout && data.struct_layout.length > 0) {
    bodyHtml += _renderStructTree(
      data.struct_layout,
      data.hex_data,
      isBss,
      data.gdb_values,
    );
  }

  // Deref data section (pointer target)
  if (data.deref_data) {
    const dd = data.deref_data;
    bodyHtml += `<div class="sym-deref-section">
      <div class="sym-deref-header">
        <i class="codicon codicon-type-hierarchy-sub"></i>
        <strong>${_escapeHtml(dd.type_name || '?')}</strong>
        <span class="sym-viewer-meta">${t('symbols.address', 'Address')}: ${dd.addr} &nbsp; ${t('symbols.size', 'Size')}: ${dd.size} ${t('symbols.bytes', 'bytes')}</span>
      </div>`;
    if (dd.struct_layout && dd.struct_layout.length > 0) {
      bodyHtml += _renderStructTree(
        dd.struct_layout,
        dd.hex_data,
        false,
        dd.gdb_values,
      );
    }
    if (dd.hex_data) {
      bodyHtml += `<div class="sym-viewer-hex">
        <div class="sym-hex-label">${t('symbols.raw_hex', 'Raw Hex')} (${_escapeHtml(dd.type_name || 'target')}):</div>
        <pre class="sym-hex-dump">${_formatHexDump(dd.hex_data)}</pre>
      </div>`;
    }
    bodyHtml += '</div>';
  } else if (data.deref_error) {
    bodyHtml += `<div class="sym-deref-error">
      <i class="codicon codicon-warning"></i> ${_escapeHtml(data.deref_error)}
    </div>`;
  }

  // Raw hex dump (pointer's own bytes or non-pointer data)
  if (data.hex_data) {
    const hexLabel = data.is_pointer
      ? `${t('symbols.raw_hex', 'Raw Hex')} (${t('symbols.pointer_raw', 'pointer')})`
      : t('symbols.raw_hex', 'Raw Hex');
    bodyHtml += '<div class="sym-viewer-hex">';
    bodyHtml += `<div class="sym-hex-label">${hexLabel}:</div>`;
    bodyHtml += `<pre class="sym-hex-dump">${_formatHexDump(data.hex_data)}</pre>`;
    bodyHtml += '</div>';
  } else if (isBss) {
    bodyHtml += '<div class="sym-viewer-hex">';
    bodyHtml += `<div class="sym-hex-label">${t('symbols.bss_no_init', 'No initial value (.bss) — read from device to view')}</div>`;
    bodyHtml += '</div>';
  }

  return `<div class="sym-viewer-container">${headerHtml}${toolbarHtml}${bodyHtml}</div>`;
}

/**
 * Render a struct layout as a collapsible tree (IDE-style variable viewer).
 * Uses gdb_values as primary display when available, falls back to hex decode.
 */
let _treeNodeCounter = 0;

function _renderStructTree(structLayout, hexData, isBss, gdbValues) {
  let html = '<div class="sym-tree-view">';
  for (const member of structLayout) {
    html += _renderTreeNode(member, hexData, isBss, gdbValues, 0);
  }
  html += '</div>';
  return html;
}

/**
 * Render a single tree node for a struct member.
 * gdbValues is now a structured JSON object from GDB Python API:
 *   - scalars: number or string
 *   - pointers: {_kind: "ptr", _addr: "0x...", _target: "type"}
 *   - func ptrs: {_kind: "func_ptr", _addr: "0x...", _sig: "void (*)(...)"}
 *   - enums: {_kind: "enum", _val: N, _name: "ENUM_NAME"}
 *   - nested structs: {field: value, ...} (no _kind key)
 *   - arrays: [elem, elem, ...]
 *   - collapsed: {_kind: "struct", _type: "type_name"}
 *   - errors: {_kind: "error", _msg: "..."}
 */
function _renderTreeNode(member, hexData, isBss, gdbValues, depth) {
  const indent = depth * 16;
  const gdbVal = gdbValues ? gdbValues[member.name] : null;
  const isExpandable = _isExpandableValue(gdbVal);

  // Determine display value
  let displayValue;
  if (gdbVal !== null && gdbVal !== undefined && !isExpandable) {
    displayValue = `<span class="sym-tree-value">${_escapeHtml(_formatGdbValue(gdbVal))}</span>`;
  } else if (isExpandable) {
    const summary = _getExpandableSummary(gdbVal);
    displayValue = `<span class="sym-tree-value sym-tree-summary">${_escapeHtml(summary)}</span>`;
  } else if (hexData) {
    const decoded = _decodeFieldValue(
      hexData,
      member.offset,
      member.size,
      member.type_name,
    );
    const hex = _extractFieldHex(hexData, member.offset, member.size);
    displayValue = decoded
      ? `<span class="sym-tree-value">${_escapeHtml(decoded)}</span> <span class="sym-hex-hint">(${hex})</span>`
      : `<span class="sym-tree-value sym-tree-hex">${hex}</span>`;
  } else if (isBss) {
    displayValue = `<span class="sym-tree-value sym-tree-no-data"><em>${t('symbols.needs_device_read', 'needs device read')}</em></span>`;
  } else {
    displayValue = '<span class="sym-tree-value">—</span>';
  }

  const nodeId = `stn_${_treeNodeCounter++}`;
  const chevron = isExpandable
    ? '<span class="sym-tree-toggle codicon codicon-chevron-right"></span>'
    : '<span class="sym-tree-toggle-placeholder"></span>';
  const expandAttr = isExpandable ? ' data-expandable="1"' : '';

  let html = `<div class="sym-tree-node" id="${nodeId}"${expandAttr} style="padding-left: ${indent}px;">
    <div class="sym-tree-row">
      ${chevron}
      <span class="sym-tree-name">${_escapeHtml(member.name)}</span>
      <span class="sym-tree-separator">:</span>
      <span class="sym-tree-type">${_escapeHtml(member.type_name)}</span>
      ${displayValue}
    </div>`;

  // Render children container (hidden by default)
  if (isExpandable) {
    html += `<div class="sym-tree-children" style="display: none;">`;
    html += _renderExpandableChildren(gdbVal, depth + 1);
    html += '</div>';
  }

  html += '</div>';
  return html;
}

/**
 * Check if a GDB value is expandable (struct dict or array).
 * JSON format: objects without _kind are structs, arrays are arrays.
 */
function _isExpandableValue(val) {
  if (val === null || val === undefined) return false;
  if (typeof val !== 'object') return false;
  if (Array.isArray(val)) return val.length > 0;
  // Objects with _kind are leaf nodes (ptr, func_ptr, enum, error, collapsed struct)
  if (val._kind) return false;
  // Plain object = struct with fields
  return Object.keys(val).length > 0;
}

/**
 * Get a short summary for an expandable value.
 */
function _getExpandableSummary(val) {
  if (!val) return '{...}';
  // New JSON format
  if (typeof val === 'object') {
    if (Array.isArray(val)) return `[${val.length}]`;
    const keys = Object.keys(val);
    if (keys.length <= 3) {
      const parts = keys.map((k) => `${k} = ${_formatGdbValue(val[k])}`);
      const s = `{${parts.join(', ')}}`;
      if (s.length <= 60) return s;
    }
    return `{${keys.length} fields}`;
  }
  return '{...}';
}

/**
 * Format a GDB JSON value for display as a single string.
 * Handles the structured types from json-print output.
 */
function _formatGdbValue(val) {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'number') return String(val);
  if (typeof val === 'string') return val;
  if (typeof val !== 'object') return String(val);

  // Structured types with _kind
  if (val._kind === 'ptr') return val._addr || '0x00000000';
  if (val._kind === 'func_ptr') {
    const addr = val._addr || '0x00000000';
    const sig = val._sig || '';
    return addr === '0x00000000' ? `NULL ${sig}` : `${addr} ${sig}`;
  }
  if (val._kind === 'enum') return val._name || String(val._val);
  if (val._kind === 'error') return `<error: ${val._msg || '?'}>`;
  if (val._kind === 'struct') return val._type || '{...}';

  // Array
  if (Array.isArray(val)) return `[${val.length}]`;

  // Plain struct object
  return `{${Object.keys(val).length} fields}`;
}

/**
 * Render children of an expandable GDB value (struct or array).
 */
function _renderExpandableChildren(gdbVal, depth) {
  if (!gdbVal || typeof gdbVal !== 'object') return '';
  if (Array.isArray(gdbVal)) {
    return _renderArrayChildren(gdbVal, depth);
  }
  if (!gdbVal._kind) {
    return _renderStructChildren(gdbVal, depth);
  }
  return '';
}

/**
 * Render children for a struct object {field: value, ...}.
 */
function _renderStructChildren(obj, depth) {
  let html = '';
  for (const [name, value] of Object.entries(obj)) {
    html += _renderJsonChildNode(name, value, depth);
  }
  return html;
}

/**
 * Render children for an array [elem, elem, ...].
 */
function _renderArrayChildren(arr, depth) {
  let html = '';
  for (let i = 0; i < arr.length; i++) {
    html += _renderJsonChildNode(`[${i}]`, arr[i], depth);
  }
  return html;
}

/**
 * Render a single child node for JSON-format GDB values.
 */
function _renderJsonChildNode(name, value, depth) {
  const childExpandable = _isExpandableValue(value);
  const childId = `stn_${_treeNodeCounter++}`;
  const indent = depth * 16;
  const chevron = childExpandable
    ? '<span class="sym-tree-toggle codicon codicon-chevron-right"></span>'
    : '<span class="sym-tree-toggle-placeholder"></span>';
  const displayVal = childExpandable
    ? `<span class="sym-tree-value sym-tree-summary">${_escapeHtml(_getExpandableSummary(value))}</span>`
    : `<span class="sym-tree-value">${_escapeHtml(_formatGdbValue(value))}</span>`;
  const expandAttr = childExpandable ? ' data-expandable="1"' : '';

  let html = `<div class="sym-tree-node" id="${childId}"${expandAttr} style="padding-left: ${indent}px;">
    <div class="sym-tree-row">
      ${chevron}
      <span class="sym-tree-name">${_escapeHtml(name)}</span>
      <span class="sym-tree-separator">:</span>
      ${displayVal}
    </div>`;
  if (childExpandable) {
    html += `<div class="sym-tree-children" style="display: none;">`;
    html += _renderExpandableChildren(value, depth + 1);
    html += '</div>';
  }
  html += '</div>';
  return html;
}

/**
 * Toggle a tree node's expanded/collapsed state.
 * Called via event delegation from .sym-tree-view click handler.
 */
function _toggleTreeNode(nodeEl) {
  if (!nodeEl) return;
  const children = nodeEl.querySelector(':scope > .sym-tree-children');
  const toggle = nodeEl.querySelector(
    ':scope > .sym-tree-row > .sym-tree-toggle',
  );
  if (!children) return;

  const isOpen = children.style.display !== 'none';
  children.style.display = isOpen ? 'none' : 'block';
  if (toggle) {
    toggle.classList.toggle('expanded', !isOpen);
  }
}

// Event delegation for tree node expand/collapse
document.addEventListener('click', (e) => {
  const row = e.target.closest('.sym-tree-row');
  if (!row) return;
  const node = row.parentElement;
  if (!node || !node.hasAttribute('data-expandable')) return;
  _toggleTreeNode(node);
});

/**
 * Handle deref checkbox toggle — persist state and trigger read.
 */
function _onDerefToggle(symName, checked) {
  _symDerefState.set(symName, checked);
  readSymbolFromDevice(symName, checked);
}

/**
 * Decode a little-endian hex string to a 0x-prefixed address string.
 */
function _decodeLittleEndianHex(hexData, size) {
  const bytes = [];
  for (let i = 0; i < size * 2 && i < hexData.length; i += 2) {
    bytes.push(hexData.substring(i, i + 2));
  }
  bytes.reverse();
  return '0x' + bytes.join('').toUpperCase();
}

/* ===========================
   HEX FORMATTING HELPERS
   =========================== */
function _extractFieldHex(hexData, offset, size) {
  const start = offset * 2;
  const end = start + size * 2;
  if (end > hexData.length) return '??';
  return hexData
    .slice(start, end)
    .replace(/(.{2})/g, '$1 ')
    .trim();
}

function _decodeFieldValue(hexData, offset, size, typeName) {
  const start = offset * 2;
  const end = start + size * 2;
  if (end > hexData.length) return '';

  const bytes = [];
  for (let i = start; i < end; i += 2) {
    bytes.push(parseInt(hexData.slice(i, i + 2), 16));
  }

  // Pointer types — show as hex address
  if (typeName.includes('*')) {
    return _decodeLittleEndianHex(hexData.slice(start, end), size);
  }

  // Integer types (little-endian ARM)
  const intTypes = [
    'int',
    'uint',
    'int8',
    'uint8',
    'int16',
    'uint16',
    'int32',
    'uint32',
    'int64',
    'uint64',
    'short',
    'long',
    'size_t',
    'int8_t',
    'uint8_t',
    'int16_t',
    'uint16_t',
    'int32_t',
    'uint32_t',
  ];
  const isInt = intTypes.some((t) =>
    typeName.toLowerCase().includes(t.toLowerCase()),
  );

  if (isInt && size <= 8) {
    let val = 0;
    for (let i = 0; i < bytes.length; i++) {
      val += bytes[i] * 256 ** i;
    }
    // Check for signed types
    if (
      !typeName.startsWith('u') &&
      !typeName.startsWith('U') &&
      !typeName.includes('uint')
    ) {
      const maxSigned = 2 ** (size * 8 - 1);
      if (val >= maxSigned) val -= 2 ** (size * 8);
    }
    return String(val);
  }

  // char array — show as string
  if (typeName.includes('char')) {
    const nullIdx = bytes.indexOf(0);
    const strBytes = nullIdx >= 0 ? bytes.slice(0, nullIdx) : bytes;
    const str = strBytes
      .map((b) => (b >= 32 && b < 127 ? String.fromCharCode(b) : '.'))
      .join('');
    return `"${str}"`;
  }

  // Float types (little-endian ARM)
  if (typeName.includes('float') && size === 4) {
    const view = new DataView(new ArrayBuffer(4));
    bytes.forEach((b, i) => view.setUint8(i, b));
    return view.getFloat32(0, true).toPrecision(7);
  }
  if (typeName.includes('double') && size === 8) {
    const view = new DataView(new ArrayBuffer(8));
    bytes.forEach((b, i) => view.setUint8(i, b));
    return view.getFloat64(0, true).toPrecision(15);
  }

  // Typedef fallback: if size is 1/2/4/8 and not a known struct, treat as integer
  if ([1, 2, 4, 8].includes(size) && !typeName.includes('[')) {
    let val = 0;
    for (let i = 0; i < bytes.length; i++) {
      val += bytes[i] * 256 ** i;
    }
    return String(val);
  }

  return '';
}

function _formatHexDump(hexData) {
  const lines = [];
  for (let i = 0; i < hexData.length; i += 32) {
    const offset = (i / 2).toString(16).padStart(4, '0');
    const hexPart = hexData
      .slice(i, i + 32)
      .replace(/(.{2})/g, '$1 ')
      .trim();
    // ASCII preview
    let ascii = '';
    for (let j = i; j < i + 32 && j < hexData.length; j += 2) {
      const b = parseInt(hexData.slice(j, j + 2), 16);
      ascii += b >= 32 && b < 127 ? String.fromCharCode(b) : '.';
    }
    lines.push(`0x${offset}: ${hexPart.padEnd(48)}  ${ascii}`);
  }
  return lines.join('\n');
}

function _escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}

/* ===========================
   SYMBOL SEARCH
   =========================== */
async function searchSymbols() {
  const query = document.getElementById('symbolSearch').value.trim();
  const list = document.getElementById('symbolList');

  const isAddrSearch =
    query.toLowerCase().startsWith('0x') ||
    (query.length >= 4 && /^[0-9a-fA-F]+$/.test(query));

  if (query.length < 2) {
    list.innerHTML = `<div style="padding: 8px; font-size: 11px; opacity: 0.7;">${t('panels.search_min_chars', 'Enter at least 2 characters')}</div>`;
    return;
  }

  // Show loading spinner while searching
  list.innerHTML = `<div class="sym-search-loading"><div class="sym-search-spinner"></div><span>${t('symbols.searching', 'Searching...')}</span></div>`;

  try {
    const res = await fetch(
      `/api/symbols/search?q=${encodeURIComponent(query)}`,
    );
    const data = await res.json();

    if (data.symbols && data.symbols.length > 0) {
      list.innerHTML = data.symbols
        .map((sym) => {
          const cfg = _getSymbolTypeConfig(sym.type || 'function');
          const colorStyle = cfg.color ? ` style="color: ${cfg.color};"` : '';
          return `
        <div class="symbol-item" onclick="onSymbolClick('${sym.name}', '${sym.addr}', '${sym.type || 'function'}')" ondblclick="onSymbolDblClick('${sym.name}', '${sym.type || 'function'}')">
          <i class="codicon ${cfg.icon} symbol-icon"${colorStyle}></i>
          <span class="symbol-name">${sym.name}</span>
          <span class="symbol-addr">${sym.addr}</span>
        </div>
      `;
        })
        .join('');
    } else if (data.error) {
      list.innerHTML = `<div style="padding: 8px; font-size: 11px; opacity: 0.7; color: #f44336;">${data.error}</div>`;
    } else {
      const hint = isAddrSearch
        ? t('panels.no_symbols_at_addr', 'No symbols found at this address')
        : t('panels.no_symbols_found', 'No symbols found');
      list.innerHTML = `<div style="padding: 8px; font-size: 11px; opacity: 0.7;">${hint}</div>`;
    }
  } catch (e) {
    list.innerHTML = `<div style="padding: 8px; font-size: 11px; opacity: 0.7; color: #f44336;">${t('panels.search_error', 'Error: {{message}}', { message: e.message })}</div>`;
  }
}

function selectSymbol(name) {
  log.info(`Selected symbol: ${name}`);
}

/* ===========================
   DEVICE READ/WRITE
   =========================== */
async function readSymbolFromDevice(symName, deref) {
  // If deref not explicitly passed, check persisted state, then checkbox
  if (deref === undefined) {
    if (_symDerefState.has(symName)) {
      deref = _symDerefState.get(symName);
    } else {
      const toggle = document.getElementById(`symDerefToggle_${symName}`);
      deref = toggle ? toggle.checked : false;
    }
  }

  const statusEl = document.getElementById(`symStatus_${symName}`);
  if (statusEl) statusEl.textContent = t('symbols.reading', 'Reading...');

  // Reuse global inject progress bar
  const progressEl = document.getElementById('injectProgress');
  const progressText = document.getElementById('injectProgressText');
  const progressFill = document.getElementById('injectProgressFill');
  if (progressEl) {
    progressEl.style.display = 'flex';
    if (progressText) {
      const cached = _symTabDataCache.get(symName);
      const cachedSize = cached?.data?.size;
      progressText.textContent = cachedSize
        ? t(
            'symbols.reading_symbol_size',
            `Reading ${symName} (${cachedSize} bytes)...`,
            {
              name: symName,
              size: cachedSize,
            },
          )
        : t('symbols.reading_symbol', `Reading ${symName}...`, {
            name: symName,
          });
    }
    if (progressFill) {
      progressFill.style.width = '100%';
      progressFill.style.background = '';
    }
  }

  const _hideProgress = () => {
    if (progressEl) progressEl.style.display = 'none';
    if (progressFill) {
      progressFill.style.width = '0%';
      progressFill.style.background = '';
    }
  };

  try {
    const result = await consumeSSEStream(
      '/api/symbols/read/stream',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: symName, deref: !!deref }),
      },
      {
        onStatus(ev) {
          if (progressText) {
            progressText.textContent = t(
              'symbols.reading_symbol_size',
              `Reading ${ev.symbol} (${ev.size} bytes)...`,
              { name: ev.symbol, size: ev.size },
            );
          }
          if (progressFill) progressFill.style.width = '0%';
        },
        onProgress(ev) {
          if (progressFill) progressFill.style.width = `${ev.percent}%`;
          if (progressText) {
            progressText.textContent = t(
              'symbols.reading_progress',
              `Reading ${symName} ${ev.percent.toFixed(0)}%`,
              {
                name: symName,
                percent: ev.percent.toFixed(0),
                read: ev.read,
                total: ev.total,
              },
            );
          }
        },
      },
    );

    const data = result;
    if (!data || !data.success) {
      log.error(`Read failed: ${data?.error || 'Unknown error'}`);
      if (statusEl)
        statusEl.textContent = `${t('symbols.error', 'Error')}: ${data?.error}`;
      if (progressFill) progressFill.style.background = '#f44336';
      setTimeout(_hideProgress, 2000);
      return;
    }

    // Update the tab content with fresh data (preserve scroll position)
    const tabId = `symval_${symName}`;
    const contentDiv = document.getElementById(`tabContent_${tabId}`);
    if (contentDiv) {
      const container = contentDiv.querySelector('.sym-viewer-container');
      const scrollTop = container ? container.scrollTop : 0;

      contentDiv.innerHTML = _renderSymbolValueContent(data, false);

      // Restore scroll position
      const newContainer = contentDiv.querySelector('.sym-viewer-container');
      if (newContainer) newContainer.scrollTop = scrollTop;

      // Restore auto-read state if active
      if (_autoReadTimers.has(symName)) {
        const btn = document.getElementById(`symAutoReadBtn_${symName}`);
        if (btn) btn.classList.add('active');
      }
    }

    // Update cache for language re-render
    _symTabDataCache.set(symName, { data, isConst: false });

    const now = new Date().toLocaleTimeString();
    const newStatusEl = document.getElementById(`symStatus_${symName}`);
    if (newStatusEl)
      newStatusEl.textContent = `${t('symbols.last_read', 'Last read')}: ${now}`;
    log.success(`Read ${data.size} bytes from device for ${symName}`);
    if (data.deref_data) {
      log.success(
        `Read ${data.deref_data.size} bytes (deref ${data.deref_data.type_name || ''}) at ${data.deref_data.addr}`,
      );
    }
    _hideProgress();
  } catch (e) {
    log.error(`Read exception: ${e}`);
    if (progressFill) progressFill.style.background = '#f44336';
    setTimeout(_hideProgress, 2000);
    if (statusEl)
      statusEl.textContent = `${t('symbols.error', 'Error')}: ${e.message}`;
  }
}

async function writeSymbolToDevice(symName) {
  const tabId = `symval_${symName}`;
  const contentDiv = document.getElementById(`tabContent_${tabId}`);
  if (!contentDiv) return;

  // Extract current hex data from the hex dump
  const hexDump = contentDiv.querySelector('.sym-hex-dump');
  if (!hexDump) {
    log.error(t('symbols.no_hex_data', 'No hex data to write'));
    return;
  }

  // Parse hex bytes from the dump text
  const dumpText = hexDump.textContent;
  const hexBytes = dumpText
    .replace(/^0x[0-9a-f]+:\s*/gm, '')
    .replace(/\s{2,}.*$/gm, '')
    .replace(/\s+/g, '')
    .trim();

  if (!hexBytes || !/^[0-9a-fA-F]+$/.test(hexBytes)) {
    log.error(t('symbols.invalid_hex', 'Invalid hex data'));
    return;
  }

  const statusEl = document.getElementById(`symStatus_${symName}`);
  if (statusEl) statusEl.textContent = t('symbols.writing', 'Writing...');

  try {
    const res = await fetch('/api/symbols/write', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: symName, hex_data: hexBytes }),
    });
    const data = await res.json();

    if (!data.success) {
      log.error(`Write failed: ${data.error}`);
      if (statusEl)
        statusEl.textContent = `${t('symbols.error', 'Error')}: ${data.error}`;
      return;
    }

    const now = new Date().toLocaleTimeString();
    if (statusEl)
      statusEl.textContent = `${t('symbols.written_at', 'Written at')} ${now}`;
    log.success(`Wrote to device for ${symName}`);
  } catch (e) {
    log.error(`Write exception: ${e}`);
    if (statusEl)
      statusEl.textContent = `${t('symbols.error', 'Error')}: ${e.message}`;
  }
}

/* ===========================
   SAVE SYMBOL DATA TO FILE
   =========================== */
async function saveSymbolData(symName) {
  const tabId = `symval_${symName}`;
  const contentDiv = document.getElementById(`tabContent_${tabId}`);
  if (!contentDiv) return;

  const hexDump = contentDiv.querySelector('.sym-hex-dump');
  if (!hexDump) {
    log.error(t('symbols.no_hex_data', 'No hex data to write'));
    return;
  }

  // Parse hex bytes from the dump text
  const dumpText = hexDump.textContent;
  const hexBytes = dumpText
    .replace(/^0x[0-9a-f]+:\s*/gm, '')
    .replace(/\s{2,}.*$/gm, '')
    .replace(/\s+/g, '')
    .trim();

  if (!hexBytes || !/^[0-9a-fA-F]+$/.test(hexBytes)) {
    log.error(t('symbols.invalid_hex', 'Invalid hex data'));
    return;
  }

  const fileName = `${symName}.bin`;
  const state = window.FPBState;

  state.fileBrowserCallback = async (selectedPath) => {
    if (!selectedPath) return;

    const fullPath = selectedPath.endsWith('/')
      ? selectedPath + fileName
      : selectedPath + '/' + fileName;

    try {
      const res = await fetch('/api/file/write/binary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: fullPath, hex_data: hexBytes }),
      });
      const data = await res.json();

      if (data.success) {
        log.success(
          t(
            'symbols.saved_to_file',
            `Saved ${data.size} bytes to: ${fullPath}`,
            { size: data.size, path: fullPath },
          ),
        );
      } else {
        log.error(
          t('symbols.save_failed', `Failed to save: ${data.error}`, {
            error: data.error,
          }),
        );
      }
    } catch (e) {
      log.error(
        t('symbols.save_file_error', `Failed to save file: ${e}`, { error: e }),
      );
    }
  };
  state.fileBrowserFilter = '';
  state.fileBrowserMode = 'dir';
  openFileBrowser(HOME_PATH);
}

/* ===========================
   AUTO-READ TIMER
   =========================== */
function toggleAutoRead(symName) {
  const btn = document.getElementById(`symAutoReadBtn_${symName}`);
  const intervalInput = document.getElementById(
    `symAutoReadInterval_${symName}`,
  );

  if (_autoReadTimers.has(symName)) {
    // Stop auto-read for this symbol
    clearInterval(_autoReadTimers.get(symName));
    _autoReadTimers.delete(symName);
    if (btn) btn.classList.remove('active');
    log.info(`Auto-read stopped for ${symName}`);
    return;
  }

  const interval = Math.max(500, parseInt(intervalInput?.value) || 1000);
  const timerId = setInterval(() => readSymbolFromDevice(symName), interval);
  _autoReadTimers.set(symName, timerId);
  if (btn) btn.classList.add('active');
  log.info(`Auto-read started for ${symName} (${interval}ms)`);
}

/* ===========================
   FIELD-LEVEL WRITE
   =========================== */
async function writeSymbolField(symName, offset, size, newHex) {
  const statusEl = document.getElementById(`symStatus_${symName}`);
  if (statusEl) statusEl.textContent = t('symbols.writing', 'Writing...');

  try {
    const res = await fetch('/api/symbols/write', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: symName, offset: offset, hex_data: newHex }),
    });
    const data = await res.json();

    if (!data.success) {
      log.error(`Field write failed: ${data.error}`);
      if (statusEl)
        statusEl.textContent = `${t('symbols.error', 'Error')}: ${data.error}`;
      return false;
    }

    const now = new Date().toLocaleTimeString();
    if (statusEl)
      statusEl.textContent = `${t('symbols.written_at', 'Written at')} ${now}`;
    log.success(`Wrote ${size} bytes at offset ${offset} for ${symName}`);
    return true;
  } catch (e) {
    log.error(`Field write exception: ${e}`);
    if (statusEl)
      statusEl.textContent = `${t('symbols.error', 'Error')}: ${e.message}`;
    return false;
  }
}

/* ===========================
   ARBITRARY ADDRESS READ
   =========================== */
async function readMemoryAddress(addrStr, size) {
  const addr = addrStr.trim();
  if (!addr || !size || size <= 0) {
    log.error(t('symbols.invalid_params', 'Invalid address or size'));
    return;
  }

  const tabId = `memview_${addr}_${size}`;
  const state = window.FPBState;

  if (state.editorTabs.find((t) => t.id === tabId)) {
    switchEditorTab(tabId);
    return;
  }

  log.debug(`Reading ${size} bytes from ${addr}...`);

  try {
    const res = await fetch(
      `/api/memory/read?addr=${encodeURIComponent(addr)}&size=${size}`,
    );
    const data = await res.json();

    if (!data.success) {
      log.error(`Memory read failed: ${data.error}`);
      return;
    }

    const tabTitle = `${data.addr} [${data.size}B]`;

    state.editorTabs.push({
      id: tabId,
      title: tabTitle,
      type: 'memory-viewer',
      closable: true,
      memAddr: data.addr,
      memSize: data.size,
    });

    const tabsHeader = document.getElementById('editorTabsHeader');
    const tabDiv = document.createElement('div');
    tabDiv.className = 'tab';
    tabDiv.setAttribute('data-tab', tabId);
    tabDiv.innerHTML = `
      <i class="codicon codicon-file-binary tab-icon" style="color: #c586c0;"></i>
      <span>${tabTitle}</span>
      <div class="tab-close" onclick="closeTab('${tabId}', event)"><i class="codicon codicon-close"></i></div>
    `;
    tabDiv.onclick = () => switchEditorTab(tabId);
    tabDiv.onmousedown = (e) => {
      if (e.button === 1) {
        e.preventDefault();
        closeTab(tabId, e);
      }
    };
    tabsHeader.appendChild(tabDiv);

    const tabsContent = document.querySelector('.editor-tabs-content');
    const contentDiv = document.createElement('div');
    contentDiv.className = 'tab-content';
    contentDiv.id = `tabContent_${tabId}`;
    contentDiv.innerHTML = `
      <div class="sym-viewer-container">
        <div class="sym-viewer-header">
          <div class="sym-viewer-title">
            <i class="codicon codicon-file-binary sym-viewer-icon"></i>
            <strong>${data.addr}</strong>
          </div>
          <div class="sym-viewer-meta">
            ${t('symbols.size', 'Size')}: ${data.size} ${t('symbols.bytes', 'bytes')}
          </div>
        </div>
        <div class="sym-viewer-hex">
          <div class="sym-hex-label">${t('symbols.raw_hex', 'Raw Hex')}:</div>
          <pre class="sym-hex-dump">${_formatHexDump(data.hex_data)}</pre>
        </div>
      </div>
    `;
    tabsContent.appendChild(contentDiv);

    switchEditorTab(tabId);
    log.success(`Read ${data.size} bytes from ${data.addr}`);
  } catch (e) {
    log.error(`Memory read exception: ${e}`);
  }
}

// Re-render all open symbol viewer tabs on language change
function _rerenderSymbolTabs() {
  const state = window.FPBState;
  if (!state || !state.editorTabs) return;

  for (const tab of state.editorTabs) {
    if (tab.type !== 'var-viewer' && tab.type !== 'const-viewer') continue;
    const cached = _symTabDataCache.get(tab.symName);
    if (!cached) continue;

    const contentDiv = document.getElementById(`tabContent_${tab.id}`);
    if (!contentDiv) continue;

    const container = contentDiv.querySelector('.sym-viewer-container');
    const scrollTop = container ? container.scrollTop : 0;

    contentDiv.innerHTML = _renderSymbolValueContent(
      cached.data,
      cached.isConst,
    );

    const newContainer = contentDiv.querySelector('.sym-viewer-container');
    if (newContainer) newContainer.scrollTop = scrollTop;

    // Restore auto-read state
    if (_autoReadTimers.has(tab.symName)) {
      const btn = document.getElementById(`symAutoReadBtn_${tab.symName}`);
      if (btn) btn.classList.add('active');
    }
  }
}

document.addEventListener('i18n:translated', _rerenderSymbolTabs);

// Export for global access
window.searchSymbols = searchSymbols;
window.selectSymbol = selectSymbol;
window.onSymbolClick = onSymbolClick;
window.onSymbolDblClick = onSymbolDblClick;
window.openSymbolValueTab = openSymbolValueTab;
window.readSymbolFromDevice = readSymbolFromDevice;
window.writeSymbolToDevice = writeSymbolToDevice;
window.saveSymbolData = saveSymbolData;
window.writeSymbolField = writeSymbolField;
window.readMemoryAddress = readMemoryAddress;
window.toggleAutoRead = toggleAutoRead;
window._onDerefToggle = _onDerefToggle;
// Export helpers for testing
window._extractFieldHex = _extractFieldHex;
window._decodeFieldValue = _decodeFieldValue;
window._formatHexDump = _formatHexDump;
window._escapeHtml = _escapeHtml;
window._renderSymbolValueContent = _renderSymbolValueContent;
window._renderStructTree = _renderStructTree;
window._renderTreeNode = _renderTreeNode;
window._isExpandableValue = _isExpandableValue;
window._formatGdbValue = _formatGdbValue;
window._decodeLittleEndianHex = _decodeLittleEndianHex;
window._autoReadTimers = _autoReadTimers;
window._symTabDataCache = _symTabDataCache;
window._symDerefState = _symDerefState;
window._rerenderSymbolTabs = _rerenderSymbolTabs;
