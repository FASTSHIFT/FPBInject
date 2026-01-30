/**
 * FPBInject Frontend JavaScript Tests
 *
 * Tests the actual application code in static/js/ with coverage.
 * Uses istanbul for code instrumentation and coverage tracking.
 *
 * Run:
 *   node tests/test_frontend.js              # Basic run
 *   node tests/test_frontend.js --coverage   # With coverage report
 *   npm run test:ci                          # CI mode with coverage
 */

const fs = require('fs');
const path = require('path');

// Parse command line arguments
const args = process.argv.slice(2);
const enableCoverage = args.includes('--coverage');
const isCI =
  args.includes('--ci') ||
  process.env.CI === 'true' ||
  process.env.GITHUB_ACTIONS === 'true';

// ===================== Coverage Setup =====================

let instrumenter = null;
let coverageMap = null;

if (enableCoverage) {
  const { createInstrumenter } = require('istanbul-lib-instrument');
  const libCoverage = require('istanbul-lib-coverage');

  instrumenter = createInstrumenter({
    esModules: false,
    compact: false,
    produceSourceMap: false,
  });
  coverageMap = libCoverage.createCoverageMap({});

  // Initialize global coverage object
  global.__coverage__ = {};
}

// ===================== Test Framework =====================

let testCount = 0;
let passCount = 0;
let failCount = 0;
const failedTests = [];

function describe(name, fn) {
  if (isCI) {
    console.log(`\n##[group]${name}`);
  } else {
    console.log(`\n\x1b[36m${name}\x1b[0m`);
  }
  fn();
  if (isCI) {
    console.log('##[endgroup]');
  }
}

function it(name, fn) {
  testCount++;
  try {
    fn();
    passCount++;
    console.log(`  ${isCI ? '' : '\x1b[32m'}✓${isCI ? '' : '\x1b[0m'} ${name}`);
  } catch (e) {
    failCount++;
    failedTests.push({ name, error: e.message });
    console.log(`  ${isCI ? '' : '\x1b[31m'}✗${isCI ? '' : '\x1b[0m'} ${name}`);
    console.log(
      `    ${isCI ? '' : '\x1b[31m'}${e.message}${isCI ? '' : '\x1b[0m'}`,
    );
  }
}

function assertEqual(actual, expected, msg = '') {
  if (actual !== expected) {
    throw new Error(
      `${msg} Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
    );
  }
}

function assertTrue(value, msg = '') {
  if (!value) throw new Error(`${msg} Expected true, got ${value}`);
}

function assertContains(str, substr, msg = '') {
  if (!str.includes(substr)) {
    throw new Error(`${msg} Expected "${str}" to contain "${substr}"`);
  }
}

function assertDeepEqual(actual, expected, msg = '') {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `${msg} Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
    );
  }
}

// ===================== Browser Environment Setup =====================

const mockLocalStorage = {
  _store: {},
  getItem(key) {
    return this._store[key] || null;
  },
  setItem(key, value) {
    this._store[key] = String(value);
  },
  removeItem(key) {
    delete this._store[key];
  },
  clear() {
    this._store = {};
  },
};

const mockElements = {};
function createMockElement(id) {
  return {
    id,
    value: '',
    _textContent: '',
    get textContent() {
      return this._textContent;
    },
    set textContent(v) {
      this._textContent = v;
      this._innerHTML = v
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    },
    _innerHTML: '',
    get innerHTML() {
      return this._innerHTML;
    },
    set innerHTML(v) {
      this._innerHTML = v;
    },
    className: '',
    style: {
      display: '',
      opacity: '',
      width: '',
      height: '',
      background: '',
      visibility: '',
      pointerEvents: '',
    },
    classList: {
      _classes: new Set(),
      add(cls) {
        this._classes.add(cls);
      },
      remove(cls) {
        this._classes.delete(cls);
      },
      contains(cls) {
        return this._classes.has(cls);
      },
      toggle(cls, force) {
        if (force !== undefined) {
          force ? this._classes.add(cls) : this._classes.delete(cls);
        } else {
          this._classes.has(cls)
            ? this._classes.delete(cls)
            : this._classes.add(cls);
        }
      },
    },
    addEventListener() {},
    removeEventListener() {},
    appendChild() {},
    querySelectorAll() {
      return [];
    },
    querySelector() {
      return null;
    },
    getAttribute() {
      return null;
    },
    setAttribute() {},
    checked: false,
    disabled: false,
    open: false,
    tagName: 'DIV',
    title: '',
  };
}

// Global browser environment
const browserGlobals = {
  localStorage: mockLocalStorage,
  document: {
    getElementById(id) {
      if (!mockElements[id]) mockElements[id] = createMockElement(id);
      return mockElements[id];
    },
    querySelectorAll() {
      return [];
    },
    querySelector() {
      return null;
    },
    createElement(tag) {
      return createMockElement(`_created_${tag}_${Date.now()}`);
    },
    addEventListener() {},
    documentElement: {
      getAttribute() {
        return 'dark';
      },
      setAttribute() {},
      style: { setProperty() {} },
    },
  },
  window: null, // Will be set below
  console,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  Promise,
  Map,
  Set,
  Array,
  Object,
  JSON,
  Math,
  Date,
  RegExp,
  Error,
  parseInt,
  parseFloat,
  isNaN,
  encodeURIComponent,
  decodeURIComponent,
  fetch: async () => ({
    json: async () => ({}),
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    text: async () => '{}',
    body: { getReader: () => ({ read: async () => ({ done: true }) }) },
  }),
  alert() {},
  confirm() {
    return true;
  },
  requestAnimationFrame(cb) {
    cb();
  },
  getComputedStyle() {
    return { getPropertyValue: () => '300px' };
  },
  Terminal: class {
    constructor() {}
    open() {}
    loadAddon() {}
    writeln() {}
    write() {}
    clear() {}
    getSelection() {
      return '';
    }
    attachCustomKeyEventHandler() {}
    onData() {}
  },
  FitAddon: {
    FitAddon: class {
      fit() {}
    },
  },
  ace: {
    edit() {
      return {
        setTheme() {},
        session: { setMode() {} },
        setOptions() {},
        setValue() {},
        getValue() {
          return '';
        },
        resize() {},
        destroy() {},
      };
    },
  },
  hljs: { highlightElement() {} },
};

// Create window object that references browserGlobals
browserGlobals.window = {
  localStorage: browserGlobals.localStorage,
  document: browserGlobals.document,
  fetch: browserGlobals.fetch,
  alert: browserGlobals.alert,
  confirm: browserGlobals.confirm,
  addEventListener() {},
  FPBState: null,
};

// ===================== Load Application Code =====================

const jsDir = path.join(__dirname, '..', 'static', 'js');

// Set up global context
for (const [key, value] of Object.entries(browserGlobals)) {
  try {
    if (key in global) {
      Object.defineProperty(global, key, {
        value,
        writable: true,
        configurable: true,
      });
    } else {
      global[key] = value;
    }
  } catch (e) {
    // Some properties can't be overridden
  }
}

function loadScript(filename) {
  const filepath = path.join(jsDir, filename);
  if (!fs.existsSync(filepath)) {
    console.warn(`Warning: ${filename} not found`);
    return;
  }

  let code = fs.readFileSync(filepath, 'utf-8');

  // Instrument code for coverage if enabled
  if (enableCoverage && instrumenter) {
    const relativePath = path.join('static', 'js', filename);
    try {
      code = instrumenter.instrumentSync(code, relativePath);
    } catch (e) {
      console.warn(`Warning: Could not instrument ${filename}: ${e.message}`);
    }
  }

  try {
    // Use Function constructor to execute in global scope
    const fn = new Function(code);
    fn();
  } catch (e) {
    console.error(`Error loading ${filename}: ${e.message}`);
  }
}

// Load modules in dependency order
const modules = [
  'core/state.js',
  'core/theme.js',
  'core/terminal.js',
  'core/connection.js',
  'core/logs.js',
  'core/slots.js',
  'ui/sash.js',
  'ui/sidebar.js',
  'features/fpb.js',
  'features/patch.js',
  'features/symbols.js',
  'features/editor.js',
  'features/config.js',
  'features/autoinject.js',
  'features/filebrowser.js',
];

console.log('Loading application modules...');
modules.forEach(loadScript);

// Get reference to window for tests
const w = browserGlobals.window;

// ===================== Tests =====================

describe('FPBState (core/state.js)', () => {
  it('FPBState is defined', () => {
    assertTrue(w.FPBState !== undefined, 'FPBState should be defined');
  });

  it('FPBState.isConnected defaults to false', () => {
    assertEqual(w.FPBState.isConnected, false);
  });

  it('FPBState.selectedSlot defaults to 0', () => {
    assertEqual(w.FPBState.selectedSlot, 0);
  });

  it('FPBState.slotStates has 6 slots', () => {
    assertEqual(w.FPBState.slotStates.length, 6);
  });

  it('FPBState.slotStates slots have correct structure', () => {
    const slot = w.FPBState.slotStates[0];
    assertEqual(slot.occupied, false);
    assertEqual(slot.func, '');
    assertEqual(slot.orig_addr, '');
    assertEqual(slot.target_addr, '');
    assertEqual(slot.code_size, 0);
  });

  it('FPBState.aceEditors is a Map', () => {
    assertTrue(w.FPBState.aceEditors instanceof Map);
  });

  it('FPBState.editorTabs is an array', () => {
    assertTrue(Array.isArray(w.FPBState.editorTabs));
  });
});

describe('Theme Functions (core/theme.js)', () => {
  it('darkTerminalTheme is defined', () => {
    assertTrue(w.darkTerminalTheme !== undefined);
    assertEqual(w.darkTerminalTheme.background, '#1e1e1e');
  });

  it('lightTerminalTheme is defined', () => {
    assertTrue(w.lightTerminalTheme !== undefined);
    assertEqual(w.lightTerminalTheme.background, '#f3f3f3');
  });

  it('getTerminalTheme returns dark theme', () => {
    const theme = w.getTerminalTheme();
    assertTrue(theme !== undefined);
  });

  it('toggleTheme is a function', () => {
    assertTrue(typeof w.toggleTheme === 'function');
  });

  it('loadThemePreference is a function', () => {
    assertTrue(typeof w.loadThemePreference === 'function');
  });

  it('updateAceEditorsTheme is a function', () => {
    assertTrue(typeof w.updateAceEditorsTheme === 'function');
  });
});

describe('Terminal Functions (core/terminal.js)', () => {
  it('initTerminals is a function', () => {
    assertTrue(typeof w.initTerminals === 'function');
  });

  it('fitTerminals is a function', () => {
    assertTrue(typeof w.fitTerminals === 'function');
  });

  it('switchTerminalTab is a function', () => {
    assertTrue(typeof w.switchTerminalTab === 'function');
  });

  it('writeToOutput is a function', () => {
    assertTrue(typeof w.writeToOutput === 'function');
  });

  it('writeToSerial is a function', () => {
    assertTrue(typeof w.writeToSerial === 'function');
  });

  it('clearCurrentTerminal is a function', () => {
    assertTrue(typeof w.clearCurrentTerminal === 'function');
  });
});

describe('Connection Functions (core/connection.js)', () => {
  it('refreshPorts is a function', () => {
    assertTrue(typeof w.refreshPorts === 'function');
  });

  it('toggleConnect is a function', () => {
    assertTrue(typeof w.toggleConnect === 'function');
  });

  it('handleConnected is a function', () => {
    assertTrue(typeof w.handleConnected === 'function');
  });

  it('handleDisconnected is a function', () => {
    assertTrue(typeof w.handleDisconnected === 'function');
  });

  it('checkConnectionStatus is a function', () => {
    assertTrue(typeof w.checkConnectionStatus === 'function');
  });
});

describe('Log Polling Functions (core/logs.js)', () => {
  it('startLogPolling is a function', () => {
    assertTrue(typeof w.startLogPolling === 'function');
  });

  it('stopLogPolling is a function', () => {
    assertTrue(typeof w.stopLogPolling === 'function');
  });

  it('fetchLogs is a function', () => {
    assertTrue(typeof w.fetchLogs === 'function');
  });
});

describe('Slot Functions (core/slots.js)', () => {
  it('updateSlotUI is a function', () => {
    assertTrue(typeof w.updateSlotUI === 'function');
  });

  it('selectSlot is a function', () => {
    assertTrue(typeof w.selectSlot === 'function');
  });

  it('fpbUnpatch is a function', () => {
    assertTrue(typeof w.fpbUnpatch === 'function');
  });

  it('fpbReinject is a function', () => {
    assertTrue(typeof w.fpbReinject === 'function');
  });

  it('fpbUnpatchAll is a function', () => {
    assertTrue(typeof w.fpbUnpatchAll === 'function');
  });

  it('updateMemoryInfo is a function', () => {
    assertTrue(typeof w.updateMemoryInfo === 'function');
  });
});

describe('Sash Functions (ui/sash.js)', () => {
  it('initSashResize is a function', () => {
    assertTrue(typeof w.initSashResize === 'function');
  });

  it('loadLayoutPreferences is a function', () => {
    assertTrue(typeof w.loadLayoutPreferences === 'function');
  });

  it('saveLayoutPreferences is a function', () => {
    assertTrue(typeof w.saveLayoutPreferences === 'function');
  });
});

describe('Sidebar Functions (ui/sidebar.js)', () => {
  it('loadSidebarState is a function', () => {
    assertTrue(typeof w.loadSidebarState === 'function');
  });

  it('saveSidebarState is a function', () => {
    assertTrue(typeof w.saveSidebarState === 'function');
  });

  it('setupSidebarStateListeners is a function', () => {
    assertTrue(typeof w.setupSidebarStateListeners === 'function');
  });

  it('updateDisabledState is a function', () => {
    assertTrue(typeof w.updateDisabledState === 'function');
  });
});

describe('FPB Command Functions (features/fpb.js)', () => {
  it('fpbPing is a function', () => {
    assertTrue(typeof w.fpbPing === 'function');
  });

  it('fpbTestSerial is a function', () => {
    assertTrue(typeof w.fpbTestSerial === 'function');
  });

  it('fpbInfo is a function', () => {
    assertTrue(typeof w.fpbInfo === 'function');
  });

  it('fpbInjectMulti is a function', () => {
    assertTrue(typeof w.fpbInjectMulti === 'function');
  });
});

describe('Patch Functions (features/patch.js)', () => {
  it('generatePatchTemplate is a function', () => {
    assertTrue(typeof w.generatePatchTemplate === 'function');
  });

  it('parseSignature is a function', () => {
    assertTrue(typeof w.parseSignature === 'function');
  });

  it('extractParamNames is a function', () => {
    assertTrue(typeof w.extractParamNames === 'function');
  });

  it('performInject is a function', () => {
    assertTrue(typeof w.performInject === 'function');
  });

  it('displayInjectionStats is a function', () => {
    assertTrue(typeof w.displayInjectionStats === 'function');
  });
});

describe('parseSignature Function', () => {
  it('extracts return type and params', () => {
    const result = w.parseSignature('int main(int argc, char **argv)', 'main');
    assertEqual(result.returnType, 'int');
    assertEqual(result.params, 'int argc, char **argv');
  });

  it('handles void return', () => {
    const result = w.parseSignature('void setup(void)', 'setup');
    assertEqual(result.returnType, 'void');
    assertEqual(result.params, '');
  });

  it('handles pointer return types', () => {
    const result = w.parseSignature('char *get_string(int id)', 'get_string');
    assertEqual(result.returnType, 'char *');
  });
});

describe('extractParamNames Function', () => {
  it('extracts simple params', () => {
    const names = w.extractParamNames('int x, int y');
    assertDeepEqual(names, ['x', 'y']);
  });

  it('handles pointers', () => {
    const names = w.extractParamNames('char *str, int *ptr');
    assertDeepEqual(names, ['str', 'ptr']);
  });

  it('handles arrays', () => {
    const names = w.extractParamNames('int arr[], char buf[256]');
    assertDeepEqual(names, ['arr', 'buf']);
  });

  it('returns empty for void', () => {
    const names = w.extractParamNames('void');
    assertDeepEqual(names, []);
  });

  it('returns empty for empty string', () => {
    const names = w.extractParamNames('');
    assertDeepEqual(names, []);
  });
});

describe('generatePatchTemplate Function', () => {
  it('generates template with function name', () => {
    const template = w.generatePatchTemplate('test_func', 0);
    assertContains(template, 'test_func');
    assertContains(template, 'inject_test_func');
    assertContains(template, 'Slot: 0');
  });

  it('includes signature when provided', () => {
    const template = w.generatePatchTemplate(
      'my_func',
      1,
      'int my_func(int x)',
    );
    assertContains(template, 'int my_func(int x)');
  });
});

describe('Symbol Functions (features/symbols.js)', () => {
  it('searchSymbols is a function', () => {
    assertTrue(typeof w.searchSymbols === 'function');
  });

  it('selectSymbol is a function', () => {
    assertTrue(typeof w.selectSymbol === 'function');
  });
});

describe('Editor Functions (features/editor.js)', () => {
  it('initAceEditor is a function', () => {
    assertTrue(typeof w.initAceEditor === 'function');
  });

  it('getAceEditorContent is a function', () => {
    assertTrue(typeof w.getAceEditorContent === 'function');
  });

  it('switchEditorTab is a function', () => {
    assertTrue(typeof w.switchEditorTab === 'function');
  });

  it('closeTab is a function', () => {
    assertTrue(typeof w.closeTab === 'function');
  });

  it('openDisassembly is a function', () => {
    assertTrue(typeof w.openDisassembly === 'function');
  });

  it('openManualPatchTab is a function', () => {
    assertTrue(typeof w.openManualPatchTab === 'function');
  });

  it('escapeHtml is a function', () => {
    assertTrue(typeof w.escapeHtml === 'function');
  });
});

describe('escapeHtml Function', () => {
  it('escapes HTML special characters', () => {
    const result = w.escapeHtml('<script>alert("xss")</script>');
    assertContains(result, '&lt;');
    assertContains(result, '&gt;');
  });

  it('leaves normal text unchanged', () => {
    assertEqual(w.escapeHtml('Hello World'), 'Hello World');
  });
});

describe('Config Functions (features/config.js)', () => {
  it('loadConfig is a function', () => {
    assertTrue(typeof w.loadConfig === 'function');
  });

  it('saveConfig is a function', () => {
    assertTrue(typeof w.saveConfig === 'function');
  });

  it('setupAutoSave is a function', () => {
    assertTrue(typeof w.setupAutoSave === 'function');
  });

  it('onAutoCompileChange is a function', () => {
    assertTrue(typeof w.onAutoCompileChange === 'function');
  });

  it('getWatchDirs is a function', () => {
    assertTrue(typeof w.getWatchDirs === 'function');
  });

  it('addWatchDir is a function', () => {
    assertTrue(typeof w.addWatchDir === 'function');
  });
});

describe('Auto-Inject Functions (features/autoinject.js)', () => {
  it('startAutoInjectPolling is a function', () => {
    assertTrue(typeof w.startAutoInjectPolling === 'function');
  });

  it('stopAutoInjectPolling is a function', () => {
    assertTrue(typeof w.stopAutoInjectPolling === 'function');
  });

  it('pollAutoInjectStatus is a function', () => {
    assertTrue(typeof w.pollAutoInjectStatus === 'function');
  });

  it('displayAutoInjectStats is a function', () => {
    assertTrue(typeof w.displayAutoInjectStats === 'function');
  });

  it('createPatchPreviewTab is a function', () => {
    assertTrue(typeof w.createPatchPreviewTab === 'function');
  });
});

describe('File Browser Functions (features/filebrowser.js)', () => {
  it('HOME_PATH is defined', () => {
    assertEqual(w.HOME_PATH, '~');
  });

  it('browseFile is a function', () => {
    assertTrue(typeof w.browseFile === 'function');
  });

  it('browseDir is a function', () => {
    assertTrue(typeof w.browseDir === 'function');
  });

  it('openFileBrowser is a function', () => {
    assertTrue(typeof w.openFileBrowser === 'function');
  });

  it('closeFileBrowser is a function', () => {
    assertTrue(typeof w.closeFileBrowser === 'function');
  });

  it('sendTerminalCommand is a function', () => {
    assertTrue(typeof w.sendTerminalCommand === 'function');
  });
});

describe('LocalStorage Integration', () => {
  it('stores and retrieves values', () => {
    mockLocalStorage.clear();
    mockLocalStorage.setItem('test_key', 'test_value');
    assertEqual(mockLocalStorage.getItem('test_key'), 'test_value');
  });

  it('returns null for non-existent keys', () => {
    mockLocalStorage.clear();
    assertEqual(mockLocalStorage.getItem('nonexistent'), null);
  });

  it('removes items correctly', () => {
    mockLocalStorage.setItem('to_remove', 'value');
    mockLocalStorage.removeItem('to_remove');
    assertEqual(mockLocalStorage.getItem('to_remove'), null);
  });
});

// ===================== Results & Coverage Report =====================

console.log('\n========================================');
console.log('    FPBInject Frontend Tests');
console.log('========================================');

console.log(`\n    Results: ${passCount}/${testCount} passed`);

if (failCount > 0) {
  if (isCI) {
    console.log(`    ${failCount} tests failed`);
    console.log('\n##[error]Failed tests:');
  } else {
    console.log(`\x1b[31m    ${failCount} tests failed\x1b[0m`);
    console.log('\nFailed tests:');
  }
  failedTests.forEach((t) => {
    console.log(
      `  ${isCI ? '' : '\x1b[31m'}- ${t.name}: ${t.error}${isCI ? '' : '\x1b[0m'}`,
    );
  });
}

// Generate coverage report if enabled
if (enableCoverage && global.__coverage__) {
  const libCoverage = require('istanbul-lib-coverage');
  const libReport = require('istanbul-lib-report');
  const reports = require('istanbul-reports');

  console.log('\n========================================');
  console.log('    Coverage Report');
  console.log('========================================\n');

  coverageMap = libCoverage.createCoverageMap(global.__coverage__);

  const context = libReport.createContext({
    dir: path.join(__dirname, 'coverage'),
    coverageMap,
  });

  // Generate text report to console
  const textReport = reports.create('text');
  textReport.execute(context);

  // Generate HTML report
  const htmlReport = reports.create('html');
  htmlReport.execute(context);

  // Generate lcov report for CI
  const lcovReport = reports.create('lcov');
  lcovReport.execute(context);

  console.log(
    `\nDetailed reports saved to: ${path.join(__dirname, 'coverage')}`,
  );
}

// Exit with appropriate code
process.exit(failCount > 0 ? 1 : 0);
