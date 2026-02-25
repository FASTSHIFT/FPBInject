/*========================================
  FPBInject Workbench - Theme Module
  ========================================*/

/* ===========================
   THEME DEFINITIONS
   =========================== */
const darkTerminalTheme = {
  background: '#1e1e1e',
  foreground: '#cccccc',
  cursor: '#ffffff',
  cursorAccent: '#1e1e1e',
  selectionBackground: '#264f78',
  selectionForeground: '#ffffff',
};

const lightTerminalTheme = {
  background: '#f3f3f3',
  foreground: '#333333',
  cursor: '#333333',
  cursorAccent: '#f3f3f3',
  selectionBackground: '#add6ff',
  selectionForeground: '#000000',
};

/* ===========================
   THEME FUNCTIONS
   =========================== */
function setTheme(theme) {
  const html = document.documentElement;
  html.setAttribute('data-theme', theme);
  localStorage.setItem('fpbinject-theme', theme);
  updateTerminalTheme();
  updateAceEditorsTheme(theme === 'dark');
}

function toggleTheme() {
  const html = document.documentElement;
  const currentTheme = html.getAttribute('data-theme');
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  setTheme(newTheme);
}

function loadThemePreference() {
  const savedTheme = localStorage.getItem('fpbinject-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
}

function updateThemeIcon() {
  // Deprecated - theme icon removed from titlebar
}

function updateTerminalTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  const termTheme =
    currentTheme === 'light' ? lightTerminalTheme : darkTerminalTheme;

  const { toolTerminal, rawTerminal } = window.FPBState;
  if (toolTerminal) {
    toolTerminal.options.theme = termTheme;
  }
  if (rawTerminal) {
    rawTerminal.options.theme = termTheme;
  }
}

function getTerminalTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  return currentTheme === 'light' ? lightTerminalTheme : darkTerminalTheme;
}

// Update Ace Editor theme when global theme changes
function updateAceEditorsTheme(isDark) {
  const theme = isDark ? 'ace/theme/tomorrow_night' : 'ace/theme/tomorrow';
  const { aceEditors } = window.FPBState;
  aceEditors.forEach((editor) => {
    editor.setTheme(theme);
  });
}

// Export for global access
window.setTheme = setTheme;
window.toggleTheme = toggleTheme;
window.loadThemePreference = loadThemePreference;
window.updateThemeIcon = updateThemeIcon;
window.updateTerminalTheme = updateTerminalTheme;
window.getTerminalTheme = getTerminalTheme;
window.updateAceEditorsTheme = updateAceEditorsTheme;
window.darkTerminalTheme = darkTerminalTheme;
window.lightTerminalTheme = lightTerminalTheme;
