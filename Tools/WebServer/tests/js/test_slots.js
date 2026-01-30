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
const { browserGlobals, resetMocks } = require('./mocks');

module.exports = function (w) {
  describe('Slot Functions (core/slots.js)', () => {
    it('updateSlotUI is a function', () =>
      assertTrue(typeof w.updateSlotUI === 'function'));
    it('selectSlot is a function', () =>
      assertTrue(typeof w.selectSlot === 'function'));
    it('fpbUnpatch is a function', () =>
      assertTrue(typeof w.fpbUnpatch === 'function'));
    it('fpbReinject is a function', () =>
      assertTrue(typeof w.fpbReinject === 'function'));
    it('fpbUnpatchAll is a function', () =>
      assertTrue(typeof w.fpbUnpatchAll === 'function'));
    it('updateMemoryInfo is a function', () =>
      assertTrue(typeof w.updateMemoryInfo === 'function'));
    it('onSlotSelectChange is a function', () =>
      assertTrue(typeof w.onSlotSelectChange === 'function'));
    it('initSlotSelectListener is a function', () =>
      assertTrue(typeof w.initSlotSelectListener === 'function'));
  });

  describe('updateMemoryInfo Function', () => {
    it('handles dynamic memory', () => {
      const memEl = browserGlobals.document.getElementById('memoryInfo');
      w.updateMemoryInfo({ is_dynamic: true, used: 1024 });
      assertContains(memEl.innerHTML, 'Dynamic');
      assertContains(memEl.innerHTML, '1024');
    });
    it('handles static memory', () => {
      const memEl = browserGlobals.document.getElementById('memoryInfo');
      w.updateMemoryInfo({
        is_dynamic: false,
        base: 0x20000000,
        size: 4096,
        used: 1024,
      });
      assertContains(memEl.innerHTML, 'Static');
      assertContains(memEl.innerHTML, '20000000');
    });
    it('calculates percentage correctly', () => {
      const memEl = browserGlobals.document.getElementById('memoryInfo');
      w.updateMemoryInfo({ is_dynamic: false, base: 0, size: 100, used: 50 });
      assertContains(memEl.innerHTML, '50%');
    });
    it('handles zero size', () => {
      const memEl = browserGlobals.document.getElementById('memoryInfo');
      w.updateMemoryInfo({ is_dynamic: false, base: 0, size: 0, used: 0 });
      assertContains(memEl.innerHTML, '0%');
    });
    it('handles 100% usage', () => {
      const memEl = browserGlobals.document.getElementById('memoryInfo');
      w.updateMemoryInfo({ is_dynamic: false, base: 0, size: 100, used: 100 });
      assertContains(memEl.innerHTML, '100%');
    });
    it('handles missing fields', () => {
      const memEl = browserGlobals.document.getElementById('memoryInfo');
      w.updateMemoryInfo({});
      assertContains(memEl.innerHTML, '0%');
    });
    it('formats base address with padding', () => {
      const memEl = browserGlobals.document.getElementById('memoryInfo');
      w.updateMemoryInfo({
        is_dynamic: false,
        base: 0x100,
        size: 100,
        used: 0,
      });
      assertContains(memEl.innerHTML, '00000100');
    });
  });

  describe('fpbUnpatch Function', () => {
    it('is async function', () => {
      assertTrue(w.fpbUnpatch.constructor.name === 'AsyncFunction');
    });
  });

  describe('fpbReinject Function', () => {
    it('is async function', () => {
      assertTrue(w.fpbReinject.constructor.name === 'AsyncFunction');
    });
  });

  describe('fpbUnpatchAll Function', () => {
    it('is async function', () => {
      assertTrue(w.fpbUnpatchAll.constructor.name === 'AsyncFunction');
    });
  });
};
