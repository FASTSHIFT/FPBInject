/**
 * Tests for features/fpb.js, features/symbols.js, features/autoinject.js, features/filebrowser.js
 */
const { describe, it, assertEqual, assertTrue } = require('./framework');
const { resetMocks } = require('./mocks');

module.exports = function (w) {
  describe('FPB Command Functions (features/fpb.js)', () => {
    it('fpbPing is a function', () =>
      assertTrue(typeof w.fpbPing === 'function'));
    it('fpbTestSerial is a function', () =>
      assertTrue(typeof w.fpbTestSerial === 'function'));
    it('fpbInfo is a function', () =>
      assertTrue(typeof w.fpbInfo === 'function'));
    it('fpbInjectMulti is a function', () =>
      assertTrue(typeof w.fpbInjectMulti === 'function'));
  });

  describe('Symbol Functions (features/symbols.js)', () => {
    it('searchSymbols is a function', () =>
      assertTrue(typeof w.searchSymbols === 'function'));
    it('selectSymbol is a function', () =>
      assertTrue(typeof w.selectSymbol === 'function'));
  });

  describe('Auto-Inject Functions (features/autoinject.js)', () => {
    it('startAutoInjectPolling is a function', () =>
      assertTrue(typeof w.startAutoInjectPolling === 'function'));
    it('stopAutoInjectPolling is a function', () =>
      assertTrue(typeof w.stopAutoInjectPolling === 'function'));
    it('pollAutoInjectStatus is a function', () =>
      assertTrue(typeof w.pollAutoInjectStatus === 'function'));
    it('displayAutoInjectStats is a function', () =>
      assertTrue(typeof w.displayAutoInjectStats === 'function'));
    it('createPatchPreviewTab is a function', () =>
      assertTrue(typeof w.createPatchPreviewTab === 'function'));
  });

  describe('File Browser Functions (features/filebrowser.js)', () => {
    it('HOME_PATH is defined', () => assertEqual(w.HOME_PATH, '~'));
    it('browseFile is a function', () =>
      assertTrue(typeof w.browseFile === 'function'));
    it('browseDir is a function', () =>
      assertTrue(typeof w.browseDir === 'function'));
    it('openFileBrowser is a function', () =>
      assertTrue(typeof w.openFileBrowser === 'function'));
    it('closeFileBrowser is a function', () =>
      assertTrue(typeof w.closeFileBrowser === 'function'));
    it('sendTerminalCommand is a function', () =>
      assertTrue(typeof w.sendTerminalCommand === 'function'));
    it('navigateTo is a function', () =>
      assertTrue(typeof w.navigateTo === 'function'));
    it('selectFileBrowserItem is a function', () =>
      assertTrue(typeof w.selectFileBrowserItem === 'function'));
    it('selectBrowserItem is a function', () =>
      assertTrue(typeof w.selectBrowserItem === 'function'));
    it('onBrowserPathKeyup is a function', () =>
      assertTrue(typeof w.onBrowserPathKeyup === 'function'));
    it('refreshSymbolsFromELF is a function', () =>
      assertTrue(typeof w.refreshSymbolsFromELF === 'function'));
  });

  describe('LocalStorage Integration', () => {
    it('stores and retrieves values', () => {
      w.localStorage.setItem('test-key', 'test-value');
      assertEqual(w.localStorage.getItem('test-key'), 'test-value');
    });
    it('returns null for non-existent keys', () => {
      assertEqual(w.localStorage.getItem('nonexistent-key'), null);
    });
    it('removes items correctly', () => {
      w.localStorage.setItem('remove-test', 'value');
      w.localStorage.removeItem('remove-test');
      assertEqual(w.localStorage.getItem('remove-test'), null);
    });
    it('clears all items', () => {
      w.localStorage.setItem('clear-test', 'value');
      w.localStorage.clear();
      assertEqual(w.localStorage.getItem('clear-test'), null);
    });
  });
};
