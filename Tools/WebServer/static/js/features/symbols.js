/*========================================
  FPBInject Workbench - Symbol Search Module
  ========================================*/

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
    list.innerHTML =
      '<div style="padding: 8px; font-size: 11px; opacity: 0.7;">Enter at least 2 characters</div>';
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
          (sym) => `
        <div class="symbol-item" onclick="openDisassembly('${sym.name}', '${sym.addr}')" ondblclick="openManualPatchTab('${sym.name}')">
          <i class="codicon codicon-symbol-method symbol-icon"></i>
          <span class="symbol-name">${sym.name}</span>
          <span class="symbol-addr">${sym.addr}</span>
        </div>
      `,
        )
        .join('');
    } else if (data.error) {
      list.innerHTML = `<div style="padding: 8px; font-size: 11px; opacity: 0.7; color: #f44336;">${data.error}</div>`;
    } else {
      const hint = isAddrSearch
        ? 'No symbols found at this address'
        : 'No symbols found';
      list.innerHTML = `<div style="padding: 8px; font-size: 11px; opacity: 0.7;">${hint}</div>`;
    }
  } catch (e) {
    list.innerHTML = `<div style="padding: 8px; font-size: 11px; opacity: 0.7; color: #f44336;">Error: ${e.message}</div>`;
  }
}

function selectSymbol(name) {
  writeToOutput(`[INFO] Selected symbol: ${name}`, 'info');
}

// Export for global access
window.searchSymbols = searchSymbols;
window.selectSymbol = selectSymbol;
