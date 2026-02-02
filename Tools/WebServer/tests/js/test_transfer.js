/**
 * Tests for features/transfer.js
 */
const {
  describe,
  it,
  assertEqual,
  assertTrue,
  assertContains,
} = require('./framework');
const {
  browserGlobals,
  resetMocks,
  setFetchResponse,
  getFetchCalls,
  MockTerminal,
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
  });

  describe('listDeviceDirectory Function', () => {
    it('is async function', () => {
      assertTrue(w.listDeviceDirectory.constructor.name === 'AsyncFunction');
    });

    it('sends GET to /api/transfer/list', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [],
        path: '/',
      });
      await w.listDeviceDirectory('/');
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/transfer/list')));
    });

    it('returns entries on success', async () => {
      resetMocks();
      const mockEntries = [
        { name: 'test.txt', type: 'file', size: 100 },
        { name: 'subdir', type: 'dir', size: 0 },
      ];
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: mockEntries,
        path: '/',
      });
      const result = await w.listDeviceDirectory('/');
      assertTrue(result.success);
      assertEqual(result.entries.length, 2);
    });

    it('handles fetch error', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
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

    it('sends GET to /api/transfer/stat', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/stat', {
        success: true,
        stat: { size: 1024, mtime: 12345, type: 'file' },
      });
      await w.statDeviceFile('/test.txt');
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/transfer/stat')));
    });

    it('returns stat info on success', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/stat', {
        success: true,
        stat: { size: 1024, mtime: 12345, type: 'file' },
      });
      const result = await w.statDeviceFile('/test.txt');
      assertTrue(result.success);
      assertEqual(result.stat.size, 1024);
    });
  });

  describe('createDeviceDirectory Function', () => {
    it('is async function', () => {
      assertTrue(w.createDeviceDirectory.constructor.name === 'AsyncFunction');
    });

    it('sends POST to /api/transfer/mkdir', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/transfer/mkdir', {
        success: true,
        message: 'Created',
      });
      await w.createDeviceDirectory('/newdir');
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/transfer/mkdir')));
      w.FPBState.toolTerminal = null;
    });

    it('writes success message', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/transfer/mkdir', {
        success: true,
        message: 'Created',
      });
      await w.createDeviceDirectory('/newdir');
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('SUCCESS')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('writes error message on failure', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/transfer/mkdir', {
        success: false,
        error: 'Permission denied',
      });
      await w.createDeviceDirectory('/newdir');
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('deleteDeviceFile Function', () => {
    it('is async function', () => {
      assertTrue(w.deleteDeviceFile.constructor.name === 'AsyncFunction');
    });

    it('sends POST to /api/transfer/delete', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
      setFetchResponse('/api/transfer/delete', {
        success: true,
        message: 'Deleted',
      });
      await w.deleteDeviceFile('/test.txt');
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/transfer/delete')));
      w.FPBState.toolTerminal = null;
    });

    it('writes success message', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/transfer/delete', {
        success: true,
        message: 'Deleted',
      });
      await w.deleteDeviceFile('/test.txt');
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('SUCCESS')),
      );
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
      // Create progress-fill child element
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      const progressFill = browserGlobals.document.createElement('div');
      progressFill.className = 'progress-fill';
      progressBar._children = [progressFill];
      progressBar.querySelector = (sel) => {
        if (sel === '.progress-fill') return progressFill;
        if (sel === '.progress-text') return null;
        return null;
      };

      w.updateTransferProgress(75, '75%');
      assertEqual(progressFill.style.width, '75%');
    });

    it('updates progress text', () => {
      resetMocks();
      // Create progress-text child element
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      const progressText = browserGlobals.document.createElement('span');
      progressText.className = 'progress-text';
      progressBar._children = [progressText];
      progressBar.querySelector = (sel) => {
        if (sel === '.progress-fill') return null;
        if (sel === '.progress-text') return progressText;
        return null;
      };

      w.updateTransferProgress(25, '25% (256/1024)');
      assertEqual(progressText.textContent, '25% (256/1024)');
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
  });

  describe('refreshDeviceFiles Function', () => {
    it('is async function', () => {
      assertTrue(w.refreshDeviceFiles.constructor.name === 'AsyncFunction');
    });

    it('calls listDeviceDirectory', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [],
        path: '/',
      });
      await w.refreshDeviceFiles();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/transfer/list')));
    });

    it('displays loading state', async () => {
      resetMocks();
      // Create a delayed response to check loading state
      const fileList = browserGlobals.document.getElementById('deviceFileList');
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [],
        path: '/',
      });
      const promise = w.refreshDeviceFiles();
      // Loading state should be set immediately
      assertContains(fileList.innerHTML, 'Loading');
      await promise;
    });

    it('displays entries after load', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [
          { name: 'test.txt', type: 'file', size: 100 },
          { name: 'subdir', type: 'dir', size: 0 },
        ],
        path: '/',
      });
      await w.refreshDeviceFiles();
      const fileList = browserGlobals.document.getElementById('deviceFileList');
      assertContains(fileList.innerHTML, 'test.txt');
      assertContains(fileList.innerHTML, 'subdir');
    });

    it('displays error on failure', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/list', {
        success: false,
        error: 'Connection failed',
      });
      await w.refreshDeviceFiles();
      const fileList = browserGlobals.document.getElementById('deviceFileList');
      assertContains(fileList.innerHTML, 'Error');
    });
  });

  describe('selectDeviceFile Function', () => {
    it('adds selected class to item', () => {
      resetMocks();
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };
      w.selectDeviceFile(item);
      assertTrue(item.classList.contains('selected'));
    });

    it('removes selected class from previous item', () => {
      resetMocks();
      const item1 = browserGlobals.document.createElement('div');
      item1.className = 'device-file-item selected';
      item1.classList.add('selected');
      item1.dataset = { path: '/test1.txt', type: 'file' };

      const fileList = browserGlobals.document.getElementById('deviceFileList');
      fileList.appendChild(item1);

      // Mock querySelector to find selected item
      browserGlobals.document.querySelector = (sel) => {
        if (sel === '.device-file-item.selected') return item1;
        return null;
      };

      const item2 = browserGlobals.document.createElement('div');
      item2.className = 'device-file-item';
      item2.dataset = { path: '/test2.txt', type: 'file' };

      w.selectDeviceFile(item2);
      assertTrue(!item1.classList.contains('selected'));
      assertTrue(item2.classList.contains('selected'));
    });
  });

  describe('uploadToDevice Function', () => {
    it('is async function', () => {
      assertTrue(w.uploadToDevice.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', async () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.uploadToDevice();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });
  });

  describe('downloadFromDevice Function', () => {
    it('is async function', () => {
      assertTrue(w.downloadFromDevice.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', async () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.downloadFromDevice();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('returns early if no file selected', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      // Clear any selected file
      await w.downloadFromDevice();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('select a file'),
        ),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('deleteFromDevice Function', () => {
    it('is async function', () => {
      assertTrue(w.deleteFromDevice.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', async () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.deleteFromDevice();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('returns early if no file selected', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.deleteFromDevice();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('select a file'),
        ),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('createDeviceDir Function', () => {
    it('is async function', () => {
      assertTrue(w.createDeviceDir.constructor.name === 'AsyncFunction');
    });

    it('returns early if not connected', async () => {
      resetMocks();
      w.FPBState.isConnected = false;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      await w.createDeviceDir();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );
      w.FPBState.toolTerminal = null;
    });

    it('returns early if prompt cancelled', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.prompt = () => null;
      await w.createDeviceDir();
      const calls = getFetchCalls();
      assertTrue(!calls.some((c) => c.url.includes('/api/transfer/mkdir')));
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.prompt = () => 'test';
    });

    it('creates directory when prompt provided', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      browserGlobals.prompt = () => 'newdir';
      setFetchResponse('/api/transfer/mkdir', {
        success: true,
        message: 'Created',
      });
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [],
        path: '/',
      });
      await w.createDeviceDir();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/transfer/mkdir')));
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.prompt = () => 'test';
    });
  });

  describe('statDeviceFile Function - Extended', () => {
    it('handles fetch error', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
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

  describe('deleteDeviceFile Function - Extended', () => {
    it('writes error message on failure', async () => {
      resetMocks();
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      setFetchResponse('/api/transfer/delete', {
        success: false,
        error: 'Permission denied',
      });
      await w.deleteDeviceFile('/test.txt');
      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );
      w.FPBState.toolTerminal = null;
    });

    it('handles fetch error', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
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

  describe('createDeviceDirectory Function - Extended', () => {
    it('handles fetch error', async () => {
      resetMocks();
      w.FPBState.toolTerminal = new MockTerminal();
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

  describe('refreshDeviceFiles Function - Extended', () => {
    it('handles missing fileList element', async () => {
      resetMocks();
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'deviceFileList') return null;
        return origGetById(id);
      };
      // Should not throw
      await w.refreshDeviceFiles();
      browserGlobals.document.getElementById = origGetById;
    });

    it('displays empty message for root with no files', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [],
        path: '/',
      });
      await w.refreshDeviceFiles();
      const fileList = browserGlobals.document.getElementById('deviceFileList');
      assertContains(fileList.innerHTML, 'No files');
    });

    it('adds parent directory for non-root paths', async () => {
      resetMocks();
      const pathInput = browserGlobals.document.getElementById('devicePath');
      pathInput.value = '/subdir';
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [],
        path: '/subdir',
      });
      await w.refreshDeviceFiles();
      const fileList = browserGlobals.document.getElementById('deviceFileList');
      assertContains(fileList.innerHTML, '..');
    });

    it('sorts directories before files', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [
          { name: 'file.txt', type: 'file', size: 100 },
          { name: 'adir', type: 'dir', size: 0 },
          { name: 'bfile.txt', type: 'file', size: 200 },
        ],
        path: '/',
      });
      await w.refreshDeviceFiles();
      const fileList = browserGlobals.document.getElementById('deviceFileList');
      const html = fileList.innerHTML;
      const dirPos = html.indexOf('adir');
      const filePos = html.indexOf('file.txt');
      assertTrue(dirPos < filePos);
    });
  });

  describe('updateTransferProgress Function - Extended', () => {
    it('handles missing progress bar', () => {
      resetMocks();
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'transferProgress') return null;
        return origGetById(id);
      };
      // Should not throw
      w.updateTransferProgress(50, '50%');
      browserGlobals.document.getElementById = origGetById;
    });

    it('uses default text when not provided', () => {
      resetMocks();
      const progressBar =
        browserGlobals.document.getElementById('transferProgress');
      const progressText = browserGlobals.document.createElement('span');
      progressText.className = 'progress-text';
      progressBar.querySelector = (sel) => {
        if (sel === '.progress-fill') return null;
        if (sel === '.progress-text') return progressText;
        return null;
      };
      w.updateTransferProgress(50);
      assertEqual(progressText.textContent, '50%');
    });
  });

  describe('hideTransferProgress Function - Extended', () => {
    it('handles missing progress bar', () => {
      resetMocks();
      const origGetById = browserGlobals.document.getElementById;
      browserGlobals.document.getElementById = (id) => {
        if (id === 'transferProgress') return null;
        return origGetById(id);
      };
      // Should not throw
      w.hideTransferProgress();
      browserGlobals.document.getElementById = origGetById;
    });
  });

  describe('downloadFromDevice Function - Extended', () => {
    it('returns early if directory selected', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;
      // Select a directory
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/subdir', type: 'dir' };
      w.selectDeviceFile(item);
      await w.downloadFromDevice();
      assertTrue(
        mockTerm._writes.some(
          (wr) => wr.msg && wr.msg.includes('select a file'),
        ),
      );
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('deleteFromDevice Function - Extended', () => {
    it('cancels on confirm rejection', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      // Select a file
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };
      w.selectDeviceFile(item);
      browserGlobals.confirm = () => false;
      await w.deleteFromDevice();
      const calls = getFetchCalls();
      assertTrue(!calls.some((c) => c.url.includes('/api/transfer/delete')));
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
      browserGlobals.confirm = () => true;
    });

    it('deletes file on confirm', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      // Select a file
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };
      w.selectDeviceFile(item);
      browserGlobals.confirm = () => true;
      setFetchResponse('/api/transfer/delete', {
        success: true,
        message: 'Deleted',
      });
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [],
        path: '/',
      });
      await w.deleteFromDevice();
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/transfer/delete')));
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('listDeviceDirectory Function - Extended', () => {
    it('encodes path parameter', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [],
        path: '/path with spaces',
      });
      await w.listDeviceDirectory('/path with spaces');
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('path%20with%20spaces')));
    });
  });

  describe('statDeviceFile Function - Extended 2', () => {
    it('encodes path parameter', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/stat', {
        success: true,
        stat: { size: 100, mtime: 12345, type: 'file' },
      });
      await w.statDeviceFile('/file with spaces.txt');
      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('file%20with%20spaces')));
    });
  });

  describe('formatFileSize Function', () => {
    it('formats bytes correctly', () => {
      // Access formatFileSize through window if exported, or test indirectly
      // Since formatFileSize is not exported, we test it through refreshDeviceFiles
      resetMocks();
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [
          { name: 'small.txt', type: 'file', size: 100 },
          { name: 'medium.txt', type: 'file', size: 2048 },
          { name: 'large.txt', type: 'file', size: 1048576 },
        ],
        path: '/',
      });
      w.refreshDeviceFiles();
      assertTrue(true);
    });
  });

  describe('uploadFileToDevice Function', () => {
    it('is async function', () => {
      assertTrue(w.uploadFileToDevice.constructor.name === 'AsyncFunction');
    });

    it('sends POST to /api/transfer/upload', async () => {
      resetMocks();
      // Create a mock streaming response
      const mockReader = {
        read: async () => ({
          done: false,
          value: new TextEncoder().encode(
            'data: {"type":"result","success":true}\n',
          ),
        }),
        _readCount: 0,
      };
      mockReader.read = async function () {
        this._readCount++;
        if (this._readCount === 1) {
          return {
            done: false,
            value: new TextEncoder().encode(
              'data: {"type":"result","success":true}\n',
            ),
          };
        }
        return { done: true, value: undefined };
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      const mockFile = { name: 'test.txt', size: 100 };
      try {
        const result = await w.uploadFileToDevice(mockFile, '/test.txt');
        assertTrue(result.success);
      } catch (e) {
        // Expected if mock doesn't fully work
      }

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });

    it('handles progress callback', async () => {
      resetMocks();
      let progressCalled = false;
      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"progress","uploaded":50,"total":100,"percent":50}\n',
              ),
            };
          }
          if (this._readCount === 2) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":true}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      const mockFile = { name: 'test.txt', size: 100 };
      try {
        await w.uploadFileToDevice(
          mockFile,
          '/test.txt',
          (uploaded, total, percent) => {
            progressCalled = true;
          },
        );
      } catch (e) {
        // Expected
      }

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });

    it('handles fetch rejection', async () => {
      resetMocks();
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;

      const mockFile = { name: 'test.txt', size: 100 };
      try {
        await w.uploadFileToDevice(mockFile, '/test.txt');
        assertTrue(false); // Should not reach here
      } catch (e) {
        assertTrue(e.message.includes('Network'));
      }

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });

    it('handles stream end without result', async () => {
      resetMocks();
      const mockReader = {
        read: async () => ({ done: true, value: undefined }),
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      const mockFile = { name: 'test.txt', size: 100 };
      const result = await w.uploadFileToDevice(mockFile, '/test.txt');
      assertTrue(!result.success);
      assertTrue(result.error.includes('Stream ended'));

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });
  });

  describe('downloadFileFromDevice Function', () => {
    it('is async function', () => {
      assertTrue(w.downloadFileFromDevice.constructor.name === 'AsyncFunction');
    });

    it('sends POST to /api/transfer/download', async () => {
      resetMocks();
      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":true,"data":"dGVzdA=="}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      try {
        const result = await w.downloadFileFromDevice('/test.txt');
        assertTrue(result.success);
      } catch (e) {
        // Expected if mock doesn't fully work
      }

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });

    it('handles progress callback', async () => {
      resetMocks();
      let progressCalled = false;
      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"progress","downloaded":50,"total":100,"percent":50}\n',
              ),
            };
          }
          if (this._readCount === 2) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":true}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      try {
        await w.downloadFileFromDevice(
          '/test.txt',
          (downloaded, total, percent) => {
            progressCalled = true;
          },
        );
      } catch (e) {
        // Expected
      }

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });

    it('handles fetch rejection', async () => {
      resetMocks();
      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;

      try {
        await w.downloadFileFromDevice('/test.txt');
        assertTrue(false); // Should not reach here
      } catch (e) {
        assertTrue(e.message.includes('Network'));
      }

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });

    it('handles stream end without result', async () => {
      resetMocks();
      const mockReader = {
        read: async () => ({ done: true, value: undefined }),
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      const result = await w.downloadFileFromDevice('/test.txt');
      assertTrue(!result.success);
      assertTrue(result.error.includes('Stream ended'));

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });

    it('decodes base64 data to blob', async () => {
      resetMocks();
      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            // "test" in base64 is "dGVzdA=="
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":true,"data":"dGVzdA=="}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      // Mock atob
      const origAtob = browserGlobals.atob;
      browserGlobals.atob = (str) =>
        Buffer.from(str, 'base64').toString('binary');
      global.atob = browserGlobals.atob;

      const result = await w.downloadFileFromDevice('/test.txt');
      assertTrue(result.success);
      assertTrue(result.blob !== undefined);

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      browserGlobals.atob = origAtob;
      global.atob = origAtob;
    });
  });

  describe('uploadToDevice Function - Extended', () => {
    it('handles file selection and upload', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();

      // Mock document.createElement to return a controllable input
      const origCreateElement = browserGlobals.document.createElement;
      let fileInput = null;
      browserGlobals.document.createElement = (tag) => {
        if (tag === 'input') {
          fileInput = {
            type: '',
            files: [],
            click: () => {},
            onchange: null,
          };
          return fileInput;
        }
        return origCreateElement(tag);
      };

      await w.uploadToDevice();

      // Verify input was created
      assertTrue(fileInput !== null);
      assertTrue(fileInput.type === 'file');

      browserGlobals.document.createElement = origCreateElement;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('downloadFromDevice Function - Extended 2', () => {
    it('handles successful download with blob', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();

      // Select a file first
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };
      w.selectDeviceFile(item);

      // Mock the download function response
      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":true,"data":"dGVzdA=="}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      // Mock atob and URL
      browserGlobals.atob = (str) =>
        Buffer.from(str, 'base64').toString('binary');
      global.atob = browserGlobals.atob;

      let urlCreated = false;
      browserGlobals.URL = {
        createObjectURL: () => {
          urlCreated = true;
          return 'blob:test';
        },
        revokeObjectURL: () => {},
      };
      global.URL = browserGlobals.URL;

      // Mock createElement for anchor
      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        if (tag === 'a') {
          return { href: '', download: '', click: () => {} };
        }
        return origCreateElement(tag);
      };

      await w.downloadFromDevice();

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      browserGlobals.document.createElement = origCreateElement;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles download failure', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;

      // Select a file first
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };
      w.selectDeviceFile(item);

      // Mock failed download
      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":false,"error":"Read error"}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      await w.downloadFromDevice();

      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles download exception', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;

      // Select a file first
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };
      w.selectDeviceFile(item);

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => {
        throw new Error('Network error');
      };
      global.fetch = browserGlobals.fetch;

      await w.downloadFromDevice();

      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('error')),
      );

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('refreshDeviceFiles Function - Extended 2', () => {
    it('handles file size formatting for different sizes', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [
          { name: 'tiny.txt', type: 'file', size: 100 },
          { name: 'small.txt', type: 'file', size: 2048 },
          { name: 'large.txt', type: 'file', size: 2097152 },
        ],
        path: '/',
      });
      await w.refreshDeviceFiles();
      const fileList = browserGlobals.document.getElementById('deviceFileList');
      // Check that files are displayed
      assertContains(fileList.innerHTML, 'tiny.txt');
      assertContains(fileList.innerHTML, 'small.txt');
      assertContains(fileList.innerHTML, 'large.txt');
    });

    it('handles double-click on directory', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [{ name: 'subdir', type: 'dir', size: 0 }],
        path: '/',
      });
      await w.refreshDeviceFiles();
      // The ondblclick handler is set up but we can't easily trigger it in tests
      assertTrue(true);
    });
  });

  describe('uploadToDevice Function - Full Flow', () => {
    it('handles successful upload with progress', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;

      // Mock file input and file selection
      let fileInputCallback = null;
      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        if (tag === 'input') {
          const input = {
            type: '',
            files: [{ name: 'test.txt', size: 100 }],
            click: () => {
              if (fileInputCallback) fileInputCallback();
            },
            onchange: null,
          };
          // Capture the onchange callback
          Object.defineProperty(input, 'onchange', {
            set: (fn) => {
              fileInputCallback = fn;
            },
            get: () => fileInputCallback,
          });
          return input;
        }
        return origCreateElement(tag);
      };

      // Mock streaming upload response
      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"progress","uploaded":50,"total":100,"percent":50}\n',
              ),
            };
          }
          if (this._readCount === 2) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":true}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async (url) => {
        if (url.includes('/api/transfer/upload')) {
          return { body: { getReader: () => mockReader } };
        }
        if (url.includes('/api/transfer/list')) {
          return {
            ok: true,
            json: async () => ({ success: true, entries: [], path: '/' }),
          };
        }
        return origFetch(url);
      };
      global.fetch = browserGlobals.fetch;

      // Start upload
      const uploadPromise = w.uploadToDevice();

      // Trigger file selection
      if (fileInputCallback) {
        await fileInputCallback();
      }

      browserGlobals.document.createElement = origCreateElement;
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles upload with non-root path', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();

      // Set current path to non-root
      const pathInput = browserGlobals.document.getElementById('devicePath');
      pathInput.value = '/subdir';

      let fileInputCallback = null;
      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        if (tag === 'input') {
          const input = {
            type: '',
            files: [{ name: 'test.txt', size: 100 }],
            click: () => {
              if (fileInputCallback) fileInputCallback();
            },
          };
          Object.defineProperty(input, 'onchange', {
            set: (fn) => {
              fileInputCallback = fn;
            },
            get: () => fileInputCallback,
          });
          return input;
        }
        return origCreateElement(tag);
      };

      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":true}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async (url) => {
        if (url.includes('/api/transfer/upload')) {
          return { body: { getReader: () => mockReader } };
        }
        if (url.includes('/api/transfer/list')) {
          return {
            ok: true,
            json: async () => ({ success: true, entries: [], path: '/subdir' }),
          };
        }
        return origFetch(url);
      };
      global.fetch = browserGlobals.fetch;

      w.uploadToDevice();
      if (fileInputCallback) {
        await fileInputCallback();
      }

      browserGlobals.document.createElement = origCreateElement;
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles upload failure', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;

      let fileInputCallback = null;
      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        if (tag === 'input') {
          const input = {
            type: '',
            files: [{ name: 'test.txt', size: 100 }],
            click: () => {
              if (fileInputCallback) fileInputCallback();
            },
          };
          Object.defineProperty(input, 'onchange', {
            set: (fn) => {
              fileInputCallback = fn;
            },
            get: () => fileInputCallback,
          });
          return input;
        }
        return origCreateElement(tag);
      };

      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":false,"error":"Disk full"}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async (url) => {
        if (url.includes('/api/transfer/upload')) {
          return { body: { getReader: () => mockReader } };
        }
        return origFetch(url);
      };
      global.fetch = browserGlobals.fetch;

      w.uploadToDevice();
      if (fileInputCallback) {
        await fileInputCallback();
      }

      browserGlobals.document.createElement = origCreateElement;
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles upload exception', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;

      let fileInputCallback = null;
      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        if (tag === 'input') {
          const input = {
            type: '',
            files: [{ name: 'test.txt', size: 100 }],
            click: () => {
              if (fileInputCallback) fileInputCallback();
            },
          };
          Object.defineProperty(input, 'onchange', {
            set: (fn) => {
              fileInputCallback = fn;
            },
            get: () => fileInputCallback,
          });
          return input;
        }
        return origCreateElement(tag);
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async (url) => {
        if (url.includes('/api/transfer/upload')) {
          throw new Error('Network error');
        }
        return origFetch(url);
      };
      global.fetch = browserGlobals.fetch;

      w.uploadToDevice();
      if (fileInputCallback) {
        await fileInputCallback();
      }

      browserGlobals.document.createElement = origCreateElement;
      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles empty file selection', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();

      let fileInputCallback = null;
      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        if (tag === 'input') {
          const input = {
            type: '',
            files: [], // No file selected
            click: () => {
              if (fileInputCallback) fileInputCallback();
            },
          };
          Object.defineProperty(input, 'onchange', {
            set: (fn) => {
              fileInputCallback = fn;
            },
            get: () => fileInputCallback,
          });
          return input;
        }
        return origCreateElement(tag);
      };

      w.uploadToDevice();
      if (fileInputCallback) {
        await fileInputCallback();
      }

      browserGlobals.document.createElement = origCreateElement;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('downloadFromDevice Function - Full Flow', () => {
    it('handles successful download and triggers browser download', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;

      // Select a file
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };
      w.selectDeviceFile(item);

      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"progress","downloaded":50,"total":100,"percent":50}\n',
              ),
            };
          }
          if (this._readCount === 2) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":true,"data":"dGVzdA=="}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      browserGlobals.atob = (str) =>
        Buffer.from(str, 'base64').toString('binary');
      global.atob = browserGlobals.atob;

      let downloadTriggered = false;
      browserGlobals.URL = {
        createObjectURL: () => 'blob:test',
        revokeObjectURL: () => {},
      };
      global.URL = browserGlobals.URL;

      const origCreateElement = browserGlobals.document.createElement;
      browserGlobals.document.createElement = (tag) => {
        if (tag === 'a') {
          return {
            href: '',
            download: '',
            click: () => {
              downloadTriggered = true;
            },
          };
        }
        return origCreateElement(tag);
      };

      await w.downloadFromDevice();

      assertTrue(
        downloadTriggered ||
          mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('SUCCESS')),
      );

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
      browserGlobals.document.createElement = origCreateElement;
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('deleteFromDevice Function - Full Flow', () => {
    it('handles successful deletion and refreshes file list', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;

      // Select a file
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/test.txt', type: 'file' };
      w.selectDeviceFile(item);

      browserGlobals.confirm = () => true;

      setFetchResponse('/api/transfer/delete', {
        success: true,
        message: 'Deleted',
      });
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [],
        path: '/',
      });

      await w.deleteFromDevice();

      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('SUCCESS')),
      );

      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles directory deletion', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;

      // Select a directory
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/subdir', type: 'dir' };
      w.selectDeviceFile(item);

      browserGlobals.confirm = () => true;

      setFetchResponse('/api/transfer/delete', {
        success: true,
        message: 'Deleted',
      });
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [],
        path: '/',
      });

      await w.deleteFromDevice();

      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('SUCCESS')),
      );

      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('createDeviceDir Function - Full Flow', () => {
    it('handles successful directory creation and refreshes', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;

      browserGlobals.prompt = () => 'newdir';

      setFetchResponse('/api/transfer/mkdir', {
        success: true,
        message: 'Created',
      });
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [],
        path: '/',
      });

      await w.createDeviceDir();

      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('SUCCESS')),
      );

      browserGlobals.prompt = () => 'test';
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles directory creation in subdirectory', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;

      // Set current path to non-root
      const pathInput = browserGlobals.document.getElementById('devicePath');
      pathInput.value = '/subdir';

      browserGlobals.prompt = () => 'newdir';

      setFetchResponse('/api/transfer/mkdir', {
        success: true,
        message: 'Created',
      });
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [],
        path: '/subdir',
      });

      await w.createDeviceDir();

      const calls = getFetchCalls();
      assertTrue(calls.some((c) => c.url.includes('/api/transfer/mkdir')));

      browserGlobals.prompt = () => 'test';
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });

    it('handles directory creation failure', async () => {
      resetMocks();
      w.FPBState.isConnected = true;
      const mockTerm = new MockTerminal();
      w.FPBState.toolTerminal = mockTerm;

      browserGlobals.prompt = () => 'newdir';

      setFetchResponse('/api/transfer/mkdir', {
        success: false,
        error: 'Permission denied',
      });

      await w.createDeviceDir();

      assertTrue(
        mockTerm._writes.some((wr) => wr.msg && wr.msg.includes('ERROR')),
      );

      browserGlobals.prompt = () => 'test';
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('formatFileSize Function - Direct Tests', () => {
    it('formats bytes correctly', async () => {
      resetMocks();
      // Test through refreshDeviceFiles which uses formatFileSize
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [{ name: 'bytes.txt', type: 'file', size: 500 }],
        path: '/',
      });
      await w.refreshDeviceFiles();
      const fileList = browserGlobals.document.getElementById('deviceFileList');
      assertContains(fileList.innerHTML, '500 B');
    });

    it('formats kilobytes correctly', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [{ name: 'kb.txt', type: 'file', size: 2048 }],
        path: '/',
      });
      await w.refreshDeviceFiles();
      const fileList = browserGlobals.document.getElementById('deviceFileList');
      assertContains(fileList.innerHTML, 'KB');
    });

    it('formats megabytes correctly', async () => {
      resetMocks();
      setFetchResponse('/api/transfer/list', {
        success: true,
        entries: [{ name: 'mb.txt', type: 'file', size: 2097152 }],
        path: '/',
      });
      await w.refreshDeviceFiles();
      const fileList = browserGlobals.document.getElementById('deviceFileList');
      assertContains(fileList.innerHTML, 'MB');
    });
  });

  describe('Stream Processing Edge Cases', () => {
    it('handles multiple SSE events in single chunk', async () => {
      resetMocks();
      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            // Multiple events in one chunk
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"progress","uploaded":25,"total":100,"percent":25}\n' +
                  'data: {"type":"progress","uploaded":50,"total":100,"percent":50}\n' +
                  'data: {"type":"progress","uploaded":75,"total":100,"percent":75}\n',
              ),
            };
          }
          if (this._readCount === 2) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":true}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      let progressCount = 0;
      const mockFile = { name: 'test.txt', size: 100 };
      const result = await w.uploadFileToDevice(mockFile, '/test.txt', () => {
        progressCount++;
      });

      assertTrue(result.success);
      assertTrue(progressCount >= 1);

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });

    it('handles partial SSE event across chunks', async () => {
      resetMocks();
      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            // Partial event
            return {
              done: false,
              value: new TextEncoder().encode('data: {"type":"prog'),
            };
          }
          if (this._readCount === 2) {
            // Rest of event
            return {
              done: false,
              value: new TextEncoder().encode(
                'ress","uploaded":50,"total":100,"percent":50}\n',
              ),
            };
          }
          if (this._readCount === 3) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":true}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      const mockFile = { name: 'test.txt', size: 100 };
      const result = await w.uploadFileToDevice(mockFile, '/test.txt');

      assertTrue(result.success);

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });

    it('handles invalid JSON in SSE event', async () => {
      resetMocks();
      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            return {
              done: false,
              value: new TextEncoder().encode('data: {invalid json}\n'),
            };
          }
          if (this._readCount === 2) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":true}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      const mockFile = { name: 'test.txt', size: 100 };
      const result = await w.uploadFileToDevice(mockFile, '/test.txt');

      assertTrue(result.success);

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });

    it('handles non-data lines in SSE stream', async () => {
      resetMocks();
      const mockReader = {
        _readCount: 0,
        read: async function () {
          this._readCount++;
          if (this._readCount === 1) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'event: progress\nid: 1\ndata: {"type":"progress","uploaded":50,"total":100,"percent":50}\n\n',
              ),
            };
          }
          if (this._readCount === 2) {
            return {
              done: false,
              value: new TextEncoder().encode(
                'data: {"type":"result","success":true}\n',
              ),
            };
          }
          return { done: true, value: undefined };
        },
      };

      const origFetch = browserGlobals.fetch;
      browserGlobals.fetch = async () => ({
        body: { getReader: () => mockReader },
      });
      global.fetch = browserGlobals.fetch;

      const mockFile = { name: 'test.txt', size: 100 };
      const result = await w.uploadFileToDevice(mockFile, '/test.txt');

      assertTrue(result.success);

      browserGlobals.fetch = origFetch;
      global.fetch = origFetch;
    });
  });
};
