/**
 * Tests for ui/sash.js and ui/sidebar.js
 */
const { describe, it, assertTrue, assertEqual } = require('./framework');
const { mockLocalStorage, browserGlobals, resetMocks } = require('./mocks');

module.exports = function (w) {
  describe('Sash Functions (ui/sash.js)', () => {
    it('initSashResize is a function', () =>
      assertTrue(typeof w.initSashResize === 'function'));
    it('loadLayoutPreferences is a function', () =>
      assertTrue(typeof w.loadLayoutPreferences === 'function'));
    it('saveLayoutPreferences is a function', () =>
      assertTrue(typeof w.saveLayoutPreferences === 'function'));
  });

  describe('saveLayoutPreferences Function', () => {
    it('saves to localStorage', () => {
      mockLocalStorage.clear();
      w.saveLayoutPreferences();
      assertTrue(mockLocalStorage.getItem('fpbinject-sidebar-width') !== null);
    });
    it('saves panel height', () => {
      mockLocalStorage.clear();
      w.saveLayoutPreferences();
      assertTrue(mockLocalStorage.getItem('fpbinject-panel-height') !== null);
    });
  });

  describe('Sidebar Functions (ui/sidebar.js)', () => {
    it('loadSidebarState is a function', () =>
      assertTrue(typeof w.loadSidebarState === 'function'));
    it('saveSidebarState is a function', () =>
      assertTrue(typeof w.saveSidebarState === 'function'));
    it('setupSidebarStateListeners is a function', () =>
      assertTrue(typeof w.setupSidebarStateListeners === 'function'));
    it('updateDisabledState is a function', () =>
      assertTrue(typeof w.updateDisabledState === 'function'));
  });

  describe('loadSidebarState Function', () => {
    it('handles empty storage', () => {
      mockLocalStorage.clear();
      w.loadSidebarState();
      assertTrue(true);
    });
    it('handles saved state', () => {
      mockLocalStorage.setItem(
        'fpbinject-sidebar-state',
        JSON.stringify({ 'details-device': true }),
      );
      w.loadSidebarState();
      assertTrue(true);
    });
    it('handles invalid JSON', () => {
      mockLocalStorage.setItem('fpbinject-sidebar-state', 'invalid json');
      w.loadSidebarState();
      assertTrue(true);
    });
    it('handles null value', () => {
      mockLocalStorage.setItem('fpbinject-sidebar-state', 'null');
      w.loadSidebarState();
      assertTrue(true);
    });
    it('handles empty object', () => {
      mockLocalStorage.setItem('fpbinject-sidebar-state', '{}');
      w.loadSidebarState();
      assertTrue(true);
    });
  });

  describe('saveSidebarState Function', () => {
    it('saves state to localStorage', () => {
      mockLocalStorage.clear();
      w.saveSidebarState();
      assertTrue(mockLocalStorage.getItem('fpbinject-sidebar-state') !== null);
    });
    it('saves valid JSON', () => {
      mockLocalStorage.clear();
      w.saveSidebarState();
      const saved = mockLocalStorage.getItem('fpbinject-sidebar-state');
      try {
        JSON.parse(saved);
        assertTrue(true);
      } catch (e) {
        assertTrue(false);
      }
    });
  });

  describe('updateDisabledState Function', () => {
    it('handles connected state', () => {
      w.FPBState.isConnected = true;
      w.updateDisabledState();
      w.FPBState.isConnected = false;
      assertTrue(true);
    });
    it('handles disconnected state', () => {
      w.FPBState.isConnected = false;
      w.updateDisabledState();
      assertTrue(true);
    });
  });
};
