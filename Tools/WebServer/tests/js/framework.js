/**
 * Test Framework - Assertion functions and test runner
 */

let testCount = 0;
let passCount = 0;
let failCount = 0;
const failedTests = [];
let isCI = false;

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

function describe(name, fn) {
  if (isCI) console.log(`\n##[group]${name}`);
  else console.log(`\n\x1b[36m${name}\x1b[0m`);
  fn();
  if (isCI) console.log('##[endgroup]');
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

function assertFalse(value, msg = '') {
  if (value) throw new Error(`${msg} Expected false, got ${value}`);
}

function assertContains(str, substr, msg = '') {
  if (!str.includes(substr)) {
    throw new Error(
      `${msg} Expected "${str.substring(0, 50)}..." to contain "${substr}"`,
    );
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
};
