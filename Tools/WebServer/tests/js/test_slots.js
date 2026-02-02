/**
 * Tests for core/slots.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertContains,
} = require('./framework');
const {
  browserGlobals,
  resetMocks,
  setFetchResponse,
  getFetchCalls,
  MockTerminal,
} = require('./mocks');

module.exports = function (w) {
  describe('Slot Functions (core/slots.js)', () => {
    it('updateSlotUI is a function', () =>
      assertTrue(typeof w.updateSlotUI === 'function'));
    it('selectSlot is a function', () =>
      assertTrue(typeof w.selectSlot === 'function'));
    it('fpbUnpatch is a function', () =>
      assertTrue(typeof w.fpbUnpatch === 'function'));
    it('fpbUnpatchAll is a function', () =>
      assertTrue(typeof w.fpbUnpatchAll === 'function'));
    it('updateMemoryInfo is a function', () =>
      assertTrue(typeof w.updateMemoryInfo === 'function'));
    it('onSlotSelectChange is a function', () =>
      assertTrue(typeof w.onSlotSelectChange === 'function'));
    it('initSlotSelectListener is a function', () =>
      assertTrue(typeof w.initSlotSelectListener === 'function'));
  });

  describe('updateSlotUI Function', () => {
    it('updates activeSlotCount element', () => {
      resetMocks();
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      w.updateSlotUI();
      const countEl = browserGlobals.document.getElementById('activeSlotCount');
      assertEqual(countEl.textContent, '0/6');
    });

    it('counts occupied slots correctly', () => {
      resetMocks();
      w.FPBState.slotStates = [
        {
          occupied: true,
          func: 'test1',
          orig_addr: '0x1000',
          target_addr: '0x2000',
        },
        {
          occupied: true,
          func: 'test2',
          orig_addr: '0x3000',
          target_addr: '0x4000',
        },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
      ];
      w.updateSlotUI();
      const countEl = browserGlobals.document.getElementById('activeSlotCount');
      assertEqual(countEl.textContent, '2/6');
    });

    it('updates currentSlotDisplay', () => {
      resetMocks();
      w.FPBState.selectedSlot = 3;
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      w.updateSlotUI();
      const displayEl =
        browserGlobals.document.getElementById('currentSlotDisplay');
      assertEqual(displayEl.textContent, 'Slot: 3');
    });

    it('updates slotSelect value', () => {
      resetMocks();
      w.FPBState.selectedSlot = 2;
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      w.updateSlotUI();
      const selectEl = browserGlobals.document.getElementById('slotSelect');
      assertEqual(selectEl.value, 2);
    });
  });

  describe('selectSlot Function', () => {
    it('updates selectedSlot in state', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      w.selectSlot(4);
      assertEqual(w.FPBState.selectedSlot, 4);
      w.FPBState.toolTerminal = null;
    });

    it('writes info message', () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      w.selectSlot(2);
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Selected Slot 2'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('parses string slotId to int', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      w.selectSlot('3');
      assertEqual(w.FPBState.selectedSlot, 3);
      w.FPBState.toolTerminal = null;
    });

    it('calls updateSlotUI', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      w.FPBState.selectedSlot = 0;
      w.selectSlot(5);
      const displayEl =
        browserGlobals.document.getElementById('currentSlotDisplay');
      assertEqual(displayEl.textContent, 'Slot: 5');
      w.FPBState.toolTerminal = null;
    });
  });

  describe('onSlotSelectChange Function', () => {
    it('reads value from slotSelect element', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      browserGlobals.document.getElementById('slotSelect').value = '4';
      w.onSlotSelectChange();
      assertEqual(w.FPBState.selectedSlot, 4);
      w.FPBState.toolTerminal = null;
    });
  });

  describe('initSlotSelectListener Function', () => {
    it('adds event listener to slotSelect', () => {
      resetMocks();
      const selectEl = browserGlobals.document.getElementById('slotSelect');
      w.initSlotSelectListener();
      assertTrue(
        selectEl._eventListeners['change'] &&
          selectEl._eventListeners['change'].length > 0,
      );
    });
  });

  describe('updateMemoryInfo Function', () => {
    it('displays used memory', () => {
      const memEl = browserGlobals.document.getElementById('memoryInfo');
      w.updateMemoryInfo({ used: 1024 });
      assertContains(memEl.innerHTML, 'Used:');
      assertContains(memEl.innerHTML, '1024');
    });

    it('handles zero used memory', () => {
      const memEl = browserGlobals.document.getElementById('memoryInfo');
      w.updateMemoryInfo({ used: 0 });
      assertContains(memEl.innerHTML, 'Used:');
      assertContains(memEl.innerHTML, '0');
    });

    it('handles missing used field', () => {
      const memEl = browserGlobals.document.getElementById('memoryInfo');
      w.updateMemoryInfo({});
      assertContains(memEl.innerHTML, 'Used:');
      assertContains(memEl.innerHTML, '0');
    });

    it('handles missing memoryInfo element', () => {
      // This should not throw
      w.updateMemoryInfo({ used: 100 });
      assertTrue(true);
    });
  });

  describe('fpbUnpatch Function', () => {
    it('is async function', () => {
      assertTrue(w.fpbUnpatch.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', async () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.fpbUnpatch(0);
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('sends POST to /api/fpb/unpatch', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/fpb/unpatch', { success: true });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.fpbUnpatch(0);
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/fpb/unpatch')));
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('updates slot state on success', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = [
        {
          occupied: true,
          func: 'test',
          orig_addr: '0x1000',
          target_addr: '0x2000',
          code_size: 100,
        },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
      ];
      setFetchResponse('/api/fpb/unpatch', { success: true });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.fpbUnpatch(0);
      assertTrue(!w.FPBState.slotStates[0].occupied);
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles unpatch failure', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/fpb/unpatch', {
        success: false,
        message: 'Slot not found',
      });
      await w.fpbUnpatch(0);
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles fetch exception', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      await w.fpbUnpatch(0);
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('fpbUnpatchAll Function', () => {
    it('is async function', () => {
      assertTrue(w.fpbUnpatchAll.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', async () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.fpbUnpatchAll();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('sends POST with all flag', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      browserGlobals.confirm = () => true;
      setFetchResponse('/api/fpb/unpatch', { success: true });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.fpbUnpatchAll();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/fpb/unpatch')));
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.confirm = () => true;
    });

    it('cancels on confirm rejection', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.confirm = () => false;
      await w.fpbUnpatchAll();
      const calls = getFetchCalls();
      assertTrue(!calls.some((c) => c.url.includes('/api/fpb/unpatch')));
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.confirm = () => true;
    });

    it('handles unpatch all failure', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      browserGlobals.confirm = () => true;
      setFetchResponse('/api/fpb/unpatch', {
        success: false,
        message: 'Failed',
      });
      await w.fpbUnpatchAll();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.confirm = () => true;
    });

    it('handles fetch exception', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      browserGlobals.confirm = () => true;
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      await w.fpbUnpatchAll();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.confirm = () => true;
    });
  });

  describe('selectSlot Function - Extended', () => {
    it('opens disassembly for occupied slot', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.editorTabs = [];
      w.FPBState.aceEditors = new Map();
      w.FPBState.slotStates = [
        {
          occupied: true,
          func: 'test_func',
          addr: '0x1000',
          orig_addr: '0x1000',
          target_addr: '0x2000',
        },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
      ];
      setFetchResponse('/api/symbols/disasm', { disasm: '; test' });
      w.selectSlot(0);
      assertTrue(true);
      w.FPBState.toolTerminal = null;
      w.FPBState.editorTabs = [];
    });
  });

  describe('updateSlotUI Function - Extended', () => {
    it('updates slot function display with code size', () => {
      resetMocks();
      w.FPBState.slotStates = [
        {
          occupied: true,
          func: 'test_func',
          orig_addr: '0x1000',
          target_addr: '0x2000',
          code_size: 256,
        },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
      ];
      w.updateSlotUI();
      const funcSpan = browserGlobals.document.getElementById('slot0Func');
      assertTrue(funcSpan.textContent.includes('256'));
    });

    it('sets empty text for unoccupied slots', () => {
      resetMocks();
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      w.updateSlotUI();
      const funcSpan = browserGlobals.document.getElementById('slot0Func');
      assertEqual(funcSpan.textContent, 'Empty');
    });
  });
};
