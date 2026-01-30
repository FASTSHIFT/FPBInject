/*========================================
  FPBInject Workbench - Sash Resize Module
  ========================================*/

/* ===========================
   SASH RESIZE FUNCTIONALITY
   =========================== */
function updateCornerSashPosition() {
  const sashCorner = document.getElementById('sashCorner');
  const sidebar = document.getElementById('sidebar');
  const panelContainer = document.getElementById('panelContainer');

  if (sashCorner && sidebar && panelContainer) {
    const sidebarRect = sidebar.getBoundingClientRect();
    const panelRect = panelContainer.getBoundingClientRect();
    sashCorner.style.left = sidebarRect.right - 2 + 'px';
    sashCorner.style.top = panelRect.top - 2 + 'px';
  }
}

function initSashResize() {
  const sashSidebar = document.getElementById('sashSidebar');
  const sashPanel = document.getElementById('sashPanel');
  const sidebar = document.getElementById('sidebar');
  const panelContainer = document.getElementById('panelContainer');

  let isResizingSidebar = false;
  let isResizingPanel = false;
  let startX = 0;
  let startY = 0;
  let startWidth = 0;
  let startHeight = 0;

  // Sidebar resize
  if (sashSidebar) {
    sashSidebar.addEventListener('mousedown', (e) => {
      e.preventDefault();
      isResizingSidebar = true;
      startX = e.clientX;
      startWidth = sidebar.offsetWidth;
      document.body.classList.add('resizing-sidebar');
      sashSidebar.classList.add('active');
    });
  }

  // Panel resize
  if (sashPanel) {
    sashPanel.addEventListener('mousedown', (e) => {
      e.preventDefault();
      isResizingPanel = true;
      startY = e.clientY;
      startHeight = panelContainer.offsetHeight;
      document.body.classList.add('resizing-panel');
      sashPanel.classList.add('active');
    });
  }

  // Corner resize
  const sashCorner = document.getElementById('sashCorner');
  let isResizingCorner = false;

  if (sashCorner) {
    sashCorner.addEventListener('mousedown', (e) => {
      e.preventDefault();
      isResizingCorner = true;
      startX = e.clientX;
      startY = e.clientY;
      startWidth = sidebar.offsetWidth;
      startHeight = panelContainer.offsetHeight;
      document.body.classList.add('resizing-sidebar');
      document.body.classList.add('resizing-panel');
      sashCorner.classList.add('active');
    });
  }

  document.addEventListener('mousemove', (e) => {
    if (isResizingSidebar) {
      const delta = e.clientX - startX;
      const newWidth = startWidth + delta;
      if (newWidth >= 150) {
        document.documentElement.style.setProperty(
          '--sidebar-width',
          newWidth + 'px',
        );
      }
    }

    if (isResizingPanel) {
      const delta = startY - e.clientY;
      const newHeight = startHeight + delta;
      if (newHeight >= 80) {
        document.documentElement.style.setProperty(
          '--panel-height',
          newHeight + 'px',
        );
      }
    }

    if (isResizingCorner) {
      const deltaX = e.clientX - startX;
      const deltaY = startY - e.clientY;
      const newWidth = startWidth + deltaX;
      const newHeight = startHeight + deltaY;

      if (newWidth >= 150) {
        document.documentElement.style.setProperty(
          '--sidebar-width',
          newWidth + 'px',
        );
      }
      if (newHeight >= 80) {
        document.documentElement.style.setProperty(
          '--panel-height',
          newHeight + 'px',
        );
      }
    }

    if (isResizingSidebar || isResizingPanel || isResizingCorner) {
      updateCornerSashPosition();
    }
  });

  document.addEventListener('mouseup', () => {
    if (isResizingSidebar) {
      isResizingSidebar = false;
      document.body.classList.remove('resizing-sidebar');
      sashSidebar.classList.remove('active');
      saveLayoutPreferences();
      fitTerminals();
    }

    if (isResizingPanel) {
      isResizingPanel = false;
      document.body.classList.remove('resizing-panel');
      sashPanel.classList.remove('active');
      saveLayoutPreferences();
      fitTerminals();
    }

    if (isResizingCorner) {
      isResizingCorner = false;
      document.body.classList.remove('resizing-sidebar');
      document.body.classList.remove('resizing-panel');
      sashCorner.classList.remove('active');
      saveLayoutPreferences();
      fitTerminals();
    }
  });

  updateCornerSashPosition();
  window.addEventListener('resize', updateCornerSashPosition);
}

function loadLayoutPreferences() {
  const sidebarWidth = localStorage.getItem('fpbinject-sidebar-width');
  const panelHeight = localStorage.getItem('fpbinject-panel-height');

  if (sidebarWidth) {
    document.documentElement.style.setProperty('--sidebar-width', sidebarWidth);
  }
  if (panelHeight) {
    document.documentElement.style.setProperty('--panel-height', panelHeight);
  }

  requestAnimationFrame(updateCornerSashPosition);
}

function saveLayoutPreferences() {
  const sidebarWidth = getComputedStyle(
    document.documentElement,
  ).getPropertyValue('--sidebar-width');
  const panelHeight = getComputedStyle(
    document.documentElement,
  ).getPropertyValue('--panel-height');

  localStorage.setItem('fpbinject-sidebar-width', sidebarWidth.trim());
  localStorage.setItem('fpbinject-panel-height', panelHeight.trim());
}

// Export for global access
window.initSashResize = initSashResize;
window.loadLayoutPreferences = loadLayoutPreferences;
window.saveLayoutPreferences = saveLayoutPreferences;
window.updateCornerSashPosition = updateCornerSashPosition;
