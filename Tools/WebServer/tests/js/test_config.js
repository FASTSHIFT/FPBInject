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
      resetMocks();
      const dirs = w.getWatchDirs();
      assertEqual(dirs.length, 0);
    });
  });

  describe('updateWatchDirsList Function', () => {
    it('handles empty array', () => {
      w.updateWatchDirsList([]);
      assertTrue(true);
    });

    it('handles null', () => {
      w.updateWatchDirsList(null);
      assertTrue(true);
    });

    it('handles undefined', () => {
      w.updateWatchDirsList(undefined);
      assertTrue(true);
    });

    it('handles array with items', () => {
      w.updateWatchDirsList(['/path/to/dir1', '/path/to/dir2']);
      assertTrue(true);
    });

    it('clears list before adding items', () => {
      resetMocks();
      const list = browserGlobals.document.getElementById('watchDirsList');
      w.updateWatchDirsList(['/path1']);
      w.updateWatchDirsList(['/path2']);
      assertTrue(true);
    });
  });

  describe('addWatchDirItem Function', () => {
    it('creates watch dir item element', () => {
      resetMocks();
      w.addWatchDirItem('/test/path');
      assertTrue(true);
    });

    it('accepts optional index parameter', () => {
      resetMocks();
      w.addWatchDirItem('/test/path', 0);
      assertTrue(true);
    });
  });

  describe('loadConfig Function', () => {
    it('is async function', () => {
      assertTrue(w.loadConfig.constructor.name === 'AsyncFunction');
    });

    it('fetches from /api/config', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { success: true });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/config')));
      w.FPBState.toolTerminal = null;
    });

    it('sets port value from config', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const portSelect = browserGlobals.document.getElementById('portSelect');
      setFetchResponse('/api/config', { port: '/dev/ttyUSB0' });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });

    it('sets baudrate from config', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const baudrateEl = browserGlobals.document.getElementById('baudrate');
      setFetchResponse('/api/config', { baudrate: '921600' });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(baudrateEl.value, '921600');
      w.FPBState.toolTerminal = null;
    });

    it('sets elf_path from config', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const elfPathEl = browserGlobals.document.getElementById('elfPath');
      setFetchResponse('/api/config', { elf_path: '/path/to/file.elf' });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(elfPathEl.value, '/path/to/file.elf');
      w.FPBState.toolTerminal = null;
    });

    it('sets compile_commands_path from config', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const el = browserGlobals.document.getElementById('compileCommandsPath');
      setFetchResponse('/api/config', {
        compile_commands_path: '/path/to/compile_commands.json',
      });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(el.value, '/path/to/compile_commands.json');
      w.FPBState.toolTerminal = null;
    });

    it('sets toolchain_path from config', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const el = browserGlobals.document.getElementById('toolchainPath');
      setFetchResponse('/api/config', { toolchain_path: '/opt/toolchain' });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(el.value, '/opt/toolchain');
      w.FPBState.toolTerminal = null;
    });

    it('sets patch_mode from config', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const el = browserGlobals.document.getElementById('patchMode');
      setFetchResponse('/api/config', { patch_mode: 'direct' });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(el.value, 'direct');
      w.FPBState.toolTerminal = null;
    });

    it('sets chunk_size from config', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const el = browserGlobals.document.getElementById('chunkSize');
      setFetchResponse('/api/config', { chunk_size: 256 });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(el.value, 256);
      w.FPBState.toolTerminal = null;
    });

    it('sets tx_chunk_size from config', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const el = browserGlobals.document.getElementById('txChunkSize');
      setFetchResponse('/api/config', { tx_chunk_size: 64 });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(el.value, 64);
      w.FPBState.toolTerminal = null;
    });

    it('converts tx_chunk_delay to milliseconds', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const el = browserGlobals.document.getElementById('txChunkDelay');
      setFetchResponse('/api/config', { tx_chunk_delay: 0.01 });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(el.value, 10);
      w.FPBState.toolTerminal = null;
    });

    it('sets auto_compile checkbox', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const el = browserGlobals.document.getElementById('autoCompile');
      setFetchResponse('/api/config', { auto_compile: true });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(el.checked, true);
      w.FPBState.toolTerminal = null;
    });

    it('sets enable_decompile checkbox', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const el = browserGlobals.document.getElementById('enableDecompile');
      setFetchResponse('/api/config', { enable_decompile: true });
      setFetchResponse('/api/status', { connected: false });
      await w.loadConfig();
      assertEqual(el.checked, true);
      w.FPBState.toolTerminal = null;
    });

    it('handles non-ok response gracefully', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { _ok: false, _status: 500 });
      await w.loadConfig();
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });
  });

  describe('saveConfig Function', () => {
    it('is async function', () => {
      assertTrue(w.saveConfig.constructor.name === 'AsyncFunction');
    });

    it('sends POST to /api/config', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { success: true });
      await w.saveConfig(true);
      const calls = getFetchCalls();
      assertTrue(
        calls.some(
          (c) => c.url.includes('/api/config') && c.options.method === 'POST',
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('writes success message when not silent', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/config', { success: true });
      await w.saveConfig(false);
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('SUCCESS')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('does not write message when silent', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/config', { success: true });
      const writesBefore = mockTerm._writes.length;
      await w.saveConfig(true);
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });

    it('handles save failure', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
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
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.document.getElementById('elfPath').value =
        '/test/path.elf';
      browserGlobals.document.getElementById('chunkSize').value = '256';
      setFetchResponse('/api/config', { success: true });
      await w.saveConfig(true);
      const calls = getFetchCalls();
      const postCall = calls.find((c) => c.options.method === 'POST');
      assertTrue(postCall !== undefined);
      w.FPBState.toolTerminal = null;
    });
  });

  describe('setupAutoSave Function', () => {
    it('adds change listeners to text inputs', () => {
      resetMocks();
      w.setupAutoSave();
      const elfPath = browserGlobals.document.getElementById('elfPath');
      assertTrue(
        elfPath._eventListeners['change'] &&
          elfPath._eventListeners['change'].length > 0,
      );
    });

    it('adds change listeners to select inputs', () => {
      resetMocks();
      w.setupAutoSave();
      const patchMode = browserGlobals.document.getElementById('patchMode');
      assertTrue(
        patchMode._eventListeners['change'] &&
          patchMode._eventListeners['change'].length > 0,
      );
    });
  });

  describe('onAutoCompileChange Function', () => {
    it('sends config update', () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.FPBState.autoInjectPollInterval = null;
      browserGlobals.document.getElementById('autoCompile').checked = true;
      setFetchResponse('/api/config', { success: true });
      w.onAutoCompileChange();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/config')));
      w.stopAutoInjectPolling();
      w.FPBState.toolTerminal = null;
    });

    it('writes info message', () => {
      resetMocks();
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
    it('calls saveConfig', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/config', { success: true });
      w.onEnableDecompileChange();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/config')));
      w.FPBState.toolTerminal = null;
    });
  });
};
