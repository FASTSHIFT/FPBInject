/**
 * Tests for core/logs.js
 */
const { describe, it, assertEqual, assertTrue } = require('./framework');
const { resetMocks } = require('./mocks');

module.exports = function (w) {
  describe('Log Polling Functions (core/logs.js)', () => {
    it('startLogPolling is a function', () =>
      assertTrue(typeof w.startLogPolling === 'function'));
    it('stopLogPolling is a function', () =>
      assertTrue(typeof w.stopLogPolling === 'function'));
    it('fetchLogs is a function', () =>
      assertTrue(typeof w.fetchLogs === 'function'));
  });

  describe('startLogPolling Function', () => {
    it('resets toolLogNextId', () => {
      w.FPBState.toolLogNextId = 100;
      w.startLogPolling();
      assertEqual(w.FPBState.toolLogNextId, 0);
      w.stopLogPolling();
    });
    it('resets rawLogNextId', () => {
      w.FPBState.rawLogNextId = 100;
      w.startLogPolling();
      assertEqual(w.FPBState.rawLogNextId, 0);
      w.stopLogPolling();
    });
    it('resets slotUpdateId', () => {
      w.FPBState.slotUpdateId = 50;
      w.startLogPolling();
      assertEqual(w.FPBState.slotUpdateId, 0);
      w.stopLogPolling();
    });
    it('sets logPollInterval', () => {
      w.FPBState.logPollInterval = null;
      w.startLogPolling();
      assertTrue(w.FPBState.logPollInterval !== null);
      w.stopLogPolling();
    });
    it('stops existing polling before starting new', () => {
      w.FPBState.logPollInterval = 123;
      w.startLogPolling();
      assertTrue(w.FPBState.logPollInterval !== 123);
      w.stopLogPolling();
    });
  });

  describe('stopLogPolling Function', () => {
    it('clears interval', () => {
      w.FPBState.logPollInterval = 123;
      w.stopLogPolling();
      assertEqual(w.FPBState.logPollInterval, null);
    });
    it('handles null interval', () => {
      w.FPBState.logPollInterval = null;
      w.stopLogPolling();
      assertEqual(w.FPBState.logPollInterval, null);
    });
    it('can be called multiple times', () => {
      w.FPBState.logPollInterval = 123;
      w.stopLogPolling();
      w.stopLogPolling();
      assertEqual(w.FPBState.logPollInterval, null);
    });
  });

  describe('fetchLogs Function', () => {
    it('is async function', () => {
      assertTrue(w.fetchLogs.constructor.name === 'AsyncFunction');
    });
  });
};
