/**
 * Tests for log file recording functionality
 */
const {
  describe,
  it,
  assertTrue,
  assertEqual,
} = require('./framework');
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
      assertTrue(!pathInput.disabled);
      assertEqual(pathInput.style.opacity, '1');
    });

    it('onLogFilePathChange is a function', () => {
      assertTrue(typeof w.onLogFilePathChange === 'function');
    });

    it('browseLogFile is a function', () => {
      assertTrue(typeof w.browseLogFile === 'function');
    });
  });
};
