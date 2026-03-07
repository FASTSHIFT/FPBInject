/**
 * Tests for features/watch.js - Watch Expression Module
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertContains,
} = require('./framework');
const { resetMocks, setFetchResponse, browserGlobals } = require('./mocks');

module.exports = function (w) {
  describe('Watch Module Exports', () => {
    it('watchEvaluate is a function', () =>
      assertTrue(typeof w.watchEvaluate === 'function'));
    it('watchDeref is a function', () =>
      assertTrue(typeof w.watchDeref === 'function'));
    it('watchAdd is a function', () =>
      assertTrue(typeof w.watchAdd === 'function'));
    it('watchRemove is a function', () =>
      assertTrue(typeof w.watchRemove === 'function'));
    it('watchGetList is a function', () =>
      assertTrue(typeof w.watchGetList === 'function'));
    it('watchClear is a function', () =>
      assertTrue(typeof w.watchClear === 'function'));
    it('watchRefreshOne is a function', () =>
      assertTrue(typeof w.watchRefreshOne === 'function'));
    it('watchRemoveEntry is a function', () =>
      assertTrue(typeof w.watchRemoveEntry === 'function'));
    it('renderWatchEntry is a function', () =>
      assertTrue(typeof w.renderWatchEntry === 'function'));
    it('_renderWatchValue is a function', () =>
      assertTrue(typeof w._renderWatchValue === 'function'));
    it('_renderWatchStructTable is a function', () =>
      assertTrue(typeof w._renderWatchStructTable === 'function'));
    it('_watchAutoTimers is a Map', () =>
      assertTrue(w._watchAutoTimers instanceof Map));
  });

  describe('watchEvaluate Function', () => {
    it('is async function', () =>
      assertTrue(w.watchEvaluate.constructor.name === 'AsyncFunction'));

    it('sends POST to /api/watch_expr/evaluate', async () => {
      setFetchResponse('/api/watch_expr/evaluate', {
        success: true,
        expr: 'g_counter',
        addr: '0x20001000',
        size: 4,
        type_name: 'uint32_t',
        is_pointer: false,
        is_aggregate: false,
        hex_data: '01000000',
        source: 'device',
      });
      const result = await w.watchEvaluate('g_counter', true);
      assertTrue(result.success);
      assertEqual(result.addr, '0x20001000');
      assertEqual(result.type_name, 'uint32_t');
    });

    it('handles error response', async () => {
      setFetchResponse('/api/watch_expr/evaluate', {
        success: false,
        error: 'GDB not available',
      });
      const result = await w.watchEvaluate('bad_expr');
      assertTrue(!result.success);
      assertContains(result.error, 'GDB');
    });
  });

  describe('watchDeref Function', () => {
    it('is async function', () =>
      assertTrue(w.watchDeref.constructor.name === 'AsyncFunction'));

    it('sends POST to /api/watch_expr/deref', async () => {
      setFetchResponse('/api/watch_expr/deref', {
        success: true,
        target_addr: '0x20003000',
        target_type: 'uint32_t',
        target_size: 4,
        hex_data: 'DEADBEEF',
      });
      const result = await w.watchDeref('0x20002000', 'uint32_t *', 256);
      assertTrue(result.success);
      assertEqual(result.target_addr, '0x20003000');
    });
  });

  describe('watchAdd Function', () => {
    it('is async function', () =>
      assertTrue(w.watchAdd.constructor.name === 'AsyncFunction'));

    it('sends POST to /api/watch_expr/add', async () => {
      setFetchResponse('/api/watch_expr/add', { success: true, id: 1 });
      const result = await w.watchAdd('g_counter');
      assertTrue(result.success);
      assertEqual(result.id, 1);
    });
  });

  describe('watchRemove Function', () => {
    it('is async function', () =>
      assertTrue(w.watchRemove.constructor.name === 'AsyncFunction'));

    it('sends POST to /api/watch_expr/remove', async () => {
      setFetchResponse('/api/watch_expr/remove', { success: true });
      const result = await w.watchRemove(1);
      assertTrue(result.success);
    });
  });

  describe('watchGetList Function', () => {
    it('is async function', () =>
      assertTrue(w.watchGetList.constructor.name === 'AsyncFunction'));

    it('fetches from /api/watch_expr/list', async () => {
      setFetchResponse('/api/watch_expr/list', {
        success: true,
        watches: [{ id: 1, expr: 'g_counter', collapsed: false }],
      });
      const result = await w.watchGetList();
      assertTrue(result.success);
      assertEqual(result.watches.length, 1);
    });
  });

  describe('watchClear Function', () => {
    it('is async function', () =>
      assertTrue(w.watchClear.constructor.name === 'AsyncFunction'));

    it('sends POST to /api/watch_expr/clear', async () => {
      setFetchResponse('/api/watch_expr/clear', { success: true });
      const result = await w.watchClear();
      assertTrue(result.success);
    });
  });

  describe('_renderWatchValue Helper', () => {
    it('renders no-data when hex_data missing', () => {
      const html = w._renderWatchValue({ hex_data: null, size: 4 });
      assertContains(html, '—');
    });

    it('renders read error', () => {
      const html = w._renderWatchValue({
        hex_data: null,
        read_error: 'Timeout',
      });
      assertContains(html, 'Timeout');
    });

    it('renders scalar value with decode', () => {
      const html = w._renderWatchValue({
        hex_data: '01000000',
        size: 4,
        type_name: 'uint32_t',
        is_aggregate: false,
      });
      assertContains(html, '1');
    });

    it('renders struct table for aggregate', () => {
      const html = w._renderWatchValue({
        hex_data: '0100000002000000',
        size: 8,
        type_name: 'struct point',
        is_aggregate: true,
        struct_layout: [
          { name: 'x', type_name: 'uint32_t', offset: 0, size: 4 },
          { name: 'y', type_name: 'uint32_t', offset: 4, size: 4 },
        ],
      });
      assertContains(html, 'watch-struct-table');
      assertContains(html, 'x');
      assertContains(html, 'y');
    });

    it('renders hex for unknown type', () => {
      const html = w._renderWatchValue({
        hex_data: 'AABB',
        size: 2,
        type_name: 'custom_t',
        is_aggregate: false,
      });
      assertContains(html, 'AA BB');
    });
  });

  describe('_renderWatchStructTable Helper', () => {
    it('renders table with fields', () => {
      const html = w._renderWatchStructTable('0100000002000000', [
        { name: 'a', type_name: 'uint32_t', offset: 0, size: 4 },
        { name: 'b', type_name: 'uint32_t', offset: 4, size: 4 },
      ]);
      assertContains(html, '<table');
      assertContains(html, 'a');
      assertContains(html, 'b');
    });

    it('shows deref button for pointer fields', () => {
      const html = w._renderWatchStructTable('00300020', [
        { name: 'ptr', type_name: 'uint8_t *', offset: 0, size: 4 },
      ]);
      assertContains(html, 'watch-deref-btn');
      assertContains(html, '[→]');
    });

    it('no deref button for non-pointer fields', () => {
      const html = w._renderWatchStructTable('01000000', [
        { name: 'val', type_name: 'int', offset: 0, size: 4 },
      ]);
      assertTrue(!html.includes('watch-deref-btn'));
    });
  });

  describe('renderWatchEntry Function', () => {
    it('renders entry with expression', () => {
      const html = w.renderWatchEntry(1, 'g_counter', {
        success: true,
        hex_data: '2A000000',
        size: 4,
        type_name: 'uint32_t',
        addr: '0x20001000',
        is_aggregate: false,
      });
      assertContains(html, 'g_counter');
      assertContains(html, 'watch-entry');
      assertContains(html, 'data-watch-id="1"');
    });

    it('renders entry with error', () => {
      const html = w.renderWatchEntry(2, 'bad_expr', {
        success: false,
        error: 'Not found',
      });
      assertContains(html, 'bad_expr');
      assertContains(html, 'Not found');
    });

    it('renders entry without data', () => {
      const html = w.renderWatchEntry(3, 'pending', null);
      assertContains(html, 'pending');
    });
  });

  describe('Panel Interaction Functions', () => {
    it('watchAddFromInput is a function', () =>
      assertTrue(typeof w.watchAddFromInput === 'function'));
    it('watchRefreshAll is a function', () =>
      assertTrue(typeof w.watchRefreshAll === 'function'));
    it('watchClearAll is a function', () =>
      assertTrue(typeof w.watchClearAll === 'function'));

    it('watchAddFromInput is async', () =>
      assertTrue(w.watchAddFromInput.constructor.name === 'AsyncFunction'));
    it('watchRefreshAll is async', () =>
      assertTrue(w.watchRefreshAll.constructor.name === 'AsyncFunction'));
    it('watchClearAll is async', () =>
      assertTrue(w.watchClearAll.constructor.name === 'AsyncFunction'));

    it('watchClearAll clears auto timers', async () => {
      w._watchAutoTimers.set(99, 12345);
      setFetchResponse('/api/watch_expr/clear', { success: true });
      await w.watchClearAll();
      assertTrue(w._watchAutoTimers.size === 0);
    });
  });
};
