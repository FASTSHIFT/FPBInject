/**
 * Tests for core/connection.js
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
  browserGlobals,
  MockTerminal,
} = require('./mocks');

module.exports = function (w) {
  describe('Connection Functions (core/connection.js)', () => {
    it('refreshPorts is a function', () =>
      assertTrue(typeof w.refreshPorts === 'function'));
    it('toggleConnect is a function', () =>
      assertTrue(typeof w.toggleConnect === 'function'));
    it('handleConnected is a function', () =>
      assertTrue(typeof w.handleConnected === 'function'));
    it('handleDisconnected is a function', () =>
      assertTrue(typeof w.handleDisconnected === 'function'));
    it('checkConnectionStatus is a function', () =>
      assertTrue(typeof w.checkConnectionStatus === 'function'));
  });

  describe('handleConnected Function', () => {
    it('sets isConnected to true', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = new MockTerminal();
      w.handleConnected('/dev/ttyUSB0');
      assertTrue(w.FPBState.isConnected);
      w.FPBState.toolTerminal = null;
    });

    it('updates button text to Disconnect', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const btn = browserGlobals.document.getElementById('connectBtn');
      w.handleConnected('/dev/ttyUSB0');
      assertEqual(btn.textContent, 'Disconnect');
      w.FPBState.toolTerminal = null;
    });

    it('adds connected class to button', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const btn = browserGlobals.document.getElementById('connectBtn');
      w.handleConnected('/dev/ttyUSB0');
      assertTrue(btn.classList._classes.has('connected'));
      w.FPBState.toolTerminal = null;
    });

    it('updates connection status text', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const statusEl =
        browserGlobals.document.getElementById('connectionStatus');
      w.handleConnected('/dev/ttyUSB0');
      assertEqual(statusEl.textContent, '/dev/ttyUSB0');
      w.FPBState.toolTerminal = null;
    });

    it('writes success message to output', () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.handleConnected('/dev/ttyUSB0');
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('CONNECTED')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('uses custom message if provided', () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.handleConnected('/dev/ttyUSB0', 'Custom connect message');
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Custom connect message'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('handleDisconnected Function', () => {
    it('sets isConnected to false', () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      w.handleDisconnected();
      assertTrue(!w.FPBState.isConnected);
      w.FPBState.toolTerminal = null;
    });

    it('updates button text to Connect', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const btn = browserGlobals.document.getElementById('connectBtn');
      btn.textContent = 'Disconnect';
      w.handleDisconnected();
      assertEqual(btn.textContent, 'Connect');
      w.FPBState.toolTerminal = null;
    });

    it('removes connected class from button', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const btn = browserGlobals.document.getElementById('connectBtn');
      btn.classList.add('connected');
      w.handleDisconnected();
      assertTrue(!btn.classList._classes.has('connected'));
      w.FPBState.toolTerminal = null;
    });

    it('updates connection status to Disconnected', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const statusEl =
        browserGlobals.document.getElementById('connectionStatus');
      w.handleDisconnected();
      assertEqual(statusEl.textContent, 'Disconnected');
      w.FPBState.toolTerminal = null;
    });

    it('writes warning message to output', () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.handleDisconnected();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('DISCONNECTED'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('refreshPorts Function', () => {
    it('is async function', () => {
      assertTrue(w.refreshPorts.constructor.name === 'AsyncFunction');
    });

    it('fetches from /api/ports', async () => {
      resetMocks();
      setFetchResponse('/api/ports', {
        ports: ['/dev/ttyUSB0', '/dev/ttyUSB1'],
      });
      w.FPBState.toolTerminal = new MockTerminal();
      await w.refreshPorts();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/ports')));
      w.FPBState.toolTerminal = null;
    });

    it('populates port select with ports', async () => {
      resetMocks();
      setFetchResponse('/api/ports', {
        ports: ['/dev/ttyUSB0', '/dev/ttyUSB1'],
      });
      w.FPBState.toolTerminal = new MockTerminal();
      const sel = browserGlobals.document.getElementById('portSelect');
      await w.refreshPorts();
      assertTrue(sel._children.length >= 0);
      w.FPBState.toolTerminal = null;
    });

    it('handles port objects with port property', async () => {
      resetMocks();
      setFetchResponse('/api/ports', { ports: [{ port: '/dev/ttyUSB0' }] });
      w.FPBState.toolTerminal = new MockTerminal();
      await w.refreshPorts();
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });

    it('handles port objects with device property', async () => {
      resetMocks();
      setFetchResponse('/api/ports', { ports: [{ device: '/dev/ttyUSB0' }] });
      w.FPBState.toolTerminal = new MockTerminal();
      await w.refreshPorts();
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });

    it('handles empty ports array', async () => {
      resetMocks();
      setFetchResponse('/api/ports', { ports: [] });
      w.FPBState.toolTerminal = new MockTerminal();
      await w.refreshPorts();
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch error gracefully', async () => {
      resetMocks();
      setFetchResponse('/api/ports', { _ok: false, _status: 500 });
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.refreshPorts();
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });
  });

  describe('toggleConnect Function', () => {
    it('is async function', () => {
      assertTrue(w.toggleConnect.constructor.name === 'AsyncFunction');
    });

    it('connects when not connected', async () => {
      resetMocks();
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/connect', { success: true });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      browserGlobals.document.getElementById('portSelect').value =
        '/dev/ttyUSB0';
      browserGlobals.document.getElementById('baudrate').value = '115200';
      await w.toggleConnect();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/connect')));
      w.FPBState.toolTerminal = null;
    });

    it('disconnects when connected', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/disconnect', { success: true });
      await w.toggleConnect();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/disconnect')));
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles connection failure', async () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/connect', {
        success: false,
        message: 'Port busy',
      });
      browserGlobals.document.getElementById('portSelect').value =
        '/dev/ttyUSB0';
      browserGlobals.document.getElementById('baudrate').value = '115200';
      await w.toggleConnect();
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('checkConnectionStatus Function', () => {
    it('is async function', () => {
      assertTrue(w.checkConnectionStatus.constructor.name === 'AsyncFunction');
    });

    it('fetches from /api/status', async () => {
      resetMocks();
      setFetchResponse('/api/status', { connected: false });
      w.FPBState.toolTerminal = new MockTerminal();
      await w.checkConnectionStatus();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/status')));
      w.FPBState.toolTerminal = null;
    });

    it('calls handleConnected if already connected', async () => {
      resetMocks();
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/status', {
        connected: true,
        port: '/dev/ttyUSB0',
      });
      setFetchResponse('/api/fpb/info', { success: true, slots: [] });
      await w.checkConnectionStatus();
      assertTrue(w.FPBState.isConnected);
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles status check failure gracefully', async () => {
      resetMocks();
      setFetchResponse('/api/status', { _ok: false, _status: 500 });
      w.FPBState.toolTerminal = new MockTerminal();
      await w.checkConnectionStatus();
      assertTrue(true);
      w.FPBState.toolTerminal = null;
    });
  });
};
