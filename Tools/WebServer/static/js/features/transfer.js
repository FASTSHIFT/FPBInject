/*========================================
  FPBInject Workbench - File Transfer Module
  ========================================*/

/* ===========================
   FILE TRANSFER STATE
   =========================== */
let transferCurrentPath = '/';
let transferSelectedFile = null;

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
    writeToOutput(`[ERROR] List directory failed: ${e}`, 'error');
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
    writeToOutput(`[ERROR] Stat file failed: ${e}`, 'error');
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
    if (data.success) {
      writeToOutput(`[SUCCESS] Created directory: ${path}`, 'success');
    } else {
      writeToOutput(
        `[ERROR] Create directory failed: ${data.error || data.message}`,
        'error',
      );
    }
    return data;
  } catch (e) {
    writeToOutput(`[ERROR] Create directory failed: ${e}`, 'error');
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
    if (data.success) {
      writeToOutput(`[SUCCESS] Deleted: ${path}`, 'success');
    } else {
      writeToOutput(
        `[ERROR] Delete failed: ${data.error || data.message}`,
        'error',
      );
    }
    return data;
  } catch (e) {
    writeToOutput(`[ERROR] Delete failed: ${e}`, 'error');
    return { success: false, error: e.message };
  }
}

/**
 * Upload file to device with progress
 * @param {File} file - File object to upload
 * @param {string} remotePath - Destination path on device
 * @param {Function} onProgress - Progress callback(uploaded, total, percent, speed, eta)
 * @returns {Promise<{success: boolean, message: string}>}
 */
async function uploadFileToDevice(file, remotePath, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('remote_path', remotePath);

    fetch('/api/transfer/upload', {
      method: 'POST',
      body: formData,
    })
      .then((response) => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function processStream() {
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
                    );
                  } else if (data.type === 'result') {
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
        reject(e);
      });
  });
}

/**
 * Download file from device with progress
 * @param {string} remotePath - Source path on device
 * @param {Function} onProgress - Progress callback(downloaded, total, percent, speed, eta)
 * @returns {Promise<{success: boolean, data: Blob, message: string}>}
 */
async function downloadFileFromDevice(remotePath, onProgress) {
  return new Promise((resolve, reject) => {
    fetch('/api/transfer/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ remote_path: remotePath }),
    })
      .then((response) => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function processStream() {
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
                    );
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
        reject(e);
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

  fileList.innerHTML = '<div class="loading">Loading...</div>';

  const result = await listDeviceDirectory(path);

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
    parentItem.innerHTML = `
      <i class="codicon codicon-folder"></i>
      <span class="file-name">..</span>
    `;
    parentItem.onclick = () => {
      const parentPath = path.split('/').slice(0, -1).join('/') || '/';
      pathInput.value = parentPath;
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
      entry.type === 'file' ? ` (${formatFileSize(entry.size)})` : '';

    item.innerHTML = `
      <i class="codicon ${icon}"></i>
      <span class="file-name">${entry.name}${sizeStr}</span>
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
function updateTransferProgress(percent, text, speed, eta) {
  const progressBar = document.getElementById('transferProgress');
  const progressFill = progressBar?.querySelector('.progress-fill');
  const progressText = progressBar?.querySelector('.progress-text');
  const progressSpeed = progressBar?.querySelector('.progress-speed');
  const progressEta = progressBar?.querySelector('.progress-eta');

  if (progressBar) {
    progressBar.style.display = 'block';
  }
  if (progressFill) {
    progressFill.style.width = `${percent}%`;
  }
  if (progressText) {
    progressText.textContent = text || `${percent}%`;
  }
  if (progressSpeed && speed !== undefined) {
    progressSpeed.textContent = formatSpeed(speed);
  }
  if (progressEta && eta !== undefined) {
    progressEta.textContent = `ETA: ${formatETA(eta)}`;
  }
}

/**
 * Hide transfer progress bar
 */
function hideTransferProgress() {
  const progressBar = document.getElementById('transferProgress');
  if (progressBar) {
    progressBar.style.display = 'none';
  }
}

/**
 * Upload file to device (UI handler)
 */
async function uploadToDevice() {
  const state = window.FPBState;
  if (!state.isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  // Create file input
  const input = document.createElement('input');
  input.type = 'file';
  input.onchange = async () => {
    const file = input.files[0];
    if (!file) return;

    // Determine remote path
    let remotePath = transferCurrentPath;
    if (remotePath === '/') {
      remotePath = `/${file.name}`;
    } else {
      remotePath = `${remotePath}/${file.name}`;
    }

    writeToOutput(`[UPLOAD] Starting: ${file.name} -> ${remotePath}`, 'info');
    updateTransferProgress(0, 'Uploading...');

    try {
      const result = await uploadFileToDevice(
        file,
        remotePath,
        (uploaded, total, percent, speed, eta) => {
          updateTransferProgress(
            percent,
            `${percent}% (${formatFileSize(uploaded)}/${formatFileSize(total)})`,
            speed,
            eta,
          );
        },
      );

      hideTransferProgress();

      if (result.success) {
        const speedStr = result.avg_speed
          ? ` (${formatSpeed(result.avg_speed)})`
          : '';
        writeToOutput(
          `[SUCCESS] Upload complete: ${remotePath}${speedStr}`,
          'success',
        );
        refreshDeviceFiles();
      } else {
        writeToOutput(`[ERROR] Upload failed: ${result.error}`, 'error');
      }
    } catch (e) {
      hideTransferProgress();
      writeToOutput(`[ERROR] Upload error: ${e}`, 'error');
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
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  if (!transferSelectedFile || transferSelectedFile.type === 'dir') {
    writeToOutput('[ERROR] Please select a file to download', 'error');
    return;
  }

  const remotePath = transferSelectedFile.path;
  const fileName = remotePath.split('/').pop();

  writeToOutput(`[DOWNLOAD] Starting: ${remotePath}`, 'info');
  updateTransferProgress(0, 'Downloading...');

  try {
    const result = await downloadFileFromDevice(
      remotePath,
      (downloaded, total, percent, speed, eta) => {
        updateTransferProgress(
          percent,
          `${percent}% (${formatFileSize(downloaded)}/${formatFileSize(total)})`,
          speed,
          eta,
        );
      },
    );

    hideTransferProgress();

    if (result.success && result.blob) {
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
      writeToOutput(
        `[SUCCESS] Download complete: ${fileName}${speedStr}`,
        'success',
      );
    } else {
      writeToOutput(`[ERROR] Download failed: ${result.error}`, 'error');
    }
  } catch (e) {
    hideTransferProgress();
    writeToOutput(`[ERROR] Download error: ${e}`, 'error');
  }
}

/**
 * Delete file from device (UI handler)
 */
async function deleteFromDevice() {
  const state = window.FPBState;
  if (!state.isConnected) {
    writeToOutput('[ERROR] Not connected', 'error');
    return;
  }

  if (!transferSelectedFile) {
    writeToOutput('[ERROR] Please select a file to delete', 'error');
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
    writeToOutput('[ERROR] Not connected', 'error');
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

/* ===========================
   EXPORTS
   =========================== */
window.listDeviceDirectory = listDeviceDirectory;
window.statDeviceFile = statDeviceFile;
window.createDeviceDirectory = createDeviceDirectory;
window.deleteDeviceFile = deleteDeviceFile;
window.uploadFileToDevice = uploadFileToDevice;
window.downloadFileFromDevice = downloadFileFromDevice;
window.refreshDeviceFiles = refreshDeviceFiles;
window.selectDeviceFile = selectDeviceFile;
window.uploadToDevice = uploadToDevice;
window.downloadFromDevice = downloadFromDevice;
window.deleteFromDevice = deleteFromDevice;
window.createDeviceDir = createDeviceDir;
window.updateTransferProgress = updateTransferProgress;
window.hideTransferProgress = hideTransferProgress;
window.formatSpeed = formatSpeed;
window.formatETA = formatETA;
