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
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', { tool_next: 6, raw_next: 11 });
      await w.fetchLogs();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/logs')));
      assertTrue(calls.some((c) => c.url.includes('tool_since=5')));
      assertTrue(calls.some((c) => c.url.includes('raw_since=10')));
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
      w.FPBState.slotStates = Array(6)
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
      w.FPBState.slotStates = Array(6)
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
      w.FPBState.slotStates = Array(6)
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
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', {
        tool_next: 0,
        raw_next: 0,
        slot_update_id: 1,
        slot_data: {
          slots: [
            {
              occupied: true,
              func: 'test_func',
              orig_addr: '0x1000',
              target_addr: '0x2000',
              code_size: 100,
            },
            { occupied: false },
            { occupied: false },
            { occupied: false },
            { occupied: false },
            { occupied: false },
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
      w.FPBState.slotStates = Array(6)
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
      w.FPBState.slotStates = Array(6)
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
      w.FPBState.slotStates = Array(6)
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
      w.FPBState.slotStates = Array(6)
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
      w.FPBState.slotStates = Array(6)
        .fill()
        .map(() => ({ occupied: false }));
      setFetchResponse('/api/logs', {
        tool_next: 0,
        raw_next: 0,
        slot_update_id: 1,
        slot_data: {
          slots: Array(6)
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
  });
};
