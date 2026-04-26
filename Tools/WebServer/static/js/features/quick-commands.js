/*========================================
  FPBInject Workbench - Quick Commands Module
  ========================================*/

/* ===========================
   CONSTANTS & STATE
   =========================== */
const QC_STORAGE_KEY = 'fpbinject-quick-commands';
const QC_GROUP_META_KEY = 'fpbinject-quick-command-groups';
let qcEditingId = null; // ID of command being edited, null = new
let qcContextTargetId = null; // ID of command for context menu
let qcGroupContextTargetName = null; // Name of group for context menu
let qcMacroAbort = null; // AbortController for macro execution
let qcExecuting = false; // Mutex: prevent concurrent command execution
let qcDragItem = null; // Currently dragged command item
let qcDragGroup = null; // Currently dragged group element

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

function loadGroupMeta() {
  try {
    const raw = localStorage.getItem(QC_GROUP_META_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error('Failed to load group meta:', e);
    return [];
  }
}

function saveGroupMeta(groups) {
  try {
    localStorage.setItem(QC_GROUP_META_KEY, JSON.stringify(groups));
  } catch (e) {
    console.error('Failed to save group meta:', e);
  }
}

function ensureGroupMeta(commands) {
  const meta = loadGroupMeta();
  const usedGroups = new Set(commands.map((c) => c.group).filter(Boolean));

  // Add missing groups
  for (const name of usedGroups) {
    if (!meta.find((g) => g.name === name)) {
      meta.push({ name, order: meta.length });
    }
  }

  // Remove orphan groups
  const cleaned = meta.filter((g) => usedGroups.has(g.name));

  // Re-index order
  cleaned.forEach((g, i) => (g.order = i));

  saveGroupMeta(cleaned);
  return cleaned;
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

  const groupMeta = ensureGroupMeta(commands);

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

  // Sort groups by meta order
  const sortedGroupNames = groupMeta
    .slice()
    .sort((a, b) => a.order - b.order)
    .map((g) => g.name)
    .filter((name) => groups[name]);

  // Render groups in order
  for (const groupName of sortedGroupNames) {
    const groupCmds = groups[groupName];
    const groupEl = document.createElement('div');
    groupEl.className = 'qc-group';
    groupEl.dataset.groupName = groupName;
    groupEl.setAttribute('draggable', 'true');
    groupEl.innerHTML =
      '<div class="qc-group-header" onclick="this.parentElement.classList.toggle(\'collapsed\')">' +
      '<span class="qc-group-drag-handle" onmousedown="event.stopPropagation()" title="' +
      t('quick_commands.drag_to_reorder', 'Drag to reorder') +
      '">≡</span>' +
      '<i class="codicon codicon-chevron-down qc-group-chevron"></i>' +
      '<i class="codicon codicon-folder"></i>' +
      '<span class="qc-group-name">' +
      escapeHtml(groupName) +
      '</span>' +
      '<button class="qc-action-btn qc-group-menu-btn" onclick="event.stopPropagation(); showGroupContextMenu(event, \'' +
      escapeHtml(groupName).replace(/'/g, "\\'") +
      '\')" title="' +
      t('quick_commands.more', 'More') +
      '">' +
      '<i class="codicon codicon-ellipsis"></i></button>' +
      '</div>';
    groupEl.oncontextmenu = (e) => {
      e.preventDefault();
      showGroupContextMenu(e, groupName);
    };
    const itemsEl = document.createElement('div');
    itemsEl.className = 'qc-group-items';
    // Sort commands by order within group
    groupCmds.sort((a, b) => (a.order || 0) - (b.order || 0));
    for (const cmd of groupCmds) {
      itemsEl.appendChild(createCommandItem(cmd));
    }
    groupEl.appendChild(itemsEl);
    setupGroupDrag(groupEl);
    list.appendChild(groupEl);
  }

  // Render ungrouped (sorted by order)
  ungrouped.sort((a, b) => (a.order || 0) - (b.order || 0));
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
  item.setAttribute('draggable', 'true');

  const icon = cmd.type === 'macro' ? 'codicon-layers' : 'codicon-terminal';
  const label = escapeHtml(cmd.name || cmd.command || 'Unnamed');
  const badge =
    cmd.type === 'macro' && cmd.steps
      ? '<span class="qc-badge">' + cmd.steps.length + ' cmds</span>'
      : '';

  item.innerHTML =
    '<span class="qc-item-drag-handle" title="' +
    t('quick_commands.drag_command', 'Drag to reorder') +
    '">≡</span>' +
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
    '\')" title="' +
    t('quick_commands.execute', 'Execute') +
    '">' +
    '<i class="codicon codicon-play"></i></button>' +
    '<button class="qc-action-btn" onclick="event.stopPropagation(); showQcContextMenu(event, \'' +
    cmd.id +
    '\')" title="' +
    t('quick_commands.more', 'More') +
    '">' +
    '<i class="codicon codicon-ellipsis"></i></button>' +
    '</span>';

  item.ondblclick = () => executeQuickCommand(cmd.id);
  item.oncontextmenu = (e) => {
    e.preventDefault();
    showQcContextMenu(e, cmd.id);
  };

  setupCommandDrag(item);

  return item;
}

/* ===========================
   COMMAND DRAG & DROP
   =========================== */

function setupCommandDrag(item) {
  item.addEventListener('dragstart', (e) => {
    qcDragItem = item;
    qcDragGroup = null;
    item.classList.add('qc-dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', item.dataset.id);
  });
  item.addEventListener('dragend', () => {
    item.classList.remove('qc-dragging');
    qcDragItem = null;
    persistCommandOrder();
  });
  item.addEventListener('dragover', (e) => {
    e.preventDefault();
    if (!qcDragItem || qcDragItem === item || qcDragGroup) return;
    e.dataTransfer.dropEffect = 'move';
    const rect = item.getBoundingClientRect();
    const mid = rect.top + rect.height / 2;
    if (e.clientY < mid) {
      item.parentElement.insertBefore(qcDragItem, item);
    } else {
      item.parentElement.insertBefore(qcDragItem, item.nextSibling);
    }
  });
}

function setupGroupDrag(groupEl) {
  const header = groupEl.querySelector('.qc-group-header');
  if (!header) return;

  groupEl.addEventListener('dragstart', (e) => {
    // Only start group drag from the drag handle
    if (!e.target.classList.contains('qc-group-drag-handle')) {
      // Could be a command item drag, let it bubble
      return;
    }
    qcDragGroup = groupEl;
    qcDragItem = null;
    groupEl.classList.add('qc-dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', groupEl.dataset.groupName);
  });
  groupEl.addEventListener('dragend', () => {
    groupEl.classList.remove('qc-dragging');
    qcDragGroup = null;
    persistGroupOrder();
  });
  groupEl.addEventListener('dragover', (e) => {
    e.preventDefault();
    if (qcDragGroup && qcDragGroup !== groupEl) {
      // Group reorder
      e.dataTransfer.dropEffect = 'move';
      const rect = groupEl.getBoundingClientRect();
      const mid = rect.top + rect.height / 2;
      const list = groupEl.parentElement;
      if (e.clientY < mid) {
        list.insertBefore(qcDragGroup, groupEl);
      } else {
        list.insertBefore(qcDragGroup, groupEl.nextSibling);
      }
    } else if (qcDragItem && !qcDragGroup) {
      // Command dropped into group
      e.dataTransfer.dropEffect = 'move';
      const itemsEl = groupEl.querySelector('.qc-group-items');
      if (itemsEl && !itemsEl.contains(qcDragItem)) {
        itemsEl.appendChild(qcDragItem);
        // Update command group
        const cmdId = qcDragItem.dataset.id;
        const commands = loadQuickCommands();
        const cmd = commands.find((c) => c.id === cmdId);
        if (cmd) {
          cmd.group = groupEl.dataset.groupName;
          saveQuickCommands(commands);
        }
      }
    }
  });
}

function persistCommandOrder() {
  const list = document.getElementById('quickCommandList');
  if (!list) return;
  const commands = loadQuickCommands();
  let order = 0;

  // Walk DOM to get current visual order
  const allItems = list.querySelectorAll('.qc-item');
  for (const itemEl of allItems) {
    const cmd = commands.find((c) => c.id === itemEl.dataset.id);
    if (cmd) {
      cmd.order = order++;
      // Update group based on parent
      const groupEl = itemEl.closest('.qc-group');
      cmd.group = groupEl ? groupEl.dataset.groupName : null;
    }
  }
  saveQuickCommands(commands);
}

function persistGroupOrder() {
  const list = document.getElementById('quickCommandList');
  if (!list) return;
  const meta = loadGroupMeta();
  const groupEls = list.querySelectorAll('.qc-group');
  let order = 0;
  for (const el of groupEls) {
    const name = el.dataset.groupName;
    const entry = meta.find((g) => g.name === name);
    if (entry) entry.order = order++;
  }
  saveGroupMeta(meta);
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

  if (qcExecuting) {
    if (typeof log !== 'undefined')
      log.warn('A command is already executing, please wait');
    return;
  }

  const commands = loadQuickCommands();
  const cmd = commands.find((c) => c.id === id);
  if (!cmd) return;

  qcExecuting = true;

  // Visual feedback
  const itemEl = document.querySelector('.qc-item[data-id="' + id + '"]');
  if (itemEl) itemEl.classList.add('executing');

  try {
    if (cmd.type === 'macro' && cmd.steps) {
      await executeMacro(cmd, itemEl);
    } else {
      let data = unescapeCommand(cmd.command || '');
      if (cmd.appendNewline !== false && !data.endsWith('\n')) {
        data += '\n';
      }
      await sendTerminalCommand(data);
    }
  } finally {
    qcExecuting = false;
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
    let stepData = unescapeCommand(step.command || '');
    if (step.appendNewline !== false && !stepData.endsWith('\n')) {
      stepData += '\n';
    }
    await sendTerminalCommand(stepData);
  }

  qcMacroAbort = null;
}

function stopMacroExecution() {
  if (qcMacroAbort) {
    qcMacroAbort.abort();
    qcMacroAbort = null;
  }
  qcExecuting = false;
}

async function sendSerialData(data) {
  // Delegate to shared sendTerminalCommand
  await sendTerminalCommand(data);
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
      let displayCmd = cmd.command || '';
      // Strip trailing \n that was auto-appended by save logic,
      // since it's controlled by the appendNewline checkbox
      if (cmd.appendNewline !== false && displayCmd.endsWith('\\n')) {
        displayCmd = displayCmd.slice(0, -2);
      }
      if (cmdInput) cmdInput.value = displayCmd;
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

let qcStepDragItem = null;

function setupStepDrag(step) {
  const handle = step.querySelector('.qc-step-drag');
  if (!handle) return;

  handle.addEventListener('mousedown', (e) => {
    qcStepDragItem = step;
    step.classList.add('qc-step-dragging');
    e.preventDefault();
  });

  step.addEventListener('dragover', (e) => {
    e.preventDefault();
    if (!qcStepDragItem || qcStepDragItem === step) return;
    const rect = step.getBoundingClientRect();
    const mid = rect.top + rect.height / 2;
    if (e.clientY < mid) {
      step.parentElement.insertBefore(qcStepDragItem, step);
    } else {
      step.parentElement.insertBefore(qcStepDragItem, step.nextSibling);
    }
  });
}

function initStepDragListeners() {
  document.addEventListener('mousemove', (e) => {
    if (!qcStepDragItem) return;
    const stepList = document.getElementById('qcStepList');
    if (!stepList) return;
    for (const child of stepList.children) {
      if (child === qcStepDragItem) continue;
      const rect = child.getBoundingClientRect();
      if (e.clientY >= rect.top && e.clientY <= rect.bottom) {
        const mid = rect.top + rect.height / 2;
        if (e.clientY < mid) {
          stepList.insertBefore(qcStepDragItem, child);
        } else {
          stepList.insertBefore(qcStepDragItem, child.nextSibling);
        }
        break;
      }
    }
  });

  document.addEventListener('mouseup', () => {
    if (qcStepDragItem) {
      qcStepDragItem.classList.remove('qc-step-dragging');
      qcStepDragItem = null;
      updateMacroSummary();
    }
  });
}

function addMacroStep(command, delay, appendNewline) {
  const stepList = document.getElementById('qcStepList');
  if (!stepList) return;

  const step = document.createElement('div');
  step.className = 'qc-step';
  const nlChecked = appendNewline !== false ? ' checked' : '';
  step.innerHTML =
    '<span class="qc-step-drag" title="' +
    t('quick_commands.drag_to_reorder', 'Drag to reorder') +
    '">≡</span>' +
    '<input type="text" class="vscode-input qc-step-cmd" value="' +
    escapeHtml(command || '') +
    '" placeholder="command" style="font-family: monospace">' +
    '<label class="qc-step-nl" title="' +
    t('quick_commands.append_newline', 'Append newline (\\n)') +
    '"><input type="checkbox" class="qc-step-nl-check"' +
    nlChecked +
    '>\\n</label>' +
    '<input type="number" class="vscode-input qc-step-delay" value="' +
    (delay != null ? delay : 0) +
    '" min="0" step="100" title="Delay (ms)"> ' +
    '<span class="qc-step-delay-unit">ms</span>' +
    '<button class="qc-action-btn" onclick="this.parentElement.remove(); updateMacroSummary()" title="' +
    t('quick_commands.remove', 'Remove') +
    '">' +
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
    addMacroStep(
      s.command || '',
      s.delay != null ? s.delay : 0,
      s.appendNewline,
    );
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
    const appendNl = step.querySelector('.qc-step-nl-check')?.checked !== false;
    steps.push({
      command: cmd,
      delay: Math.max(0, delay),
      appendNewline: appendNl,
    });
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
  // Sync group meta if new group was created
  ensureGroupMeta(commands);
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
  ensureGroupMeta(commands);
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
   GROUP OPERATIONS
   =========================== */

function renameGroup(oldName) {
  if (!oldName) return;
  const newName = prompt(
    t('quick_commands.rename_prompt', 'Enter new group name:'),
    oldName,
  );
  if (newName === null || newName.trim() === '') return;

  const trimmed = newName.trim();
  const commands = loadQuickCommands();

  // Update all commands in this group
  for (const cmd of commands) {
    if (cmd.group === oldName) {
      cmd.group = trimmed;
    }
  }
  saveQuickCommands(commands);

  // Update group meta
  const meta = loadGroupMeta();
  const existing = meta.find((g) => g.name === trimmed);
  const old = meta.find((g) => g.name === oldName);
  if (existing && old) {
    // Merge: remove old entry (commands already moved)
    const idx = meta.indexOf(old);
    if (idx >= 0) meta.splice(idx, 1);
  } else if (old) {
    old.name = trimmed;
  }
  saveGroupMeta(meta);
  renderQuickCommands();
}

function deleteGroup(groupName) {
  if (!groupName) return;
  const confirmMsg = t(
    'quick_commands.confirm_delete_group',
    'Delete group "{{name}}"? Commands will be ungrouped.',
    { name: groupName },
  );
  if (!confirm(confirmMsg)) return;

  const commands = loadQuickCommands();
  for (const cmd of commands) {
    if (cmd.group === groupName) {
      cmd.group = null;
    }
  }
  saveQuickCommands(commands);
  ensureGroupMeta(commands);
  renderQuickCommands();
}

/* ===========================
   CONTEXT MENUS
   =========================== */

function showQcContextMenu(event, id) {
  event.preventDefault();
  event.stopPropagation();
  qcContextTargetId = id;

  hideQcContextMenus();
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

function showGroupContextMenu(event, groupName) {
  event.preventDefault();
  event.stopPropagation();
  qcGroupContextTargetName = groupName;

  hideQcContextMenus();
  const menu = document.getElementById('qcGroupContextMenu');
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

function showQuickCommandMenu(event) {
  event.preventDefault();
  event.stopPropagation();

  hideQcContextMenus();
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
  const ids = ['qcContextMenu', 'qcSectionMenu', 'qcGroupContextMenu'];
  for (const id of ids) {
    const menu = document.getElementById(id);
    if (menu) menu.style.display = 'none';
  }
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

function qcGroupContextAction(action) {
  hideQcContextMenus();
  const name = qcGroupContextTargetName;
  if (!name) return;

  switch (action) {
    case 'rename':
      renameGroup(name);
      break;
    case 'delete':
      deleteGroup(name);
      break;
  }
  qcGroupContextTargetName = null;
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
  ensureGroupMeta(commands);
  renderQuickCommands();
}

/* ===========================
   SELECTIVE EXPORT
   =========================== */

function openExportDialog() {
  hideQcContextMenus();
  const commands = loadQuickCommands();
  if (commands.length === 0) {
    alert(t('quick_commands.nothing_to_export', 'No commands to export'));
    return;
  }

  const modal = document.getElementById('qcExportModal');
  if (!modal) return;

  const listEl = document.getElementById('qcExportList');
  if (!listEl) return;

  const groupMeta = ensureGroupMeta(commands);

  // Build checkbox tree
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

  let html = '';

  // Select All
  html +=
    '<label class="qc-export-item qc-export-select-all">' +
    '<input type="checkbox" checked onchange="onExportSelectAll(this.checked)" />' +
    '<span data-i18n="quick_commands.select_all">' +
    t('quick_commands.select_all', 'Select All') +
    '</span></label>';

  const sortedGroups = groupMeta
    .slice()
    .sort((a, b) => a.order - b.order)
    .map((g) => g.name)
    .filter((n) => groups[n]);

  for (const gName of sortedGroups) {
    html +=
      '<div class="qc-export-group">' +
      '<label class="qc-export-item qc-export-group-label">' +
      '<input type="checkbox" checked data-export-group="' +
      escapeHtml(gName) +
      '" onchange="onExportGroupToggle(this)" />' +
      '<i class="codicon codicon-folder"></i> ' +
      escapeHtml(gName) +
      '</label>';
    for (const cmd of groups[gName]) {
      const label =
        cmd.type === 'macro'
          ? '[Macro] ' + escapeHtml(cmd.name || '')
          : escapeHtml(cmd.name || cmd.command || '');
      html +=
        '<label class="qc-export-item qc-export-cmd" style="padding-left: 24px">' +
        '<input type="checkbox" checked data-export-id="' +
        cmd.id +
        '" data-export-group-name="' +
        escapeHtml(gName) +
        '" onchange="onExportItemToggle()" />' +
        label +
        '</label>';
    }
    html += '</div>';
  }

  if (ungrouped.length > 0) {
    html +=
      '<div class="qc-export-group">' +
      '<label class="qc-export-item qc-export-group-label">' +
      '<input type="checkbox" checked data-export-group="__ungrouped__" onchange="onExportGroupToggle(this)" />' +
      '<i class="codicon codicon-folder-opened"></i> ' +
      t('quick_commands.ungrouped', '(Ungrouped)') +
      '</label>';
    for (const cmd of ungrouped) {
      const label =
        cmd.type === 'macro'
          ? '[Macro] ' + escapeHtml(cmd.name || '')
          : escapeHtml(cmd.name || cmd.command || '');
      html +=
        '<label class="qc-export-item qc-export-cmd" style="padding-left: 24px">' +
        '<input type="checkbox" checked data-export-id="' +
        cmd.id +
        '" data-export-group-name="__ungrouped__" onchange="onExportItemToggle()" />' +
        label +
        '</label>';
    }
    html += '</div>';
  }

  listEl.innerHTML = html;
  updateExportCount();
  modal.classList.add('show');
}

function onExportSelectAll(checked) {
  const modal = document.getElementById('qcExportModal');
  if (!modal) return;
  const boxes = modal.querySelectorAll('input[type="checkbox"]');
  for (const box of boxes) {
    box.checked = checked;
    box.indeterminate = false;
  }
  updateExportCount();
}

function onExportGroupToggle(groupCheckbox) {
  const groupName = groupCheckbox.getAttribute('data-export-group');
  const modal = document.getElementById('qcExportModal');
  if (!modal) return;
  const items = modal.querySelectorAll(
    'input[data-export-group-name="' + groupName + '"]',
  );
  for (const item of items) {
    item.checked = groupCheckbox.checked;
  }
  updateExportSelectAll();
  updateExportCount();
}

function onExportItemToggle() {
  // Update parent group checkbox state
  const modal = document.getElementById('qcExportModal');
  if (!modal) return;
  const groupCheckboxes = modal.querySelectorAll('input[data-export-group]');
  for (const gc of groupCheckboxes) {
    const groupName = gc.getAttribute('data-export-group');
    const items = modal.querySelectorAll(
      'input[data-export-group-name="' + groupName + '"]',
    );
    const checkedCount = Array.from(items).filter((i) => i.checked).length;
    if (checkedCount === 0) {
      gc.checked = false;
      gc.indeterminate = false;
    } else if (checkedCount === items.length) {
      gc.checked = true;
      gc.indeterminate = false;
    } else {
      gc.checked = false;
      gc.indeterminate = true;
    }
  }
  updateExportSelectAll();
  updateExportCount();
}

function updateExportSelectAll() {
  const modal = document.getElementById('qcExportModal');
  if (!modal) return;
  const allItems = modal.querySelectorAll('input[data-export-id]');
  const checkedCount = Array.from(allItems).filter((i) => i.checked).length;
  const selectAll = modal.querySelector('.qc-export-select-all input');
  if (!selectAll) return;
  if (checkedCount === 0) {
    selectAll.checked = false;
    selectAll.indeterminate = false;
  } else if (checkedCount === allItems.length) {
    selectAll.checked = true;
    selectAll.indeterminate = false;
  } else {
    selectAll.checked = false;
    selectAll.indeterminate = true;
  }
}

function updateExportCount() {
  const modal = document.getElementById('qcExportModal');
  if (!modal) return;
  const allItems = modal.querySelectorAll('input[data-export-id]');
  const selected = Array.from(allItems).filter((i) => i.checked).length;
  const total = allItems.length;
  const countEl = document.getElementById('qcExportCount');
  if (countEl) {
    countEl.textContent = t(
      'quick_commands.selected_count',
      'Selected: {{selected}} / {{total}} commands',
      { selected, total },
    );
  }
  const exportBtn = document.getElementById('qcExportBtn');
  if (exportBtn) exportBtn.disabled = selected === 0;
}

function executeExport() {
  const modal = document.getElementById('qcExportModal');
  if (!modal) return;

  const selectedIds = new Set();
  const items = modal.querySelectorAll('input[data-export-id]:checked');
  for (const item of items) {
    selectedIds.add(item.getAttribute('data-export-id'));
  }

  if (selectedIds.size === 0) return;

  const commands = loadQuickCommands();
  const exported = commands.filter((c) => selectedIds.has(c.id));

  // Only include groups that have exported commands
  const usedGroups = new Set(exported.map((c) => c.group).filter(Boolean));
  const groupMeta = loadGroupMeta().filter((g) => usedGroups.has(g.name));

  const data = JSON.stringify(
    { version: 2, groups: groupMeta, commands: exported },
    null,
    2,
  );
  const blob = new Blob([data], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'quick_commands.json';
  a.click();
  URL.revokeObjectURL(url);

  modal.classList.remove('show');
}

function closeExportDialog() {
  const modal = document.getElementById('qcExportModal');
  if (modal) modal.classList.remove('show');
}

/* ===========================
   IMPORT WITH CONFLICT HANDLING
   =========================== */

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
        if (data.commands.length === 0) {
          alert(t('quick_commands.nothing_to_import', 'No commands to import'));
          return;
        }
        openImportDialog(data);
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

function resolveImportConflicts(incoming, existing) {
  const conflicts = [];
  for (const inc of incoming) {
    const match = existing.find((ex) => {
      if (ex.name !== inc.name || ex.type !== inc.type) return false;
      if (inc.type === 'single') return ex.command === inc.command;
      return true; // macro: name + type match is enough
    });
    if (match) {
      conflicts.push({ incoming: inc, existing: match });
    }
  }
  return conflicts;
}

function openImportDialog(fileData) {
  const modal = document.getElementById('qcImportModal');
  if (!modal) return;

  const existing = loadQuickCommands();
  const incoming = fileData.commands || [];
  const incomingGroups = fileData.groups || [];
  const conflicts = resolveImportConflicts(incoming, existing);
  const conflictIds = new Set(conflicts.map((c) => c.incoming.id));

  // Store on modal for later use
  modal._importData = {
    incoming,
    incomingGroups,
    existing,
    conflicts,
  };

  const listEl = document.getElementById('qcImportList');
  if (!listEl) return;

  // Build preview
  const groups = {};
  const ungrouped = [];
  for (const cmd of incoming) {
    if (cmd.group) {
      if (!groups[cmd.group]) groups[cmd.group] = [];
      groups[cmd.group].push(cmd);
    } else {
      ungrouped.push(cmd);
    }
  }

  let html = '';

  const renderCmd = (cmd) => {
    const conflict = conflicts.find((c) => c.incoming.id === cmd.id);
    const label =
      cmd.type === 'macro'
        ? '[Macro] ' + escapeHtml(cmd.name || '')
        : escapeHtml(cmd.name || cmd.command || '');
    let line =
      '<div class="qc-import-item" style="padding-left: 24px" data-import-id="' +
      cmd.id +
      '">';
    if (conflict) {
      line +=
        '<span class="qc-import-conflict-icon" title="' +
        t('quick_commands.conflict', 'Conflict') +
        '">⚠</span> ' +
        '<span class="qc-import-label">' +
        label +
        '</span>' +
        '<span class="qc-import-conflict-actions">' +
        '<button class="vscode-btn secondary qc-import-skip-btn" data-import-id="' +
        cmd.id +
        '" onclick="setImportConflictAction(this, \'skip\')">' +
        t('quick_commands.conflict_skip', 'Skip') +
        '</button>' +
        '<button class="vscode-btn secondary qc-import-overwrite-btn" data-import-id="' +
        cmd.id +
        '" onclick="setImportConflictAction(this, \'overwrite\')">' +
        t('quick_commands.conflict_overwrite', 'Overwrite') +
        '</button>' +
        '</span>';
    } else {
      line +=
        '<label><input type="checkbox" checked data-import-id="' +
        cmd.id +
        '" onchange="updateImportSummary()" />' +
        label +
        '</label>';
    }
    line += '</div>';
    return line;
  };

  // Render grouped
  const sortedGroupNames =
    incomingGroups.length > 0
      ? incomingGroups
          .slice()
          .sort((a, b) => a.order - b.order)
          .map((g) => g.name)
          .filter((n) => groups[n])
      : Object.keys(groups);

  for (const gName of sortedGroupNames) {
    html +=
      '<div class="qc-import-group">' +
      '<div class="qc-import-group-label">' +
      '<i class="codicon codicon-folder"></i> ' +
      escapeHtml(gName) +
      '</div>';
    for (const cmd of groups[gName]) {
      html += renderCmd(cmd);
    }
    html += '</div>';
  }

  if (ungrouped.length > 0) {
    html +=
      '<div class="qc-import-group">' +
      '<div class="qc-import-group-label">' +
      '<i class="codicon codicon-folder-opened"></i> ' +
      t('quick_commands.ungrouped', '(Ungrouped)') +
      '</div>';
    for (const cmd of ungrouped) {
      html += renderCmd(cmd);
    }
    html += '</div>';
  }

  listEl.innerHTML = html;

  // Set default conflict actions to 'skip'
  const skipBtns = listEl.querySelectorAll('.qc-import-skip-btn');
  for (const btn of skipBtns) {
    btn.classList.add('active');
  }

  // Set strategy radio
  const strategyRadios = modal.querySelectorAll(
    'input[name="qcImportStrategy"]',
  );
  for (const r of strategyRadios) {
    r.checked = r.value === 'per_item';
  }

  updateImportSummary();
  modal.classList.add('show');
}

function setImportConflictAction(btn, action) {
  const id = btn.getAttribute('data-import-id');
  const row = btn.closest('.qc-import-item');
  if (!row) return;
  const skipBtn = row.querySelector('.qc-import-skip-btn');
  const overwriteBtn = row.querySelector('.qc-import-overwrite-btn');
  if (skipBtn) skipBtn.classList.toggle('active', action === 'skip');
  if (overwriteBtn)
    overwriteBtn.classList.toggle('active', action === 'overwrite');
  row.dataset.conflictAction = action;
  updateImportSummary();
}

function onImportStrategyChange(strategy) {
  const modal = document.getElementById('qcImportModal');
  if (!modal || !modal._importData) return;

  if (strategy === 'per_item') return; // Keep individual choices

  const action = strategy === 'skip_all' ? 'skip' : 'overwrite';
  const listEl = document.getElementById('qcImportList');
  if (!listEl) return;

  const conflictItems = listEl.querySelectorAll(
    '.qc-import-item[data-import-id]',
  );
  for (const item of conflictItems) {
    if (!item.querySelector('.qc-import-conflict-icon')) continue;
    item.dataset.conflictAction = action;
    const skipBtn = item.querySelector('.qc-import-skip-btn');
    const overwriteBtn = item.querySelector('.qc-import-overwrite-btn');
    if (skipBtn) skipBtn.classList.toggle('active', action === 'skip');
    if (overwriteBtn)
      overwriteBtn.classList.toggle('active', action === 'overwrite');
  }
  updateImportSummary();
}

function updateImportSummary() {
  const modal = document.getElementById('qcImportModal');
  if (!modal || !modal._importData) return;

  const listEl = document.getElementById('qcImportList');
  if (!listEl) return;

  const { conflicts } = modal._importData;
  let newCount = 0;
  let skipCount = 0;
  let overwriteCount = 0;

  // Count non-conflict checked items
  const checkboxes = listEl.querySelectorAll(
    'input[type="checkbox"][data-import-id]',
  );
  for (const cb of checkboxes) {
    if (cb.checked) newCount++;
  }

  // Count conflict actions
  const conflictItems = listEl.querySelectorAll('.qc-import-conflict-icon');
  for (const icon of conflictItems) {
    const row = icon.closest('.qc-import-item');
    if (row && row.dataset.conflictAction === 'overwrite') {
      overwriteCount++;
    } else {
      skipCount++;
    }
  }

  const summaryEl = document.getElementById('qcImportSummary');
  if (summaryEl) {
    summaryEl.textContent = t(
      'quick_commands.import_summary',
      'New: {{new}}  Conflicts: {{conflicts}}  Skip: {{skip}}',
      { new: newCount, conflicts: conflicts.length, skip: skipCount },
    );
  }
}

function executeImport() {
  const modal = document.getElementById('qcImportModal');
  if (!modal || !modal._importData) return;

  const { incoming, incomingGroups, existing, conflicts } = modal._importData;
  const listEl = document.getElementById('qcImportList');
  if (!listEl) return;

  const conflictMap = new Map();
  for (const c of conflicts) {
    conflictMap.set(c.incoming.id, c);
  }

  let imported = 0;

  for (const cmd of incoming) {
    const conflict = conflictMap.get(cmd.id);
    if (conflict) {
      // Check action
      const row = listEl.querySelector(
        '.qc-import-item[data-import-id="' + cmd.id + '"]',
      );
      const action = row ? row.dataset.conflictAction : 'skip';
      if (action === 'overwrite') {
        // Replace existing command data but keep local id
        const ex = conflict.existing;
        ex.name = cmd.name;
        ex.type = cmd.type;
        ex.command = cmd.command;
        ex.steps = cmd.steps;
        ex.appendNewline = cmd.appendNewline;
        ex.group = cmd.group;
        imported++;
      }
      // skip: do nothing
    } else {
      // Non-conflict: check if checkbox is checked
      const cb = listEl.querySelector(
        'input[type="checkbox"][data-import-id="' + cmd.id + '"]',
      );
      if (cb && cb.checked) {
        cmd.id = generateId();
        cmd.order = existing.length + imported;
        existing.push(cmd);
        imported++;
      }
    }
  }

  saveQuickCommands(existing);

  // Merge group meta
  if (incomingGroups.length > 0) {
    const meta = loadGroupMeta();
    for (const ig of incomingGroups) {
      if (!meta.find((g) => g.name === ig.name)) {
        meta.push({ name: ig.name, order: meta.length });
      }
    }
    saveGroupMeta(meta);
  }
  ensureGroupMeta(existing);

  renderQuickCommands();
  modal.classList.remove('show');

  if (typeof showNotification === 'function') {
    showNotification(
      t('quick_commands.imported_count', 'Imported {{count}} commands', {
        count: imported,
      }),
      'success',
    );
  }
}

function closeImportDialog() {
  const modal = document.getElementById('qcImportModal');
  if (modal) {
    modal.classList.remove('show');
    modal._importData = null;
  }
}

/* ===========================
   LEGACY EXPORT (replaced by selective)
   =========================== */

function exportQuickCommands() {
  openExportDialog();
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
  saveGroupMeta([]);
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
   KEYBOARD SHORTCUT
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
window.loadGroupMeta = loadGroupMeta;
window.saveGroupMeta = saveGroupMeta;
window.ensureGroupMeta = ensureGroupMeta;
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
window.showGroupContextMenu = showGroupContextMenu;
window.showQuickCommandMenu = showQuickCommandMenu;
window.hideQcContextMenus = hideQcContextMenus;
window.qcContextAction = qcContextAction;
window.qcGroupContextAction = qcGroupContextAction;
window.renameGroup = renameGroup;
window.deleteGroup = deleteGroup;
window.exportQuickCommands = exportQuickCommands;
window.openExportDialog = openExportDialog;
window.onExportSelectAll = onExportSelectAll;
window.onExportGroupToggle = onExportGroupToggle;
window.onExportItemToggle = onExportItemToggle;
window.updateExportCount = updateExportCount;
window.executeExport = executeExport;
window.closeExportDialog = closeExportDialog;
window.importQuickCommands = importQuickCommands;
window.resolveImportConflicts = resolveImportConflicts;
window.openImportDialog = openImportDialog;
window.setImportConflictAction = setImportConflictAction;
window.onImportStrategyChange = onImportStrategyChange;
window.updateImportSummary = updateImportSummary;
window.executeImport = executeImport;
window.closeImportDialog = closeImportDialog;
window.clearAllQuickCommands = clearAllQuickCommands;
window.testRunQuickCommand = testRunQuickCommand;
window.initQuickCommands = initQuickCommands;
window.unescapeCommand = unescapeCommand;
window.escapeCommandForDisplay = escapeCommandForDisplay;
window.generateId = generateId;
window.sendSerialData = sendSerialData;
window.moveToGroup = moveToGroup;
window.initStepDragListeners = initStepDragListeners;
window.collectMacroSteps = collectMacroSteps;
window.populateGroupDropdown = populateGroupDropdown;
window.persistCommandOrder = persistCommandOrder;
window.persistGroupOrder = persistGroupOrder;
window.renderMacroSteps = renderMacroSteps;
