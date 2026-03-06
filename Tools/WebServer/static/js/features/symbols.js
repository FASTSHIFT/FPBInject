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

  try {
    const res = await fetch(
      `/api/symbols/value?name=${encodeURIComponent(symName)}`,
    );
    const data = await res.json();

    if (!data.success) {
      log.error(`Failed to load symbol value: ${data.error}`);
      return;
    }

    const isConst = symType === 'const';
    const tabTitle = `${symName} [${isConst ? 'const' : 'var'}]`;
    const tabIcon = isConst ? 'codicon-symbol-constant' : 'codicon-symbol-variable';
    const tabColor = isConst ? '#4fc1ff' : '#75beff';

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
      if (e.button === 1) { e.preventDefault(); closeTab(tabId, e); }
    };
    tabsHeader.appendChild(tabDiv);

    const tabsContent = document.querySelector('.editor-tabs-content');
    const contentDiv = document.createElement('div');
    contentDiv.className = 'tab-content';
    contentDiv.id = `tabContent_${tabId}`;
    contentDiv.innerHTML = _renderSymbolValueContent(data, isConst);
    tabsContent.appendChild(contentDiv);

    switchEditorTab(tabId);
    log.success(`Opened ${isConst ? 'const' : 'variable'} viewer for ${symName}`);
  } catch (e) {
    log.error(`Failed to load symbol value: ${e}`);
  }
}

function _renderSymbolValueContent(data, isConst) {
  const sectionLabel = isConst ? 'Read-Only' : 'Read-Write';
  const isBss = data.section && data.section.startsWith('.bss');

  let headerHtml = `
    <div class="sym-viewer-header">
      <div class="sym-viewer-title">
        <span class="sym-viewer-icon">${isConst ? '📌' : '📊'}</span>
        <strong>${_escapeHtml(data.name)}</strong>
      </div>
      <div class="sym-viewer-meta">
        Address: ${data.addr} &nbsp; Size: ${data.size} bytes &nbsp;
        Section: ${_escapeHtml(data.section)} (${sectionLabel})
      </div>
    </div>
  `;

  let bodyHtml = '';

  if (data.struct_layout && data.struct_layout.length > 0) {
    // Struct table view
    bodyHtml += '<div class="sym-viewer-struct">';
    bodyHtml += '<table class="sym-struct-table"><thead><tr>';
    bodyHtml += '<th>Field</th><th>Type</th><th>Offset</th><th>Size</th><th>Value</th>';
    bodyHtml += '</tr></thead><tbody>';

    for (const member of data.struct_layout) {
      const valueHex = data.hex_data
        ? _extractFieldHex(data.hex_data, member.offset, member.size)
        : (isBss ? '<em>needs device read</em>' : '—');
      const valueDecoded = data.hex_data
        ? _decodeFieldValue(data.hex_data, member.offset, member.size, member.type_name)
        : '';
      const displayValue = valueDecoded
        ? `${valueDecoded} <span class="sym-hex-hint">(${valueHex})</span>`
        : valueHex;

      bodyHtml += `<tr>
        <td class="sym-field-name">${_escapeHtml(member.name)}</td>
        <td class="sym-field-type">${_escapeHtml(member.type_name)}</td>
        <td>+${member.offset}</td>
        <td>${member.size}</td>
        <td class="sym-field-value">${displayValue}</td>
      </tr>`;
    }
    bodyHtml += '</tbody></table></div>';
  }

  // Raw hex dump
  if (data.hex_data) {
    bodyHtml += '<div class="sym-viewer-hex">';
    bodyHtml += '<div class="sym-hex-label">Raw Hex:</div>';
    bodyHtml += `<pre class="sym-hex-dump">${_formatHexDump(data.hex_data)}</pre>`;
    bodyHtml += '</div>';
  } else if (isBss) {
    bodyHtml += '<div class="sym-viewer-hex">';
    bodyHtml += `<div class="sym-hex-label">${t('symbols.bss_no_init', 'No initial value (.bss) — read from device to view')}</div>`;
    bodyHtml += '</div>';
  }

  return `<div class="sym-viewer-container">${headerHtml}${bodyHtml}</div>`;
}

/* ===========================
   HEX FORMATTING HELPERS
   =========================== */
function _extractFieldHex(hexData, offset, size) {
  const start = offset * 2;
  const end = start + size * 2;
  if (end > hexData.length) return '??';
  return hexData.slice(start, end).replace(/(.{2})/g, '$1 ').trim();
}

function _decodeFieldValue(hexData, offset, size, typeName) {
  const start = offset * 2;
  const end = start + size * 2;
  if (end > hexData.length) return '';

  const bytes = [];
  for (let i = start; i < end; i += 2) {
    bytes.push(parseInt(hexData.slice(i, i + 2), 16));
  }

  // Integer types (little-endian ARM)
  const intTypes = ['int', 'uint', 'int8', 'uint8', 'int16', 'uint16',
    'int32', 'uint32', 'int64', 'uint64', 'short', 'long', 'size_t',
    'int8_t', 'uint8_t', 'int16_t', 'uint16_t', 'int32_t', 'uint32_t'];
  const isInt = intTypes.some((t) => typeName.toLowerCase().includes(t.toLowerCase()));

  if (isInt && size <= 8) {
    let val = 0;
    for (let i = 0; i < bytes.length; i++) {
      val += bytes[i] * (256 ** i);
    }
    // Check for signed types
    if (!typeName.startsWith('u') && !typeName.startsWith('U') && !typeName.includes('uint')) {
      const maxSigned = 2 ** (size * 8 - 1);
      if (val >= maxSigned) val -= 2 ** (size * 8);
    }
    return String(val);
  }

  // char array — show as string
  if (typeName.includes('char')) {
    const nullIdx = bytes.indexOf(0);
    const strBytes = nullIdx >= 0 ? bytes.slice(0, nullIdx) : bytes;
    const str = strBytes.map((b) => (b >= 32 && b < 127) ? String.fromCharCode(b) : '.').join('');
    return `"${str}"`;
  }

  return '';
}

function _formatHexDump(hexData) {
  const lines = [];
  for (let i = 0; i < hexData.length; i += 32) {
    const offset = (i / 2).toString(16).padStart(4, '0');
    const hexPart = hexData.slice(i, i + 32).replace(/(.{2})/g, '$1 ').trim();
    // ASCII preview
    let ascii = '';
    for (let j = i; j < i + 32 && j < hexData.length; j += 2) {
      const b = parseInt(hexData.slice(j, j + 2), 16);
      ascii += (b >= 32 && b < 127) ? String.fromCharCode(b) : '.';
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

  try {
    const res = await fetch(
      `/api/symbols/search?q=${encodeURIComponent(query)}`,
    );
    const data = await res.json();

    if (data.symbols && data.symbols.length > 0) {
      list.innerHTML = data.symbols
        .map(
          (sym) => {
            const cfg = _getSymbolTypeConfig(sym.type || 'function');
            const colorStyle = cfg.color ? ` style="color: ${cfg.color};"` : '';
            return `
        <div class="symbol-item" onclick="onSymbolClick('${sym.name}', '${sym.addr}', '${sym.type || 'function'}')" ondblclick="onSymbolDblClick('${sym.name}', '${sym.type || 'function'}')">
          <i class="codicon ${cfg.icon} symbol-icon"${colorStyle}></i>
          <span class="symbol-name">${sym.name}</span>
          <span class="symbol-addr">${sym.addr}</span>
        </div>
      `;
          },
        )
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

// Export for global access
window.searchSymbols = searchSymbols;
window.selectSymbol = selectSymbol;
window.onSymbolClick = onSymbolClick;
window.onSymbolDblClick = onSymbolDblClick;
window.openSymbolValueTab = openSymbolValueTab;
