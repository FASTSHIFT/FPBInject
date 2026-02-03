/*========================================
  FPBInject Workbench - Sidebar State Module
  ========================================*/

/* ===========================
   SIDEBAR STATE PERSISTENCE
   =========================== */
const SIDEBAR_STATE_KEY = 'fpbinject-sidebar-state';

function loadSidebarState() {
  try {
    const savedState = localStorage.getItem(SIDEBAR_STATE_KEY);
    if (savedState) {
      const state = JSON.parse(savedState);
      for (const [id, isOpen] of Object.entries(state)) {
        const details = document.getElementById(id);
        if (details && details.tagName === 'DETAILS') {
          details.open = isOpen;
        }
      }
    }
  } catch (e) {
    console.warn('Failed to load sidebar state:', e);
  }
}

function saveSidebarState() {
  try {
    const state = {};
    document.querySelectorAll('details[id^="details-"]').forEach((details) => {
      state[details.id] = details.open;
    });
    localStorage.setItem(SIDEBAR_STATE_KEY, JSON.stringify(state));
  } catch (e) {
    console.warn('Failed to save sidebar state:', e);
  }
}

function setupSidebarStateListeners() {
  document.querySelectorAll('details[id^="details-"]').forEach((details) => {
    details.addEventListener('toggle', () => {
      saveSidebarState();
      syncActivityBarState();
    });
  });
}

function syncActivityBarState() {
  // Find the first open section and mark its activity item as active
  const openSection = document.querySelector('details[id^="details-"][open]');
  document.querySelectorAll('.activity-item[data-section]').forEach((item) => {
    if (openSection && item.dataset.section === openSection.id) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });
}

/* ===========================
   UI DISABLED STATE
   =========================== */
function updateDisabledState() {
  const state = window.FPBState;
  const disableWhenDisconnected = ['slotSelect', 'injectBtn'];
  const opacityElements = ['editorContainer', 'slotContainer'];

  disableWhenDisconnected.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.disabled = !state.isConnected;
      el.style.opacity = state.isConnected ? '1' : '0.5';
    }
  });

  opacityElements.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.style.opacity = state.isConnected ? '1' : '0.6';
      el.style.pointerEvents = state.isConnected ? 'auto' : 'none';
    }
  });

  const deviceInfoContent = document.getElementById('deviceInfoContent');
  if (deviceInfoContent) {
    deviceInfoContent.style.opacity = state.isConnected ? '1' : '0.5';
    deviceInfoContent.querySelectorAll('button').forEach((btn) => {
      btn.disabled = !state.isConnected;
    });
    deviceInfoContent.querySelectorAll('.slot-item').forEach((item) => {
      item.style.pointerEvents = state.isConnected ? 'auto' : 'none';
    });
  }

  document.querySelectorAll('#slotContainer .slot-btn').forEach((btn) => {
    btn.disabled = !state.isConnected;
  });
}

/* ===========================
   ACTIVITY BAR SECTION NAVIGATION
   =========================== */
function activateSection(sectionId) {
  // Close all details sections
  document.querySelectorAll('details[id^="details-"]').forEach((details) => {
    details.open = false;
  });

  // Open the target section
  const targetSection = document.getElementById(sectionId);
  if (targetSection) {
    targetSection.open = true;
    // Scroll section into view smoothly
    targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // Update activity bar active state
  document.querySelectorAll('.activity-item[data-section]').forEach((item) => {
    if (item.dataset.section === sectionId) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  // Save state
  saveSidebarState();
}

/* ===========================
   SIDEBAR SECTION HEIGHT RESIZE
   =========================== */
const SIDEBAR_SECTION_HEIGHTS_KEY = 'fpbinject-sidebar-section-heights';
let resizingSection = null;
let resizeStartY = 0;
let resizeStartHeight = 0;

function loadSidebarSectionHeights() {
  try {
    const savedHeights = localStorage.getItem(SIDEBAR_SECTION_HEIGHTS_KEY);
    if (savedHeights) {
      const heights = JSON.parse(savedHeights);
      for (const [sectionId, height] of Object.entries(heights)) {
        const section = document.querySelector(
          `.sidebar-section[data-section-id="${sectionId}"] .sidebar-content`,
        );
        if (section) {
          section.style.height = height;
        }
      }
    }
  } catch (e) {
    console.warn('Failed to load sidebar section heights:', e);
  }
}

function saveSidebarSectionHeight(sectionId, height) {
  try {
    const savedHeights = localStorage.getItem(SIDEBAR_SECTION_HEIGHTS_KEY);
    const heights = savedHeights ? JSON.parse(savedHeights) : {};
    heights[sectionId] = height;
    localStorage.setItem(SIDEBAR_SECTION_HEIGHTS_KEY, JSON.stringify(heights));
  } catch (e) {
    console.warn('Failed to save sidebar section height:', e);
  }
}

function setupSidebarSectionResize() {
  const handles = document.querySelectorAll('.sidebar-section-resize-handle');

  handles.forEach((handle) => {
    const section = handle.closest('.sidebar-section');
    if (!section) return;

    const sectionId = section.dataset.sectionId;
    const content = section.querySelector('.sidebar-content');
    if (!content) return;

    handle.addEventListener('mousedown', (e) => {
      resizingSection = { section, content, sectionId };
      resizeStartY = e.clientY;
      resizeStartHeight = content.offsetHeight;
      handle.classList.add('resizing');
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });
  });

  document.addEventListener('mousemove', (e) => {
    if (!resizingSection) return;

    const deltaY = e.clientY - resizeStartY;
    const newHeight = resizeStartHeight + deltaY;
    const minHeight = 100;
    const maxHeight = window.innerHeight * 0.6;

    if (newHeight >= minHeight && newHeight <= maxHeight) {
      resizingSection.content.style.height = `${newHeight}px`;
    }
  });

  document.addEventListener('mouseup', () => {
    if (resizingSection) {
      const handle = resizingSection.section.querySelector(
        '.sidebar-section-resize-handle',
      );
      if (handle) {
        handle.classList.remove('resizing');
      }
      document.body.style.cursor = '';
      document.body.style.userSelect = '';

      // Save the new height
      if (resizingSection.content.style.height) {
        saveSidebarSectionHeight(
          resizingSection.sectionId,
          resizingSection.content.style.height,
        );
      }

      resizingSection = null;
    }
  });
}

// Export for global access
window.loadSidebarState = loadSidebarState;
window.saveSidebarState = saveSidebarState;
window.setupSidebarStateListeners = setupSidebarStateListeners;
window.updateDisabledState = updateDisabledState;
window.activateSection = activateSection;
window.syncActivityBarState = syncActivityBarState;
window.loadSidebarSectionHeights = loadSidebarSectionHeights;
window.saveSidebarSectionHeight = saveSidebarSectionHeight;
window.setupSidebarSectionResize = setupSidebarSectionResize;
