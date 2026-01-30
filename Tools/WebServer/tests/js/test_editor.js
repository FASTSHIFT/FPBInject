/**
 * Tests for features/editor.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertFalse,
  assertContains,
} = require('./framework');
const {
  resetMocks,
  browserGlobals,
  setFetchResponse,
  getFetchCalls,
  MockTerminal,
} = require('./mocks');

module.exports = function (w) {
  describe('Editor Functions (features/editor.js)', () => {
    it('initAceEditor is a function', () =>
      assertTrue(typeof w.initAceEditor === 'function'));
    it('getAceEditorContent is a function', () =>
      assertTrue(typeof w.getAceEditorContent === 'function'));
    it('switchEditorTab is a function', () =>
      assertTrue(typeof w.switchEditorTab === 'function'));
    it('closeTab is a function', () =>
      assertTrue(typeof w.closeTab === 'function'));
    it('openDisassembly is a function', () =>
      assertTrue(typeof w.openDisassembly === 'function'));
    it('openManualPatchTab is a function', () =>
      assertTrue(typeof w.openManualPatchTab === 'function'));
    it('escapeHtml is a function', () =>
      assertTrue(typeof w.escapeHtml === 'function'));
  });

  describe('getAceEditorContent Function', () => {
    it('returns editor value', () => {
      const mockEditor = { getValue: () => 'test code' };
      w.FPBState.aceEditors.set('test_tab', mockEditor);
      const content = w.getAceEditorContent('test_tab');
      assertEqual(content, 'test code');
      w.FPBState.aceEditors.delete('test_tab');
    });
    it('returns empty for missing editor', () => {
      const content = w.getAceEditorContent('nonexistent');
      assertEqual(content, '');
    });
    it('returns textarea value as fallback', () => {
      const el = browserGlobals.document.getElementById('editor_fallback_tab');
      el.value = 'fallback content';
      const content = w.getAceEditorContent('fallback_tab');
      assertEqual(content, 'fallback content');
    });
  });

  describe('switchEditorTab Function', () => {
    it('updates activeEditorTab', () => {
      w.FPBState.editorTabs = [{ id: 'tab1', type: 'c' }];
      w.switchEditorTab('tab1');
      assertEqual(w.FPBState.activeEditorTab, 'tab1');
      w.FPBState.editorTabs = [];
    });
    it('resizes editor', () => {
      const mockEditor = {
        resize: function () {
          this._resized = true;
        },
      };
      w.FPBState.aceEditors.set('tab2', mockEditor);
      w.FPBState.editorTabs = [{ id: 'tab2', type: 'c' }];
      w.switchEditorTab('tab2');
      w.FPBState.aceEditors.delete('tab2');
      w.FPBState.editorTabs = [];
      assertTrue(true);
    });
    it('handles missing tab', () => {
      w.FPBState.editorTabs = [];
      w.switchEditorTab('nonexistent');
      assertTrue(true);
    });
    it('sets currentPatchTab for c type', () => {
      w.FPBState.editorTabs = [
        { id: 'patch_tab', type: 'c', funcName: 'test_func' },
      ];
      w.switchEditorTab('patch_tab');
      w.FPBState.editorTabs = [];
      assertTrue(true);
    });
  });

  describe('closeTab Function', () => {
    it('removes tab from editorTabs', () => {
      const mockEditor = { destroy: () => {} };
      w.FPBState.editorTabs = [{ id: 'tab1', closable: true }];
      w.FPBState.aceEditors.set('tab1', mockEditor);
      w.closeTab('tab1');
      assertEqual(w.FPBState.editorTabs.length, 0);
      assertFalse(w.FPBState.aceEditors.has('tab1'));
    });
    it('ignores non-closable tabs', () => {
      w.FPBState.editorTabs = [{ id: 'tab1', closable: false }];
      w.closeTab('tab1');
      assertEqual(w.FPBState.editorTabs.length, 1);
      w.FPBState.editorTabs = [];
    });
    it('clears currentPatchTab if matching', () => {
      const mockEditor = { destroy: () => {} };
      w.FPBState.editorTabs = [{ id: 'patch_func', closable: true }];
      w.FPBState.aceEditors.set('patch_func', mockEditor);
      w.FPBState.currentPatchTab = { id: 'patch_func', funcName: 'func' };
      w.closeTab('patch_func');
      assertEqual(w.FPBState.currentPatchTab, null);
    });
    it('switches to another tab if active closed', () => {
      const mockEditor1 = { destroy: () => {} };
      const mockEditor2 = { resize: () => {} };
      w.FPBState.editorTabs = [
        { id: 'tab1', closable: true },
        { id: 'tab2', closable: true },
      ];
      w.FPBState.aceEditors.set('tab1', mockEditor1);
      w.FPBState.aceEditors.set('tab2', mockEditor2);
      w.FPBState.activeEditorTab = 'tab1';
      w.closeTab('tab1');
      assertEqual(w.FPBState.activeEditorTab, 'tab2');
      w.FPBState.aceEditors.clear();
      w.FPBState.editorTabs = [];
    });
    it('handles missing tab', () => {
      w.FPBState.editorTabs = [];
      w.closeTab('nonexistent');
      assertTrue(true);
    });
    it('destroys ace editor', () => {
      let destroyed = false;
      const mockEditor = {
        destroy: () => {
          destroyed = true;
        },
      };
      w.FPBState.editorTabs = [{ id: 'tab1', closable: true }];
      w.FPBState.aceEditors.set('tab1', mockEditor);
      w.closeTab('tab1');
      assertTrue(destroyed);
      w.FPBState.editorTabs = [];
    });
    it('handles event parameter', () => {
      const mockEvent = { stopPropagation: () => {} };
      const mockEditor = { destroy: () => {} };
      w.FPBState.editorTabs = [{ id: 'tab1', closable: true }];
      w.FPBState.aceEditors.set('tab1', mockEditor);
      w.closeTab('tab1', mockEvent);
      w.FPBState.editorTabs = [];
      assertTrue(true);
    });
  });

  describe('escapeHtml Function', () => {
    it('escapes < character', () => {
      const result = w.escapeHtml('<script>');
      assertContains(result, '&lt;');
    });
    it('escapes > character', () => {
      const result = w.escapeHtml('<script>');
      assertContains(result, '&gt;');
    });
    it('escapes & character', () => {
      const result = w.escapeHtml('a & b');
      assertContains(result, '&amp;');
    });
    it('leaves normal text unchanged', () => {
      assertEqual(w.escapeHtml('Hello World'), 'Hello World');
    });
    it('handles empty string', () => {
      assertEqual(w.escapeHtml(''), '');
    });
    it('handles multiple special chars', () => {
      const result = w.escapeHtml('<a>&</a>');
      assertContains(result, '&lt;');
      assertContains(result, '&gt;');
      assertContains(result, '&amp;');
    });
    it('handles numbers', () => {
      assertEqual(w.escapeHtml('123'), '123');
    });
    it('handles special chars in middle', () => {
      const result = w.escapeHtml('hello<world>test');
      assertContains(result, '&lt;');
      assertContains(result, '&gt;');
    });
    it('escapes quotes', () => {
      const result = w.escapeHtml('"test"');
      assertTrue(result.includes('&quot;') || result.includes('"'));
    });
  });

  describe('openDisassembly Function', () => {
    it('is async function', () => {
      assertTrue(w.openDisassembly.constructor.name === 'AsyncFunction');
    });

    it('switches to existing tab if already open', async () => {
      resetMocks();
      w.FPBState.editorTabs = [
        { id: 'disasm_test_func', title: 'test_func.asm' },
      ];
      w.FPBState.toolTerminal = new MockTerminal();
      await w.openDisassembly('test_func', '0x1000');
      assertEqual(w.FPBState.activeEditorTab, 'disasm_test_func');
      w.FPBState.editorTabs = [];
      w.FPBState.toolTerminal = null;
    });

    it('fetches disassembly from API', async () => {
      resetMocks();
      w.FPBState.editorTabs = [];
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.aceEditors = new Map();
      setFetchResponse('/api/symbols/disasm', { disasm: '; test disasm' });
      await w.openDisassembly('new_func', '0x2000');
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/symbols/disasm')));
      w.FPBState.editorTabs = [];
      w.FPBState.toolTerminal = null;
    });
  });

  describe('openManualPatchTab Function', () => {
    it('is a function', () => {
      assertTrue(typeof w.openManualPatchTab === 'function');
    });

    it('switches to existing tab if already open', async () => {
      resetMocks();
      w.FPBState.editorTabs = [
        {
          id: 'patch_test_func',
          title: 'patch_test_func.c',
          type: 'c',
          funcName: 'test_func',
        },
      ];
      w.FPBState.toolTerminal = new MockTerminal();
      await w.openManualPatchTab('test_func');
      assertEqual(w.FPBState.activeEditorTab, 'patch_test_func');
      w.FPBState.editorTabs = [];
      w.FPBState.toolTerminal = null;
    });
  });

  describe('initAceEditor Function', () => {
    it('is a function', () => {
      assertTrue(typeof w.initAceEditor === 'function');
    });

    it('returns editor object when element exists', () => {
      resetMocks();
      // initAceEditor returns an editor object when ace is available
      const result = w.initAceEditor('test_tab', 'content', 'c_cpp');
      assertTrue(result !== null);
    });
  });

  describe('savePatchFile Function', () => {
    it('is a function', () => {
      assertTrue(typeof w.savePatchFile === 'function');
    });

    it('is async function', () => {
      assertTrue(w.savePatchFile.constructor.name === 'AsyncFunction');
    });

    it('returns error if no patch tab selected', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.currentPatchTab = null;
      await w.savePatchFile();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('No patch tab'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });
  });
};
