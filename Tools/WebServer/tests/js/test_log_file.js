/**
 * Tests for log file recording functionality
 */
const {
  describe,
  it,
  assertTrue,
  assertEqual,
  assertContains,
} = require('./framework');
const {
  resetMocks,
  setFetchResponse,
  getFetchCalls,
  browserGlobals,
} = require('./mocks');

module.exports = function (w) {
  describe('Log File Recording (features/config.js)', () => {
    it('updateLogFilePathState disables inputs when recording', () => {
      const doc = browserGlobals.document;
      doc.body.innerHTML = `
        <input type="text" id="logFilePath" />
        <button id="browseLogFileBtn"></button>
      `;

      w.updateLogFilePathState(true);

      const pathInput = doc.getElementById('logFilePath');
      const browseBtn = doc.getElementById('browseLogFileBtn');

      assertTrue(pathInput.disabled);
      assertEqual(pathInput.style.opacity, '0.5');
    });

    it('updateLogFilePathState enables inputs when not recording', () => {
      const doc = browserGlobals.document;
      doc.body.innerHTML = `
        <input type="text" id="logFilePath" />
        <button id="browseLogFileBtn"></button>
      `;

      w.updateLogFilePathState(false);

      const pathInput = doc.getElementById('logFilePath');
      const browseBtn = doc.getElementById('browseLogFileBtn');

      assertTrue(!pathInput.disabled);
      assertEqual(pathInput.style.opacity, '1');
    });

    it('onLogFilePathChange saves path when not recording', async () => {
      const doc = browserGlobals.document;
      doc.body.innerHTML = `
        <input type="checkbox" id="logFileEnabled" />
        <input type="text" id="logFilePath" value="/tmp/new.log" />
      `;

      resetMocks();
      setFetchResponse({ success: true });

      await w.onLogFilePathChange();

      const calls = getFetchCalls();
      assertEqual(calls.length, 1);
      assertEqual(calls[0].url, '/api/config');
      assertContains(calls[0].body, 'log_file_path');
    });

    it('onLogFilePathChange does not save when recording', async () => {
      const doc = browserGlobals.document;
      doc.body.innerHTML = `
        <input type="checkbox" id="logFileEnabled" checked />
        <input type="text" id="logFilePath" value="/tmp/new.log" />
      `;

      resetMocks();

      await w.onLogFilePathChange();

      const calls = getFetchCalls();
      assertEqual(calls.length, 0);
    });

    it('onLogFilePathChange does not save empty path', async () => {
      const doc = browserGlobals.document;
      doc.body.innerHTML = `
        <input type="checkbox" id="logFileEnabled" />
        <input type="text" id="logFilePath" value="   " />
      `;

      resetMocks();

      await w.onLogFilePathChange();

      const calls = getFetchCalls();
      assertEqual(calls.length, 0);
    });

    it('onLogFileEnabledChange uses default path when empty', async () => {
      const doc = browserGlobals.document;
      doc.body.innerHTML = `
        <input type="checkbox" id="logFileEnabled" checked />
        <input type="text" id="logFilePath" value="" />
        <div id="output"></div>
      `;

      resetMocks();
      setFetchResponse({ success: true, enabled: false, path: '' });

      await w.onLogFileEnabledChange();

      const pathInput = doc.getElementById('logFilePath');
      assertEqual(pathInput.value, '~/fpb_console.log');
    });

    it('browseLogFile appends default filename to directory', () => {
      const doc = browserGlobals.document;
      doc.body.innerHTML = `
        <input type="checkbox" id="logFileEnabled" />
        <input type="text" id="logFilePath" value="" />
      `;

      w.FPBState = w.FPBState || {};
      w.HOME_PATH = '/home/user';
      w.openFileBrowser = () => {};
      w.onLogFilePathChange = () => {};

      w.browseLogFile();

      if (w.FPBState.fileBrowserCallback) {
        w.FPBState.fileBrowserCallback('/tmp');
        const pathInput = doc.getElementById('logFilePath');
        assertEqual(pathInput.value, '/tmp/console.log');
      }
    });

    it('browseLogFile keeps .log filename', () => {
      const doc = browserGlobals.document;
      doc.body.innerHTML = `
        <input type="checkbox" id="logFileEnabled" />
        <input type="text" id="logFilePath" value="" />
      `;

      w.FPBState = w.FPBState || {};
      w.HOME_PATH = '/home/user';
      w.openFileBrowser = () => {};
      w.onLogFilePathChange = () => {};

      w.browseLogFile();

      if (w.FPBState.fileBrowserCallback) {
        w.FPBState.fileBrowserCallback('/tmp/my.log');
        const pathInput = doc.getElementById('logFilePath');
        assertEqual(pathInput.value, '/tmp/my.log');
      }
    });
  });
};
