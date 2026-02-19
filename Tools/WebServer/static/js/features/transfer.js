/*========================================
  FPBInject Workbench - File Transfer Module
  ========================================*/

/* ===========================
   FILE TRANSFER STATE
   =========================== */
let transferCurrentPath = '/';
let transferSelectedFile = null;
let transferAbortController = null;

/* ===========================
   CRC VERIFICATION ALERTS
   =========================== */

/**
 * Show CRC warning popup (non-blocking)
 * @param {string} message - Warning message
 */
function showCrcWarning(message) {
  log.warn(message);
  // Use non-blocking notification
  if (typeof showNotification === 'function') {
    showNotification(message, 'warning');
  } else {
    console.warn('CRC Warning:', message);
  }
}

/**
 * Show CRC error popup (blocking alert)
 * @param {string} message - Error message
 */
function showCrcError(message) {
  log.error(message);
  // Use blocking alert for critical CRC errors
  alert(
    `CRC Verification Failed!\n\n${message}\n\nThe transferred file may be corrupted.`,
  );
}

/* ===========================
   DEVICE FILE OPERATIONS
   =========================== */

/**
 * List directory contents on device
 * @param {string} path - Directory path
 * @returns {Promise<{success: boolean, entries: Array}>}
 */
async function listDeviceDirectory(path = '/') {
  try {
    const res = await fetch(
      `/api/transfer/list?path=${encodeURIComponent(path)}`,
    );
    const data = await res.json();
    return data;
  } catch (e) {
    log.error(`List directory failed: ${e}`);
    return { success: false, entries: [], error: e.message };
  }
}

/**
 * Get file status on device
 * @param {string} path - File path
 * @returns {Promise<{success: boolean, stat: Object}>}
 */
async function statDeviceFile(path) {
  try {
    const res = await fetch(
      `/api/transfer/stat?path=${encodeURIComponent(path)}`,
    );
    const data = await res.json();
    return data;
  } catch (e) {
    log.error(`Stat file failed: ${e}`);
    return { success: false, error: e.message };
  }
}

/**
 * Create directory on device
 * @param {string} path - Directory path
 * @returns {Promise<{success: boolean, message: string}>}
 */
async function createDeviceDirectory(path) {
  try {
    const res = await fetch('/api/transfer/mkdir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    const data = await res.json();
    if (!data.success) {
      writeToOutput(
        `[ERROR] Create directory failed: ${data.error || data.message}`,
        'error',
      );
    }
    return data;
  } catch (e) {
    log.error(`Create directory failed: ${e}`);
    return { success: false, error: e.message };
  }
}

/**
 * Delete file on device
 * @param {string} path - File path
 * @returns {Promise<{success: boolean, message: string}>}
 */
async function deleteDeviceFile(path) {
  try {
    const res = await fetch('/api/transfer/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    const data = await res.json();
    if (!data.success) {
      writeToOutput(
        `[ERROR] Delete failed: ${data.error || data.message}`,
        'error',
      );
    }
    return data;
  } catch (e) {
    log.error(`Delete failed: ${e}`);
    return { success: false, error: e.message };
  }
}

/**
 * Rename file or directory on device
 * @param {string} oldPath - Current path
 * @param {string} newPath - New path
 * @returns {Promise<{success: boolean, message: string}>}
 */
async function renameDeviceFile(oldPath, newPath) {
  try {
    const res = await fetch('/api/transfer/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_path: oldPath, new_path: newPath }),
    });
    const data = await res.json();
    if (!data.success) {
      writeToOutput(
        `[ERROR] Rename failed: ${data.error || data.message}`,
        'error',
      );
    }
    return data;
  } catch (e) {
    log.error(`Rename failed: ${e}`);
    return { success: false, error: e.message };
  }
}

/**
 * Upload file to device with progress and cancel support
 * @param {File} file - File object to upload
 * @param {string} remotePath - Destination path on device
 * @param {Function} onProgress - Progress callback(uploaded, total, percent, speed, eta)
 * @returns {Promise<{success: boolean, message: string}>}
 */
async function uploadFileToDevice(file, remotePath, onProgress) {
  // Create abort controller for cancellation
  transferAbortController = new AbortController();

  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('remote_path', remotePath);

    fetch('/api/transfer/upload', {
      method: 'POST',
      body: formData,
      signal: transferAbortController.signal,
    })
      .then((response) => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function processStream() {
          // Check for abort
          if (transferAbortController.signal.aborted) {
            resolve({
              success: false,
              error: 'Transfer cancelled',
              cancelled: true,
            });
            return;
          }

          reader.read().then(({ done, value }) => {
            if (done) {
              resolve({ success: false, error: 'Stream ended unexpectedly' });
              return;
            }

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.type === 'progress' && onProgress) {
                    onProgress(
                      data.uploaded,
                      data.total,
                      data.percent,
                      data.speed,
                      data.eta,
                      data.stats,
                    );
                  } else if (data.type === 'log') {
                    // Display transfer log in OUTPUT
                    writeToOutput(data.message, 'warning');
                  } else if (data.type === 'crc_warning') {
                    // Show CRC warning popup
                    showCrcWarning(data.message);
                  } else if (data.type === 'result') {
                    transferAbortController = null;
                    // Show CRC error popup if applicable
                    if (!data.success && data.crc_error) {
                      showCrcError(data.error);
                    }
                    resolve(data);
                    return;
                  }
                } catch (e) {
                  // Ignore parse errors
                }
              }
            }

            processStream();
          });
        }

        processStream();
      })
      .catch((e) => {
        transferAbortController = null;
        if (e.name === 'AbortError') {
          resolve({
            success: false,
            error: 'Transfer cancelled',
            cancelled: true,
          });
        } else {
          reject(e);
        }
      });
  });
}

/**
 * Download file from device with progress and cancel support
 * @param {string} remotePath - Source path on device
 * @param {Function} onProgress - Progress callback(downloaded, total, percent, speed, eta)
 * @returns {Promise<{success: boolean, data: Blob, message: string}>}
 */
async function downloadFileFromDevice(remotePath, onProgress) {
  // Create abort controller for cancellation
  transferAbortController = new AbortController();

  return new Promise((resolve, reject) => {
    fetch('/api/transfer/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ remote_path: remotePath }),
      signal: transferAbortController.signal,
    })
      .then((response) => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function processStream() {
          // Check for abort
          if (transferAbortController.signal.aborted) {
            resolve({
              success: false,
              error: 'Transfer cancelled',
              cancelled: true,
            });
            return;
          }

          reader.read().then(({ done, value }) => {
            if (done) {
              resolve({ success: false, error: 'Stream ended unexpectedly' });
              return;
            }

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.type === 'progress' && onProgress) {
                    onProgress(
                      data.downloaded,
                      data.total,
                      data.percent,
                      data.speed,
                      data.eta,
                      data.stats,
                    );
                  } else if (data.type === 'log') {
                    // Display transfer log in OUTPUT
                    writeToOutput(data.message, 'warning');
                  } else if (data.type === 'crc_warning') {
                    // Show CRC warning popup
                    showCrcWarning(data.message);
                  } else if (data.type === 'result') {
                    if (data.success && data.data) {
                      // Decode base64 to blob
                      const binary = atob(data.data);
                      const bytes = new Uint8Array(binary.length);
                      for (let i = 0; i < binary.length; i++) {
                        bytes[i] = binary.charCodeAt(i);
                      }
                      data.blob = new Blob([bytes]);
                    }
                    // Show CRC error popup if applicable
                    if (!data.success && data.crc_error) {
                      showCrcError(data.error);
                    }
                    transferAbortController = null;
                    resolve(data);
                    return;
                  }
                } catch (e) {
                  // Ignore parse errors
                }
              }
            }

            processStream();
          });
        }

        processStream();
      })
      .catch((e) => {
        transferAbortController = null;
        if (e.name === 'AbortError') {
          resolve({
            success: false,
            error: 'Transfer cancelled',
            cancelled: true,
          });
        } else {
          reject(e);
        }
      });
  });
}

/* ===========================
   UI FUNCTIONS
   =========================== */

/**
 * Refresh device file list
 */
async function refreshDeviceFiles() {
  const pathInput = document.getElementById('devicePath');
  const path = pathInput ? pathInput.value || '/' : '/';
  transferCurrentPath = path;

  const fileList = document.getElementById('deviceFileList');
  if (!fileList) return;

  // Only show loading if list is empty or has error/empty message
  const hasContent = fileList.querySelector('.device-file-item');
  let loadingIndicator = null;
  let loadingTimeout = null;

  if (!hasContent) {
    fileList.innerHTML = '<div class="loading">Loading...</div>';
  } else {
    // Delay showing loading overlay by 500ms
    loadingTimeout = setTimeout(() => {
      loadingIndicator = document.createElement('div');
      loadingIndicator.className = 'loading-overlay';
      loadingIndicator.innerHTML = '<div class="loading-spinner"></div>';
      fileList.style.position = 'relative';
      fileList.appendChild(loadingIndicator);
    }, 500);
  }

  const result = await listDeviceDirectory(path);

  // Clear timeout and remove loading overlay if it exists
  if (loadingTimeout) {
    clearTimeout(loadingTimeout);
  }
  const loadingOverlay = fileList.querySelector('.loading-overlay');
  if (loadingOverlay) {
    loadingOverlay.remove();
  }

  if (!result.success) {
    fileList.innerHTML = `<div class="error">Error: ${result.error || 'Failed to list'}</div>`;
    return;
  }

  fileList.innerHTML = '';
  transferSelectedFile = null;

  // Add parent directory entry if not at root
  if (path !== '/') {
    const parentItem = document.createElement('div');
    parentItem.className = 'device-file-item';
    parentItem.dataset.path = path.split('/').slice(0, -1).join('/') || '/';
    parentItem.dataset.type = 'dir';
    parentItem.innerHTML = `
      <i class="codicon codicon-folder"></i>
      <span class="file-name">..</span>
    `;
    parentItem.onclick = () => selectDeviceFile(parentItem);
    parentItem.ondblclick = () => {
      pathInput.value = parentItem.dataset.path;
      refreshDeviceFiles();
    };
    fileList.appendChild(parentItem);
  }

  // Sort: directories first, then files
  const entries = result.entries || [];
  entries.sort((a, b) => {
    if (a.type === 'dir' && b.type !== 'dir') return -1;
    if (a.type !== 'dir' && b.type === 'dir') return 1;
    return a.name.localeCompare(b.name);
  });

  for (const entry of entries) {
    const item = document.createElement('div');
    item.className = 'device-file-item';
    item.dataset.path =
      path === '/' ? `/${entry.name}` : `${path}/${entry.name}`;
    item.dataset.type = entry.type;

    const icon = entry.type === 'dir' ? 'codicon-folder' : 'codicon-file';
    const sizeStr =
      entry.type === 'file'
        ? `<span class="file-size">${formatFileSize(entry.size)}</span>`
        : '';

    item.innerHTML = `
      <i class="codicon ${icon}"></i>
      <span class="file-name">${entry.name}</span>
      ${sizeStr}
    `;

    item.onclick = () => selectDeviceFile(item);
    item.ondblclick = () => {
      if (entry.type === 'dir') {
        pathInput.value = item.dataset.path;
        refreshDeviceFiles();
      }
    };

    fileList.appendChild(item);
  }

  if (entries.length === 0 && path === '/') {
    fileList.innerHTML = '<div class="empty">No files</div>';
  }
}

/**
 * Select a device file item
 */
function selectDeviceFile(item) {
  // Deselect previous
  const prev = document.querySelector('.device-file-item.selected');
  if (prev) prev.classList.remove('selected');

  item.classList.add('selected');
  transferSelectedFile = {
    path: item.dataset.path,
    type: item.dataset.type,
  };
}

/**
 * Format file size for display
 */
function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Format speed for display (bytes per second)
 */
function formatSpeed(bytesPerSec) {
  if (bytesPerSec < 1024) return `${bytesPerSec.toFixed(0)} B/s`;
  if (bytesPerSec < 1024 * 1024)
    return `${(bytesPerSec / 1024).toFixed(1)} KB/s`;
  return `${(bytesPerSec / (1024 * 1024)).toFixed(1)} MB/s`;
}

/**
 * Format ETA for display (seconds)
 */
function formatETA(seconds) {
  if (seconds < 1) return '<1s';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  }
  const hours = Math.floor(seconds / 3600);
  const mins = Math.round((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

/**
 * Update transfer progress bar
 */
function updateTransferProgress(percent, text, speed, eta, stats) {
  const progressBar = document.getElementById('transferProgress');
  const progressFill = progressBar?.querySelector('.progress-fill');
  const progressText = progressBar?.querySelector('.progress-text');
  const progressSpeed = progressBar?.querySelector('.progress-speed');
  const progressEta = progressBar?.querySelector('.progress-eta');
  const progressStats = progressBar?.querySelector('.progress-stats');
  const progressLoss = progressBar?.querySelector('.progress-loss');

  if (progressBar) {
    progressBar.style.display = 'block';
  }
  if (progressFill) {
    progressFill.style.width = `${percent}%`;
  }
  if (progressText) {
    // Always show 1 decimal place for percentage
    const percentStr =
      typeof percent === 'number' ? percent.toFixed(1) : percent;
    progressText.textContent = text || `${percentStr}%`;
  }
  if (progressSpeed && speed !== undefined) {
    progressSpeed.textContent = formatSpeed(speed);
  }
  if (progressEta && eta !== undefined) {
    progressEta.textContent = `ETA: ${formatETA(eta)}`;
  }
  // Update packet loss stats - always show
  if (progressStats && progressLoss && stats) {
    const lossRate = stats.packet_loss_rate || 0;
    const retries = stats.retry_count || 0;
    progressStats.style.display = 'block';
    let lossText = [`Loss: ${lossRate.toFixed(1)}%`];
    if (retries > 0) lossText.push(`Retries: ${retries}`);
    progressLoss.textContent = lossText.join(' | ');
  }
}

/**
 * Hide transfer progress bar
 */
function hideTransferProgress() {
  const progressBar = document.getElementById('transferProgress');
  if (progressBar) {
    progressBar.style.display = 'none';
    // Also hide stats
    const progressStats = progressBar.querySelector('.progress-stats');
    if (progressStats) {
      progressStats.style.display = 'none';
    }
  }
  // Reset control buttons
  updateTransferControls(false);
}

/**
 * Cancel current transfer
 */
async function cancelTransfer() {
  if (transferAbortController) {
    // Notify backend to cancel
    try {
      await fetch('/api/transfer/cancel', { method: 'POST' });
    } catch (e) {
      // Ignore errors
    }

    transferAbortController.abort();
    transferAbortController = null;
    log.warn('Transfer cancelled');
    hideTransferProgress();
  }
}

/**
 * Check if transfer is in progress
 */
function isTransferInProgress() {
  return transferAbortController !== null;
}

/**
 * Update transfer control buttons visibility
 */
function updateTransferControls(show) {
  const cancelBtn = document.getElementById('transferCancelBtn');
  if (cancelBtn) cancelBtn.style.display = show ? 'flex' : 'none';
}

/* ===========================
   DRAG AND DROP
   =========================== */

// Track drag enter/leave count to handle nested elements
let dragEnterCount = 0;

/**
 * Reset drag state (for testing)
 */
function resetDragState() {
  dragEnterCount = 0;
}

/**
 * Initialize drag and drop for file upload
 */
function initTransferDragDrop() {
  const dropZone = document.getElementById('deviceFileList');
  if (!dropZone) return;

  // Prevent default drag behaviors on body to allow drop
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((eventName) => {
    document.body.addEventListener(eventName, preventDefaults, false);
  });

  // Prevent default on drop zone
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((eventName) => {
    dropZone.addEventListener(eventName, preventDefaults, false);
  });

  // Track drag enter/leave to handle nested elements properly
  dropZone.addEventListener('dragenter', handleDragEnter, false);
  dropZone.addEventListener('dragleave', handleDragLeave, false);
  dropZone.addEventListener('dragover', handleDragOver, false);
  dropZone.addEventListener('drop', handleDrop, false);
}

/**
 * Handle drag enter event
 */
function handleDragEnter(e) {
  dragEnterCount++;
  highlightDropZone(true);
}

/**
 * Handle drag leave event
 */
function handleDragLeave(e) {
  dragEnterCount--;
  if (dragEnterCount <= 0) {
    dragEnterCount = 0;
    highlightDropZone(false);
  }
}

/**
 * Handle drag over event (needed to allow drop)
 */
function handleDragOver(e) {
  // Keep highlighting while dragging over
  highlightDropZone(true);
}

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

function highlightDropZone(highlight) {
  const dropZone = document.getElementById('deviceFileList');
  if (dropZone) {
    dropZone.classList.toggle('drag-over', highlight);
  }
}

/**
 * Handle dropped files or folders
 */
async function handleDrop(e) {
  // Reset drag state
  dragEnterCount = 0;
  highlightDropZone(false);

  const state = window.FPBState;
  if (!state.isConnected) {
    writeToOutput(
      '[ERROR] Not connected to device. Please connect first.',
      'error',
    );
    return;
  }

  const dt = e.dataTransfer;

  // Check if we have items (for folder support)
  if (dt.items && dt.items.length > 0) {
    const entries = [];
    for (let i = 0; i < dt.items.length; i++) {
      const item = dt.items[i];
      if (item.webkitGetAsEntry) {
        const entry = item.webkitGetAsEntry();
        if (entry) entries.push(entry);
      }
    }

    if (entries.length > 0) {
      for (const entry of entries) {
        if (entry.isDirectory) {
          await uploadFolderEntry(entry, transferCurrentPath);
        } else if (entry.isFile) {
          const file = await getFileFromEntry(entry);
          if (file) await uploadDroppedFile(file);
        }
      }
      return;
    }
  }

  // Fallback to files (no folder support)
  const files = dt.files;
  if (files.length === 0) return;

  for (const file of files) {
    await uploadDroppedFile(file);
  }
}

/**
 * Get File object from FileEntry
 */
function getFileFromEntry(fileEntry) {
  return new Promise((resolve) => {
    fileEntry.file(resolve, () => resolve(null));
  });
}

/**
 * Read all entries from a directory entry
 */
function readDirectoryEntries(dirReader) {
  return new Promise((resolve) => {
    const entries = [];
    function readBatch() {
      dirReader.readEntries(
        (batch) => {
          if (batch.length === 0) {
            resolve(entries);
          } else {
            entries.push(...batch);
            readBatch(); // Continue reading (readEntries returns max 100 at a time)
          }
        },
        () => resolve(entries),
      );
    }
    readBatch();
  });
}

/**
 * Collect all files from a directory entry recursively
 * @returns {Promise<Array<{file: File, relativePath: string}>>}
 */
async function collectFilesFromEntry(entry, basePath = '') {
  const files = [];

  if (entry.isFile) {
    const file = await getFileFromEntry(entry);
    if (file) {
      files.push({ file, relativePath: basePath + entry.name });
    }
  } else if (entry.isDirectory) {
    const dirPath = basePath + entry.name + '/';
    const dirReader = entry.createReader();
    const entries = await readDirectoryEntries(dirReader);

    for (const childEntry of entries) {
      const childFiles = await collectFilesFromEntry(childEntry, dirPath);
      files.push(...childFiles);
    }
  }

  return files;
}

/**
 * Upload a folder entry to device
 */
async function uploadFolderEntry(dirEntry, remotePath) {
  const folderName = dirEntry.name;
  const targetPath =
    remotePath === '/' ? `/${folderName}` : `${remotePath}/${folderName}`;

  log.info(`Scanning folder: ${folderName}...`);

  // Collect all files first (only collect contents, not the root folder itself)
  const dirReader = dirEntry.createReader();
  const entries = await readDirectoryEntries(dirReader);

  const files = [];
  for (const childEntry of entries) {
    const childFiles = await collectFilesFromEntry(childEntry, '');
    files.push(...childFiles);
  }

  if (files.length === 0) {
    log.warn(`Folder is empty: ${folderName}`);
    // Still create the empty directory
    await createDeviceDirectory(targetPath);
    refreshDeviceFiles();
    return;
  }

  log.info(`Found ${files.length} files in ${folderName}`);

  // Upload folder
  await uploadFolderFiles(files, targetPath, folderName);
}

/**
 * Upload collected files to device with folder structure
 * @param {Array<{file: File, relativePath: string}>} files - Files to upload
 * @param {string} targetPath - Base target path on device
 * @param {string} folderName - Folder name for display
 */
async function uploadFolderFiles(files, targetPath, folderName) {
  const totalFiles = files.length;
  let uploadedFiles = 0;
  let totalBytes = files.reduce((sum, f) => sum + f.file.size, 0);
  let uploadedBytes = 0;
  const startTime = Date.now();

  // Track created directories to avoid duplicates
  const createdDirs = new Set();

  updateTransferProgress(0, `Uploading folder: 0/${totalFiles} files`);
  updateTransferControls(true);

  for (const { file, relativePath } of files) {
    // Check if cancelled
    if (transferAbortController && transferAbortController.signal.aborted) {
      log.warn('Folder upload cancelled');
      hideTransferProgress();
      return;
    }

    const remoteFilePath = `${targetPath}/${relativePath}`;

    // Create parent directories if needed
    const parentDir = remoteFilePath.substring(
      0,
      remoteFilePath.lastIndexOf('/'),
    );
    if (parentDir && !createdDirs.has(parentDir)) {
      // Create all parent directories
      const parts = parentDir.split('/').filter((p) => p);
      let currentPath = '';
      for (const part of parts) {
        currentPath += '/' + part;
        if (!createdDirs.has(currentPath)) {
          await createDeviceDirectory(currentPath);
          createdDirs.add(currentPath);
        }
      }
    }

    // Upload file
    const fileStartBytes = uploadedBytes;
    try {
      const result = await uploadFileToDevice(
        file,
        remoteFilePath,
        (uploaded, total, percent, speed, eta, stats) => {
          const currentBytes = fileStartBytes + uploaded;
          const overallPercent = (currentBytes / totalBytes) * 100;
          const elapsed = (Date.now() - startTime) / 1000;
          const overallSpeed = elapsed > 0 ? currentBytes / elapsed : 0;
          const remainingBytes = totalBytes - currentBytes;
          const overallEta =
            overallSpeed > 0 ? remainingBytes / overallSpeed : 0;

          updateTransferProgress(
            overallPercent,
            `Folder: ${uploadedFiles}/${totalFiles} files (${overallPercent.toFixed(1)}%)`,
            overallSpeed,
            overallEta,
            stats,
          );
        },
      );

      if (result.success) {
        uploadedBytes += file.size;
        uploadedFiles++;
      } else if (result.cancelled) {
        log.warn('Folder upload cancelled');
        hideTransferProgress();
        return;
      } else {
        log.error(`Failed to upload ${relativePath}: ${result.error}`);
      }
    } catch (e) {
      log.error(`Upload error for ${relativePath}: ${e}`);
    }
  }

  hideTransferProgress();

  const elapsed = (Date.now() - startTime) / 1000;
  const avgSpeed = elapsed > 0 ? uploadedBytes / elapsed : 0;

  log.success(
    `Folder upload complete: ${folderName} (${uploadedFiles}/${totalFiles} files, ${formatSpeed(avgSpeed)})`,
  );

  refreshDeviceFiles();
}

/**
 * Format transfer stats for display
 */
function formatTransferStats(stats) {
  if (!stats) return '';
  const parts = [];
  if (stats.packet_loss_rate !== undefined && stats.packet_loss_rate > 0) {
    parts.push(`loss: ${stats.packet_loss_rate}%`);
  }
  if (stats.retry_count > 0) {
    parts.push(`retries: ${stats.retry_count}`);
  }
  if (stats.crc_errors > 0) {
    parts.push(`CRC errors: ${stats.crc_errors}`);
  }
  return parts.length > 0 ? ` [${parts.join(', ')}]` : '';
}

/**
 * Show transfer error alert dialog
 * @param {string} operation - 'Upload' or 'Download'
 * @param {string} fileName - File name
 * @param {string} error - Error message
 * @param {object} stats - Transfer statistics (optional)
 */
function showTransferErrorAlert(operation, fileName, error, stats) {
  let message = `${operation} failed for "${fileName}":\n\n${error}`;
  if (stats) {
    const statParts = [];
    if (stats.retry_count > 0) statParts.push(`Retries: ${stats.retry_count}`);
    if (stats.crc_errors > 0) statParts.push(`CRC errors: ${stats.crc_errors}`);
    if (stats.timeout_errors > 0)
      statParts.push(`Timeout errors: ${stats.timeout_errors}`);
    if (stats.packet_loss_rate > 0)
      statParts.push(`Packet loss: ${stats.packet_loss_rate}%`);
    if (statParts.length > 0) {
      message += `\n\nTransfer Statistics:\n${statParts.join('\n')}`;
    }
  }
  alert(message);
}

/**
 * Upload a dropped file
 */
async function uploadDroppedFile(file) {
  // Determine remote path
  let remotePath = transferCurrentPath;
  if (remotePath === '/') {
    remotePath = `/${file.name}`;
  } else {
    remotePath = `${remotePath}/${file.name}`;
  }

  log.info(`Starting upload: ${file.name} -> ${remotePath}`);
  updateTransferProgress(0, 'Uploading...');
  updateTransferControls(true);

  try {
    const result = await uploadFileToDevice(
      file,
      remotePath,
      (uploaded, total, percent, speed, eta, stats) => {
        updateTransferProgress(
          percent,
          `${percent.toFixed(1)}% (${formatFileSize(uploaded)}/${formatFileSize(total)})`,
          speed,
          eta,
          stats,
        );
      },
    );

    hideTransferProgress();

    if (result.cancelled) {
      log.warn(`Upload cancelled: ${file.name}`);
    } else if (result.success) {
      const speedStr = result.avg_speed
        ? ` (${formatSpeed(result.avg_speed)})`
        : '';
      const statsStr = formatTransferStats(result.stats);
      log.success(`Upload complete: ${remotePath}${speedStr}${statsStr}`);
      refreshDeviceFiles();
    } else {
      log.error(`Upload failed: ${result.error}`);
      showTransferErrorAlert('Upload', file.name, result.error, result.stats);
    }
  } catch (e) {
    hideTransferProgress();
    log.error(`Upload error: ${e}`);
    showTransferErrorAlert('Upload', file.name, e.message || String(e));
  }
}

/**
 * Upload file to device (UI handler)
 */
async function uploadToDevice() {
  const state = window.FPBState;
  if (!state.isConnected) {
    log.error('Not connected');
    return;
  }

  // Create file input
  const input = document.createElement('input');
  input.type = 'file';
  input.multiple = true; // Allow multiple file selection
  input.onchange = async () => {
    const files = input.files;
    if (!files || files.length === 0) return;

    for (const file of files) {
      await uploadDroppedFile(file);
    }
  };
  input.click();
}

/**
 * Upload folder to device (UI handler)
 */
async function uploadFolderToDevice() {
  const state = window.FPBState;
  if (!state.isConnected) {
    log.error('Not connected');
    return;
  }

  // Create folder input
  const input = document.createElement('input');
  input.type = 'file';
  input.webkitdirectory = true;
  input.onchange = async () => {
    const files = input.files;
    if (!files || files.length === 0) return;

    // Group files by folder structure
    // webkitRelativePath gives us "folderName/subdir/file.txt"
    const fileMap = new Map(); // folderName -> [{file, relativePath}]

    for (const file of files) {
      const relativePath = file.webkitRelativePath;
      if (!relativePath) continue;

      const parts = relativePath.split('/');
      const folderName = parts[0];
      const fileRelativePath = parts.slice(1).join('/');

      if (!fileMap.has(folderName)) {
        fileMap.set(folderName, []);
      }
      fileMap.get(folderName).push({ file, relativePath: fileRelativePath });
    }

    // Upload each folder
    for (const [folderName, folderFiles] of fileMap) {
      const targetPath =
        transferCurrentPath === '/'
          ? `/${folderName}`
          : `${transferCurrentPath}/${folderName}`;
      await uploadFolderFiles(folderFiles, targetPath, folderName);
    }
  };
  input.click();
}

/**
 * Download file from device (UI handler)
 */
async function downloadFromDevice() {
  const state = window.FPBState;
  if (!state.isConnected) {
    log.error('Not connected');
    return;
  }

  if (!transferSelectedFile || transferSelectedFile.type === 'dir') {
    log.error('Please select a file to download');
    return;
  }

  const remotePath = transferSelectedFile.path;
  const fileName = remotePath.split('/').pop();

  log.info(`Starting download: ${remotePath}`);
  updateTransferProgress(0, 'Downloading...');
  updateTransferControls(true);

  try {
    const result = await downloadFileFromDevice(
      remotePath,
      (downloaded, total, percent, speed, eta, stats) => {
        updateTransferProgress(
          percent,
          `${percent.toFixed(1)}% (${formatFileSize(downloaded)}/${formatFileSize(total)})`,
          speed,
          eta,
          stats,
        );
      },
    );

    hideTransferProgress();

    if (result.cancelled) {
      log.warn(`Download cancelled: ${fileName}`);
    } else if (result.success && result.blob) {
      // Trigger browser download
      const url = URL.createObjectURL(result.blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);

      const speedStr = result.avg_speed
        ? ` (${formatSpeed(result.avg_speed)})`
        : '';
      const statsStr = formatTransferStats(result.stats);
      log.success(`Download complete: ${fileName}${speedStr}${statsStr}`);
    } else {
      log.error(`Download failed: ${result.error}`);
      showTransferErrorAlert('Download', fileName, result.error, result.stats);
    }
  } catch (e) {
    hideTransferProgress();
    log.error(`Download error: ${e}`);
    showTransferErrorAlert('Download', fileName, e.message || String(e));
  }
}

/**
 * Delete file from device (UI handler)
 */
async function deleteFromDevice() {
  const state = window.FPBState;
  if (!state.isConnected) {
    log.error('Not connected');
    return;
  }

  if (!transferSelectedFile) {
    log.error('Please select a file to delete');
    return;
  }

  const path = transferSelectedFile.path;
  const typeStr = transferSelectedFile.type === 'dir' ? 'directory' : 'file';

  if (!confirm(`Are you sure you want to delete ${typeStr}: ${path}?`)) {
    return;
  }

  const result = await deleteDeviceFile(path);
  if (result.success) {
    refreshDeviceFiles();
  }
}

/**
 * Create new directory on device (UI handler)
 */
async function createDeviceDir() {
  const state = window.FPBState;
  if (!state.isConnected) {
    log.error('Not connected');
    return;
  }

  const name = prompt('Enter directory name:');
  if (!name) return;

  let path = transferCurrentPath;
  if (path === '/') {
    path = `/${name}`;
  } else {
    path = `${path}/${name}`;
  }

  const result = await createDeviceDirectory(path);
  if (result.success) {
    refreshDeviceFiles();
  }
}

/**
 * Rename file or directory on device (UI handler)
 */
async function renameOnDevice() {
  const state = window.FPBState;
  if (!state.isConnected) {
    log.error('Not connected');
    return;
  }

  if (!transferSelectedFile) {
    log.error('Please select a file or directory to rename');
    return;
  }

  const oldPath = transferSelectedFile.path;
  const oldName = oldPath.split('/').pop();
  const parentPath = oldPath.substring(0, oldPath.lastIndexOf('/')) || '/';

  const newName = prompt('Enter new name:', oldName);
  if (!newName || newName === oldName) return;

  const newPath =
    parentPath === '/' ? `/${newName}` : `${parentPath}/${newName}`;

  const result = await renameDeviceFile(oldPath, newPath);
  if (result.success) {
    refreshDeviceFiles();
  }
}

/* ===========================
   EXPORTS
   =========================== */
window.listDeviceDirectory = listDeviceDirectory;
window.statDeviceFile = statDeviceFile;
window.createDeviceDirectory = createDeviceDirectory;
window.deleteDeviceFile = deleteDeviceFile;
window.renameDeviceFile = renameDeviceFile;
window.uploadFileToDevice = uploadFileToDevice;
window.downloadFileFromDevice = downloadFileFromDevice;
window.refreshDeviceFiles = refreshDeviceFiles;
window.selectDeviceFile = selectDeviceFile;
window.uploadToDevice = uploadToDevice;
window.uploadFolderToDevice = uploadFolderToDevice;
window.downloadFromDevice = downloadFromDevice;
window.deleteFromDevice = deleteFromDevice;
window.renameOnDevice = renameOnDevice;
window.createDeviceDir = createDeviceDir;
window.updateTransferProgress = updateTransferProgress;
window.hideTransferProgress = hideTransferProgress;
window.formatSpeed = formatSpeed;
window.formatETA = formatETA;
window.formatTransferStats = formatTransferStats;
// CRC verification
window.showCrcWarning = showCrcWarning;
window.showCrcError = showCrcError;
// Cancel
window.cancelTransfer = cancelTransfer;
window.isTransferInProgress = isTransferInProgress;
window.updateTransferControls = updateTransferControls;
// Drag and drop
window.initTransferDragDrop = initTransferDragDrop;
window.preventDefaults = preventDefaults;
window.highlightDropZone = highlightDropZone;
window.handleDragEnter = handleDragEnter;
window.handleDragLeave = handleDragLeave;
window.handleDragOver = handleDragOver;
window.handleDrop = handleDrop;
window.uploadDroppedFile = uploadDroppedFile;
window.resetDragState = resetDragState;
window.showTransferErrorAlert = showTransferErrorAlert;
// Folder upload helpers
window.getFileFromEntry = getFileFromEntry;
window.readDirectoryEntries = readDirectoryEntries;
window.collectFilesFromEntry = collectFilesFromEntry;
window.uploadFolderEntry = uploadFolderEntry;
window.uploadFolderFiles = uploadFolderFiles;
