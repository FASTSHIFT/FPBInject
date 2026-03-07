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
      file_transfer: 'FILE TRANSFER',
      quick_commands: 'QUICK COMMANDS',
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
      baudrate_custom: 'Custom',
      connect: 'Connect',
      disconnect: 'Disconnect',
      connecting: 'Connecting...',
      advanced_settings: 'Advanced Settings',
      data_bits: 'Data Bits',
      parity: 'Parity',
      stop_bits: 'Stop Bits',
      flow_control: 'Flow Control',
      parity_none: 'None',
      parity_even: 'Even',
      parity_odd: 'Odd',
      parity_mark: 'Mark',
      parity_space: 'Space',
      flow_none: 'None',
      status: {
        connected: 'Connected',
        disconnected: 'Disconnected',
      },
    },

    // Buttons
    buttons: {
      inject: 'Inject',
      browse: 'Browse',
      save: 'Save',
      cancel: 'Cancel',
      clear: 'Clear',
      refresh: 'Refresh',
      add: 'Add',
      remove: 'Remove',
    },

    // Tabs
    tabs: {
      symbols: 'SYMBOLS',
      output: 'OUTPUT',
      serial: 'SERIAL',
    },

    // Panels
    panels: {
      fpb_slots: 'FPB SLOTS',
      slot_empty: 'Empty',
      no_symbols: 'No symbols loaded',
      search_min_chars: 'Enter at least 2 characters',
      no_symbols_found: 'No symbols found',
      no_symbols_at_addr: 'No symbols found at this address',
      search_error: 'Error: {{message}}',
      memory_not_available: 'Memory info not available',
      click_refresh: "Click 'Refresh' to load files",
      search_placeholder: 'Search by name or address',
    },

    // Symbol viewer
    symbols: {
      searching: 'Searching...',
      reading: 'Reading...',
      writing: 'Writing...',
      bss_no_init: 'No initial value (.bss) — read from device to view',
      read_only: 'Read-Only',
      read_write: 'Read-Write',
      address: 'Address',
      size: 'Size',
      bytes: 'bytes',
      section: 'Section',
      raw_hex: 'Raw Hex',
      read_from_device: 'Read from Device',
      write_to_device: 'Write to Device',
      last_read: 'Last read',
      written_at: 'Written at',
      error: 'Error',
      no_hex_data: 'No hex data to write',
      invalid_hex: 'Invalid hex data',
      field: 'Field',
      type: 'Type',
      offset: 'Offset',
      value: 'Value',
      needs_device_read: 'needs device read',
      auto_read: 'Auto',
      auto_read_hint: 'Toggle periodic auto-read',
      auto_read_interval_hint: 'Auto-read interval (ms)',
      invalid_params: 'Invalid address or size',
    },

    // Watch expressions
    watch: {
      title: 'WATCH',
      add_placeholder: 'Add expression...',
      refresh_all: 'Refresh All',
      clear_all: 'Clear All',
      no_watches: 'No watch expressions',
      add_tooltip: 'Add',
      refresh_tooltip: 'Refresh',
      remove_tooltip: 'Remove',
      deref_tooltip: 'Dereference',
    },

    // Status bar
    // Status bar
    statusbar: {
      ready: 'Ready',
      starting: 'Starting...',
      compiling: 'Compiling...',
      injecting: 'Injecting...',
      detecting: 'Detecting changes...',
      generating: 'Generating patch...',
      auto_inject_complete: 'Auto-inject complete!',
      auto_inject_failed: 'Auto-inject failed!',
      connected: 'Connected',
      disconnected: 'Disconnected',
      watcher_off: 'Watcher: Off',
      watcher_on: 'Watcher: On',
      slot: 'Slot: {{slot}}',
      uploading: 'Uploading... {{uploaded}}/{{total}} bytes ({{percent}}%)',
      complete: 'Complete!',
      failed: 'Failed!',
      decompiling_start: 'Starting decompilation...',
      analyzing_elf: 'Analyzing ELF (first time)...',
      decompiling_func: 'Decompiling function...',
    },

    // Messages
    messages: {
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
      folder_download_not_supported:
        'Folder download is not supported. Please select files only, or package the folder before downloading.',
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
      // Reinject
      no_inject_cache: 'No injection cache available',
      confirm_reinject: 'Re-inject {{count}} file(s)?',
      reinject_partial: 'Re-injection: {{success}} succeeded, {{fail}} failed',
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

    // Quick Commands
    quick_commands: {
      new_command: 'New Command',
      edit_command: 'Edit Command',
      single_command: 'Single Command',
      command_macro: 'Command Macro',
      name: 'Name',
      name_placeholder: 'e.g. ps -A',
      command: 'Command',
      command_placeholder: 'e.g. ps -A',
      append_newline: 'Append newline (\\n)',
      steps: 'Steps',
      add_step: 'Add Step',
      group: 'Group',
      no_group: 'No Group',
      new_group: '+ New Group...',
      group_name_placeholder: 'Group name',
      test_run: 'Test Run',
      execute: 'Execute',
      more: 'More',
      drag_to_reorder: 'Drag to reorder',
      remove: 'Remove',
      edit: 'Edit',
      duplicate: 'Duplicate',
      delete: 'Delete',
      move_to_group: 'Move to Group...',
      import: 'Import Commands...',
      export: 'Export All...',
      clear_all: 'Clear All',
      empty: 'No commands yet',
      unnamed: 'Command',
      unnamed_macro: 'Macro',
      macro_summary: 'Total: {{count}} commands, ~{{seconds}}s',
      confirm_delete: 'Delete "{{name}}"?',
      confirm_clear: 'Delete all {{count}} commands?',
      nothing_to_export: 'No commands to export',
      invalid_format: 'Invalid file format',
      import_error: 'Failed to import: ',
      imported_count: 'Imported {{count}} commands',
      move_prompt: 'Enter group name (empty to ungroup):',
    },

    // Transfer
    transfer: {
      file: 'File',
      folder: 'Folder',
      download: 'Download',
    },

    // Device
    device: {
      ping: 'Ping Device',
      info: 'Get Info',
      test: 'Throughput Test',
      clear_all: 'Clear All',
      reinject: 'Re-inject',
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
      activity_quick_commands: 'Quick Commands',
      activity_watch: 'Watch',
      more_actions: 'More Actions',
      // Device
      ping: 'Detect if device is connected and responsive',
      info: 'Get device FPB hardware information',
      test_serial: 'Test serial throughput to find max transfer size',
      reinject: 'Re-inject all cached files',
      clear_all: 'Clear all FPB slots',
      clear_slot: 'Clear slot',
      reinject_all: 'Re-inject all ({{count}} files)',
      slot_original: 'Original',
      slot_target: 'Target',
      slot_code_size: 'Code size',
      // Terminal
      pause: 'Pause',
      resume: 'Resume',
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
        'Trampoline: Use code trampoline (FPB v1 only)\nDebugMonitor: Use DebugMonitor exception (FPB v1/v2)\nDirect: Direct code replacement (FPB v1 only)\nNote: FPB v2 only supports DebugMonitor mode, will auto-switch',
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

    // Tutorial
    tutorial: {
      next: 'Next',
      prev: 'Previous',
      skip: 'Skip',
      skip_all: 'Skip All',
      finish: 'Get Started',
      step_of: '{{current}} / {{total}}',
      btn_title: 'Tutorial',
      btn_label: 'Tutorial',

      welcome_title: 'Welcome to FPBInject Workbench',
      welcome_desc:
        'An ARM Cortex-M runtime code injection tool based on FPB hardware.<br><br>This guide will show you where to find all the features.',

      appearance_title: 'Language & Theme',
      appearance_desc: 'First, choose your preferred language and theme.',
      appearance_language: 'Language',
      appearance_language_desc:
        'Switch the interface language from the dropdown.',
      appearance_theme: 'Theme',
      appearance_theme_desc: 'Choose between dark and light theme.',

      connection_title: 'Serial Connection',
      connection_desc:
        'The Connection section lets you connect to your device via serial port.',
      connection_port: 'Serial Port',
      connection_port_desc:
        'Select your device port from the dropdown. Click refresh to scan for new ports.',
      connection_baudrate: 'Baud Rate',
      connection_baudrate_desc:
        'Set the communication speed (default: 115200).',
      connection_connect: 'Connect Button',
      connection_connect_desc:
        'Click to establish connection with your device.',

      device_title: 'Hot Patch',
      device_desc:
        'The Device section shows information about your connected device.',
      device_info: 'Device Info',
      device_info_desc:
        'View device status, FPB hardware capabilities, and active patches.',
      device_ping: 'Ping Device',
      device_ping_desc:
        'Test device responsiveness and check connection health.',
      device_slots: 'FPB Slots',
      device_slots_desc:
        'See available and used FPB comparator slots for patching.',

      quickcmd_title: 'Quick Commands',
      quickcmd_desc:
        'Quick commands let you send serial commands or execute macros.',
      quickcmd_feature_single: 'Single Command',
      quickcmd_feature_single_desc:
        'Send a serial command instantly to your device.',
      quickcmd_feature_macro: 'Macro',
      quickcmd_feature_macro_desc:
        'Execute a sequence of commands with configurable delays.',
      quickcmd_add: 'Add Commands',
      quickcmd_add_desc:
        'Create custom commands and organize them for quick access.',

      transfer_title: 'File Transfer',
      transfer_desc:
        'The Transfer section handles file operations with your device.',
      transfer_upload: 'Upload Files',
      transfer_upload_desc:
        'Send files from your computer to the device filesystem.',
      transfer_download: 'Download Files',
      transfer_download_desc:
        'Retrieve files from the device to your local system.',
      transfer_browse: 'Browse Filesystem',
      transfer_browse_desc:
        'Navigate device directories and manage files remotely.',

      symbols_title: 'Symbol Analysis',
      symbols_desc: 'The Symbols section helps you analyze firmware functions.',
      symbols_search: 'Search Functions',
      symbols_search_desc:
        'Find functions in your ELF firmware by name pattern.',
      symbols_disasm: 'Disassembly',
      symbols_disasm_desc: 'View assembly instructions for selected functions.',
      symbols_decompile: 'Decompile',
      symbols_decompile_desc:
        'Generate pseudo-C code using Ghidra for better understanding.',

      watch_title: 'Watch Expressions',
      watch_desc:
        'The Watch section lets you monitor C/C++ variables and expressions on the device in real time.',
      watch_add_expr: 'Add Expression',
      watch_add_expr_desc:
        'Type a C/C++ symbol name or cast expression (e.g. <code>g_counter</code>, <code>*(struct cfg *)0x20001000</code>).',
      watch_live_value: 'Live Value',
      watch_live_value_desc:
        'View decoded values, struct fields, and pointer targets read from device memory.',
      watch_refresh: 'Refresh',
      watch_refresh_desc:
        'Click Refresh All to re-read all watched values from the device.',

      config_title: 'Configuration',
      config_desc: 'The Configuration section contains all workbench settings.',
      config_ui: 'UI Settings',
      config_ui_desc: 'Language, theme, and interface preferences.',
      config_project: 'Project Paths',
      config_project_desc: 'ELF firmware file and compile database locations.',
      config_inject: 'Injection Settings',
      config_inject_desc: 'Patch mode, file watch, and auto-injection options.',
      config_more: 'More Options',
      config_more_desc: 'Serial, terminal, logging, and advanced settings.',
      config_autoinject_title: 'How Auto-Inject Works',
      config_autoinject_desc:
        'When enabled, the system monitors file changes in your specified watch directories. Any file containing the <code>/* FPB_INJECT */</code> marker will be automatically compiled and injected into the device at runtime via FPB hardware, replacing the original function without reflashing.',
      config_autoinject_example: 'Example patch file:',
      config_hint: 'Expand each section to configure settings.',

      complete_title: 'Tutorial Complete!',
      complete_desc: 'You now know where to find all the features.',
      complete_configured: 'Visited',
      complete_skipped: 'Skipped',
      complete_hint:
        'Click the 🎓 button in the title bar to restart this tutorial anytime.',

      // Gate messages
      gate_connection:
        '⏳ Please connect to your device using the sidebar, then click Next.',
      gate_connection_ok: '✅ Device connected successfully!',
      gate_device:
        '⏳ Please click "Throughput Test" to optimize serial transfer parameters.',
      gate_device_ok: '✅ Throughput test completed!',
      gate_transfer:
        '⏳ Please click "Refresh" in the Transfer section to load the file list.',
      gate_transfer_ok: '✅ File list loaded successfully!',
      gate_config:
        '⏳ Please fill in ELF path, compile database, toolchain, add watch directories, and enable auto-inject.',
      gate_config_ok: '✅ All configuration fields are set!',
      gate_config_elf: 'ELF Path',
      gate_config_compiledb: 'Compile Database',
      gate_config_toolchain: 'Toolchain',
      gate_config_watchdirs: 'Watch Directories',
      gate_config_autoinject: 'Auto-Inject',

      // Hello inject steps
      hello_search_title: 'Search Target Function',
      hello_search_desc:
        "Let's try a real injection! Search for the hello function in the Symbols panel.",
      hello_search_input: 'Search Symbol',
      hello_search_input_desc:
        'Type <code>fl_hello</code> in the search box and press Enter.',
      hello_search_result: 'View Results',
      hello_search_result_desc:
        'The list shows the function address and name from your ELF firmware.',
      hello_search_dblclick: 'Double-Click to Patch',
      hello_search_dblclick_desc:
        'Double-click the symbol to auto-generate a patch template in the editor.',
      gate_hello_search:
        '⏳ Please search for <code>fl_hello</code> and double-click to create a patch tab.',
      gate_hello_search_ok: '✅ Patch tab created!',

      hello_inject_title: 'Edit & Inject Patch',
      hello_inject_desc:
        'The generated patch template can be injected directly. Select a slot and click inject.',
      hello_inject_edit: 'Edit Code',
      hello_inject_edit_desc:
        'Change the <code>fl_println</code> string to your own message.',
      hello_inject_slot: 'Select Slot',
      hello_inject_slot_desc:
        'Make sure an available FPB slot is selected in the toolbar.',
      hello_inject_run: 'Click Inject',
      hello_inject_run_desc:
        'Click the inject button in the toolbar and wait for completion.',
      gate_hello_inject: '⏳ Please select a slot and click the inject button.',
      gate_hello_inject_ok: '✅ Injection successful!',

      gate_hello_verify:
        '⏳ Please switch to the Serial terminal tab to continue.',
      gate_hello_verify_ok: '✅ Serial terminal active!',

      hello_verify_title: 'Verify Injection',
      hello_verify_desc:
        'Send the hello command in the serial terminal to verify the injection effect.',
      hello_verify_send_cmd: 'Send Command',
      hello_verify_send_cmd_desc:
        'Type <code>fl -c hello</code> in the serial terminal and press Enter.',
      hello_verify_check_output: 'Check Output',
      hello_verify_check_output_desc:
        'The output should show the injected message instead of the original one.',

      hello_unpatch_title: 'Unpatch',
      hello_unpatch_desc:
        'Remove the injection and verify the original function is restored.',
      hello_unpatch_click: 'Click ✕ to Unpatch',
      hello_unpatch_click_desc:
        'In the Device Info panel, click the ✕ button on the occupied slot to remove the injection.',
      hello_unpatch_verify: 'Verify Restore',
      hello_unpatch_verify_desc:
        'Send <code>fl -c hello</code> again — the output should revert to the original message.',
      gate_hello_unpatch:
        '⏳ Please click ✕ on the occupied slot to remove the injection.',
      gate_hello_unpatch_ok: '✅ Unpatch complete!',
      hello_unpatch_hint:
        'This is the complete FPB runtime code injection workflow — replace any function without reflashing!',
    },
  },
};
