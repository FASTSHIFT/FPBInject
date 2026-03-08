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
      // Tree view now shows summary instead of inline table
      assertContains(html, 'watch-type-summary');
      assertContains(html, '2 fields');
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
      // Tree view uses watch-tree-node instead of watch-entry
      assertContains(html, 'watch-tree-node');
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

  describe('Tree View Exports', () => {
    it('watchRenderAll is a function', () =>
      assertTrue(typeof w.watchRenderAll === 'function'));
    it('watchToggleExpand is a function', () =>
      assertTrue(typeof w.watchToggleExpand === 'function'));
    it('watchDerefField is a function', () =>
      assertTrue(typeof w.watchDerefField === 'function'));
    it('watchSetAutoRefresh is a function', () =>
      assertTrue(typeof w.watchSetAutoRefresh === 'function'));
    it('watchCollapseAll is a function', () =>
      assertTrue(typeof w.watchCollapseAll === 'function'));
    it('watchExpandAll is a function', () =>
      assertTrue(typeof w.watchExpandAll === 'function'));
    it('_buildWatchTreeNode is a function', () =>
      assertTrue(typeof w._buildWatchTreeNode === 'function'));
    it('_watchExpandedState is a Map', () =>
      assertTrue(w._watchExpandedState instanceof Map));
    it('_watchDataCache is a Map', () =>
      assertTrue(w._watchDataCache instanceof Map));
  });

  describe('watchToggleExpand Function', () => {
    it('toggles expanded state for a node id', () => {
      const nodeId = 'test_node_123';
      w._watchExpandedState.delete(nodeId);
      // First toggle: undefined -> false (collapsed)
      w.watchToggleExpand(nodeId);
      assertEqual(w._watchExpandedState.get(nodeId), false);
      // Second toggle: false -> true (expanded)
      w.watchToggleExpand(nodeId);
      assertEqual(w._watchExpandedState.get(nodeId), true);
      w._watchExpandedState.delete(nodeId);
    });
  });

  describe('watchCollapseAll Function', () => {
    it('sets all expanded states to false', () => {
      w._watchExpandedState.set('a', true);
      w._watchExpandedState.set('b', true);
      w.watchCollapseAll();
      assertEqual(w._watchExpandedState.get('a'), false);
      assertEqual(w._watchExpandedState.get('b'), false);
      w._watchExpandedState.clear();
    });

    it('collapses DOM nodes not yet tracked', () => {
      // Mock document.querySelectorAll to return nodes
      const origQuerySelectorAll = browserGlobals.document.querySelectorAll;
      browserGlobals.document.querySelectorAll = (selector) => {
        if (selector === '.watch-tree-node[data-depth="0"]') {
          return [
            {
              getAttribute: (name) => (name === 'data-watch-id' ? '30' : null),
            },
            {
              getAttribute: (name) => (name === 'data-watch-id' ? '40' : null),
            },
          ];
        }
        return origQuerySelectorAll.call(browserGlobals.document, selector);
      };
      w._watchExpandedState.clear();
      w.watchCollapseAll();
      assertEqual(w._watchExpandedState.get('30'), false);
      assertEqual(w._watchExpandedState.get('40'), false);
      // Cleanup
      w._watchExpandedState.clear();
      browserGlobals.document.querySelectorAll = origQuerySelectorAll;
    });
  });

  describe('watchExpandAll Function', () => {
    it('is a function that can be called', () => {
      assertTrue(typeof w.watchExpandAll === 'function');
      // Just verify it doesn't throw
      w.watchExpandAll();
    });

    it('sets all expanded states to true for DOM nodes', () => {
      // Mock document.querySelectorAll to return nodes
      const origQuerySelectorAll = browserGlobals.document.querySelectorAll;
      browserGlobals.document.querySelectorAll = (selector) => {
        if (selector === '.watch-tree-node[data-depth="0"]') {
          return [
            {
              getAttribute: (name) => (name === 'data-watch-id' ? '10' : null),
            },
            {
              getAttribute: (name) => (name === 'data-watch-id' ? '20' : null),
            },
          ];
        }
        return origQuerySelectorAll.call(browserGlobals.document, selector);
      };
      w._watchExpandedState.clear();
      w.watchExpandAll();
      assertEqual(w._watchExpandedState.get('10'), true);
      assertEqual(w._watchExpandedState.get('20'), true);
      // Cleanup
      w._watchExpandedState.clear();
      browserGlobals.document.querySelectorAll = origQuerySelectorAll;
    });
  });

  describe('watchSetAutoRefresh Function', () => {
    it('sets global auto refresh interval', () => {
      w.watchSetAutoRefresh(1000);
      assertEqual(w.watchGetAutoRefreshInterval(), 1000);
      // Clean up
      w.watchSetAutoRefresh(0);
    });

    it('clears timer when interval is 0', () => {
      w.watchSetAutoRefresh(1000);
      assertTrue(w.watchGetAutoRefreshInterval() === 1000);
      w.watchSetAutoRefresh(0);
      assertEqual(w.watchGetAutoRefreshInterval(), 0);
    });
  });

  describe('_buildWatchTreeNode Function', () => {
    it('builds node for scalar value', () => {
      const html = w._buildWatchTreeNode(
        1,
        'g_counter',
        'counter',
        {
          success: true,
          hex_data: '2A000000',
          size: 4,
          type_name: 'uint32_t',
          is_aggregate: false,
        },
        0,
      );
      assertContains(html, 'watch-tree-node');
      assertContains(html, 'counter');
      assertContains(html, 'watch-node-type');
    });

    it('builds expandable node for struct', () => {
      const html = w._buildWatchTreeNode(
        2,
        'g_point',
        'point',
        {
          success: true,
          hex_data: '0100000002000000',
          size: 8,
          type_name: 'struct point',
          is_aggregate: true,
          struct_layout: [
            { name: 'x', type_name: 'uint32_t', offset: 0, size: 4 },
            { name: 'y', type_name: 'uint32_t', offset: 4, size: 4 },
          ],
        },
        0,
      );
      assertContains(html, 'watch-tree-node');
      assertContains(html, 'watch-expand-icon');
    });

    it('applies depth via CSS variable', () => {
      const html = w._buildWatchTreeNode(
        3,
        'a.b.c',
        'nested',
        {
          success: true,
          hex_data: '01',
          size: 1,
          type_name: 'uint8_t',
          is_aggregate: false,
        },
        2,
      );
      assertContains(html, '--depth: 2');
    });

    it('handles null data gracefully', () => {
      const html = w._buildWatchTreeNode(4, 'expr', 'pending', null, 0);
      assertContains(html, 'watch-tree-node');
      assertContains(html, 'pending');
    });

    it('handles error data', () => {
      const html = w._buildWatchTreeNode(
        5,
        'bad_expr',
        'bad',
        {
          success: false,
          error: 'Symbol not found',
        },
        0,
      );
      assertContains(html, 'watch-tree-node');
      assertContains(html, 'watch-error');
    });
  });

  describe('watchDerefField Function', () => {
    it('is async function', () =>
      assertTrue(w.watchDerefField.constructor.name === 'AsyncFunction'));

    it('calls deref API for pointer field', async () => {
      setFetchResponse('/api/watch_expr/deref', {
        success: true,
        target_addr: '0x20004000',
        target_type: 'uint8_t',
        target_size: 1,
        hex_data: 'FF',
      });
      setFetchResponse('/api/watch_expr/add', { success: true, id: 99 });
      setFetchResponse('/api/watch_expr/list', { success: true, watches: [] });
      const result = await w.watchDerefField(
        'node1',
        '0x20003000',
        'uint8_t *',
      );
      // Function doesn't return result directly, just verify no error
      assertTrue(true);
    });
  });

  describe('Value Change Detection', () => {
    it('_watchDataCache stores previous values', () => {
      w._watchDataCache.set('test_expr', {
        expr: 'test',
        data: { hex_data: 'AABBCCDD' },
      });
      assertEqual(w._watchDataCache.get('test_expr').data.hex_data, 'AABBCCDD');
      w._watchDataCache.delete('test_expr');
    });
  });

  describe('renderWatchEntry uses tree node', () => {
    it('renders tree node structure', () => {
      const html = w.renderWatchEntry(1, 'g_counter', {
        success: true,
        hex_data: '2A000000',
        size: 4,
        type_name: 'uint32_t',
        addr: '0x20001000',
        is_aggregate: false,
      });
      assertContains(html, 'watch-tree-node');
      assertContains(html, 'data-watch-id="1"');
    });
  });

  describe('_renderWatchValue for aggregates', () => {
    it('renders field count summary for struct', () => {
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
      assertContains(html, 'watch-type-summary');
      assertContains(html, '2 fields');
    });
  });

  describe('watchGetAutoRefreshInterval Function', () => {
    it('returns current interval', () => {
      w.watchSetAutoRefresh(2000);
      assertEqual(w.watchGetAutoRefreshInterval(), 2000);
      w.watchSetAutoRefresh(0);
    });

    it('returns 0 when disabled', () => {
      w.watchSetAutoRefresh(0);
      assertEqual(w.watchGetAutoRefreshInterval(), 0);
    });
  });

  describe('watchRenderAll Function', () => {
    it('is async function', () =>
      assertTrue(w.watchRenderAll.constructor.name === 'AsyncFunction'));
  });

  describe('watchRefreshOne Function', () => {
    it('is async function', () =>
      assertTrue(w.watchRefreshOne.constructor.name === 'AsyncFunction'));

    it('evaluates and updates cache', async () => {
      setFetchResponse('/api/watch_expr/evaluate', {
        success: true,
        hex_data: 'DEADBEEF',
        size: 4,
        type_name: 'uint32_t',
        is_aggregate: false,
      });
      await w.watchRefreshOne(99, 'test_var');
      const cached = w._watchDataCache.get(99);
      assertTrue(cached !== undefined);
      assertEqual(cached.expr, 'test_var');
      w._watchDataCache.delete(99);
    });
  });

  describe('watchRemoveEntry Function', () => {
    it('is async function', () =>
      assertTrue(w.watchRemoveEntry.constructor.name === 'AsyncFunction'));

    it('removes from cache and timers', async () => {
      w._watchDataCache.set(88, { expr: 'to_remove', data: {} });
      w._watchAutoTimers.set(88, 12345);
      setFetchResponse('/api/watch_expr/remove', { success: true });
      await w.watchRemoveEntry(88);
      assertTrue(!w._watchDataCache.has(88));
      assertTrue(!w._watchAutoTimers.has(88));
    });
  });

  describe('watchAddFromInput Function', () => {
    it('is async function', () =>
      assertTrue(w.watchAddFromInput.constructor.name === 'AsyncFunction'));

    it('returns early if input element not found', async () => {
      const origGetElementById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'watchExprInput') return null;
        return origGetElementById.call(browserGlobals.document, id);
      };
      await w.watchAddFromInput();
      browserGlobals.document.getElementById = origGetElementById;
      assertTrue(true);
    });

    it('returns early if input is empty', async () => {
      const input = browserGlobals.document.getElementById('watchExprInput');
      input.value = '   ';
      await w.watchAddFromInput();
      assertTrue(true);
    });

    it('adds expression and renders node', async () => {
      const input = browserGlobals.document.getElementById('watchExprInput');
      input.value = 'new_expr';
      setFetchResponse('/api/watch_expr/add', { success: true, id: 200 });
      setFetchResponse('/api/watch_expr/evaluate', {
        success: true,
        hex_data: 'AABBCCDD',
        size: 4,
        type_name: 'int',
        is_aggregate: false,
      });
      const panel = browserGlobals.document.getElementById('watchPanel');
      panel.innerHTML = '<div class="watch-empty">No watches</div>';
      panel.insertAdjacentHTML = (pos, html) => {
        panel.innerHTML += html;
      };
      panel.querySelector = (sel) => {
        if (sel === '.watch-empty') {
          const el = { remove: () => {} };
          return el;
        }
        return null;
      };
      await w.watchAddFromInput();
      assertEqual(input.value, '');
      const cached = w._watchDataCache.get(200);
      assertTrue(cached !== undefined);
      assertEqual(cached.expr, 'new_expr');
      w._watchDataCache.delete(200);
    });
  });

  describe('Watch LocalStorage Persistence', () => {
    it('_saveWatchesToStorage is a function', () =>
      assertTrue(typeof w._saveWatchesToStorage === 'function'));

    it('_loadWatchesFromStorage is a function', () =>
      assertTrue(typeof w._loadWatchesFromStorage === 'function'));

    it('watchRestoreFromStorage is a function', () =>
      assertTrue(typeof w.watchRestoreFromStorage === 'function'));

    it('watchRestoreFromStorage is async function', () =>
      assertTrue(
        w.watchRestoreFromStorage.constructor.name === 'AsyncFunction',
      ));

    it('_loadWatchesFromStorage returns empty array when no data', () => {
      browserGlobals.localStorage.removeItem('fpbinject_watch_expressions');
      const result = w._loadWatchesFromStorage();
      assertTrue(Array.isArray(result));
      assertEqual(result.length, 0);
    });

    it('_loadWatchesFromStorage returns stored expressions', () => {
      browserGlobals.localStorage.setItem(
        'fpbinject_watch_expressions',
        JSON.stringify(['expr1', 'expr2']),
      );
      const result = w._loadWatchesFromStorage();
      assertEqual(result.length, 2);
      assertEqual(result[0], 'expr1');
      assertEqual(result[1], 'expr2');
      browserGlobals.localStorage.removeItem('fpbinject_watch_expressions');
    });

    it('_loadWatchesFromStorage handles invalid JSON gracefully', () => {
      browserGlobals.localStorage.setItem(
        'fpbinject_watch_expressions',
        'invalid json',
      );
      const result = w._loadWatchesFromStorage();
      assertTrue(Array.isArray(result));
      assertEqual(result.length, 0);
      browserGlobals.localStorage.removeItem('fpbinject_watch_expressions');
    });

    it('_saveWatchesToStorage saves expressions to localStorage', () => {
      browserGlobals.localStorage.removeItem('fpbinject_watch_expressions');
      w._watchDataCache.set(1, { expr: 'test_expr_1', data: {} });
      w._watchDataCache.set(2, { expr: 'test_expr_2', data: {} });
      // Mock document.querySelectorAll to return nodes
      const origQuerySelectorAll = browserGlobals.document.querySelectorAll;
      browserGlobals.document.querySelectorAll = (selector) => {
        if (selector === '.watch-tree-node[data-depth="0"]') {
          return [
            { getAttribute: (name) => (name === 'data-watch-id' ? '1' : null) },
            { getAttribute: (name) => (name === 'data-watch-id' ? '2' : null) },
          ];
        }
        return origQuerySelectorAll.call(browserGlobals.document, selector);
      };
      w._saveWatchesToStorage();
      const stored = browserGlobals.localStorage.getItem(
        'fpbinject_watch_expressions',
      );
      assertTrue(stored !== null);
      const parsed = JSON.parse(stored);
      assertEqual(parsed.length, 2);
      // Cleanup
      w._watchDataCache.delete(1);
      w._watchDataCache.delete(2);
      browserGlobals.document.querySelectorAll = origQuerySelectorAll;
      browserGlobals.localStorage.removeItem('fpbinject_watch_expressions');
    });

    it('watchRestoreFromStorage restores expressions without evaluating', async () => {
      browserGlobals.localStorage.setItem(
        'fpbinject_watch_expressions',
        JSON.stringify(['restored_expr']),
      );
      setFetchResponse('/api/watch_expr/add', { success: true, id: 100 });
      const panel = browserGlobals.document.getElementById('watchPanel');
      // Add insertAdjacentHTML mock
      panel.insertAdjacentHTML = (position, html) => {
        panel.innerHTML += html;
      };
      const emptyDiv = browserGlobals.document.createElement('div');
      emptyDiv.className = 'watch-empty';
      emptyDiv.textContent = 'No watches';
      panel.innerHTML = '';
      panel.appendChild(emptyDiv);
      // Mock querySelector for empty placeholder
      const origQuerySelector = panel.querySelector;
      panel.querySelector = (selector) => {
        if (selector === '.watch-empty') return emptyDiv;
        return null;
      };
      await w.watchRestoreFromStorage();
      // Check that expression was added to cache without data
      const cached = w._watchDataCache.get(100);
      assertTrue(cached !== undefined);
      assertEqual(cached.expr, 'restored_expr');
      assertEqual(cached.data, null);
      // Cleanup
      w._watchDataCache.delete(100);
      panel.innerHTML = '';
      panel.querySelector = origQuerySelector;
      browserGlobals.localStorage.removeItem('fpbinject_watch_expressions');
    });

    it('watchRestoreFromStorage does nothing when no stored expressions', async () => {
      browserGlobals.localStorage.removeItem('fpbinject_watch_expressions');
      const panel = browserGlobals.document.getElementById('watchPanel');
      panel.innerHTML = '<div class="watch-empty">No watches</div>';
      await w.watchRestoreFromStorage();
      // Panel should remain unchanged
      assertTrue(panel.innerHTML.includes('watch-empty'));
    });
  });
};
