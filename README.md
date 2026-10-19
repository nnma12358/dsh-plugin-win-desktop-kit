# dsh-plugin-win-desktop-kit

桌面与文档小工具。把工作区里零散但可复用的自制脚本封装成 4 个 DSH 工具。

## 工具

| 工具 | 对应脚本 | 说明 | 平台 |
|---|---|---|---|
| `pdf_extract` | `pdf-extract.py` | PDF 取文本 → `{text, pages}`。pypdf → PyPDF2 → 纯标准库三级回退 | 跨平台 |
| `dir_sizes` | `drill.ps1` | 用 `robocopy /L /XJ` 统计各子目录占用，标出 >100 MB 的目录 | Windows |
| `icon_build` | `make_icon.py` | 从含 SVG path 的源文件生成多尺寸透明 ICO + 256px PNG 预览 | 跨平台 |
| `launcher_build` | `build.bat` + `launcher.cs` | 用系统自带 csc.exe 编译 `Harness.exe` 启动器 | Windows |

### `pdf_extract`

三级回退：`pypdf` → `PyPDF2` → 纯标准库（直接解压 PDF 流并解析文本操作符）。
纯标准库路径读不了 CID/CMap 编码或嵌入字体的 PDF，扫描件（没有文字层）也会返回空文本。

### `dir_sizes`

`robocopy /L` 是**只列不拷**模式，不会改动任何文件；`/XJ` 跳过 junction，
避免目录联接造成的死循环。这是全套里唯一参数化、可安全对任意目录使用的统计脚本。

### `icon_build`

```
make_icon.py <FishLogo.tsx> [out.ico] [preview.png]
```
只用标准库（`math`/`re`/`struct`/`zlib`），不需要 Pillow。
源文件必须含 `d="..."`，否则报错退出（原版会直接 `AttributeError`）。

### `launcher_build`

```
Harness.exe                 # 探测服务 → 直接开浏览器
Harness.exe http://host:3080
```

编译只需要 Windows 自带的 `%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe`，
不用装 SDK。需要一个 `Harness.ico`（本包已附）。

## ⚠️ 关于 `Harness.exe` 的两件事

1. **它会把配置里的 `start` 字段当 shell 命令执行，且每次启动服务不在线时自动执行。**
   来自 `launcher.cs`：`new ProcessStartInfo("cmd.exe", "/c " + startCmd)`，异常被空 `catch` 吞掉。
   本包附带的是 `payload/harness-launcher.json.example`（`"start": ""`）。
   填 `start` 之前请确认你信任那个文件的内容——`&`、`|`、引号都能拼出新命令。
2. **配置必须和 exe 放在同一个目录。**
   `launcher.cs` 从 `AppDomain.CurrentDomain.BaseDirectory` 读 `harness-launcher.json`，
   不是当前工作目录。工作区里 `Harness.exe` 在根目录、配置在 `harness-launcher/` 子目录，
   所以现存的这个 exe **读不到任何配置**，会静默退回内置默认值并弹出窗口。

另：`launcher.cs` 把任何 HTTP 响应（含 4xx/5xx）都当作「服务在线」，
如果 3080 端口被别的程序占用，它会开浏览器指向错误的服务。

## 安装

桌面端 profile 由 Electron 应用独占管理（`dsh plugin --profile desktop …` 会被官方拒绝）。二选一：
应用内「设置 → 插件 → 添加本地插件」；或把目录放进
`%USERPROFILE%\.dsh\profiles\desktop\plugins\`，在该 profile 的 `package.json` 加 `link:` 依赖、
包名加入 `dsh.profile.bundles`，再用自带 pnpm 装依赖。装完重启 dsh desktop。

纯源码包，无构建步骤：`main` / `exports` 指向 `lib/`，`dsh.bundle.patch` 指向 `cordis.patch.yml`。
