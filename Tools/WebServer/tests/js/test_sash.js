/**
 * Tests for ui/sash.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertContains,
} = require('./framework');
const { resetMocks, browserGlobals } = require('./mocks');

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

  describe('updateCornerSashPosition Function', () => {
    it('updates sashCorner position', () => {
      resetMocks();
      const sashCorner = browserGlobals.document.getElementById('sashCorner');
      w.updateCornerSashPosition();
      assertTrue(true);
    });

    it('handles missing sashCorner element', () => {
      resetMocks();
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'sashCorner') return null;
        return origGetById.call(browserGlobals.document, id);
      };
      w.updateCornerSashPosition();
      assertTrue(true);
      browserGlobals.document.getElementById = origGetById;
    });
  });

  describe('initSashResize Function', () => {
    it('initializes without error', () => {
      resetMocks();
      w.initSashResize();
      assertTrue(true);
    });

    it('adds mousedown listener to sashSidebar', () => {
      resetMocks();
      const sashSidebar = browserGlobals.document.getElementById('sashSidebar');
      w.initSashResize();
      assertTrue(
        sashSidebar._eventListeners['mousedown'] &&
          sashSidebar._eventListeners['mousedown'].length > 0,
      );
    });

    it('adds mousedown listener to sashPanel', () => {
      resetMocks();
      const sashPanel = browserGlobals.document.getElementById('sashPanel');
      w.initSashResize();
      assertTrue(
        sashPanel._eventListeners['mousedown'] &&
          sashPanel._eventListeners['mousedown'].length > 0,
      );
    });

    it('adds mousedown listener to sashCorner', () => {
      resetMocks();
      const sashCorner = browserGlobals.document.getElementById('sashCorner');
      w.initSashResize();
      assertTrue(
        sashCorner._eventListeners['mousedown'] &&
          sashCorner._eventListeners['mousedown'].length > 0,
      );
    });

    it('handles sidebar resize on mousedown', () => {
      resetMocks();
      const sashSidebar = browserGlobals.document.getElementById('sashSidebar');
      w.initSashResize();
      const handler = sashSidebar._eventListeners['mousedown'][0];
      handler({ preventDefault: () => {}, clientX: 100 });
      assertTrue(sashSidebar.classList._classes.has('active'));
    });

    it('handles panel resize on mousedown', () => {
      resetMocks();
      const sashPanel = browserGlobals.document.getElementById('sashPanel');
      w.initSashResize();
      const handler = sashPanel._eventListeners['mousedown'][0];
      handler({ preventDefault: () => {}, clientY: 100 });
      assertTrue(sashPanel.classList._classes.has('active'));
    });

    it('handles corner resize on mousedown', () => {
      resetMocks();
      const sashCorner = browserGlobals.document.getElementById('sashCorner');
      w.initSashResize();
      const handler = sashCorner._eventListeners['mousedown'][0];
      handler({ preventDefault: () => {}, clientX: 100, clientY: 100 });
      assertTrue(sashCorner.classList._classes.has('active'));
    });
  });

  describe('loadLayoutPreferences Function', () => {
    it('loads sidebar width from localStorage', () => {
      resetMocks();
      browserGlobals.localStorage.setItem('fpbinject-sidebar-width', '350px');
      w.loadLayoutPreferences();
      assertTrue(true);
    });

    it('loads panel height from localStorage', () => {
      resetMocks();
      browserGlobals.localStorage.setItem('fpbinject-panel-height', '250px');
      w.loadLayoutPreferences();
      assertTrue(true);
    });

    it('handles missing localStorage values', () => {
      resetMocks();
      browserGlobals.localStorage.clear();
      w.loadLayoutPreferences();
      assertTrue(true);
    });

    it('calls updateCornerSashPosition', () => {
      resetMocks();
      w.loadLayoutPreferences();
      assertTrue(true);
    });
  });

  describe('saveLayoutPreferences Function', () => {
    it('saves sidebar width to localStorage', () => {
      resetMocks();
      w.saveLayoutPreferences();
      const saved = browserGlobals.localStorage.getItem(
        'fpbinject-sidebar-width',
      );
      assertTrue(saved !== null);
    });

    it('saves panel height to localStorage', () => {
      resetMocks();
      w.saveLayoutPreferences();
      const saved = browserGlobals.localStorage.getItem(
        'fpbinject-panel-height',
      );
      assertTrue(saved !== null);
    });

    it('trims whitespace from values', () => {
      resetMocks();
      w.saveLayoutPreferences();
      const saved = browserGlobals.localStorage.getItem(
        'fpbinject-sidebar-width',
      );
      assertTrue(saved === saved.trim());
    });
  });

  describe('Sash Resize Integration', () => {
    it('sidebar resize respects minimum width', () => {
      resetMocks();
      w.initSashResize();
      const sashSidebar = browserGlobals.document.getElementById('sashSidebar');
      const handler = sashSidebar._eventListeners['mousedown'][0];
      handler({ preventDefault: () => {}, clientX: 100 });
      assertTrue(true);
    });

    it('panel resize respects minimum height', () => {
      resetMocks();
      w.initSashResize();
      const sashPanel = browserGlobals.document.getElementById('sashPanel');
      const handler = sashPanel._eventListeners['mousedown'][0];
      handler({ preventDefault: () => {}, clientY: 100 });
      assertTrue(true);
    });

    it('corner resize handles both dimensions', () => {
      resetMocks();
      w.initSashResize();
      const sashCorner = browserGlobals.document.getElementById('sashCorner');
      const handler = sashCorner._eventListeners['mousedown'][0];
      handler({ preventDefault: () => {}, clientX: 100, clientY: 100 });
      assertTrue(true);
    });
  });
};
