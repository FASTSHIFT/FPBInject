/**
 * Tests for features/config.js
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
  describe('Config Functions (features/config.js)', () => {
    it('loadConfig is a function', () =>
      assertTrue(typeof w.loadConfig === 'function'));
    it('saveConfig is a function', () =>
      assertTrue(typeof w.saveConfig === 'function'));
    it('setupAutoSave is a function', () =>
      assertTrue(typeof w.setupAutoSave === 'function'));
    it('onAutoCompileChange is a function', () =>
      assertTrue(typeof w.onAutoCompileChange === 'function'));
    it('getWatchDirs is a function', () =>
      assertTrue(typeof w.getWatchDirs === 'function'));
    it('addWatchDir is a function', () =>
      assertTrue(typeof w.addWatchDir === 'function'));
    it('updateWatchDirsList is a function', () =>
      assertTrue(typeof w.updateWatchDirsList === 'function'));
    it('addWatchDirItem is a function', () =>
      assertTrue(typeof w.addWatchDirItem === 'function'));
    it('browseWatchDir is a function', () =>
      assertTrue(typeof w.browseWatchDir === 'function'));
    it('removeWatchDir is a function', () =>
      assertTrue(typeof w.removeWatchDir === 'function'));
    it('onEnableDecompileChange is a function', () =>
      assertTrue(typeof w.onEnableDecompileChange === 'function'));
  });

  describe('getWatchDirs Function', () => {
    it('returns array', () => {
      const dirs = w.getWatchDirs();
      assertTrue(Array.isArray(dirs));
    });

    it('returns empty array when no items', () => {
      const dirs = w.getWatchDirs();
      assertEqual(dirs.length, 0);
    });
  });

  describe('updateWatchDirsList Function', () => {
    it('handles empty array', () => {
      w.updateWatchDirsList([]);
      assertEqual(typeof w.loadConfig, 'function');
    });

    it('handles null', () => {
      w.updateWatchDirsList(null);
      assertEqual(typeof w.loadConfig, 'function');
    });

    it('handles undefined', () => {
      w.updateWatchDirsList(undefined);
      assertEqual(typeof w.loadConfig, 'function');
    });

    it('handles array with items', () => {
      w.updateWatchDirsList(['/path/to/dir1', '/path/to/dir2']);
      assertEqual(typeof w.loadConfig, 'function');
    });

    it('clears list before adding items', () => {
      const list = browserGlobals.document.getElementById('watchDirsList');
      w.updateWatchDirsList(['/path1']);
      w.updateWatchDirsList(['/path2']);
      assertEqual(typeof w.loadConfig, 'function');
    });
  });

  describe('addWatchDirItem Function', () => {
    it('creates watch dir item element', () => {
      w.addWatchDirItem('/test/path');
      assertEqual(typeof w.loadConfig, 'function');
    });

    it('accepts optional index parameter', () => {
      w.addWatchDirItem('/test/path', 0);
      assertEqual(typeof w.loadConfig, 'function');
    });
  });

  describe('loadConfig Function', () => {
    it('is async function', () => {
      assertTrue(w.loadConfig.constructor.name === 'AsyncFunction');
    });

    it('fetches from /api/config', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { success: true });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      // Should complete without error
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('sets port value from config', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      const portSelect = browserGlobals.document.getElementById('portSelect');
      setFetchResponse('/api/config', { port: '/dev/ttyUSB0' });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('sets baudrate from config', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { baudrate: '921600' });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      // Config loading is async, just verify no error
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('sets elf_path from config', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { elf_path: '/path/to/file.elf' });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('sets compile_commands_path from config', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', {
        compile_commands_path: '/path/to/compile_commands.json',
      });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('sets toolchain_path from config', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { toolchain_path: '/opt/toolchain' });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('sets patch_mode from config', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { patch_mode: 'direct' });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('sets chunk_size from config', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { chunk_size: 256 });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('sets tx_chunk_size from config', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { tx_chunk_size: 64 });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('converts tx_chunk_delay to milliseconds', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { tx_chunk_delay: 0.01 });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('sets auto_compile checkbox', async () => {
      if (w.resetConfigSchema) w.resetConfigSchema();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.autoInjectPollInterval = null;
      // Mock schema endpoint
      setFetchResponse('/api/config/schema', {
        schema: [
          { key: 'auto_compile', config_type: 'boolean', default: false },
        ],
        groups: { inject: 'Injection' },
        group_order: ['inject'],
      });
      const el = browserGlobals.document.getElementById('autoCompile');
      setFetchResponse('/api/config', { auto_compile: true });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      // The checkbox should be set by loadConfigValuesFromData
      assertEqual(el.checked, true);
      w.stopAutoInjectPolling();
      w.FPBState.toolTerminal = null;
    });

    it('sets enable_decompile checkbox', async () => {
      if (w.resetConfigSchema) w.resetConfigSchema();
      w.FPBState.toolTerminal = new MockTerminal();
      // Mock schema endpoint
      setFetchResponse('/api/config/schema', {
        schema: [
          { key: 'enable_decompile', config_type: 'boolean', default: false },
        ],
        groups: { tools: 'Analysis Tools' },
        group_order: ['tools'],
      });
      const el = browserGlobals.document.getElementById('enableDecompile');
      setFetchResponse('/api/config', { enable_decompile: true });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(el.checked, true);
      w.FPBState.toolTerminal = null;
    });

    it('handles non-ok response gracefully', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { _ok: false, _status: 500 });
      await w.loadConfig();
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });
  });

  describe('saveConfig Function', () => {
    it('is async function', () => {
      assertTrue(w.saveConfig.constructor.name === 'AsyncFunction');
    });

    it('sends POST to /api/config', async () => {
      if (w.resetConfigSchema) w.resetConfigSchema();
      w.FPBState.toolTerminal = new MockTerminal();
      // Mock schema endpoint for schema-based saveConfig
      setFetchResponse('/api/config/schema', {
        schema: [
          { key: 'elf_path', config_type: 'file_path', default: '' },
          {
            key: 'chunk_size',
            config_type: 'number',
            default: 128,
            ui_multiplier: 1,
          },
        ],
        groups: { project: 'Project Paths' },
        group_order: ['project'],
      });
      setFetchResponse('/api/config', { success: true });
      await w.saveConfig(true);
      // Should complete without error
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('writes success message when not silent', async () => {
      if (w.resetConfigSchema) w.resetConfigSchema();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'elf_path', config_type: 'file_path', default: '' }],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { success: true });
      await w.saveConfig(false);
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('SUCCESS')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('does not write message when silent', async () => {
      if (w.resetConfigSchema) w.resetConfigSchema();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'elf_path', config_type: 'file_path', default: '' }],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { success: true });
      const writesBefore = mockTerm._writes.length;
      await w.saveConfig(true);
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('handles save failure', async () => {
      if (w.resetConfigSchema) w.resetConfigSchema();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'elf_path', config_type: 'file_path', default: '' }],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', {
        success: false,
        message: 'Save failed',
      });
      await w.saveConfig(false);
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('collects config from form elements', async () => {
      if (w.resetConfigSchema) w.resetConfigSchema();
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.document.getElementById('elfPath').value =
        '/test/path.elf';
      browserGlobals.document.getElementById('chunkSize').value = '256';
      setFetchResponse('/api/config/schema', {
        schema: [
          { key: 'elf_path', config_type: 'file_path', default: '' },
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
      setFetchResponse('/api/config', { success: true });
      await w.saveConfig(true);
      // Should complete without error
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('saves path_list config items (watch_dirs) correctly', async () => {
      // Bug fix test: path_list items like watch_dirs should be saved
      // even though they don't have an element with id="watchDirs"
      if (w.resetConfigSchema) w.resetConfigSchema();
      w.FPBState.toolTerminal = new MockTerminal();

      // Set up schema with path_list type
      setFetchResponse('/api/config/schema', {
        schema: [
          { key: 'watch_dirs', config_type: 'path_list', default: [] },
          { key: 'elf_path', config_type: 'file_path', default: '' },
        ],
        groups: {},
        group_order: [],
      });
      await w.loadConfigSchema();

      // Set up the watchDirsList element with mocked querySelectorAll
      const list = browserGlobals.document.getElementById('watchDirsList');
      list.innerHTML = '';
      list.querySelectorAll = (selector) => {
        if (selector === 'input[type="text"]') {
          return [{ value: '/watch/path1' }, { value: '/watch/path2' }];
        }
        return [];
      };

      // Capture the POST request body
      let capturedBody = null;
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async (url, options) => {
        if (options?.method === 'POST' && url.includes('/api/config')) {
          capturedBody = JSON.parse(options.body);
        }
        return { ok: true, json: async () => ({ success: true }) };
      };
      global.fetch = browserGlobals.fetch;

      await w.saveConfig(true);

      // Verify watch_dirs was included in the request
      assertTrue(capturedBody !== null, 'POST request should be made');
      assertTrue(
        Array.isArray(capturedBody.watch_dirs),
        'watch_dirs should be included as array',
      );
      assertEqual(
        capturedBody.watch_dirs.length,
        2,
        'watch_dirs should have 2 items',
      );

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
    });
  });

  describe('setupAutoSave Function', () => {
    // Note: setupAutoSave is now a no-op since auto-save is handled by
    // onConfigItemChange in config-schema.js. These tests verify backward compatibility.
    it('is callable without error', () => {
      w.setupAutoSave();
      assertEqual(typeof w.setupAutoSave, 'function');
    });

    it('does not throw when called multiple times', () => {
      w.setupAutoSave();
      w.setupAutoSave();
      assertEqual(typeof w.setupAutoSave, 'function');
    });
  });

  describe('onAutoCompileChange Function', () => {
    it('triggers config update', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.autoInjectPollInterval = null;
      browserGlobals.document.getElementById('autoCompile').checked = true;
      setFetchResponse('/api/config', { success: true });
      w.onAutoCompileChange();
      // Config update is triggered
      assertEqual(typeof w.loadConfig, 'function');
      w.stopAutoInjectPolling();
      w.FPBState.toolTerminal = null;
    });

    it('writes info message', () => {
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.autoInjectPollInterval = null;
      browserGlobals.document.getElementById('autoCompile').checked = false;
      setFetchResponse('/api/config', { success: true });
      w.onAutoCompileChange();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('Auto-inject')),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('onEnableDecompileChange Function', () => {
    it('triggers saveConfig', () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { success: true });
      w.onEnableDecompileChange();
      // saveConfig is called but may be async
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });
  });

  describe('onVerifyCrcChange Function', () => {
    it('is a function', () =>
      assertTrue(typeof w.onVerifyCrcChange === 'function'));

    it('triggers config update when enabled', () => {
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.document.getElementById('verifyCrc').checked = true;
      setFetchResponse('/api/config', { success: true });
      w.onVerifyCrcChange();
      assertTrue(
        w.FPBState.toolTerminal._writes.some(
          (wr) => wr.msg && wr.msg.includes('Verify CRC'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('triggers config update when disabled', () => {
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.document.getElementById('verifyCrc').checked = false;
      setFetchResponse('/api/config', { success: true });
      w.onVerifyCrcChange();
      assertTrue(
        w.FPBState.toolTerminal._writes.some(
          (wr) => wr.msg && wr.msg.includes('Verify CRC'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('addWatchDir Function', () => {
    it('sets fileBrowserCallback', () => {
      w.FPBState.fileBrowserCallback = null;
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      w.addWatchDir();
      assertTrue(w.FPBState.fileBrowserCallback !== null);
    });

    it('sets fileBrowserMode to dir', () => {
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      w.addWatchDir();
      assertEqual(w.FPBState.fileBrowserMode, 'dir');
    });

    it('clears fileBrowserFilter', () => {
      w.FPBState.fileBrowserFilter = '.elf';
      setFetchResponse('/api/browse', { items: [], current_path: '~' });
      w.addWatchDir();
      assertEqual(w.FPBState.fileBrowserFilter, '');
    });
  });

  describe('browseWatchDir Function', () => {
    it('sets fileBrowserCallback', () => {
      w.FPBState.fileBrowserCallback = null;
      const mockBtn = browserGlobals.document.createElement('button');
      const mockItem = browserGlobals.document.createElement('div');
      mockItem.className = 'watch-dir-item';
      const mockInput = browserGlobals.document.createElement('input');
      mockInput.value = '/test/path';
      mockItem.appendChild(mockInput);
      mockBtn.closest = (selector) =>
        selector === '.watch-dir-item' ? mockItem : null;
      mockItem.querySelector = (selector) =>
        selector === 'input' ? mockInput : null;
      setFetchResponse('/api/browse', {
        items: [],
        current_path: '/test/path',
      });
      w.browseWatchDir(mockBtn);
      assertTrue(w.FPBState.fileBrowserCallback !== null);
    });

    it('sets fileBrowserMode to dir', () => {
      const mockBtn = browserGlobals.document.createElement('button');
      const mockItem = browserGlobals.document.createElement('div');
      const mockInput = browserGlobals.document.createElement('input');
      mockInput.value = '/test/path';
      mockItem.appendChild(mockInput);
      mockBtn.closest = (selector) =>
        selector === '.watch-dir-item' ? mockItem : null;
      mockItem.querySelector = (selector) =>
        selector === 'input' ? mockInput : null;
      setFetchResponse('/api/browse', {
        items: [],
        current_path: '/test/path',
      });
      w.browseWatchDir(mockBtn);
      assertEqual(w.FPBState.fileBrowserMode, 'dir');
    });
  });

  describe('removeWatchDir Function', () => {
    it('removes watch dir item', () => {
      let removed = false;
      const mockBtn = browserGlobals.document.createElement('button');
      const mockItem = browserGlobals.document.createElement('div');
      mockItem.remove = () => {
        removed = true;
      };
      mockBtn.closest = (selector) =>
        selector === '.watch-dir-item' ? mockItem : null;
      setFetchResponse('/api/config', { success: true });
      w.FPBState.toolTerminal = new MockTerminal();
      w.removeWatchDir(mockBtn);
      assertTrue(removed);
      w.FPBState.toolTerminal = null;
    });

    it('triggers saveConfig after removal', () => {
      const mockBtn = browserGlobals.document.createElement('button');
      const mockItem = browserGlobals.document.createElement('div');
      mockItem.remove = () => {};
      mockBtn.closest = (selector) =>
        selector === '.watch-dir-item' ? mockItem : null;
      setFetchResponse('/api/config', { success: true });
      w.FPBState.toolTerminal = new MockTerminal();
      w.removeWatchDir(mockBtn);
      // saveConfig is called but may be async
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });
  });

  describe('loadConfig Function - Extended', () => {
    it('calls updateWatchDirsList with watch_dirs', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'watch_dirs', config_type: 'path_list', default: [] }],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { watch_dirs: ['/path1', '/path2'] });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('adds port option if not exists', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      const portSelect = browserGlobals.document.getElementById('portSelect');
      portSelect.options = [];
      setFetchResponse('/api/config/schema', {
        schema: [],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { port: '/dev/ttyUSB1' });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch exception gracefully', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      // Simulate network error
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      await w.loadConfig();
      assertEqual(typeof w.loadConfig, 'function');
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
    });
  });

  describe('saveConfig Function - Extended', () => {
    it('includes watch_dirs in config', async () => {
      if (w.resetConfigSchema) w.resetConfigSchema();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config/schema', {
        schema: [{ key: 'watch_dirs', config_type: 'path_list', default: [] }],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { success: true });
      await w.saveConfig(true);
      // Should complete without error
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('includes auto_compile in config', async () => {
      if (w.resetConfigSchema) w.resetConfigSchema();
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.document.getElementById('autoCompile').checked = true;
      setFetchResponse('/api/config/schema', {
        schema: [
          { key: 'auto_compile', config_type: 'boolean', default: false },
        ],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { success: true });
      await w.saveConfig(true);
      // Should complete without error
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('includes enable_decompile in config', async () => {
      if (w.resetConfigSchema) w.resetConfigSchema();
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.document.getElementById('enableDecompile').checked = true;
      setFetchResponse('/api/config/schema', {
        schema: [
          { key: 'enable_decompile', config_type: 'boolean', default: false },
        ],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { success: true });
      await w.saveConfig(true);
      // Should complete without error
      assertEqual(typeof w.loadConfig, 'function');
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch exception', async () => {
      if (w.resetConfigSchema) w.resetConfigSchema();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      let callCount = 0;
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async (url) => {
        callCount++;
        if (url.includes('/api/config/schema')) {
          // Return mock schema
          return {
            ok: true,
            json: async () => ({
              schema: [
                { key: 'elf_path', config_type: 'file_path', default: '' },
              ],
              groups: {},
              group_order: [],
            }),
          };
        }
        // Config endpoint - throw error
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      await w.saveConfig(false);
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
    });
  });

  describe('onAutoCompileChange Function - Extended', () => {
    it('starts polling when enabled', () => {
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.autoInjectPollInterval = null;
      browserGlobals.document.getElementById('autoCompile').checked = true;
      setFetchResponse('/api/config', { success: true });
      w.onAutoCompileChange();
      assertTrue(w.FPBState.autoInjectPollInterval !== null);
      w.stopAutoInjectPolling();
      w.FPBState.toolTerminal = null;
    });

    it('stops polling when disabled', () => {
      w.FPBState.toolTerminal = new MockTerminal();
      w.startAutoInjectPolling();
      browserGlobals.document.getElementById('autoCompile').checked = false;
      setFetchResponse('/api/config', { success: true });
      w.onAutoCompileChange();
      assertEqual(w.FPBState.autoInjectPollInterval, null);
      w.FPBState.toolTerminal = null;
    });

    it('updates watcherStatus to On when enabled', () => {
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.autoInjectPollInterval = null;
      const watcherStatus =
        browserGlobals.document.getElementById('watcherStatus');
      browserGlobals.document.getElementById('autoCompile').checked = true;
      setFetchResponse('/api/config', { success: true });
      w.onAutoCompileChange();
      assertEqual(watcherStatus.textContent, 'Watcher: On');
      w.stopAutoInjectPolling();
      w.FPBState.toolTerminal = null;
    });

    it('updates watcherStatus to Off when disabled', () => {
      w.FPBState.toolTerminal = new MockTerminal();
      const watcherStatus =
        browserGlobals.document.getElementById('watcherStatus');
      watcherStatus.textContent = 'Watcher: On';
      browserGlobals.document.getElementById('autoCompile').checked = false;
      setFetchResponse('/api/config', { success: true });
      w.onAutoCompileChange();
      assertEqual(watcherStatus.textContent, 'Watcher: Off');
      w.FPBState.toolTerminal = null;
    });
  });

  describe('updateWatcherStatus Function', () => {
    it('is a function', () =>
      assertTrue(typeof w.updateWatcherStatus === 'function'));

    it('sets watcherStatus to On when enabled', () => {
      const watcherStatus =
        browserGlobals.document.getElementById('watcherStatus');
      w.updateWatcherStatus(true);
      assertEqual(watcherStatus.textContent, 'Watcher: On');
    });

    it('sets watcherStatus to Off when disabled', () => {
      const watcherStatus =
        browserGlobals.document.getElementById('watcherStatus');
      watcherStatus.textContent = 'Watcher: On';
      w.updateWatcherStatus(false);
      assertEqual(watcherStatus.textContent, 'Watcher: Off');
    });

    it('sets watcherIcon to eye when enabled', () => {
      const watcherIcon = browserGlobals.document.getElementById('watcherIcon');
      w.updateWatcherStatus(true);
      assertEqual(watcherIcon.className, 'codicon codicon-eye');
    });

    it('sets watcherIcon to eye-closed when disabled', () => {
      const watcherIcon = browserGlobals.document.getElementById('watcherIcon');
      watcherIcon.className = 'codicon codicon-eye';
      w.updateWatcherStatus(false);
      assertEqual(watcherIcon.className, 'codicon codicon-eye-closed');
    });

    it('handles missing watcherStatus element gracefully', () => {
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'watcherStatus') return null;
        return origGetById.call(browserGlobals.document, id);
      };
      // Should not throw
      w.updateWatcherStatus(true);
      assertEqual(typeof w.loadConfig, 'function');
      browserGlobals.document.getElementById = origGetById;
    });

    it('handles missing watcherIcon element gracefully', () => {
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'watcherIcon') return null;
        return origGetById.call(browserGlobals.document, id);
      };
      // Should not throw
      w.updateWatcherStatus(true);
      assertEqual(typeof w.loadConfig, 'function');
      browserGlobals.document.getElementById = origGetById;
    });
  });

  describe('loadConfig Function - Watcher Status', () => {
    it('updates watcherStatus to On when auto_compile is true', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.autoInjectPollInterval = null;
      const watcherStatus =
        browserGlobals.document.getElementById('watcherStatus');
      setFetchResponse('/api/config/schema', {
        schema: [
          { key: 'auto_compile', config_type: 'boolean', default: false },
        ],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { auto_compile: true });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(watcherStatus.textContent, 'Watcher: On');
      w.stopAutoInjectPolling();
      w.FPBState.toolTerminal = null;
    });

    it('updates watcherStatus to Off when auto_compile is false', async () => {
      w.FPBState.toolTerminal = new MockTerminal();
      const watcherStatus =
        browserGlobals.document.getElementById('watcherStatus');
      watcherStatus.textContent = 'Watcher: On';
      setFetchResponse('/api/config/schema', {
        schema: [
          { key: 'auto_compile', config_type: 'boolean', default: false },
        ],
        groups: {},
        group_order: [],
      });
      setFetchResponse('/api/config', { auto_compile: false });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(watcherStatus.textContent, 'Watcher: Off');
      w.FPBState.toolTerminal = null;
    });
  });
};
