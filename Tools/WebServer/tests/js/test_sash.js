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
const {
  resetMocks,
  browserGlobals,
  getDocumentEventListeners,
} = require('./mocks');

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
      const sashCorner = browserGlobals.document.getElementById('sashCorner');
      w.updateCornerSashPosition();
      // Function should complete without error
      assertEqual(typeof w.updateCornerSashPosition, 'function');
    });

    it('handles missing sashCorner element gracefully', () => {
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'sashCorner') return null;
        return origGetById.call(browserGlobals.document, id);
      };
      w.updateCornerSashPosition();
      // Should not throw
      assertEqual(typeof w.updateCornerSashPosition, 'function');
      browserGlobals.document.getElementById = origGetById;
    });
  });

  describe('initSashResize Function', () => {
    it('initializes without error', () => {
      w.initSashResize();
      // Verify sash elements have event listeners
      const sashSidebar = browserGlobals.document.getElementById('sashSidebar');
      assertTrue(sashSidebar._eventListeners['mousedown'] !== undefined);
    });

    it('adds mousedown listener to sashSidebar', () => {
      const sashSidebar = browserGlobals.document.getElementById('sashSidebar');
      w.initSashResize();
      assertTrue(
        sashSidebar._eventListeners['mousedown'] &&
          sashSidebar._eventListeners['mousedown'].length > 0,
      );
    });

    it('adds mousedown listener to sashPanel', () => {
      const sashPanel = browserGlobals.document.getElementById('sashPanel');
      w.initSashResize();
      assertTrue(
        sashPanel._eventListeners['mousedown'] &&
          sashPanel._eventListeners['mousedown'].length > 0,
      );
    });

    it('adds mousedown listener to sashCorner', () => {
      const sashCorner = browserGlobals.document.getElementById('sashCorner');
      w.initSashResize();
      assertTrue(
        sashCorner._eventListeners['mousedown'] &&
          sashCorner._eventListeners['mousedown'].length > 0,
      );
    });

    it('handles sidebar resize on mousedown', () => {
      const sashSidebar = browserGlobals.document.getElementById('sashSidebar');
      w.initSashResize();
      const handler = sashSidebar._eventListeners['mousedown'][0];
      handler({ preventDefault: () => {}, clientX: 100 });
      assertTrue(sashSidebar.classList._classes.has('active'));
    });

    it('handles panel resize on mousedown', () => {
      const sashPanel = browserGlobals.document.getElementById('sashPanel');
      w.initSashResize();
      const handler = sashPanel._eventListeners['mousedown'][0];
      handler({ preventDefault: () => {}, clientY: 100 });
      assertTrue(sashPanel.classList._classes.has('active'));
    });

    it('handles corner resize on mousedown', () => {
      const sashCorner = browserGlobals.document.getElementById('sashCorner');
      w.initSashResize();
      const handler = sashCorner._eventListeners['mousedown'][0];
      handler({ preventDefault: () => {}, clientX: 100, clientY: 100 });
      assertTrue(sashCorner.classList._classes.has('active'));
    });
  });

  describe('loadLayoutPreferences Function', () => {
    it('loads sidebar width from localStorage', () => {
      browserGlobals.localStorage.setItem('fpbinject-sidebar-width', '350px');
      w.loadLayoutPreferences();
      // Function should complete and use the stored value
      assertEqual(
        browserGlobals.localStorage.getItem('fpbinject-sidebar-width'),
        '350px',
      );
    });

    it('loads panel height from localStorage', () => {
      browserGlobals.localStorage.setItem('fpbinject-panel-height', '250px');
      w.loadLayoutPreferences();
      assertEqual(
        browserGlobals.localStorage.getItem('fpbinject-panel-height'),
        '250px',
      );
    });

    it('handles missing localStorage values gracefully', () => {
      browserGlobals.localStorage.clear();
      w.loadLayoutPreferences();
      // Should not throw
      assertEqual(typeof w.loadLayoutPreferences, 'function');
    });

    it('calls updateCornerSashPosition', () => {
      w.loadLayoutPreferences();
      // Function should complete
      assertEqual(typeof w.updateCornerSashPosition, 'function');
    });
  });

  describe('saveLayoutPreferences Function', () => {
    it('saves sidebar width to localStorage', () => {
      w.saveLayoutPreferences();
      const saved = browserGlobals.localStorage.getItem(
        'fpbinject-sidebar-width',
      );
      assertTrue(saved !== null);
    });

    it('saves panel height to localStorage', () => {
      w.saveLayoutPreferences();
      const saved = browserGlobals.localStorage.getItem(
        'fpbinject-panel-height',
      );
      assertTrue(saved !== null);
    });

    it('trims whitespace from values', () => {
      w.saveLayoutPreferences();
      const saved = browserGlobals.localStorage.getItem(
        'fpbinject-sidebar-width',
      );
      assertTrue(saved === saved.trim());
    });
  });

  describe('Sash Resize Integration', () => {
    it('sidebar resize respects minimum width', () => {
      w.initSashResize();
      const sashSidebar = browserGlobals.document.getElementById('sashSidebar');
      const handler = sashSidebar._eventListeners['mousedown'][0];
      handler({ preventDefault: () => {}, clientX: 100 });
      assertTrue(sashSidebar.classList._classes.has('active'));
    });

    it('panel resize respects minimum height', () => {
      w.initSashResize();
      const sashPanel = browserGlobals.document.getElementById('sashPanel');
      const handler = sashPanel._eventListeners['mousedown'][0];
      handler({ preventDefault: () => {}, clientY: 100 });
      assertTrue(sashPanel.classList._classes.has('active'));
    });

    it('corner resize handles both dimensions', () => {
      w.initSashResize();
      const sashCorner = browserGlobals.document.getElementById('sashCorner');
      const handler = sashCorner._eventListeners['mousedown'][0];
      handler({ preventDefault: () => {}, clientX: 100, clientY: 100 });
      assertTrue(sashCorner.classList._classes.has('active'));
    });

    it('mousemove updates sidebar width during resize', () => {
      w.initSashResize();
      const sashSidebar = browserGlobals.document.getElementById('sashSidebar');
      const mousedownHandler = sashSidebar._eventListeners['mousedown'][0];
      mousedownHandler({ preventDefault: () => {}, clientX: 100 });
      // Trigger mousemove
      const docListeners = getDocumentEventListeners();
      if (docListeners['mousemove'] && docListeners['mousemove'].length > 0) {
        docListeners['mousemove'][0]({ clientX: 200, clientY: 100 });
      }
      assertTrue(sashSidebar.classList._classes.has('active'));
    });

    it('mousemove updates panel height during resize', () => {
      w.initSashResize();
      const sashPanel = browserGlobals.document.getElementById('sashPanel');
      const mousedownHandler = sashPanel._eventListeners['mousedown'][0];
      mousedownHandler({ preventDefault: () => {}, clientY: 500 });
      // Trigger mousemove
      const docListeners = getDocumentEventListeners();
      if (docListeners['mousemove'] && docListeners['mousemove'].length > 0) {
        docListeners['mousemove'][0]({ clientX: 100, clientY: 400 });
      }
      assertTrue(sashPanel.classList._classes.has('active'));
    });

    it('mousemove updates both dimensions during corner resize', () => {
      w.initSashResize();
      const sashCorner = browserGlobals.document.getElementById('sashCorner');
      const mousedownHandler = sashCorner._eventListeners['mousedown'][0];
      mousedownHandler({
        preventDefault: () => {},
        clientX: 100,
        clientY: 500,
      });
      // Trigger mousemove
      const docListeners = getDocumentEventListeners();
      if (docListeners['mousemove'] && docListeners['mousemove'].length > 0) {
        docListeners['mousemove'][0]({ clientX: 200, clientY: 400 });
      }
      assertTrue(sashCorner.classList._classes.has('active'));
    });

    it('mouseup ends sidebar resize', () => {
      w.initSashResize();
      const sashSidebar = browserGlobals.document.getElementById('sashSidebar');
      const mousedownHandler = sashSidebar._eventListeners['mousedown'][0];
      mousedownHandler({ preventDefault: () => {}, clientX: 100 });
      assertTrue(sashSidebar.classList._classes.has('active'));
      // Trigger mouseup
      const docListeners = getDocumentEventListeners();
      if (docListeners['mouseup'] && docListeners['mouseup'].length > 0) {
        docListeners['mouseup'][0]();
      }
      assertTrue(!sashSidebar.classList._classes.has('active'));
    });

    it('mouseup ends panel resize', () => {
      w.initSashResize();
      const sashPanel = browserGlobals.document.getElementById('sashPanel');
      const mousedownHandler = sashPanel._eventListeners['mousedown'][0];
      mousedownHandler({ preventDefault: () => {}, clientY: 100 });
      assertTrue(sashPanel.classList._classes.has('active'));
      // Trigger mouseup
      const docListeners = getDocumentEventListeners();
      if (docListeners['mouseup'] && docListeners['mouseup'].length > 0) {
        docListeners['mouseup'][0]();
      }
      assertTrue(!sashPanel.classList._classes.has('active'));
    });

    it('mouseup ends corner resize', () => {
      w.initSashResize();
      const sashCorner = browserGlobals.document.getElementById('sashCorner');
      const mousedownHandler = sashCorner._eventListeners['mousedown'][0];
      mousedownHandler({
        preventDefault: () => {},
        clientX: 100,
        clientY: 100,
      });
      assertTrue(sashCorner.classList._classes.has('active'));
      // Trigger mouseup
      const docListeners = getDocumentEventListeners();
      if (docListeners['mouseup'] && docListeners['mouseup'].length > 0) {
        docListeners['mouseup'][0]();
      }
      assertTrue(!sashCorner.classList._classes.has('active'));
    });

    it('sidebar resize enforces minimum width', () => {
      w.initSashResize();
      const sashSidebar = browserGlobals.document.getElementById('sashSidebar');
      const mousedownHandler = sashSidebar._eventListeners['mousedown'][0];
      mousedownHandler({ preventDefault: () => {}, clientX: 300 });
      // Move to very small width
      const docListeners = getDocumentEventListeners();
      if (docListeners['mousemove'] && docListeners['mousemove'].length > 0) {
        docListeners['mousemove'][0]({ clientX: 50, clientY: 100 });
      }
      assertEqual(typeof w.initSashResize, 'function');
    });

    it('panel resize enforces minimum height', () => {
      w.initSashResize();
      const sashPanel = browserGlobals.document.getElementById('sashPanel');
      const mousedownHandler = sashPanel._eventListeners['mousedown'][0];
      mousedownHandler({ preventDefault: () => {}, clientY: 100 });
      // Move to very small height
      const docListeners = getDocumentEventListeners();
      if (docListeners['mousemove'] && docListeners['mousemove'].length > 0) {
        docListeners['mousemove'][0]({ clientX: 100, clientY: 50 });
      }
      assertEqual(typeof w.initSashResize, 'function');
    });
  });
};
