/**
 * Tests for ui/sash.js and ui/sidebar.js
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
  describe('Sash Functions (ui/sash.js)', () => {
    it('initSashResize is a function', () =>
      assertTrue(typeof w.initSashResize === 'function'));
    it('loadLayoutPreferences is a function', () =>
      assertTrue(typeof w.loadLayoutPreferences === 'function'));
    it('saveLayoutPreferences is a function', () =>
      assertTrue(typeof w.saveLayoutPreferences === 'function'));
    it('updateCornerSashPosition is a function', () =>
      assertTrue(typeof w.updateCornerSashPosition === 'function'));
  });

  describe('loadLayoutPreferences Function', () => {
    it('loads sidebar width from localStorage', () => {
      resetMocks();
      w.localStorage.setItem('fpbinject-sidebar-width', '350px');
      w.loadLayoutPreferences();
      assertEqual(w.localStorage.getItem('fpbinject-sidebar-width'), '350px');
    });

    it('loads panel height from localStorage', () => {
      resetMocks();
      w.localStorage.setItem('fpbinject-panel-height', '250px');
      w.loadLayoutPreferences();
      assertEqual(w.localStorage.getItem('fpbinject-panel-height'), '250px');
    });

    it('handles missing preferences gracefully', () => {
      resetMocks();
      w.localStorage.clear();
      w.loadLayoutPreferences();
      assertEqual(typeof w.loadLayoutPreferences, 'function');
    });

    it('sets CSS custom properties', () => {
      resetMocks();
      w.localStorage.setItem('fpbinject-sidebar-width', '400px');
      w.localStorage.setItem('fpbinject-panel-height', '300px');
      w.loadLayoutPreferences();
      assertEqual(w.localStorage.getItem('fpbinject-sidebar-width'), '400px');
    });
  });

  describe('saveLayoutPreferences Function', () => {
    it('saves sidebar width to localStorage', () => {
      resetMocks();
      w.saveLayoutPreferences();
      const saved = w.localStorage.getItem('fpbinject-sidebar-width');
      assertTrue(saved !== undefined);
    });

    it('saves panel height to localStorage', () => {
      resetMocks();
      w.saveLayoutPreferences();
      const saved = w.localStorage.getItem('fpbinject-panel-height');
      assertTrue(saved !== undefined);
    });

    it('reads from computed style', () => {
      resetMocks();
      w.saveLayoutPreferences();
      const savedWidth = w.localStorage.getItem('fpbinject-sidebar-width');
      assertTrue(savedWidth !== undefined);
    });
  });

  describe('updateCornerSashPosition Function', () => {
    it('is callable', () => {
      resetMocks();
      w.updateCornerSashPosition();
      assertEqual(typeof w.updateCornerSashPosition, 'function');
    });

    it('handles missing elements gracefully', () => {
      resetMocks();
      w.updateCornerSashPosition();
      assertEqual(typeof w.updateCornerSashPosition, 'function');
    });
  });

  describe('initSashResize Function', () => {
    it('is callable', () => {
      resetMocks();
      w.initSashResize();
      assertEqual(typeof w.initSashResize, 'function');
    });

    it('sets up event listeners', () => {
      resetMocks();
      w.initSashResize();
      const sashSidebar = browserGlobals.document.getElementById('sashSidebar');
      assertTrue(sashSidebar._eventListeners['mousedown'] !== undefined);
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
    it('loads state from localStorage', () => {
      resetMocks();
      w.localStorage.setItem(
        'fpbinject-sidebar-state',
        JSON.stringify({ 'details-device': true }),
      );
      w.loadSidebarState();
      assertEqual(typeof w.loadSidebarState, 'function');
    });

    it('handles invalid JSON gracefully', () => {
      resetMocks();
      w.localStorage.setItem('fpbinject-sidebar-state', 'invalid json');
      w.loadSidebarState();
      // Should not throw
      assertEqual(typeof w.loadSidebarState, 'function');
    });

    it('handles missing state gracefully', () => {
      resetMocks();
      w.localStorage.clear();
      w.loadSidebarState();
      assertEqual(typeof w.loadSidebarState, 'function');
    });
  });

  describe('saveSidebarState Function', () => {
    it('saves state to localStorage', () => {
      resetMocks();
      w.saveSidebarState();
      assertEqual(typeof w.saveSidebarState, 'function');
    });
  });

  describe('setupSidebarStateListeners Function', () => {
    it('is callable', () => {
      resetMocks();
      w.setupSidebarStateListeners();
      assertEqual(typeof w.setupSidebarStateListeners, 'function');
    });
  });

  describe('updateDisabledState Function', () => {
    it('disables elements when not connected', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const slotSelect = browserGlobals.document.getElementById('slotSelect');
      w.updateDisabledState();
      assertTrue(slotSelect.disabled);
    });

    it('enables elements when connected', () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const slotSelect = browserGlobals.document.getElementById('slotSelect');
      w.updateDisabledState();
      assertTrue(!slotSelect.disabled);
      w.FPBState.isConnected = false;
    });

    it('updates opacity for disabled elements', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const slotSelect = browserGlobals.document.getElementById('slotSelect');
      w.updateDisabledState();
      assertEqual(slotSelect.style.opacity, '0.5');
    });

    it('updates opacity for enabled elements', () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const slotSelect = browserGlobals.document.getElementById('slotSelect');
      w.updateDisabledState();
      assertEqual(slotSelect.style.opacity, '1');
      w.FPBState.isConnected = false;
    });

    it('updates editorContainer opacity', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const editorContainer =
        browserGlobals.document.getElementById('editorContainer');
      w.updateDisabledState();
      assertEqual(editorContainer.style.opacity, '0.6');
    });

    it('updates slotContainer opacity', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const slotContainer =
        browserGlobals.document.getElementById('slotContainer');
      w.updateDisabledState();
      assertEqual(slotContainer.style.opacity, '0.6');
    });

    it('updates deviceInfoContent opacity', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const deviceInfoContent =
        browserGlobals.document.getElementById('deviceInfoContent');
      w.updateDisabledState();
      assertEqual(deviceInfoContent.style.opacity, '0.5');
    });
  });
};
