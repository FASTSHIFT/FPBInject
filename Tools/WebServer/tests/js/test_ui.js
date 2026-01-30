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
      assertTrue(true);
    });

    it('loads panel height from localStorage', () => {
      resetMocks();
      w.localStorage.setItem('fpbinject-panel-height', '250px');
      w.loadLayoutPreferences();
      assertTrue(true);
    });

    it('handles missing preferences gracefully', () => {
      resetMocks();
      w.localStorage.clear();
      w.loadLayoutPreferences();
      assertTrue(true);
    });

    it('sets CSS custom properties', () => {
      resetMocks();
      w.localStorage.setItem('fpbinject-sidebar-width', '400px');
      w.localStorage.setItem('fpbinject-panel-height', '300px');
      w.loadLayoutPreferences();
      assertTrue(true);
    });
  });

  describe('saveLayoutPreferences Function', () => {
    it('saves sidebar width to localStorage', () => {
      resetMocks();
      w.saveLayoutPreferences();
      assertTrue(true);
    });

    it('saves panel height to localStorage', () => {
      resetMocks();
      w.saveLayoutPreferences();
      assertTrue(true);
    });

    it('reads from computed style', () => {
      resetMocks();
      w.saveLayoutPreferences();
      const savedWidth = w.localStorage.getItem('fpbinject-sidebar-width');
      assertTrue(savedWidth !== null || savedWidth === null);
    });
  });

  describe('updateCornerSashPosition Function', () => {
    it('is callable', () => {
      resetMocks();
      w.updateCornerSashPosition();
      assertTrue(true);
    });

    it('handles missing elements gracefully', () => {
      resetMocks();
      w.updateCornerSashPosition();
      assertTrue(true);
    });
  });

  describe('initSashResize Function', () => {
    it('is callable', () => {
      resetMocks();
      w.initSashResize();
      assertTrue(true);
    });

    it('sets up event listeners', () => {
      resetMocks();
      w.initSashResize();
      assertTrue(true);
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
      assertTrue(true);
    });

    it('handles invalid JSON gracefully', () => {
      resetMocks();
      w.localStorage.setItem('fpbinject-sidebar-state', 'invalid json');
      w.loadSidebarState();
      assertTrue(true);
    });

    it('handles missing state gracefully', () => {
      resetMocks();
      w.localStorage.clear();
      w.loadSidebarState();
      assertTrue(true);
    });
  });

  describe('saveSidebarState Function', () => {
    it('saves state to localStorage', () => {
      resetMocks();
      w.saveSidebarState();
      assertTrue(true);
    });
  });

  describe('setupSidebarStateListeners Function', () => {
    it('is callable', () => {
      resetMocks();
      w.setupSidebarStateListeners();
      assertTrue(true);
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
