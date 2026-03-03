/*========================================
  FPBInject Workbench - Quick Commands Module
  ========================================*/

/* ===========================
   CONSTANTS & STATE
   =========================== */
const QC_STORAGE_KEY = 'fpbinject-quick-commands';
let qcEditingId = null; // ID of command being edited, null = new
let qcContextTargetId = null; // ID of command for context menu
let qcMacroAbort = null; // AbortController for macro execution

/* ===========================
   STORAGE
   =========================== */

function loadQuickCommands() {
  try {
    const raw = localStorage.getItem(QC_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error('Failed to load quick commands:', e);
    return [];
  }
}

function saveQuickCommands(commands) {
  try {
    localStorage.setItem(QC_STORAGE_KEY, JSON.stringify(commands));
  } catch (e) {
    console.error('Failed to save quick commands:', e);
  }
}

function generateId() {
  return 'qc_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
}

/* ===========================
   ESCAPE HANDLING
   =========================== */

function unescapeCommand(str) {
  return str
    .replace(/\\n/g, '\n')
    .replace(/\\r/g, '\r')
    .replace(/\\t/g, '\t')
    .replace(/\\x1b/g, '\x1b')
    .replace(/\\\\/g, '\\');
}

function escapeCommandForDisplay(str) {
  return str
    .replace(/\\/g, '\\\\')
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '\\r')
    .replace(/\t/g, '\\t')
    .replace(/\x1b/g, '\\x1b');
}

/* ===========================
   RENDER COMMAND LIST
   =========================== */

function renderQuickCommands() {
  const list = document.getElementById('quickCommandList');
  if (!list) return;

  const commands = loadQuickCommands();
  list.innerHTML = '';

  if (commands.length === 0) {
    list.innerHTML =
      '<div class="empty" style="padding: 8px; font-size: 11px; opacity: 0.7" ' +
      'data-i18n="quick_commands.empty">No commands yet</div>';
    if (typeof translatePage === 'function') translatePage();
    return;
  }

  // Group commands
  const groups = {};
  const ungrouped = [];
  for (const cmd of commands) {
    if (cmd.group) {
      if (!groups[cmd.group]) groups[cmd.group] = [];
      groups[cmd.group].push(cmd);
    } else {
      ungrouped.push(cmd);
    }
  }

  // Render groups
  for (const [groupName, groupCmds] of Object.entries(groups)) {
    const groupEl = document.createElement('div');
    groupEl.className = 'qc-group';
    groupEl.innerHTML =
      '<div class="qc-group-header" onclick="this.parentElement.classList.toggle(\'collapsed\')">' +
      '<i class="codicon codicon-chevron-down qc-group-chevron"></i>' +
      '<i class="codicon codicon-folder"></i>' +
      '<span class="qc-group-name">' +
      escapeHtml(groupName) +
      '</span>' +
      '</div>';
    const itemsEl = document.createElement('div');
    itemsEl.className = 'qc-group-items';
    for (const cmd of groupCmds) {
      itemsEl.appendChild(createCommandItem(cmd));
    }
    groupEl.appendChild(itemsEl);
    list.appendChild(groupEl);
  }

  // Render ungrouped
  for (const cmd of ungrouped) {
    list.appendChild(createCommandItem(cmd));
  }

  if (typeof translatePage === 'function') translatePage();
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function createCommandItem(cmd) {
  const item = document.createElement('div');
  item.className = 'qc-item';
  item.dataset.id = cmd.id;

  const icon = cmd.type === 'macro' ? 'codicon-layers' : 'codicon-terminal';
  const label = escapeHtml(cmd.name || cmd.command || 'Unnamed');
  const badge =
    cmd.type === 'macro' && cmd.steps
      ? '<span class="qc-badge">' + cmd.steps.length + ' cmds</span>'
      : '';

  item.innerHTML =
    '<i class="codicon ' +
    icon +
    ' qc-item-icon"></i>' +
    '<span class="qc-item-name" title="' +
    escapeHtml(cmd.name || '') +
    '">' +
    label +
    '</span>' +
    badge +
    '<span class="qc-item-actions">' +
    '<button class="qc-action-btn" onclick="event.stopPropagation(); executeQuickCommand(\'' +
    cmd.id +
    '\')" title="Execute">' +
    '<i class="codicon codicon-play"></i></button>' +
    '<button class="qc-action-btn" onclick="event.stopPropagation(); showQcContextMenu(event, \'' +
    cmd.id +
    '\')" title="More">' +
    '<i class="codicon codicon-ellipsis"></i></button>' +
    '</span>';

  item.ondblclick = () => executeQuickCommand(cmd.id);
  item.oncontextmenu = (e) => {
    e.preventDefault();
    showQcContextMenu(e, cmd.id);
  };

  return item;
}

/* ===========================
   COMMAND EXECUTION
   =========================== */

async function executeQuickCommand(id) {
  const state = window.FPBState;
  if (!state || !state.isConnected) {
    if (typeof log !== 'undefined') log.error('Not connected');
    return;
  }

  const commands = loadQuickCommands();
  const cmd = commands.find((c) => c.id === id);
  if (!cmd) return;

  // Visual feedback
  const itemEl = document.querySelector('.qc-item[data-id="' + id + '"]');
  if (itemEl) itemEl.classList.add('executing');

  try {
    if (cmd.type === 'macro' && cmd.steps) {
      await executeMacro(cmd, itemEl);
    } else {
      let data = cmd.command || '';
      if (cmd.appendNewline !== false) data = unescapeCommand(data);
      else data = unescapeCommand(data);
      await sendSerialData(data);
    }
  } finally {
    if (itemEl) {
      setTimeout(() => itemEl.classList.remove('executing'), 300);
    }
  }
}

async function executeMacro(cmd, itemEl) {
  qcMacroAbort = new AbortController();
  const signal = qcMacroAbort.signal;

  for (let i = 0; i < cmd.steps.length; i++) {
    if (signal.aborted) break;

    const step = cmd.steps[i];

    // Wait delay
    if (step.delay > 0) {
      await new Promise((resolve, reject) => {
        const timer = setTimeout(resolve, step.delay);
        signal.addEventListener(
          'abort',
          () => {
            clearTimeout(timer);
            resolve();
          },
          { once: true },
        );
      });
    }

    if (signal.aborted) break;

    // Send command
    await sendSerialData(unescapeCommand(step.command || ''));
  }

  qcMacroAbort = null;
}

function stopMacroExecution() {
  if (qcMacroAbort) {
    qcMacroAbort.abort();
    qcMacroAbort = null;
  }
}

async function sendSerialData(data) {
  try {
    await fetch('/api/serial/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: data }),
    });
  } catch (e) {
    console.error('Send serial data failed:', e);
  }
}

/* ===========================
   EDITOR MODAL
   =========================== */

function openQuickCommandEditor(id) {
  qcEditingId = id || null;
  const modal = document.getElementById('quickCommandEditorModal');
  if (!modal) return;

  const titleEl = document.getElementById('quickCommandEditorTitle');
  const nameInput = document.getElementById('qcName');
  const cmdInput = document.getElementById('qcCommand');
  const appendNl = document.getElementById('qcAppendNewline');
  const groupSelect = document.getElementById('qcGroup');
  const testBtn = document.getElementById('qcTestRunBtn');

  // Populate group dropdown
  populateGroupDropdown(groupSelect);

  if (id) {
    // Edit mode
    const commands = loadQuickCommands();
    const cmd = commands.find((c) => c.id === id);
    if (!cmd) return;

    if (titleEl)
      titleEl.textContent = t('quick_commands.edit_command', 'Edit Command');
    if (nameInput) nameInput.value = cmd.name || '';

    if (cmd.type === 'macro') {
      document.querySelector('input[name="qcType"][value="macro"]').checked =
        true;
      onQcTypeChange();
      renderMacroSteps(cmd.steps || []);
    } else {
      document.querySelector('input[name="qcType"][value="single"]').checked =
        true;
      onQcTypeChange();
      if (cmdInput) cmdInput.value = escapeCommandForDisplay(cmd.command || '');
      if (appendNl) appendNl.checked = cmd.appendNewline !== false;
    }

    if (groupSelect) groupSelect.value = cmd.group || '';
  } else {
    // New mode
    if (titleEl)
      titleEl.textContent = t('quick_commands.new_command', 'New Command');
    if (nameInput) nameInput.value = '';
    if (cmdInput) cmdInput.value = '';
    if (appendNl) appendNl.checked = true;
    document.querySelector('input[name="qcType"][value="single"]').checked =
      true;
    onQcTypeChange();
    if (groupSelect) groupSelect.value = '';
  }

  // Show test run only when connected
  if (testBtn) {
    testBtn.style.display =
      window.FPBState && window.FPBState.isConnected ? '' : 'none';
  }

  modal.classList.add('show');
}

function closeQuickCommandEditor() {
  const modal = document.getElementById('quickCommandEditorModal');
  if (modal) modal.classList.remove('show');
  qcEditingId = null;
}

function onQcTypeChange() {
  const isMacro = document.querySelector(
    'input[name="qcType"][value="macro"]',
  ).checked;
  const singleSection = document.getElementById('qcSingleSection');
  const macroSection = document.getElementById('qcMacroSection');
  if (singleSection) singleSection.style.display = isMacro ? 'none' : '';
  if (macroSection) macroSection.style.display = isMacro ? '' : 'none';

  if (isMacro) {
    const stepList = document.getElementById('qcStepList');
    if (stepList && stepList.children.length === 0) {
      addMacroStep();
    }
  }
}

function onQcGroupChange() {
  const select = document.getElementById('qcGroup');
  const newGroupInput = document.getElementById('qcNewGroup');
  if (!select || !newGroupInput) return;

  if (select.value === '__new__') {
    newGroupInput.style.display = '';
    newGroupInput.focus();
  } else {
    newGroupInput.style.display = 'none';
    newGroupInput.value = '';
  }
}

function populateGroupDropdown(select) {
  if (!select) return;
  const commands = loadQuickCommands();
  const groups = [...new Set(commands.map((c) => c.group).filter(Boolean))];

  select.innerHTML =
    '<option value="" data-i18n="quick_commands.no_group">No Group</option>';
  for (const g of groups) {
    select.innerHTML +=
      '<option value="' + escapeHtml(g) + '">' + escapeHtml(g) + '</option>';
  }
  select.innerHTML +=
    '<option value="__new__" data-i18n="quick_commands.new_group">+ New Group...</option>';

  if (typeof translatePage === 'function') translatePage();
}

/* ===========================
   MACRO STEP EDITOR
   =========================== */

let qcDragItem = null;

function setupStepDrag(step) {
  const handle = step.querySelector('.qc-step-drag');
  if (!handle) return;

  handle.addEventListener('mousedown', (e) => {
    qcDragItem = step;
    step.classList.add('qc-step-dragging');
    e.preventDefault();
  });

  step.addEventListener('dragover', (e) => {
    e.preventDefault();
    if (!qcDragItem || qcDragItem === step) return;
    const rect = step.getBoundingClientRect();
    const mid = rect.top + rect.height / 2;
    if (e.clientY < mid) {
      step.parentElement.insertBefore(qcDragItem, step);
    } else {
      step.parentElement.insertBefore(qcDragItem, step.nextSibling);
    }
  });
}

function initStepDragListeners() {
  document.addEventListener('mousemove', (e) => {
    if (!qcDragItem) return;
    const stepList = document.getElementById('qcStepList');
    if (!stepList) return;
    for (const child of stepList.children) {
      if (child === qcDragItem) continue;
      const rect = child.getBoundingClientRect();
      if (e.clientY >= rect.top && e.clientY <= rect.bottom) {
        const mid = rect.top + rect.height / 2;
        if (e.clientY < mid) {
          stepList.insertBefore(qcDragItem, child);
        } else {
          stepList.insertBefore(qcDragItem, child.nextSibling);
        }
        break;
      }
    }
  });

  document.addEventListener('mouseup', () => {
    if (qcDragItem) {
      qcDragItem.classList.remove('qc-step-dragging');
      qcDragItem = null;
      updateMacroSummary();
    }
  });
}

function addMacroStep(command, delay) {
  const stepList = document.getElementById('qcStepList');
  if (!stepList) return;

  const idx = stepList.children.length;
  const step = document.createElement('div');
  step.className = 'qc-step';
  step.innerHTML =
    '<span class="qc-step-drag" title="Drag to reorder">≡</span>' +
    '<input type="text" class="vscode-input qc-step-cmd" value="' +
    escapeHtml(command || '') +
    '" placeholder="command" style="font-family: monospace">' +
    '<input type="number" class="vscode-input qc-step-delay" value="' +
    (delay || (idx === 0 ? 0 : 500)) +
    '" min="0" step="100" title="Delay (ms)"> ' +
    '<span class="qc-step-delay-unit">ms</span>' +
    '<button class="qc-action-btn" onclick="this.parentElement.remove(); updateMacroSummary()" title="Remove">' +
    '<i class="codicon codicon-close"></i></button>';

  setupStepDrag(step);
  stepList.appendChild(step);
  updateMacroSummary();

  // Focus the new command input
  const cmdInput = step.querySelector('.qc-step-cmd');
  if (cmdInput) cmdInput.focus();
}

function renderMacroSteps(steps) {
  const stepList = document.getElementById('qcStepList');
  if (!stepList) return;
  stepList.innerHTML = '';
  for (const s of steps) {
    addMacroStep(escapeCommandForDisplay(s.command || ''), s.delay || 0);
  }
}

function updateMacroSummary() {
  const stepList = document.getElementById('qcStepList');
  const summary = document.getElementById('qcMacroSummary');
  if (!stepList || !summary) return;

  const count = stepList.children.length;
  let totalDelay = 0;
  for (const step of stepList.children) {
    const delayInput = step.querySelector('.qc-step-delay');
    totalDelay += parseInt(delayInput?.value || 0, 10);
  }

  const seconds = (totalDelay / 1000).toFixed(1);
  summary.textContent = t(
    'quick_commands.macro_summary',
    'Total: {{count}} commands, ~{{seconds}}s',
    { count, seconds },
  );
}

function collectMacroSteps() {
  const stepList = document.getElementById('qcStepList');
  if (!stepList) return [];
  const steps = [];
  for (const step of stepList.children) {
    const cmd = step.querySelector('.qc-step-cmd')?.value || '';
    const delay = parseInt(
      step.querySelector('.qc-step-delay')?.value || 0,
      10,
    );
    steps.push({ command: cmd, delay: Math.max(0, delay) });
  }
  return steps;
}

/* ===========================
   SAVE / DELETE
   =========================== */

function saveQuickCommand() {
  const isMacro = document.querySelector(
    'input[name="qcType"][value="macro"]',
  ).checked;
  const name = document.getElementById('qcName')?.value?.trim();
  const groupSelect = document.getElementById('qcGroup');
  const newGroupInput = document.getElementById('qcNewGroup');

  let group = groupSelect?.value || '';
  if (group === '__new__') {
    group = newGroupInput?.value?.trim() || '';
  }

  const commands = loadQuickCommands();

  let cmd;
  if (qcEditingId) {
    cmd = commands.find((c) => c.id === qcEditingId);
    if (!cmd) return;
  } else {
    cmd = { id: generateId(), order: commands.length };
    commands.push(cmd);
  }

  cmd.type = isMacro ? 'macro' : 'single';
  cmd.group = group || null;

  if (isMacro) {
    const steps = collectMacroSteps();
    if (steps.length === 0) return;
    cmd.steps = steps;
    cmd.command = null;
    cmd.appendNewline = undefined;
    cmd.name = name || t('quick_commands.unnamed_macro', 'Macro');
  } else {
    const rawCmd = document.getElementById('qcCommand')?.value || '';
    const appendNl = document.getElementById('qcAppendNewline')?.checked;
    let finalCmd = rawCmd;
    if (appendNl && !rawCmd.endsWith('\\n')) {
      finalCmd = rawCmd + '\\n';
    }
    cmd.command = finalCmd;
    cmd.appendNewline = appendNl;
    cmd.steps = null;
    cmd.name =
      name ||
      rawCmd.replace(/\\n$/, '') ||
      t('quick_commands.unnamed', 'Command');
  }

  saveQuickCommands(commands);
  renderQuickCommands();
  closeQuickCommandEditor();
}

function deleteQuickCommand(id) {
  const commands = loadQuickCommands();
  const idx = commands.findIndex((c) => c.id === id);
  if (idx < 0) return;

  const cmd = commands[idx];
  const confirmMsg = t('quick_commands.confirm_delete', 'Delete "{{name}}"?', {
    name: cmd.name,
  });
  if (!confirm(confirmMsg)) return;

  commands.splice(idx, 1);
  saveQuickCommands(commands);
  renderQuickCommands();
}

function duplicateQuickCommand(id) {
  const commands = loadQuickCommands();
  const cmd = commands.find((c) => c.id === id);
  if (!cmd) return;

  const copy = JSON.parse(JSON.stringify(cmd));
  copy.id = generateId();
  copy.name = (copy.name || '') + ' (copy)';
  copy.order = commands.length;
  commands.push(copy);
  saveQuickCommands(commands);
  renderQuickCommands();
}

/* ===========================
   CONTEXT MENU
   =========================== */

function showQcContextMenu(event, id) {
  event.preventDefault();
  event.stopPropagation();
  qcContextTargetId = id;

  const menu = document.getElementById('qcContextMenu');
  if (!menu) return;

  menu.style.display = 'block';
  menu.style.left = event.clientX + 'px';
  menu.style.top = event.clientY + 'px';

  // Ensure menu stays within viewport
  requestAnimationFrame(() => {
    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      menu.style.left = window.innerWidth - rect.width - 4 + 'px';
    }
    if (rect.bottom > window.innerHeight) {
      menu.style.top = window.innerHeight - rect.height - 4 + 'px';
    }
  });

  // Close on next click
  setTimeout(() => {
    document.addEventListener('click', hideQcContextMenus, { once: true });
  }, 0);
}

function showQuickCommandMenu(event) {
  event.preventDefault();
  event.stopPropagation();

  const menu = document.getElementById('qcSectionMenu');
  if (!menu) return;

  menu.style.display = 'block';
  menu.style.left = event.clientX + 'px';
  menu.style.top = event.clientY + 'px';

  requestAnimationFrame(() => {
    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      menu.style.left = window.innerWidth - rect.width - 4 + 'px';
    }
    if (rect.bottom > window.innerHeight) {
      menu.style.top = window.innerHeight - rect.height - 4 + 'px';
    }
  });

  setTimeout(() => {
    document.addEventListener('click', hideQcContextMenus, { once: true });
  }, 0);
}

function hideQcContextMenus() {
  const menu1 = document.getElementById('qcContextMenu');
  const menu2 = document.getElementById('qcSectionMenu');
  if (menu1) menu1.style.display = 'none';
  if (menu2) menu2.style.display = 'none';
}

function qcContextAction(action) {
  hideQcContextMenus();
  const id = qcContextTargetId;
  if (!id) return;

  switch (action) {
    case 'execute':
      executeQuickCommand(id);
      break;
    case 'edit':
      openQuickCommandEditor(id);
      break;
    case 'duplicate':
      duplicateQuickCommand(id);
      break;
    case 'delete':
      deleteQuickCommand(id);
      break;
    case 'move':
      moveToGroup(id);
      break;
  }
  qcContextTargetId = null;
}

function moveToGroup(id) {
  const commands = loadQuickCommands();
  const cmd = commands.find((c) => c.id === id);
  if (!cmd) return;

  const groups = [...new Set(commands.map((c) => c.group).filter(Boolean))];
  const groupList =
    groups.length > 0
      ? '\n' + groups.map((g, i) => i + 1 + '. ' + g).join('\n')
      : '';
  const input = prompt(
    t('quick_commands.move_prompt', 'Enter group name (empty to ungroup):') +
      groupList,
    cmd.group || '',
  );
  if (input === null) return;

  cmd.group = input.trim() || null;
  saveQuickCommands(commands);
  renderQuickCommands();
}

/* ===========================
   IMPORT / EXPORT
   =========================== */

function exportQuickCommands() {
  hideQcContextMenus();
  const commands = loadQuickCommands();
  if (commands.length === 0) {
    alert(t('quick_commands.nothing_to_export', 'No commands to export'));
    return;
  }

  const data = JSON.stringify({ version: 1, commands: commands }, null, 2);
  const blob = new Blob([data], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'quick_commands.json';
  a.click();
  URL.revokeObjectURL(url);
}

function importQuickCommands() {
  hideQcContextMenus();
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json';
  input.onchange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result);
        if (!data.commands || !Array.isArray(data.commands)) {
          alert(t('quick_commands.invalid_format', 'Invalid file format'));
          return;
        }
        const existing = loadQuickCommands();
        let imported = 0;
        for (const cmd of data.commands) {
          // Assign new IDs to avoid conflicts
          cmd.id = generateId();
          cmd.order = existing.length + imported;
          existing.push(cmd);
          imported++;
        }
        saveQuickCommands(existing);
        renderQuickCommands();
        if (typeof showNotification === 'function') {
          showNotification(
            t('quick_commands.imported_count', 'Imported {{count}} commands', {
              count: imported,
            }),
            'success',
          );
        }
      } catch (err) {
        alert(
          t('quick_commands.import_error', 'Failed to import: ') + err.message,
        );
      }
    };
    reader.readAsText(file);
  };
  input.click();
}

function clearAllQuickCommands() {
  hideQcContextMenus();
  const commands = loadQuickCommands();
  if (commands.length === 0) return;

  if (
    !confirm(
      t('quick_commands.confirm_clear', 'Delete all {{count}} commands?', {
        count: commands.length,
      }),
    )
  ) {
    return;
  }
  saveQuickCommands([]);
  renderQuickCommands();
}

/* ===========================
   TEST RUN
   =========================== */

function testRunQuickCommand() {
  const state = window.FPBState;
  if (!state || !state.isConnected) {
    if (typeof log !== 'undefined') log.error('Not connected');
    return;
  }

  const isMacro = document.querySelector(
    'input[name="qcType"][value="macro"]',
  ).checked;

  if (isMacro) {
    const steps = collectMacroSteps();
    if (steps.length === 0) return;
    const tempCmd = { type: 'macro', steps: steps };
    executeMacro(tempCmd, null);
  } else {
    const rawCmd = document.getElementById('qcCommand')?.value || '';
    const appendNl = document.getElementById('qcAppendNewline')?.checked;
    let data = rawCmd;
    if (appendNl && !rawCmd.endsWith('\\n')) data = rawCmd + '\\n';
    sendSerialData(unescapeCommand(data));
  }
}

/* ===========================
   KEYBOARD SHORTCUT (F4)
   =========================== */

function initQuickCommandKeyboard() {
  document.addEventListener('keydown', (e) => {
    // Ignore if typing in input/textarea
    if (
      e.target.tagName === 'INPUT' ||
      e.target.tagName === 'TEXTAREA' ||
      e.target.tagName === 'SELECT'
    )
      return;
    // Escape closes menus
    if (e.key === 'Escape') {
      hideQcContextMenus();
    }
  });
}

/* ===========================
   INIT
   =========================== */

function initQuickCommands() {
  renderQuickCommands();
  initQuickCommandKeyboard();
  initStepDragListeners();
}

// Auto-init when DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initQuickCommands);
} else {
  initQuickCommands();
}

/* ===========================
   EXPORTS
   =========================== */
window.loadQuickCommands = loadQuickCommands;
window.saveQuickCommands = saveQuickCommands;
window.renderQuickCommands = renderQuickCommands;
window.executeQuickCommand = executeQuickCommand;
window.stopMacroExecution = stopMacroExecution;
window.openQuickCommandEditor = openQuickCommandEditor;
window.closeQuickCommandEditor = closeQuickCommandEditor;
window.onQcTypeChange = onQcTypeChange;
window.onQcGroupChange = onQcGroupChange;
window.addMacroStep = addMacroStep;
window.updateMacroSummary = updateMacroSummary;
window.saveQuickCommand = saveQuickCommand;
window.deleteQuickCommand = deleteQuickCommand;
window.duplicateQuickCommand = duplicateQuickCommand;
window.showQcContextMenu = showQcContextMenu;
window.showQuickCommandMenu = showQuickCommandMenu;
window.hideQcContextMenus = hideQcContextMenus;
window.qcContextAction = qcContextAction;
window.exportQuickCommands = exportQuickCommands;
window.importQuickCommands = importQuickCommands;
window.clearAllQuickCommands = clearAllQuickCommands;
window.testRunQuickCommand = testRunQuickCommand;
window.initQuickCommands = initQuickCommands;
window.unescapeCommand = unescapeCommand;
window.escapeCommandForDisplay = escapeCommandForDisplay;
window.generateId = generateId;
window.sendSerialData = sendSerialData;
window.moveToGroup = moveToGroup;
window.initStepDragListeners = initStepDragListeners;
