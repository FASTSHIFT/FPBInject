/*========================================
  FPBInject Workbench - English Translations
  ========================================*/

window.i18nResources = window.i18nResources || {};
window.i18nResources['en'] = {
  translation: {
    // Sidebar sections
    sidebar: {
      connection: 'CONNECTION',
      config: 'CONFIG',
      explorer: 'EXPLORER',
      file_transfer: 'FILE TRANSFER',
    },

    // Config groups
    config: {
      groups: {
        connection: 'Connection',
        project: 'Project Paths',
        inject: 'Injection',
        transfer: 'Transfer',
        logging: 'Logging',
        tools: 'Analysis Tools',
        ui: 'User Interface',
      },
      // Config item labels
      labels: {
        elf_path: 'ELF Path',
        compile_commands_path: 'Compile DB',
        toolchain_path: 'Toolchain',
        patch_mode: 'Inject Mode',
        auto_compile: 'Auto Inject on Save',
        watch_dirs: 'Watch Directories',
        chunk_size: 'Chunk Size',
        tx_chunk_size: 'TX Chunk',
        tx_chunk_delay: 'TX Delay',
        transfer_max_retries: 'Max Retries',
        wakeup_shell_cnt: 'Wakeup Count',
        verify_crc: 'Verify CRC after Transfer',
        log_file_path: 'Log Path',
        log_file_enabled: 'Record Serial Logs',
        serial_echo_enabled: 'Serial TX Echo',
        ghidra_path: 'Ghidra Path',
        enable_decompile: 'Enable Decompilation',
        ui_language: 'Language',
      },
    },

    // Connection panel
    connection: {
      port: 'Port',
      baudrate: 'Baud Rate',
      connect: 'Connect',
      disconnect: 'Disconnect',
      connecting: 'Connecting...',
      refresh: 'Refresh',
      status: {
        connected: 'Connected',
        disconnected: 'Disconnected',
      },
    },

    // Buttons
    buttons: {
      inject: 'Inject',
      compile: 'Compile',
      browse: 'Browse',
      save: 'Save',
      cancel: 'Cancel',
      clear: 'Clear',
      refresh: 'Refresh',
      add: 'Add',
      remove: 'Remove',
      start: 'Start',
      stop: 'Stop',
    },

    // Tabs
    tabs: {
      patch: 'PATCH',
      symbols: 'SYMBOLS',
      output: 'OUTPUT',
      serial: 'SERIAL',
      problems: 'PROBLEMS',
    },

    // Panels
    panels: {
      fpb_slots: 'FPB SLOTS',
      slot_empty: 'Empty',
      slot_occupied: 'Occupied',
      no_file_open: 'No file open',
      no_symbols: 'No symbols loaded',
      memory_not_available: 'Memory info not available',
      click_refresh: "Click 'Refresh' to load files",
      search_placeholder: 'Search by name or address',
    },

    // Status bar
    // Status bar
    statusbar: {
      ready: 'Ready',
      compiling: 'Compiling...',
      injecting: 'Injecting...',
      connected: 'Connected',
      disconnected: 'Disconnected',
      watcher_off: 'Watcher: Off',
      watcher_on: 'Watcher: On',
      slot: 'Slot: {{slot}}',
    },

    // Messages
    messages: {
      config_saved: 'Configuration saved',
      connect_success: 'Connected successfully',
      connect_failed: 'Connection failed',
      inject_success: 'Injection successful',
      inject_failed: 'Injection failed',
      compile_success: 'Compilation successful',
      compile_failed: 'Compilation failed',
    },

    // Modals
    modals: {
      file_browser: 'File Browser',
      go: 'Go',
      select: 'Select',
    },

    // Editor
    editor: {
      slot: 'SLOT',
      no_file_open: 'No file open',
    },

    // Transfer
    transfer: {
      file: 'File',
      folder: 'Folder',
      download: 'Download',
      upload: 'Upload',
      cancel: 'Cancel',
    },

    // Device
    device: {
      ping: 'Ping Device',
      info: 'Get Info',
      test: 'Throughput Test',
      clear_all: 'Clear All',
      slot_n: 'Slot {{n}}',
      fpb_v2_only: 'FPB v2 only',
      fpb_v2_required: 'This slot requires FPB v2 hardware',
      bytes: 'Bytes',
      used: 'Used',
    },

    // Tooltips
    tooltips: {
      // Activity bar
      activity_connection: 'Connection',
      activity_device: 'Device Info',
      activity_transfer: 'File Transfer',
      activity_symbols: 'Symbols',
      activity_config: 'Configuration',
      // Device
      test_serial: 'Test serial throughput to find max transfer size',
      clear_slot: 'Clear slot',
      // Symbols
      symbols_hint:
        'Single-click: view disassembly; Double-click: create patch',
      // Transfer
      upload_file: 'Upload files to device',
      upload_folder: 'Upload folder to device',
      download_file: 'Download selected file',
      rename_file: 'Rename selected file',
      cancel_transfer: 'Cancel transfer',
      // Terminal
      pause: 'Pause',
      // Theme
      toggle_theme: 'Toggle Theme',
      // Config items
      elf_path:
        'Path to the compiled ELF file for symbol lookup and disassembly',
      compile_commands_path:
        'Path to compile_commands.json for accurate compile flags',
      toolchain_path: 'Path to cross-compiler toolchain bin directory',
      patch_mode:
        'Trampoline: Use code trampoline (default)\nDebugMonitor: Use DebugMonitor exception\nDirect: Direct code replacement',
      auto_compile:
        'Automatically compile and inject when source files are saved',
      watch_dirs: 'Directories to watch for file changes',
      chunk_size:
        'Size of each uploaded data block. Smaller values are more stable but slower.',
      tx_chunk_size:
        'TX chunk size for serial commands (bytes). 0 = disabled. Workaround for slow serial drivers.',
      tx_chunk_delay: 'Delay between TX chunks. Only used when TX Chunk > 0.',
      transfer_max_retries:
        'Maximum retry attempts for file transfer when CRC mismatch occurs.',
      wakeup_shell_cnt:
        'Number of newlines to send before entering fl mode to wake up shell.',
      verify_crc: 'Verify file integrity with CRC after transfer',
      log_file_path: 'Path to save serial logs',
      log_file_enabled: 'Record serial communication logs to file',
      serial_echo_enabled: 'Echo TX commands to SERIAL panel (for debugging)',
      ghidra_path:
        'Path to Ghidra installation directory (containing support/analyzeHeadless)',
      enable_decompile:
        'Enable decompilation when creating patch templates (requires Ghidra)',
      ui_language: 'UI display language',
    },
  },
};
