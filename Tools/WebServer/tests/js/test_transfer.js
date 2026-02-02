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
const { browserGlobals, resetMocks, MockTerminal } = require('./mocks');

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
    it('formatSpeed is a function', () =>
      assertTrue(typeof w.formatSpeed === 'function'));
    it('formatETA is a function', () =>
      assertTrue(typeof w.formatETA === 'function'));
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
    it('handleDrop is a function', () =>
      assertTrue(typeof w.handleDrop === 'function'));
    it('uploadDroppedFile is a function', () =>
      assertTrue(typeof w.uploadDroppedFile === 'function'));
  });

  describe('listDeviceDirectory Function', () => {
    it('is async function', () => {
      assertTrue(w.listDeviceDirectory.constructor.name === 'AsyncFunction');
    });
  });

  describe('statDeviceFile Function', () => {
    it('is async function', () => {
      assertTrue(w.statDeviceFile.constructor.name === 'AsyncFunction');
    });
  });

  describe('createDeviceDirectory Function', () => {
    it('is async function', () => {
      assertTrue(w.createDeviceDirectory.constructor.name === 'AsyncFunction');
    });
  });

  describe('deleteDeviceFile Function', () => {
    it('is async function', () => {
      assertTrue(w.deleteDeviceFile.constructor.name === 'AsyncFunction');
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
      w.selectDeviceFile(item);
      assertTrue(item.classList.contains('selected'));
    });

    it('removes selected class from previous item', () => {
      resetMocks();
      const item1 = browserGlobals.document.createElement('div');
      item1.className = 'device-file-item';
      item1.classList.add('selected');
      item1.dataset = { path: '/test1.txt', type: 'file' };

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
      assertEqual(progressText.textContent, '50%');
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

    it('returns early if directory selected', () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();
      // Select a directory
      const item = browserGlobals.document.createElement('div');
      item.className = 'device-file-item';
      item.dataset = { path: '/testdir', type: 'dir' };
      w.selectDeviceFile(item);
      w.downloadFromDevice();
      assertTrue(
        w.FPBState.toolTerminal._writes.some(
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
        listeners[event] = handler;
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
    it('returns early if not connected', () => {
      resetMocks();
      w.FPBState.isConnected = false;
      w.FPBState.toolTerminal = new MockTerminal();

      const mockEvent = {
        dataTransfer: { files: [] },
      };

      w.handleDrop(mockEvent);
      assertTrue(
        w.FPBState.toolTerminal._writes.some(
          (wr) => wr.msg && wr.msg.includes('Not connected'),
        ),
      );

      w.FPBState.toolTerminal = null;
    });

    it('returns early if no files dropped', () => {
      resetMocks();
      w.FPBState.isConnected = true;
      w.FPBState.toolTerminal = new MockTerminal();

      const mockEvent = {
        dataTransfer: { files: [] },
      };

      // Should not throw, just return early
      w.handleDrop(mockEvent);
      w.FPBState.toolTerminal = null;
      w.FPBState.isConnected = false;
    });
  });

  describe('uploadDroppedFile Function', () => {
    it('is async function', () => {
      assertTrue(w.uploadDroppedFile.constructor.name === 'AsyncFunction');
    });
  });
};
