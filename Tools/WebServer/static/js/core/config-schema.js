/*========================================
  FPBInject Workbench - Configuration Schema Module
  
  This module provides schema-driven configuration management.
  The schema is fetched from the backend and used to:
  - Dynamically render config UI
  - Load/save config values
  - Validate config values
  ========================================*/

// Cached schema
let _configSchema = null;

/**
 * Reset cached schema (for testing purposes).
 */
function resetConfigSchema() {
  _configSchema = null;
}

/**
 * Load configuration schema from backend.
 * @returns {Promise<Object>} Schema object with schema, groups, group_order
 */
async function loadConfigSchema() {
  if (_configSchema) return _configSchema;

  try {
    const res = await fetch('/api/config/schema');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    _configSchema = await res.json();
    return _configSchema;
  } catch (e) {
    console.error('Failed to load config schema:', e);
    return null;
  }
}

/**
 * Get cached schema (must call loadConfigSchema first).
 * @returns {Object|null} Cached schema
 */
function getConfigSchema() {
  return _configSchema;
}

/**
 * Convert snake_case to camelCase for element IDs.
 * @param {string} key - snake_case key
 * @returns {string} camelCase key
 */
function keyToElementId(key) {
  return key.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

/**
 * Get translated label for a config item.
 * @param {Object} item - Config item from schema
 * @returns {string} Translated label or original label
 */
function getConfigLabel(item) {
  if (typeof t === 'function' && isI18nReady()) {
    const key = `config.labels.${item.key}`;
    const translated = t(key);
    if (translated !== key) return translated;
  }
  return item.label;
}

/**
 * Get translated tooltip for a config item.
 * @param {Object} item - Config item from schema
 * @returns {string} Translated tooltip or original tooltip
 */
function getConfigTooltip(item) {
  if (typeof t === 'function' && isI18nReady()) {
    const key = `tooltips.${item.key}`;
    const translated = t(key);
    if (translated !== key) return translated;
  }
  return item.tooltip || '';
}

/**
 * Render a single config item as HTML.
 * @param {Object} item - Config item from schema
 * @returns {string} HTML string
 */
function renderConfigItem(item) {
  const elementId = keyToElementId(item.key);
  const tooltipText = getConfigTooltip(item);
  const tooltip = tooltipText ? ` title="${escapeHtml(tooltipText)}"` : '';

  switch (item.config_type) {
    case 'file_path':
    case 'dir_path':
    case 'path':
      return renderPathInput(item, elementId, tooltip);
    case 'number':
      return renderNumberInput(item, elementId, tooltip);
    case 'boolean':
      return renderCheckbox(item, elementId, tooltip);
    case 'select':
      return renderSelect(item, elementId, tooltip);
    case 'path_list':
      return renderPathList(item, elementId, tooltip);
    default:
      return renderTextInput(item, elementId, tooltip);
  }
}

function renderPathInput(item, elementId, tooltip) {
  const isLogPath = item.key === 'log_file_path';
  const browseFunc =
    item.config_type === 'dir_path'
      ? `browseDir('${elementId}')`
      : item.config_type === 'file_path'
        ? `browseFile('${elementId}', '${item.file_ext || ''}')`
        : isLogPath
          ? `browseLogFile()`
          : `browseDir('${elementId}')`;

  const browseBtnId = isLogPath ? ' id="browseLogFileBtn"' : '';
  const label = getConfigLabel(item);
  const tooltipText = getConfigTooltip(item);
  const i18nLabel = `data-i18n="config.labels.${item.key}"`;
  const i18nPlaceholder = `data-i18n="[placeholder]tooltips.${item.key}"`;

  return `
    <div class="config-item config-item-path"${tooltip}>
      <label for="${elementId}" ${i18nLabel}>${label}</label>
      <input type="text" id="${elementId}" class="vscode-input" 
             placeholder="${tooltipText}" ${i18nPlaceholder}
             onchange="onConfigItemChange('${item.key}')" />
      <button class="vscode-btn icon-only secondary"${browseBtnId} onclick="${browseFunc}">
        <i class="codicon codicon-folder-opened"></i>
      </button>
    </div>
  `;
}

function renderNumberInput(item, elementId, tooltip) {
  const min = item.min_value !== null ? ` min="${item.min_value}"` : '';
  const max = item.max_value !== null ? ` max="${item.max_value}"` : '';
  const step = item.step !== null ? ` step="${item.step}"` : '';
  const unit = item.unit ? `<span class="config-unit">${item.unit}</span>` : '';
  const label = getConfigLabel(item);
  const i18nLabel = `data-i18n="config.labels.${item.key}"`;

  return `
    <div class="config-item config-item-number"${tooltip}>
      <label for="${elementId}" ${i18nLabel}>${label}</label>
      <input type="number" id="${elementId}" class="vscode-input"
             value="${item.default}"${min}${max}${step}
             onchange="onConfigItemChange('${item.key}')" />
      ${unit}
    </div>
  `;
}

function renderCheckbox(item, elementId, tooltip) {
  const checked = item.default ? ' checked' : '';
  const label = getConfigLabel(item);
  const i18nLabel = `data-i18n="config.labels.${item.key}"`;

  return `
    <div class="config-item config-item-checkbox"${tooltip}>
      <input type="checkbox" id="${elementId}"${checked}
             onchange="onConfigItemChange('${item.key}')" />
      <label for="${elementId}" ${i18nLabel}>${label}</label>
    </div>
  `;
}

function renderSelect(item, elementId, tooltip) {
  const options = item.options
    .map(([value, label]) => {
      const selected = value === item.default ? ' selected' : '';
      return `<option value="${value}"${selected}>${label}</option>`;
    })
    .join('');
  const label = getConfigLabel(item);
  const i18nLabel = `data-i18n="config.labels.${item.key}"`;

  return `
    <div class="config-item config-item-select"${tooltip}>
      <label for="${elementId}" ${i18nLabel}>${label}</label>
      <select id="${elementId}" class="vscode-select"
              onchange="onConfigItemChange('${item.key}')">
        ${options}
      </select>
    </div>
  `;
}

function renderPathList(item, elementId, tooltip) {
  const dependsAttr = item.depends_on
    ? ` data-depends-on="${item.depends_on}"`
    : '';
  const label = getConfigLabel(item);
  const i18nLabel = `data-i18n="config.labels.${item.key}"`;

  return `
    <div class="config-item config-item-path-list" id="${elementId}Section"${dependsAttr}${tooltip}>
      <div class="config-path-list-header">
        <span ${i18nLabel}>${label}</span>
        <button class="vscode-btn icon-only secondary" onclick="addPathListItem('${item.key}')" title="Add">
          <i class="codicon codicon-add"></i>
        </button>
      </div>
      <div id="${elementId}List" class="config-path-list">
        <!-- Dynamically populated -->
      </div>
    </div>
  `;
}

function renderTextInput(item, elementId, tooltip) {
  const label = getConfigLabel(item);

  return `
    <div class="config-item config-item-text"${tooltip}>
      <label for="${elementId}">${label}</label>
      <input type="text" id="${elementId}" class="vscode-input"
             value="${item.default || ''}"
             onchange="onConfigItemChange('${item.key}')" />
    </div>
  `;
}

/**
 * Get translated group label.
 * @param {string} groupId - Group ID
 * @param {string} defaultLabel - Default label from schema
 * @returns {string} Translated label or default
 */
function getGroupLabel(groupId, defaultLabel) {
  if (typeof t === 'function' && isI18nReady()) {
    const key = `config.groups.${groupId}`;
    const translated = t(key);
    if (translated !== key) return translated;
  }
  return defaultLabel;
}

/**
 * Render the entire config panel from schema.
 * @param {string} containerId - ID of container element
 */
async function renderConfigPanel(containerId) {
  const schema = await loadConfigSchema();
  if (!schema) {
    console.error('Failed to load config schema');
    return;
  }

  const container = document.getElementById(containerId);
  if (!container) {
    console.error(`Container ${containerId} not found`);
    return;
  }

  let html = '';

  // Render groups in order
  for (const groupId of schema.group_order) {
    const groupLabel = getGroupLabel(groupId, schema.groups[groupId]);
    const groupItems = schema.schema
      .filter((item) => item.group === groupId)
      .sort((a, b) => a.order - b.order);

    if (groupItems.length === 0) continue;

    html += `
      <div class="config-group" data-group="${groupId}">
        <div class="config-group-header" data-group="${groupId}">${groupLabel}</div>
        <div class="config-group-content">
    `;

    for (const item of groupItems) {
      html += renderConfigItem(item);
    }

    html += `
        </div>
      </div>
    `;
  }

  container.innerHTML = html;

  // Setup dependency visibility
  setupDependencies(schema);
}

/**
 * Setup visibility dependencies between config items.
 */
function setupDependencies(schema) {
  for (const item of schema.schema) {
    if (item.depends_on) {
      const dependsOnId = keyToElementId(item.depends_on);
      const dependsOnEl = document.getElementById(dependsOnId);
      const sectionId = keyToElementId(item.key) + 'Section';
      const sectionEl = document.getElementById(sectionId);

      if (dependsOnEl && sectionEl) {
        // Set initial visibility
        sectionEl.style.display = dependsOnEl.checked ? 'block' : 'none';

        // Add change listener
        dependsOnEl.addEventListener('change', () => {
          sectionEl.style.display = dependsOnEl.checked ? 'block' : 'none';
        });
      }
    }
  }
}

/**
 * Load config values from backend and populate form.
 */
async function loadConfigValues() {
  const schema = await loadConfigSchema();
  if (!schema) return;

  try {
    const res = await fetch('/api/config');
    if (!res.ok) return;

    const data = await res.json();

    for (const item of schema.schema) {
      const elementId = keyToElementId(item.key);
      const el = document.getElementById(elementId);
      if (!el) continue;

      let value = data[item.key];
      if (value === undefined || value === null) {
        value = item.default;
      }

      if (item.config_type === 'boolean') {
        el.checked = value;
      } else if (item.config_type === 'number' && item.ui_multiplier !== 1) {
        // Apply UI multiplier (e.g., seconds to ms)
        el.value = Math.round(value * item.ui_multiplier);
      } else if (item.config_type === 'path_list') {
        // Handle path list separately
        updatePathList(item.key, value || []);
      } else {
        el.value = value;
      }
    }

    // Update dependency visibility
    setupDependencies(schema);
  } catch (e) {
    console.warn('Config load failed:', e);
  }
}

/**
 * Save config values to backend.
 * @param {boolean} silent - If true, don't show success message
 */
async function saveConfigValues(silent = false) {
  const schema = getConfigSchema();
  if (!schema) return;

  const config = {};

  for (const item of schema.schema) {
    const elementId = keyToElementId(item.key);

    // path_list type doesn't have a direct element with elementId
    if (item.config_type === 'path_list') {
      config[item.key] = getPathListValues(item.key);
      continue;
    }

    const el = document.getElementById(elementId);
    if (!el) continue;

    if (item.config_type === 'boolean') {
      config[item.key] = el.checked;
    } else if (item.config_type === 'number') {
      let value = parseFloat(el.value) || item.default;
      // Reverse UI multiplier
      if (item.ui_multiplier !== 1) {
        value = value / item.ui_multiplier;
      }
      config[item.key] = value;
    } else {
      config[item.key] = el.value;
    }
  }

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    const data = await res.json();

    if (data.success) {
      if (!silent && typeof log !== 'undefined') {
        log.success('Configuration saved');
      }
    } else {
      throw new Error(data.message || 'Save failed');
    }
  } catch (e) {
    if (typeof log !== 'undefined') {
      log.error(`Save failed: ${e}`);
    }
  }
}

/**
 * Handle config item change.
 * @param {string} key - Config key that changed
 */
function onConfigItemChange(key) {
  // Special handling for certain keys - delegate to config.js handlers
  switch (key) {
    case 'auto_compile':
      if (typeof onAutoCompileChange === 'function') {
        onAutoCompileChange();
        return; // Handler will save config
      }
      break;
    case 'verify_crc':
      if (typeof onVerifyCrcChange === 'function') {
        onVerifyCrcChange();
        return; // Handler will save config
      }
      break;
    case 'log_file_enabled':
      if (typeof onLogFileEnabledChange === 'function') {
        onLogFileEnabledChange();
        return; // Handler manages its own state
      }
      break;
    case 'log_file_path':
      if (typeof onLogFilePathChange === 'function') {
        onLogFilePathChange();
        return; // Handler will save config
      }
      break;
    case 'enable_decompile':
      if (typeof onEnableDecompileChange === 'function') {
        onEnableDecompileChange();
        return; // Handler will save config
      }
      break;
    case 'ghidra_path':
      if (typeof onGhidraPathChange === 'function') {
        onGhidraPathChange();
        return; // Handler will save config
      }
      break;
  }

  // Default: save config
  if (typeof saveConfig === 'function') {
    saveConfig(true);
  } else {
    saveConfigValues(true);
  }
}

/**
 * Update path list UI.
 * @param {string} key - Config key
 * @param {Array} paths - Array of paths
 */
function updatePathList(key, paths) {
  const elementId = keyToElementId(key);
  const listEl = document.getElementById(elementId + 'List');
  if (!listEl) return;

  listEl.innerHTML = '';
  for (const path of paths) {
    addPathListItemElement(key, path);
  }
}

/**
 * Get path list values.
 * @param {string} key - Config key
 * @returns {Array} Array of paths
 */
function getPathListValues(key) {
  const elementId = keyToElementId(key);
  const listEl = document.getElementById(elementId + 'List');
  if (!listEl) return [];

  const inputs = listEl.querySelectorAll('input[type="text"]');
  return Array.from(inputs)
    .map((input) => input.value.trim())
    .filter((v) => v);
}

/**
 * Add item to path list.
 * @param {string} key - Config key
 */
function addPathListItem(key) {
  if (typeof window.FPBState !== 'undefined') {
    window.FPBState.fileBrowserCallback = (path) => {
      addPathListItemElement(key, path);
      saveConfigValues(true);
    };
    window.FPBState.fileBrowserFilter = '';
    window.FPBState.fileBrowserMode = 'dir';
    if (typeof openFileBrowser === 'function') {
      openFileBrowser(typeof HOME_PATH !== 'undefined' ? HOME_PATH : '~');
    }
  }
}

/**
 * Add path list item element.
 * @param {string} key - Config key
 * @param {string} path - Path value
 */
function addPathListItemElement(key, path) {
  const elementId = keyToElementId(key);
  const listEl = document.getElementById(elementId + 'List');
  if (!listEl) return;

  const item = document.createElement('div');
  item.className = 'config-path-list-item';
  item.innerHTML = `
    <input type="text" value="${escapeHtml(path)}" class="vscode-input"
           onchange="onConfigItemChange('${key}')" />
    <button class="vscode-btn icon-only secondary" onclick="browsePathListItem(this, '${key}')" title="Browse">
      <i class="codicon codicon-folder-opened"></i>
    </button>
    <button class="vscode-btn icon-only secondary" onclick="removePathListItem(this, '${key}')" title="Remove">
      <i class="codicon codicon-close"></i>
    </button>
  `;
  listEl.appendChild(item);
}

/**
 * Browse for path list item.
 * @param {HTMLElement} btn - Button element
 * @param {string} key - Config key
 */
function browsePathListItem(btn, key) {
  const input = btn.parentElement.querySelector('input');
  if (typeof window.FPBState !== 'undefined') {
    window.FPBState.fileBrowserCallback = (path) => {
      input.value = path;
      saveConfigValues(true);
    };
    window.FPBState.fileBrowserFilter = '';
    window.FPBState.fileBrowserMode = 'dir';
    if (typeof openFileBrowser === 'function') {
      openFileBrowser(
        input.value || (typeof HOME_PATH !== 'undefined' ? HOME_PATH : '~'),
      );
    }
  }
}

/**
 * Remove path list item.
 * @param {HTMLElement} btn - Button element
 * @param {string} key - Config key
 */
function removePathListItem(btn, key) {
  btn.parentElement.remove();
  saveConfigValues(true);
}

/**
 * Escape HTML special characters.
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Export for global access
window.loadConfigSchema = loadConfigSchema;
window.getConfigSchema = getConfigSchema;
window.resetConfigSchema = resetConfigSchema;
window.renderConfigPanel = renderConfigPanel;
window.loadConfigValues = loadConfigValues;
window.saveConfigValues = saveConfigValues;
window.onConfigItemChange = onConfigItemChange;
window.updatePathList = updatePathList;
window.getPathListValues = getPathListValues;
window.addPathListItem = addPathListItem;
window.addPathListItemElement = addPathListItemElement;
window.browsePathListItem = browsePathListItem;
window.removePathListItem = removePathListItem;
window.keyToElementId = keyToElementId;
