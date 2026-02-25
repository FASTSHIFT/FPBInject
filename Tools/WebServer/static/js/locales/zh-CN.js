/*========================================
  FPBInject Workbench - 简体中文翻译
  ========================================*/

window.i18nResources = window.i18nResources || {};
window.i18nResources['zh-CN'] = {
  translation: {
    // 侧边栏
    sidebar: {
      connection: '连接',
      config: '配置',
      explorer: '浏览器',
      device: '热补丁',
      transfer: '文件传输',
      symbols: '符号',
      file_transfer: '文件传输',
    },

    // 配置组
    config: {
      groups: {
        connection: '连接',
        project: '项目路径',
        inject: '注入',
        transfer: '传输',
        logging: '日志',
        tools: '分析工具',
        ui: '用户界面',
      },
      // 配置项标签
      labels: {
        elf_path: 'ELF 路径',
        compile_commands_path: '编译数据库',
        toolchain_path: '工具链',
        patch_mode: '注入模式',
        auto_compile: '保存时自动注入',
        watch_dirs: '监视目录',
        chunk_size: '块大小',
        tx_chunk_size: '发送块大小',
        tx_chunk_delay: '发送延迟',
        transfer_max_retries: '最大重试次数',
        wakeup_shell_cnt: '唤醒次数',
        verify_crc: '传输后校验 CRC',
        log_file_path: '日志路径',
        log_file_enabled: '记录串口日志',
        serial_echo_enabled: '串口发送回显',
        ghidra_path:
          '<a href="https://github.com/NationalSecurityAgency/ghidra" target="_blank" style="color: var(--vscode-textLink-foreground); text-decoration: underline;">Ghidra <i class="codicon codicon-link-external" style="font-size: 10px;"></i></a> 路径',
        enable_decompile: '启用反编译',
        ui_theme: '主题',
        ui_language: '语言',
      },
      // 配置选项值
      options: {
        dark: '深色',
        light: '浅色',
      },
    },

    // 连接面板
    connection: {
      port: '端口',
      baudrate: '波特率',
      connect: '连接',
      disconnect: '断开',
      connecting: '连接中...',
      refresh: '刷新',
      status: {
        connected: '已连接',
        disconnected: '未连接',
      },
    },

    // 按钮
    buttons: {
      inject: '注入',
      compile: '编译',
      browse: '浏览',
      save: '保存',
      cancel: '取消',
      clear: '清除',
      refresh: '刷新',
      add: '添加',
      remove: '移除',
      start: '开始',
      stop: '停止',
    },

    // 标签页
    tabs: {
      patch: '补丁',
      symbols: '符号',
      output: '输出',
      serial: '串口',
      problems: '问题',
    },

    // 面板
    panels: {
      fpb_slots: '热补丁',
      slot_empty: '空闲',
      slot_occupied: '已占用',
      no_file_open: '未打开文件',
      no_symbols: '未加载符号',
      memory_not_available: '内存信息不可用',
      click_refresh: '点击"刷新"加载文件',
      search_placeholder: '按名称或地址搜索',
    },

    // 状态栏
    statusbar: {
      ready: '就绪',
      compiling: '编译中...',
      injecting: '注入中...',
      connected: '已连接',
      disconnected: '未连接',
      watcher_off: '监视器: 关闭',
      watcher_on: '监视器: 开启',
      slot: '槽位: {{slot}}',
    },

    // 消息
    messages: {
      config_saved: '配置已保存',
      connect_success: '连接成功',
      connect_failed: '连接失败',
      inject_success: '注入成功',
      inject_failed: '注入失败',
      compile_success: '编译成功',
      compile_failed: '编译失败',
      // 设备探测消息
      not_connected: '未连接到设备',
      ping_success: '设备已探测到',
      device_responding: '设备正在响应',
      ping_failed: '设备探测失败',
      device_not_responding: '设备无响应',
      error: '错误',
      // 设备信息消息
      device_info_success: '设备信息已获取',
      device_info_failed: '获取设备信息失败',
      fpb_version: 'FPB 版本',
      build_time: '构建时间',
      memory_used: '已用内存',
      slots_used: '已用槽位',
      unknown_error: '未知错误',
      // 构建时间不匹配
      build_time_mismatch: '构建时间不匹配',
      build_time_mismatch_desc: '设备固件和 ELF 文件的构建时间不同。',
      build_time_mismatch_warn: '这可能导致注入失败或行为异常。',
      device_firmware: '设备固件',
      elf_file: 'ELF 文件',
      build_time_mismatch_hint: '请确保 ELF 文件与设备上运行的固件匹配。',
    },

    // 模态框
    modals: {
      file_browser: '文件浏览器',
      go: '前往',
      select: '选择',
    },

    // 编辑器
    editor: {
      slot: '槽位',
      no_file_open: '未打开文件',
    },

    // 传输
    transfer: {
      file: '文件',
      folder: '文件夹',
      download: '下载',
      upload: '上传',
      cancel: '取消',
    },

    // 设备
    device: {
      ping: '探测设备',
      info: '获取信息',
      test: '吞吐测试',
      clear_all: '清除所有',
      slot_n: '槽位 {{n}}',
      fpb_v2_only: '仅 FPB v2',
      fpb_v2_required: '此补丁需要 FPB v2 硬件',
      bytes: '字节',
      used: '已用',
    },

    // 提示
    tooltips: {
      // 活动栏
      activity_connection: '连接',
      activity_device: '热补丁',
      activity_transfer: '文件传输',
      activity_symbols: '符号',
      activity_config: '配置',
      // 设备
      test_serial: '测试串口吞吐量以找到最大传输大小',
      clear_slot: '清除槽位',
      // 符号
      symbols_hint: '单击：查看反汇编；双击：创建补丁',
      // 传输
      upload_file: '上传文件到设备',
      upload_folder: '上传文件夹到设备',
      download_file: '下载选中的文件',
      rename_file: '重命名选中的文件',
      cancel_transfer: '取消传输',
      // 终端
      pause: '暂停',
      // 主题
      toggle_theme: '切换主题',
      // 配置项
      elf_path: '编译后的 ELF 文件路径，用于符号查找和反汇编',
      compile_commands_path:
        'compile_commands.json 路径，用于获取准确的编译参数',
      toolchain_path: '交叉编译工具链 bin 目录路径',
      patch_mode:
        'Trampoline: 使用代码跳板（默认）\nDebugMonitor: 使用调试监视器异常\nDirect: 直接代码替换',
      auto_compile: '源文件保存时自动编译并注入',
      watch_dirs: '监视文件变化的目录',
      chunk_size: '每个上传数据块的大小。较小的值更稳定但更慢。',
      tx_chunk_size:
        '串口命令的发送块大小（字节）。0 = 禁用。用于解决慢速串口驱动问题。',
      tx_chunk_delay: '发送块之间的延迟。仅在发送块大小 > 0 时使用。',
      transfer_max_retries: 'CRC 校验失败时的最大重试次数。',
      wakeup_shell_cnt: '进入 fl 模式前发送换行符的次数，用于唤醒 shell。',
      verify_crc: '传输后使用 CRC 校验文件完整性',
      log_file_path: '串口日志保存路径',
      log_file_enabled: '将串口通信日志记录到文件',
      serial_echo_enabled: '在串口面板回显发送的命令（用于调试）',
      ghidra_path: 'Ghidra 安装目录路径（包含 support/analyzeHeadless）',
      enable_decompile: '创建补丁模板时启用反编译（需要 Ghidra）',
      ui_theme: '界面颜色主题',
      ui_language: '界面显示语言',
    },
  },
};
