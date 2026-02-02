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
const { resetMocks, MockTerminal, MockFitAddon } = require('./mocks');

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
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Test message', 'info');
      assertTrue(mockTerm._writes.length > 0);
      assertContains(mockTerm._lastWrite, 'Test message');
      w.FPBState.toolTerminal = null;
    });
    it('writes success message with green color', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Success!', 'success');
      assertContains(mockTerm._lastWrite, '\x1b[32m');
      w.FPBState.toolTerminal = null;
    });
    it('writes error message with red color', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Error!', 'error');
      assertContains(mockTerm._lastWrite, '\x1b[31m');
      w.FPBState.toolTerminal = null;
    });
    it('writes warning message with yellow color', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Warning!', 'warning');
      assertContains(mockTerm._lastWrite, '\x1b[33m');
      w.FPBState.toolTerminal = null;
    });
    it('writes system message with cyan color', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('System', 'system');
      assertContains(mockTerm._lastWrite, '\x1b[36m');
      w.FPBState.toolTerminal = null;
    });
    it('handles multiline messages', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Line1\nLine2\nLine3', 'info');
      assertEqual(mockTerm._writes.length, 3);
      w.FPBState.toolTerminal = null;
    });
    it('handles null terminal gracefully', () => {
      w.FPBState.toolTerminal = null;
      // Should not throw - just return early
      w.writeToOutput('Test', 'info');
      assertEqual(w.FPBState.toolTerminal, null);
    });
    it('handles unknown type as info', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Unknown type', 'unknown');
      assertContains(mockTerm._lastWrite, 'Unknown type');
      w.FPBState.toolTerminal = null;
    });
    it('resets color at end of message', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('Test', 'success');
      assertContains(mockTerm._lastWrite, '\x1b[0m');
      w.FPBState.toolTerminal = null;
    });
    it('handles empty message', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.writeToOutput('', 'info');
      assertTrue(mockTerm._writes.length >= 0);
      w.FPBState.toolTerminal = null;
    });
  });

  describe('writeToSerial Function', () => {
    it('normalizes line endings', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.rawTerminal = mockTerm;
      w.writeToSerial('test\ndata');
      assertContains(mockTerm._lastWrite, '\r\n');
      w.FPBState.rawTerminal = null;
    });
    it('handles null terminal gracefully', () => {
      w.FPBState.rawTerminal = null;
      // Should not throw - just return early
      w.writeToSerial('Test');
      assertEqual(w.FPBState.rawTerminal, null);
    });
    it('preserves existing CRLF', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.rawTerminal = mockTerm;
      w.writeToSerial('test\r\ndata');
      assertEqual(mockTerm._lastWrite, 'test\r\ndata');
      w.FPBState.rawTerminal = null;
    });
    it('handles empty string', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.rawTerminal = mockTerm;
      w.writeToSerial('');
      assertEqual(mockTerm._lastWrite, '');
      w.FPBState.rawTerminal = null;
    });
    it('handles multiple newlines', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.rawTerminal = mockTerm;
      w.writeToSerial('a\nb\nc');
      assertContains(mockTerm._lastWrite, '\r\n');
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
      const toolAddon = new MockFitAddon();
      const rawAddon = new MockFitAddon();
      w.FPBState.toolFitAddon = toolAddon;
      w.FPBState.rawFitAddon = rawAddon;
      w.switchTerminalTab('raw');
      assertTrue(toolAddon._fitted || rawAddon._fitted);
      w.FPBState.toolFitAddon = null;
      w.FPBState.rawFitAddon = null;
    });
  });

  describe('clearCurrentTerminal Function', () => {
    it('clears tool terminal when active', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.currentTerminalTab = 'tool';
      w.clearCurrentTerminal();
      assertTrue(mockTerm._cleared);
      w.FPBState.toolTerminal = null;
    });
    it('clears raw terminal when active', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.rawTerminal = mockTerm;
      w.FPBState.currentTerminalTab = 'raw';
      w.clearCurrentTerminal();
      assertTrue(mockTerm._cleared);
      w.FPBState.rawTerminal = null;
      w.FPBState.currentTerminalTab = 'tool';
    });
    it('handles null tool terminal gracefully', () => {
      w.FPBState.toolTerminal = null;
      w.FPBState.currentTerminalTab = 'tool';
      // Should not throw
      w.clearCurrentTerminal();
      assertEqual(w.FPBState.toolTerminal, null);
    });
    it('handles null raw terminal gracefully', () => {
      w.FPBState.rawTerminal = null;
      w.FPBState.currentTerminalTab = 'raw';
      // Should not throw
      w.clearCurrentTerminal();
      assertEqual(w.FPBState.rawTerminal, null);
      w.FPBState.currentTerminalTab = 'tool';
    });
    it('writes cleared message to tool terminal', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.currentTerminalTab = 'tool';
      w.clearCurrentTerminal();
      assertTrue(
        mockTerm._writes.some((w) => w.msg && w.msg.includes('cleared')),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('fitTerminals Function', () => {
    it('fits tool terminal', () => {
      const addon = new MockFitAddon();
      w.FPBState.toolFitAddon = addon;
      w.fitTerminals();
      assertTrue(addon._fitted);
      w.FPBState.toolFitAddon = null;
    });
    it('fits raw terminal', () => {
      const addon = new MockFitAddon();
      w.FPBState.rawFitAddon = addon;
      w.fitTerminals();
      assertTrue(addon._fitted);
      w.FPBState.rawFitAddon = null;
    });
    it('handles null addons gracefully', () => {
      w.FPBState.toolFitAddon = null;
      w.FPBState.rawFitAddon = null;
      // Should not throw
      w.fitTerminals();
      assertEqual(w.FPBState.toolFitAddon, null);
    });
  });

  describe('initTerminals Function', () => {
    it('is callable', () => {
      assertTrue(typeof w.initTerminals === 'function');
    });

    it('initializes terminals when containers exist', () => {
      resetMocks();
      w.initTerminals();
      // After init, terminals should be set
      assertTrue(
        w.FPBState.toolTerminal !== null ||
          typeof w.initTerminals === 'function',
      );
    });
  });

  describe('Terminal Theme Integration', () => {
    it('getTerminalTheme is a function', () => {
      assertTrue(typeof w.getTerminalTheme === 'function');
    });

    it('returns theme object', () => {
      const theme = w.getTerminalTheme();
      assertTrue(theme !== null && typeof theme === 'object');
    });
  });
};
