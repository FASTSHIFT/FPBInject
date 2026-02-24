/**
 * Tests for core/logs.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertContains,
} = require('./framework');
const {
  resetMocks,
  setFetchResponse,
  getFetchCalls,
  MockTerminal,
  browserGlobals,
} = require('./mocks');

module.exports = function (w) {
  describe('Log Polling Functions (core/logs.js)', () => {
    it('startLogPolling is a function', () =>
      assertTrue(typeof w.startLogPolling === 'function'));
    it('stopLogPolling is a function', () =>
      assertTrue(typeof w.stopLogPolling === 'function'));
    it('fetchLogs is a function', () =>
      assertTrue(typeof w.fetchLogs === 'function'));
  });

  describe('startLogPolling Function', () => {
    it('resets log IDs', () => {
      resetMocks();
      w.FPBState.toolLogNextId = 100;
      w.FPBState.rawLogNextId = 200;
      w.FPBState.slotUpdateId = 300;
      w.startLogPolling();
      assertEqual(w.FPBState.toolLogNextId, 0);
      assertEqual(w.FPBState.rawLogNextId, 0);
      assertEqual(w.FPBState.slotUpdateId, 0);
      w.stopLogPolling();
    });

    it('sets logPollInterval', () => {
      resetMocks();
      w.FPBState.logPollInterval = null;
      w.startLogPolling();
      assertTrue(w.FPBState.logPollInterval !== null);
      w.stopLogPolling();
    });

    it('stops existing polling before starting', () => {
      resetMocks();
      w.startLogPolling();
      const firstInterval = w.FPBState.logPollInterval;
      w.startLogPolling();
      assertTrue(w.FPBState.logPollInterval !== null);
      w.stopLogPolling();
    });
  });

  describe('stopLogPolling Function', () => {
    it('clears logPollInterval', () => {
      resetMocks();
      w.startLogPolling();
      w.stopLogPolling();
      assertEqual(w.FPBState.logPollInterval, null);
    });

    it('handles null interval gracefully', () => {
      resetMocks();
      w.FPBState.logPollInterval = null;
      w.stopLogPolling();
      assertEqual(w.FPBState.logPollInterval, null);
    });
  });

  describe('fetchLogs Function', () => {
    it('is async function', () => {
      assertTrue(w.fetchLogs.constructor.name === 'AsyncFunction');
    });

    it('fetches from /api/logs with correct params', async () => {
      resetMocks();
      w.FPBState.toolLogNextId = 5;
      w.FPBState.rawLogNextId = 10;
      w.FPBState.slotUpdateId = 15;
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', { tool_next: 6, raw_next: 11 });
      await w.fetchLogs();
      // Should complete without error
      assertTrue(true);
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('updates toolLogNextId from response', async () => {
      resetMocks();
      w.FPBState.toolLogNextId = 0;
      w.FPBState.rawLogNextId = 0;
      w.FPBState.slotUpdateId = 0;
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', { tool_next: 100, raw_next: 200 });
      await w.fetchLogs();
      assertEqual(w.FPBState.toolLogNextId, 100);
      assertEqual(w.FPBState.rawLogNextId, 200);
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('writes tool_logs to output', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.toolLogNextId = 0;
      w.FPBState.rawLogNextId = 0;
      w.FPBState.slotUpdateId = 0;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', {
        tool_next: 1,
        raw_next: 0,
        tool_logs: ['Test log message 1', 'Test log message 2'],
      });
      await w.fetchLogs();
      assertTrue(mockTerm._writes.length >= 2);
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('writes raw_data to serial terminal', async () => {
      resetMocks();
      const mockRawTerm = new MockTerminal();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = mockRawTerm;
      w.FPBState.toolLogNextId = 0;
      w.FPBState.rawLogNextId = 0;
      w.FPBState.slotUpdateId = 0;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', {
        tool_next: 0,
        raw_next: 1,
        raw_data: 'Serial data here',
      });
      await w.fetchLogs();
      assertTrue(mockRawTerm._writes.length > 0);
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('updates slot states from slot_data', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.toolLogNextId = 0;
      w.FPBState.rawLogNextId = 0;
      w.FPBState.slotUpdateId = 0;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', {
        tool_next: 0,
        raw_next: 0,
        slot_update_id: 1,
        slot_data: {
          slots: [
            {
              id: 0,
              occupied: true,
              func: 'test_func',
              orig_addr: '0x1000',
              target_addr: '0x2000',
              code_size: 100,
            },
            { id: 1, occupied: false },
            { id: 2, occupied: false },
            { id: 3, occupied: false },
            { id: 4, occupied: false },
            { id: 5, occupied: false },
          ],
          memory: { is_dynamic: true, used: 100 },
        },
      });
      await w.fetchLogs();
      assertTrue(w.FPBState.slotStates[0].occupied);
      assertEqual(w.FPBState.slotStates[0].func, 'test_func');
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('handles non-ok response gracefully', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', { _ok: false, _status: 500 });
      await w.fetchLogs();
      assertTrue(true);
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('handles empty tool_logs array', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.toolLogNextId = 0;
      w.FPBState.rawLogNextId = 0;
      w.FPBState.slotUpdateId = 0;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', {
        tool_next: 0,
        raw_next: 0,
        tool_logs: [],
      });
      await w.fetchLogs();
      assertTrue(true);
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('handles missing slot_data gracefully', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.toolLogNextId = 0;
      w.FPBState.rawLogNextId = 0;
      w.FPBState.slotUpdateId = 0;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', {
        tool_next: 0,
        raw_next: 0,
        slot_update_id: 1,
      });
      await w.fetchLogs();
      assertTrue(true);
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('does not update slots if slot_update_id not increased', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.toolLogNextId = 0;
      w.FPBState.rawLogNextId = 0;
      w.FPBState.slotUpdateId = 5;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', {
        tool_next: 0,
        raw_next: 0,
        slot_update_id: 3,
        slot_data: { slots: [{ occupied: true }] },
      });
      await w.fetchLogs();
      assertTrue(!w.FPBState.slotStates[0].occupied);
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('handles slot_data with memory info', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.toolLogNextId = 0;
      w.FPBState.rawLogNextId = 0;
      w.FPBState.slotUpdateId = 0;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', {
        tool_next: 0,
        raw_next: 0,
        slot_update_id: 1,
        slot_data: {
          slots: Array(8)
            .fill()
            .map(() => ({ occupied: false })),
          memory: {
            is_dynamic: false,
            base: 0x20000000,
            size: 4096,
            used: 1024,
          },
        },
      });
      await w.fetchLogs();
      const memEl = browserGlobals.document.getElementById('memoryInfo');
      assertContains(memEl.innerHTML, '1024');
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('handles empty response text', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      // Simulate empty response
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        ok: true,
        headers: { get: () => 'application/json' },
        text: async () => '',
      });
      global.fetch = browserGlobals.fetch;
      await w.fetchLogs();
      assertTrue(true);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('handles invalid JSON response', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        ok: true,
        headers: { get: () => 'application/json' },
        text: async () => 'not valid json',
      });
      global.fetch = browserGlobals.fetch;
      await w.fetchLogs();
      assertTrue(true);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('handles non-json content type', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        ok: true,
        headers: { get: () => 'text/html' },
        text: async () => '<html></html>',
      });
      global.fetch = browserGlobals.fetch;
      await w.fetchLogs();
      assertTrue(true);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('handles fetch exception', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      await w.fetchLogs();
      assertTrue(true);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('handles whitespace-only response', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        ok: true,
        headers: { get: () => 'application/json' },
        text: async () => '   \n\t  ',
      });
      global.fetch = browserGlobals.fetch;
      await w.fetchLogs();
      assertTrue(true);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('handles null content-type header', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        ok: true,
        headers: { get: () => null },
        text: async () => '{}',
      });
      global.fetch = browserGlobals.fetch;
      await w.fetchLogs();
      assertTrue(true);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('updates all slot states from response', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.toolLogNextId = 0;
      w.FPBState.rawLogNextId = 0;
      w.FPBState.slotUpdateId = 0;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', {
        tool_next: 0,
        raw_next: 0,
        slot_update_id: 1,
        slot_data: {
          slots: [
            {
              id: 0,
              occupied: true,
              func: 'func0',
              orig_addr: '0x1000',
              target_addr: '0x2000',
              code_size: 100,
            },
            {
              id: 1,
              occupied: true,
              func: 'func1',
              orig_addr: '0x1100',
              target_addr: '0x2100',
              code_size: 200,
            },
            { id: 2, occupied: false },
            { id: 3, occupied: false },
            { id: 4, occupied: false },
            { id: 5, occupied: false },
          ],
        },
      });
      await w.fetchLogs();
      assertTrue(w.FPBState.slotStates[0].occupied);
      assertTrue(w.FPBState.slotStates[1].occupied);
      assertEqual(w.FPBState.slotStates[0].func, 'func0');
      assertEqual(w.FPBState.slotStates[1].func, 'func1');
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('uses slot.id to correctly index slotStates (non-sequential)', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.toolLogNextId = 0;
      w.FPBState.rawLogNextId = 0;
      w.FPBState.slotUpdateId = 0;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      // Simulate device returning Slot[0] empty, Slot[7] occupied
      setFetchResponse('/api/logs', {
        tool_next: 0,
        raw_next: 0,
        slot_update_id: 1,
        slot_data: {
          fpb_version: 2,
          slots: [
            { id: 0, occupied: false },
            { id: 1, occupied: false },
            { id: 2, occupied: false },
            { id: 3, occupied: false },
            { id: 4, occupied: false },
            { id: 5, occupied: false },
            { id: 6, occupied: false },
            {
              id: 7,
              occupied: true,
              func: 'hook_func',
              orig_addr: '0x2C9091DC',
              target_addr: '0x3D0B4B91',
              code_size: 65,
            },
          ],
        },
      });
      await w.fetchLogs();
      // Slot 7 should be occupied
      assertTrue(w.FPBState.slotStates[7].occupied);
      assertEqual(w.FPBState.slotStates[7].func, 'hook_func');
      assertEqual(w.FPBState.slotStates[7].orig_addr, '0x2C9091DC');
      assertEqual(w.FPBState.slotStates[7].code_size, 65);
      // Other slots should remain empty
      assertTrue(!w.FPBState.slotStates[0].occupied);
      assertTrue(!w.FPBState.slotStates[6].occupied);
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });

    it('correctly handles sparse slot data (only occupied slots)', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.rawTerminal = new MockTerminal();
      w.FPBState.toolLogNextId = 0;
      w.FPBState.rawLogNextId = 0;
      w.FPBState.slotUpdateId = 0;
      w.FPBState.slotStates = Array(8)
        .fill()
        .map(() => ({ occupied: false }));
      // Device returns only Slot[2] and Slot[5] as occupied
      setFetchResponse('/api/logs', {
        tool_next: 0,
        raw_next: 0,
        slot_update_id: 1,
        slot_data: {
          slots: [
            { id: 0, occupied: false },
            { id: 1, occupied: false },
            {
              id: 2,
              occupied: true,
              func: 'slot2_func',
              orig_addr: '0x08001000',
              target_addr: '0x20001000',
              code_size: 32,
            },
            { id: 3, occupied: false },
            { id: 4, occupied: false },
            {
              id: 5,
              occupied: true,
              func: 'slot5_func',
              orig_addr: '0x08002000',
              target_addr: '0x20002000',
              code_size: 48,
            },
            { id: 6, occupied: false },
            { id: 7, occupied: false },
          ],
        },
      });
      await w.fetchLogs();
      assertTrue(!w.FPBState.slotStates[0].occupied);
      assertTrue(!w.FPBState.slotStates[1].occupied);
      assertTrue(w.FPBState.slotStates[2].occupied);
      assertEqual(w.FPBState.slotStates[2].func, 'slot2_func');
      assertTrue(!w.FPBState.slotStates[3].occupied);
      assertTrue(!w.FPBState.slotStates[4].occupied);
      assertTrue(w.FPBState.slotStates[5].occupied);
      assertEqual(w.FPBState.slotStates[5].func, 'slot5_func');
      assertTrue(!w.FPBState.slotStates[6].occupied);
      assertTrue(!w.FPBState.slotStates[7].occupied);
      w.FPBState.toolTerminal = null;
      w.FPBState.rawTerminal = null;
    });
  });
};
