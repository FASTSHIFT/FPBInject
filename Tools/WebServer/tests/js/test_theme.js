/**
 * Tests for core/theme.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertContains,
} = require('./framework');
const { mockLocalStorage, browserGlobals, resetMocks } = require('./mocks');

module.exports = function (w) {
  describe('Theme Functions (core/theme.js)', () => {
    it('darkTerminalTheme is defined', () => {
      assertTrue(w.darkTerminalTheme !== undefined);
      assertEqual(w.darkTerminalTheme.background, '#1e1e1e');
      assertEqual(w.darkTerminalTheme.foreground, '#cccccc');
    });
    it('lightTerminalTheme is defined', () => {
      assertTrue(w.lightTerminalTheme !== undefined);
      assertEqual(w.lightTerminalTheme.background, '#f3f3f3');
      assertEqual(w.lightTerminalTheme.foreground, '#333333');
    });
    it('darkTerminalTheme has cursor color', () => {
      assertEqual(w.darkTerminalTheme.cursor, '#ffffff');
    });
    it('lightTerminalTheme has cursor color', () => {
      assertEqual(w.lightTerminalTheme.cursor, '#333333');
    });
    it('darkTerminalTheme has selection color', () => {
      assertEqual(w.darkTerminalTheme.selectionBackground, '#264f78');
    });
    it('lightTerminalTheme has selection color', () => {
      assertEqual(w.lightTerminalTheme.selectionBackground, '#add6ff');
    });
    it('getTerminalTheme returns dark theme by default', () => {
      browserGlobals.document.documentElement._theme = 'dark';
      const theme = w.getTerminalTheme();
      assertEqual(theme.background, '#1e1e1e');
    });
    it('getTerminalTheme returns light theme when set', () => {
      browserGlobals.document.documentElement._theme = 'light';
      const theme = w.getTerminalTheme();
      assertEqual(theme.background, '#f3f3f3');
      browserGlobals.document.documentElement._theme = 'dark';
    });
    it('toggleTheme is a function', () =>
      assertTrue(typeof w.toggleTheme === 'function'));
    it('toggleTheme switches from dark to light', () => {
      resetMocks();
      browserGlobals.document.documentElement._theme = 'dark';
      w.toggleTheme();
      assertEqual(browserGlobals.document.documentElement._theme, 'light');
      assertEqual(mockLocalStorage.getItem('fpbinject-theme'), 'light');
    });
    it('toggleTheme switches from light to dark', () => {
      browserGlobals.document.documentElement._theme = 'light';
      w.toggleTheme();
      assertEqual(browserGlobals.document.documentElement._theme, 'dark');
    });
    it('toggleTheme saves preference to localStorage', () => {
      resetMocks();
      browserGlobals.document.documentElement._theme = 'dark';
      w.toggleTheme();
      assertEqual(mockLocalStorage.getItem('fpbinject-theme'), 'light');
    });
    it('loadThemePreference is a function', () =>
      assertTrue(typeof w.loadThemePreference === 'function'));
    it('loadThemePreference loads saved theme', () => {
      mockLocalStorage.setItem('fpbinject-theme', 'light');
      w.loadThemePreference();
      assertEqual(browserGlobals.document.documentElement._theme, 'light');
      browserGlobals.document.documentElement._theme = 'dark';
    });
    it('loadThemePreference defaults to dark', () => {
      mockLocalStorage.clear();
      w.loadThemePreference();
      assertEqual(browserGlobals.document.documentElement._theme, 'dark');
    });
    it('updateAceEditorsTheme is a function', () =>
      assertTrue(typeof w.updateAceEditorsTheme === 'function'));
    it('updateAceEditorsTheme updates all editors to dark', () => {
      const mockEditor = {
        setTheme: function (t) {
          this._theme = t;
        },
      };
      w.FPBState.aceEditors.set('test', mockEditor);
      w.updateAceEditorsTheme(true);
      assertEqual(mockEditor._theme, 'ace/theme/tomorrow_night');
      w.FPBState.aceEditors.clear();
    });
    it('updateAceEditorsTheme updates all editors to light', () => {
      const mockEditor = {
        setTheme: function (t) {
          this._theme = t;
        },
      };
      w.FPBState.aceEditors.set('test', mockEditor);
      w.updateAceEditorsTheme(false);
      assertEqual(mockEditor._theme, 'ace/theme/tomorrow');
      w.FPBState.aceEditors.clear();
    });
    it('updateAceEditorsTheme handles multiple editors', () => {
      const editor1 = {
        setTheme: function (t) {
          this._theme = t;
        },
      };
      const editor2 = {
        setTheme: function (t) {
          this._theme = t;
        },
      };
      w.FPBState.aceEditors.set('ed1', editor1);
      w.FPBState.aceEditors.set('ed2', editor2);
      w.updateAceEditorsTheme(true);
      assertEqual(editor1._theme, 'ace/theme/tomorrow_night');
      assertEqual(editor2._theme, 'ace/theme/tomorrow_night');
      w.FPBState.aceEditors.clear();
    });
    it('updateAceEditorsTheme handles empty editors map', () => {
      w.FPBState.aceEditors.clear();
      w.updateAceEditorsTheme(true);
      assertEqual(w.FPBState.aceEditors.size, 0);
    });
    it('updateThemeIcon is a function', () =>
      assertTrue(typeof w.updateThemeIcon === 'function'));
    it('updateTerminalTheme is a function', () =>
      assertTrue(typeof w.updateTerminalTheme === 'function'));
    it('updateTerminalTheme updates tool terminal', () => {
      const mockTerm = { options: {} };
      w.FPBState.toolTerminal = mockTerm;
      browserGlobals.document.documentElement._theme = 'dark';
      w.updateTerminalTheme();
      assertEqual(mockTerm.options.theme.background, '#1e1e1e');
      w.FPBState.toolTerminal = null;
    });
    it('updateTerminalTheme updates raw terminal', () => {
      const mockTerm = { options: {} };
      w.FPBState.rawTerminal = mockTerm;
      browserGlobals.document.documentElement._theme = 'light';
      w.updateTerminalTheme();
      assertEqual(mockTerm.options.theme.background, '#f3f3f3');
      w.FPBState.rawTerminal = null;
      browserGlobals.document.documentElement._theme = 'dark';
    });
    it('updateTerminalTheme handles null terminals gracefully', () => {
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
      w.updateTerminalTheme();
      assertEqual(w.FPBState.toolTerminal, null);
      assertEqual(w.FPBState.rawTerminal, null);
    });
  });
};
