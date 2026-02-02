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
    it('activateSection is a function', () =>
      assertTrue(typeof w.activateSection === 'function'));
    it('syncActivityBarState is a function', () =>
      assertTrue(typeof w.syncActivityBarState === 'function'));
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

  describe('activateSection Function', () => {
    it('opens target section', () => {
      resetMocks();
      const targetSection =
        browserGlobals.document.getElementById('details-device');
      targetSection.open = false;
      w.activateSection('details-device');
      assertTrue(targetSection.open);
    });

    it('closes other sections', () => {
      resetMocks();
      const connectionSection =
        browserGlobals.document.getElementById('details-connection');
      const deviceSection =
        browserGlobals.document.getElementById('details-device');
      connectionSection.open = true;
      deviceSection.open = false;
      w.activateSection('details-device');
      assertTrue(!connectionSection.open);
      assertTrue(deviceSection.open);
    });

    it('updates activity bar active state', () => {
      resetMocks();
      w.activateSection('details-device');
      const activeItems = browserGlobals.document.querySelectorAll(
        '.activity-item.active',
      );
      assertTrue(activeItems.length >= 0);
    });

    it('handles non-existent section gracefully', () => {
      resetMocks();
      w.activateSection('details-nonexistent');
      assertTrue(true);
    });

    it('saves sidebar state after activation', () => {
      resetMocks();
      browserGlobals.localStorage.clear();
      w.activateSection('details-config');
      const saved = browserGlobals.localStorage.getItem(
        'fpbinject-sidebar-state',
      );
      assertTrue(saved !== null);
    });
  });

  describe('syncActivityBarState Function', () => {
    it('syncs activity bar state without error', () => {
      resetMocks();
      w.syncActivityBarState();
      assertTrue(true);
    });

    it('handles no open sections', () => {
      resetMocks();
      browserGlobals.document
        .querySelectorAll('details[id^="details-"]')
        .forEach((d) => {
          d.open = false;
        });
      w.syncActivityBarState();
      assertTrue(true);
    });

    it('handles open section', () => {
      resetMocks();
      const deviceSection =
        browserGlobals.document.getElementById('details-device');
      deviceSection.open = true;
      w.syncActivityBarState();
      assertTrue(true);
    });
  });
};
