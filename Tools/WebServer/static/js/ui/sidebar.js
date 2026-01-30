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
    details.addEventListener('toggle', saveSidebarState);
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

// Export for global access
window.loadSidebarState = loadSidebarState;
window.saveSidebarState = saveSidebarState;
window.setupSidebarStateListeners = setupSidebarStateListeners;
window.updateDisabledState = updateDisabledState;
