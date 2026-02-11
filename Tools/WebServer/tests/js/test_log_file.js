/**
 * Tests for log file recording functionality
 */
const { describe, it, assertTrue, assertEqual } = require('./framework');
const { browserGlobals } = require('./mocks');

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
      assertTrue(browseBtn.disabled);
      assertEqual(pathInput.style.opacity, '0.5');
      assertEqual(browseBtn.style.opacity, '0.5');
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
      assertTrue(!browseBtn.disabled);
      assertEqual(pathInput.style.opacity, '1');
      assertEqual(browseBtn.style.opacity, '1');
    });

    it('onLogFileEnabledChange is an async function', () => {
      assertTrue(w.onLogFileEnabledChange.constructor.name === 'AsyncFunction');
    });

    it('onLogFilePathChange is an async function', () => {
      assertTrue(w.onLogFilePathChange.constructor.name === 'AsyncFunction');
    });

    it('browseLogFile is a function', () => {
      assertTrue(typeof w.browseLogFile === 'function');
    });

    it('browseLogFile returns early when recording', () => {
      const doc = browserGlobals.document;
      doc.body.innerHTML = `
        <input type="checkbox" id="logFileEnabled" checked />
        <input type="text" id="logFilePath" value="" />
      `;

      // Mock openFileBrowser to track if it was called
      let openFileBrowserCalled = false;
      const originalOpenFileBrowser = w.openFileBrowser;
      w.openFileBrowser = () => {
        openFileBrowserCalled = true;
      };

      w.browseLogFile();

      // Should not call openFileBrowser when recording
      assertTrue(!openFileBrowserCalled);

      w.openFileBrowser = originalOpenFileBrowser;
    });
  });
};
