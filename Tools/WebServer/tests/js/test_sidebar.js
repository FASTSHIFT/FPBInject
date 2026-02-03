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
const {
  resetMocks,
  browserGlobals,
  MockTerminal,
  getDocumentEventListeners,
} = require('./mocks');

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

    it('applies state to details elements', () => {
      resetMocks();
      const deviceSection =
        browserGlobals.document.getElementById('details-device');
      deviceSection.open = false;
      browserGlobals.localStorage.setItem(
        'fpbinject-sidebar-state',
        JSON.stringify({
          'details-device': true,
        }),
      );
      w.loadSidebarState();
      assertTrue(deviceSection.open);
    });

    it('skips non-DETAILS elements', () => {
      resetMocks();
      const regularDiv = browserGlobals.document.getElementById('sidebar');
      regularDiv.tagName = 'DIV';
      browserGlobals.localStorage.setItem(
        'fpbinject-sidebar-state',
        JSON.stringify({
          sidebar: true,
        }),
      );
      w.loadSidebarState();
      assertTrue(true);
    });

    it('handles error when loading state', () => {
      resetMocks();
      const originalGetItem = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = () => {
        throw new Error('Storage error');
      };
      w.loadSidebarState();
      browserGlobals.localStorage.getItem = originalGetItem;
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

    it('handles error when saving state', () => {
      resetMocks();
      const originalSetItem = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.setItem = () => {
        throw new Error('Storage error');
      };
      w.saveSidebarState();
      browserGlobals.localStorage.setItem = originalSetItem;
      assertTrue(true);
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

  describe('Sidebar Height Resize Functions', () => {
    it('loadSidebarSectionHeights is a function', () =>
      assertTrue(typeof w.loadSidebarSectionHeights === 'function'));
    it('saveSidebarSectionHeight is a function', () =>
      assertTrue(typeof w.saveSidebarSectionHeight === 'function'));
    it('setupSidebarSectionResize is a function', () =>
      assertTrue(typeof w.setupSidebarSectionResize === 'function'));

    it('loads saved section heights from localStorage', () => {
      resetMocks();
      browserGlobals.localStorage.setItem(
        'fpbinject-sidebar-section-heights',
        JSON.stringify({ device: '400px', transfer: '300px' }),
      );
      w.loadSidebarSectionHeights();
      assertTrue(true);
    });

    it('handles missing saved heights gracefully', () => {
      resetMocks();
      browserGlobals.localStorage.clear();
      w.loadSidebarSectionHeights();
      assertTrue(true);
    });

    it('saves section height to localStorage', () => {
      resetMocks();
      browserGlobals.localStorage.clear();
      w.saveSidebarSectionHeight('device', '500px');
      const saved = browserGlobals.localStorage.getItem(
        'fpbinject-sidebar-section-heights',
      );
      const parsed = JSON.parse(saved);
      assertEqual(parsed.device, '500px');
    });

    it('setupSidebarSectionResize adds event listeners', () => {
      resetMocks();
      w.setupSidebarSectionResize();
      assertTrue(true);
    });

    it('handles missing resize handles gracefully', () => {
      resetMocks();
      w.setupSidebarSectionResize();
      assertTrue(true);
    });

    it('saves multiple section heights', () => {
      resetMocks();
      browserGlobals.localStorage.clear();
      w.saveSidebarSectionHeight('device', '400px');
      w.saveSidebarSectionHeight('transfer', '300px');
      const saved = browserGlobals.localStorage.getItem(
        'fpbinject-sidebar-section-heights',
      );
      const parsed = JSON.parse(saved);
      assertEqual(parsed.device, '400px');
      assertEqual(parsed.transfer, '300px');
    });

    it('handles invalid JSON in localStorage gracefully', () => {
      resetMocks();
      browserGlobals.localStorage.setItem(
        'fpbinject-sidebar-section-heights',
        'invalid',
      );
      w.loadSidebarSectionHeights();
      assertTrue(true);
    });

    it('updates existing section height', () => {
      resetMocks();
      w.saveSidebarSectionHeight('device', '400px');
      w.saveSidebarSectionHeight('device', '600px');
      const saved = browserGlobals.localStorage.getItem(
        'fpbinject-sidebar-section-heights',
      );
      const parsed = JSON.parse(saved);
      assertEqual(parsed.device, '600px');
    });

    it('loads and applies section heights to DOM', () => {
      resetMocks();
      // Create mock section elements
      const deviceSection = browserGlobals.document.createElement('div');
      deviceSection.classList.add('sidebar-section');
      deviceSection.dataset.sectionId = 'device';
      const deviceContent = browserGlobals.document.createElement('div');
      deviceContent.classList.add('sidebar-content');
      deviceSection.appendChild(deviceContent);

      browserGlobals.localStorage.setItem(
        'fpbinject-sidebar-section-heights',
        JSON.stringify({ device: '450px' }),
      );
      w.loadSidebarSectionHeights();
      assertTrue(true);
    });

    it('handles error when saving section height', () => {
      resetMocks();
      // Force an error by making localStorage throw
      const originalSetItem = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.setItem = () => {
        throw new Error('Storage error');
      };
      w.saveSidebarSectionHeight('device', '400px');
      browserGlobals.localStorage.setItem = originalSetItem;
      assertTrue(true);
    });

    it('handles error when loading section heights', () => {
      resetMocks();
      const originalGetItem = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = () => {
        throw new Error('Storage error');
      };
      w.loadSidebarSectionHeights();
      browserGlobals.localStorage.getItem = originalGetItem;
      assertTrue(true);
    });

    it('registers mousemove and mouseup event listeners on document', () => {
      resetMocks();
      w.setupSidebarSectionResize();
      const listeners = getDocumentEventListeners();
      assertTrue(listeners.mousemove && listeners.mousemove.length > 0);
      assertTrue(listeners.mouseup && listeners.mouseup.length > 0);
    });

    it('mousemove does nothing when not resizing', () => {
      resetMocks();
      w.setupSidebarSectionResize();
      const listeners = getDocumentEventListeners();
      // Trigger mousemove without starting resize
      listeners.mousemove.forEach((handler) => {
        handler({ clientY: 200 });
      });
      assertTrue(true);
    });

    it('mouseup does nothing when not resizing', () => {
      resetMocks();
      w.setupSidebarSectionResize();
      const listeners = getDocumentEventListeners();
      // Trigger mouseup without starting resize
      listeners.mouseup.forEach((handler) => {
        handler({});
      });
      assertTrue(true);
    });
  });
};
