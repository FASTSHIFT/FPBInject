/**
 * Tests for core/connection.js
 */
const { describe, it, assertEqual, assertTrue } = require('./framework');
const { resetMocks } = require('./mocks');

module.exports = function (w) {
  describe('Connection Functions (core/connection.js)', () => {
    it('refreshPorts is a function', () =>
      assertTrue(typeof w.refreshPorts === 'function'));
    it('toggleConnect is a function', () =>
      assertTrue(typeof w.toggleConnect === 'function'));
    it('handleConnected is a function', () =>
      assertTrue(typeof w.handleConnected === 'function'));
    it('handleDisconnected is a function', () =>
      assertTrue(typeof w.handleDisconnected === 'function'));
    it('checkConnectionStatus is a function', () =>
      assertTrue(typeof w.checkConnectionStatus === 'function'));
  });

  describe('handleConnected Function', () => {
    it('is callable', () => {
      assertTrue(typeof w.handleConnected === 'function');
    });
  });

  describe('handleDisconnected Function', () => {
    it('is callable', () => {
      assertTrue(typeof w.handleDisconnected === 'function');
    });
  });

  describe('toggleConnect Function', () => {
    it('is async function', () => {
      assertTrue(w.toggleConnect.constructor.name === 'AsyncFunction');
    });
  });

  describe('checkConnectionStatus Function', () => {
    it('is async function', () => {
      assertTrue(w.checkConnectionStatus.constructor.name === 'AsyncFunction');
    });
  });

  describe('refreshPorts Function', () => {
    it('is async function', () => {
      assertTrue(w.refreshPorts.constructor.name === 'AsyncFunction');
    });
  });
};
