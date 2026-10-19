/* ============================================================================
 * dsh-plugin-win-desktop-kit — 桌面/文档小工具（profile bundle, Host half）
 *
 * 把工作区里零散但可复用的自制脚本封装成 DSH 工具：
 *   pdf-extract.py → pdf_extract      PDF 取文本（pypdf → PyPDF2 → 纯标准库三级回退）
 *   drill.ps1      → dir_sizes        用 robocopy /L 快速统计各子目录占用（Windows）
 *   make_icon.py   → icon_build       SVG 路径 → 多尺寸 ICO/PNG（纯标准库）
 *   build.bat      → launcher_build   用系统自带 csc.exe 编译 Harness.exe（Windows）
 *
 * 这里不放任何会删除文件的东西：drill.ps1 是 robocopy /L（只列不拷），
 * build.bat 只覆盖它自己目录下的 Harness.exe。
 * ========================================================================== */

import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'win-desktop-kit'
export const inject = ['tools']

const PAYLOAD = join(dirname(fileURLToPath(import.meta.url)), '..', 'payload')

/* -------------------------------------------------------------------- 进程 */

function run(argv, opts = {}) {
  return new Promise((resolveResult) => {
    let child
    try {
      child = spawn(argv[0], argv.slice(1), {
        cwd: opts.cwd || PAYLOAD,
        env: { ...process.env, ...(opts.env || {}) },
        windowsHide: true,
      })
    } catch (error) {
      resolveResult({ code: -1, stdout: '', stderr: String((error && error.message) || error), timedOut: false })
      return
    }
    const cap = opts.maxBytes || 4000000
    let stdout = ''
    let stderr = ''
    let timedOut = false
    let timer = null
    if (opts.timeoutMs) {
      timer = setTimeout(() => {
        timedOut = true
        try { child.kill('SIGKILL') } catch { /* 已经退出 */ }
      }, opts.timeoutMs)
    }
    child.stdout.on('data', (d) => { if (stdout.length < cap) stdout += d.toString('utf8') })
    child.stderr.on('data', (d) => { if (stderr.length < cap) stderr += d.toString('utf8') })
    child.on('error', (error) => {
      if (timer) clearTimeout(timer)
      resolveResult({ code: -1, stdout, stderr: stderr + String((error && error.message) || error), timedOut })
    })
    child.on('close', (code) => {
      if (timer) clearTimeout(timer)
      resolveResult({ code, stdout, stderr, timedOut })
    })
  })
}

async function toWindowsPath(linuxPath) {
  if (process.platform === 'win32') return linuxPath
  const r = await run(['wslpath', '-w', linuxPath], { timeoutMs: 15000 })
  return (r.code === 0 && r.stdout.trim()) ? r.stdout.trim() : linuxPath
}

function resolvePowerShell() {
  if (process.env.DSH_POWERSHELL) return process.env.DSH_POWERSHELL
  if (process.platform === 'win32') return 'powershell.exe'
  const interop = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
  return existsSync(interop) ? interop : 'powershell.exe'
}

const PY_CANDIDATES = ['python3', 'python', 'py']

/* 同 pptx 插件：Windows 下强制 UTF-8，避免中文/特殊字符触发 GBK 编码错误。 */
const PY_ENV = { PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' }

/**
 * dsh desktop 自带受管 Python（resources/runtime/primary-runtime/dependencies/python）。
 * 桌面版用户机器上往往没有系统 Python，所以优先用它。
 */
function desktopRuntimePython() {
  const exe = process.platform === 'win32' ? 'python.exe' : 'python3'
  const rel = ['runtime', 'primary-runtime', 'dependencies', 'python', exe]
  const bases = []
  if (process.env.DSH_DESKTOP_RUNTIME) bases.push(process.env.DSH_DESKTOP_RUNTIME)
  if (process.resourcesPath) bases.push(process.resourcesPath)
  let dir = ''
  try { dir = dirname(process.execPath || '') } catch { dir = '' }
  for (let i = 0; i < 7 && dir; i += 1) {
    bases.push(dir, join(dir, 'resources'))
    const parent = dirname(dir)
    if (parent === dir) break
    dir = parent
  }
  for (const base of bases) {
    try {
      const candidate = join(base, ...rel)
      if (existsSync(candidate)) return candidate
    } catch { /* 忽略非法路径 */ }
  }
  return undefined
}

/** 找一个能跑起来的解释器（这里不要求任何第三方库）。 */
async function resolvePython() {
  const override = process.env.DSH_PYTHON
  const candidates = override ? [override] : [desktopRuntimePython(), ...PY_CANDIDATES].filter(Boolean)
  for (const candidate of candidates) {
    const r = await run([candidate, '-c', 'print(1)'], { timeoutMs: 20000, env: PY_ENV })
    if (r.code === 0) return candidate
  }
  return null
}

function define(ctx, spec) {
  ctx.tools.register({
    name: spec.name,
    description: spec.description,
    parameters: { type: 'object', properties: spec.properties, required: spec.required || [] },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: String(value) }],
    },
    execute: async (args) => {
      try {
        return await spec.execute(args || {})
      } catch (error) {
        return '工具内部错误：' + String((error && error.message) || error)
      }
    },
  })
}

/* ------------------------------------------------------------------- 注册 */

export function apply(ctx) {
  /* --- PDF 取文本 -------------------------------------------------------- */
  define(ctx, {
    name: 'pdf_extract',
    description: '从 PDF 提取纯文本，返回 {"text": ..., "pages": N} 的 JSON。'
      + '优先用 pypdf，其次 PyPDF2，都没有时退回纯标准库解析（只能读未嵌入字体/CID 的简单 PDF）。'
      + '注意：扫描件没有文字层，提取结果会是空的。',
    properties: {
      path: { type: 'string', description: '.pdf 文件路径（必填）。' },
    },
    required: ['path'],
    async execute(args) {
      if (!args.path) return '缺少必填参数 path。'
      if (!existsSync(args.path)) return '文件不存在：' + args.path
      const python = await resolvePython()
      if (!python) return '未找到 Python 解释器（python3 / python / py）。'
      const r = await run([python, join(PAYLOAD, 'pdf-extract.py'), args.path], { timeoutMs: 180000, env: PY_ENV })
      const text = [r.stdout.trim(), r.stderr.trim()].filter(Boolean).join('\n')
      if (r.code !== 0) return '退出码 ' + String(r.code) + '。\n' + text
      return text
    },
  })

  /* --- 目录占用统计 ------------------------------------------------------ */
  define(ctx, {
    name: 'dir_sizes',
    description: '统计某个目录下每个子目录的占用（Windows，用 robocopy /L 只列不拷，速度快），'
      + '并标出超过 100 MB 的目录。用来找「磁盘被什么吃掉了」。',
    properties: {
      root: { type: 'string', description: '要统计的目录，例如 C:\\Users\\<你的用户名>（必填）。' },
    },
    required: ['root'],
    async execute(args) {
      if (!args.root) return '缺少必填参数 root。'
      const scriptPath = await toWindowsPath(join(PAYLOAD, 'drill.ps1'))
      const r = await run([resolvePowerShell(), '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', scriptPath, '-Root', args.root], { timeoutMs: 600000 })
      const text = [r.stdout.trim(), r.stderr.trim()].filter(Boolean).join('\n')
      if (r.timedOut) return '超时（已终止）。\n' + text
      if (r.code !== 0) return '退出码 ' + String(r.code) + '（需要 Windows）。\n' + text
      return text
    },
  })

  /* --- 图标生成 ---------------------------------------------------------- */
  define(ctx, {
    name: 'icon_build',
    description: '从一个含 SVG path 的源码文件（例如 FishLogo.tsx）里取出路径，'
      + '生成透明背景的多尺寸 ICO 与 256px PNG 预览。纯 Python 标准库，不需要 Pillow。',
    properties: {
      src: { type: 'string', description: '含 d="..." 的源文件路径（必填）。' },
      outIco: { type: 'string', description: '输出 .ico 路径；默认写回插件 payload 目录。' },
      outPng: { type: 'string', description: '输出预览 .png 路径。' },
    },
    required: ['src'],
    async execute(args) {
      if (!args.src) return '缺少必填参数 src。'
      if (!existsSync(args.src)) return '文件不存在：' + args.src
      const python = await resolvePython()
      if (!python) return '未找到 Python 解释器（python3 / python / py）。'
      const argv = [python, join(PAYLOAD, 'make_icon.py'), resolve(args.src)]
      if (args.outIco) argv.push(resolve(args.outIco))
      if (args.outPng) argv.push(resolve(args.outPng))
      const r = await run(argv, { timeoutMs: 180000, env: PY_ENV })
      const text = [r.stdout.trim(), r.stderr.trim()].filter(Boolean).join('\n')
      if (r.code !== 0) return '退出码 ' + String(r.code) + '。\n' + text
      return text.split('\n').slice(-3).join('\n')  // 前面是 ASCII 预览，只留结论
    },
  })

  /* --- 编译启动器 -------------------------------------------------------- */
  define(ctx, {
    name: 'launcher_build',
    description: '用 Windows 自带 .NET Framework 的 csc.exe 编译 payload 里的 launcher.cs，'
      + '生成 Harness.exe（无控制台窗口的托盘启动器：探测服务是否在线 → 打开浏览器）。'
      + '需要 .NET Framework 4.x，无需安装任何 SDK。编译产物写在插件 payload 目录。',
    properties: {},
    async execute() {
      const batPath = join(PAYLOAD, 'build.bat')
      if (!existsSync(batPath)) return 'build.bat 不存在：' + batPath
      const hostBat = await toWindowsPath(batPath)
      const r = await run(['cmd.exe', '/c', hostBat], { timeoutMs: 300000, cwd: PAYLOAD })
      const text = [r.stdout.trim(), r.stderr.trim()].filter(Boolean).join('\n')
      if (r.code !== 0) return '退出码 ' + String(r.code) + '（需要 Windows + .NET Framework 4.x）。\n' + text
      return text + '\n产物：' + join(PAYLOAD, 'Harness.exe')
    },
  })
}
