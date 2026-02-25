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
      device: 'DEVICE',
      transfer: 'TRANSFER',
      symbols: 'SYMBOLS',
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
        ui_theme: 'Theme',
        ui_language: 'Language',
      },
      // Config option values
      options: {
        dark: 'Dark',
        light: 'Light',
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
      no_ports: '-- No ports available --',
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
      no_port_selected: 'Please select a serial port first.',
      check_port_hint:
        'Please check if the device is connected and the port is correct.',
      inject_success: 'Injection successful',
      inject_failed: 'Injection failed',
      compile_success: 'Compilation successful',
      compile_failed: 'Compilation failed',
      // Device detection messages
      not_connected: 'Not connected to device',
      ping_success: 'Device Detected',
      device_responding: 'Device is responding',
      ping_failed: 'Device Detection Failed',
      device_not_responding: 'Device is not responding',
      error: 'Error',
      // Device info messages
      device_info_success: 'Device Info Retrieved',
      device_info_failed: 'Failed to Get Device Info',
      fpb_version: 'FPB Version',
      build_time: 'Build Time',
      memory_used: 'Memory Used',
      slots_used: 'Slots Used',
      unknown_error: 'Unknown error',
      // Build time mismatch
      build_time_mismatch: 'Build Time Mismatch',
      build_time_mismatch_desc:
        'The device firmware and ELF file have different build times.',
      build_time_mismatch_warn:
        'This may cause injection to fail or behave unexpectedly.',
      device_firmware: 'Device firmware',
      elf_file: 'ELF file',
      build_time_mismatch_hint:
        'Please ensure the ELF file matches the firmware running on the device.',
      // Backend disconnection
      backend_disconnected: 'Backend server has disconnected.',
      backend_restart_hint: 'Please restart the server and refresh the page.',
      // CRC errors
      crc_verification_failed: 'CRC Verification Failed!',
      file_may_be_corrupted: 'The transferred file may be corrupted.',
      // Transfer errors
      upload_failed: 'Upload failed',
      download_failed: 'Download failed',
      transfer_stats: 'Transfer Statistics',
      retries: 'Retries',
      crc_errors: 'CRC errors',
      timeout_errors: 'Timeout errors',
      packet_loss: 'Packet loss',
      // Delete confirmation
      confirm_delete: 'Are you sure you want to delete',
      directory: 'directory',
      // Injection failures
      injection_failed_count: '{{count}} injection(s) failed!',
      failed_functions: 'Failed functions',
      slots_full_hint: 'This may be due to FPB Slots being full.',
      clear_slots_hint:
        'Please clear some Slots in DEVICE INFO panel and try again.',
      // Serial test
      serial_test_complete: 'Serial Throughput Test Complete!',
      current_chunk_size: 'Current chunk size',
      recommended_chunk_size: 'Recommended chunk size',
      apply_recommended_size:
        'Do you want to apply the recommended chunk size?',
      // ELF watcher
      elf_file_changed: 'ELF file "{{fileName}}" has changed.',
      reload_symbols_now: 'Reload symbols now?',
      // Slot warnings
      all_slots_occupied: 'All {{count}} FPB Slots are occupied!',
      current_slots: 'Current slots',
      clear_slots_before_inject: 'Please clear some slots before injecting.',
      use_clear_all_hint:
        'Use "Clear All" button or click ✕ on individual slots.',
      click_ok_to_open_device: 'Click OK to open Device Info panel.',
      slot_occupied_by: 'Slot {{slot}} is already occupied by "{{func}}".',
      overwrite_slot: 'Do you want to overwrite it?',
      // Clear all slots
      confirm_clear_all_slots: 'Are you sure you want to clear all FPB slots?',
      unpatch_all_warning: 'This will unpatch all injected functions.',
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
      ui_theme: 'UI color theme',
      ui_language: 'UI display language',
    },
  },
};
