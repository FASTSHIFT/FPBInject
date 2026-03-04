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
      quick_commands: '快捷指令',
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
        ghidra_path: 'Ghidra 路径',
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
      starting: '启动中...',
      compiling: '编译中...',
      injecting: '注入中...',
      detecting: '检测变更中...',
      generating: '生成补丁中...',
      auto_inject_complete: '自动注入完成！',
      auto_inject_failed: '自动注入失败！',
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
      // 后端断开连接
      backend_disconnected: '后端服务器已断开连接。',
      backend_restart_hint: '请重启服务器并刷新页面。',
      // CRC 错误
      crc_verification_failed: 'CRC 校验失败！',
      file_may_be_corrupted: '传输的文件可能已损坏。',
      // 传输错误
      upload_failed: '上传失败',
      download_failed: '下载失败',
      folder_download_not_supported:
        '不支持文件夹下载，请只选择文件，或者将文件夹打包后下载。',
      transfer_stats: '传输统计',
      retries: '重试次数',
      crc_errors: 'CRC 错误',
      timeout_errors: '超时错误',
      packet_loss: '丢包率',
      // 删除确认
      confirm_delete: '确定要删除',
      directory: '目录',
      // 注入失败
      injection_failed_count: '{{count}} 个注入失败！',
      failed_functions: '失败的函数',
      slots_full_hint: '这可能是因为 FPB 槽位已满。',
      clear_slots_hint: '请在设备信息面板中清除一些槽位后重试。',
      // 串口测试
      serial_test_complete: '串口吞吐测试完成！',
      current_chunk_size: '当前块大小',
      recommended_chunk_size: '推荐块大小',
      apply_recommended_size: '是否应用推荐的块大小？',
      // ELF 监视器
      elf_file_changed: 'ELF 文件 "{{fileName}}" 已更改。',
      reload_symbols_now: '立即重新加载符号？',
      // 槽位警告
      all_slots_occupied: '所有 {{count}} 个 FPB 槽位都已占用！',
      current_slots: '当前槽位',
      clear_slots_before_inject: '请在注入前清除一些槽位。',
      use_clear_all_hint: '使用"清除所有"按钮或点击单个槽位上的 ✕。',
      click_ok_to_open_device: '点击确定打开设备信息面板。',
      slot_occupied_by: '槽位 {{slot}} 已被 "{{func}}" 占用。',
      overwrite_slot: '是否覆盖？',
      // 清除所有槽位
      confirm_clear_all_slots: '确定要清除所有 FPB 槽位吗？',
      unpatch_all_warning: '这将取消所有已注入的函数。',
      // 重新注入
      no_inject_cache: '没有可重新注入的缓存',
      confirm_reinject: '确定重新注入 {{count}} 个文件？',
      reinject_success: '重新注入完成：{{count}} 个成功',
      reinject_partial: '重新注入：{{success}} 个成功，{{fail}} 个失败',
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

    // 快捷指令
    quick_commands: {
      new_command: '新建命令',
      edit_command: '编辑命令',
      single_command: '单条命令',
      command_macro: '命令组合',
      name: '名称',
      name_placeholder: '例如 ps -A',
      command: '命令',
      command_placeholder: '例如 ps -A',
      append_newline: '追加换行符 (\\n)',
      steps: '步骤',
      add_step: '添加步骤',
      group: '分组',
      no_group: '无分组',
      new_group: '+ 新建分组...',
      group_name_placeholder: '分组名称',
      test_run: '试运行',
      execute: '执行',
      more: '更多',
      drag_to_reorder: '拖拽排序',
      remove: '移除',
      edit: '编辑',
      duplicate: '复制',
      delete: '删除',
      move_to_group: '移动到分组...',
      import: '导入命令...',
      export: '导出全部...',
      clear_all: '清空全部',
      empty: '暂无命令',
      unnamed: '命令',
      unnamed_macro: '宏',
      macro_summary: '共 {{count}} 条命令，约 {{seconds}} 秒',
      confirm_delete: '删除「{{name}}」？',
      confirm_clear: '删除全部 {{count}} 条命令？',
      nothing_to_export: '没有可导出的命令',
      invalid_format: '文件格式无效',
      import_error: '导入失败：',
      imported_count: '已导入 {{count}} 条命令',
      move_prompt: '输入分组名称（留空取消分组）：',
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
      reinject: '重新注入',
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
      activity_quick_commands: '快捷指令',
      more_actions: '更多操作',
      // 设备
      ping: '检测设备是否已连接并响应',
      info: '获取设备 FPB 硬件信息',
      test_serial: '测试串口吞吐量以找到最大传输大小',
      reinject: '重新注入所有缓存的文件',
      clear_all: '清除所有 FPB 槽位',
      clear_slot: '清除槽位',
      reinject_all: '重新注入全部 ({{count}} 个文件)',
      slot_original: '劫持地址',
      slot_target: '跳转地址',
      slot_code_size: '代码大小',
      // 终端
      pause: '暂停',
      resume: '继续',
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
        'Trampoline: 使用代码跳板（仅 FPB v1）\nDebugMonitor: 使用调试监视器异常（FPB v1/v2）\nDirect: 直接代码替换（仅 FPB v1）\n注意: FPB v2 仅支持 DebugMonitor 模式，会自动切换',
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

    // 教学引导
    tutorial: {
      next: '下一步',
      prev: '上一步',
      skip: '跳过',
      skip_all: '跳过全部',
      finish: '开始使用',
      step_of: '{{current}} / {{total}}',
      btn_title: '教学引导',
      btn_label: '教学',

      welcome_title: '欢迎使用 FPBInject Workbench',
      welcome_desc:
        '基于 ARM Cortex-M FPB 硬件单元的运行时代码注入工具。<br><br>本教程将带您了解所有功能的位置。',

      appearance_title: '语言和主题',
      appearance_desc: '首先，选择您偏好的语言和主题。',
      appearance_language: '语言',
      appearance_language_desc: '从下拉菜单切换界面语言。',
      appearance_theme: '主题',
      appearance_theme_desc: '在深色和浅色主题之间切换。',

      connection_title: '串口连接',
      connection_desc: '连接区域用于通过串口连接您的设备。',
      connection_port: '串口端口',
      connection_port_desc: '从下拉菜单选择设备端口。点击刷新按钮扫描新端口。',
      connection_baudrate: '波特率',
      connection_baudrate_desc: '设置通信速度（默认：115200）。',
      connection_connect: '连接按钮',
      connection_connect_desc: '点击以建立与设备的连接。',

      device_title: '热补丁',
      device_desc: '设备区域显示已连接设备的信息。',
      device_info: '设备信息',
      device_info_desc: '查看设备状态、FPB 硬件能力和活动补丁。',
      device_ping: 'Ping 设备',
      device_ping_desc: '测试设备响应性并检查连接健康状态。',
      device_slots: 'FPB 槽位',
      device_slots_desc: '查看可用和已使用的 FPB 比较器槽位。',

      quickcmd_title: '快捷指令',
      quickcmd_desc: '快捷指令可以发送串口命令或执行宏命令。',
      quickcmd_feature_single: '单条命令',
      quickcmd_feature_single_desc: '即时向设备发送一条串口命令。',
      quickcmd_feature_macro: '组合命令',
      quickcmd_feature_macro_desc: '按顺序执行多条命令，支持配置延时。',
      quickcmd_add: '添加命令',
      quickcmd_add_desc: '创建自定义命令并组织它们以便快速访问。',

      transfer_title: '文件传输',
      transfer_desc: '传输区域处理与设备的文件操作。',
      transfer_upload: '上传文件',
      transfer_upload_desc: '从计算机发送文件到设备文件系统。',
      transfer_download: '下载文件',
      transfer_download_desc: '从设备检索文件到本地系统。',
      transfer_browse: '浏览文件系统',
      transfer_browse_desc: '导航设备目录并远程管理文件。',

      symbols_title: '符号分析',
      symbols_desc: '符号区域帮助您分析固件函数。',
      symbols_search: '搜索函数',
      symbols_search_desc: '通过名称模式在 ELF 固件中查找函数。',
      symbols_disasm: '反汇编',
      symbols_disasm_desc: '查看选定函数的汇编指令。',
      symbols_decompile: '反编译',
      symbols_decompile_desc: '使用 Ghidra 生成伪 C 代码以便更好理解。',

      config_title: '配置',
      config_desc: '配置区域包含所有工作台设置。',
      config_ui: 'UI 设置',
      config_ui_desc: '语言、主题和界面偏好设置。',
      config_project: '项目路径',
      config_project_desc: 'ELF 固件文件和编译数据库位置。',
      config_inject: '注入设置',
      config_inject_desc: '补丁模式、文件监视和自动注入选项。',
      config_more: '更多选项',
      config_more_desc: '串口、终端、日志和高级设置。',
      config_hint: '展开每个部分以配置设置。',

      complete_title: '教程完成！',
      complete_desc: '您现在知道在哪里找到所有功能了。',
      complete_configured: '已访问',
      complete_skipped: '已跳过',
      complete_hint: '点击标题栏的 🎓 按钮可随时重新进入教学。',

      // 门控提示
      gate_connection: '⏳ 请在左侧边栏连接设备后，再点击下一步。',
      gate_connection_ok: '✅ 设备连接成功！',
      gate_device: '⏳ 请点击「吞吐测试」按钮优化串口传输参数。',
      gate_device_ok: '✅ 吞吐测试完成！',
      gate_transfer: '⏳ 请在传输区域点击「刷新」加载文件列表。',
      gate_transfer_ok: '✅ 文件列表加载成功！',
      gate_config:
        '⏳ 请填写 ELF 路径、编译数据库、工具链，添加监控目录，并启用自动注入。',
      gate_config_ok: '✅ 所有配置项已设置！',
      gate_config_elf: 'ELF 路径',
      gate_config_compiledb: '编译数据库',
      gate_config_toolchain: '工具链',
      gate_config_watchdirs: '监控目录',
      gate_config_autoinject: '自动注入',
    },
  },
};
