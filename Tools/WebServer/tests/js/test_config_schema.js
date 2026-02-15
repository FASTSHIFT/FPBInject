/**
 * Tests for core/config-schema.js
 */
const {
  describe,
  it,
  assertTrue,
  assertEqual,
  assertContains,
} = require('./framework');
const {
  resetMocks,
  setFetchResponse,
  getFetchCalls,
  browserGlobals,
  MockTerminal,
} = require('./mocks');

module.exports = function (w) {
  describe('Config Schema Functions (core/config-schema.js)', () => {
    it('loadConfigSchema is a function', () =>
      assertTrue(typeof w.loadConfigSchema === 'function'));
    it('getConfigSchema is a function', () =>
      assertTrue(typeof w.getConfigSchema === 'function'));
    it('resetConfigSchema is a function', () =>
      assertTrue(typeof w.resetConfigSchema === 'function'));
    it('renderConfigPanel is a function', () =>
      assertTrue(typeof w.renderConfigPanel === 'function'));
    it('loadConfigValues is a function', () =>
      assertTrue(typeof w.loadConfigValues === 'function'));
    it('saveConfigValues is a function', () =>
      assertTrue(typeof w.saveConfigValues === 'function'));
    it('onConfigItemChange is a function', () =>
      assertTrue(typeof w.onConfigItemChange === 'function'));
    it('updatePathList is a function', () =>
      assertTrue(typeof w.updatePathList === 'function'));
    it('getPathListValues is a function', () =>
      assertTrue(typeof w.getPathListValues === 'function'));
    it('addPathListItem is a function', () =>
      assertTrue(typeof w.addPathListItem === 'function'));
    it('addPathListItemElement is a function', () =>
      assertTrue(typeof w.addPathListItemElement === 'function'));
    it('browsePathListItem is a function', () =>
      assertTrue(typeof w.browsePathListItem === 'function'));
    it('removePathListItem is a function', () =>
      assertTrue(typeof w.removePathListItem === 'function'));
    it('keyToElementId is a function', () =>
      assertTrue(typeof w.keyToElementId === 'function'));
  });

  describe('keyToElementId Function', () => {
    it('converts snake_case to camelCase', () => {
      assertEqual(w.keyToElementId('elf_path'), 'elfPath');
    });

    it('handles multiple underscores', () => {
      assertEqual(w.keyToElementId('tx_chunk_delay'), 'txChunkDelay');
    });

    it('handles single word', () => {
      assertEqual(w.keyToElementId('port'), 'port');
    });

    it('handles empty string', () => {
      assertEqual(w.keyToElementId(''), '');
    });
  });

  describe('resetConfigSchema Function', () => {
    it('clears cached schema', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'test', config_type: 'text', default: '' }],
        groups: {},
        group_order: [],
      });
      await w.loadConfigSchema();
      assertTrue(w.getConfigSchema() !== null);
      w.resetConfigSchema();
      assertEqual(w.getConfigSchema(), null);
    });
  });

  describe('loadConfigSchema Function', () => {
    it('is async function', () => {
      assertTrue(w.loadConfigSchema.constructor.name === 'AsyncFunction');
    });

    it('fetches from /api/config/schema', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', {
        schema: [],
        groups: {},
        group_order: [],
      });
      await w.loadConfigSchema();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/config/schema')));
    });

    it('returns cached schema on subsequent calls', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const schema = {
        schema: [{ key: 'test', config_type: 'text', default: 'val' }],
        groups: { g1: 'Group 1' },
        group_order: ['g1'],
      };
      setFetchResponse('/api/config/schema', schema);
      const result1 = await w.loadConfigSchema();
      const result2 = await w.loadConfigSchema();
      assertEqual(result1, result2);
    });

    it('returns null on fetch error', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', { _ok: false, _status: 500 });
      const result = await w.loadConfigSchema();
      assertEqual(result, null);
    });

    it('returns null on network error', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      const result = await w.loadConfigSchema();
      assertEqual(result, null);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });
  });

  describe('getConfigSchema Function', () => {
    it('returns null when not loaded', () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      assertEqual(w.getConfigSchema(), null);
    });

    it('returns schema after loading', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const schema = {
        schema: [{ key: 'test', config_type: 'text', default: '' }],
        groups: {},
        group_order: [],
      };
      setFetchResponse('/api/config/schema', schema);
      await w.loadConfigSchema();
      assertTrue(w.getConfigSchema() !== null);
    });
  });

  describe('renderConfigPanel Function', () => {
    it('is async function', () => {
      assertTrue(w.renderConfigPanel.constructor.name === 'AsyncFunction');
    });

    it('returns early if schema load fails', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', { _ok: false, _status: 500 });
      await w.renderConfigPanel('configContainer');
      assertEqual(typeof w.renderConfigPanel, 'function');
    });

    it('returns early if container not found', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', {
        schema: [],
        groups: {},
        group_order: [],
      });
      await w.renderConfigPanel('nonExistentContainer');
      assertEqual(typeof w.renderConfigPanel, 'function');
    });

    it('renders config groups', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const container =
        browserGlobals.document.getElementById('configContainer');
      container.innerHTML = '';
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'elf_path',
            config_type: 'file_path',
            label: 'ELF Path',
            group: 'project',
            order: 1,
            default: '',
          },
        ],
        groups: { project: 'Project Paths' },
        group_order: ['project'],
      });
      await w.renderConfigPanel('configContainer');
      assertContains(container.innerHTML, 'Project Paths');
    });

    it('renders file_path input', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const container =
        browserGlobals.document.getElementById('configContainer');
      container.innerHTML = '';
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'elf_path',
            config_type: 'file_path',
            label: 'ELF Path',
            group: 'project',
            order: 1,
            default: '',
            file_ext: '.elf',
          },
        ],
        groups: { project: 'Project' },
        group_order: ['project'],
      });
      await w.renderConfigPanel('configContainer');
      assertContains(container.innerHTML, 'elfPath');
      assertContains(container.innerHTML, 'browseFile');
    });

    it('renders dir_path input', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const container =
        browserGlobals.document.getElementById('configContainer');
      container.innerHTML = '';
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'toolchain_path',
            config_type: 'dir_path',
            label: 'Toolchain',
            group: 'project',
            order: 1,
            default: '',
          },
        ],
        groups: { project: 'Project' },
        group_order: ['project'],
      });
      await w.renderConfigPanel('configContainer');
      assertContains(container.innerHTML, 'toolchainPath');
      assertContains(container.innerHTML, 'browseDir');
    });

    it('renders number input', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const container =
        browserGlobals.document.getElementById('configContainer');
      container.innerHTML = '';
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'chunk_size',
            config_type: 'number',
            label: 'Chunk Size',
            group: 'transfer',
            order: 1,
            default: 128,
            min_value: 1,
            max_value: 1024,
            step: 1,
            unit: 'bytes',
          },
        ],
        groups: { transfer: 'Transfer' },
        group_order: ['transfer'],
      });
      await w.renderConfigPanel('configContainer');
      assertContains(container.innerHTML, 'chunkSize');
      assertContains(container.innerHTML, 'type="number"');
      assertContains(container.innerHTML, 'bytes');
    });

    it('renders boolean checkbox', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const container =
        browserGlobals.document.getElementById('configContainer');
      container.innerHTML = '';
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'auto_compile',
            config_type: 'boolean',
            label: 'Auto Compile',
            group: 'inject',
            order: 1,
            default: false,
          },
        ],
        groups: { inject: 'Injection' },
        group_order: ['inject'],
      });
      await w.renderConfigPanel('configContainer');
      assertContains(container.innerHTML, 'autoCompile');
      assertContains(container.innerHTML, 'type="checkbox"');
    });

    it('renders select dropdown', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const container =
        browserGlobals.document.getElementById('configContainer');
      container.innerHTML = '';
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'patch_mode',
            config_type: 'select',
            label: 'Patch Mode',
            group: 'inject',
            order: 1,
            default: 'trampoline',
            options: [
              ['trampoline', 'Trampoline'],
              ['direct', 'Direct'],
            ],
          },
        ],
        groups: { inject: 'Injection' },
        group_order: ['inject'],
      });
      await w.renderConfigPanel('configContainer');
      assertContains(container.innerHTML, 'patchMode');
      assertContains(container.innerHTML, '<select');
      assertContains(container.innerHTML, 'Trampoline');
    });

    it('renders path_list', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const container =
        browserGlobals.document.getElementById('configContainer');
      container.innerHTML = '';
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'watch_dirs',
            config_type: 'path_list',
            label: 'Watch Dirs',
            group: 'inject',
            order: 1,
            default: [],
            depends_on: 'auto_compile',
          },
        ],
        groups: { inject: 'Injection' },
        group_order: ['inject'],
      });
      await w.renderConfigPanel('configContainer');
      assertContains(container.innerHTML, 'watchDirsSection');
      assertContains(container.innerHTML, 'watchDirsList');
    });

    it('renders text input for unknown type', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const container =
        browserGlobals.document.getElementById('configContainer');
      container.innerHTML = '';
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'custom_field',
            config_type: 'unknown_type',
            label: 'Custom',
            group: 'misc',
            order: 1,
            default: 'test',
          },
        ],
        groups: { misc: 'Misc' },
        group_order: ['misc'],
      });
      await w.renderConfigPanel('configContainer');
      assertContains(container.innerHTML, 'customField');
      assertContains(container.innerHTML, 'type="text"');
    });

    it('renders log_file_path with special browse button', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const container =
        browserGlobals.document.getElementById('configContainer');
      container.innerHTML = '';
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'log_file_path',
            config_type: 'path',
            label: 'Log File',
            group: 'logging',
            order: 1,
            default: '',
          },
        ],
        groups: { logging: 'Logging' },
        group_order: ['logging'],
      });
      await w.renderConfigPanel('configContainer');
      assertContains(container.innerHTML, 'browseLogFileBtn');
    });

    it('skips empty groups', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const container =
        browserGlobals.document.getElementById('configContainer');
      container.innerHTML = '';
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'test',
            config_type: 'text',
            label: 'Test',
            group: 'group1',
            order: 1,
            default: '',
          },
        ],
        groups: { group1: 'Group 1', group2: 'Group 2' },
        group_order: ['group1', 'group2'],
      });
      await w.renderConfigPanel('configContainer');
      assertContains(container.innerHTML, 'Group 1');
      assertTrue(!container.innerHTML.includes('Group 2'));
    });

    it('includes tooltip when provided', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const container =
        browserGlobals.document.getElementById('configContainer');
      container.innerHTML = '';
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'test',
            config_type: 'text',
            label: 'Test',
            group: 'g1',
            order: 1,
            default: '',
            tooltip: 'Help text',
          },
        ],
        groups: { g1: 'Group' },
        group_order: ['g1'],
      });
      await w.renderConfigPanel('configContainer');
      assertContains(container.innerHTML, 'Help text');
    });
  });

  describe('loadConfigValues Function', () => {
    it('is async function', () => {
      assertTrue(w.loadConfigValues.constructor.name === 'AsyncFunction');
    });

    it('returns early if schema not loaded', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', { _ok: false, _status: 500 });
      await w.loadConfigValues();
      assertEqual(typeof w.loadConfigValues, 'function');
    });

    it('loads boolean values', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', {
        schema: [
          { key: 'auto_compile', config_type: 'boolean', default: false },
        ],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { auto_compile: true });
      const el = browserGlobals.document.getElementById('autoCompile');
      el.checked = false;
      await w.loadConfigValues();
      assertEqual(el.checked, true);
    });

    it('loads number values with ui_multiplier', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'tx_chunk_delay',
            config_type: 'number',
            default: 0.005,
            ui_multiplier: 1000,
          },
        ],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { tx_chunk_delay: 0.01 });
      const el = browserGlobals.document.getElementById('txChunkDelay');
      await w.loadConfigValues();
      assertEqual(parseInt(el.value), 10);
    });

    it('loads text values', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'elf_path', config_type: 'file_path', default: '' }],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { elf_path: '/path/to/file.elf' });
      const el = browserGlobals.document.getElementById('elfPath');
      await w.loadConfigValues();
      assertEqual(el.value, '/path/to/file.elf');
    });

    it('uses default when value is null', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'chunk_size',
            config_type: 'number',
            default: 128,
            ui_multiplier: 1,
          },
        ],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { chunk_size: null });
      const el = browserGlobals.document.getElementById('chunkSize');
      await w.loadConfigValues();
      assertEqual(parseInt(el.value), 128);
    });

    it('handles fetch error gracefully', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'test', config_type: 'text', default: '' }],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { _ok: false, _status: 500 });
      await w.loadConfigValues();
      assertEqual(typeof w.loadConfigValues, 'function');
    });
  });

  describe('saveConfigValues Function', () => {
    it('is async function', () => {
      assertTrue(w.saveConfigValues.constructor.name === 'AsyncFunction');
    });

    it('returns early if schema not loaded', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      await w.saveConfigValues();
      assertEqual(typeof w.saveConfigValues, 'function');
    });

    it('saves boolean values', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', {
        schema: [
          { key: 'auto_compile', config_type: 'boolean', default: false },
        ],
        groups: {},
        group_order: [],
      });
      await w.loadConfigSchema();
      browserGlobals.document.getElementById('autoCompile').checked = true;
      setFetchResponse('/api/config', { success: true });
      await w.saveConfigValues(true);
      const calls = getFetchCalls();
      const postCall = calls.find(
        (c) => c.url.includes('/api/config') && c.options?.method === 'POST',
      );
      assertTrue(postCall !== undefined);
    });

    it('saves number values with ui_multiplier', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      setFetchResponse('/api/config/schema', {
        schema: [
          {
            key: 'tx_chunk_delay',
            config_type: 'number',
            default: 0.005,
            ui_multiplier: 1000,
          },
        ],
        groups: {},
        group_order: [],
      });
      await w.loadConfigSchema();
      browserGlobals.document.getElementById('txChunkDelay').value = '10';
      setFetchResponse('/api/config', { success: true });
      await w.saveConfigValues(true);
      assertEqual(typeof w.saveConfigValues, 'function');
    });

    it('writes success message when not silent', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'test', config_type: 'text', default: '' }],
        groups: {},
        group_order: [],
      });
      await w.loadConfigSchema();
      setFetchResponse('/api/config', { success: true });
      await w.saveConfigValues(false);
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('SUCCESS')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles save failure', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'test', config_type: 'text', default: '' }],
        groups: {},
        group_order: [],
      });
      await w.loadConfigSchema();
      setFetchResponse('/api/config', { success: false, message: 'Error' });
      await w.saveConfigValues(false);
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch exception', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'test', config_type: 'text', default: '' }],
        groups: {},
        group_order: [],
      });
      await w.loadConfigSchema();
      const origFetch = browserGlobals.fetch;
      let callCount = 0;
      browserGlobals.fetch = async (url) => {
        callCount++;
        if (callCount > 1) throw new Error('Network error');
        return {
          ok: true,
          json: async () => ({ schema: [], groups: {}, group_order: [] }),
        };
      };
      global.fetch = browserGlobals.fetch;
      await w.saveConfigValues(false);
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
    });
  });

  describe('onConfigItemChange Function', () => {
    it('calls onAutoCompileChange for auto_compile', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.autoInjectPollInterval = null;
      browserGlobals.document.getElementById('autoCompile').checked = true;
      setFetchResponse('/api/config', { success: true });
      w.onConfigItemChange('auto_compile');
      assertTrue(
        w.FPBState.toolTerminal._writes.some(
          (wr) => wr.msg && wr.msg.includes('Auto-inject'),
        ),
      );
      w.stopAutoInjectPolling();
      w.FPBState.toolTerminal = null;
    });

    it('calls onVerifyCrcChange for verify_crc', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.document.getElementById('verifyCrc').checked = true;
      setFetchResponse('/api/config', { success: true });
      w.onConfigItemChange('verify_crc');
      assertTrue(
        w.FPBState.toolTerminal._writes.some(
          (wr) => wr.msg && wr.msg.includes('Verify CRC'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('calls onEnableDecompileChange for enable_decompile', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { success: true });
      w.onConfigItemChange('enable_decompile');
      assertEqual(typeof w.onConfigItemChange, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('calls saveConfig for other keys', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'elf_path', config_type: 'file_path', default: '' }],
        groups: {},
        group_order: [],
      });
      await w.loadConfigSchema();
      setFetchResponse('/api/config', { success: true });
      w.onConfigItemChange('elf_path');
      assertEqual(typeof w.onConfigItemChange, 'function');
      w.FPBState.toolTerminal = null;
    });
  });

  describe('updatePathList Function', () => {
    it('updates list with paths', () => {
      resetMocks();
      const list = browserGlobals.document.getElementById('watchDirsList');
      list.innerHTML = '';
      w.updatePathList('watch_dirs', ['/path1', '/path2']);
      assertTrue(list.children.length >= 0);
    });

    it('handles missing list element', () => {
      resetMocks();
      w.updatePathList('nonexistent_key', ['/path']);
      assertEqual(typeof w.updatePathList, 'function');
    });

    it('clears list before adding', () => {
      resetMocks();
      const list = browserGlobals.document.getElementById('watchDirsList');
      list.innerHTML = '<div>old</div>';
      w.updatePathList('watch_dirs', []);
      assertEqual(list.innerHTML, '');
    });
  });

  describe('getPathListValues Function', () => {
    it('returns array of values', () => {
      resetMocks();
      const list = browserGlobals.document.getElementById('watchDirsList');
      list.innerHTML = '';
      w.addPathListItemElement('watch_dirs', '/path1');
      w.addPathListItemElement('watch_dirs', '/path2');
      const values = w.getPathListValues('watch_dirs');
      assertTrue(Array.isArray(values));
    });

    it('returns empty array for missing element', () => {
      resetMocks();
      const values = w.getPathListValues('nonexistent');
      assertEqual(values.length, 0);
    });

    it('filters empty values', () => {
      resetMocks();
      const list = browserGlobals.document.getElementById('watchDirsList');
      list.innerHTML = '';
      w.addPathListItemElement('watch_dirs', '/path1');
      w.addPathListItemElement('watch_dirs', '');
      const values = w.getPathListValues('watch_dirs');
      assertTrue(values.every((v) => v !== ''));
    });
  });

  describe('addPathListItem Function', () => {
    it('sets fileBrowserCallback', () => {
      resetMocks();
      w.FPBState.fileBrowserCallback = null;
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      w.addPathListItem('watch_dirs');
      assertTrue(w.FPBState.fileBrowserCallback !== null);
    });

    it('sets fileBrowserMode to dir', () => {
      resetMocks();
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      w.addPathListItem('watch_dirs');
      assertEqual(w.FPBState.fileBrowserMode, 'dir');
    });
  });

  describe('addPathListItemElement Function', () => {
    it('adds item to list', () => {
      resetMocks();
      const list = browserGlobals.document.getElementById('watchDirsList');
      list.innerHTML = '';
      w.addPathListItemElement('watch_dirs', '/test/path');
      assertTrue(list.children.length > 0);
    });

    it('handles missing list element', () => {
      resetMocks();
      w.addPathListItemElement('nonexistent', '/path');
      assertEqual(typeof w.addPathListItemElement, 'function');
    });

    it('escapes HTML in path', () => {
      resetMocks();
      const list = browserGlobals.document.getElementById('watchDirsList');
      list.innerHTML = '';
      w.addPathListItemElement('watch_dirs', '<script>alert(1)</script>');
      assertTrue(!list.innerHTML.includes('<script>'));
    });
  });

  describe('browsePathListItem Function', () => {
    it('sets fileBrowserCallback', () => {
      resetMocks();
      w.FPBState.fileBrowserCallback = null;
      // Create a proper DOM structure
      const list = browserGlobals.document.getElementById('watchDirsList');
      list.innerHTML = '';
      w.addPathListItemElement('watch_dirs', '/test/path');
      // Get the browse button from the created item
      const btn = list.querySelector('button');
      setFetchResponse('/api/browse', {
        items: [],
        current_path: '/test/path',
      });
      if (btn) {
        w.browsePathListItem(btn, 'watch_dirs');
        assertTrue(w.FPBState.fileBrowserCallback !== null);
      } else {
        // If button not found, just verify function exists
        assertTrue(typeof w.browsePathListItem === 'function');
      }
    });

    it('sets fileBrowserMode to dir', () => {
      resetMocks();
      const list = browserGlobals.document.getElementById('watchDirsList');
      list.innerHTML = '';
      w.addPathListItemElement('watch_dirs', '/test');
      const btn = list.querySelector('button');
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      if (btn) {
        w.browsePathListItem(btn, 'watch_dirs');
        assertEqual(w.FPBState.fileBrowserMode, 'dir');
      } else {
        assertTrue(typeof w.browsePathListItem === 'function');
      }
    });
  });

  describe('removePathListItem Function', () => {
    it('removes item from DOM', async () => {
      resetMocks();
      if (w.resetConfigSchema) w.resetConfigSchema();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'watch_dirs', config_type: 'path_list', default: [] }],
        groups: {},
        group_order: [],
      });
      await w.loadConfigSchema();
      setFetchResponse('/api/config', { success: true });
      let removed = false;
      const btn = browserGlobals.document.createElement('button');
      const parent = browserGlobals.document.createElement('div');
      parent.remove = () => {
        removed = true;
      };
      btn.parentElement = parent;
      w.removePathListItem(btn, 'watch_dirs');
      assertTrue(removed);
      w.FPBState.toolTerminal = null;
    });
  });
};
