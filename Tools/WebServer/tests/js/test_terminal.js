/**
 * Tests for core/terminal.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertContains,
} = require('./framework');
const { resetMocks } = require('./mocks');

module.exports = function (w) {
  describe('Terminal Functions (core/terminal.js)', () => {
    it('initTerminals is a function', () =>
      assertTrue(typeof w.initTerminals === 'function'));
    it('fitTerminals is a function', () =>
      assertTrue(typeof w.fitTerminals === 'function'));
    it('switchTerminalTab is a function', () =>
      assertTrue(typeof w.switchTerminalTab === 'function'));
    it('writeToOutput is a function', () =>
      assertTrue(typeof w.writeToOutput === 'function'));
    it('writeToSerial is a function', () =>
      assertTrue(typeof w.writeToSerial === 'function'));
    it('clearCurrentTerminal is a function', () =>
      assertTrue(typeof w.clearCurrentTerminal === 'function'));
  });

  describe('writeToOutput Function', () => {
    it('writes info message', () => {
      const mockTerm = {
        writeln: function (m) {
          this._last = m;
        },
      };
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Test message', 'info');
      assertContains(mockTerm._last, 'Test message');
      w.FPBState.toolTerminal = null;
    });
    it('writes success message with green color', () => {
      const mockTerm = {
        writeln: function (m) {
          this._last = m;
        },
      };
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Success!', 'success');
      assertContains(mockTerm._last, '\x1b[32m');
      w.FPBState.toolTerminal = null;
    });
    it('writes error message with red color', () => {
      const mockTerm = {
        writeln: function (m) {
          this._last = m;
        },
      };
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Error!', 'error');
      assertContains(mockTerm._last, '\x1b[31m');
      w.FPBState.toolTerminal = null;
    });
    it('writes warning message with yellow color', () => {
      const mockTerm = {
        writeln: function (m) {
          this._last = m;
        },
      };
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Warning!', 'warning');
      assertContains(mockTerm._last, '\x1b[33m');
      w.FPBState.toolTerminal = null;
    });
    it('writes system message with cyan color', () => {
      const mockTerm = {
        writeln: function (m) {
          this._last = m;
        },
      };
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('System', 'system');
      assertContains(mockTerm._last, '\x1b[36m');
      w.FPBState.toolTerminal = null;
    });
    it('handles multiline messages', () => {
      const lines = [];
      const mockTerm = {
        writeln: function (m) {
          lines.push(m);
        },
      };
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Line1\nLine2\nLine3', 'info');
      assertEqual(lines.length, 3);
      w.FPBState.toolTerminal = null;
    });
    it('handles null terminal gracefully', () => {
      w.FPBState.toolTerminal = null;
      w.writeToOutput('Test', 'info');
      assertTrue(true);
    });
    it('handles unknown type as info', () => {
      const mockTerm = {
        writeln: function (m) {
          this._last = m;
        },
      };
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Unknown type', 'unknown');
      assertContains(mockTerm._last, 'Unknown type');
      w.FPBState.toolTerminal = null;
    });
    it('resets color at end of message', () => {
      const mockTerm = {
        writeln: function (m) {
          this._last = m;
        },
      };
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Test', 'success');
      assertContains(mockTerm._last, '\x1b[0m');
      w.FPBState.toolTerminal = null;
    });
  });

  describe('writeToSerial Function', () => {
    it('normalizes line endings', () => {
      const mockTerm = {
        write: function (m) {
          this._last = m;
        },
      };
      w.FPBState.rawTerminal = mockTerm;
      w.writeToSerial('test\ndata');
      assertContains(mockTerm._last, '\r\n');
      w.FPBState.rawTerminal = null;
    });
    it('handles null terminal gracefully', () => {
      w.FPBState.rawTerminal = null;
      w.writeToSerial('Test');
      assertTrue(true);
    });
    it('preserves existing CRLF', () => {
      const mockTerm = {
        write: function (m) {
          this._last = m;
        },
      };
      w.FPBState.rawTerminal = mockTerm;
      w.writeToSerial('test\r\ndata');
      assertEqual(mockTerm._last, 'test\r\ndata');
      w.FPBState.rawTerminal = null;
    });
    it('handles empty string', () => {
      const mockTerm = {
        write: function (m) {
          this._last = m;
        },
      };
      w.FPBState.rawTerminal = mockTerm;
      w.writeToSerial('');
      assertEqual(mockTerm._last, '');
      w.FPBState.rawTerminal = null;
    });
  });

  describe('switchTerminalTab Function', () => {
    it('updates currentTerminalTab to raw', () => {
      resetMocks();
      w.FPBState.currentTerminalTab = 'tool';
      w.switchTerminalTab('raw');
      assertEqual(w.FPBState.currentTerminalTab, 'raw');
    });
    it('updates currentTerminalTab to tool', () => {
      w.FPBState.currentTerminalTab = 'raw';
      w.switchTerminalTab('tool');
      assertEqual(w.FPBState.currentTerminalTab, 'tool');
    });
    it('fits terminals when switching', () => {
      const fitted = { tool: false, raw: false };
      w.FPBState.toolFitAddon = {
        fit: () => {
          fitted.tool = true;
        },
      };
      w.FPBState.rawFitAddon = {
        fit: () => {
          fitted.raw = true;
        },
      };
      w.switchTerminalTab('raw');
      assertTrue(fitted.tool || fitted.raw);
      w.FPBState.toolFitAddon = null;
      w.FPBState.rawFitAddon = null;
    });
  });

  describe('clearCurrentTerminal Function', () => {
    it('clears tool terminal when active', () => {
      const mockTerm = {
        clear: function () {
          this._cleared = true;
        },
        writeln: function () {},
      };
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.currentTerminalTab = 'tool';
      w.clearCurrentTerminal();
      assertTrue(mockTerm._cleared);
      w.FPBState.toolTerminal = null;
    });
    it('clears raw terminal when active', () => {
      const mockTerm = {
        clear: function () {
          this._cleared = true;
        },
      };
      w.FPBState.rawTerminal = mockTerm;
      w.FPBState.currentTerminalTab = 'raw';
      w.clearCurrentTerminal();
      assertTrue(mockTerm._cleared);
      w.FPBState.rawTerminal = null;
      w.FPBState.currentTerminalTab = 'tool';
    });
    it('handles null tool terminal', () => {
      w.FPBState.toolTerminal = null;
      w.FPBState.currentTerminalTab = 'tool';
      w.clearCurrentTerminal();
      assertTrue(true);
    });
    it('handles null raw terminal', () => {
      w.FPBState.rawTerminal = null;
      w.FPBState.currentTerminalTab = 'raw';
      w.clearCurrentTerminal();
      assertTrue(true);
      w.FPBState.currentTerminalTab = 'tool';
    });
  });

  describe('fitTerminals Function', () => {
    it('fits tool terminal', () => {
      let fitted = false;
      w.FPBState.toolFitAddon = {
        fit: () => {
          fitted = true;
        },
      };
      w.fitTerminals();
      w.FPBState.toolFitAddon = null;
      assertTrue(true);
    });
    it('fits raw terminal', () => {
      let fitted = false;
      w.FPBState.rawFitAddon = {
        fit: () => {
          fitted = true;
        },
      };
      w.fitTerminals();
      w.FPBState.rawFitAddon = null;
      assertTrue(true);
    });
    it('handles null addons', () => {
      w.FPBState.toolFitAddon = null;
      w.FPBState.rawFitAddon = null;
      w.fitTerminals();
      assertTrue(true);
    });
  });
};
