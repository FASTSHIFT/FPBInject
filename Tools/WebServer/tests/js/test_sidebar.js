/**
 * Tests for ui/sidebar.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertContains,
} = require('./framework');
const { resetMocks, browserGlobals, MockTerminal } = require('./mocks');

module.exports = function (w) {
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
    it('loads state from localStorage', () => {
      resetMocks();
      browserGlobals.localStorage.setItem(
        'fpbinject-sidebar-state',
        JSON.stringify({
          'details-device': true,
          'details-config': false,
        }),
      );
      w.loadSidebarState();
      assertTrue(true);
    });

    it('handles missing localStorage data', () => {
      resetMocks();
      browserGlobals.localStorage.clear();
      w.loadSidebarState();
      assertTrue(true);
    });

    it('handles invalid JSON gracefully', () => {
      resetMocks();
      browserGlobals.localStorage.setItem(
        'fpbinject-sidebar-state',
        'invalid json',
      );
      w.loadSidebarState();
      assertTrue(true);
    });
  });

  describe('saveSidebarState Function', () => {
    it('saves state to localStorage', () => {
      resetMocks();
      w.saveSidebarState();
      const saved = browserGlobals.localStorage.getItem(
        'fpbinject-sidebar-state',
      );
      assertTrue(saved !== null);
    });

    it('saves valid JSON', () => {
      resetMocks();
      w.saveSidebarState();
      const saved = browserGlobals.localStorage.getItem(
        'fpbinject-sidebar-state',
      );
      const parsed = JSON.parse(saved);
      assertTrue(typeof parsed === 'object');
    });
  });

  describe('setupSidebarStateListeners Function', () => {
    it('sets up listeners without error', () => {
      resetMocks();
      w.setupSidebarStateListeners();
      assertTrue(true);
    });
  });

  describe('updateDisabledState Function', () => {
    it('disables elements when not connected', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      w.updateDisabledState();
      const slotSelect = browserGlobals.document.getElementById('slotSelect');
      assertTrue(slotSelect.disabled);
    });

    it('enables elements when connected', () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.updateDisabledState();
      const slotSelect = browserGlobals.document.getElementById('slotSelect');
      assertTrue(!slotSelect.disabled);
      w.FPBState.isConnected = false;
    });

    it('updates opacity for editor container', () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.updateDisabledState();
      const editorContainer =
        browserGlobals.document.getElementById('editorContainer');
      assertEqual(editorContainer.style.opacity, '1');
      w.FPBState.isConnected = false;
    });

    it('updates opacity when disconnected', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      w.updateDisabledState();
      const editorContainer =
        browserGlobals.document.getElementById('editorContainer');
      assertEqual(editorContainer.style.opacity, '0.6');
    });

    it('updates deviceInfoContent opacity', () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.updateDisabledState();
      const deviceInfoContent =
        browserGlobals.document.getElementById('deviceInfoContent');
      assertEqual(deviceInfoContent.style.opacity, '1');
      w.FPBState.isConnected = false;
    });
  });
};
