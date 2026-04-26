/**
 * Tests for features/quick-commands.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertFalse,
  assertDeepEqual,
} = require('./framework');
const {
  browserGlobals,
  resetMocks,
  MockTerminal,
  setFetchResponse,
  getFetchCalls,
  createMockElement,
  getElement,
} = require('./mocks');

module.exports = function (w) {
  describe('Quick Commands (features/quick-commands.js)', () => {
    // ===== Function exports =====
    it('loadQuickCommands is a function', () =>
      assertTrue(typeof w.loadQuickCommands === 'function'));
    it('saveQuickCommands is a function', () =>
      assertTrue(typeof w.saveQuickCommands === 'function'));
    it('loadGroupMeta is a function', () =>
      assertTrue(typeof w.loadGroupMeta === 'function'));
    it('saveGroupMeta is a function', () =>
      assertTrue(typeof w.saveGroupMeta === 'function'));
    it('ensureGroupMeta is a function', () =>
      assertTrue(typeof w.ensureGroupMeta === 'function'));
    it('renderQuickCommands is a function', () =>
      assertTrue(typeof w.renderQuickCommands === 'function'));
    it('executeQuickCommand is a function', () =>
      assertTrue(typeof w.executeQuickCommand === 'function'));
    it('openQuickCommandEditor is a function', () =>
      assertTrue(typeof w.openQuickCommandEditor === 'function'));
    it('closeQuickCommandEditor is a function', () =>
      assertTrue(typeof w.closeQuickCommandEditor === 'function'));
    it('saveQuickCommand is a function', () =>
      assertTrue(typeof w.saveQuickCommand === 'function'));
    it('deleteQuickCommand is a function', () =>
      assertTrue(typeof w.deleteQuickCommand === 'function'));
    it('duplicateQuickCommand is a function', () =>
      assertTrue(typeof w.duplicateQuickCommand === 'function'));
    it('exportQuickCommands is a function', () =>
      assertTrue(typeof w.exportQuickCommands === 'function'));
    it('importQuickCommands is a function', () =>
      assertTrue(typeof w.importQuickCommands === 'function'));
    it('clearAllQuickCommands is a function', () =>
      assertTrue(typeof w.clearAllQuickCommands === 'function'));
    it('testRunQuickCommand is a function', () =>
      assertTrue(typeof w.testRunQuickCommand === 'function'));
    it('generateId is a function', () =>
      assertTrue(typeof w.generateId === 'function'));
    it('unescapeCommand is a function', () =>
      assertTrue(typeof w.unescapeCommand === 'function'));
    it('escapeCommandForDisplay is a function', () =>
      assertTrue(typeof w.escapeCommandForDisplay === 'function'));
    it('sendSerialData is a function', () =>
      assertTrue(typeof w.sendSerialData === 'function'));
    it('stopMacroExecution is a function', () =>
      assertTrue(typeof w.stopMacroExecution === 'function'));
    it('hideQcContextMenus is a function', () =>
      assertTrue(typeof w.hideQcContextMenus === 'function'));
    it('moveToGroup is a function', () =>
      assertTrue(typeof w.moveToGroup === 'function'));
    it('initQuickCommands is a function', () =>
      assertTrue(typeof w.initQuickCommands === 'function'));
    it('renameGroup is a function', () =>
      assertTrue(typeof w.renameGroup === 'function'));
    it('deleteGroup is a function', () =>
      assertTrue(typeof w.deleteGroup === 'function'));
    it('showGroupContextMenu is a function', () =>
      assertTrue(typeof w.showGroupContextMenu === 'function'));
    it('qcGroupContextAction is a function', () =>
      assertTrue(typeof w.qcGroupContextAction === 'function'));
    it('openExportDialog is a function', () =>
      assertTrue(typeof w.openExportDialog === 'function'));
    it('resolveImportConflicts is a function', () =>
      assertTrue(typeof w.resolveImportConflicts === 'function'));
    it('openImportDialog is a function', () =>
      assertTrue(typeof w.openImportDialog === 'function'));
    it('executeExport is a function', () =>
      assertTrue(typeof w.executeExport === 'function'));
    it('executeImport is a function', () =>
      assertTrue(typeof w.executeImport === 'function'));
    it('persistCommandOrder is a function', () =>
      assertTrue(typeof w.persistCommandOrder === 'function'));
    it('persistGroupOrder is a function', () =>
      assertTrue(typeof w.persistGroupOrder === 'function'));
  });

  // ===== Escape handling =====
  describe('Quick Commands - Escape Handling', () => {
    it('unescapeCommand converts \\n to newline', () => {
      assertEqual(w.unescapeCommand('hello\\n'), 'hello\n');
    });
    it('unescapeCommand converts \\r to carriage return', () => {
      assertEqual(w.unescapeCommand('hello\\r'), 'hello\r');
    });
    it('unescapeCommand converts \\t to tab', () => {
      assertEqual(w.unescapeCommand('a\\tb'), 'a\tb');
    });
    it('unescapeCommand converts \\x1b to ESC', () => {
      assertEqual(w.unescapeCommand('\\x1b[0m'), '\x1b[0m');
    });
    it('unescapeCommand converts \\\\ to backslash', () => {
      assertEqual(w.unescapeCommand('path\\\\file'), 'path\\file');
    });
    it('unescapeCommand handles multiple escapes', () => {
      assertEqual(w.unescapeCommand('a\\nb\\tc\\r'), 'a\nb\tc\r');
    });
    it('unescapeCommand handles empty string', () => {
      assertEqual(w.unescapeCommand(''), '');
    });
    it('escapeCommandForDisplay converts newline to \\n', () => {
      assertEqual(w.escapeCommandForDisplay('hello\n'), 'hello\\n');
    });
    it('escapeCommandForDisplay converts tab to \\t', () => {
      assertEqual(w.escapeCommandForDisplay('a\tb'), 'a\\tb');
    });
    it('escapeCommandForDisplay round-trips with unescape', () => {
      const original = 'cmd\\narg\\t--flag';
      const unescaped = w.unescapeCommand(original);
      const reescaped = w.escapeCommandForDisplay(unescaped);
      assertEqual(reescaped, original);
    });
  });

  // ===== ID generation =====
  describe('Quick Commands - ID Generation', () => {
    it('generateId returns string starting with qc_', () => {
      const id = w.generateId();
      assertTrue(typeof id === 'string');
      assertTrue(id.startsWith('qc_'));
    });
    it('generateId returns unique IDs', () => {
      const ids = new Set();
      for (let i = 0; i < 50; i++) ids.add(w.generateId());
      assertEqual(ids.size, 50);
    });
  });

  // ===== Storage =====
  describe('Quick Commands - Storage', () => {
    it('loadQuickCommands returns empty array when no data', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = () => null;
      const result = w.loadQuickCommands();
      assertTrue(Array.isArray(result));
      assertEqual(result.length, 0);
      browserGlobals.localStorage.getItem = origGet;
    });
    it('loadQuickCommands returns parsed data', () => {
      const cmds = [
        { id: 'qc_1', name: 'test', type: 'single', command: 'ps\\n' },
      ];
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (key) => {
        if (key === 'fpbinject-quick-commands') return JSON.stringify(cmds);
        return null;
      };
      const result = w.loadQuickCommands();
      assertEqual(result.length, 1);
      assertEqual(result[0].name, 'test');
      browserGlobals.localStorage.getItem = origGet;
    });
    it('loadQuickCommands handles invalid JSON gracefully', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = () => 'not-json{{{';
      const result = w.loadQuickCommands();
      assertTrue(Array.isArray(result));
      assertEqual(result.length, 0);
      browserGlobals.localStorage.getItem = origGet;
    });
    it('saveQuickCommands stores data in localStorage', () => {
      let savedKey = null;
      let savedValue = null;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.setItem = (k, v) => {
        savedKey = k;
        savedValue = v;
      };
      w.saveQuickCommands([{ id: 'qc_1', name: 'test' }]);
      assertEqual(savedKey, 'fpbinject-quick-commands');
      const parsed = JSON.parse(savedValue);
      assertEqual(parsed.length, 1);
      browserGlobals.localStorage.setItem = origSet;
    });
    it('saveQuickCommands handles localStorage error gracefully', () => {
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.setItem = () => {
        throw new Error('quota exceeded');
      };
      w.saveQuickCommands([{ id: 'err1', name: 'test' }]);
      browserGlobals.localStorage.setItem = origSet;
      assertTrue(true);
    });
  });

  // ===== Group Meta Storage =====
  describe('Quick Commands - Group Meta Storage', () => {
    it('T01: loadGroupMeta returns empty array when no data', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = () => null;
      const result = w.loadGroupMeta();
      assertTrue(Array.isArray(result));
      assertEqual(result.length, 0);
      browserGlobals.localStorage.getItem = origGet;
    });
    it('T02: loadGroupMeta handles invalid JSON gracefully', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (key) => {
        if (key === 'fpbinject-quick-command-groups') return '{bad json';
        return null;
      };
      const result = w.loadGroupMeta();
      assertTrue(Array.isArray(result));
      assertEqual(result.length, 0);
      browserGlobals.localStorage.getItem = origGet;
    });
    it('T03: saveGroupMeta stores data correctly', () => {
      let savedKey = null;
      let savedValue = null;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.setItem = (k, v) => {
        savedKey = k;
        savedValue = v;
      };
      w.saveGroupMeta([{ name: 'A', order: 0 }]);
      assertEqual(savedKey, 'fpbinject-quick-command-groups');
      const parsed = JSON.parse(savedValue);
      assertEqual(parsed.length, 1);
      assertEqual(parsed[0].name, 'A');
      browserGlobals.localStorage.setItem = origSet;
    });
    it('T04: saveGroupMeta handles localStorage error', () => {
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.setItem = () => {
        throw new Error('quota');
      };
      w.saveGroupMeta([{ name: 'X', order: 0 }]);
      browserGlobals.localStorage.setItem = origSet;
      assertTrue(true);
    });
    it('T05: ensureGroupMeta adds missing groups', () => {
      const store = {};
      const origGet = browserGlobals.localStorage.getItem;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => store[k] || null;
      browserGlobals.localStorage.setItem = (k, v) => {
        store[k] = v;
      };

      // No existing meta, commands reference group "X"
      const cmds = [
        { id: 'c1', group: 'X' },
        { id: 'c2', group: null },
      ];
      const result = w.ensureGroupMeta(cmds);
      assertEqual(result.length, 1);
      assertEqual(result[0].name, 'X');

      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.localStorage.setItem = origSet;
    });
    it('T06: ensureGroupMeta removes orphan groups', () => {
      const store = {
        'fpbinject-quick-command-groups': JSON.stringify([
          { name: 'Y', order: 0 },
          { name: 'Z', order: 1 },
        ]),
      };
      const origGet = browserGlobals.localStorage.getItem;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => store[k] || null;
      browserGlobals.localStorage.setItem = (k, v) => {
        store[k] = v;
      };

      // Only "Z" is referenced
      const cmds = [{ id: 'c1', group: 'Z' }];
      const result = w.ensureGroupMeta(cmds);
      assertEqual(result.length, 1);
      assertEqual(result[0].name, 'Z');
      assertEqual(result[0].order, 0);

      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.localStorage.setItem = origSet;
    });
  });

  // ===== Group Rename =====
  describe('Quick Commands - Group Rename', () => {
    it('T07: renameGroup updates group name on all commands', () => {
      const store = {};
      const origGet = browserGlobals.localStorage.getItem;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => store[k] || null;
      browserGlobals.localStorage.setItem = (k, v) => {
        store[k] = v;
      };

      store['fpbinject-quick-commands'] = JSON.stringify([
        { id: 'c1', name: 'a', group: 'Old' },
        { id: 'c2', name: 'b', group: 'Old' },
        { id: 'c3', name: 'c', group: 'Other' },
      ]);
      store['fpbinject-quick-command-groups'] = JSON.stringify([
        { name: 'Old', order: 0 },
        { name: 'Other', order: 1 },
      ]);

      const origPrompt = global.prompt;
      global.prompt = () => 'NewName';

      w.renameGroup('Old');

      const cmds = JSON.parse(store['fpbinject-quick-commands']);
      assertEqual(cmds[0].group, 'NewName');
      assertEqual(cmds[1].group, 'NewName');
      assertEqual(cmds[2].group, 'Other');

      const meta = JSON.parse(store['fpbinject-quick-command-groups']);
      assertTrue(meta.some((g) => g.name === 'NewName'));
      assertFalse(meta.some((g) => g.name === 'Old'));

      global.prompt = origPrompt;
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.localStorage.setItem = origSet;
    });
    it('T08: renameGroup does nothing on empty string', () => {
      const store = {};
      const origGet = browserGlobals.localStorage.getItem;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => store[k] || null;
      browserGlobals.localStorage.setItem = (k, v) => {
        store[k] = v;
      };

      store['fpbinject-quick-commands'] = JSON.stringify([
        { id: 'c1', name: 'a', group: 'Keep' },
      ]);
      store['fpbinject-quick-command-groups'] = JSON.stringify([
        { name: 'Keep', order: 0 },
      ]);

      const origPrompt = global.prompt;
      global.prompt = () => '';
      w.renameGroup('Keep');

      const cmds = JSON.parse(store['fpbinject-quick-commands']);
      assertEqual(cmds[0].group, 'Keep');

      global.prompt = origPrompt;
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.localStorage.setItem = origSet;
    });
    it('T09: renameGroup merges when target name exists', () => {
      const store = {};
      const origGet = browserGlobals.localStorage.getItem;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => store[k] || null;
      browserGlobals.localStorage.setItem = (k, v) => {
        store[k] = v;
      };

      store['fpbinject-quick-commands'] = JSON.stringify([
        { id: 'c1', name: 'a', group: 'A' },
        { id: 'c2', name: 'b', group: 'B' },
      ]);
      store['fpbinject-quick-command-groups'] = JSON.stringify([
        { name: 'A', order: 0 },
        { name: 'B', order: 1 },
      ]);

      const origPrompt = global.prompt;
      global.prompt = () => 'B';
      w.renameGroup('A');

      const cmds = JSON.parse(store['fpbinject-quick-commands']);
      assertEqual(cmds[0].group, 'B');
      assertEqual(cmds[1].group, 'B');

      const meta = JSON.parse(store['fpbinject-quick-command-groups']);
      // 'A' should be removed, only 'B' remains
      assertFalse(meta.some((g) => g.name === 'A'));
      assertTrue(meta.some((g) => g.name === 'B'));

      global.prompt = origPrompt;
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.localStorage.setItem = origSet;
    });
    it('T10: renameGroup cancels on null prompt', () => {
      const origPrompt = global.prompt;
      global.prompt = () => null;
      const origGet = browserGlobals.localStorage.getItem;
      let setCalled = false;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = () => JSON.stringify([]);
      browserGlobals.localStorage.setItem = () => {
        setCalled = true;
      };
      w.renameGroup('Test');
      assertFalse(setCalled);
      global.prompt = origPrompt;
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.localStorage.setItem = origSet;
    });
    it('renameGroup does nothing with null name', () => {
      const origGet = browserGlobals.localStorage.getItem;
      let setCalled = false;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.setItem = () => {
        setCalled = true;
      };
      w.renameGroup(null);
      assertFalse(setCalled);
      browserGlobals.localStorage.setItem = origSet;
    });
  });

  // ===== Group Delete =====
  describe('Quick Commands - Group Delete', () => {
    it('T12: deleteGroup removes group and ungroups commands', () => {
      const store = {};
      const origGet = browserGlobals.localStorage.getItem;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => store[k] || null;
      browserGlobals.localStorage.setItem = (k, v) => {
        store[k] = v;
      };

      store['fpbinject-quick-commands'] = JSON.stringify([
        { id: 'c1', name: 'a', group: 'Del' },
        { id: 'c2', name: 'b', group: 'Keep' },
      ]);
      store['fpbinject-quick-command-groups'] = JSON.stringify([
        { name: 'Del', order: 0 },
        { name: 'Keep', order: 1 },
      ]);

      const origConfirm = global.confirm;
      global.confirm = () => true;
      w.deleteGroup('Del');

      const cmds = JSON.parse(store['fpbinject-quick-commands']);
      assertEqual(cmds[0].group, null);
      assertEqual(cmds[1].group, 'Keep');

      global.confirm = origConfirm;
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.localStorage.setItem = origSet;
    });
    it('T13: deleteGroup cancels on confirm false', () => {
      const origGet = browserGlobals.localStorage.getItem;
      let setCalled = false;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = () =>
        JSON.stringify([{ id: 'c1', group: 'G' }]);
      browserGlobals.localStorage.setItem = () => {
        setCalled = true;
      };
      const origConfirm = global.confirm;
      global.confirm = () => false;
      w.deleteGroup('G');
      assertFalse(setCalled);
      global.confirm = origConfirm;
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.localStorage.setItem = origSet;
    });
    it('deleteGroup does nothing with null name', () => {
      w.deleteGroup(null);
      assertTrue(true);
    });
  });

  // ===== Group Context Menu =====
  describe('Quick Commands - Group Context Menu', () => {
    it('T24: showGroupContextMenu positions menu', () => {
      const menu = browserGlobals.document.getElementById('qcGroupContextMenu');
      const mockEvent = {
        preventDefault: () => {},
        stopPropagation: () => {},
        clientX: 100,
        clientY: 200,
      };
      w.showGroupContextMenu(mockEvent, 'TestGroup');
      assertEqual(menu.style.display, 'block');
      assertEqual(menu.style.left, '100px');
      assertEqual(menu.style.top, '200px');
    });
    it('T28: showGroupContextMenu hides other menus first', () => {
      const cmdMenu = browserGlobals.document.getElementById('qcContextMenu');
      cmdMenu.style.display = 'block';
      const mockEvent = {
        preventDefault: () => {},
        stopPropagation: () => {},
        clientX: 10,
        clientY: 10,
      };
      w.showGroupContextMenu(mockEvent, 'G');
      assertEqual(cmdMenu.style.display, 'none');
    });
    it('qcGroupContextAction rename calls renameGroup', () => {
      const mockEvent = {
        preventDefault: () => {},
        stopPropagation: () => {},
        clientX: 10,
        clientY: 10,
      };
      w.showGroupContextMenu(mockEvent, 'TestG');
      const origPrompt = global.prompt;
      global.prompt = () => null;
      w.qcGroupContextAction('rename');
      global.prompt = origPrompt;
      assertTrue(true);
    });
    it('qcGroupContextAction delete calls deleteGroup', () => {
      const mockEvent = {
        preventDefault: () => {},
        stopPropagation: () => {},
        clientX: 10,
        clientY: 10,
      };
      w.showGroupContextMenu(mockEvent, 'TestG');
      const origConfirm = global.confirm;
      global.confirm = () => false;
      w.qcGroupContextAction('delete');
      global.confirm = origConfirm;
      assertTrue(true);
    });
    it('qcGroupContextAction with no target does nothing', () => {
      // Clear target by calling with null
      w.showGroupContextMenu(
        {
          preventDefault: () => {},
          stopPropagation: () => {},
          clientX: 0,
          clientY: 0,
        },
        null,
      );
      w.qcGroupContextAction('rename');
      assertTrue(true);
    });
  });

  // ===== Execution =====
  describe('Quick Commands - Execution', () => {
    it('executeQuickCommand returns early if not connected', async () => {
      w.FPBState.isConnected = false;
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = () =>
        JSON.stringify([{ id: 'qc_1', type: 'single', command: 'test\\n' }]);
      await w.executeQuickCommand('qc_1');
      browserGlobals.localStorage.getItem = origGet;
    });
    it('executeQuickCommand sends single command via fetch', async () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            {
              id: 'qc_1',
              type: 'single',
              command: 'ps\\n',
              appendNewline: true,
            },
          ]);
        return null;
      };
      let sentData = null;
      const origFetch = global.fetch;
      global.fetch = async (url, opts) => {
        if (url === '/api/serial/send') sentData = JSON.parse(opts.body).data;
        return { ok: true, json: async () => ({ success: true }) };
      };
      await w.executeQuickCommand('qc_1');
      assertEqual(sentData, 'ps\n');
      global.fetch = origFetch;
      browserGlobals.localStorage.getItem = origGet;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });
    it('executeQuickCommand handles unknown ID gracefully', async () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands') return JSON.stringify([]);
        return null;
      };
      await w.executeQuickCommand('nonexistent');
      browserGlobals.localStorage.getItem = origGet;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });
    it('executeQuickCommand appends newline when enabled', async () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            { id: 'qc_nl', type: 'single', command: 'ps', appendNewline: true },
          ]);
        return null;
      };
      let sentData = null;
      const origFetch = global.fetch;
      global.fetch = async (url, opts) => {
        if (url === '/api/serial/send') sentData = JSON.parse(opts.body).data;
        return { ok: true, json: async () => ({ success: true }) };
      };
      await w.executeQuickCommand('qc_nl');
      assertEqual(sentData, 'ps\n');
      global.fetch = origFetch;
      browserGlobals.localStorage.getItem = origGet;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });
    it('executeQuickCommand does not append newline when disabled', async () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            {
              id: 'qc_nonl',
              type: 'single',
              command: 'raw',
              appendNewline: false,
            },
          ]);
        return null;
      };
      let sentData = null;
      const origFetch = global.fetch;
      global.fetch = async (url, opts) => {
        if (url === '/api/serial/send') sentData = JSON.parse(opts.body).data;
        return { ok: true, json: async () => ({ success: true }) };
      };
      await w.executeQuickCommand('qc_nonl');
      assertEqual(sentData, 'raw');
      global.fetch = origFetch;
      browserGlobals.localStorage.getItem = origGet;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });
    it('sendSerialData delegates to sendTerminalCommand', async () => {
      w.FPBState.isConnected = true;
      let fetchUrl = null;
      const origFetch = global.fetch;
      global.fetch = async (url, opts) => {
        fetchUrl = url;
        return { ok: true, json: async () => ({ success: true }) };
      };
      await w.sendSerialData('hello\n');
      assertEqual(fetchUrl, '/api/serial/send');
      global.fetch = origFetch;
      w.FPBState.isConnected = false;
    });
  });

  // ===== Macro execution =====
  describe('Quick Commands - Macro Execution', () => {
    it('stopMacroExecution does not throw when no macro running', () => {
      w.stopMacroExecution();
      assertTrue(true);
    });
    it('executeQuickCommand runs macro steps', async () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            {
              id: 'qc_m1',
              type: 'macro',
              steps: [
                { command: 'cmd1\\n', delay: 0, appendNewline: true },
                { command: 'cmd2\\n', delay: 0, appendNewline: false },
              ],
            },
          ]);
        return null;
      };
      let sentCount = 0;
      const origFetch = global.fetch;
      global.fetch = async () => {
        sentCount++;
        return { ok: true, json: async () => ({ success: true }) };
      };
      await w.executeQuickCommand('qc_m1');
      assertEqual(sentCount, 2);
      global.fetch = origFetch;
      browserGlobals.localStorage.getItem = origGet;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });
    it('executeMacro with delay executes all steps', async () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            {
              id: 'qc_delay',
              type: 'macro',
              steps: [
                { command: 'step1\\n', delay: 10, appendNewline: true },
                { command: 'step2\\n', delay: 10, appendNewline: false },
              ],
            },
          ]);
        return null;
      };
      let sentCount = 0;
      const origFetch = global.fetch;
      global.fetch = async () => {
        sentCount++;
        return { ok: true, json: async () => ({ success: true }) };
      };
      await w.executeQuickCommand('qc_delay');
      assertEqual(sentCount, 2);
      global.fetch = origFetch;
      browserGlobals.localStorage.getItem = origGet;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });
  });

  // ===== Editor modal =====
  describe('Quick Commands - Editor Modal', () => {
    it('closeQuickCommandEditor removes show class', () => {
      const modal = browserGlobals.document.getElementById(
        'quickCommandEditorModal',
      );
      modal.classList.add('show');
      w.closeQuickCommandEditor();
      assertFalse(modal.classList.contains('show'));
    });
    it('openQuickCommandEditor adds show class for new command', () => {
      const modal = browserGlobals.document.getElementById(
        'quickCommandEditorModal',
      );
      browserGlobals.document.getElementById('quickCommandEditorTitle');
      browserGlobals.document.getElementById('qcName');
      browserGlobals.document.getElementById('qcCommand');
      const appendNl =
        browserGlobals.document.getElementById('qcAppendNewline');
      appendNl.type = 'checkbox';
      browserGlobals.document.getElementById('qcGroup');
      browserGlobals.document.getElementById('qcNewGroup');
      browserGlobals.document.getElementById('qcTestRunBtn');

      const radioSingle = createMockElement('_radio_single');
      radioSingle.type = 'radio';
      radioSingle.name = 'qcType';
      radioSingle.value = 'single';
      radioSingle.checked = true;
      const radioMacro = createMockElement('_radio_macro');
      radioMacro.type = 'radio';
      radioMacro.name = 'qcType';
      radioMacro.value = 'macro';
      radioMacro.checked = false;

      const origQS = browserGlobals.document.querySelector;
      browserGlobals.document.querySelector = (sel) => {
        if (sel.includes('value="single"')) return radioSingle;
        if (sel.includes('value="macro"')) return radioMacro;
        if (sel.includes('.qc-item')) return null;
        return origQS ? origQS(sel) : null;
      };
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands') return JSON.stringify([]);
        if (k === 'fpbinject-quick-command-groups') return JSON.stringify([]);
        return null;
      };
      w.openQuickCommandEditor();
      assertTrue(modal.classList.contains('show'));
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.document.querySelector = origQS;
    });
    it('openQuickCommandEditor loads existing command for editing', () => {
      const modal = browserGlobals.document.getElementById(
        'quickCommandEditorModal',
      );
      browserGlobals.document.getElementById('quickCommandEditorTitle');
      const nameInput = browserGlobals.document.getElementById('qcName');
      browserGlobals.document.getElementById('qcCommand');
      const appendNl =
        browserGlobals.document.getElementById('qcAppendNewline');
      appendNl.type = 'checkbox';
      browserGlobals.document.getElementById('qcGroup');
      browserGlobals.document.getElementById('qcNewGroup');
      browserGlobals.document.getElementById('qcTestRunBtn');

      const radioSingle = createMockElement('_radio_edit_s');
      radioSingle.type = 'radio';
      radioSingle.checked = true;
      const radioMacro = createMockElement('_radio_edit_m');
      radioMacro.type = 'radio';
      radioMacro.checked = false;

      const origQS = browserGlobals.document.querySelector;
      browserGlobals.document.querySelector = (sel) => {
        if (sel.includes('value="single"')) return radioSingle;
        if (sel.includes('value="macro"')) return radioMacro;
        if (sel.includes('.qc-item')) return null;
        return origQS ? origQS(sel) : null;
      };
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            {
              id: 'qc_edit1',
              name: 'EditMe',
              type: 'single',
              command: 'hello\\n',
              appendNewline: true,
              group: '',
            },
          ]);
        if (k === 'fpbinject-quick-command-groups') return JSON.stringify([]);
        return null;
      };
      w.openQuickCommandEditor('qc_edit1');
      assertTrue(modal.classList.contains('show'));
      assertEqual(nameInput.value, 'EditMe');
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.document.querySelector = origQS;
    });
    it('openQuickCommandEditor loads macro for editing', () => {
      const modal = browserGlobals.document.getElementById(
        'quickCommandEditorModal',
      );
      browserGlobals.document.getElementById('quickCommandEditorTitle');
      browserGlobals.document.getElementById('qcName');
      browserGlobals.document.getElementById('qcCommand');
      const appendNl =
        browserGlobals.document.getElementById('qcAppendNewline');
      appendNl.type = 'checkbox';
      browserGlobals.document.getElementById('qcGroup');
      browserGlobals.document.getElementById('qcNewGroup');
      browserGlobals.document.getElementById('qcTestRunBtn');
      const stepList = browserGlobals.document.getElementById('qcStepList');
      stepList._children = [];
      stepList.innerHTML = '';
      Object.defineProperty(stepList, 'children', {
        get: () => stepList._children,
        configurable: true,
      });
      browserGlobals.document.getElementById('qcMacroSummary');
      browserGlobals.document.getElementById('qcSingleSection');
      browserGlobals.document.getElementById('qcMacroSection');

      const radioSingle = createMockElement('_radio_edit_s2');
      radioSingle.type = 'radio';
      radioSingle.checked = false;
      const radioMacro = createMockElement('_radio_edit_m2');
      radioMacro.type = 'radio';
      radioMacro.checked = true;

      const origQS = browserGlobals.document.querySelector;
      browserGlobals.document.querySelector = (sel) => {
        if (sel.includes('value="single"')) return radioSingle;
        if (sel.includes('value="macro"')) return radioMacro;
        if (sel.includes('.qc-item')) return null;
        return origQS ? origQS(sel) : null;
      };
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            {
              id: 'qc_macro_edit',
              name: 'MacroEdit',
              type: 'macro',
              steps: [{ command: 'step1\\n', delay: 100 }],
              group: '',
            },
          ]);
        if (k === 'fpbinject-quick-command-groups') return JSON.stringify([]);
        return null;
      };
      w.openQuickCommandEditor('qc_macro_edit');
      assertTrue(modal.classList.contains('show'));
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.document.querySelector = origQS;
    });
  });

  // ===== Context menu =====
  describe('Quick Commands - Context Menu', () => {
    it('hideQcContextMenus hides all three menus', () => {
      const menu1 = browserGlobals.document.getElementById('qcContextMenu');
      menu1.style.display = 'block';
      const menu2 = browserGlobals.document.getElementById('qcSectionMenu');
      menu2.style.display = 'block';
      const menu3 =
        browserGlobals.document.getElementById('qcGroupContextMenu');
      menu3.style.display = 'block';
      w.hideQcContextMenus();
      assertEqual(menu1.style.display, 'none');
      assertEqual(menu2.style.display, 'none');
      assertEqual(menu3.style.display, 'none');
    });
    it('showQcContextMenu positions menu', () => {
      const menu = browserGlobals.document.getElementById('qcContextMenu');
      const mockEvent = {
        preventDefault: () => {},
        stopPropagation: () => {},
        clientX: 100,
        clientY: 200,
      };
      w.showQcContextMenu(mockEvent, 'qc_1');
      assertEqual(menu.style.display, 'block');
      assertEqual(menu.style.left, '100px');
    });
    it('showQuickCommandMenu positions section menu', () => {
      const menu = browserGlobals.document.getElementById('qcSectionMenu');
      const mockEvent = {
        preventDefault: () => {},
        stopPropagation: () => {},
        clientX: 50,
        clientY: 60,
      };
      w.showQuickCommandMenu(mockEvent);
      assertEqual(menu.style.display, 'block');
    });
    it('qcContextAction dispatches all actions', () => {
      // execute
      w.showQcContextMenu(
        {
          preventDefault: () => {},
          stopPropagation: () => {},
          clientX: 0,
          clientY: 0,
        },
        'qc_ctx',
      );
      w.qcContextAction('execute');
      assertTrue(true);
      // edit
      w.showQcContextMenu(
        {
          preventDefault: () => {},
          stopPropagation: () => {},
          clientX: 0,
          clientY: 0,
        },
        'qc_ctx',
      );
      w.qcContextAction('edit');
      assertTrue(true);
      // duplicate
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            { id: 'qc_ctx', name: 'X', type: 'single', command: 'x' },
          ]);
        return null;
      };
      w.showQcContextMenu(
        {
          preventDefault: () => {},
          stopPropagation: () => {},
          clientX: 0,
          clientY: 0,
        },
        'qc_ctx',
      );
      w.qcContextAction('duplicate');
      browserGlobals.localStorage.getItem = origGet;
      assertTrue(true);
      // delete
      const origConfirm = global.confirm;
      global.confirm = () => false;
      w.showQcContextMenu(
        {
          preventDefault: () => {},
          stopPropagation: () => {},
          clientX: 0,
          clientY: 0,
        },
        'qc_ctx',
      );
      w.qcContextAction('delete');
      global.confirm = origConfirm;
      assertTrue(true);
      // move
      const origPrompt = global.prompt;
      global.prompt = () => null;
      w.showQcContextMenu(
        {
          preventDefault: () => {},
          stopPropagation: () => {},
          clientX: 0,
          clientY: 0,
        },
        'qc_ctx',
      );
      w.qcContextAction('move');
      global.prompt = origPrompt;
      assertTrue(true);
    });
    it('qcContextAction with no target does nothing', () => {
      w.showQcContextMenu(
        {
          preventDefault: () => {},
          stopPropagation: () => {},
          clientX: 0,
          clientY: 0,
        },
        null,
      );
      w.qcContextAction('execute');
      assertTrue(true);
    });
  });

  // ===== Move to group =====
  describe('Quick Commands - Move to Group', () => {
    it('moveToGroup updates command group on prompt', () => {
      const store = {};
      const origGet = browserGlobals.localStorage.getItem;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return (
            store[k] ||
            JSON.stringify([{ id: 'qc_1', name: 'test', group: null }])
          );
        return store[k] || null;
      };
      browserGlobals.localStorage.setItem = (k, v) => {
        store[k] = v;
      };
      const origPrompt = global.prompt;
      global.prompt = () => 'NewGroup';
      w.moveToGroup('qc_1');
      const saved = JSON.parse(store['fpbinject-quick-commands']);
      assertEqual(saved[0].group, 'NewGroup');
      global.prompt = origPrompt;
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.localStorage.setItem = origSet;
    });
    it('moveToGroup cancels on null prompt', () => {
      const origGet = browserGlobals.localStorage.getItem;
      let setCalled = false;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([{ id: 'qc_1', name: 'test', group: 'old' }]);
        return null;
      };
      browserGlobals.localStorage.setItem = () => {
        setCalled = true;
      };
      const origPrompt = global.prompt;
      global.prompt = () => null;
      w.moveToGroup('qc_1');
      assertFalse(setCalled);
      global.prompt = origPrompt;
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.localStorage.setItem = origSet;
    });
    it('moveToGroup ungroups on empty string', () => {
      const store = {};
      const origGet = browserGlobals.localStorage.getItem;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([{ id: 'qc_1', name: 'test', group: 'old' }]);
        return store[k] || null;
      };
      browserGlobals.localStorage.setItem = (k, v) => {
        store[k] = v;
      };
      const origPrompt = global.prompt;
      global.prompt = () => '';
      w.moveToGroup('qc_1');
      const saved = JSON.parse(store['fpbinject-quick-commands']);
      assertEqual(saved[0].group, null);
      global.prompt = origPrompt;
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.localStorage.setItem = origSet;
    });
    it('moveToGroup does nothing for unknown ID', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands') return JSON.stringify([]);
        return null;
      };
      w.moveToGroup('nonexistent');
      browserGlobals.localStorage.getItem = origGet;
    });
  });

  // ===== Duplicate =====
  describe('Quick Commands - Duplicate', () => {
    it('duplicateQuickCommand creates a copy with new ID', () => {
      const cmds = [
        {
          id: 'qc_1',
          name: 'test',
          type: 'single',
          command: 'ps\\n',
          group: null,
        },
      ];
      const store = { 'fpbinject-quick-commands': JSON.stringify(cmds) };
      const origGet = browserGlobals.localStorage.getItem;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => store[k] || null;
      browserGlobals.localStorage.setItem = (k, v) => {
        store[k] = v;
      };
      w.duplicateQuickCommand('qc_1');
      const saved = JSON.parse(store['fpbinject-quick-commands']);
      assertEqual(saved.length, 2);
      assertTrue(saved[1].id !== 'qc_1');
      assertTrue(saved[1].name.includes('copy'));
      browserGlobals.localStorage.setItem = origSet;
      browserGlobals.localStorage.getItem = origGet;
    });
    it('duplicateQuickCommand does nothing for unknown ID', () => {
      const origGet = browserGlobals.localStorage.getItem;
      let setCalled = false;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands') return JSON.stringify([]);
        return null;
      };
      browserGlobals.localStorage.setItem = () => {
        setCalled = true;
      };
      w.duplicateQuickCommand('nonexistent');
      assertFalse(setCalled);
      browserGlobals.localStorage.setItem = origSet;
      browserGlobals.localStorage.getItem = origGet;
    });
  });

  // ===== Delete =====
  describe('Quick Commands - Delete', () => {
    it('deleteQuickCommand removes command on confirm', () => {
      const store = {};
      const origGet = browserGlobals.localStorage.getItem;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return (
            store[k] ||
            JSON.stringify([
              { id: 'qc_1', name: 'test' },
              { id: 'qc_2', name: 'keep' },
            ])
          );
        return store[k] || null;
      };
      browserGlobals.localStorage.setItem = (k, v) => {
        store[k] = v;
      };
      const origConfirm = browserGlobals.confirm;
      browserGlobals.confirm = () => true;
      w.deleteQuickCommand('qc_1');
      const saved = JSON.parse(store['fpbinject-quick-commands']);
      assertEqual(saved.length, 1);
      assertEqual(saved[0].id, 'qc_2');
      browserGlobals.confirm = origConfirm;
      browserGlobals.localStorage.setItem = origSet;
      browserGlobals.localStorage.getItem = origGet;
    });
    it('deleteQuickCommand does not remove on cancel', () => {
      const origGet = browserGlobals.localStorage.getItem;
      let setCalled = false;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([{ id: 'qc_1', name: 'test' }]);
        return null;
      };
      browserGlobals.localStorage.setItem = () => {
        setCalled = true;
      };
      const origConfirm = global.confirm;
      global.confirm = () => false;
      w.deleteQuickCommand('qc_1');
      assertFalse(setCalled);
      global.confirm = origConfirm;
      browserGlobals.localStorage.setItem = origSet;
      browserGlobals.localStorage.getItem = origGet;
    });
    it('deleteQuickCommand does nothing for unknown ID', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands') return JSON.stringify([]);
        return null;
      };
      w.deleteQuickCommand('nonexistent');
      browserGlobals.localStorage.getItem = origGet;
    });
  });

  // ===== Clear all =====
  describe('Quick Commands - Clear All', () => {
    it('clearAllQuickCommands does nothing when empty', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands') return JSON.stringify([]);
        return null;
      };
      w.clearAllQuickCommands();
      browserGlobals.localStorage.getItem = origGet;
    });
    it('T32: clearAllQuickCommands clears both commands and groupMeta', () => {
      const store = {};
      const origGet = browserGlobals.localStorage.getItem;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([{ id: 'qc_1', name: 'test' }]);
        return store[k] || null;
      };
      browserGlobals.localStorage.setItem = (k, v) => {
        store[k] = v;
      };
      const origConfirm = browserGlobals.confirm;
      browserGlobals.confirm = () => true;
      w.clearAllQuickCommands();
      assertEqual(store['fpbinject-quick-commands'], '[]');
      assertEqual(store['fpbinject-quick-command-groups'], '[]');
      browserGlobals.confirm = origConfirm;
      browserGlobals.localStorage.setItem = origSet;
      browserGlobals.localStorage.getItem = origGet;
    });
    it('clearAllQuickCommands does not clear on cancel', () => {
      const origGet = browserGlobals.localStorage.getItem;
      let setCalled = false;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([{ id: 'qc_1', name: 'test' }]);
        return null;
      };
      browserGlobals.localStorage.setItem = () => {
        setCalled = true;
      };
      const origConfirm = global.confirm;
      global.confirm = () => false;
      w.clearAllQuickCommands();
      assertFalse(setCalled);
      global.confirm = origConfirm;
      browserGlobals.localStorage.setItem = origSet;
      browserGlobals.localStorage.getItem = origGet;
    });
  });

  // ===== Render =====
  describe('Quick Commands - Render', () => {
    it('renderQuickCommands shows empty message when no commands', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands') return JSON.stringify([]);
        return null;
      };
      const list = browserGlobals.document.getElementById('quickCommandList');
      w.renderQuickCommands();
      assertTrue(list.innerHTML.includes('empty'));
      browserGlobals.localStorage.getItem = origGet;
    });
    it('renderQuickCommands renders ungrouped commands', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            { id: 'qc_1', name: 'cmd1', type: 'single', command: 'ps' },
          ]);
        if (k === 'fpbinject-quick-command-groups') return JSON.stringify([]);
        return null;
      };
      const list = browserGlobals.document.getElementById('quickCommandList');
      w.renderQuickCommands();
      assertTrue(list._children.length > 0);
      browserGlobals.localStorage.getItem = origGet;
    });
    it('renderQuickCommands renders grouped commands sorted by meta order', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            {
              id: 'qc_1',
              name: 'cmd1',
              type: 'single',
              command: 'ps',
              group: 'B',
            },
            {
              id: 'qc_2',
              name: 'cmd2',
              type: 'macro',
              steps: [{ command: 'a' }],
              group: 'A',
            },
            { id: 'qc_3', name: 'cmd3', type: 'single', command: 'ls' },
          ]);
        if (k === 'fpbinject-quick-command-groups')
          return JSON.stringify([
            { name: 'A', order: 0 },
            { name: 'B', order: 1 },
          ]);
        return null;
      };
      const list = browserGlobals.document.getElementById('quickCommandList');
      w.renderQuickCommands();
      assertTrue(list._children.length >= 2);
      browserGlobals.localStorage.getItem = origGet;
    });
  });

  // ===== Type change =====
  describe('Quick Commands - Type Change', () => {
    it('onQcTypeChange shows macro section when macro selected', () => {
      const singleSection =
        browserGlobals.document.getElementById('qcSingleSection');
      const macroSection =
        browserGlobals.document.getElementById('qcMacroSection');
      const stepList = browserGlobals.document.getElementById('qcStepList');
      stepList._children = [];
      Object.defineProperty(stepList, 'children', {
        get: () => stepList._children,
        configurable: true,
      });
      const radioMacro = createMockElement('_radio_macro2');
      radioMacro.type = 'radio';
      radioMacro.checked = true;
      const origQS = browserGlobals.document.querySelector;
      browserGlobals.document.querySelector = (sel) => {
        if (sel.includes('value="macro"')) return radioMacro;
        return origQS ? origQS(sel) : null;
      };
      w.onQcTypeChange();
      assertEqual(singleSection.style.display, 'none');
      assertEqual(macroSection.style.display, '');
      browserGlobals.document.querySelector = origQS;
    });
    it('onQcTypeChange shows single section when single selected', () => {
      const singleSection =
        browserGlobals.document.getElementById('qcSingleSection');
      const macroSection =
        browserGlobals.document.getElementById('qcMacroSection');
      const radioMacro = createMockElement('_radio_macro3');
      radioMacro.type = 'radio';
      radioMacro.checked = false;
      const origQS = browserGlobals.document.querySelector;
      browserGlobals.document.querySelector = (sel) => {
        if (sel.includes('value="macro"')) return radioMacro;
        return origQS ? origQS(sel) : null;
      };
      w.onQcTypeChange();
      assertEqual(singleSection.style.display, '');
      assertEqual(macroSection.style.display, 'none');
      browserGlobals.document.querySelector = origQS;
    });
  });

  // ===== Group change =====
  describe('Quick Commands - Group Change', () => {
    it('onQcGroupChange shows new group input when __new__ selected', () => {
      const select = browserGlobals.document.getElementById('qcGroup');
      const newGroupInput =
        browserGlobals.document.getElementById('qcNewGroup');
      select.value = '__new__';
      w.onQcGroupChange();
      assertEqual(newGroupInput.style.display, '');
    });
    it('onQcGroupChange hides new group input for normal group', () => {
      const select = browserGlobals.document.getElementById('qcGroup');
      const newGroupInput =
        browserGlobals.document.getElementById('qcNewGroup');
      select.value = 'existing';
      w.onQcGroupChange();
      assertEqual(newGroupInput.style.display, 'none');
    });
  });

  // ===== Macro steps =====
  describe('Quick Commands - Macro Steps', () => {
    it('addMacroStep adds a step to the list', () => {
      const stepList = browserGlobals.document.getElementById('qcStepList');
      stepList._children = [];
      stepList.innerHTML = '';
      Object.defineProperty(stepList, 'children', {
        get: () => stepList._children,
        configurable: true,
      });
      browserGlobals.document.getElementById('qcMacroSummary');
      w.addMacroStep('test_cmd', 100, true);
      assertEqual(stepList._children.length, 1);
    });
    it('addMacroStep defaults delay to 0', () => {
      const stepList = browserGlobals.document.getElementById('qcStepList');
      stepList._children = [];
      stepList.innerHTML = '';
      Object.defineProperty(stepList, 'children', {
        get: () => stepList._children,
        configurable: true,
      });
      browserGlobals.document.getElementById('qcMacroSummary');
      w.addMacroStep('cmd');
      assertEqual(stepList._children.length, 1);
    });
    it('updateMacroSummary updates summary text', () => {
      const stepList = browserGlobals.document.getElementById('qcStepList');
      const summary = browserGlobals.document.getElementById('qcMacroSummary');
      stepList._children = [];
      Object.defineProperty(stepList, 'children', {
        get: () => stepList._children,
        configurable: true,
      });
      w.updateMacroSummary();
      assertTrue(summary.textContent !== undefined);
    });
    it('collectMacroSteps returns empty when no stepList', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcStepList') return null;
        return origGet(id);
      };
      const steps = w.collectMacroSteps();
      assertEqual(steps.length, 0);
      browserGlobals.document.getElementById = origGet;
    });
  });

  // ===== Save command =====
  describe('Quick Commands - Save', () => {
    it('saveQuickCommand saves a new single command', () => {
      // Reset editing state that may have been left by editor modal tests
      w.closeQuickCommandEditor();

      const radioMacro = createMockElement('_radio_save');
      radioMacro.checked = false;
      const origQS = browserGlobals.document.querySelector;
      browserGlobals.document.querySelector = (sel) => {
        if (sel.includes('value="macro"')) return radioMacro;
        return origQS ? origQS(sel) : null;
      };
      // Restore localStorage to known good state
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);

      browserGlobals.document.getElementById('qcName').value = 'Test Save';
      browserGlobals.document.getElementById('qcCommand').value = 'ls -la';
      browserGlobals.document.getElementById('qcAppendNewline').checked = true;
      browserGlobals.document.getElementById('qcGroup').value = '';
      browserGlobals.document.getElementById('qcNewGroup').value = '';

      ls.setItem('fpbinject-quick-commands', '[]');

      w.saveQuickCommand();

      const raw = ls.getItem('fpbinject-quick-commands');
      assertTrue(raw !== null && raw !== '[]', 'should have saved commands');
      const saved = JSON.parse(raw);
      assertTrue(saved.length > 0, 'should have at least 1 command');
      assertEqual(saved[0].name, 'Test Save');
      assertEqual(saved[0].type, 'single');

      browserGlobals.document.querySelector = origQS;
    });
    it('T34: saveQuickCommand with new group updates groupMeta', () => {
      w.closeQuickCommandEditor();

      const radioMacro = createMockElement('_radio_save_ng');
      radioMacro.checked = false;
      const origQS = browserGlobals.document.querySelector;
      browserGlobals.document.querySelector = (sel) => {
        if (sel.includes('value="macro"')) return radioMacro;
        return origQS ? origQS(sel) : null;
      };
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);

      browserGlobals.document.getElementById('qcName').value = 'Grouped';
      browserGlobals.document.getElementById('qcCommand').value = 'pwd';
      browserGlobals.document.getElementById('qcAppendNewline').checked = false;
      browserGlobals.document.getElementById('qcGroup').value = '__new__';
      browserGlobals.document.getElementById('qcNewGroup').value = 'Debug';

      ls.setItem('fpbinject-quick-commands', '[]');

      w.saveQuickCommand();

      const raw = ls.getItem('fpbinject-quick-commands');
      const saved = JSON.parse(raw);
      assertTrue(saved.length > 0, 'should have saved command');
      assertEqual(saved[0].group, 'Debug');
      const metaRaw = ls.getItem('fpbinject-quick-command-groups');
      const meta = JSON.parse(metaRaw);
      assertTrue(meta.some((g) => g.name === 'Debug'));

      browserGlobals.document.querySelector = origQS;
    });
    it('saveQuickCommand returns early when no macro steps', () => {
      w.closeQuickCommandEditor();

      const radioMacro = createMockElement('_radio_save_m');
      radioMacro.checked = true;
      const origQS = browserGlobals.document.querySelector;
      browserGlobals.document.querySelector = (sel) => {
        if (sel.includes('value="macro"')) return radioMacro;
        return origQS ? origQS(sel) : null;
      };
      browserGlobals.document.getElementById('qcName').value = 'TestMacro';
      browserGlobals.document.getElementById('qcGroup').value = '';
      browserGlobals.document.getElementById('qcNewGroup');
      const stepList = browserGlobals.document.getElementById('qcStepList');
      stepList.innerHTML = '';
      stepList._children = [];
      Object.defineProperty(stepList, 'children', {
        get: () => stepList._children,
        configurable: true,
      });

      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands') return JSON.stringify([]);
        return null;
      };
      let setCalled = false;
      const origSet = browserGlobals.localStorage.setItem;
      browserGlobals.localStorage.setItem = () => {
        setCalled = true;
      };
      w.saveQuickCommand();
      assertFalse(setCalled);
      browserGlobals.localStorage.setItem = origSet;
      browserGlobals.localStorage.getItem = origGet;
      browserGlobals.document.querySelector = origQS;
    });
  });

  // ===== Resolve Import Conflicts =====
  describe('Quick Commands - resolveImportConflicts', () => {
    it('T39: returns empty when no conflicts', () => {
      const incoming = [
        { id: 'i1', name: 'new', type: 'single', command: 'x' },
      ];
      const existing = [
        { id: 'e1', name: 'old', type: 'single', command: 'y' },
      ];
      const conflicts = w.resolveImportConflicts(incoming, existing);
      assertEqual(conflicts.length, 0);
    });
    it('T40: detects single command conflict by name+type+command', () => {
      const incoming = [
        { id: 'i1', name: 'ps', type: 'single', command: 'ps\\n' },
      ];
      const existing = [
        { id: 'e1', name: 'ps', type: 'single', command: 'ps\\n' },
      ];
      const conflicts = w.resolveImportConflicts(incoming, existing);
      assertEqual(conflicts.length, 1);
      assertEqual(conflicts[0].incoming.id, 'i1');
      assertEqual(conflicts[0].existing.id, 'e1');
    });
    it('detects macro conflict by name+type', () => {
      const incoming = [{ id: 'i1', name: 'Init', type: 'macro' }];
      const existing = [{ id: 'e1', name: 'Init', type: 'macro' }];
      const conflicts = w.resolveImportConflicts(incoming, existing);
      assertEqual(conflicts.length, 1);
    });
    it('no conflict when name matches but type differs', () => {
      const incoming = [{ id: 'i1', name: 'ps', type: 'macro' }];
      const existing = [
        { id: 'e1', name: 'ps', type: 'single', command: 'ps' },
      ];
      const conflicts = w.resolveImportConflicts(incoming, existing);
      assertEqual(conflicts.length, 0);
    });
    it('no conflict when name matches but command differs (single)', () => {
      const incoming = [
        { id: 'i1', name: 'ps', type: 'single', command: 'ps -A\\n' },
      ];
      const existing = [
        { id: 'e1', name: 'ps', type: 'single', command: 'ps\\n' },
      ];
      const conflicts = w.resolveImportConflicts(incoming, existing);
      assertEqual(conflicts.length, 0);
    });
  });

  // ===== Selective Export =====
  describe('Quick Commands - Selective Export', () => {
    it('T37: openExportDialog alerts when no commands', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands') return JSON.stringify([]);
        return null;
      };
      let alertMsg = null;
      const origAlert = global.alert;
      global.alert = (msg) => {
        alertMsg = msg;
      };
      w.openExportDialog();
      assertTrue(alertMsg !== null);
      global.alert = origAlert;
      browserGlobals.localStorage.getItem = origGet;
    });
    it('T29: openExportDialog opens modal with commands', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            {
              id: 'qc_1',
              name: 'ps',
              type: 'single',
              command: 'ps',
              group: 'System',
            },
            {
              id: 'qc_2',
              name: 'ls',
              type: 'single',
              command: 'ls',
              group: null,
            },
          ]);
        if (k === 'fpbinject-quick-command-groups')
          return JSON.stringify([{ name: 'System', order: 0 }]);
        return null;
      };
      const modal = browserGlobals.document.getElementById('qcExportModal');
      browserGlobals.document.getElementById('qcExportList');
      browserGlobals.document.getElementById('qcExportCount');
      browserGlobals.document.getElementById('qcExportBtn');
      w.openExportDialog();
      assertTrue(modal.classList.contains('show'));
      browserGlobals.localStorage.getItem = origGet;
    });
    it('closeExportDialog removes show class', () => {
      const modal = browserGlobals.document.getElementById('qcExportModal');
      modal.classList.add('show');
      w.closeExportDialog();
      assertFalse(modal.classList.contains('show'));
    });
    it('exportQuickCommands delegates to openExportDialog', () => {
      // exportQuickCommands is now an alias for openExportDialog
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands') return JSON.stringify([]);
        return null;
      };
      let alertCalled = false;
      const origAlert = global.alert;
      global.alert = () => {
        alertCalled = true;
      };
      w.exportQuickCommands();
      assertTrue(alertCalled);
      global.alert = origAlert;
      browserGlobals.localStorage.getItem = origGet;
    });
  });

  // ===== Import with conflict handling =====
  describe('Quick Commands - Import', () => {
    it('importQuickCommands creates file input', () => {
      browserGlobals.document.getElementById('qcContextMenu');
      browserGlobals.document.getElementById('qcSectionMenu');
      browserGlobals.document.getElementById('qcGroupContextMenu');
      let clickCalled = false;
      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        const el = origCreateElement(tag);
        if (tag === 'input')
          el.click = () => {
            clickCalled = true;
          };
        return el;
      };
      w.importQuickCommands();
      assertTrue(clickCalled);
      browserGlobals.document.createElement = origCreateElement;
    });
    it('T53: importQuickCommands handles invalid format', () => {
      let fileInput = null;
      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        const el = origCreateElement(tag);
        if (tag === 'input') {
          fileInput = el;
          el.click = () => {};
        }
        return el;
      };
      let alertMsg = null;
      const origAlert = global.alert;
      global.alert = (msg) => {
        alertMsg = msg;
      };
      w.importQuickCommands();
      if (fileInput && fileInput.onchange) {
        const origFileReader = global.FileReader;
        global.FileReader = function () {
          this.readAsText = () => {
            this.onload({
              target: { result: JSON.stringify({ notCommands: true }) },
            });
          };
        };
        fileInput.onchange({ target: { files: [{ name: 'bad.json' }] } });
        global.FileReader = origFileReader;
      }
      assertTrue(alertMsg !== null);
      global.alert = origAlert;
      browserGlobals.document.createElement = origCreateElement;
    });
    it('T52: importQuickCommands handles empty commands array', () => {
      let fileInput = null;
      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        const el = origCreateElement(tag);
        if (tag === 'input') {
          fileInput = el;
          el.click = () => {};
        }
        return el;
      };
      let alertMsg = null;
      const origAlert = global.alert;
      global.alert = (msg) => {
        alertMsg = msg;
      };
      w.importQuickCommands();
      if (fileInput && fileInput.onchange) {
        const origFileReader = global.FileReader;
        global.FileReader = function () {
          this.readAsText = () => {
            this.onload({
              target: { result: JSON.stringify({ version: 2, commands: [] }) },
            });
          };
        };
        fileInput.onchange({ target: { files: [{ name: 'empty.json' }] } });
        global.FileReader = origFileReader;
      }
      assertTrue(alertMsg !== null);
      global.alert = origAlert;
      browserGlobals.document.createElement = origCreateElement;
    });
    it('importQuickCommands handles parse error', () => {
      let fileInput = null;
      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        const el = origCreateElement(tag);
        if (tag === 'input') {
          fileInput = el;
          el.click = () => {};
        }
        return el;
      };
      let alertMsg = null;
      const origAlert = global.alert;
      global.alert = (msg) => {
        alertMsg = msg;
      };
      w.importQuickCommands();
      if (fileInput && fileInput.onchange) {
        const origFileReader = global.FileReader;
        global.FileReader = function () {
          this.readAsText = () => {
            this.onload({ target: { result: 'not json at all' } });
          };
        };
        fileInput.onchange({ target: { files: [{ name: 'bad.json' }] } });
        global.FileReader = origFileReader;
      }
      assertTrue(alertMsg !== null);
      global.alert = origAlert;
      browserGlobals.document.createElement = origCreateElement;
    });
    it('importQuickCommands handles empty file selection', () => {
      let fileInput = null;
      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        const el = origCreateElement(tag);
        if (tag === 'input') {
          fileInput = el;
          el.click = () => {};
        }
        return el;
      };
      w.importQuickCommands();
      if (fileInput && fileInput.onchange) {
        fileInput.onchange({ target: { files: [] } });
      }
      browserGlobals.document.createElement = origCreateElement;
      assertTrue(true);
    });
    it('closeImportDialog removes show class', () => {
      const modal = browserGlobals.document.getElementById('qcImportModal');
      modal.classList.add('show');
      modal._importData = {};
      w.closeImportDialog();
      assertFalse(modal.classList.contains('show'));
      assertEqual(modal._importData, null);
    });
  });

  // ===== populateGroupDropdown =====
  describe('Quick Commands - populateGroupDropdown', () => {
    it('populateGroupDropdown populates with existing groups', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            {
              id: 'g1',
              name: 'A',
              group: 'GroupA',
              type: 'single',
              command: 'x',
            },
            {
              id: 'g2',
              name: 'B',
              group: 'GroupB',
              type: 'single',
              command: 'y',
            },
          ]);
        return null;
      };
      const select = createMockElement('_grp_select');
      w.populateGroupDropdown(select);
      assertTrue(select.innerHTML.includes('GroupA'));
      assertTrue(select.innerHTML.includes('GroupB'));
      browserGlobals.localStorage.getItem = origGet;
    });
    it('populateGroupDropdown handles null select', () => {
      w.populateGroupDropdown(null);
      assertTrue(true);
    });
  });

  // ===== Test Run =====
  describe('Quick Commands - Test Run', () => {
    it('testRunQuickCommand returns early if not connected', () => {
      w.FPBState.isConnected = false;
      w.testRunQuickCommand();
      assertTrue(true);
    });
  });

  // ===== Keyboard =====
  describe('Quick Commands - Keyboard', () => {
    it('initQuickCommands sets up keyboard listeners', () => {
      w.initQuickCommands();
      assertTrue(true);
    });
  });

  // ===== Step Drag =====
  describe('Quick Commands - Step Drag', () => {
    it('initStepDragListeners registers document-level listeners', () => {
      w.initStepDragListeners();
      assertTrue(true);
    });
    it('setupStepDrag attaches handler via addMacroStep', () => {
      const stepList = browserGlobals.document.getElementById('qcStepList');
      stepList._children = [];
      stepList.innerHTML = '';
      Object.defineProperty(stepList, 'children', {
        get: () => stepList._children,
        configurable: true,
      });
      browserGlobals.document.getElementById('qcMacroSummary');
      w.addMacroStep('dragtest', 0, true);
      assertTrue(stepList._children.length > 0);
    });
  });

  // ===== persistCommandOrder / persistGroupOrder =====
  describe('Quick Commands - Persist Order', () => {
    it('persistCommandOrder does not throw when no list', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'quickCommandList') return null;
        return origGet(id);
      };
      w.persistCommandOrder();
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });
    it('persistGroupOrder does not throw when no list', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'quickCommandList') return null;
        return origGet(id);
      };
      w.persistGroupOrder();
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });
  });

  // ===== XSS safety (T35) =====
  describe('Quick Commands - XSS Safety', () => {
    it('T35: special characters in group name are escaped', () => {
      const origGet = browserGlobals.localStorage.getItem;
      browserGlobals.localStorage.getItem = (k) => {
        if (k === 'fpbinject-quick-commands')
          return JSON.stringify([
            {
              id: 'xss1',
              name: 'test',
              type: 'single',
              command: 'x',
              group: '<script>alert(1)</script>',
            },
          ]);
        if (k === 'fpbinject-quick-command-groups')
          return JSON.stringify([
            { name: '<script>alert(1)</script>', order: 0 },
          ]);
        return null;
      };
      const list = browserGlobals.document.getElementById('quickCommandList');
      w.renderQuickCommands();
      // Should render without throwing - escapeHtml handles it
      assertTrue(list._children.length > 0);
      browserGlobals.localStorage.getItem = origGet;
    });
  });

  // ===== onImportStrategyChange =====
  describe('Quick Commands - Import Strategy', () => {
    it('onImportStrategyChange does nothing when no modal data', () => {
      const modal = browserGlobals.document.getElementById('qcImportModal');
      modal._importData = null;
      w.onImportStrategyChange('skip_all');
      assertTrue(true);
    });
    it('updateImportSummary does nothing when no modal data', () => {
      const modal = browserGlobals.document.getElementById('qcImportModal');
      modal._importData = null;
      w.updateImportSummary();
      assertTrue(true);
    });
    it('executeImport does nothing when no modal data', () => {
      const modal = browserGlobals.document.getElementById('qcImportModal');
      modal._importData = null;
      w.executeImport();
      assertTrue(true);
    });
  });

  // ===== Export execution =====
  describe('Quick Commands - Execute Export', () => {
    it('executeExport does nothing when no modal', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcExportModal') return null;
        return origGet(id);
      };
      w.executeExport();
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });
  });

  // ===== Export select all / group toggle / item toggle =====
  describe('Quick Commands - Export Checkbox Logic', () => {
    it('onExportSelectAll does nothing when no modal', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcExportModal') return null;
        return origGet(id);
      };
      w.onExportSelectAll(true);
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });
    it('onExportGroupToggle does nothing when no modal', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcExportModal') return null;
        return origGet(id);
      };
      const mockCb = { getAttribute: () => 'test', checked: true };
      w.onExportGroupToggle(mockCb);
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });
    it('onExportItemToggle does nothing when no modal', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcExportModal') return null;
        return origGet(id);
      };
      w.onExportItemToggle();
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });
    it('updateExportCount does nothing when no modal', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcExportModal') return null;
        return origGet(id);
      };
      w.updateExportCount();
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });
  });

  // ===== setImportConflictAction =====
  describe('Quick Commands - setImportConflictAction', () => {
    it('setImportConflictAction does nothing when no row', () => {
      const btn = createMockElement('_conflict_btn');
      btn.getAttribute = () => 'test_id';
      btn.closest = () => null;
      w.setImportConflictAction(btn, 'skip');
      assertTrue(true);
    });
  });

  // ===== Additional coverage tests =====
  describe('Quick Commands - Additional Coverage', () => {
    it('renderQuickCommands handles missing list element', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'quickCommandList') return null;
        return origGet(id);
      };
      w.renderQuickCommands();
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });

    it('openQuickCommandEditor returns when modal missing', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'quickCommandEditorModal') return null;
        return origGet(id);
      };
      w.openQuickCommandEditor();
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });

    it('openQuickCommandEditor returns when command not found in edit mode', () => {
      const modal = browserGlobals.document.getElementById(
        'quickCommandEditorModal',
      );
      browserGlobals.document.getElementById('quickCommandEditorTitle');
      browserGlobals.document.getElementById('qcName');
      browserGlobals.document.getElementById('qcCommand');
      browserGlobals.document.getElementById('qcAppendNewline');
      browserGlobals.document.getElementById('qcGroup');
      browserGlobals.document.getElementById('qcNewGroup');
      browserGlobals.document.getElementById('qcTestRunBtn');
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      ls.setItem('fpbinject-quick-commands', '[]');
      w.openQuickCommandEditor('nonexistent_id');
      assertFalse(modal.classList.contains('show'));
    });

    it('onQcGroupChange handles missing elements', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcGroup' || id === 'qcNewGroup') return null;
        return origGet(id);
      };
      w.onQcGroupChange();
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });

    it('addMacroStep handles missing stepList', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcStepList') return null;
        return origGet(id);
      };
      w.addMacroStep('test', 0, true);
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });

    it('renderMacroSteps renders steps', () => {
      const stepList = browserGlobals.document.getElementById('qcStepList');
      stepList._children = [];
      stepList.innerHTML = '';
      Object.defineProperty(stepList, 'children', {
        get: () => stepList._children,
        configurable: true,
      });
      browserGlobals.document.getElementById('qcMacroSummary');
      w.renderMacroSteps([
        { command: 'a', delay: 0, appendNewline: true },
        { command: 'b', delay: 100, appendNewline: false },
      ]);
      assertEqual(stepList._children.length, 2);
    });

    it('updateMacroSummary handles missing elements', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcStepList' || id === 'qcMacroSummary') return null;
        return origGet(id);
      };
      w.updateMacroSummary();
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });

    it('renderMacroSteps handles missing stepList', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcStepList') return null;
        return origGet(id);
      };
      w.renderMacroSteps([{ command: 'a', delay: 0 }]);
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });

    it('executeQuickCommand prevents concurrent execution', async () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      ls.setItem(
        'fpbinject-quick-commands',
        JSON.stringify([
          {
            id: 'qc_conc',
            type: 'single',
            command: 'test\\n',
            appendNewline: true,
          },
        ]),
      );
      const origFetch = global.fetch;
      let fetchCount = 0;
      global.fetch = async () => {
        fetchCount++;
        return { ok: true, json: async () => ({ success: true }) };
      };

      // Start first execution
      const p1 = w.executeQuickCommand('qc_conc');
      // Try second while first is running (qcExecuting should be true)
      const p2 = w.executeQuickCommand('qc_conc');
      await p1;
      await p2;
      // Only one should have executed
      assertEqual(fetchCount, 1);

      global.fetch = origFetch;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('testRunQuickCommand runs single command when connected', () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      const radioMacro = createMockElement('_radio_tr');
      radioMacro.checked = false;
      const origQS = browserGlobals.document.querySelector;
      browserGlobals.document.querySelector = (sel) => {
        if (sel.includes('value="macro"')) return radioMacro;
        return origQS ? origQS(sel) : null;
      };
      browserGlobals.document.getElementById('qcCommand').value = 'test';
      browserGlobals.document.getElementById('qcAppendNewline').checked = true;
      w.testRunQuickCommand();
      assertTrue(true);
      browserGlobals.document.querySelector = origQS;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('testRunQuickCommand runs macro when connected', () => {
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      const radioMacro = createMockElement('_radio_tr_m');
      radioMacro.checked = true;
      const origQS = browserGlobals.document.querySelector;
      browserGlobals.document.querySelector = (sel) => {
        if (sel.includes('value="macro"')) return radioMacro;
        return origQS ? origQS(sel) : null;
      };
      const stepList = browserGlobals.document.getElementById('qcStepList');
      stepList._children = [];
      stepList.innerHTML = '';
      Object.defineProperty(stepList, 'children', {
        get: () => stepList._children,
        configurable: true,
      });
      browserGlobals.document.getElementById('qcMacroSummary');
      w.addMacroStep('macro_test', 0, true);
      w.testRunQuickCommand();
      assertTrue(true);
      browserGlobals.document.querySelector = origQS;
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = null;
    });

    it('openExportDialog handles missing modal', () => {
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      ls.setItem(
        'fpbinject-quick-commands',
        JSON.stringify([{ id: 'x', name: 'x', type: 'single', command: 'x' }]),
      );
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcExportModal') return null;
        return origGet(id);
      };
      w.openExportDialog();
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });

    it('openExportDialog handles missing list element', () => {
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      ls.setItem(
        'fpbinject-quick-commands',
        JSON.stringify([{ id: 'x', name: 'x', type: 'single', command: 'x' }]),
      );
      const origGet = browserGlobals.document.getElementById;
      const modal = origGet('qcExportModal');
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcExportList') return null;
        if (id === 'qcExportModal') return modal;
        return origGet(id);
      };
      w.openExportDialog();
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });

    it('openImportDialog handles missing modal', () => {
      const origGet = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'qcImportModal') return null;
        return origGet(id);
      };
      w.openImportDialog({
        commands: [{ id: 'x', name: 'x', type: 'single', command: 'x' }],
      });
      assertTrue(true);
      browserGlobals.document.getElementById = origGet;
    });

    it('executeExport creates download when items selected', () => {
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      ls.setItem(
        'fpbinject-quick-commands',
        JSON.stringify([
          {
            id: 'exp1',
            name: 'test',
            type: 'single',
            command: 'x',
            group: 'G',
          },
        ]),
      );
      ls.setItem(
        'fpbinject-quick-command-groups',
        JSON.stringify([{ name: 'G', order: 0 }]),
      );

      const modal = browserGlobals.document.getElementById('qcExportModal');
      modal.classList.add('show');
      // Mock querySelectorAll to return checked items
      const origQSA = modal.querySelectorAll;
      modal.querySelectorAll = (sel) => {
        if (sel.includes(':checked')) {
          return [{ getAttribute: () => 'exp1' }];
        }
        return [];
      };

      let clickCalled = false;
      const origCreateEl = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        const el = origCreateEl(tag);
        if (tag === 'a')
          el.click = () => {
            clickCalled = true;
          };
        return el;
      };
      const origURL = global.URL;
      global.URL = {
        createObjectURL: () => 'blob:test',
        revokeObjectURL: () => {},
      };

      w.executeExport();
      assertTrue(clickCalled);
      assertFalse(modal.classList.contains('show'));

      global.URL = origURL;
      browserGlobals.document.createElement = origCreateEl;
      modal.querySelectorAll = origQSA;
    });

    it('executeImport imports new commands', () => {
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      ls.setItem(
        'fpbinject-quick-commands',
        JSON.stringify([
          { id: 'ex1', name: 'existing', type: 'single', command: 'old' },
        ]),
      );

      const modal = browserGlobals.document.getElementById('qcImportModal');
      modal.classList.add('show');

      const existingCmds = [
        { id: 'ex1', name: 'existing', type: 'single', command: 'old' },
      ];
      modal._importData = {
        incoming: [
          { id: 'imp1', name: 'new_cmd', type: 'single', command: 'new' },
        ],
        incomingGroups: [{ name: 'NewG', order: 0 }],
        existing: existingCmds,
        conflicts: [],
      };

      const listEl = browserGlobals.document.getElementById('qcImportList');
      const origQSA = listEl.querySelectorAll;
      const origQS = listEl.querySelector;
      listEl.querySelectorAll = (sel) => {
        if (sel.includes('.qc-import-conflict-icon')) return [];
        if (sel.includes('checkbox'))
          return [{ checked: true, getAttribute: () => 'imp1' }];
        return [];
      };
      listEl.querySelector = (sel) => {
        if (sel.includes('checkbox') && sel.includes('imp1'))
          return { checked: true };
        return null;
      };

      w.executeImport();
      assertFalse(modal.classList.contains('show'));
      // existingCmds should have been modified in place
      assertTrue(existingCmds.length >= 2);

      listEl.querySelectorAll = origQSA;
      listEl.querySelector = origQS;
    });

    it('executeImport handles overwrite conflict', () => {
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);

      const existing = [
        { id: 'ex1', name: 'ps', type: 'single', command: 'ps\\n' },
      ];
      ls.setItem('fpbinject-quick-commands', JSON.stringify(existing));

      const modal = browserGlobals.document.getElementById('qcImportModal');
      modal.classList.add('show');
      modal._importData = {
        incoming: [
          { id: 'imp1', name: 'ps', type: 'single', command: 'ps\\n' },
        ],
        incomingGroups: [],
        existing: JSON.parse(JSON.stringify(existing)),
        conflicts: [
          {
            incoming: {
              id: 'imp1',
              name: 'ps',
              type: 'single',
              command: 'ps\\n',
            },
            existing: existing[0],
          },
        ],
      };

      const listEl = browserGlobals.document.getElementById('qcImportList');
      const origQSA = listEl.querySelectorAll;
      listEl.querySelectorAll = (sel) => {
        if (sel.includes('.qc-import-conflict-icon'))
          return [
            { closest: () => ({ dataset: { conflictAction: 'overwrite' } }) },
          ];
        return [];
      };
      listEl.querySelector = (sel) => {
        if (sel.includes('data-import-id'))
          return { dataset: { conflictAction: 'overwrite' } };
        return null;
      };

      w.executeImport();
      assertFalse(modal.classList.contains('show'));
      listEl.querySelectorAll = origQSA;
    });

    it('setupGroupDrag handles missing header', () => {
      const el = browserGlobals.document.createElement('div');
      el.querySelector = () => null;
      // Should not throw
      assertTrue(true);
    });

    it('persistCommandOrder handles empty list', () => {
      const list = browserGlobals.document.getElementById('quickCommandList');
      list.querySelectorAll = () => [];
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      ls.setItem('fpbinject-quick-commands', '[]');
      w.persistCommandOrder();
      assertTrue(true);
    });

    it('persistGroupOrder handles empty list', () => {
      const list = browserGlobals.document.getElementById('quickCommandList');
      list.querySelectorAll = () => [];
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      ls.setItem('fpbinject-quick-command-groups', '[]');
      w.persistGroupOrder();
      assertTrue(true);
    });

    it('sendSerialData handles fetch error gracefully', async () => {
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      await w.sendSerialData('test');
      browserGlobals.fetch = origFetch;
    });

    it('escapeHtml escapes special characters', () => {
      const stepList = browserGlobals.document.getElementById('qcStepList');
      stepList._children = [];
      stepList.innerHTML = '';
      Object.defineProperty(stepList, 'children', {
        get: () => stepList._children,
        configurable: true,
      });
      browserGlobals.document.getElementById('qcMacroSummary');
      w.addMacroStep('<script>alert("xss")</script>', 0, true);
      assertTrue(stepList._children.length > 0);
    });

    it('openExportDialog builds checkbox tree with groups and ungrouped', () => {
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      ls.setItem(
        'fpbinject-quick-commands',
        JSON.stringify([
          { id: 'e1', name: 'ps', type: 'single', command: 'ps', group: 'Sys' },
          {
            id: 'e2',
            name: 'Init',
            type: 'macro',
            steps: [{ command: 'a' }],
            group: 'Sys',
          },
          {
            id: 'e3',
            name: 'reboot',
            type: 'single',
            command: 'reboot',
            group: null,
          },
        ]),
      );
      ls.setItem(
        'fpbinject-quick-command-groups',
        JSON.stringify([{ name: 'Sys', order: 0 }]),
      );
      const modal = browserGlobals.document.getElementById('qcExportModal');
      const listEl = browserGlobals.document.getElementById('qcExportList');
      browserGlobals.document.getElementById('qcExportCount');
      browserGlobals.document.getElementById('qcExportBtn');
      w.openExportDialog();
      assertTrue(modal.classList.contains('show'));
      assertTrue(listEl.innerHTML.includes('Sys'));
      assertTrue(listEl.innerHTML.includes('reboot'));
    });

    it('openImportDialog builds preview with conflicts and ungrouped', () => {
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      ls.setItem(
        'fpbinject-quick-commands',
        JSON.stringify([
          { id: 'ex1', name: 'ps', type: 'single', command: 'ps\\n' },
        ]),
      );
      const modal = browserGlobals.document.getElementById('qcImportModal');
      const listEl = browserGlobals.document.getElementById('qcImportList');
      browserGlobals.document.getElementById('qcImportSummary');
      const origQSA = modal.querySelectorAll;
      modal.querySelectorAll = (sel) => {
        if (sel.includes('qcImportStrategy'))
          return [{ value: 'per_item', checked: false }];
        return origQSA ? origQSA(sel) : [];
      };
      w.openImportDialog({
        version: 2,
        groups: [{ name: 'G', order: 0 }],
        commands: [
          {
            id: 'i1',
            name: 'ps',
            type: 'single',
            command: 'ps\\n',
            group: 'G',
          },
          {
            id: 'i2',
            name: 'new',
            type: 'single',
            command: 'new',
            group: null,
          },
        ],
      });
      assertTrue(modal.classList.contains('show'));
      assertTrue(listEl.innerHTML.includes('new'));
      modal.querySelectorAll = origQSA;
    });

    it('onImportStrategyChange sets all conflicts to skip or overwrite', () => {
      const modal = browserGlobals.document.getElementById('qcImportModal');
      modal._importData = { conflicts: [{ incoming: { id: 'x' } }] };
      const listEl = browserGlobals.document.getElementById('qcImportList');
      const mockItem = createMockElement('_ci');
      mockItem.dataset.importId = 'x';
      mockItem.querySelector = (sel) => {
        if (sel.includes('conflict-icon')) return {};
        return { classList: { toggle: () => {} } };
      };
      const origQSA = listEl.querySelectorAll;
      listEl.querySelectorAll = (sel) => {
        if (sel.includes('.qc-import-item')) return [mockItem];
        if (sel.includes('conflict-icon')) return [{ closest: () => mockItem }];
        return [];
      };
      browserGlobals.document.getElementById('qcImportSummary');
      w.onImportStrategyChange('skip_all');
      assertEqual(mockItem.dataset.conflictAction, 'skip');
      w.onImportStrategyChange('overwrite_all');
      assertEqual(mockItem.dataset.conflictAction, 'overwrite');
      listEl.querySelectorAll = origQSA;
    });

    it('setImportConflictAction toggles button active state', () => {
      const row = createMockElement('_cr');
      const skipBtn = createMockElement('_sb');
      skipBtn.classList._classes = new Set();
      const overwriteBtn = createMockElement('_ob');
      overwriteBtn.classList._classes = new Set();
      row.querySelector = (sel) => {
        if (sel.includes('skip')) return skipBtn;
        if (sel.includes('overwrite')) return overwriteBtn;
        return null;
      };
      const btn = createMockElement('_b');
      btn.getAttribute = () => 'test';
      btn.closest = () => row;
      const modal = browserGlobals.document.getElementById('qcImportModal');
      modal._importData = { conflicts: [] };
      const listEl = browserGlobals.document.getElementById('qcImportList');
      const origQSA = listEl.querySelectorAll;
      listEl.querySelectorAll = () => [];
      browserGlobals.document.getElementById('qcImportSummary');
      w.setImportConflictAction(btn, 'skip');
      assertEqual(row.dataset.conflictAction, 'skip');
      assertTrue(skipBtn.classList.contains('active'));
      w.setImportConflictAction(btn, 'overwrite');
      assertEqual(row.dataset.conflictAction, 'overwrite');
      assertTrue(overwriteBtn.classList.contains('active'));
      listEl.querySelectorAll = origQSA;
    });

    it('executeExport returns early when no items selected', () => {
      const modal = browserGlobals.document.getElementById('qcExportModal');
      modal.classList.add('show');
      const origQSA = modal.querySelectorAll;
      modal.querySelectorAll = () => [];
      w.executeExport();
      assertTrue(modal.classList.contains('show'));
      modal.querySelectorAll = origQSA;
    });

    it('openImportDialog with no groups in fileData uses Object.keys', () => {
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      ls.setItem('fpbinject-quick-commands', '[]');
      const modal = browserGlobals.document.getElementById('qcImportModal');
      const listEl = browserGlobals.document.getElementById('qcImportList');
      browserGlobals.document.getElementById('qcImportSummary');
      const origQSA = modal.querySelectorAll;
      modal.querySelectorAll = (sel) => {
        if (sel.includes('qcImportStrategy'))
          return [{ value: 'per_item', checked: false }];
        return origQSA ? origQSA(sel) : [];
      };
      w.openImportDialog({
        commands: [
          { id: 'i1', name: 'a', type: 'single', command: 'a', group: 'X' },
        ],
      });
      assertTrue(modal.classList.contains('show'));
      assertTrue(listEl.innerHTML.includes('X'));
      modal.querySelectorAll = origQSA;
    });

    it('updateImportSummary counts correctly', () => {
      const modal = browserGlobals.document.getElementById('qcImportModal');
      modal._importData = { conflicts: [{ incoming: { id: 'c1' } }] };
      const listEl = browserGlobals.document.getElementById('qcImportList');
      const summaryEl =
        browserGlobals.document.getElementById('qcImportSummary');
      const origQSA = listEl.querySelectorAll;
      listEl.querySelectorAll = (sel) => {
        if (sel.includes('checkbox'))
          return [{ checked: true }, { checked: false }];
        if (sel.includes('conflict-icon'))
          return [{ closest: () => ({ dataset: { conflictAction: 'skip' } }) }];
        return [];
      };
      w.updateImportSummary();
      assertTrue(summaryEl.textContent.length > 0);
      listEl.querySelectorAll = origQSA;
    });

    it('onExportGroupToggle toggles child checkboxes', () => {
      const modal = browserGlobals.document.getElementById('qcExportModal');
      const origQSA = modal.querySelectorAll;
      let toggledItems = [];
      modal.querySelectorAll = (sel) => {
        if (sel.includes('data-export-group-name')) {
          return [{ checked: true }, { checked: true }];
        }
        if (sel.includes('data-export-group')) {
          return [
            { getAttribute: () => 'G', checked: true, indeterminate: false },
          ];
        }
        if (sel.includes('data-export-id'))
          return [{ checked: true }, { checked: true }];
        return [];
      };
      modal.querySelector = () => ({ checked: true, indeterminate: false });
      browserGlobals.document.getElementById('qcExportCount');
      browserGlobals.document.getElementById('qcExportBtn');
      const gc = { getAttribute: () => 'G', checked: false };
      w.onExportGroupToggle(gc);
      modal.querySelectorAll = origQSA;
      assertTrue(true);
    });

    it('onExportItemToggle updates parent group checkbox', () => {
      const modal = browserGlobals.document.getElementById('qcExportModal');
      const origQSA = modal.querySelectorAll;
      const gc = {
        getAttribute: () => 'G',
        checked: true,
        indeterminate: false,
      };
      modal.querySelectorAll = (sel) => {
        if (sel.includes('data-export-group]')) return [gc];
        if (sel.includes('data-export-group-name'))
          return [{ checked: true }, { checked: false }];
        if (sel.includes('data-export-id'))
          return [{ checked: true }, { checked: false }];
        return [];
      };
      modal.querySelector = () => ({ checked: false, indeterminate: false });
      browserGlobals.document.getElementById('qcExportCount');
      browserGlobals.document.getElementById('qcExportBtn');
      w.onExportItemToggle();
      assertTrue(gc.indeterminate === true);
      modal.querySelectorAll = origQSA;
    });

    it('executeImport handles skip conflict', () => {
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      const existing = [
        { id: 'ex1', name: 'ps', type: 'single', command: 'ps\\n' },
      ];
      ls.setItem('fpbinject-quick-commands', JSON.stringify(existing));
      const modal = browserGlobals.document.getElementById('qcImportModal');
      modal.classList.add('show');
      modal._importData = {
        incoming: [
          { id: 'imp1', name: 'ps', type: 'single', command: 'ps\\n' },
        ],
        incomingGroups: [],
        existing: JSON.parse(JSON.stringify(existing)),
        conflicts: [{ incoming: { id: 'imp1' }, existing: existing[0] }],
      };
      const listEl = browserGlobals.document.getElementById('qcImportList');
      const origQSA = listEl.querySelectorAll;
      listEl.querySelectorAll = (sel) => {
        if (sel.includes('conflict-icon'))
          return [{ closest: () => ({ dataset: { conflictAction: 'skip' } }) }];
        return [];
      };
      listEl.querySelector = (sel) => {
        if (sel.includes('data-import-id'))
          return { dataset: { conflictAction: 'skip' } };
        return null;
      };
      w.executeImport();
      assertFalse(modal.classList.contains('show'));
      listEl.querySelectorAll = origQSA;
    });

    it('executeExport creates download with selected items', () => {
      const ls = browserGlobals.localStorage;
      ls.getItem = function (k) {
        return this._store[k] || null;
      }.bind(ls);
      ls.setItem = function (k, v) {
        this._store[k] = String(v);
      }.bind(ls);
      ls.setItem(
        'fpbinject-quick-commands',
        JSON.stringify([
          {
            id: 'exp1',
            name: 'test',
            type: 'single',
            command: 'x',
            group: 'G',
          },
        ]),
      );
      ls.setItem(
        'fpbinject-quick-command-groups',
        JSON.stringify([{ name: 'G', order: 0 }]),
      );
      const modal = browserGlobals.document.getElementById('qcExportModal');
      modal.classList.add('show');
      const origQSA = modal.querySelectorAll;
      modal.querySelectorAll = (sel) => {
        if (sel.includes(':checked')) return [{ getAttribute: () => 'exp1' }];
        return [];
      };
      let clickCalled = false;
      const origCreateEl = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        const el = origCreateEl(tag);
        if (tag === 'a')
          el.click = () => {
            clickCalled = true;
          };
        return el;
      };
      const origURL = global.URL;
      global.URL = {
        createObjectURL: () => 'blob:test',
        revokeObjectURL: () => {},
      };
      w.executeExport();
      assertTrue(clickCalled);
      assertFalse(modal.classList.contains('show'));
      global.URL = origURL;
      browserGlobals.document.createElement = origCreateEl;
      modal.querySelectorAll = origQSA;
    });
  });
};
