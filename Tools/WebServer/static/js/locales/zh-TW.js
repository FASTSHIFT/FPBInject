/*========================================
  FPBInject Workbench - 繁體中文翻譯
  ========================================*/

window.i18nResources = window.i18nResources || {};
window.i18nResources['zh-TW'] = {
  translation: {
    // 側邊欄
    sidebar: {
      connection: '連線',
      config: '設定',
      explorer: '瀏覽器',
      device: '熱補丁',
      transfer: '檔案傳輸',
      symbols: '符號',
      file_transfer: '檔案傳輸',
      quick_commands: '快捷指令',
    },

    // 設定組
    config: {
      groups: {
        connection: '連線',
        project: '專案路徑',
        inject: '注入',
        transfer: '傳輸',
        logging: '日誌',
        tools: '分析工具',
        ui: '使用者介面',
      },
      // 設定項標籤
      labels: {
        elf_path: 'ELF 路徑',
        compile_commands_path: '編譯資料庫',
        toolchain_path: '工具鏈',
        patch_mode: '注入模式',
        auto_compile: '儲存時自動注入',
        watch_dirs: '監視目錄',
        chunk_size: '區塊大小',
        tx_chunk_size: '傳送區塊大小',
        tx_chunk_delay: '傳送延遲',
        transfer_max_retries: '最大重試次數',
        wakeup_shell_cnt: '喚醒次數',
        verify_crc: '傳輸後驗證 CRC',
        log_file_path: '日誌路徑',
        log_file_enabled: '記錄串列埠日誌',
        serial_echo_enabled: '串列埠傳送回顯',
        ghidra_path: 'Ghidra 路徑',
        enable_decompile: '啟用反編譯',
        ui_theme: '主題',
        ui_language: '語言',
      },
      // 配置選項值
      options: {
        dark: '深色',
        light: '淺色',
      },
    },

    // 連線面板
    connection: {
      port: '連接埠',
      baudrate: '鮑率',
      connect: '連線',
      disconnect: '斷開',
      connecting: '連線中...',
      refresh: '重新整理',
      advanced_settings: '進階設定',
      data_bits: '資料位元',
      parity: '校驗位元',
      stop_bits: '停止位元',
      flow_control: '流量控制',
      parity_none: '無',
      parity_even: 'Even',
      parity_odd: 'Odd',
      parity_mark: 'Mark',
      parity_space: 'Space',
      flow_none: '無',
      status: {
        connected: '已連線',
        disconnected: '未連線',
      },
    },

    // 按鈕
    buttons: {
      inject: '注入',
      compile: '編譯',
      browse: '瀏覽',
      save: '儲存',
      cancel: '取消',
      clear: '清除',
      refresh: '重新整理',
      add: '新增',
      remove: '移除',
      start: '開始',
      stop: '停止',
    },

    // 標籤頁
    tabs: {
      patch: '補丁',
      symbols: '符號',
      output: '輸出',
      serial: '串列埠',
      problems: '問題',
    },

    // 面板
    panels: {
      fpb_slots: '熱補丁',
      slot_empty: '空閒',
      slot_occupied: '已佔用',
      no_file_open: '未開啟檔案',
      no_symbols: '未載入符號',
      memory_not_available: '記憶體資訊不可用',
      click_refresh: '點擊「重新整理」載入檔案',
      search_placeholder: '按名稱或地址搜尋',
    },

    // 狀態列
    statusbar: {
      ready: '就緒',
      starting: '啟動中...',
      compiling: '編譯中...',
      injecting: '注入中...',
      detecting: '偵測變更中...',
      generating: '產生補丁中...',
      auto_inject_complete: '自動注入完成！',
      auto_inject_failed: '自動注入失敗！',
      connected: '已連線',
      disconnected: '未連線',
      watcher_off: '監視器: 關閉',
      watcher_on: '監視器: 開啟',
      slot: '槽位: {{slot}}',
    },

    // 訊息
    messages: {
      config_saved: '設定已儲存',
      connect_success: '連線成功',
      connect_failed: '連線失敗',
      inject_success: '注入成功',
      inject_failed: '注入失敗',
      compile_success: '編譯成功',
      compile_failed: '編譯失敗',
      // 裝置探測訊息
      not_connected: '未連線到裝置',
      ping_success: '裝置已探測到',
      device_responding: '裝置正在回應',
      ping_failed: '裝置探測失敗',
      device_not_responding: '裝置無回應',
      error: '錯誤',
      // 裝置資訊訊息
      device_info_success: '裝置資訊已取得',
      device_info_failed: '取得裝置資訊失敗',
      fpb_version: 'FPB 版本',
      build_time: '建置時間',
      memory_used: '已用記憶體',
      slots_used: '已用槽位',
      unknown_error: '未知錯誤',
      // 建置時間不符
      build_time_mismatch: '建置時間不符',
      build_time_mismatch_desc: '裝置韌體和 ELF 檔案的建置時間不同。',
      build_time_mismatch_warn: '這可能導致注入失敗或行為異常。',
      device_firmware: '裝置韌體',
      elf_file: 'ELF 檔案',
      build_time_mismatch_hint: '請確保 ELF 檔案與裝置上執行的韌體相符。',
      // 後端斷開連線
      backend_disconnected: '後端伺服器已斷開連線。',
      backend_restart_hint: '請重新啟動伺服器並重新整理頁面。',
      // CRC 錯誤
      crc_verification_failed: 'CRC 校驗失敗！',
      file_may_be_corrupted: '傳輸的檔案可能已損壞。',
      // 傳輸錯誤
      upload_failed: '上傳失敗',
      download_failed: '下載失敗',
      folder_download_not_supported:
        '不支援資料夾下載，請只選擇檔案，或者將資料夾打包後下載。',
      transfer_stats: '傳輸統計',
      retries: '重試次數',
      crc_errors: 'CRC 錯誤',
      timeout_errors: '逾時錯誤',
      packet_loss: '封包遺失率',
      // 刪除確認
      confirm_delete: '確定要刪除',
      directory: '目錄',
      // 注入失敗
      injection_failed_count: '{{count}} 個注入失敗！',
      failed_functions: '失敗的函式',
      slots_full_hint: '這可能是因為 FPB 槽位已滿。',
      clear_slots_hint: '請在裝置資訊面板中清除一些槽位後重試。',
      // 序列埠測試
      serial_test_complete: '序列埠吞吐測試完成！',
      current_chunk_size: '目前區塊大小',
      recommended_chunk_size: '建議區塊大小',
      apply_recommended_size: '是否套用建議的區塊大小？',
      // ELF 監視器
      elf_file_changed: 'ELF 檔案 "{{fileName}}" 已變更。',
      reload_symbols_now: '立即重新載入符號？',
      // 槽位警告
      all_slots_occupied: '所有 {{count}} 個 FPB 槽位都已佔用！',
      current_slots: '目前槽位',
      clear_slots_before_inject: '請在注入前清除一些槽位。',
      use_clear_all_hint: '使用「清除所有」按鈕或點擊單個槽位上的 ✕。',
      click_ok_to_open_device: '點擊確定開啟裝置資訊面板。',
      slot_occupied_by: '槽位 {{slot}} 已被 "{{func}}" 佔用。',
      overwrite_slot: '是否覆蓋？',
      // 清除所有槽位
      confirm_clear_all_slots: '確定要清除所有 FPB 槽位嗎？',
      unpatch_all_warning: '這將取消所有已注入的函式。',
      // 重新注入
      no_inject_cache: '沒有可重新注入的快取',
      confirm_reinject: '確定重新注入 {{count}} 個檔案？',
      reinject_success: '重新注入完成：{{count}} 個成功',
      reinject_partial: '重新注入：{{success}} 個成功，{{fail}} 個失敗',
    },

    // 模態框
    modals: {
      file_browser: '檔案瀏覽器',
      go: '前往',
      select: '選擇',
    },

    // 編輯器
    editor: {
      slot: '槽位',
      no_file_open: '未開啟檔案',
    },

    // 快捷指令
    quick_commands: {
      new_command: '新增指令',
      edit_command: '編輯指令',
      single_command: '單條指令',
      command_macro: '指令組合',
      name: '名稱',
      name_placeholder: '例如 ps -A',
      command: '指令',
      command_placeholder: '例如 ps -A',
      append_newline: '附加換行符 (\\n)',
      steps: '步驟',
      add_step: '新增步驟',
      group: '分組',
      no_group: '無分組',
      new_group: '+ 新增分組...',
      group_name_placeholder: '分組名稱',
      test_run: '試執行',
      execute: '執行',
      more: '更多',
      drag_to_reorder: '拖曳排序',
      remove: '移除',
      edit: '編輯',
      duplicate: '複製',
      delete: '刪除',
      move_to_group: '移至分組...',
      import: '匯入指令...',
      export: '匯出全部...',
      clear_all: '清除全部',
      empty: '尚無指令',
      unnamed: '指令',
      unnamed_macro: '巨集',
      macro_summary: '共 {{count}} 條指令，約 {{seconds}} 秒',
      confirm_delete: '刪除「{{name}}」？',
      confirm_clear: '刪除全部 {{count}} 條指令？',
      nothing_to_export: '沒有可匯出的指令',
      invalid_format: '檔案格式無效',
      import_error: '匯入失敗：',
      imported_count: '已匯入 {{count}} 條指令',
      move_prompt: '輸入分組名稱（留空取消分組）：',
    },

    // 傳輸
    transfer: {
      file: '檔案',
      folder: '資料夾',
      download: '下載',
      upload: '上傳',
      cancel: '取消',
    },

    // 裝置
    device: {
      ping: '探測裝置',
      info: '取得資訊',
      test: '吞吐測試',
      clear_all: '清除所有',
      reinject: '重新注入',
      slot_n: '槽位 {{n}}',
      fpb_v2_only: '僅 FPB v2',
      fpb_v2_required: '此補丁需要 FPB v2 硬體',
      bytes: '位元組',
      used: '已用',
    },

    // 提示
    tooltips: {
      // 活動列
      activity_connection: '連線',
      activity_device: '熱補丁',
      activity_transfer: '檔案傳輸',
      activity_symbols: '符號',
      activity_config: '設定',
      activity_quick_commands: '快捷指令',
      more_actions: '更多操作',
      // 裝置
      ping: '檢測裝置是否已連線並回應',
      info: '取得裝置 FPB 硬體資訊',
      test_serial: '測試串列埠吞吐量以找到最大傳輸大小',
      reinject: '重新注入所有快取的檔案',
      clear_all: '清除所有 FPB 槽位',
      clear_slot: '清除槽位',
      reinject_all: '重新注入全部 ({{count}} 個檔案)',
      slot_original: '劫持地址',
      slot_target: '跳轉地址',
      slot_code_size: '程式碼大小',
      // 終端
      pause: '暫停',
      resume: '繼續',
      // 符號
      symbols_hint: '單擊：查看反組譯；雙擊：建立補丁',
      // 傳輸
      upload_file: '上傳檔案到裝置',
      upload_folder: '上傳資料夾到裝置',
      download_file: '下載選中的檔案',
      rename_file: '重新命名選中的檔案',
      cancel_transfer: '取消傳輸',
      // 終端
      pause: '暫停',
      // 主題
      toggle_theme: '切換主題',
      // 設定項
      elf_path: '編譯後的 ELF 檔案路徑，用於符號查詢和反組譯',
      compile_commands_path:
        'compile_commands.json 路徑，用於取得準確的編譯參數',
      toolchain_path: '交叉編譯工具鏈 bin 目錄路徑',
      patch_mode:
        'Trampoline: 使用程式碼跳板（僅 FPB v1）\nDebugMonitor: 使用除錯監視器例外（FPB v1/v2）\nDirect: 直接程式碼替換（僅 FPB v1）\n注意: FPB v2 僅支援 DebugMonitor 模式，會自動切換',
      auto_compile: '原始檔儲存時自動編譯並注入',
      watch_dirs: '監視檔案變化的目錄',
      chunk_size: '每個上傳資料區塊的大小。較小的值更穩定但更慢。',
      tx_chunk_size:
        '串列埠命令的傳送區塊大小（位元組）。0 = 停用。用於解決慢速串列埠驅動問題。',
      tx_chunk_delay: '傳送區塊之間的延遲。僅在傳送區塊大小 > 0 時使用。',
      transfer_max_retries: 'CRC 驗證失敗時的最大重試次數。',
      wakeup_shell_cnt: '進入 fl 模式前傳送換行符的次數，用於喚醒 shell。',
      verify_crc: '傳輸後使用 CRC 驗證檔案完整性',
      log_file_path: '串列埠日誌儲存路徑',
      log_file_enabled: '將串列埠通訊日誌記錄到檔案',
      serial_echo_enabled: '在串列埠面板回顯傳送的命令（用於除錯）',
      ghidra_path: 'Ghidra 安裝目錄路徑（包含 support/analyzeHeadless）',
      enable_decompile: '建立補丁範本時啟用反編譯（需要 Ghidra）',
      ui_theme: '介面顏色主題',
      ui_language: '介面顯示語言',
    },

    // 教學引導
    tutorial: {
      next: '下一步',
      prev: '上一步',
      skip: '跳過',
      skip_all: '跳過全部',
      finish: '開始使用',
      step_of: '{{current}} / {{total}}',
      btn_title: '教學引導',
      btn_label: '教學',

      welcome_title: '歡迎使用 FPBInject Workbench',
      welcome_desc:
        '基於 ARM Cortex-M FPB 硬體單元的執行時程式碼注入工具。<br><br>本教學將帶您了解所有功能的位置。',

      appearance_title: '語言和主題',
      appearance_desc: '首先，選擇您偏好的語言和主題。',
      appearance_language: '語言',
      appearance_language_desc: '從下拉選單切換介面語言。',
      appearance_theme: '主題',
      appearance_theme_desc: '在深色和淺色主題之間切換。',

      connection_title: '串列埠連線',
      connection_desc: '連線區域用於透過串列埠連線您的裝置。',
      connection_port: '串列埠連接埠',
      connection_port_desc:
        '從下拉選單選擇裝置連接埠。點擊重新整理按鈕掃描新連接埠。',
      connection_baudrate: '鮑率',
      connection_baudrate_desc: '設定通訊速度（預設：115200）。',
      connection_connect: '連線按鈕',
      connection_connect_desc: '點擊以建立與裝置的連線。',

      device_title: '熱補丁',
      device_desc: '裝置區域顯示已連線裝置的資訊。',
      device_info: '裝置資訊',
      device_info_desc: '檢視裝置狀態、FPB 硬體能力和活動補丁。',
      device_ping: 'Ping 裝置',
      device_ping_desc: '測試裝置回應性並檢查連線健康狀態。',
      device_slots: 'FPB 槽位',
      device_slots_desc: '檢視可用和已使用的 FPB 比較器槽位。',

      quickcmd_title: '快捷指令',
      quickcmd_desc: '快捷指令可以傳送串列埠命令或執行巨集命令。',
      quickcmd_feature_single: '單條命令',
      quickcmd_feature_single_desc: '即時向裝置傳送一條串列埠命令。',
      quickcmd_feature_macro: '組合命令',
      quickcmd_feature_macro_desc: '按順序執行多條命令，支援設定延遲。',
      quickcmd_add: '新增命令',
      quickcmd_add_desc: '建立自訂命令並組織它們以便快速存取。',

      transfer_title: '檔案傳輸',
      transfer_desc: '傳輸區域處理與裝置的檔案操作。',
      transfer_upload: '上傳檔案',
      transfer_upload_desc: '從電腦傳送檔案到裝置檔案系統。',
      transfer_download: '下載檔案',
      transfer_download_desc: '從裝置擷取檔案到本機系統。',
      transfer_browse: '瀏覽檔案系統',
      transfer_browse_desc: '導覽裝置目錄並遠端管理檔案。',

      symbols_title: '符號分析',
      symbols_desc: '符號區域幫助您分析韌體函式。',
      symbols_search: '搜尋函式',
      symbols_search_desc: '透過名稱模式在 ELF 韌體中查詢函式。',
      symbols_disasm: '反組譯',
      symbols_disasm_desc: '檢視選定函式的組合語言指令。',
      symbols_decompile: '反編譯',
      symbols_decompile_desc: '使用 Ghidra 產生偽 C 程式碼以便更好理解。',

      editor_title: '程式碼編輯器',
      editor_desc: '編輯器區域用於撰寫和修改補丁程式碼。',
      editor_tabs: '檔案標籤',
      editor_tabs_desc: '開啟多個補丁檔案，透過標籤頁在它們之間切換。',
      editor_edit: '程式碼編輯',
      editor_edit_desc:
        '使用語法醒目提示撰寫補丁程式碼。使用 <code>/* FPB_INJECT */</code> 標記來指定可注入的函式。',
      editor_inject: '儲存和注入',
      editor_inject_desc:
        '儲存補丁檔案並點擊注入按鈕將其套用到裝置，或啟用自動注入實現免手動操作。',

      logs_title: '輸出和串列埠',
      logs_desc: '底部面板顯示系統輸出和串列埠通訊。',
      logs_output: '輸出',
      logs_output_desc: '檢視編譯結果、注入日誌和系統訊息。',
      logs_serial: '串列埠',
      logs_serial_desc:
        '互動式串列埠終端，用於與裝置直接通訊。您可以傳送命令並檢視即時回應。',

      config_title: '設定',
      config_desc: '設定區域包含所有工作台設定。',
      config_ui: 'UI 設定',
      config_ui_desc: '語言、主題和介面偏好設定。',
      config_project: '專案路徑',
      config_project_desc: 'ELF 韌體檔案和編譯資料庫位置。',
      config_inject: '注入設定',
      config_inject_desc: '補丁模式、檔案監視和自動注入選項。',
      config_more: '更多選項',
      config_more_desc: '串列埠、終端、日誌和進階設定。',
      config_autoinject_title: '自動注入原理',
      config_autoinject_desc:
        '啟用後，系統會監控您指定目錄中的檔案修改動作。任何包含 <code>/* FPB_INJECT */</code> 標記的檔案都會被自動編譯，並透過 FPB 硬體在執行時注入裝置，替換原始函式，無需重新燒錄韌體。',
      config_autoinject_example: '補丁檔案範例：',
      config_hint: '展開每個部分以設定選項。',

      complete_title: '教學完成！',
      complete_desc: '您現在知道在哪裡找到所有功能了。',
      complete_configured: '已造訪',
      complete_skipped: '已跳過',
      complete_hint: '點擊標題列的 🎓 按鈕可隨時重新進入教學。',

      // 門控提示
      gate_connection: '⏳ 請在左側邊欄連線裝置後，再點擊下一步。',
      gate_connection_ok: '✅ 裝置連線成功！',
      gate_device: '⏳ 請點擊「吞吐測試」按鈕優化串列埠傳輸參數。',
      gate_device_ok: '✅ 吞吐測試完成！',
      gate_transfer: '⏳ 請在傳輸區域點擊「重新整理」載入檔案列表。',
      gate_transfer_ok: '✅ 檔案列表載入成功！',
      gate_config:
        '⏳ 請填寫 ELF 路徑、編譯資料庫、工具鏈，新增監控目錄，並啟用自動注入。',
      gate_config_ok: '✅ 所有設定項已完成！',
      gate_config_elf: 'ELF 路徑',
      gate_config_compiledb: '編譯資料庫',
      gate_config_toolchain: '工具鏈',
      gate_config_watchdirs: '監控目錄',
      gate_config_autoinject: '自動注入',
      gate_logs: '⏳ 請點擊底部面板的「串列埠」標籤。',
      gate_logs_ok: '✅ 串列埠終端已啟用！',

      // 注入體驗步驟
      demo_search_title: '搜尋目標函式',
      demo_search_desc: '接下來實際體驗一次注入！在符號面板中搜尋演示函式。',
      demo_search_input: '搜尋符號',
      demo_search_input_desc:
        '在搜尋框中輸入 <code>fl_cmd_demo</code> 並按 Enter。',
      demo_search_result: '檢視結果',
      demo_search_result_desc: '列表中會顯示 ELF 韌體中的函式位址和名稱。',
      demo_search_dblclick: '雙擊建立補丁',
      demo_search_dblclick_desc: '雙擊符號，編輯器中會自動產生補丁範本程式碼。',
      gate_demo_search:
        '⏳ 請搜尋 <code>fl_cmd_demo</code> 並雙擊建立補丁標籤頁。',
      gate_demo_search_ok: '✅ 補丁標籤頁已建立！',

      demo_inject_title: '編輯並注入補丁',
      demo_inject_desc: '生成的補丁範本可以直接注入，選擇槽位後點擊注入即可。',
      demo_inject_edit: '修改程式碼',
      demo_inject_edit_desc:
        '將 <code>fl_println</code> 中的字串改為您自己的訊息。',
      demo_inject_slot: '選擇 Slot',
      demo_inject_slot_desc: '確認工具列的 Slot 下拉框選擇了可用槽位。',
      demo_inject_run: '點擊「注入」按鈕',
      demo_inject_run_desc: '點擊工具列的「注入」按鈕，等待注入完成。',
      gate_demo_inject: '⏳ 請選擇槽位後點擊「注入」按鈕。',
      gate_demo_inject_ok: '✅ 注入成功！',

      demo_verify_title: '驗證注入效果',
      demo_verify_desc: '在串口終端傳送 demo 命令，驗證注入是否生效。',
      demo_verify_send_cmd: '傳送命令',
      demo_verify_send_cmd_desc:
        '已自動進入 fl 模式，在串口終端輸入 <code>--cmd demo</code> 並按 Enter。',
      demo_verify_check_output: '檢查輸出',
      demo_verify_check_output_desc: '輸出應顯示注入後的訊息，而不是原始訊息。',

      demo_unpatch_title: '取消注入',
      demo_unpatch_desc: '移除注入並驗證原始函式已恢復。',
      demo_unpatch_click: '點擊 ✕ 取消注入',
      demo_unpatch_click_desc:
        '在熱補丁面板中，點擊已佔用槽位的 ✕ 按鈕移除注入。',
      demo_unpatch_verify: '驗證恢復',
      demo_unpatch_verify_desc:
        '在 fl 模式下再次傳送 <code>--cmd demo</code>，輸出應恢復為原始訊息。',
      gate_demo_unpatch: '⏳ 請點擊已佔用槽位的 ✕ 按鈕取消注入。',
      gate_demo_unpatch_ok: '✅ 已取消注入！',
      demo_unpatch_hint:
        '這就是 FPB 執行時程式碼注入的完整流程 — 無需重新燒錄即可替換任意函式！',
    },
  },
};
