/**
 * Tests for features/config.js
 */
const { describe, it, assertTrue, assertEqual } = require('./framework');
const { resetMocks } = require('./mocks');

module.exports = function (w) {
  describe('Config Functions (features/config.js)', () => {
    it('loadConfig is a function', () =>
      assertTrue(typeof w.loadConfig === 'function'));
    it('saveConfig is a function', () =>
      assertTrue(typeof w.saveConfig === 'function'));
    it('setupAutoSave is a function', () =>
      assertTrue(typeof w.setupAutoSave === 'function'));
    it('onAutoCompileChange is a function', () =>
      assertTrue(typeof w.onAutoCompileChange === 'function'));
    it('getWatchDirs is a function', () =>
      assertTrue(typeof w.getWatchDirs === 'function'));
    it('addWatchDir is a function', () =>
      assertTrue(typeof w.addWatchDir === 'function'));
    it('updateWatchDirsList is a function', () =>
      assertTrue(typeof w.updateWatchDirsList === 'function'));
    it('addWatchDirItem is a function', () =>
      assertTrue(typeof w.addWatchDirItem === 'function'));
    it('browseWatchDir is a function', () =>
      assertTrue(typeof w.browseWatchDir === 'function'));
    it('removeWatchDir is a function', () =>
      assertTrue(typeof w.removeWatchDir === 'function'));
    it('onEnableDecompileChange is a function', () =>
      assertTrue(typeof w.onEnableDecompileChange === 'function'));
  });

  describe('getWatchDirs Function', () => {
    it('returns array', () => {
      const dirs = w.getWatchDirs();
      assertTrue(Array.isArray(dirs));
    });
  });

  describe('updateWatchDirsList Function', () => {
    it('handles empty array', () => {
      w.updateWatchDirsList([]);
      assertTrue(true);
    });
    it('handles null', () => {
      w.updateWatchDirsList(null);
      assertTrue(true);
    });
    it('handles undefined', () => {
      w.updateWatchDirsList(undefined);
      assertTrue(true);
    });
    it('handles array with items', () => {
      w.updateWatchDirsList(['/path/to/dir1', '/path/to/dir2']);
      assertTrue(true);
    });
  });

  describe('loadConfig Function', () => {
    it('is async function', () => {
      assertTrue(w.loadConfig.constructor.name === 'AsyncFunction');
    });
  });

  describe('saveConfig Function', () => {
    it('is async function', () => {
      assertTrue(w.saveConfig.constructor.name === 'AsyncFunction');
    });
  });
};
