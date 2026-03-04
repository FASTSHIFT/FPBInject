/*========================================
  FPBInject Workbench - Tutorial System
  ========================================*/

const TUTORIAL_STORAGE_KEY = 'fpbinject_tutorial_completed';

const TUTORIAL_STEPS = [
  { id: 'welcome', sidebar: null },
  { id: 'appearance', sidebar: null },
  { id: 'connection', sidebar: 'details-connection' },
  { id: 'device', sidebar: 'details-device' },
  { id: 'quickcmd', sidebar: 'details-quick-commands' },
  { id: 'transfer', sidebar: 'details-transfer' },
  { id: 'symbols', sidebar: 'details-symbols' },
  { id: 'config', sidebar: 'details-configuration' },
  { id: 'complete', sidebar: null },
];

let tutorialStep = 0;
let tutorialActive = false;
let tutorialStepConfigured = {}; // Track which steps user configured
let currentHighlightedElement = null;

/* ===========================
   UI HIGHLIGHTING
   =========================== */

function highlightElement(selector) {
  clearHighlight();

  const element = document.querySelector(selector);
  if (!element) return;

  // Find the parent sidebar-section of the target
  const targetSection = element.closest('.sidebar-section');

  // Dim all other sidebar-section containers
  const allSections = document.querySelectorAll('.sidebar .sidebar-section');
  allSections.forEach((section) => {
    if (section !== targetSection) {
      section.classList.add('tutorial-dimmed');
    }
  });

  // Highlight target
  element.classList.add(
    'tutorial-highlight-target',
    'tutorial-highlight-pulse',
  );
  currentHighlightedElement = element;

  // Scroll into view
  setTimeout(() => {
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 100);
}

function clearHighlight() {
  // Remove all dimmed classes
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
}

function activateSidebarForStep(sidebarId) {
  if (!sidebarId) return;

  // Find which activity bar button corresponds to this sidebar section
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

  // Open the details element
  setTimeout(() => {
    const details = document.getElementById(sidebarId);
    if (details && details.tagName === 'DETAILS') {
      details.open = true;
    }
  }, 200);
}

/* ===========================
   LIFECYCLE
   =========================== */

function shouldShowTutorial(configData) {
  return (
    configData &&
    configData.first_launch === true &&
    !localStorage.getItem(TUTORIAL_STORAGE_KEY)
  );
}

function startTutorial() {
  tutorialStep = 0;
  tutorialActive = true;
  tutorialStepConfigured = {};
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
  localStorage.setItem(TUTORIAL_STORAGE_KEY, 'true');
  const overlay = document.getElementById('tutorialOverlay');
  if (overlay) overlay.classList.remove('show');

  // Save any config changes made during tutorial
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

  // Clear previous highlights
  clearHighlight();

  // Title
  const titleKey = `tutorial.${step.id}_title`;
  if (title) title.textContent = t(titleKey, step.id);

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
    body.innerHTML = renderer();
  }

  // Activate sidebar and highlight
  if (step.sidebar) {
    activateSidebarForStep(step.sidebar);
    setTimeout(() => {
      highlightElement(`#${step.sidebar}`);
    }, 300);
  }

  // Progress dots
  renderTutorialProgress();

  // Button visibility
  const isFirst = tutorialStep === 0;
  const isLast = tutorialStep === TUTORIAL_STEPS.length - 1;

  if (prevBtn) prevBtn.style.display = isFirst ? 'none' : '';
  if (skipBtn) skipBtn.style.display = isLast ? 'none' : '';
  if (skipAllBtn) skipAllBtn.style.display = isLast ? 'none' : '';

  if (nextBtn) {
    nextBtn.textContent = isLast
      ? t('tutorial.finish', 'Get Started')
      : t('tutorial.next', 'Next');
  }

  // Translate dynamic content
  if (typeof translatePage === 'function') translatePage();
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
          <select id="tutorialLangSelect" class="vscode-select" onchange="if(typeof changeLanguage==='function') changeLanguage(this.value)">
            <option value="en" ${currentLang === 'en' ? 'selected' : ''}>English</option>
            <option value="zh-CN" ${currentLang === 'zh-CN' ? 'selected' : ''}>简体中文</option>
            <option value="zh-TW" ${currentLang === 'zh-TW' ? 'selected' : ''}>繁體中文</option>
          </select>
        </div>
        <div class="tutorial-config-item">
          <label><i class="codicon codicon-color-mode"></i> ${t('tutorial.appearance_theme', 'Theme')}</label>
          <select id="tutorialThemeSelect" class="vscode-select" onchange="if(typeof setTheme==='function') setTheme(this.value)">
            <option value="dark" ${currentTheme === 'dark' ? 'selected' : ''}>${t('config.options.dark', 'Dark')}</option>
            <option value="light" ${currentTheme === 'light' ? 'selected' : ''}>${t('config.options.light', 'Light')}</option>
          </select>
        </div>
      </div>
    `;
  },

  connection() {
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
      <p class="tutorial-hint" style="margin-top: 12px; opacity: 0.7; font-size: 12px;">
        ${t('tutorial.connection_hint', 'Look at the highlighted section on the left sidebar.')}
      </p>
    `;
  },

  device() {
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
    return `
      <p>${t('tutorial.config_desc', 'The Configuration section contains all workbench settings.')}</p>
      <div class="tutorial-feature-list">
        <div class="tutorial-feature-item">
          <i class="codicon codicon-symbol-color"></i>
          <div>
            <strong>${t('tutorial.config_ui', 'UI Settings')}</strong>
            ${t('tutorial.config_ui_desc', 'Language, theme, and interface preferences.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-file-binary"></i>
          <div>
            <strong>${t('tutorial.config_project', 'Project Paths')}</strong>
            ${t('tutorial.config_project_desc', 'ELF firmware file and compile database locations.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-debug-alt"></i>
          <div>
            <strong>${t('tutorial.config_inject', 'Injection Settings')}</strong>
            ${t('tutorial.config_inject_desc', 'Patch mode, file watch, and auto-injection options.')}
          </div>
        </div>
        <div class="tutorial-feature-item">
          <i class="codicon codicon-output"></i>
          <div>
            <strong>${t('tutorial.config_more', 'More Options')}</strong>
            ${t('tutorial.config_more_desc', 'Serial, terminal, logging, and advanced settings.')}
          </div>
        </div>
      </div>
      <p class="tutorial-hint" style="margin-top: 12px; opacity: 0.7; font-size: 12px;">
        ${t('tutorial.config_hint', 'Expand each section to configure settings.')}
      </p>
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
