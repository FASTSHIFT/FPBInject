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
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.updateSlotUI();
      const countEl = browserGlobals.document.getElementById('activeSlotCount');
      assertEqual(countEl.textContent, '0/6');
    });

    it('counts occupied slots correctly', () => {
      w.FPBState.fpbVersion = 1;
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
        { occupied: false },
        { occupied: false },
      ];
      w.updateSlotUI();
      const countEl = browserGlobals.document.getElementById('activeSlotCount');
      assertEqual(countEl.textContent, '2/6');
    });

    it('updates currentSlotDisplay', () => {
      w.FPBState.selectedSlot = 3;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.updateSlotUI();
      const displayEl =
        browserGlobals.document.getElementById('currentSlotDisplay');
      assertEqual(displayEl.textContent, 'Slot: 3');
    });

    it('updates slotSelect value', () => {
      w.FPBState.selectedSlot = 2;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.updateSlotUI();
      const selectEl = browserGlobals.document.getElementById('slotSelect');
      assertEqual(selectEl.value, 2);
    });
  });

  describe('selectSlot Function', () => {
    it('updates selectedSlot in state', () => {
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.selectSlot(4);
      assertEqual(w.FPBState.selectedSlot, 4);
      w.FPBState.toolTerminal = null;
    });

    it('writes info message', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
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
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.selectSlot('3');
      assertEqual(w.FPBState.selectedSlot, 3);
      w.FPBState.toolTerminal = null;
    });

    it('calls updateSlotUI', () => {
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
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
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
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

    it('handles missing memoryInfo element gracefully', () => {
      // Should not throw when element doesn't exist
      w.updateMemoryInfo({ used: 100 });
      // Verify function completed without error
      assertEqual(typeof w.updateMemoryInfo, 'function');
    });
  });

  describe('fpbUnpatch Function', () => {
    it('is async function', () => {
      assertTrue(w.fpbUnpatch.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', async () => {
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
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/fpb/unpatch', { success: true });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.fpbUnpatch(0);
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('cleared')),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('updates slot state on success', async () => {
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
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/fpb/unpatch', {
        success: false,
        message: 'Slot not found',
      });
      await w.fpbUnpatch(0);
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Failed')),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles fetch exception', async () => {
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
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      // Need to set global.confirm for this test
      const origConfirm = global.confirm;
      global.confirm = () => true;
      setFetchResponse('/api/fpb/unpatch', { success: true });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.fpbUnpatchAll();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('cleared')),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      global.confirm = origConfirm;
    });

    it('cancels on confirm rejection', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      const origConfirm = global.confirm;
      global.confirm = () => false;
      await w.fpbUnpatchAll();
      // Should return early without making any writes about unpatch
      assertTrue(
        !mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('cleared')),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      global.confirm = origConfirm;
    });

    it('handles unpatch all failure', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      const origConfirm = global.confirm;
      global.confirm = () => true;
      setFetchResponse('/api/fpb/unpatch', {
        success: false,
        message: 'Failed',
      });
      await w.fpbUnpatchAll();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Failed')),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      global.confirm = origConfirm;
    });

    it('handles fetch exception', async () => {
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      const origConfirm = global.confirm;
      global.confirm = () => true;
      const origFetch = global.fetch;
      global.fetch = async () => {
        throw new Error('Network error');
      };
      await w.fpbUnpatchAll();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('error')),
      );
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      global.confirm = origConfirm;
    });
  });

  describe('selectSlot Function - Extended', () => {
    it('opens disassembly for occupied slot', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
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
        { occupied: false },
        { occupied: false },
      ];
      setFetchResponse('/api/symbols/disasm', { disasm: '; test' });
      w.selectSlot(0);
      assertEqual(w.FPBState.selectedSlot, 0);
      w.FPBState.toolTerminal = null;
      w.FPBState.editorTabs = [];
    });
  });

  describe('updateSlotUI Function - Extended', () => {
    it('updates slot function display with code size', () => {
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
        { occupied: false },
        { occupied: false },
      ];
      w.updateSlotUI();
      const funcSpan = browserGlobals.document.getElementById('slot0Func');
      assertTrue(funcSpan.textContent.includes('256'));
    });

    it('sets empty text for unoccupied slots', () => {
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.updateSlotUI();
      const funcSpan = browserGlobals.document.getElementById('slot0Func');
      assertEqual(funcSpan.textContent, 'Empty');
    });

    it('toggles occupied class on slot items', () => {
      // Create slot item with proper structure
      const slotItem = browserGlobals.document.getElementById('slotItem0');
      slotItem.classList.add('slot-item');
      slotItem.dataset.slot = '0';
      const actionsDiv = browserGlobals.document.createElement('div');
      actionsDiv.classList.add('slot-actions');
      slotItem.appendChild(actionsDiv);
      slotItem.querySelector = (sel) =>
        sel === '.slot-actions' ? actionsDiv : null;

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
        { occupied: false },
        { occupied: false },
      ];
      w.FPBState.selectedSlot = 0;
      w.updateSlotUI();
      assertTrue(slotItem.classList._classes.has('occupied'));
      assertTrue(slotItem.classList._classes.has('active'));
      assertEqual(actionsDiv.style.display, 'flex');
    });

    it('hides actions div for unoccupied slots', () => {
      const slotItem = browserGlobals.document.getElementById('slotItem1');
      slotItem.classList.add('slot-item');
      slotItem.dataset.slot = '1';
      const actionsDiv = browserGlobals.document.createElement('div');
      actionsDiv.classList.add('slot-actions');
      slotItem.appendChild(actionsDiv);
      slotItem.querySelector = (sel) =>
        sel === '.slot-actions' ? actionsDiv : null;

      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.updateSlotUI();
      assertEqual(actionsDiv.style.display, 'none');
    });

    it('sets title for occupied slots', () => {
      w.FPBState.slotStates = [
        {
          occupied: true,
          func: 'my_func',
          orig_addr: '0x08001000',
          target_addr: '0x20002000',
          code_size: 512,
        },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
      ];
      w.updateSlotUI();
      const funcSpan = browserGlobals.document.getElementById('slot0Func');
      assertTrue(funcSpan.title.includes('Original'));
      assertTrue(funcSpan.title.includes('Target'));
      assertTrue(funcSpan.title.includes('512'));
    });

    it('clears title for unoccupied slots', () => {
      const funcSpan = browserGlobals.document.getElementById('slot0Func');
      funcSpan.title = 'Previous title';
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.updateSlotUI();
      assertEqual(funcSpan.title, '');
    });

    it('handles slot without func name', () => {
      w.FPBState.slotStates = [
        {
          occupied: true,
          func: '',
          orig_addr: '0x1000',
          target_addr: '0x2000',
          code_size: 0,
        },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
        { occupied: false },
      ];
      w.updateSlotUI();
      const funcSpan = browserGlobals.document.getElementById('slot0Func');
      assertTrue(funcSpan.textContent.includes('0x1000'));
      assertTrue(!funcSpan.textContent.includes('()'));
    });
  });

  describe('FPB v2 8-Slot Support', () => {
    it('fpbVersion getter/setter works', () => {
      w.FPBState.fpbVersion = 1;
      assertEqual(w.FPBState.fpbVersion, 1);
      w.FPBState.fpbVersion = 2;
      assertEqual(w.FPBState.fpbVersion, 2);
    });

    it('slotStates supports 8 slots', () => {
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      assertEqual(w.FPBState.slotStates.length, 8);
    });

    it('updateSlotUI shows 6 slots for v1', () => {
      w.FPBState.fpbVersion = 1;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.updateSlotUI();
      const countEl = browserGlobals.document.getElementById('activeSlotCount');
      assertEqual(countEl.textContent, '0/6');
    });

    it('updateSlotUI shows 8 slots for v2', () => {
      w.FPBState.fpbVersion = 2;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.updateSlotUI();
      const countEl = browserGlobals.document.getElementById('activeSlotCount');
      assertEqual(countEl.textContent, '0/8');
    });

    it('updateSlotUI counts all 8 occupied slots for v2', () => {
      w.FPBState.fpbVersion = 2;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map((_, i) => ({
          occupied: true,
          func: `test${i}`,
          orig_addr: `0x${i}000`,
          target_addr: `0x${i}100`,
        }));
      w.updateSlotUI();
      const countEl = browserGlobals.document.getElementById('activeSlotCount');
      assertEqual(countEl.textContent, '8/8');
    });

    it('updateSlotUI only counts 6 occupied slots for v1', () => {
      w.FPBState.fpbVersion = 1;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map((_, i) => ({
          occupied: true,
          func: `test${i}`,
          orig_addr: `0x${i}000`,
          target_addr: `0x${i}100`,
        }));
      w.updateSlotUI();
      const countEl = browserGlobals.document.getElementById('activeSlotCount');
      assertEqual(countEl.textContent, '6/6');
    });

    it('selectSlot blocks slots 6-7 for v1', () => {
      w.FPBState.fpbVersion = 1;
      w.FPBState.selectedSlot = 0;
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.selectSlot(6);
      assertEqual(w.FPBState.selectedSlot, 0);
      w.FPBState.toolTerminal = null;
    });

    it('selectSlot allows slots 6-7 for v2', () => {
      w.FPBState.fpbVersion = 2;
      w.FPBState.selectedSlot = 0;
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      w.selectSlot(6);
      assertEqual(w.FPBState.selectedSlot, 6);
      w.selectSlot(7);
      assertEqual(w.FPBState.selectedSlot, 7);
      w.FPBState.toolTerminal = null;
    });

    it('fpbUnpatchAll resets to 8 slots', async () => {
      w.FPBState.isConnected = true;
      w.FPBState.fpbVersion = 2;
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map((_, i) => ({
          occupied: true,
          func: `test${i}`,
          orig_addr: `0x${i}000`,
          target_addr: `0x${i}100`,
        }));
      browserGlobals.window.confirm = () => true;
      setFetchResponse('/api/fpb/unpatch', { success: true });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.fpbUnpatchAll();
      assertEqual(w.FPBState.slotStates.length, 8);
      assertTrue(w.FPBState.slotStates.every((s) => !s.occupied));
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });
};
