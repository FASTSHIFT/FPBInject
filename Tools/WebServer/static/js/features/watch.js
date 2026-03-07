/*========================================
  FPBInject Workbench - Watch Expression Module
  ========================================*/

/* ===========================
   WATCH STATE
   =========================== */
const _watchAutoTimers = new Map();

/* ===========================
   WATCH EXPRESSION API
   =========================== */

async function watchEvaluate(expr, readDevice) {
  if (readDevice === undefined) readDevice = true;
  try {
    const res = await fetch('/api/watch_expr/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expr: expr, read_device: readDevice }),
    });
    return await res.json();
  } catch (e) {
    return { success: false, error: e.message };
  }
}

async function watchDeref(addr, typeName, maxSize) {
  try {
    const res = await fetch('/api/watch_expr/deref', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        addr: addr,
        type_name: typeName,
        max_size: maxSize || 256,
      }),
    });
    return await res.json();
  } catch (e) {
    return { success: false, error: e.message };
  }
}

async function watchAdd(expr) {
  try {
    const res = await fetch('/api/watch_expr/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expr: expr }),
    });
    return await res.json();
  } catch (e) {
    return { success: false, error: e.message };
  }
}

async function watchRemove(id) {
  try {
    const res = await fetch('/api/watch_expr/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: id }),
    });
    return await res.json();
  } catch (e) {
    return { success: false, error: e.message };
  }
}

async function watchGetList() {
  try {
    const res = await fetch('/api/watch_expr/list');
    return await res.json();
  } catch (e) {
    return { success: false, error: e.message };
  }
}

async function watchClear() {
  try {
    const res = await fetch('/api/watch_expr/clear', { method: 'POST' });
    return await res.json();
  } catch (e) {
    return { success: false, error: e.message };
  }
}

/* ===========================
   WATCH VALUE RENDERING
   =========================== */

function _renderWatchValue(data) {
  if (!data.hex_data) {
    if (data.read_error)
      return `<span class="watch-error">${data.read_error}</span>`;
    return '<span class="watch-no-data">—</span>';
  }

  if (
    data.is_aggregate &&
    data.struct_layout &&
    data.struct_layout.length > 0
  ) {
    return _renderWatchStructTable(data.hex_data, data.struct_layout);
  }

  // Scalar value
  const decoded =
    typeof _decodeFieldValue === 'function'
      ? _decodeFieldValue(data.hex_data, 0, data.size, data.type_name)
      : '';
  const hexStr = data.hex_data.replace(/(.{2})/g, '$1 ').trim();

  if (decoded) {
    return `<span class="watch-decoded">${decoded}</span> <span class="watch-hex-hint">(${hexStr})</span>`;
  }
  return `<span class="watch-hex">${hexStr}</span>`;
}

function _renderWatchStructTable(hexData, layout) {
  let html = '<table class="watch-struct-table"><thead><tr>';
  html += '<th>Field</th><th>Type</th><th>Value</th>';
  html += '</tr></thead><tbody>';

  for (const member of layout) {
    const decoded =
      typeof _decodeFieldValue === 'function'
        ? _decodeFieldValue(
            hexData,
            member.offset,
            member.size,
            member.type_name,
          )
        : '';
    const fieldHex =
      typeof _extractFieldHex === 'function'
        ? _extractFieldHex(hexData, member.offset, member.size)
        : '';
    const display = decoded
      ? `${decoded} <span class="watch-hex-hint">(${fieldHex})</span>`
      : fieldHex;

    const isPtr = member.type_name && member.type_name.trim().endsWith('*');
    const derefTitle =
      typeof t === 'function'
        ? t('watch.deref_tooltip', 'Dereference')
        : 'Dereference';
    const derefBtn = isPtr
      ? ` <button class="watch-deref-btn" title="${derefTitle}">[→]</button>`
      : '';

    html += `<tr>
      <td class="watch-field-name">${member.name}</td>
      <td class="watch-field-type">${member.type_name}</td>
      <td class="watch-field-value">${display}${derefBtn}</td>
    </tr>`;
  }

  html += '</tbody></table>';
  return html;
}

/* ===========================
   WATCH PANEL RENDERING
   =========================== */

function renderWatchEntry(id, expr, data) {
  const hasData = data && data.success;
  const typeInfo = hasData ? data.type_name : '';
  const addrInfo = hasData ? data.addr : '';
  const sizeInfo = hasData ? `${data.size}B` : '';
  const errorMsg = data && !data.success ? data.error : '';

  let valueHtml = '';
  if (hasData) {
    valueHtml = _renderWatchValue(data);
  } else if (errorMsg) {
    valueHtml = `<span class="watch-error">${errorMsg}</span>`;
  }

  const refreshTitle =
    typeof t === 'function' ? t('watch.refresh_tooltip', 'Refresh') : 'Refresh';
  const removeTitle =
    typeof t === 'function' ? t('watch.remove_tooltip', 'Remove') : 'Remove';

  return `<div class="watch-entry" data-watch-id="${id}">
    <div class="watch-entry-header">
      <span class="watch-expr" title="${addrInfo} ${typeInfo} ${sizeInfo}">${expr}</span>
      <span class="watch-actions">
        <button class="watch-btn" onclick="watchRefreshOne(${id}, '${expr.replace(/'/g, "\\'")}')" title="${refreshTitle}"><i class="codicon codicon-refresh"></i></button>
        <button class="watch-btn" onclick="watchRemoveEntry(${id})" title="${removeTitle}"><i class="codicon codicon-close"></i></button>
      </span>
    </div>
    <div class="watch-entry-value">${valueHtml}</div>
  </div>`;
}

async function watchRefreshOne(id, expr) {
  const data = await watchEvaluate(expr, true);
  const container = document.querySelector(
    `.watch-entry[data-watch-id="${id}"]`,
  );
  if (container) {
    const valueDiv = container.querySelector('.watch-entry-value');
    if (valueDiv) {
      valueDiv.innerHTML = data.success
        ? _renderWatchValue(data)
        : `<span class="watch-error">${data.error}</span>`;
    }
  }
}

async function watchRemoveEntry(id) {
  await watchRemove(id);
  const container = document.querySelector(
    `.watch-entry[data-watch-id="${id}"]`,
  );
  if (container) container.remove();
  // Stop auto-refresh if active
  if (_watchAutoTimers.has(id)) {
    clearInterval(_watchAutoTimers.get(id));
    _watchAutoTimers.delete(id);
  }
}

/* ===========================
   PANEL INTERACTION
   =========================== */

async function watchAddFromInput() {
  const input = document.getElementById('watchExprInput');
  if (!input) return;
  const expr = input.value.trim();
  if (!expr) return;

  const addResult = await watchAdd(expr);
  if (!addResult.success) {
    if (typeof log !== 'undefined')
      log.error('Watch add failed: ' + (addResult.error || ''));
    return;
  }

  input.value = '';

  // Evaluate and render
  const data = await watchEvaluate(expr, true);
  const panel = document.getElementById('watchPanel');
  if (!panel) return;

  // Remove empty placeholder
  const empty = panel.querySelector('.watch-empty');
  if (empty) empty.remove();

  const html = renderWatchEntry(addResult.id, expr, data);
  panel.insertAdjacentHTML('beforeend', html);
}

async function watchRefreshAll() {
  const listResult = await watchGetList();
  if (!listResult.success) return;

  for (const w of listResult.watches) {
    await watchRefreshOne(w.id, w.expr);
  }
}

async function watchClearAll() {
  await watchClear();
  const panel = document.getElementById('watchPanel');
  if (panel) {
    const noWatchesText =
      typeof t === 'function'
        ? t('watch.no_watches', 'No watch expressions')
        : 'No watch expressions';
    panel.innerHTML = '<div class="watch-empty">' + noWatchesText + '</div>';
  }
  // Stop all auto-refresh timers
  for (const [id, timerId] of _watchAutoTimers) {
    clearInterval(timerId);
  }
  _watchAutoTimers.clear();
}

/* ===========================
   EXPORTS
   =========================== */
window.watchEvaluate = watchEvaluate;
window.watchDeref = watchDeref;
window.watchAdd = watchAdd;
window.watchRemove = watchRemove;
window.watchGetList = watchGetList;
window.watchClear = watchClear;
window.watchRefreshOne = watchRefreshOne;
window.watchRemoveEntry = watchRemoveEntry;
window.renderWatchEntry = renderWatchEntry;
window.watchAddFromInput = watchAddFromInput;
window.watchRefreshAll = watchRefreshAll;
window.watchClearAll = watchClearAll;
window._renderWatchValue = _renderWatchValue;
window._renderWatchStructTable = _renderWatchStructTable;
window._watchAutoTimers = _watchAutoTimers;
