/**
 * Test Framework - Assertion functions and test runner
 *
 * Features:
 * - Automatic state isolation: each test gets a clean FPBState
 * - Automatic mock reset before each test
 */

let testCount = 0;
let passCount = 0;
let failCount = 0;
const failedTests = [];
let isCI = false;

// References for state isolation (set via init())
let mocksModule = null;
let windowRef = null;

function setCI(value) {
  isCI = value;
}

function getStats() {
  return { testCount, passCount, failCount, failedTests };
}

function resetStats() {
  testCount = 0;
  passCount = 0;
  failCount = 0;
  failedTests.length = 0;
}

// Initialize framework with mocks and window reference
function init(mocks, win) {
  mocksModule = mocks;
  windowRef = win;
}

// Create a fresh FPBState
function createFreshFPBState() {
  return {
    isConnected: false,
    selectedSlot: 0,
    slotStates: Array(6)
      .fill()
      .map(() => ({
        occupied: false,
        func: '',
        orig_addr: '',
        target_addr: '',
        code_size: 0,
      })),
    toolTerminal: null,
    serialTerminal: null,
    logPollInterval: null,
    toolLogNextId: 0,
    serialLogNextId: 0,
    currentPatchTab: null,
    patchTabs: [],
    aceEditors: new Map(),
    autoInjectPollInterval: null,
    lastAutoInjectStatus: null,
    autoInjectProgressHideTimer: null,
    fileBrowserMode: 'file',
    currentBrowserPath: '~',
    fileBrowserCallback: null,
  };
}

// Reset FPBState to clean state
function resetFPBState() {
  if (!windowRef || !windowRef.FPBState) return;
  const state = windowRef.FPBState;
  const fresh = createFreshFPBState();
  Object.keys(fresh).forEach((key) => {
    if (key === 'aceEditors') {
      state.aceEditors.clear();
    } else {
      state[key] = fresh[key];
    }
  });
}

// Setup before each test
function beforeEachTest() {
  if (mocksModule && mocksModule.resetMocks) {
    mocksModule.resetMocks();
  }
  resetFPBState();
}

// Cleanup after each test
function afterEachTest() {
  if (windowRef && windowRef.FPBState) {
    const state = windowRef.FPBState;
    if (state.logPollInterval) {
      clearInterval(state.logPollInterval);
      state.logPollInterval = null;
    }
    if (state.autoInjectPollInterval) {
      clearInterval(state.autoInjectPollInterval);
      state.autoInjectPollInterval = null;
    }
  }
}

function describe(name, fn) {
  if (isCI) console.log(`\n##[group]${name}`);
  else console.log(`\n\x1b[36m${name}\x1b[0m`);
  fn();
  if (isCI) console.log('##[endgroup]');
}

function it(name, fn) {
  testCount++;

  // Auto reset state before each test
  beforeEachTest();

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

  // Auto cleanup after each test
  afterEachTest();
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

function assertFalse(value, msg = '') {
  if (value) throw new Error(`${msg} Expected false, got ${value}`);
}

function assertContains(str, substr, msg = '') {
  if (!str || !str.includes(substr)) {
    const preview = str ? str.substring(0, 50) : '(empty)';
    throw new Error(`${msg} Expected "${preview}..." to contain "${substr}"`);
  }
}

function assertDeepEqual(actual, expected, msg = '') {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `${msg} Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
    );
  }
}

module.exports = {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertFalse,
  assertContains,
  assertDeepEqual,
  setCI,
  getStats,
  resetStats,
  init,
  waitForPendingTests: async () => {}, // No-op for sync framework
};
