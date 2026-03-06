/*========================================
  FPBInject Workbench - Tutorial System
  ========================================*/

const TUTORIAL_STORAGE_KEY = 'fpbinject_tutorial_completed';

/**
 * Gate functions: return true when the step's prerequisite is satisfied.
 * Each gated step also has a gateHint (i18n key for the waiting message)
 * and a gateOk (i18n key for the success message).
 */
const TUTORIAL_STEPS = [
  { id: 'welcome', sidebar: null },
  { id: 'appearance', sidebar: null },
  {
    id: 'connection',
    sidebar: 'details-connection',
    gate: () => !!(window.FPBState && window.FPBState.isConnected),
    gateHint: 'tutorial.gate_connection',
    gateOk: 'tutorial.gate_connection_ok',
  },
  {
    id: 'device',
    sidebar: 'details-device',
    gate: () => !!(window.FPBState && window.FPBState.throughputTested),
    gateHint: 'tutorial.gate_device',
    gateOk: 'tutorial.gate_device_ok',
  },
  { id: 'quickcmd', sidebar: 'details-quick-commands' },
  { id: 'transfer', sidebar: 'details-transfer' },
  { id: 'symbols', sidebar: 'details-symbols' },
  {
    id: 'config',
    sidebar: 'details-configuration',
    gate: () => {
      const elfPath = document.getElementById('elfPath')?.value || '';
      const compileDb =
        document.getElementById('compileCommandsPath')?.value || '';
      const toolchain = document.getElementById('toolchainPath')?.value || '';
      const autoCompile =
        document.getElementById('autoCompile')?.checked || false;
      const watchDirs =
        typeof getWatchDirs === 'function' ? getWatchDirs() : [];
      return !!(
        elfPath &&
        compileDb &&
        toolchain &&
        autoCompile &&
        watchDirs.length > 0
      );
    },
    gateHint: 'tutorial.gate_config',
    gateOk: 'tutorial.gate_config_ok',
  },
  {
    id: 'hello_search',
    sidebar: 'details-symbols',
    gate: () => {
      const tabs = document.querySelectorAll('#editorTabsHeader .tab');
      return Array.from(tabs).some((t) => t.textContent.includes('fl_hello'));
    },
    gateHint: 'tutorial.gate_hello_search',
    gateOk: 'tutorial.gate_hello_search_ok',
  },
  {
    id: 'hello_inject',
    sidebar: null,
    highlight: '#editorContainer',
    gate: () => {
      const slotStates = window.FPBState?.slotStates || [];
      return slotStates.some((s) => s && s.occupied);
    },
    gateHint: 'tutorial.gate_hello_inject',
    gateOk: 'tutorial.gate_hello_inject_ok',
  },
  {
    id: 'hello_verify',
    sidebar: null,
    highlight: '#panelContainer',
  },
  {
    id: 'hello_unpatch',
    sidebar: 'details-device',
    gate: () => {
      const slotStates = window.FPBState?.slotStates || [];
      return slotStates.every((s) => !s || !s.occupied);
    },
    gateHint: 'tutorial.gate_hello_unpatch',
    gateOk: 'tutorial.gate_hello_unpatch_ok',
  },
  { id: 'complete', sidebar: null },
];

let tutorialStep = 0;
let tutorialActive = false;
let tutorialStepConfigured = {};
let currentHighlightedElement = null;
let tutorialGatePollTimer = null;
let tutorialDraggedByUser = false;

/* ===========================
   UI HIGHLIGHTING
   =========================== */

function highlightElement(selector) {
  clearHighlight();

  const element = document.querySelector(selector);
  if (!element) return;

  const targetSection = element.closest('.sidebar-section');

  document.querySelectorAll('.sidebar .sidebar-section').forEach((section) => {
    if (section !== targetSection) {
      section.classList.add('tutorial-dimmed');
    }
  });

  element.classList.add(
    'tutorial-highlight-target',
    'tutorial-highlight-pulse',
  );
  currentHighlightedElement = element;

  setTimeout(() => {
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 100);
}

function clearHighlight() {
  document.querySelectorAll('.tutorial-dimmed').forEach((el) => {
    el.classList.remove('tutorial-dimmed');
  });

  if (currentHighlightedElement) {
    currentHighlightedElement.classList.remove(
      'tutorial-highlight-target',
      'tutorial-highlight-pulse',
    );
    currentHighlightedElement = null;
  }

  clearConfigGateHighlights();
}

function highlightNonSidebarElement(selector) {
  clearHighlight();
  const element = document.querySelector(selector);
  if (!element) return;

  element.classList.add(
    'tutorial-highlight-target',
    'tutorial-highlight-pulse',
  );
  currentHighlightedElement = element;
}

function activateSidebarForStep(sidebarId) {
  if (!sidebarId) return;

  const sectionMap = {
    'details-connection': 'connection',
    'details-device': 'device',
    'details-quick-commands': 'quick-commands',
    'details-transfer': 'transfer',
    'details-symbols': 'symbols',
    'details-configuration': 'configuration',
  };

  const sectionName = sectionMap[sidebarId];
  if (sectionName && typeof activateSection === 'function') {
    activateSection(sectionName);
  }

  setTimeout(() => {
    const details = document.getElementById(sidebarId);
    if (details && details.tagName === 'DETAILS') {
      details.open = true;
    }
  }, 200);
}

/* ===========================
   GATE SYSTEM
   =========================== */

function getStepGateStatus(step) {
  if (!step || !step.gate) return { gated: false, passed: true };
  return { gated: true, passed: step.gate() };
}

function startGatePoll() {
  stopGatePoll();
  tutorialGatePollTimer = setInterval(() => {
    if (!tutorialActive) {
      stopGatePoll();
      return;
    }
    const step = TUTORIAL_STEPS[tutorialStep];
    const { gated, passed } = getStepGateStatus(step);

    // Update per-field highlights and checklist for config gate
    if (step.id === 'config') {
      highlightConfigGateFields();
      const checklistEl = document.querySelector('.tutorial-gate-checklist');
      if (checklistEl) {
        const tmp = document.createElement('div');
        tmp.innerHTML = renderConfigGateChecklist();
        const newChecklist = tmp.firstElementChild;
        if (newChecklist) checklistEl.replaceWith(newChecklist);
      }
    }

    if (gated && passed) {
      stopGatePoll();
      renderTutorialStep();
    }
  }, 500);
}

function stopGatePoll() {
  if (tutorialGatePollTimer) {
    clearInterval(tutorialGatePollTimer);
    tutorialGatePollTimer = null;
  }
}

/* ===========================
   LIFECYCLE
   =========================== */

function shouldShowTutorial(configData) {
  if (!configData || configData.first_launch !== true) return false;
  // first_launch means config.json was recreated — clear stale localStorage
  localStorage.removeItem(TUTORIAL_STORAGE_KEY);
  return true;
}

function startTutorial() {
  tutorialStep = 0;
  tutorialActive = true;
  tutorialStepConfigured = {};
  resetTutorialPosition();
  renderTutorialStep();
  const overlay = document.getElementById('tutorialOverlay');
  if (overlay) overlay.classList.add('show');
}

function tutorialNext() {
  markCurrentStepConfigured();
  if (tutorialStep < TUTORIAL_STEPS.length - 1) {
    tutorialStep++;
    renderTutorialStep();
  } else {
    finishTutorial();
  }
}

function tutorialPrev() {
  if (tutorialStep > 0) {
    tutorialStep--;
    renderTutorialStep();
  }
}

function tutorialSkip() {
  if (tutorialStep < TUTORIAL_STEPS.length - 1) {
    tutorialStep++;
    renderTutorialStep();
  } else {
    finishTutorial();
  }
}

function tutorialSkipAll() {
  finishTutorial();
}

function finishTutorial() {
  tutorialActive = false;
  clearHighlight();
  stopGatePoll();
  localStorage.setItem(TUTORIAL_STORAGE_KEY, 'true');
  const overlay = document.getElementById('tutorialOverlay');
  if (overlay) overlay.classList.remove('show');

  if (typeof saveConfig === 'function') {
    saveConfig(true);
  }
}

function markCurrentStepConfigured() {
  const step = TUTORIAL_STEPS[tutorialStep];
  if (step) tutorialStepConfigured[step.id] = true;
}

/* ===========================
   RENDERING
   =========================== */

function renderTutorialStep() {
  const step = TUTORIAL_STEPS[tutorialStep];
  const body = document.getElementById('tutorialBody');
  const title = document.getElementById('tutorialTitle');
  const stepCount = document.getElementById('tutorialStepCount');
  const prevBtn = document.getElementById('tutorialPrevBtn');
  const skipBtn = document.getElementById('tutorialSkipBtn');
  const nextBtn = document.getElementById('tutorialNextBtn');
  const skipAllBtn = document.getElementById('tutorialSkipAllBtn');

  if (!body || !step) return;

  clearHighlight();
  tutorialDraggedByUser = false;

  // Title
  if (title) title.textContent = t(`tutorial.${step.id}_title`, step.id);

  // Step count
  if (stepCount) {
    stepCount.textContent = t('tutorial.step_of', '{{current}} / {{total}}', {
      current: tutorialStep + 1,
      total: TUTORIAL_STEPS.length,
    });
  }

  // Render body
  const renderer = stepRenderers[step.id];
  if (renderer) {
    body.style.animation = 'none';
    body.innerHTML = renderer();
    void body.offsetHeight;
    body.style.animation = '';
  }

  // Activate sidebar and highlight
  const overlay = document.getElementById('tutorialOverlay');
  const needsBlocking = !step.sidebar && !step.highlight;
  if (overlay) {
    overlay.classList.toggle('tutorial-blocking', needsBlocking);
  }

  if (step.sidebar) {
    activateSidebarForStep(step.sidebar);
    setTimeout(() => {
      highlightElement(`#${step.sidebar}`);
      positionModalNearTarget(`#${step.sidebar}`);
      // Apply per-field visual guides for config gate
      if (step.id === 'config') {
        setTimeout(() => highlightConfigGateFields(), 100);
      }
    }, 300);
  } else if (step.highlight) {
    setTimeout(() => {
      highlightNonSidebarElement(step.highlight);
      positionModalNearTarget(step.highlight);
    }, 300);
  } else {
    positionModalNearTarget(null);
  }

  renderTutorialProgress();

  // Button visibility
  const isFirst = tutorialStep === 0;
  const isLast = tutorialStep === TUTORIAL_STEPS.length - 1;

  if (prevBtn) prevBtn.style.display = isFirst ? 'none' : '';
  if (skipBtn) skipBtn.style.display = isLast ? 'none' : '';
  if (skipAllBtn) skipAllBtn.style.display = isLast ? 'none' : '';

  // Gate: disable Next until condition met
  const { gated, passed } = getStepGateStatus(step);

  if (nextBtn) {
    nextBtn.textContent = isLast
      ? t('tutorial.finish', 'Get Started')
      : t('tutorial.next', 'Next');

    if (gated && !passed) {
      nextBtn.disabled = true;
      nextBtn.title = step.gateHint ? t(step.gateHint, '') : '';
    } else {
      nextBtn.disabled = false;
      nextBtn.title = '';
    }
  }

  // Start/stop gate polling
  stopGatePoll();
  if (gated && !passed) {
    startGatePoll();
  }

  // Auto-enter fl mode for hello_verify / hello_unpatch steps
  if (step.id === 'hello_verify' || step.id === 'hello_unpatch') {
    if (
      window.FPBState?.isConnected &&
      typeof sendTerminalCommand === 'function'
    ) {
      sendTerminalCommand('fl\n');
    }
  }

  if (typeof translatePage === 'function') translatePage();
}

function renderConfigGateChecklist() {
  const elfPath = document.getElementById('elfPath')?.value || '';
  const compileDb = document.getElementById('compileCommandsPath')?.value || '';
  const toolchain = document.getElementById('toolchainPath')?.value || '';
  const autoCompile = document.getElementById('autoCompile')?.checked || false;
  const watchDirs = typeof getWatchDirs === 'function' ? getWatchDirs() : [];

  const items = [
    { done: !!elfPath, label: t('tutorial.gate_config_elf', 'ELF Path') },
    {
      done: !!compileDb,
      label: t('tutorial.gate_config_compiledb', 'Compile Database'),
    },
    {
      done: !!toolchain,
      label: t('tutorial.gate_config_toolchain', 'Toolchain'),
    },
    {
      done: watchDirs.length > 0,
      label: t('tutorial.gate_config_watchdirs', 'Watch Directories'),
    },
    {
      done: autoCompile,
      label: t('tutorial.gate_config_autoinject', 'Auto-Inject'),
    },
  ];

  const rows = items
    .map((item) => {
      const icon = item.done
        ? 'codicon-pass-filled'
        : 'codicon-circle-large-outline';
      const cls = item.done ? 'done' : '';
      return `<div class="tutorial-gate-check-item ${cls}"><i class="codicon ${icon}"></i><span>${item.label}</span></div>`;
    })
    .join('');

  return `<div class="tutorial-gate-checklist">${rows}</div>`;
}

/* --- Config gate per-field visual guides --- */

const CONFIG_GATE_FIELDS = [
  { id: 'elfPath', check: (el) => !!el.value },
  { id: 'compileCommandsPath', check: (el) => !!el.value },
  { id: 'toolchainPath', check: (el) => !!el.value },
  { id: 'autoCompile', check: (el) => !!el.checked },
  {
    id: 'watchDirsSection',
    check: () => {
      const dirs = typeof getWatchDirs === 'function' ? getWatchDirs() : [];
      return dirs.length > 0;
    },
  },
];

function highlightConfigGateFields() {
  for (const field of CONFIG_GATE_FIELDS) {
    const el = document.getElementById(field.id);
    if (!el) continue;
    const target = el.closest('.config-item') || el;
    if (field.check(el)) {
      target.classList.remove('tutorial-field-guide');
    } else {
      target.classList.add('tutorial-field-guide');
      target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }
}

function clearConfigGateHighlights() {
  document.querySelectorAll('.tutorial-field-guide').forEach((el) => {
    el.classList.remove('tutorial-field-guide');
  });
}

function renderGateStatus(step) {
  const { gated, passed } = getStepGateStatus(step);
  if (!gated) return '';

  const statusClass = passed ? 'success' : '';
  const statusText = passed
    ? t(step.gateOk || 'tutorial.gate_ok', '✅ Ready!')
    : t(step.gateHint || 'tutorial.gate_waiting', '⏳ Waiting...');

  return `<div class="tutorial-connect-status ${statusClass}" style="display: block;">${statusText}</div>`;
}

function renderTutorialProgress() {
  const container = document.getElementById('tutorialProgress');
  if (!container) return;

  let html = '';
  for (let i = 0; i < TUTORIAL_STEPS.length; i++) {
    let cls = 'tutorial-dot';
    if (i === tutorialStep) cls += ' active';
    else if (i < tutorialStep) cls += ' completed';
    html += `<button class="${cls}" onclick="tutorialGoTo(${i})"></button>`;
  }
  container.innerHTML = html;
}

function tutorialGoTo(index) {
  if (index >= 0 && index < TUTORIAL_STEPS.length) {
    tutorialStep = index;
    renderTutorialStep();
  }
}

/* ===========================
   STEP RENDERERS
   =========================== */

const stepRenderers = {
  welcome() {
    return `
      <div class="tutorial-icon">🔧</div>
      <div class="tutorial-welcome-title">${t('tutorial.welcome_title', 'Welcome to FPBInject Workbench')}</div>
      <p class="tutorial-welcome-subtitle">${t('tutorial.welcome_desc', 'An ARM Cortex-M runtime code injection tool based on FPB hardware.')}</p>
    `;
  },

  appearance() {
    const currentLang = localStorage.getItem('fpbinject_ui_language') || 'en';
    const currentTheme =
      document.documentElement.getAttribute('data-theme') || 'dark';

    return `
      <p>${t('tutorial.appearance_desc', 'First, choose your preferred language and theme.')}</p>
      <div class="tutorial-config-group">
        <div class="tutorial-config-item">
          <label><i class="codicon codicon-globe"></i> ${t('tutorial.appearance_language', 'Language')}</label>
          <select id="tutorialLangSelect" class="vscode-select" onchange="var v=this.value;var el=document.getElementById('uiLanguage');if(el)el.value=v;if(typeof changeLanguage==='function'){changeLanguage(v).then(function(){renderTutorialStep();if(typeof saveConfig==='function')saveConfig(true)})}">
            <option value="en" ${currentLang === 'en' ? 'selected' : ''}>English</option>
            <option value="zh-CN" ${currentLang === 'zh-CN' ? 'selected' : ''}>简体中文</option>
            <option value="zh-TW" ${currentLang === 'zh-TW' ? 'selected' : ''}>繁體中文</option>
          </select>
        </div>
        <div class="tutorial-config-item">
          <label><i class="codicon codicon-color-mode"></i> ${t('tutorial.appearance_theme', 'Theme')}</label>
          <select id="tutorialThemeSelect" class="vscode-select" onchange="var v=this.value;var el=document.getElementById('uiTheme');if(el)el.value=v;if(typeof setTheme==='function'){setTheme(v);if(typeof saveConfig==='function')saveConfig(true)}">
            <option value="dark" ${currentTheme === 'dark' ? 'selected' : ''}>${t('config.options.dark', 'Dark')}</option>
            <option value="light" ${currentTheme === 'light' ? 'selected' : ''}>${t('config.options.light', 'Light')}</option>
          </select>
        </div>
      </div>
    `;
  },

  connection() {
    const step = TUTORIAL_STEPS.find((s) => s.id === 'connection');
    return `
      <p>${t('tutorial.connection_desc', 'The Connection section lets you connect to your device via serial port.')}</p>
      <div class="tutorial-feature-list">
        <div class="tutorial-feature-item">
          <i class="codicon codicon-plug"></i>
          <div>
            <strong>${t('tutorial.connection_port', 'Serial Port')}</strong>
            ${t('tutorial.connection_port_desc', 'Select your device port from the dropdown. Click refresh to scan for new ports.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-dashboard"></i>
          <div>
            <strong>${t('tutorial.connection_baudrate', 'Baud Rate')}</strong>
            ${t('tutorial.connection_baudrate_desc', 'Set the communication speed (default: 115200).')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-debug-start"></i>
          <div>
            <strong>${t('tutorial.connection_connect', 'Connect Button')}</strong>
            ${t('tutorial.connection_connect_desc', 'Click to establish connection with your device.')}
          </div>
        </div>
      </div>
      ${renderGateStatus(step)}
    `;
  },

  device() {
    const step = TUTORIAL_STEPS.find((s) => s.id === 'device');
    return `
      <p>${t('tutorial.device_desc', 'The Device section shows information about your connected device.')}</p>
      <div class="tutorial-feature-list">
        <div class="tutorial-feature-item">
          <i class="codicon codicon-info"></i>
          <div>
            <strong>${t('tutorial.device_info', 'Device Info')}</strong>
            ${t('tutorial.device_info_desc', 'View device status, FPB hardware capabilities, and active patches.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-pulse"></i>
          <div>
            <strong>${t('tutorial.device_ping', 'Ping Device')}</strong>
            ${t('tutorial.device_ping_desc', 'Test device responsiveness and check connection health.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-layers"></i>
          <div>
            <strong>${t('tutorial.device_slots', 'FPB Slots')}</strong>
            ${t('tutorial.device_slots_desc', 'See available and used FPB comparator slots for patching.')}
          </div>
        </div>
      </div>
      ${renderGateStatus(step)}
    `;
  },

  quickcmd() {
    return `
      <p>${t('tutorial.quickcmd_desc', 'Quick commands let you send serial commands or execute macros.')}</p>
      <div class="tutorial-feature-list">
        <div class="tutorial-feature-item">
          <i class="codicon codicon-terminal"></i>
          <div>
            <strong>${t('tutorial.quickcmd_feature_single', 'Single Command')}</strong>
            ${t('tutorial.quickcmd_feature_single_desc', 'Send a serial command instantly to your device.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-list-ordered"></i>
          <div>
            <strong>${t('tutorial.quickcmd_feature_macro', 'Macro')}</strong>
            ${t('tutorial.quickcmd_feature_macro_desc', 'Execute a sequence of commands with configurable delays.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-add"></i>
          <div>
            <strong>${t('tutorial.quickcmd_add', 'Add Commands')}</strong>
            ${t('tutorial.quickcmd_add_desc', 'Create custom commands and organize them for quick access.')}
          </div>
        </div>
      </div>
    `;
  },

  transfer() {
    const step = TUTORIAL_STEPS.find((s) => s.id === 'transfer');
    return `
      <p>${t('tutorial.transfer_desc', 'The Transfer section handles file operations with your device.')}</p>
      <div class="tutorial-feature-list">
        <div class="tutorial-feature-item">
          <i class="codicon codicon-cloud-upload"></i>
          <div>
            <strong>${t('tutorial.transfer_upload', 'Upload Files')}</strong>
            ${t('tutorial.transfer_upload_desc', 'Send files from your computer to the device filesystem.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-cloud-download"></i>
          <div>
            <strong>${t('tutorial.transfer_download', 'Download Files')}</strong>
            ${t('tutorial.transfer_download_desc', 'Retrieve files from the device to your local system.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-folder"></i>
          <div>
            <strong>${t('tutorial.transfer_browse', 'Browse Filesystem')}</strong>
            ${t('tutorial.transfer_browse_desc', 'Navigate device directories and manage files remotely.')}
          </div>
        </div>
      </div>
      ${renderGateStatus(step)}
    `;
  },

  symbols() {
    return `
      <p>${t('tutorial.symbols_desc', 'The Symbols section helps you analyze firmware functions.')}</p>
      <div class="tutorial-feature-list">
        <div class="tutorial-feature-item">
          <i class="codicon codicon-search"></i>
          <div>
            <strong>${t('tutorial.symbols_search', 'Search Functions')}</strong>
            ${t('tutorial.symbols_search_desc', 'Find functions in your ELF firmware by name pattern.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-code"></i>
          <div>
            <strong>${t('tutorial.symbols_disasm', 'Disassembly')}</strong>
            ${t('tutorial.symbols_disasm_desc', 'View assembly instructions for selected functions.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-file-code"></i>
          <div>
            <strong>${t('tutorial.symbols_decompile', 'Decompile')}</strong>
            ${t('tutorial.symbols_decompile_desc', 'Generate pseudo-C code using Ghidra for better understanding.')}
          </div>
        </div>
      </div>
    `;
  },

  config() {
    const step = TUTORIAL_STEPS.find((s) => s.id === 'config');
    return `
      <p>${t('tutorial.config_desc', 'The Configuration section contains all workbench settings.')}</p>
      ${renderConfigGateChecklist()}
      <div style="margin-top: 14px; padding: 12px; background: var(--vscode-input-bg); border-radius: 6px;">
        <p style="margin: 0 0 8px; font-weight: 600; font-size: 13px;">
          <i class="codicon codicon-lightbulb" style="color: var(--vscode-button-bg);"></i>
          ${t('tutorial.config_autoinject_title', 'How Auto-Inject Works')}
        </p>
        <p style="margin: 0 0 8px; font-size: 12px; line-height: 1.6;">
          ${t('tutorial.config_autoinject_desc', 'When enabled, the system watches your source files. Any file containing the <code>/* FPB_INJECT */</code> marker will be automatically compiled and injected into the device at runtime via FPB hardware, replacing the original function without reflashing.')}
        </p>
        <p style="margin: 0 0 6px; font-size: 11px; opacity: 0.7;">
          ${t('tutorial.config_autoinject_example', 'Example patch file:')}
        </p>
        <pre style="margin: 0; padding: 8px 10px; background: var(--vscode-editor-bg, #1e1e1e); border-radius: 4px; font-size: 12px; line-height: 1.5; overflow-x: auto;"><code><span style="color: #6a9955;">/* FPB_INJECT */</span>
<span style="color: #569cd6;">void</span> <span style="color: #dcdcaa;">my_function</span>(<span style="color: #569cd6;">int</span> arg)
{
    <span style="color: #6a9955;">// your code here</span>
}</code></pre>
      </div>
      <p class="tutorial-hint" style="margin-top: 12px; opacity: 0.7; font-size: 12px;">
        ${t('tutorial.config_hint', 'Expand each section to configure settings.')}
      </p>
      ${renderGateStatus(step)}
    `;
  },

  hello_search() {
    const step = TUTORIAL_STEPS.find((s) => s.id === 'hello_search');
    return `
      <p>${t('tutorial.hello_search_desc', "Let's try a real injection! Search for the hello function in the Symbols panel.")}</p>
      <div class="tutorial-feature-list">
        <div class="tutorial-feature-item">
          <i class="codicon codicon-search"></i>
          <div>
            <strong>${t('tutorial.hello_search_input', 'Search Symbol')}</strong>
            ${t('tutorial.hello_search_input_desc', 'Type <code>fl_hello</code> in the search box and press Enter.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-list-flat"></i>
          <div>
            <strong>${t('tutorial.hello_search_result', 'View Results')}</strong>
            ${t('tutorial.hello_search_result_desc', 'The list shows the function address and name from your ELF firmware.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-edit"></i>
          <div>
            <strong>${t('tutorial.hello_search_dblclick', 'Double-Click to Patch')}</strong>
            ${t('tutorial.hello_search_dblclick_desc', 'Double-click the symbol to auto-generate a patch template in the editor.')}
          </div>
        </div>
      </div>
      ${renderGateStatus(step)}
    `;
  },

  hello_inject() {
    const step = TUTORIAL_STEPS.find((s) => s.id === 'hello_inject');
    return `
      <p>${t('tutorial.hello_inject_desc', 'The generated patch template can be injected directly. Select a slot and click inject.')}</p>
      <div class="tutorial-feature-list">
        <div class="tutorial-feature-item">
          <i class="codicon codicon-edit"></i>
          <div>
            <strong>${t('tutorial.hello_inject_edit', 'Edit Code')}</strong>
            ${t('tutorial.hello_inject_edit_desc', 'Change the <code>fl_println</code> string to your own message.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-layers"></i>
          <div>
            <strong>${t('tutorial.hello_inject_slot', 'Select Slot')}</strong>
            ${t('tutorial.hello_inject_slot_desc', 'Make sure an available FPB slot is selected in the toolbar.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-play"></i>
          <div>
            <strong>${t('tutorial.hello_inject_run', 'Click Inject')}</strong>
            ${t('tutorial.hello_inject_run_desc', 'Click the inject button in the toolbar and wait for completion.')}
          </div>
        </div>
      </div>
      ${renderGateStatus(step)}
    `;
  },

  hello_verify() {
    return `
      <p>${t('tutorial.hello_verify_desc', 'Send the hello command in the serial terminal to verify the injection effect.')}</p>
      <div class="tutorial-feature-list">
        <div class="tutorial-feature-item">
          <i class="codicon codicon-terminal"></i>
          <div>
            <strong>${t('tutorial.hello_verify_send_cmd', 'Send Command')}</strong>
            ${t('tutorial.hello_verify_send_cmd_desc', 'Type <code>fl -c hello</code> in the serial terminal and press Enter.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-check"></i>
          <div>
            <strong>${t('tutorial.hello_verify_check_output', 'Check Output')}</strong>
            ${t('tutorial.hello_verify_check_output_desc', 'The output should show the injected message instead of the original one.')}
          </div>
        </div>
      </div>
    `;
  },

  hello_unpatch() {
    const step = TUTORIAL_STEPS.find((s) => s.id === 'hello_unpatch');
    return `
      <p>${t('tutorial.hello_unpatch_desc', 'Remove the injection and verify the original function is restored.')}</p>
      <div class="tutorial-feature-list">
        <div class="tutorial-feature-item">
          <i class="codicon codicon-close"></i>
          <div>
            <strong>${t('tutorial.hello_unpatch_click', 'Click ✕ to Unpatch')}</strong>
            ${t('tutorial.hello_unpatch_click_desc', 'In the Device Info panel, click the ✕ button on the occupied slot to remove the injection.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-terminal"></i>
          <div>
            <strong>${t('tutorial.hello_unpatch_verify', 'Verify Restore')}</strong>
            ${t('tutorial.hello_unpatch_verify_desc', 'Send <code>fl -c hello</code> again — the output should revert to the original message.')}
          </div>
        </div>
      </div>
      <p class="tutorial-hint" style="margin-top: 14px; text-align: center; opacity: 0.7; font-size: 12px;">
        ${t('tutorial.hello_unpatch_hint', 'This is the complete FPB runtime code injection workflow — replace any function without reflashing!')}
      </p>
      ${renderGateStatus(step)}
    `;
  },

  complete() {
    let summaryHtml = '';
    const summarySteps = TUTORIAL_STEPS.filter(
      (s) => s.id !== 'welcome' && s.id !== 'complete',
    );
    for (const s of summarySteps) {
      const configured = tutorialStepConfigured[s.id];
      const icon = configured ? 'codicon-check' : 'codicon-circle-outline';
      const cls = configured ? 'configured' : 'skipped';
      const label = configured
        ? t('tutorial.complete_configured', 'Visited')
        : t('tutorial.complete_skipped', 'Skipped');
      const stepTitle = t(`tutorial.${s.id}_title`, s.id);
      summaryHtml += `
        <div class="tutorial-summary-item ${cls}">
          <i class="codicon ${icon}"></i>
          <span>${stepTitle}</span>
          <span style="margin-left: auto; opacity: 0.6; font-size: 11px;">${label}</span>
        </div>
      `;
    }

    return `
      <div class="tutorial-icon">🎉</div>
      <div class="tutorial-welcome-title">${t('tutorial.complete_title', 'Tutorial Complete!')}</div>
      <p class="tutorial-welcome-subtitle">${t('tutorial.complete_desc', 'You now know where to find all the features.')}</p>
      <div class="tutorial-summary">${summaryHtml}</div>
      <p class="tutorial-hint" style="margin-top: 16px; text-align: center; opacity: 0.6; font-size: 11px;">
        ${t('tutorial.complete_hint', 'Click the 🎓 button to restart this tutorial.')}
      </p>
    `;
  },
};

/* ===========================
   DRAG SUPPORT
   =========================== */

function initTutorialDrag() {
  const header = document.querySelector('.tutorial-header');
  const modal = document.querySelector('.tutorial-modal');
  if (!header || !modal) return;

  let dragging = false;
  let offsetX = 0;
  let offsetY = 0;

  header.addEventListener('mousedown', (e) => {
    if (e.target.tagName === 'SELECT' || e.target.tagName === 'BUTTON') return;
    dragging = true;
    tutorialDraggedByUser = true;
    const rect = modal.getBoundingClientRect();
    offsetX = e.clientX - rect.left;
    offsetY = e.clientY - rect.top;

    // Switch from flex-centered to absolute positioning
    modal.style.transition = 'none';
    modal.style.position = 'fixed';
    modal.style.left = rect.left + 'px';
    modal.style.top = rect.top + 'px';
    modal.style.margin = '0';
    e.preventDefault();
  });

  document.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    let x = e.clientX - offsetX;
    let y = e.clientY - offsetY;

    // Clamp to viewport
    const rect = modal.getBoundingClientRect();
    x = Math.max(0, Math.min(x, window.innerWidth - rect.width));
    y = Math.max(0, Math.min(y, window.innerHeight - rect.height));

    modal.style.left = x + 'px';
    modal.style.top = y + 'px';
  });

  document.addEventListener('mouseup', () => {
    if (dragging) {
      dragging = false;
      modal.style.transition = '';
    }
  });
}

// Reset modal position when tutorial restarts
function resetTutorialPosition() {
  const modal = document.querySelector('.tutorial-modal');
  if (modal) {
    modal.style.position = '';
    modal.style.left = '';
    modal.style.top = '';
    modal.style.margin = '';
    modal.classList.remove('tutorial-modal-positioned');
  }
}

/**
 * Position the tutorial modal next to the highlighted target element.
 * Prefers placing to the right; falls back to left, then centers.
 * For steps with no highlight target, resets to centered layout.
 */
function positionModalNearTarget(targetSelector) {
  const modal = document.querySelector('.tutorial-modal');
  if (!modal) return;

  // User dragged the modal — respect their position
  if (tutorialDraggedByUser) return;

  // No target — reset to flex-centered
  if (!targetSelector) {
    // Only reset if currently positioned
    if (modal.classList.contains('tutorial-modal-positioned')) {
      resetTutorialPosition();
    }
    return;
  }

  const target = document.querySelector(targetSelector);
  if (!target) return;

  const targetRect = target.getBoundingClientRect();
  const modalRect = modal.getBoundingClientRect();
  const gap = 16; // px gap between target and modal
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const mw = modalRect.width;
  const mh = modalRect.height;

  let x, y;

  // Try right of target
  if (targetRect.right + gap + mw <= vw) {
    x = targetRect.right + gap;
  }
  // Try left of target
  else if (targetRect.left - gap - mw >= 0) {
    x = targetRect.left - gap - mw;
  }
  // Fallback: center horizontally
  else {
    x = Math.max(0, (vw - mw) / 2);
  }

  // Vertically align to target center, clamped to viewport
  y = targetRect.top + targetRect.height / 2 - mh / 2;
  y = Math.max(gap, Math.min(y, vh - mh - gap));

  // Switch to fixed positioning with transition
  if (!modal.classList.contains('tutorial-modal-positioned')) {
    // FLIP: capture current center position, then animate to target
    const currentRect = modal.getBoundingClientRect();
    modal.style.transition = 'none';
    modal.style.position = 'fixed';
    modal.style.margin = '0';
    modal.style.left = currentRect.left + 'px';
    modal.style.top = currentRect.top + 'px';
    modal.classList.add('tutorial-modal-positioned');
    // Next frame: enable transition and move to target
    requestAnimationFrame(() => {
      modal.style.transition = '';
      requestAnimationFrame(() => {
        modal.style.left = x + 'px';
        modal.style.top = y + 'px';
      });
    });
  } else {
    modal.style.left = x + 'px';
    modal.style.top = y + 'px';
  }
}

// Init drag on page load
document.addEventListener('DOMContentLoaded', initTutorialDrag);

/* ===========================
   EXPORTS
   =========================== */

window.shouldShowTutorial = shouldShowTutorial;
window.startTutorial = startTutorial;
window.tutorialNext = tutorialNext;
window.tutorialPrev = tutorialPrev;
window.tutorialSkip = tutorialSkip;
window.tutorialSkipAll = tutorialSkipAll;
window.tutorialGoTo = tutorialGoTo;
window.finishTutorial = finishTutorial;
window.renderTutorialStep = renderTutorialStep;
window.renderGateStatus = renderGateStatus;
window.getStepGateStatus = getStepGateStatus;
window.resetTutorialPosition = resetTutorialPosition;
window.positionModalNearTarget = positionModalNearTarget;
