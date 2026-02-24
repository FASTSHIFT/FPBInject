/**
 * Tests for core/state.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertFalse,
} = require('./framework');

module.exports = function (w) {
  describe('FPBState (core/state.js)', () => {
    it('FPBState is defined', () => assertTrue(w.FPBState !== undefined));
    it('isConnected defaults to false', () =>
      assertEqual(w.FPBState.isConnected, false));
    it('selectedSlot defaults to 0', () =>
      assertEqual(w.FPBState.selectedSlot, 0));
    it('slotStates has 8 slots', () =>
      assertEqual(w.FPBState.slotStates.length, 8));
    it('slotStates slots have correct structure', () => {
      const slot = w.FPBState.slotStates[0];
      assertEqual(slot.occupied, false);
      assertEqual(slot.func, '');
      assertEqual(slot.orig_addr, '');
      assertEqual(slot.target_addr, '');
      assertEqual(slot.code_size, 0);
    });
    it('aceEditors is a Map', () =>
      assertTrue(w.FPBState.aceEditors instanceof Map));
    it('editorTabs is an array', () =>
      assertTrue(Array.isArray(w.FPBState.editorTabs)));

    // Getters and setters
    it('can set isConnected', () => {
      w.FPBState.isConnected = true;
      assertEqual(w.FPBState.isConnected, true);
      w.FPBState.isConnected = false;
    });
    it('can set selectedSlot', () => {
      w.FPBState.selectedSlot = 3;
      assertEqual(w.FPBState.selectedSlot, 3);
      w.FPBState.selectedSlot = 0;
    });
    it('fpbVersion defaults to 1', () => assertEqual(w.FPBState.fpbVersion, 1));
    it('can set fpbVersion', () => {
      w.FPBState.fpbVersion = 2;
      assertEqual(w.FPBState.fpbVersion, 2);
      w.FPBState.fpbVersion = 1;
    });
    it('can set currentTerminalTab', () => {
      w.FPBState.currentTerminalTab = 'raw';
      assertEqual(w.FPBState.currentTerminalTab, 'raw');
      w.FPBState.currentTerminalTab = 'tool';
    });
    it('can set editorTabs', () => {
      w.FPBState.editorTabs = [{ id: 'test' }];
      assertEqual(w.FPBState.editorTabs.length, 1);
      w.FPBState.editorTabs = [];
    });
    it('can set fileBrowserCallback', () => {
      const cb = () => {};
      w.FPBState.fileBrowserCallback = cb;
      assertEqual(w.FPBState.fileBrowserCallback, cb);
      w.FPBState.fileBrowserCallback = null;
    });
    it('can set fileBrowserMode', () => {
      w.FPBState.fileBrowserMode = 'dir';
      assertEqual(w.FPBState.fileBrowserMode, 'dir');
      w.FPBState.fileBrowserMode = 'file';
    });
    it('can set toolLogNextId', () => {
      w.FPBState.toolLogNextId = 100;
      assertEqual(w.FPBState.toolLogNextId, 100);
      w.FPBState.toolLogNextId = 0;
    });
    it('can set rawLogNextId', () => {
      w.FPBState.rawLogNextId = 50;
      assertEqual(w.FPBState.rawLogNextId, 50);
      w.FPBState.rawLogNextId = 0;
    });
    it('can set slotUpdateId', () => {
      w.FPBState.slotUpdateId = 25;
      assertEqual(w.FPBState.slotUpdateId, 25);
      w.FPBState.slotUpdateId = 0;
    });
    it('can set activeEditorTab', () => {
      w.FPBState.activeEditorTab = 'tab1';
      assertEqual(w.FPBState.activeEditorTab, 'tab1');
      w.FPBState.activeEditorTab = null;
    });
    it('can set currentPatchTab', () => {
      w.FPBState.currentPatchTab = { id: 'patch1', funcName: 'test' };
      assertEqual(w.FPBState.currentPatchTab.id, 'patch1');
      w.FPBState.currentPatchTab = null;
    });
    it('can set toolTerminal', () => {
      const term = { writeln: () => {} };
      w.FPBState.toolTerminal = term;
      assertEqual(w.FPBState.toolTerminal, term);
      w.FPBState.toolTerminal = null;
    });
    it('can set rawTerminal', () => {
      const term = { write: () => {} };
      w.FPBState.rawTerminal = term;
      assertEqual(w.FPBState.rawTerminal, term);
      w.FPBState.rawTerminal = null;
    });
    it('can set toolFitAddon', () => {
      const addon = { fit: () => {} };
      w.FPBState.toolFitAddon = addon;
      assertEqual(w.FPBState.toolFitAddon, addon);
      w.FPBState.toolFitAddon = null;
    });
    it('can set rawFitAddon', () => {
      const addon = { fit: () => {} };
      w.FPBState.rawFitAddon = addon;
      assertEqual(w.FPBState.rawFitAddon, addon);
      w.FPBState.rawFitAddon = null;
    });
    it('can set logPollInterval', () => {
      w.FPBState.logPollInterval = 123;
      assertEqual(w.FPBState.logPollInterval, 123);
      w.FPBState.logPollInterval = null;
    });
    it('can set autoInjectPollInterval', () => {
      w.FPBState.autoInjectPollInterval = 456;
      assertEqual(w.FPBState.autoInjectPollInterval, 456);
      w.FPBState.autoInjectPollInterval = null;
    });
    it('can set lastAutoInjectStatus', () => {
      w.FPBState.lastAutoInjectStatus = 'compiling';
      assertEqual(w.FPBState.lastAutoInjectStatus, 'compiling');
      w.FPBState.lastAutoInjectStatus = 'idle';
    });
    it('can set autoInjectProgressHideTimer', () => {
      w.FPBState.autoInjectProgressHideTimer = 789;
      assertEqual(w.FPBState.autoInjectProgressHideTimer, 789);
      w.FPBState.autoInjectProgressHideTimer = null;
    });
    it('can set slotStates array', () => {
      const newStates = [
        {
          occupied: true,
          func: 'test',
          orig_addr: '0x1000',
          target_addr: '0x2000',
          code_size: 100,
        },
      ];
      w.FPBState.slotStates = newStates;
      assertEqual(w.FPBState.slotStates[0].occupied, true);
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({
          occupied: false,
          func: '',
          orig_addr: '',
          target_addr: '',
          code_size: 0,
        }));
    });
    it('can set fileBrowserFilter', () => {
      w.FPBState.fileBrowserFilter = '*.c';
      assertEqual(w.FPBState.fileBrowserFilter, '*.c');
      w.FPBState.fileBrowserFilter = '';
    });
    it('can set currentBrowserPath', () => {
      w.FPBState.currentBrowserPath = '/home/user';
      assertEqual(w.FPBState.currentBrowserPath, '/home/user');
      w.FPBState.currentBrowserPath = '/';
    });
    it('can set selectedBrowserItem', () => {
      w.FPBState.selectedBrowserItem = '/path/to/file';
      assertEqual(w.FPBState.selectedBrowserItem, '/path/to/file');
      w.FPBState.selectedBrowserItem = null;
    });
  });
};
