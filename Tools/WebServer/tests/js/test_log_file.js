/*========================================
  FPBInject Workbench - Log File Tests
  ========================================*/

import { describe, it, expect, beforeEach, afterEach } from './framework.js';
import { mockFetch, resetMocks } from './mocks.js';

describe('Log File Recording', () => {
  beforeEach(() => {
    resetMocks();
    document.body.innerHTML = `
      <input type="checkbox" id="logFileEnabled" />
      <input type="text" id="logFilePath" value="/tmp/test.log" />
      <div id="logFilePathRow" style="display: none;"></div>
      <div id="output"></div>
    `;
  });

  afterEach(() => {
    resetMocks();
  });

  describe('onLogFileEnabledChange', () => {
    it('should show path input when enabled', async () => {
      const checkbox = document.getElementById('logFileEnabled');
      const pathRow = document.getElementById('logFilePathRow');

      mockFetch('/api/log_file/start', {
        success: true,
      });

      checkbox.checked = true;
      await window.onLogFileEnabledChange();

      expect(pathRow.style.display).toBe('flex');
    });

    it('should hide path input when disabled', async () => {
      const checkbox = document.getElementById('logFileEnabled');
      const pathRow = document.getElementById('logFilePathRow');

      mockFetch('/api/log_file/stop', {
        success: true,
      });

      checkbox.checked = false;
      await window.onLogFileEnabledChange();

      expect(pathRow.style.display).toBe('none');
    });

    it('should start recording when enabled with valid path', async () => {
      const checkbox = document.getElementById('logFileEnabled');
      const pathInput = document.getElementById('logFilePath');

      pathInput.value = '/tmp/test.log';

      mockFetch('/api/log_file/start', {
        success: true,
      });

      checkbox.checked = true;
      await window.onLogFileEnabledChange();

      const calls = window.fetch.mock.calls;
      expect(calls.length).toBe(1);
      expect(calls[0][0]).toBe('/api/log_file/start');

      const body = JSON.parse(calls[0][1].body);
      expect(body.path).toBe('/tmp/test.log');
    });

    it('should use default path when path is empty', async () => {
      const checkbox = document.getElementById('logFileEnabled');
      const pathInput = document.getElementById('logFilePath');
      const pathRow = document.getElementById('logFilePathRow');

      pathInput.value = '';

      mockFetch('/api/log_file/start', {
        success: true,
      });

      checkbox.checked = true;
      await window.onLogFileEnabledChange();

      expect(pathInput.value).toBe('/tmp/fpb_console.log');
      expect(pathRow.style.display).toBe('flex');
    });

    it('should handle start recording error', async () => {
      const checkbox = document.getElementById('logFileEnabled');
      const pathRow = document.getElementById('logFilePathRow');

      mockFetch('/api/log_file/start', {
        success: false,
        error: 'Permission denied',
      });

      checkbox.checked = true;
      await window.onLogFileEnabledChange();

      expect(checkbox.checked).toBe(false);
      expect(pathRow.style.display).toBe('none');
    });

    it('should stop recording when disabled', async () => {
      const checkbox = document.getElementById('logFileEnabled');

      mockFetch('/api/log_file/stop', {
        success: true,
      });

      checkbox.checked = false;
      await window.onLogFileEnabledChange();

      const calls = window.fetch.mock.calls;
      expect(calls.length).toBe(1);
      expect(calls[0][0]).toBe('/api/log_file/stop');
    });

    it('should handle stop recording error', async () => {
      const checkbox = document.getElementById('logFileEnabled');

      mockFetch('/api/log_file/stop', {
        success: false,
        error: 'Not recording',
      });

      checkbox.checked = false;
      await window.onLogFileEnabledChange();

      // Should still attempt to stop
      const calls = window.fetch.mock.calls;
      expect(calls.length).toBe(1);
    });
  });

  describe('loadConfig', () => {
    it('should load log file config', async () => {
      mockFetch('/api/config', {
        log_file_enabled: true,
        log_file_path: '/tmp/test.log',
      });

      mockFetch('/api/connection/status', {
        connected: false,
      });

      await window.loadConfig();

      const checkbox = document.getElementById('logFileEnabled');
      const pathInput = document.getElementById('logFilePath');
      const pathRow = document.getElementById('logFilePathRow');

      expect(checkbox.checked).toBe(true);
      expect(pathInput.value).toBe('/tmp/test.log');
      expect(pathRow.style.display).toBe('flex');
    });

    it('should hide path row when log file disabled', async () => {
      mockFetch('/api/config', {
        log_file_enabled: false,
        log_file_path: '',
      });

      mockFetch('/api/connection/status', {
        connected: false,
      });

      await window.loadConfig();

      const pathRow = document.getElementById('logFilePathRow');
      expect(pathRow.style.display).toBe('none');
    });
  });

  describe('saveConfig', () => {
    it('should save log file config', async () => {
      const checkbox = document.getElementById('logFileEnabled');
      const pathInput = document.getElementById('logFilePath');

      checkbox.checked = true;
      pathInput.value = '/tmp/test.log';

      // Mock all required elements
      document.body.innerHTML += `
        <input type="text" id="elfPath" value="" />
        <input type="text" id="compileCommandsPath" value="" />
        <input type="text" id="toolchainPath" value="" />
        <select id="patchMode"><option value="trampoline" selected></option></select>
        <input type="number" id="chunkSize" value="128" />
        <input type="number" id="txChunkSize" value="0" />
        <input type="number" id="txChunkDelay" value="5" />
        <input type="number" id="transferMaxRetries" value="3" />
        <input type="checkbox" id="autoCompile" />
        <input type="checkbox" id="enableDecompile" />
        <input type="checkbox" id="verifyCrc" />
        <div id="watchDirsList"></div>
      `;

      mockFetch('/api/config', {
        success: true,
      });

      await window.saveConfig(true);

      const calls = window.fetch.mock.calls;
      const configCall = calls.find((call) => call[0] === '/api/config');

      expect(configCall).toBeDefined();

      const body = JSON.parse(configCall[1].body);
      expect(body.log_file_enabled).toBe(true);
      expect(body.log_file_path).toBe('/tmp/test.log');
    });
  });

  describe('browseLogFile', () => {
    it('should open file browser for log file directory', () => {
      document.body.innerHTML += `<button id="browseLogFileBtn"></button>`;

      window.FPBState = {
        fileBrowserCallback: null,
        fileBrowserFilter: '',
        fileBrowserMode: '',
      };

      window.HOME_PATH = '/home/user';
      window.openFileBrowser = (path) => {
        // Mock implementation
      };

      document.getElementById('logFileEnabled').checked = false;
      window.browseLogFile();

      expect(window.FPBState.fileBrowserFilter).toBe('');
      expect(window.FPBState.fileBrowserMode).toBe('dir');
      expect(typeof window.FPBState.fileBrowserCallback).toBe('function');
    });

    it('should not allow browsing while recording', () => {
      document.body.innerHTML += `<button id="browseLogFileBtn"></button>`;

      window.FPBState = {
        fileBrowserCallback: null,
        fileBrowserFilter: '',
        fileBrowserMode: '',
      };

      window.HOME_PATH = '/home/user';
      window.openFileBrowser = (path) => {
        throw new Error('Should not be called');
      };

      document.getElementById('logFileEnabled').checked = true;
      window.browseLogFile();

      // Should not set callback when recording
      expect(window.FPBState.fileBrowserCallback).toBe(null);
    });

    it('should append default filename when directory selected', () => {
      const pathInput = document.getElementById('logFilePath');
      document.body.innerHTML += `<button id="browseLogFileBtn"></button>`;

      window.FPBState = {
        fileBrowserCallback: null,
        fileBrowserFilter: '',
        fileBrowserMode: '',
      };

      window.HOME_PATH = '/home/user';
      window.openFileBrowser = (path) => {};
      window.onLogFilePathChange = () => {};

      document.getElementById('logFileEnabled').checked = false;
      window.browseLogFile();

      // Simulate directory selection
      window.FPBState.fileBrowserCallback('/tmp');

      expect(pathInput.value).toBe('/tmp/console.log');
    });

    it('should keep filename when file path selected', () => {
      const pathInput = document.getElementById('logFilePath');
      document.body.innerHTML += `<button id="browseLogFileBtn"></button>`;

      window.FPBState = {
        fileBrowserCallback: null,
        fileBrowserFilter: '',
        fileBrowserMode: '',
      };

      window.HOME_PATH = '/home/user';
      window.openFileBrowser = (path) => {};
      window.onLogFilePathChange = () => {};

      document.getElementById('logFileEnabled').checked = false;
      window.browseLogFile();

      // Simulate file selection
      window.FPBState.fileBrowserCallback('/tmp/my_custom.log');

      expect(pathInput.value).toBe('/tmp/my_custom.log');
    });
  });

  describe('updateLogFilePathState', () => {
    it('should disable path input when recording', () => {
      document.body.innerHTML += `<button id="browseLogFileBtn"></button>`;
      const pathInput = document.getElementById('logFilePath');
      const browseBtn = document.getElementById('browseLogFileBtn');

      window.updateLogFilePathState(true);

      expect(pathInput.disabled).toBe(true);
      expect(pathInput.style.opacity).toBe('0.5');
      expect(browseBtn.disabled).toBe(true);
      expect(browseBtn.style.opacity).toBe('0.5');
      expect(browseBtn.style.cursor).toBe('not-allowed');
    });

    it('should enable path input when not recording', () => {
      document.body.innerHTML += `<button id="browseLogFileBtn"></button>`;
      const pathInput = document.getElementById('logFilePath');
      const browseBtn = document.getElementById('browseLogFileBtn');

      window.updateLogFilePathState(false);

      expect(pathInput.disabled).toBe(false);
      expect(pathInput.style.opacity).toBe('1');
      expect(browseBtn.disabled).toBe(false);
      expect(browseBtn.style.opacity).toBe('1');
      expect(browseBtn.style.cursor).toBe('pointer');
    });
  });

  describe('onLogFilePathChange', () => {
    it('should save path when not recording', async () => {
      const pathInput = document.getElementById('logFilePath');
      pathInput.value = '/tmp/new.log';

      document.getElementById('logFileEnabled').checked = false;

      mockFetch('/api/config', {
        success: true,
      });

      await window.onLogFilePathChange();

      const calls = window.fetch.mock.calls;
      expect(calls.length).toBe(1);
      expect(calls[0][0]).toBe('/api/config');

      const body = JSON.parse(calls[0][1].body);
      expect(body.log_file_path).toBe('/tmp/new.log');
    });

    it('should not save path when recording', async () => {
      const pathInput = document.getElementById('logFilePath');
      pathInput.value = '/tmp/new.log';

      document.getElementById('logFileEnabled').checked = true;

      await window.onLogFilePathChange();

      const calls = window.fetch.mock.calls;
      expect(calls.length).toBe(0);
    });

    it('should not save empty path', async () => {
      const pathInput = document.getElementById('logFilePath');
      pathInput.value = '   ';

      document.getElementById('logFileEnabled').checked = false;

      await window.onLogFilePathChange();

      const calls = window.fetch.mock.calls;
      expect(calls.length).toBe(0);
    });
  });

  describe('status check integration', () => {
    it('should check status before starting', async () => {
      const checkbox = document.getElementById('logFileEnabled');
      const pathInput = document.getElementById('logFilePath');
      pathInput.value = '/tmp/test.log';

      mockFetch('/api/log_file/status', {
        success: true,
        enabled: false,
        path: '',
      });

      mockFetch('/api/log_file/start', {
        success: true,
      });

      checkbox.checked = true;
      await window.onLogFileEnabledChange();

      const calls = window.fetch.mock.calls;
      expect(calls[0][0]).toBe('/api/log_file/status');
      expect(calls[1][0]).toBe('/api/log_file/start');
    });

    it('should not restart if already recording same path', async () => {
      const checkbox = document.getElementById('logFileEnabled');
      const pathInput = document.getElementById('logFilePath');
      pathInput.value = '/tmp/test.log';

      mockFetch('/api/log_file/status', {
        success: true,
        enabled: true,
        path: '/tmp/test.log',
      });

      checkbox.checked = true;
      await window.onLogFileEnabledChange();

      const calls = window.fetch.mock.calls;
      expect(calls.length).toBe(1);
      expect(calls[0][0]).toBe('/api/log_file/status');
    });

    it('should stop and restart if recording different path', async () => {
      const checkbox = document.getElementById('logFileEnabled');
      const pathInput = document.getElementById('logFilePath');
      pathInput.value = '/tmp/new.log';

      mockFetch('/api/log_file/status', {
        success: true,
        enabled: true,
        path: '/tmp/old.log',
      });

      mockFetch('/api/log_file/stop', {
        success: true,
      });

      mockFetch('/api/log_file/start', {
        success: true,
      });

      checkbox.checked = true;
      await window.onLogFileEnabledChange();

      const calls = window.fetch.mock.calls;
      expect(calls[0][0]).toBe('/api/log_file/status');
      expect(calls[1][0]).toBe('/api/log_file/stop');
      expect(calls[2][0]).toBe('/api/log_file/start');
    });
  });
});
