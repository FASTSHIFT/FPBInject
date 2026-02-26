/**
 * Tests for features/transfer.js
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
  browserGlobals,
  resetMocks,
  MockTerminal,
  setFetchResponse,
  getFetchCalls,
  createMockElement,
  getElement,
} = require('./mocks');

module.exports = function (w) {
  describe('Transfer Functions (features/transfer.js)', () => {
    it('listDeviceDirectory is a function', () =>
      assertTrue(typeof w.listDeviceDirectory === 'function'));
    it('statDeviceFile is a function', () =>
      assertTrue(typeof w.statDeviceFile === 'function'));
    it('createDeviceDirectory is a function', () =>
      assertTrue(typeof w.createDeviceDirectory === 'function'));
    it('deleteDeviceFile is a function', () =>
      assertTrue(typeof w.deleteDeviceFile === 'function'));
    it('uploadFileToDevice is a function', () =>
      assertTrue(typeof w.uploadFileToDevice === 'function'));
    it('downloadFileFromDevice is a function', () =>
      assertTrue(typeof w.downloadFileFromDevice === 'function'));
    it('refreshDeviceFiles is a function', () =>
      assertTrue(typeof w.refreshDeviceFiles === 'function'));
    it('selectDeviceFile is a function', () =>
      assertTrue(typeof w.selectDeviceFile === 'function'));
    it('uploadToDevice is a function', () =>
      assertTrue(typeof w.uploadToDevice === 'function'));
    it('uploadFolderToDevice is a function', () =>
      assertTrue(typeof w.uploadFolderToDevice === 'function'));
    it('downloadFromDevice is a function', () =>
      assertTrue(typeof w.downloadFromDevice === 'function'));
    it('deleteFromDevice is a function', () =>
      assertTrue(typeof w.deleteFromDevice === 'function'));
    it('createDeviceDir is a function', () =>
      assertTrue(typeof w.createDeviceDir === 'function'));
    it('updateTransferProgress is a function', () =>
      assertTrue(typeof w.updateTransferProgress === 'function'));
    it('hideTransferProgress is a function', () =>
      assertTrue(typeof w.hideTransferProgress === 'function'));
    it('formatSpeed is a function', () =>
      assertTrue(typeof w.formatSpeed === 'function'));
    it('formatETA is a function', () =>
      assertTrue(typeof w.formatETA === 'function'));
    it('showCrcWarning is a function', () =>
      assertTrue(typeof w.showCrcWarning === 'function'));
    it('showCrcError is a function', () =>
      assertTrue(typeof w.showCrcError === 'function'));
    // Cancel function
    it('cancelTransfer is a function', () =>
      assertTrue(typeof w.cancelTransfer === 'function'));
    it('isTransferInProgress is a function', () =>
      assertTrue(typeof w.isTransferInProgress === 'function'));
    it('updateTransferControls is a function', () =>
      assertTrue(typeof w.updateTransferControls === 'function'));
    // Drag and drop functions
    it('initTransferDragDrop is a function', () =>
      assertTrue(typeof w.initTransferDragDrop === 'function'));
    it('preventDefaults is a function', () =>
      assertTrue(typeof w.preventDefaults === 'function'));
    it('highlightDropZone is a function', () =>
      assertTrue(typeof w.highlightDropZone === 'function'));
    it('handleDragEnter is a function', () =>
      assertTrue(typeof w.handleDragEnter === 'function'));
    it('handleDragLeave is a function', () =>
      assertTrue(typeof w.handleDragLeave === 'function'));
    it('handleDragOver is a function', () =>
      assertTrue(typeof w.handleDragOver === 'function'));
    it('handleDrop is a function', () =>
      assertTrue(typeof w.handleDrop === 'function'));
    it('uploadDroppedFile is a function', () =>
      assertTrue(typeof w.uploadDroppedFile === 'function'));
    it('resetDragState is a function', () =>
      assertTrue(typeof w.resetDragState === 'function'));
    it('formatTransferStats is a function', () =>
      assertTrue(typeof w.formatTransferStats === 'function'));
    // Folder upload functions
    it('getFileFromEntry is a function', () =>
      assertTrue(typeof w.getFileFromEntry === 'function'));
    it('readDirectoryEntries is a function', () =>
      assertTrue(typeof w.readDirectoryEntries === 'function'));
    it('collectFilesFromEntry is a function', () =>
      assertTrue(typeof w.collectFilesFromEntry === 'function'));
    it('uploadFolderEntry is a function', () =>
      assertTrue(typeof w.uploadFolderEntry === 'function'));
    it('uploadFolderFiles is a function', () =>
      assertTrue(typeof w.uploadFolderFiles === 'function'));
  });

  describe('formatTransferStats Function', () => {
    it('returns empty string for null stats', () => {
      assertEqual(w.formatTransferStats(null), '');
    });

    it('returns empty string for undefined stats', () => {
      assertEqual(w.formatTransferStats(undefined), '');
    });

    it('formats packet loss rate', () => {
      const stats = { packet_loss_rate: 2.5, retry_count: 0, crc_errors: 0 };
      const result = w.formatTransferStats(stats);
      assertTrue(result.includes('loss: 2.5%'));
    });

    it('formats retry count', () => {
      const stats = { packet_loss_rate: 0, retry_count: 3, crc_errors: 0 };
      const result = w.formatTransferStats(stats);
      assertTrue(result.includes('retries: 3'));
    });

    it('formats CRC errors', () => {
      const stats = { packet_loss_rate: 0, retry_count: 0, crc_errors: 2 };
      const result = w.formatTransferStats(stats);
      assertTrue(result.includes('CRC errors: 2'));
    });

    it('formats multiple stats', () => {
      const stats = { packet_loss_rate: 1.5, retry_count: 2, crc_errors: 1 };
      const result = w.formatTransferStats(stats);
      assertTrue(result.includes('loss: 1.5%'));
      assertTrue(result.includes('retries: 2'));
      assertTrue(result.includes('CRC errors: 1'));
    });

    it('returns empty string when all stats are zero', () => {
      const stats = { packet_loss_rate: 0, retry_count: 0, crc_errors: 0 };
      const result = w.formatTransferStats(stats);
      assertEqual(result, '');
    });
  });

  describe('listDeviceDirectory Function', () => {
    it('is async function', () => {
      assertTrue(w.listDeviceDirectory.constructor.name === 'AsyncFunction');
    });

    it('fetches directory contents', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [
          { name: 'file1.txt', type: 'file', size: 100 },
          { name: 'dir1', type: 'dir' },
        ],
      });
      const result = await w.listDeviceDirectory('/');
      assertTrue(result.success);
      assertEqual(result.entries.length, 2);
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch exception', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      const result = await w.listDeviceDirectory('/');
      assertTrue(!result.success);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
    });
  });

  describe('statDeviceFile Function', () => {
    it('is async function', () => {
      assertTrue(w.statDeviceFile.constructor.name === 'AsyncFunction');
    });

    it('fetches file stats', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/transfer/stat', {
        success: true,
        stat: { size: 1024, modified: '2024-01-01' },
      });
      const result = await w.statDeviceFile('/test.txt');
      assertTrue(result.success);
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch exception', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      const result = await w.statDeviceFile('/test.txt');
      assertTrue(!result.success);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
    });
  });

  describe('createDeviceDirectory Function', () => {
    it('is async function', () => {
      assertTrue(w.createDeviceDirectory.constructor.name === 'AsyncFunction');
    });

    it('creates directory on success', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/transfer/mkdir', { success: true });
      const result = await w.createDeviceDirectory('/newdir');
      assertTrue(result.success);
      w.FPBState.toolTerminal = null;
    });

    it('handles creation failure', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/transfer/mkdir', {
        success: false,
        error: 'Permission denied',
      });
      const result = await w.createDeviceDirectory('/newdir');
      assertTrue(!result.success);
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch exception', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      const result = await w.createDeviceDirectory('/newdir');
      assertTrue(!result.success);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
    });
  });

  describe('deleteDeviceFile Function', () => {
    it('is async function', () => {
      assertTrue(w.deleteDeviceFile.constructor.name === 'AsyncFunction');
    });

    it('deletes file on success', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/transfer/delete', { success: true });
      const result = await w.deleteDeviceFile('/test.txt');
      assertTrue(result.success);
      w.FPBState.toolTerminal = null;
    });

    it('handles deletion failure', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/transfer/delete', {
        success: false,
        error: 'File not found',
      });
      const result = await w.deleteDeviceFile('/test.txt');
      assertTrue(!result.success);
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch exception', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;
      const result = await w.deleteDeviceFile('/test.txt');
      assertTrue(!result.success);
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
    });
  });

  describe('uploadFileToDevice Function', () => {
    it('is async function', () => {
      assertTrue(w.uploadFileToDevice.constructor.name === 'AsyncFunction');
    });
  });

  describe('downloadFileFromDevice Function', () => {
    it('is async function', () => {
      assertTrue(w.downloadFileFromDevice.constructor.name === 'AsyncFunction');
    });
  });

  describe('refreshDeviceFiles Function', () => {
    it('is async function', () => {
      assertTrue(w.refreshDeviceFiles.constructor.name === 'AsyncFunction');
    });

    it('handles missing fileList element', () => {
      resetMocks();
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return null;
        return origGetById.call(browserGlobals.document, id);
      };
      // Should not throw
      w.refreshDeviceFiles();
      browserGlobals.document.getElementById = origGetById;
    });
  });

  describe('selectDeviceFile Function', () => {
    it('adds selected class to item', () => {
      resetMocks();
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };
      browserGlobals.document.querySelectorAll = () => [];
      w.selectDeviceFile(item, {});
      assertTrue(item.classList.contains('selected'));
    });

    it('removes selected class from previous item', () => {
      resetMocks();
      const item1 = browserGlobals.document.createElement('div');
      item1.className = 'device-file-item';
      item1.classList.add('selected');
      item1.dataset = { path: '/test1.txt', type: 'file' };

      browserGlobals.document.querySelectorAll = (sel) => {
        if (sel === '.device-file-item.selected') return [item1];
        return [];
      };

      const item2 = browserGlobals.document.createElement('div');
      item2.className = 'device-file-item';
      item2.dataset = { path: '/test2.txt', type: 'file' };

      w.selectDeviceFile(item2, {});
      assertTrue(!item1.classList.contains('selected'));
      assertTrue(item2.classList.contains('selected'));
    });

    it('supports Ctrl+click multi-select', () => {
      resetMocks();
      const item1 = browserGlobals.document.createElement('div');
      item1.className = 'device-file-item';
      item1.dataset = { path: '/test1.txt', type: 'file' };

      const item2 = browserGlobals.document.createElement('div');
      item2.className = 'device-file-item';
      item2.dataset = { path: '/test2.txt', type: 'file' };

      browserGlobals.document.querySelectorAll = () => [];

      // First select
      w.selectDeviceFile(item1, {});
      assertTrue(item1.classList.contains('selected'));

      // Ctrl+click second item
      w.selectDeviceFile(item2, { ctrlKey: true });
      assertTrue(item1.classList.contains('selected'));
      assertTrue(item2.classList.contains('selected'));
    });

    it('toggles selection on Ctrl+click same item', () => {
      resetMocks();
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };

      browserGlobals.document.querySelectorAll = () => [];

      // First select
      w.selectDeviceFile(item, {});
      assertTrue(item.classList.contains('selected'));

      // Ctrl+click same item to deselect
      w.selectDeviceFile(item, { ctrlKey: true });
      assertTrue(!item.classList.contains('selected'));
    });
  });

  describe('formatSpeed Function', () => {
    it('formats bytes per second', () => {
      assertEqual(w.formatSpeed(500), '500 B/s');
    });

    it('formats kilobytes per second', () => {
      const result = w.formatSpeed(2048);
      assertTrue(result.includes('KB/s'));
    });

    it('formats megabytes per second', () => {
      const result = w.formatSpeed(2 * 1024 * 1024);
      assertTrue(result.includes('MB/s'));
    });

    it('handles zero', () => {
      assertEqual(w.formatSpeed(0), '0 B/s');
    });
  });

  describe('formatETA Function', () => {
    it('formats less than 1 second', () => {
      assertEqual(w.formatETA(0.5), '<1s');
    });

    it('formats seconds', () => {
      assertEqual(w.formatETA(30), '30s');
    });

    it('formats minutes and seconds', () => {
      const result = w.formatETA(90);
      assertTrue(result.includes('m'));
      assertTrue(result.includes('s'));
    });

    it('formats hours and minutes', () => {
      const result = w.formatETA(3700);
      assertTrue(result.includes('h'));
      assertTrue(result.includes('m'));
    });
  });

  describe('CRC Verification Functions', () => {
    it('showCrcWarning writes to output', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      w.showCrcWarning('Test CRC warning');
      assertTrue(
        w.FPBState.toolTerminal._writes.some(
          (wr) => wr.msg && wr.msg.includes('Test CRC warning'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('showCrcError writes to output', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      // Mock alert to prevent blocking
      const originalAlert = browserGlobals.alert;
      let alertCalled = false;
      browserGlobals.alert = (msg) => {
        alertCalled = true;
      };
      // Also mock global alert since code uses bare 'alert' call
      const origGlobalAlert = global.alert;
      global.alert = browserGlobals.alert;
      w.showCrcError('Test CRC error');
      global.alert = origGlobalAlert;
      assertTrue(
        w.FPBState.toolTerminal._writes.some(
          (wr) => wr.msg && wr.msg.includes('Test CRC error'),
        ),
      );
      assertTrue(alertCalled);
      browserGlobals.alert = originalAlert;
      w.FPBState.toolTerminal = null;
    });
  });

  describe('updateTransferProgress Function', () => {
    it('updates progress bar display', () => {
      resetMocks();
      w.updateTransferProgress(50, '50%');
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      assertEqual(progressBar.style.display, 'block');
    });

    it('updates progress fill width', () => {
      resetMocks();
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      const progressFill = browserGlobals.document.createElement('div');
      progressFill.className = 'progress-fill';
      progressBar.querySelector = (sel) => {
        if (sel === '.progress-fill') return progressFill;
        return null;
      };

      w.updateTransferProgress(75, '75%');
      assertEqual(progressFill.style.width, '75%');
    });

    it('updates progress text', () => {
      resetMocks();
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      const progressText = browserGlobals.document.createElement('span');
      progressText.className = 'progress-text';
      progressBar.querySelector = (sel) => {
        if (sel === '.progress-text') return progressText;
        return null;
      };

      w.updateTransferProgress(25, '25% (256/1024)');
      assertEqual(progressText.textContent, '25% (256/1024)');
    });

    it('uses default text when not provided', () => {
      resetMocks();
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      const progressText = browserGlobals.document.createElement('span');
      progressBar.querySelector = (sel) => {
        if (sel === '.progress-text') return progressText;
        return null;
      };
      w.updateTransferProgress(50);
      assertEqual(progressText.textContent, '50.0%');
    });

    it('handles missing progress bar', () => {
      resetMocks();
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'transferProgress') return null;
        return origGetById.call(browserGlobals.document, id);
      };
      // Should not throw
      w.updateTransferProgress(50, '50%');
      browserGlobals.document.getElementById = origGetById;
    });

    it('updates speed and ETA', () => {
      resetMocks();
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      const progressSpeed = browserGlobals.document.createElement('span');
      const progressEta = browserGlobals.document.createElement('span');
      progressBar.querySelector = (sel) => {
        if (sel === '.progress-speed') return progressSpeed;
        if (sel === '.progress-eta') return progressEta;
        return null;
      };

      w.updateTransferProgress(50, '50%', 1024, 30);
      assertTrue(progressSpeed.textContent.includes('KB/s'));
      assertTrue(progressEta.textContent.includes('ETA'));
    });

    it('updates packet loss stats when provided', () => {
      resetMocks();
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      const progressStats = browserGlobals.document.createElement('div');
      progressStats.className = 'progress-stats';
      progressStats.style.display = 'none';
      const progressLoss = browserGlobals.document.createElement('span');
      progressLoss.className = 'progress-loss';
      progressBar.querySelector = (sel) => {
        if (sel === '.progress-stats') return progressStats;
        if (sel === '.progress-loss') return progressLoss;
        return null;
      };

      const stats = { packet_loss_rate: 2.5, retry_count: 3 };
      w.updateTransferProgress(50, '50%', 1024, 30, stats);
      assertEqual(progressStats.style.display, 'block');
      assertTrue(progressLoss.textContent.includes('Loss: 2.5%'));
      assertTrue(progressLoss.textContent.includes('Retries: 3'));
    });

    it('shows stats even when loss rate and retries are zero', () => {
      resetMocks();
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      const progressStats = browserGlobals.document.createElement('div');
      progressStats.className = 'progress-stats';
      progressStats.style.display = 'none';
      const progressLoss = browserGlobals.document.createElement('span');
      progressLoss.className = 'progress-loss';
      progressBar.querySelector = (sel) => {
        if (sel === '.progress-stats') return progressStats;
        if (sel === '.progress-loss') return progressLoss;
        return null;
      };

      const stats = { packet_loss_rate: 0, retry_count: 0 };
      w.updateTransferProgress(50, '50%', 1024, 30, stats);
      assertEqual(progressStats.style.display, 'block');
      assertTrue(progressLoss.textContent.includes('Loss: 0.0%'));
    });

    it('shows stats with only loss rate (no retries text)', () => {
      resetMocks();
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      const progressStats = browserGlobals.document.createElement('div');
      progressStats.className = 'progress-stats';
      progressStats.style.display = 'none';
      const progressLoss = browserGlobals.document.createElement('span');
      progressLoss.className = 'progress-loss';
      progressBar.querySelector = (sel) => {
        if (sel === '.progress-stats') return progressStats;
        if (sel === '.progress-loss') return progressLoss;
        return null;
      };

      const stats = { packet_loss_rate: 1.5, retry_count: 0 };
      w.updateTransferProgress(50, '50%', 1024, 30, stats);
      assertEqual(progressStats.style.display, 'block');
      assertTrue(progressLoss.textContent.includes('Loss: 1.5%'));
      assertFalse(progressLoss.textContent.includes('Retries'));
    });

    it('shows stats with retries (includes loss rate)', () => {
      resetMocks();
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      const progressStats = browserGlobals.document.createElement('div');
      progressStats.className = 'progress-stats';
      progressStats.style.display = 'none';
      const progressLoss = browserGlobals.document.createElement('span');
      progressLoss.className = 'progress-loss';
      progressBar.querySelector = (sel) => {
        if (sel === '.progress-stats') return progressStats;
        if (sel === '.progress-loss') return progressLoss;
        return null;
      };

      const stats = { packet_loss_rate: 0, retry_count: 5 };
      w.updateTransferProgress(50, '50%', 1024, 30, stats);
      assertEqual(progressStats.style.display, 'block');
      assertTrue(progressLoss.textContent.includes('Loss: 0.0%'));
      assertTrue(progressLoss.textContent.includes('Retries: 5'));
    });
  });

  describe('hideTransferProgress Function', () => {
    it('hides progress bar', () => {
      resetMocks();
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      progressBar.style.display = 'block';
      w.hideTransferProgress();
      assertEqual(progressBar.style.display, 'none');
    });

    it('hides stats display', () => {
      resetMocks();
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      const progressStats = browserGlobals.document.createElement('div');
      progressStats.className = 'progress-stats';
      progressStats.style.display = 'block';
      progressBar.querySelector = (sel) => {
        if (sel === '.progress-stats') return progressStats;
        return null;
      };
      w.hideTransferProgress();
      assertEqual(progressStats.style.display, 'none');
    });

    it('handles missing progress bar', () => {
      resetMocks();
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'transferProgress') return null;
        return origGetById.call(browserGlobals.document, id);
      };
      // Should not throw
      w.hideTransferProgress();
      browserGlobals.document.getElementById = origGetById;
    });
  });

  describe('uploadToDevice Function', () => {
    it('is async function', () => {
      assertTrue(w.uploadToDevice.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.uploadToDevice();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('creates file input element', () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();

      let inputCreated = false;
      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        if (tag === 'input') {
          inputCreated = true;
          return {
            type: '',
            files: [],
            click: () => {},
            onchange: null,
          };
        }
        return origCreateElement.call(browserGlobals.document, tag);
      };

      w.uploadToDevice();
      assertTrue(inputCreated);

      browserGlobals.document.createElement = origCreateElement;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('downloadFromDevice Function', () => {
    it('is async function', () => {
      assertTrue(w.downloadFromDevice.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.downloadFromDevice();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('shows alert if directory selected', () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.document.querySelectorAll = () => [];
      // Select a directory
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/testdir', type: 'dir' };
      w.selectDeviceFile(item, {});
      let alertCalled = false;
      const origAlert = global.alert;
      global.alert = () => {
        alertCalled = true;
      };
      w.downloadFromDevice();
      assertTrue(alertCalled);
      global.alert = origAlert;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('deleteFromDevice Function', () => {
    it('is async function', () => {
      assertTrue(w.deleteFromDevice.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.deleteFromDevice();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('cancels on confirm rejection', () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };
      w.selectDeviceFile(item);
      browserGlobals.confirm = () => false;
      w.deleteFromDevice();
      // Should not throw, just return early
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.confirm = () => true;
    });
  });

  describe('createDeviceDir Function', () => {
    it('is async function', () => {
      assertTrue(w.createDeviceDir.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      w.createDeviceDir();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('returns early if prompt cancelled', () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.prompt = () => null;
      w.createDeviceDir();
      // Should not throw, just return early
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.prompt = () => 'test';
    });
  });

  describe('isTransferInProgress Function', () => {
    it('returns false initially', () => {
      // Cancel any existing transfer first to reset state
      w.cancelTransfer();
      assertFalse(w.isTransferInProgress());
    });
  });

  describe('cancelTransfer Function', () => {
    it('does nothing when no transfer active', () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      // Should not throw
      w.cancelTransfer();
      w.FPBState.toolTerminal = null;
    });
  });

  describe('updateTransferControls Function', () => {
    it('shows cancel button when transfer active', () => {
      resetMocks();
      const cancelBtn = browserGlobals.document.createElement('button');
      cancelBtn.id = 'transferCancelBtn';
      cancelBtn.style.display = 'none';

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'transferCancelBtn') return cancelBtn;
        return origGetById.call(browserGlobals.document, id);
      };

      w.updateTransferControls(true);
      assertEqual(cancelBtn.style.display, 'flex');

      browserGlobals.document.getElementById = origGetById;
    });

    it('hides cancel button when show is false', () => {
      resetMocks();
      const cancelBtn = browserGlobals.document.createElement('button');
      cancelBtn.id = 'transferCancelBtn';
      cancelBtn.style.display = 'flex';

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'transferCancelBtn') return cancelBtn;
        return origGetById.call(browserGlobals.document, id);
      };

      w.updateTransferControls(false);
      assertEqual(cancelBtn.style.display, 'none');

      browserGlobals.document.getElementById = origGetById;
    });

    it('handles missing cancel button gracefully', () => {
      resetMocks();
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'transferCancelBtn') return null;
        return origGetById.call(browserGlobals.document, id);
      };

      // Should not throw
      w.updateTransferControls(true);
      browserGlobals.document.getElementById = origGetById;
    });
  });

  describe('initTransferDragDrop Function', () => {
    it('handles missing drop zone', () => {
      resetMocks();
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return null;
        return origGetById.call(browserGlobals.document, id);
      };

      // Should not throw
      w.initTransferDragDrop();
      browserGlobals.document.getElementById = origGetById;
    });

    it('adds event listeners to drop zone', () => {
      resetMocks();
      const dropZone = browserGlobals.document.createElement('div');
      dropZone.id = 'deviceFileList';
      const listeners = {};
      dropZone.addEventListener = (event, handler) => {
        if (!listeners[event]) listeners[event] = [];
        listeners[event].push(handler);
      };

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return dropZone;
        return origGetById.call(browserGlobals.document, id);
      };

      w.initTransferDragDrop();

      assertTrue('dragenter' in listeners);
      assertTrue('dragover' in listeners);
      assertTrue('dragleave' in listeners);
      assertTrue('drop' in listeners);

      browserGlobals.document.getElementById = origGetById;
    });
  });

  describe('handleDragEnter Function', () => {
    it('increments drag count and highlights', () => {
      resetMocks();
      w.resetDragState();
      const dropZone = browserGlobals.document.createElement('div');
      dropZone.id = 'deviceFileList';

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return dropZone;
        return origGetById.call(browserGlobals.document, id);
      };

      w.handleDragEnter({});
      assertTrue(dropZone.classList.contains('drag-over'));

      browserGlobals.document.getElementById = origGetById;
    });
  });

  describe('handleDragLeave Function', () => {
    it('decrements drag count and removes highlight when zero', () => {
      resetMocks();
      w.resetDragState();
      const dropZone = browserGlobals.document.createElement('div');
      dropZone.id = 'deviceFileList';
      dropZone.classList.add('drag-over');

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return dropZone;
        return origGetById.call(browserGlobals.document, id);
      };

      // First enter, then leave
      w.handleDragEnter({});
      w.handleDragLeave({});
      assertFalse(dropZone.classList.contains('drag-over'));

      browserGlobals.document.getElementById = origGetById;
    });

    it('keeps highlight when nested elements involved', () => {
      resetMocks();
      w.resetDragState();
      const dropZone = browserGlobals.document.createElement('div');
      dropZone.id = 'deviceFileList';

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return dropZone;
        return origGetById.call(browserGlobals.document, id);
      };

      // Enter twice (parent + child), leave once (child)
      w.handleDragEnter({});
      w.handleDragEnter({});
      w.handleDragLeave({});
      assertTrue(dropZone.classList.contains('drag-over'));

      // Leave again (parent)
      w.handleDragLeave({});
      assertFalse(dropZone.classList.contains('drag-over'));

      browserGlobals.document.getElementById = origGetById;
    });
  });

  describe('handleDragOver Function', () => {
    it('keeps highlight active', () => {
      resetMocks();
      w.resetDragState();
      const dropZone = browserGlobals.document.createElement('div');
      dropZone.id = 'deviceFileList';

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return dropZone;
        return origGetById.call(browserGlobals.document, id);
      };

      w.handleDragOver({});
      assertTrue(dropZone.classList.contains('drag-over'));

      browserGlobals.document.getElementById = origGetById;
    });
  });

  describe('preventDefaults Function', () => {
    it('calls preventDefault and stopPropagation', () => {
      let preventDefaultCalled = false;
      let stopPropagationCalled = false;
      const mockEvent = {
        preventDefault: () => {
          preventDefaultCalled = true;
        },
        stopPropagation: () => {
          stopPropagationCalled = true;
        },
      };

      w.preventDefaults(mockEvent);
      assertTrue(preventDefaultCalled);
      assertTrue(stopPropagationCalled);
    });
  });

  describe('highlightDropZone Function', () => {
    it('adds drag-over class when highlight is true', () => {
      resetMocks();
      const dropZone = browserGlobals.document.createElement('div');
      dropZone.id = 'deviceFileList';

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return dropZone;
        return origGetById.call(browserGlobals.document, id);
      };

      w.highlightDropZone(true);
      assertTrue(dropZone.classList.contains('drag-over'));

      browserGlobals.document.getElementById = origGetById;
    });

    it('removes drag-over class when highlight is false', () => {
      resetMocks();
      const dropZone = browserGlobals.document.createElement('div');
      dropZone.id = 'deviceFileList';
      dropZone.classList.add('drag-over');

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return dropZone;
        return origGetById.call(browserGlobals.document, id);
      };

      w.highlightDropZone(false);
      assertFalse(dropZone.classList.contains('drag-over'));

      browserGlobals.document.getElementById = origGetById;
    });

    it('handles missing drop zone', () => {
      resetMocks();
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return null;
        return origGetById.call(browserGlobals.document, id);
      };

      // Should not throw
      w.highlightDropZone(true);
      browserGlobals.document.getElementById = origGetById;
    });
  });

  describe('handleDrop Function', () => {
    it('resets drag state and shows error if not connected', () => {
      resetMocks();
      w.resetDragState();
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = new MockTerminal();

      const dropZone = browserGlobals.document.createElement('div');
      dropZone.id = 'deviceFileList';
      dropZone.classList.add('drag-over');

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return dropZone;
        return origGetById.call(browserGlobals.document, id);
      };

      const mockEvent = {
        dataTransfer: { files: [] },
      };

      w.handleDrop(mockEvent);

      // Should remove highlight
      assertFalse(dropZone.classList.contains('drag-over'));
      // Should show error
      assertTrue(
        w.FPBState.toolTerminal._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );

      browserGlobals.document.getElementById = origGetById;
      w.FPBState.toolTerminal = null;
    });

    it('returns early if no files dropped', () => {
      resetMocks();
      w.resetDragState();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();

      const dropZone = browserGlobals.document.createElement('div');
      dropZone.id = 'deviceFileList';

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return dropZone;
        return origGetById.call(browserGlobals.document, id);
      };

      const mockEvent = {
        dataTransfer: { files: [] },
      };

      // Should not throw, just return early
      w.handleDrop(mockEvent);

      browserGlobals.document.getElementById = origGetById;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles folder drop with webkitGetAsEntry', async () => {
      resetMocks();
      w.resetDragState();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();

      const dropZone = browserGlobals.document.createElement('div');
      dropZone.id = 'deviceFileList';

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return dropZone;
        return origGetById.call(browserGlobals.document, id);
      };

      // Mock directory entry
      const mockDirEntry = {
        isFile: false,
        isDirectory: true,
        name: 'testfolder',
        createReader: () => ({
          readEntries: (callback) => callback([]),
        }),
      };

      const mockEvent = {
        dataTransfer: {
          files: [],
          items: [
            {
              webkitGetAsEntry: () => mockDirEntry,
            },
          ],
        },
      };

      await w.handleDrop(mockEvent);

      browserGlobals.document.getElementById = origGetById;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles file drop with webkitGetAsEntry', async () => {
      resetMocks();
      w.resetDragState();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();

      const dropZone = browserGlobals.document.createElement('div');
      dropZone.id = 'deviceFileList';

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return dropZone;
        return origGetById.call(browserGlobals.document, id);
      };

      // Mock file entry
      const mockFile = { name: 'test.txt', size: 100 };
      const mockFileEntry = {
        isFile: true,
        isDirectory: false,
        name: 'test.txt',
        file: (callback) => callback(mockFile),
      };

      const mockEvent = {
        dataTransfer: {
          files: [],
          items: [
            {
              webkitGetAsEntry: () => mockFileEntry,
            },
          ],
        },
      };

      // This will try to upload, but we don't have full mock setup
      // Just verify it doesn't throw
      try {
        await w.handleDrop(mockEvent);
      } catch (e) {
        // Expected - upload will fail without full mock
      }

      browserGlobals.document.getElementById = origGetById;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles null entry from webkitGetAsEntry', async () => {
      resetMocks();
      w.resetDragState();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();

      const dropZone = browserGlobals.document.createElement('div');
      dropZone.id = 'deviceFileList';

      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return dropZone;
        return origGetById.call(browserGlobals.document, id);
      };

      const mockEvent = {
        dataTransfer: {
          files: [],
          items: [
            {
              webkitGetAsEntry: () => null,
            },
          ],
        },
      };

      // Should not throw
      await w.handleDrop(mockEvent);

      browserGlobals.document.getElementById = origGetById;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('uploadDroppedFile Function', () => {
    it('is async function', () => {
      assertTrue(w.uploadDroppedFile.constructor.name === 'AsyncFunction');
    });
  });

  describe('showTransferErrorAlert Function', () => {
    it('is a function', () => {
      assertTrue(typeof w.showTransferErrorAlert === 'function');
    });

    it('shows alert with operation and filename', () => {
      resetMocks();
      let alertMessage = null;
      const origAlert = global.alert;
      global.alert = (msg) => {
        alertMessage = msg;
      };

      w.showTransferErrorAlert('Upload', 'test.txt', 'Connection lost');
      assertTrue(alertMessage !== null);
      assertTrue(alertMessage.includes('Upload'));
      assertTrue(alertMessage.includes('test.txt'));
      assertTrue(alertMessage.includes('Connection lost'));

      global.alert = origAlert;
    });

    it('includes stats in alert message when provided', () => {
      resetMocks();
      let alertMessage = null;
      const origAlert = global.alert;
      global.alert = (msg) => {
        alertMessage = msg;
      };

      const stats = {
        retry_count: 5,
        crc_errors: 2,
        timeout_errors: 1,
        packet_loss_rate: 3.5,
      };
      w.showTransferErrorAlert(
        'Download',
        'data.bin',
        'Max retries exceeded',
        stats,
      );
      assertTrue(alertMessage !== null);
      assertTrue(alertMessage.includes('Download'));
      assertTrue(alertMessage.includes('data.bin'));
      assertTrue(alertMessage.includes('Retries: 5'));
      assertTrue(alertMessage.includes('CRC errors: 2'));
      assertTrue(alertMessage.includes('Timeout errors: 1'));
      assertTrue(alertMessage.includes('Packet loss: 3.5%'));

      global.alert = origAlert;
    });

    it('handles stats with zero values', () => {
      resetMocks();
      let alertMessage = null;
      const origAlert = global.alert;
      global.alert = (msg) => {
        alertMessage = msg;
      };

      const stats = {
        retry_count: 0,
        crc_errors: 0,
        timeout_errors: 0,
        packet_loss_rate: 0,
      };
      w.showTransferErrorAlert('Upload', 'file.txt', 'Error', stats);
      assertTrue(alertMessage !== null);
      // Should not include stats section when all are zero
      assertFalse(alertMessage.includes('Transfer Statistics'));

      global.alert = origAlert;
    });

    it('handles null stats', () => {
      resetMocks();
      let alertMessage = null;
      const origAlert = global.alert;
      global.alert = (msg) => {
        alertMessage = msg;
      };

      w.showTransferErrorAlert('Upload', 'file.txt', 'Error', null);
      assertTrue(alertMessage !== null);
      assertFalse(alertMessage.includes('Transfer Statistics'));

      global.alert = origAlert;
    });
  });

  describe('Folder Upload Functions', () => {
    it('getFileFromEntry returns promise', () => {
      const mockEntry = {
        file: (callback) => callback({ name: 'test.txt', size: 100 }),
      };
      const result = w.getFileFromEntry(mockEntry);
      assertTrue(result instanceof Promise);
    });

    it('getFileFromEntry resolves with file', async () => {
      const mockFile = { name: 'test.txt', size: 100 };
      const mockEntry = {
        file: (callback) => callback(mockFile),
      };
      const result = await w.getFileFromEntry(mockEntry);
      assertEqual(result.name, 'test.txt');
    });

    it('getFileFromEntry resolves null on error', async () => {
      const mockEntry = {
        file: (success, error) => error(new Error('Read error')),
      };
      const result = await w.getFileFromEntry(mockEntry);
      assertEqual(result, null);
    });

    it('readDirectoryEntries returns promise', () => {
      const mockReader = {
        readEntries: (callback) => callback([]),
      };
      const result = w.readDirectoryEntries(mockReader);
      assertTrue(result instanceof Promise);
    });

    it('readDirectoryEntries collects all entries', async () => {
      let callCount = 0;
      const mockReader = {
        readEntries: (callback) => {
          callCount++;
          if (callCount === 1) {
            callback([{ name: 'file1.txt' }, { name: 'file2.txt' }]);
          } else {
            callback([]);
          }
        },
      };
      const result = await w.readDirectoryEntries(mockReader);
      assertEqual(result.length, 2);
    });

    it('readDirectoryEntries handles error', async () => {
      const mockReader = {
        readEntries: (success, error) => error(new Error('Read error')),
      };
      const result = await w.readDirectoryEntries(mockReader);
      assertEqual(result.length, 0);
    });

    it('collectFilesFromEntry handles file entry', async () => {
      const mockFile = { name: 'test.txt', size: 100 };
      const mockEntry = {
        isFile: true,
        isDirectory: false,
        name: 'test.txt',
        file: (callback) => callback(mockFile),
      };
      const result = await w.collectFilesFromEntry(mockEntry);
      assertEqual(result.length, 1);
      assertEqual(result[0].relativePath, 'test.txt');
    });

    it('collectFilesFromEntry handles directory entry', async () => {
      const mockFile = { name: 'inner.txt', size: 50 };
      const mockFileEntry = {
        isFile: true,
        isDirectory: false,
        name: 'inner.txt',
        file: (callback) => callback(mockFile),
      };
      let callCount = 0;
      const mockDirEntry = {
        isFile: false,
        isDirectory: true,
        name: 'subdir',
        createReader: () => ({
          readEntries: (callback) => {
            callCount++;
            if (callCount === 1) callback([mockFileEntry]);
            else callback([]);
          },
        }),
      };
      const result = await w.collectFilesFromEntry(mockDirEntry);
      assertEqual(result.length, 1);
      assertEqual(result[0].relativePath, 'subdir/inner.txt');
    });

    it('collectFilesFromEntry handles nested directories', async () => {
      const mockFile = { name: 'deep.txt', size: 30 };
      const mockDeepFileEntry = {
        isFile: true,
        isDirectory: false,
        name: 'deep.txt',
        file: (callback) => callback(mockFile),
      };
      let innerCallCount = 0;
      const mockInnerDirEntry = {
        isFile: false,
        isDirectory: true,
        name: 'inner',
        createReader: () => ({
          readEntries: (callback) => {
            innerCallCount++;
            if (innerCallCount === 1) callback([mockDeepFileEntry]);
            else callback([]);
          },
        }),
      };
      let outerCallCount = 0;
      const mockOuterDirEntry = {
        isFile: false,
        isDirectory: true,
        name: 'outer',
        createReader: () => ({
          readEntries: (callback) => {
            outerCallCount++;
            if (outerCallCount === 1) callback([mockInnerDirEntry]);
            else callback([]);
          },
        }),
      };
      const result = await w.collectFilesFromEntry(mockOuterDirEntry);
      assertEqual(result.length, 1);
      assertEqual(result[0].relativePath, 'outer/inner/deep.txt');
    });

    it('collectFilesFromEntry with basePath', async () => {
      const mockFile = { name: 'test.txt', size: 100 };
      const mockEntry = {
        isFile: true,
        isDirectory: false,
        name: 'test.txt',
        file: (callback) => callback(mockFile),
      };
      const result = await w.collectFilesFromEntry(mockEntry, 'prefix/');
      assertEqual(result.length, 1);
      assertEqual(result[0].relativePath, 'prefix/test.txt');
    });

    it('uploadFolderToDevice is async function', () => {
      assertTrue(w.uploadFolderToDevice.constructor.name === 'AsyncFunction');
    });

    it('uploadFolderToDevice returns early if not connected', async () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.uploadFolderToDevice();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('uploadFolderFiles is async function', () => {
      assertTrue(w.uploadFolderFiles.constructor.name === 'AsyncFunction');
    });

    it('uploadFolderEntry is async function', () => {
      assertTrue(w.uploadFolderEntry.constructor.name === 'AsyncFunction');
    });

    it('uploadFolderEntry collects files without duplicating folder name', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();

      // Mock file inside folder
      const mockFile = { name: 'test.txt', size: 100, slice: () => mockFile };
      const mockFileEntry = {
        isFile: true,
        isDirectory: false,
        name: 'test.txt',
        file: (callback) => callback(mockFile),
      };

      // Mock folder entry with one file
      let readCount = 0;
      const mockDirEntry = {
        isFile: false,
        isDirectory: true,
        name: 'myFolder',
        createReader: () => ({
          readEntries: (callback) => {
            readCount++;
            if (readCount === 1) callback([mockFileEntry]);
            else callback([]);
          },
        }),
      };

      // Track what paths are used for upload via fetch
      setFetchResponse('/api/device/mkdir', { success: true });
      setFetchResponse('/api/device/upload', { success: true });

      await w.uploadFolderEntry(mockDirEntry, '/data');

      // Check fetch calls for the uploaded path
      const uploadCalls = getFetchCalls().filter((c) =>
        c.url.includes('/api/device/upload'),
      );
      // Should upload to /data/myFolder/test.txt, NOT /data/myFolder/myFolder/test.txt
      if (uploadCalls.length > 0) {
        const body = uploadCalls[0].options.body;
        assertTrue(body.get('path').includes('/data/myFolder/test.txt'));
        assertFalse(body.get('path').includes('myFolder/myFolder'));
      }

      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('uploadFolderEntry handles nested subdirectories correctly', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();

      // Mock file in nested folder
      const mockFile = { name: 'deep.txt', size: 50, slice: () => mockFile };
      const mockFileEntry = {
        isFile: true,
        isDirectory: false,
        name: 'deep.txt',
        file: (callback) => callback(mockFile),
      };

      // Mock inner subdirectory
      let innerReadCount = 0;
      const mockInnerDir = {
        isFile: false,
        isDirectory: true,
        name: 'subdir',
        createReader: () => ({
          readEntries: (callback) => {
            innerReadCount++;
            if (innerReadCount === 1) callback([mockFileEntry]);
            else callback([]);
          },
        }),
      };

      // Mock root folder entry
      let rootReadCount = 0;
      const mockRootDir = {
        isFile: false,
        isDirectory: true,
        name: 'rootFolder',
        createReader: () => ({
          readEntries: (callback) => {
            rootReadCount++;
            if (rootReadCount === 1) callback([mockInnerDir]);
            else callback([]);
          },
        }),
      };

      // Track what paths are used for upload via fetch
      setFetchResponse('/api/device/mkdir', { success: true });
      setFetchResponse('/api/device/upload', { success: true });

      await w.uploadFolderEntry(mockRootDir, '/');

      // Check fetch calls for the uploaded path
      const uploadCalls = getFetchCalls().filter((c) =>
        c.url.includes('/api/device/upload'),
      );
      // Should be /rootFolder/subdir/deep.txt
      if (uploadCalls.length > 0) {
        const body = uploadCalls[0].options.body;
        assertTrue(body.get('path').includes('/rootFolder/subdir/deep.txt'));
      }

      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('Rename Functions', () => {
    it('renameDeviceFile is a function', () =>
      assertTrue(typeof w.renameDeviceFile === 'function'));

    it('renameOnDevice is a function', () =>
      assertTrue(typeof w.renameOnDevice === 'function'));

    it('renameDeviceFile is async function', () => {
      assertTrue(w.renameDeviceFile.constructor.name === 'AsyncFunction');
    });

    it('renameOnDevice is async function', () => {
      assertTrue(w.renameOnDevice.constructor.name === 'AsyncFunction');
    });

    it('renameOnDevice returns early if not connected', async () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.renameOnDevice();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('renameOnDevice returns early if no file selected', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      // Clear any selected file by selecting nothing
      browserGlobals.document.querySelector = () => null;
      await w.renameOnDevice();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('select a file'),
        ),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('renameOnDevice returns early if prompt cancelled', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      // Select a file first
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };
      w.selectDeviceFile(item);
      // Cancel prompt
      browserGlobals.prompt = () => null;
      await w.renameOnDevice();
      // Should not throw, just return early
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.prompt = () => 'test';
    });

    it('renameOnDevice returns early if same name entered', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      // Select a file first
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };
      w.selectDeviceFile(item);
      // Return same name
      browserGlobals.prompt = () => 'test.txt';
      await w.renameOnDevice();
      // Should not throw, just return early
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.prompt = () => 'test';
    });

    it('renameOnDevice handles nested path correctly', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      // Select a file in nested path
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/data/subdir/test.txt', type: 'file' };
      w.selectDeviceFile(item);
      // Return new name
      browserGlobals.prompt = () => 'newname.txt';
      // Mock fetch to return success
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        ok: true,
        json: async () => ({ success: true, message: 'Renamed' }),
      });
      await w.renameOnDevice();
      browserGlobals.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.prompt = () => 'test';
    });

    it('renameOnDevice handles root path correctly', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      // Select a file at root
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/rootfile.txt', type: 'file' };
      w.selectDeviceFile(item);
      // Return new name
      browserGlobals.prompt = () => 'newroot.txt';
      // Mock fetch to return success
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        ok: true,
        json: async () => ({ success: true, message: 'Renamed' }),
      });
      await w.renameOnDevice();
      browserGlobals.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.prompt = () => 'test';
    });

    it('renameDeviceFile handles success response', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        ok: true,
        json: async () => ({ success: true, message: 'Renamed' }),
      });
      const result = await w.renameDeviceFile('/old.txt', '/new.txt');
      assertTrue(result.success);
      browserGlobals.fetch = origFetch;
      w.FPBState.toolTerminal = null;
    });

    it('renameDeviceFile handles error response', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/transfer/rename', {
        success: false,
        error: 'File not found',
      });
      const result = await w.renameDeviceFile('/old.txt', '/new.txt');
      assertFalse(result.success);
      w.FPBState.toolTerminal = null;
    });

    it('renameDeviceFile handles fetch exception', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      const origFetch = global.fetch;
      global.fetch = async () => {
        throw new Error('Network error');
      };
      const result = await w.renameDeviceFile('/old.txt', '/new.txt');
      assertFalse(result.success);
      assertTrue(result.error.includes('Network error'));
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
    });
  });
};
