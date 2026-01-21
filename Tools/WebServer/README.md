# FPBInject WebServer

基于 FPB (Flash Patch and Breakpoint) 单元的热补丁注入工具，支持在不重新烧录固件的情况下动态修改运行中的函数。

## 功能特性

- 🔥 **热补丁注入**：实时修改目标函数，无需重新编译烧录
- 📝 **标记式开发**：在源码中添加 `/* FPB_INJECT */` 标记即可自动检测
- 🔄 **文件监控**：自动监控源文件变化，保存即注入
- 🖥️ **Web 界面**：VS Code 风格的现代化 UI
- 📟 **串口终端**：内置串口监控和交互终端

## 快速开始

### 1. 下位机部署 (NuttX)

#### 克隆仓库

```bash
cd apps/examples
git clone https://github.com/FASTSHIFT/FPBInject.git
```

#### 配置编译

```bash
# 进入 NuttX 根目录
cd nuttx

# 打开 menuconfig
make menuconfig
```

在 menuconfig 中启用 FPBInject：

```
Application Configuration  --->
    Examples  --->
        [*] FPBInject - FPB based function injection
```

#### 编译烧录

```bash
make -j$(nproc)
# 使用你的烧录工具烧录固件
```

### 2. 上位机部署 (WebServer)

#### 安装依赖

```bash
cd apps/examples/FPBInject/Tools/WebServer
pip install -r requirements.txt
```

#### 启动服务

```bash
./main.py
# 或
python3 main.py
```

服务默认运行在 `http://127.0.0.1:5500`

### 3. 使用流程

#### 3.1 配置连接

1. 打开浏览器访问 `http://127.0.0.1:5500`
2. 在 **Settings** 面板中配置：
   - **Serial Port**：选择设备串口（如 `/dev/ttyACM0`）
   - **ELF Path**：选择编译生成的 ELF 文件路径
   - **Toolchain Path**：配置交叉编译工具链路径（如 `arm-none-eabi-`）
   - **Compile Commands**：选择 `compile_commands.json` 路径（用于获取编译参数）

3. 点击 **Connect** 连接设备

#### 3.2 标记函数

在需要热补丁的函数前添加标记注释：

```c
/* FPB_INJECT */
void my_function(int arg)
{
    // 你的代码
}
```

支持的标记格式：
- `/* FPB_INJECT */`
- `/* FPB-INJECT */`
- `// FPB_INJECT`
- `/*FPB_INJECT*/`（大小写不敏感）

#### 3.3 自动注入

1. 在 **Settings** 中启用 **Auto Compile**
2. 在 **Watch Dirs** 中添加源码目录
3. 修改带标记的源文件并保存
4. WebServer 会自动检测变化、编译并注入

#### 3.4 手动注入

1. 在左侧 **SYMBOLS** 列表中搜索双击目标函数
2. 在编辑器中修改代码
3. 点击 **Inject** 按钮执行注入

## 界面说明

### 主要区域

| 区域 | 说明 |
|------|------|
| **Device Info** | 显示设备连接状态、FPB Slot 使用情况 |
| **Functions** | 从 ELF 解析的函数列表，支持搜索 |
| **Editor** | 代码编辑区，支持语法高亮 |
| **OUTPUT** | 工具输出日志 |
| **SERIAL PORT** | 串口原始数据终端 |

### Slot 管理

FPB 硬件支持 6 个比较器（Slot），每个 Slot 可以拦截一个函数：

- 🟢 **绿色**：Slot 已占用
- ⚫ **灰色**：Slot 空闲
- 点击 **🔄** 重新注入
- 点击 **🗑️** 清除 Slot

## 配置文件

配置自动保存到 `~/.fpbinject_config.json`，包含：

```json
{
  "port": "/dev/ttyACM0",
  "baudrate": 115200,
  "elf_path": "/path/to/firmware.elf",
  "toolchain_path": "/path/to/toolchain/bin",
  "compile_commands_path": "/path/to/compile_commands.json",
  "watch_dirs": ["/path/to/source"],
  "auto_connect": true,
  "auto_compile": true
}
```

## 工作原理

1. **标记检测**：扫描源文件中的 `FPB_INJECT` 标记
2. **补丁生成**：复制源文件，将标记函数重命名为 `inject_xxx`
3. **交叉编译**：使用原始编译参数编译补丁代码
4. **代码上传**：通过串口将机器码上传到设备 RAM
5. **FPB 配置**：配置 FPB 单元将原函数调用重定向到新代码

## 故障排除

### 编译错误：找不到头文件

确保 `compile_commands.json` 路径正确，它包含了完整的编译参数和头文件路径。

### 注入失败：No available FPB slots

6 个 Slot 已全部占用，点击 **Clear All** 清除所有 Slot 后重试。

### 串口响应被日志打断

系统会自动重试，如果频繁失败，可以尝试降低其他模块的日志输出。

## 开发测试

```bash
# 运行所有测试
./test/run_tests.py

# 代码格式化
./format.sh
```

## License

MIT License
