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
        ghidra_path:
          '<a href="https://github.com/NationalSecurityAgency/ghidra" target="_blank" style="color: var(--vscode-textLink-foreground); text-decoration: underline;">Ghidra <i class="codicon codicon-link-external" style="font-size: 10px;"></i></a> 路徑',
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
      compiling: '編譯中...',
      injecting: '注入中...',
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
      // 裝置
      test_serial: '測試串列埠吞吐量以找到最大傳輸大小',
      clear_slot: '清除槽位',
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
        'Trampoline: 使用程式碼跳板（預設）\nDebugMonitor: 使用除錯監視器例外\nDirect: 直接程式碼替換',
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
  },
};
