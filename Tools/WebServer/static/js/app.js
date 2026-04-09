/*========================================
  FPBInject Workbench - Main Application Entry Point
  
  This file serves as the main entry point that initializes
  all modules. The actual functionality is split into:
  
  Core Modules:
  - core/state.js      - Global state management
  - core/theme.js      - Theme toggle functionality
  - core/terminal.js   - Terminal management
  - core/connection.js - Connection management
  - core/logs.js       - Log polling
  - core/slots.js      - Slot management
  
  UI Modules:
  - ui/sash.js         - Sash resize functionality
  - ui/sidebar.js      - Sidebar state persistence
  
  Feature Modules:
  - features/fpb.js        - FPB commands
  - features/patch.js      - Patch operations
  - features/symbols.js    - Symbol search
  - features/editor.js     - Editor/tab management
  - features/config.js     - Configuration
  - features/autoinject.js - Auto-inject polling
  - features/filebrowser.js - File browser
  ========================================*/

/* ===========================
   INITIALIZATION
   =========================== */
document.addEventListener('DOMContentLoaded', () => {
  loadThemePreference();
  initTerminals();
  refreshPorts();
  loadConfig();
  initSashResize();
  loadLayoutPreferences();
  loadSidebarState();
  updateSlotUI();
  initSlotSelectListener();
  updateDisabledState();
  setupAutoSave();
  setupSidebarStateListeners();
  startBackendHealthCheck();
  // Restore watch expressions from localStorage (without auto-refresh)
  if (typeof watchRestoreFromStorage === 'function') {
    watchRestoreFromStorage();
  }
});

/* Global Ctrl+S handler for text file tabs */
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    const state = window.FPBState;
    if (!state) return;
    const activeTab = state.editorTabs.find(
      (tab) => tab.id === state.activeEditorTab,
    );
    if (activeTab && activeTab.type === 'textfile') {
      e.preventDefault();
      saveDeviceTextFile(activeTab.id);
    }
  }
});
