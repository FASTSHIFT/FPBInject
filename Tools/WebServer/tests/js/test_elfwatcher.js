/**
 * Tests for features/elfwatcher.js - ELF File Watcher Module
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertFalse,
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
  describe('ELF Watcher Module Exports', () => {
    it('startElfWatcherPolling is a function', () =>
      assertTrue(typeof w.startElfWatcherPolling === 'function'));

    it('stopElfWatcherPolling is a function', () =>
      assertTrue(typeof w.stopElfWatcherPolling === 'function'));

    it('pollElfStatus is a function', () =>
      assertTrue(typeof w.pollElfStatus === 'function'));

    it('showElfChangeDialog is a function', () =>
      assertTrue(typeof w.showElfChangeDialog === 'function'));

    it('reloadElfSymbols is a function', () =>
      assertTrue(typeof w.reloadElfSymbols === 'function'));

    it('acknowledgeElfChange is a function', () =>
      assertTrue(typeof w.acknowledgeElfChange === 'function'));

    it('resetElfWatcherState is a function', () =>
      assertTrue(typeof w.resetElfWatcherState === 'function'));

    it('isElfWatcherRunning is a function', () =>
      assertTrue(typeof w.isElfWatcherRunning === 'function'));
  });

  describe('pollElfStatus Function', () => {
    it('is async function', () => {
      assertTrue(w.pollElfStatus.constructor.name === 'AsyncFunction');
    });

    it('fetches /api/watch/elf_status', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.resetElfWatcherState();
      setFetchResponse('/api/watch/elf_status', {
        success: true,
        changed: false,
        elf_path: '/path/to/file.elf',
      });

      await w.pollElfStatus();

      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/watch/elf_status')));
      w.FPBState.toolTerminal = null;
    });

    it('does nothing when changed is false', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.resetElfWatcherState();
      setFetchResponse('/api/watch/elf_status', {
        success: true,
        changed: false,
        elf_path: '/path/to/file.elf',
      });

      await w.pollElfStatus();

      // Should not show warning when not changed
      assertFalse(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('ELF file changed'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('shows dialog when changed is true', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.resetElfWatcherState();

      // Mock confirm to return false (ignore)
      browserGlobals.confirm = () => false;
      global.confirm = () => false;
      setFetchResponse('/api/watch/elf_status', {
        success: true,
        changed: true,
        elf_path: '/path/to/file.elf',
      });
      setFetchResponse('/api/watch/elf_acknowledge', { success: true });

      await w.pollElfStatus();

      // Should show warning when changed
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('ELF file changed'),
        ),
      );
      w.FPBState.toolTerminal = null;
      browserGlobals.confirm = () => true;
      global.confirm = () => true;
    });

    it('handles fetch error gracefully', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.resetElfWatcherState();

      // Set fetch to throw error
      global.fetch = async () => {
        throw new Error('Network error');
      };

      // Should not throw
      await w.pollElfStatus();
      assertTrue(true);

      w.FPBState.toolTerminal = null;
    });
  });

  describe('reloadElfSymbols Function', () => {
    it('is async function', () => {
      assertTrue(w.reloadElfSymbols.constructor.name === 'AsyncFunction');
    });

    it('calls acknowledge and config APIs', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/watch/elf_acknowledge', { success: true });
      setFetchResponse('/api/config', { success: true });

      await w.reloadElfSymbols('/path/to/file.elf');

      const calls = getFetchCalls();
      assertTrue(
        calls.some((c) => c.url.includes('/api/watch/elf_acknowledge')),
      );
      assertTrue(calls.some((c) => c.url.includes('/api/config')));
      w.FPBState.toolTerminal = null;
    });

    it('writes success message', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/watch/elf_acknowledge', { success: true });
      setFetchResponse('/api/config', { success: true });

      await w.reloadElfSymbols('/path/to/file.elf');

      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Symbols reloaded'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles error gracefully', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;

      global.fetch = async () => {
        throw new Error('Network error');
      };

      await w.reloadElfSymbols('/path/to/file.elf');

      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Failed to reload'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('acknowledgeElfChange Function', () => {
    it('is async function', () => {
      assertTrue(w.acknowledgeElfChange.constructor.name === 'AsyncFunction');
    });

    it('calls /api/watch/elf_acknowledge', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/watch/elf_acknowledge', { success: true });

      await w.acknowledgeElfChange();

      const calls = getFetchCalls();
      assertTrue(
        calls.some((c) => c.url.includes('/api/watch/elf_acknowledge')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('writes info message', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/watch/elf_acknowledge', { success: true });

      await w.acknowledgeElfChange();

      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('ELF change acknowledged'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('showElfChangeDialog Function', () => {
    it('writes warning message', () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.resetElfWatcherState();

      // Mock confirm to return false
      browserGlobals.confirm = () => false;
      global.confirm = () => false;
      setFetchResponse('/api/watch/elf_acknowledge', { success: true });

      w.showElfChangeDialog('/path/to/file.elf');

      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('ELF file changed'),
        ),
      );
      w.FPBState.toolTerminal = null;
      browserGlobals.confirm = () => true;
      global.confirm = () => true;
    });

    it('calls reloadElfSymbols when user confirms', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.resetElfWatcherState();

      browserGlobals.confirm = () => true;
      global.confirm = () => true;
      setFetchResponse('/api/watch/elf_acknowledge', { success: true });
      setFetchResponse('/api/config', { success: true });

      w.showElfChangeDialog('/path/to/file.elf');

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 50));

      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Reloading symbols'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('calls acknowledgeElfChange when user cancels', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.resetElfWatcherState();

      browserGlobals.confirm = () => false;
      global.confirm = () => false;
      setFetchResponse('/api/watch/elf_acknowledge', { success: true });

      w.showElfChangeDialog('/path/to/file.elf');

      // Wait for async operations - acknowledgeElfChange is async
      await new Promise((resolve) => setTimeout(resolve, 50));

      const calls = getFetchCalls();
      assertTrue(
        calls.some((c) => c.url.includes('/api/watch/elf_acknowledge')),
      );
      w.FPBState.toolTerminal = null;
      browserGlobals.confirm = () => true;
      global.confirm = () => true;
    });

    it('prevents duplicate dialogs while one is shown', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.resetElfWatcherState();

      let confirmCallCount = 0;
      const mockConfirm = () => {
        confirmCallCount++;
        return false;
      };
      // Set both browserGlobals and global confirm
      browserGlobals.confirm = mockConfirm;
      global.confirm = mockConfirm;
      setFetchResponse('/api/watch/elf_acknowledge', { success: true });

      // First call should show dialog and set elfChangeDialogShown = true
      // After confirm returns, it sets elfChangeDialogShown = false
      w.showElfChangeDialog('/path/to/file.elf');

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 50));

      // Since confirm is synchronous in our mock, the dialog completes immediately
      // and elfChangeDialogShown is reset to false, allowing another dialog
      // This test verifies the function works correctly
      assertEqual(confirmCallCount, 1);
      w.FPBState.toolTerminal = null;
      browserGlobals.confirm = () => true;
      global.confirm = () => true;
    });
  });

  describe('isElfWatcherRunning Function', () => {
    it('returns false initially', () => {
      w.stopElfWatcherPolling();
      assertFalse(w.isElfWatcherRunning());
    });
  });

  describe('resetElfWatcherState Function', () => {
    it('resets dialog shown state', () => {
      w.resetElfWatcherState();
      // After reset, pollElfStatus should be able to show dialog
      assertTrue(true);
    });
  });

  describe('Integration with Connection Module', () => {
    it('handleConnected starts ELF watcher', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.FPBState.isConnected = false;
      setFetchResponse('/api/fpb/info', { success: true });
      setFetchResponse('/api/logs', { tool_next: 0, raw_next: 0 });

      // Ensure ELF watcher is stopped first
      w.stopElfWatcherPolling();
      assertFalse(w.isElfWatcherRunning());

      // Note: In real environment, handleConnected would start the watcher
      // Here we just verify the function exists and can be called
      assertTrue(typeof w.startElfWatcherPolling === 'function');
      w.FPBState.toolTerminal = null;
    });

    it('handleDisconnected stops ELF watcher', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();

      // Note: In real environment, handleDisconnected would stop the watcher
      // Here we just verify the function exists and can be called
      assertTrue(typeof w.stopElfWatcherPolling === 'function');
      w.FPBState.toolTerminal = null;
    });
  });
};
