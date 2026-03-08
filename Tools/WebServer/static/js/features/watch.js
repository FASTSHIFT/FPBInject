/*========================================
  FPBInject Workbench - Watch Expression Module
  VS Code-style Tree View Implementation
  ========================================*/

/* ===========================
   WATCH STATE
   =========================== */
const _watchAutoTimers = new Map();
const _watchPrevValues = new Map(); // For value change highlighting
const _watchExpandedState = new Map(); // Track expanded/collapsed state
let _watchAutoRefreshInterval = 0;
let _watchAutoRefreshTimer = null;

const WATCH_STORAGE_KEY = 'fpbinject_watch_expressions';

/* ===========================
   LOCAL STORAGE PERSISTENCE
   =========================== */

function _saveWatchesToStorage() {
  try {
    const watches = [];
    const nodes = document.querySelectorAll('.watch-tree-node[data-depth="0"]');
    nodes.forEach((node) => {
      const id = node.getAttribute('data-watch-id');
      const cached = _watchDataCache.get(parseInt(id));
      if (cached && cached.expr) {
        watches.push(cached.expr);
      }
    });
    localStorage.setItem(WATCH_STORAGE_KEY, JSON.stringify(watches));
  } catch (e) {
    console.warn('Failed to save watch expressions:', e);
  }
}

function _loadWatchesFromStorage() {
  try {
    const stored = localStorage.getItem(WATCH_STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    console.warn('Failed to load watch expressions:', e);
  }
  return [];
}

async function watchRestoreFromStorage() {
  const expressions = _loadWatchesFromStorage();
  if (expressions.length === 0) return;

  const panel = document.getElementById('watchPanel');
  if (!panel) return;

  // Clear empty placeholder
  const empty = panel.querySelector('.watch-empty');
  if (empty) empty.remove();

  for (const expr of expressions) {
    const addResult = await watchAdd(expr);
    if (addResult.success) {
      // Don't evaluate on startup - just show the expression with no data
      _watchDataCache.set(addResult.id, { expr, data: null });
      const html = _buildWatchTreeNode(addResult.id, expr, expr, null, 0);
      panel.insertAdjacentHTML('beforeend', html);
    }
  }
}

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

  // For aggregate types, return summary (children shown in tree)
  if (
    data.is_aggregate &&
    data.struct_layout &&
    data.struct_layout.length > 0
  ) {
    const typeName = data.type_name || 'struct';
    return `<span class="watch-type-summary">{${data.struct_layout.length} fields}</span>`;
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
   TREE VIEW RENDERING
   =========================== */

function _buildWatchTreeNode(id, expr, name, data, depth = 0) {
  const hasData = data && data.success;
  const typeName = hasData ? data.type_name : '';
  const isExpandable =
    hasData &&
    data.is_aggregate &&
    data.struct_layout &&
    data.struct_layout.length > 0;
  const nodeId = `${id}`;
  const isExpanded = _watchExpandedState.get(nodeId) !== false; // Default expanded

  let valueHtml = '';
  if (hasData) {
    valueHtml = _renderWatchValue(data);
  } else if (data && data.error) {
    valueHtml = `<span class="watch-error">${data.error}</span>`;
  }

  // Build node HTML
  let html = `<div class="watch-tree-node" data-watch-id="${nodeId}" data-depth="${depth}" style="--depth: ${depth}">`;

  // Expand icon
  if (isExpandable) {
    const iconClass = isExpanded ? 'expanded' : 'collapsed';
    html += `<span class="watch-expand-icon ${iconClass}" onclick="watchToggleExpand('${nodeId}')"></span>`;
  } else {
    html += `<span class="watch-expand-icon leaf"></span>`;
  }

  // Name/Expression
  html += `<span class="watch-node-name">${escapeHtml(name || expr)}</span>`;

  // Type (dimmed)
  if (typeName) {
    html += `<span class="watch-node-type">${escapeHtml(typeName)}</span>`;
  }

  // Value
  html += `<span class="watch-node-value" data-node-id="${nodeId}">${valueHtml}</span>`;

  // Actions (only for root nodes)
  if (depth === 0) {
    const refreshTitle =
      typeof t === 'function'
        ? t('watch.refresh_tooltip', 'Refresh')
        : 'Refresh';
    const removeTitle =
      typeof t === 'function' ? t('watch.remove_tooltip', 'Remove') : 'Remove';
    html += `<span class="watch-node-actions">`;
    html += `<button class="watch-btn" onclick="watchRefreshOne(${id}, '${expr.replace(/'/g, "\\'")}')" title="${refreshTitle}"><i class="codicon codicon-refresh"></i></button>`;
    html += `<button class="watch-btn" onclick="watchRemoveEntry(${id})" title="${removeTitle}"><i class="codicon codicon-close"></i></button>`;
    html += `</span>`;
  }

  html += `</div>`;

  // Render children if expanded
  if (isExpandable && isExpanded && data.hex_data) {
    html += `<div class="watch-tree-children" data-parent="${nodeId}">`;
    for (let i = 0; i < data.struct_layout.length; i++) {
      const member = data.struct_layout[i];
      const childId = `${id}.${i}`;
      const childValue = _extractMemberValue(data.hex_data, member);
      html += _buildWatchTreeChildNode(childId, member, childValue, depth + 1);
    }
    html += `</div>`;
  }

  return html;
}

function _buildWatchTreeChildNode(nodeId, member, value, depth) {
  const typeName = member.type_name || '';
  const isPtr = typeName.trim().endsWith('*');

  let html = `<div class="watch-tree-node" data-watch-id="${nodeId}" data-depth="${depth}" style="--depth: ${depth}">`;

  // No expand for simple fields (could add for nested structs later)
  html += `<span class="watch-expand-icon leaf"></span>`;

  // Field name
  html += `<span class="watch-node-name">${escapeHtml(member.name)}</span>`;

  // Type
  html += `<span class="watch-node-type">${escapeHtml(typeName)}</span>`;

  // Value
  const valueHtml =
    value !== null
      ? `<span class="watch-decoded">${value.decoded}</span> <span class="watch-hex-hint">(${value.hex})</span>`
      : '<span class="watch-no-data">—</span>';

  html += `<span class="watch-node-value" data-node-id="${nodeId}">${valueHtml}</span>`;

  // Deref button for pointers
  if (isPtr && value && value.decoded !== '0x00000000') {
    const derefTitle =
      typeof t === 'function'
        ? t('watch.deref_tooltip', 'Dereference')
        : 'Dereference';
    html += `<button class="watch-deref-btn" onclick="watchDerefField('${nodeId}', '${value.decoded}', '${typeName}')" title="${derefTitle}">→</button>`;
  }

  html += `</div>`;
  return html;
}

function _extractMemberValue(hexData, member) {
  if (!hexData) return null;

  const fieldHex =
    typeof _extractFieldHex === 'function'
      ? _extractFieldHex(hexData, member.offset, member.size)
      : '';

  const decoded =
    typeof _decodeFieldValue === 'function'
      ? _decodeFieldValue(hexData, member.offset, member.size, member.type_name)
      : fieldHex;

  return { hex: fieldHex, decoded: decoded };
}

function watchToggleExpand(nodeId) {
  const currentState = _watchExpandedState.get(nodeId);
  const newState = currentState === false;
  _watchExpandedState.set(nodeId, newState);

  // Re-render the watch panel
  watchRenderAll();
}

async function watchDerefField(nodeId, addr, typeName) {
  const result = await watchDeref(addr, typeName);
  if (result.success) {
    // Add as new watch expression
    const expr = `*(${typeName.replace(' *', ' *)')})${addr}`;
    await watchAdd(expr);
    await watchRenderAll();
  } else {
    if (typeof log !== 'undefined') {
      log.error('Deref failed: ' + (result.error || ''));
    }
  }
}

/* ===========================
   WATCH PANEL RENDERING
   =========================== */

// Store watch data for re-rendering
const _watchDataCache = new Map();

function renderWatchEntry(id, expr, data) {
  // Cache data for re-rendering
  _watchDataCache.set(id, { expr, data });
  return _buildWatchTreeNode(id, expr, expr, data, 0);
}

async function watchRenderAll() {
  const panel = document.getElementById('watchPanel');
  if (!panel) return;

  const listResult = await watchGetList();
  if (!listResult.success) return;

  if (listResult.watches.length === 0) {
    const noWatchesText =
      typeof t === 'function'
        ? t('watch.no_watches', 'No watch expressions')
        : 'No watch expressions';
    panel.innerHTML = `<div class="watch-empty">${noWatchesText}</div>`;
    return;
  }

  let html = '';
  for (const w of listResult.watches) {
    const cached = _watchDataCache.get(w.id);
    if (cached && cached.data) {
      html += _buildWatchTreeNode(w.id, w.expr, w.expr, cached.data, 0);
    } else {
      // Fetch data if not cached
      const data = await watchEvaluate(w.expr, true);
      _watchDataCache.set(w.id, { expr: w.expr, data });
      html += _buildWatchTreeNode(w.id, w.expr, w.expr, data, 0);
    }
  }
  panel.innerHTML = html;
}

async function watchRefreshOne(id, expr) {
  const data = await watchEvaluate(expr, true);
  const oldData = _watchDataCache.get(id);

  // Check for value changes and highlight
  if (oldData && oldData.data && data.success) {
    _checkAndHighlightChanges(id, oldData.data, data);
  }

  _watchDataCache.set(id, { expr, data });

  // Re-render just this entry
  const node = document.querySelector(
    `.watch-tree-node[data-watch-id="${id}"][data-depth="0"]`,
  );
  if (node) {
    const parent = node.parentElement;
    const newHtml = _buildWatchTreeNode(id, expr, expr, data, 0);

    // Find and remove children container if exists
    const childrenContainer = parent.querySelector(
      `.watch-tree-children[data-parent="${id}"]`,
    );
    if (childrenContainer) {
      childrenContainer.remove();
    }

    // Replace node
    node.outerHTML = newHtml;
  }
}

function _checkAndHighlightChanges(id, oldData, newData) {
  // Compare hex_data for changes
  if (oldData.hex_data !== newData.hex_data) {
    setTimeout(() => {
      const valueEl = document.querySelector(
        `.watch-node-value[data-node-id="${id}"]`,
      );
      if (valueEl) {
        valueEl.classList.add('changed');
        setTimeout(() => valueEl.classList.remove('changed'), 1000);
      }
    }, 50);
  }
}

async function watchRemoveEntry(id) {
  await watchRemove(id);
  _watchDataCache.delete(id);
  _watchExpandedState.delete(String(id));

  // Remove from DOM
  const node = document.querySelector(
    `.watch-tree-node[data-watch-id="${id}"][data-depth="0"]`,
  );
  if (node) {
    // Also remove children container
    const childrenContainer = node.parentElement.querySelector(
      `.watch-tree-children[data-parent="${id}"]`,
    );
    if (childrenContainer) {
      childrenContainer.remove();
    }
    node.remove();
  }

  // Show empty message if no watches left
  const panel = document.getElementById('watchPanel');
  if (
    panel &&
    panel.querySelectorAll('.watch-tree-node[data-depth="0"]').length === 0
  ) {
    const noWatchesText =
      typeof t === 'function'
        ? t('watch.no_watches', 'No watch expressions')
        : 'No watch expressions';
    panel.innerHTML = `<div class="watch-empty">${noWatchesText}</div>`;
  }

  // Stop auto-refresh if active
  if (_watchAutoTimers.has(id)) {
    clearInterval(_watchAutoTimers.get(id));
    _watchAutoTimers.delete(id);
  }

  // Save to localStorage
  _saveWatchesToStorage();
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
  _watchDataCache.set(addResult.id, { expr, data });

  const panel = document.getElementById('watchPanel');
  if (!panel) return;

  // Remove empty placeholder
  const empty = panel.querySelector('.watch-empty');
  if (empty) empty.remove();

  const html = _buildWatchTreeNode(addResult.id, expr, expr, data, 0);
  panel.insertAdjacentHTML('beforeend', html);

  // Save to localStorage
  _saveWatchesToStorage();
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
  _watchDataCache.clear();
  _watchExpandedState.clear();
  _watchPrevValues.clear();

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

  // Clear localStorage
  _saveWatchesToStorage();
}

/* ===========================
   AUTO-REFRESH
   =========================== */

function watchSetAutoRefresh(intervalMs) {
  if (_watchAutoRefreshTimer) {
    clearInterval(_watchAutoRefreshTimer);
    _watchAutoRefreshTimer = null;
  }

  _watchAutoRefreshInterval = intervalMs;

  if (intervalMs > 0) {
    _watchAutoRefreshTimer = setInterval(watchRefreshAll, intervalMs);
    if (typeof log !== 'undefined') {
      log.info(`Watch auto-refresh enabled: ${intervalMs}ms`);
    }
  } else {
    if (typeof log !== 'undefined') {
      log.info('Watch auto-refresh disabled');
    }
  }
}

function watchGetAutoRefreshInterval() {
  return _watchAutoRefreshInterval;
}

/* ===========================
   COLLAPSE/EXPAND ALL
   =========================== */

function watchCollapseAll() {
  for (const [key] of _watchExpandedState) {
    _watchExpandedState.set(key, false);
  }
  // Also collapse any that aren't tracked yet
  const nodes = document.querySelectorAll('.watch-tree-node[data-depth="0"]');
  nodes.forEach((node) => {
    const id = node.getAttribute('data-watch-id');
    if (id) _watchExpandedState.set(id, false);
  });
  watchRenderAll();
}

function watchExpandAll() {
  const nodes = document.querySelectorAll('.watch-tree-node[data-depth="0"]');
  nodes.forEach((node) => {
    const id = node.getAttribute('data-watch-id');
    if (id) _watchExpandedState.set(id, true);
  });
  watchRenderAll();
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
window.watchRenderAll = watchRenderAll;
window.watchToggleExpand = watchToggleExpand;
window.watchDerefField = watchDerefField;
window.watchSetAutoRefresh = watchSetAutoRefresh;
window.watchGetAutoRefreshInterval = watchGetAutoRefreshInterval;
window.watchCollapseAll = watchCollapseAll;
window.watchExpandAll = watchExpandAll;
window.watchRestoreFromStorage = watchRestoreFromStorage;
window._saveWatchesToStorage = _saveWatchesToStorage;
window._loadWatchesFromStorage = _loadWatchesFromStorage;
window._renderWatchValue = _renderWatchValue;
window._renderWatchStructTable = _renderWatchStructTable;
window._buildWatchTreeNode = _buildWatchTreeNode;
window._watchAutoTimers = _watchAutoTimers;
window._watchDataCache = _watchDataCache;
window._watchExpandedState = _watchExpandedState;
