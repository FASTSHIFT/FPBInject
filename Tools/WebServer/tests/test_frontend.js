/**
 * FPBInject Frontend JavaScript Tests - Main Entry Point
 *
 * Uses modular test files from tests/js/ directory.
 *
 * Run:
 *   node tests/test_frontend.js              # Basic run
 *   node tests/test_frontend.js --coverage   # With coverage report
 */

const fs = require('fs');
const path = require('path');

// Clear test module cache to ensure fresh loads
Object.keys(require.cache).forEach((key) => {
  if (key.includes('tests/js/')) delete require.cache[key];
});

// Force reload of framework
delete require.cache[require.resolve('./js/framework')];
delete require.cache[require.resolve('./js/mocks')];

// Parse command line arguments
const args = process.argv.slice(2);
const enableCoverage = args.includes('--coverage');
const isCI =
  args.includes('--ci') ||
  process.env.CI === 'true' ||
  process.env.GITHUB_ACTIONS === 'true';

// Parse --threshold parameter (default: 80%)
let coverageThreshold = 80;
const thresholdIdx = args.indexOf('--threshold');
if (thresholdIdx !== -1 && args[thresholdIdx + 1]) {
  const parsed = parseInt(args[thresholdIdx + 1], 10);
  if (!isNaN(parsed) && parsed >= 0 && parsed <= 100) {
    coverageThreshold = parsed;
  }
}

// ===================== Coverage Setup =====================

let instrumenter = null;

if (enableCoverage) {
  const { createInstrumenter } = require('istanbul-lib-instrument');
  instrumenter = createInstrumenter({
    esModules: false,
    compact: false,
    produceSourceMap: false,
  });
  global.__coverage__ = {};
}

// ===================== Load Test Framework & Mocks =====================

const framework = require('./js/framework');
const mocks = require('./js/mocks');
const { browserGlobals, resetMocks } = mocks;

framework.setCI(isCI);

// Set up global browser environment
for (const [key, value] of Object.entries(browserGlobals)) {
  try {
    global[key] = value;
  } catch (e) {}
}

// Ensure window is properly set up
global.window = browserGlobals.window;

// ===================== Load Application Code =====================

const jsDir = path.join(__dirname, '..', 'static', 'js');

// Functions that need to be available globally for cross-module calls
const globalFunctions = [
  'writeToOutput',
  'writeToSerial',
  'startLogPolling',
  'stopLogPolling',
  'fpbInfo',
  'updateDisabledState',
  'updateSlotUI',
  'updateMemoryInfo',
  'openDisassembly',
  'startAutoInjectPolling',
  'stopAutoInjectPolling',
  'checkConnectionStatus',
  'checkBackendHealth',
  'startBackendHealthCheck',
  'stopBackendHealthCheck',
  'saveConfig',
  'openFileBrowser',
  'switchEditorTab',
  'escapeHtml',
  'fitTerminals',
  'getTerminalTheme',
  'getAceEditorContent',
  'HOME_PATH',
];

// Sync window exports to global scope after each module load
function syncWindowToGlobal() {
  const w = browserGlobals.window;
  globalFunctions.forEach((fn) => {
    if (w[fn] !== undefined) {
      global[fn] = w[fn];
    }
  });
}

function loadScript(filename) {
  const filepath = path.join(jsDir, filename);
  if (!fs.existsSync(filepath)) {
    console.warn(`Warning: ${filename} not found`);
    return;
  }

  let code = fs.readFileSync(filepath, 'utf-8');

  if (enableCoverage && instrumenter) {
    const relativePath = path.join('static', 'js', filename);
    try {
      code = instrumenter.instrumentSync(code, relativePath);
    } catch (e) {
      console.warn(`Warning: Could not instrument ${filename}: ${e.message}`);
    }
  }

  try {
    // Use indirect eval to run in global scope while preserving __coverage__
    (0, eval)(code);
    // Sync window exports to global after each module loads
    syncWindowToGlobal();
  } catch (e) {
    console.error(`Error loading ${filename}: ${e.message}`);
  }
}

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
  'features/transfer.js',
];

console.log('Loading application modules...');
modules.forEach(loadScript);

// Get window reference (application code exports to window)
const w = browserGlobals.window;

// Initialize framework with mocks and window reference for state isolation
framework.init(mocks, w);

// ===================== Run Test Modules =====================

console.log('Running tests...\n');

require('./js/test_state')(w);
require('./js/test_theme')(w);
require('./js/test_terminal')(w);
require('./js/test_connection')(w);
require('./js/test_logs')(w);
require('./js/test_slots')(w);
require('./js/test_ui')(w);
require('./js/test_sash')(w);
require('./js/test_sidebar')(w);
require('./js/test_patch')(w);
require('./js/test_editor')(w);
require('./js/test_config')(w);
require('./js/test_features')(w);
require('./js/test_transfer')(w);

// Wait for all async tests to complete then report results
(async () => {
  await framework.waitForPendingTests();

  // ===================== Results & Coverage Report =====================

  const stats = framework.getStats();

  console.log('\n========================================');
  console.log('    FPBInject Frontend Tests');
  console.log('========================================');
  console.log(`\n    Results: ${stats.passCount}/${stats.testCount} passed`);

  if (stats.failCount > 0) {
    console.log(
      isCI
        ? `    ${stats.failCount} tests failed`
        : `\x1b[31m    ${stats.failCount} tests failed\x1b[0m`,
    );
    console.log(isCI ? '\n##[error]Failed tests:' : '\nFailed tests:');
    stats.failedTests.forEach((t) => {
      console.log(
        `  ${isCI ? '' : '\x1b[31m'}- ${t.name}: ${t.error}${isCI ? '' : '\x1b[0m'}`,
      );
    });
  }

  // Generate coverage report
  if (enableCoverage && global.__coverage__) {
    const libCoverage = require('istanbul-lib-coverage');
    const libReport = require('istanbul-lib-report');
    const reports = require('istanbul-reports');

    console.log('\n========================================');
    console.log('    Coverage Report');
    console.log('========================================\n');

    const coverageMap = libCoverage.createCoverageMap(global.__coverage__);
    const context = libReport.createContext({
      dir: path.join(__dirname, 'coverage'),
      coverageMap,
    });

    reports.create('text').execute(context);
    reports.create('html').execute(context);
    reports.create('lcov').execute(context);

    console.log(`\nReports saved to: ${path.join(__dirname, 'coverage')}`);

    // Calculate overall coverage and check threshold
    const summary = coverageMap.getCoverageSummary();
    const stmtCoverage = summary.statements.pct;

    console.log('\n========================================');
    console.log('    Coverage Threshold Check');
    console.log('========================================');
    console.log(`\n    Statement coverage: ${stmtCoverage.toFixed(2)}%`);
    console.log(`    Required threshold: ${coverageThreshold}%`);

    if (stmtCoverage < coverageThreshold) {
      console.log(
        isCI
          ? `\n##[error]Coverage ${stmtCoverage.toFixed(2)}% is below threshold ${coverageThreshold}%`
          : `\n\x1b[31m    ❌ Coverage is below threshold!\x1b[0m`,
      );
      process.exit(1);
    } else {
      console.log(
        isCI
          ? `\n    ✅ Coverage meets threshold`
          : `\n\x1b[32m    ✅ Coverage meets threshold\x1b[0m`,
      );
    }
  }

  process.exit(stats.failCount > 0 ? 1 : 0);
})();
