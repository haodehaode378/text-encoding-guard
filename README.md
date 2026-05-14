# AI Text Encoding Guard

[中文](#中文) | [English](#english)

> AI 编码助手把中文搞成乱码了？自动检测，一键修复。
>
> AI agents corrupting your Chinese text? Detect it, fix it, ship it.

[![CI](https://github.com/haodehaode378/text-encoding-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/haodehaode378/text-encoding-guard/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ai-text-encoding-guard)](https://pypi.org/project/ai-text-encoding-guard/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 中文

### 问题：AI 编码的"编码刺客"

你让 Claude / Cursor / Copilot 改个注释，它顺手把整段中文变成了乱码。你没发现，直接 merge。第二天用户看到的是这个：

```
修复前（乱码）                    修复后（正常）
──────────────────────           ──────────────────────
// 鐢ㄦ埛鐧诲綍鎴愬姛               // 用户登录成功
// 鏁版嵁搴撹繛鎺ュけ璐�             // 数据库连接失败
// 璁㈠崟鍒涘缓鎴愬姛锛屽崟鍙凤細         // 订单创建成功，单号：
```

**这不是假设。** 这是每天都在发生的事。AI 助手在编辑文件时，UTF-8 字节被误读为 GBK，中文就废了。更隐蔽的是 HTML 标签损坏：

```html
<!-- AI 编辑后 -->
<div class="user-card">
  <p>鐢ㄦ埛涓�績</p>
  ?/div>          <!-- ← </div> 的 < 被吃掉了 -->

<!-- 应该是 -->
<div class="user-card">
  <p>用户中心</p>
</div>
```

### 谁会中招

| 场景 | 中招概率 | 后果 |
|------|----------|------|
| Claude Code 编辑含中文的 Vue/React 组件 | 极高 | UI 文案全变乱码，用户直接看到 |
| Cursor 批量重构中文注释 | 高 | 代码可读性归零，新人看不懂 |
| Copilot 生成中文文档 | 中 | README/CHANGELOG 变天书 |
| CI/CD 自动化脚本处理中文文件 | 中 | 静默损坏，上线后才发现 |

### 安装

```bash
pip install ai-text-encoding-guard
```

或从源码安装：

```bash
git clone https://github.com/haodehaode378/text-encoding-guard.git
cd text-encoding-guard
pip install -e ".[test]"
```

### 快速开始

```bash
# 扫描项目
check-mojibake --root ./src

# 自动修复（创建 .bak 备份）
check-mojibake --root ./src --fix-gbk

# JSON 输出
check-mojibake --root ./src --json

# CI 卡点：有乱码就失败
check-mojibake --root . --fail-on-find
```

不安装也可以直接用：

```bash
python scripts/check_mojibake.py --root ./src
# 或
python -m check_mojibake --root ./src
```

### 七大检测维度

| 乱码类型 | 产生原因 | 检测信号 | 权重 |
|----------|----------|----------|------|
| 口字码 | UTF-8 读 GBK | Unicode 替换字符 `�` | +12/个 |
| 破标签 | AI 编辑吞尖括号 | 损坏的 HTML 闭合标签 (`?/div>`) | +10/个 |
| 古文码 | GBK 读 UTF-8 | 18 个已知乱码码点 | +2/个 |
| 锟拷码 | UTF-8→GBK→UTF-8 双重转换 | `锟斤拷` 模式匹配 | +8/次 |
| 烫屯码 | VC 调试未初始化内存 | `烫烫烫`/`屯屯屯` 重复模式 | +6/次 |
| 问句码 | 双重转换 | 中文后连续 `??` | +8/次 |
| 符号码 | ISO8859-1 读 UTF-8/GBK | 拉丁扩展字符密集出现 | +2/个 |

文件总分 > 0 即标记为可疑。分数越高，乱码越严重。

### 修复机制

`--fix-gbk` 不是盲目替换。它遵循**三重安全门**：

```
1. 尝试 GB18030 编码 → UTF-8 解码（逆向还原）
   也尝试反方向：UTF-8 编码 → GB18030 解码
2. 修复后分数必须 ≤ 原分数的 1/3
3. 绝对改善值必须 ≥ 8 分
   ↓
全部通过 → 写入修复 + 创建 .bak.mojibake 备份
任一失败 → 跳过，标记为需人工检查
```

### CI 集成（GitHub Actions）

**一行搞定：**

```yaml
name: Encoding Guard
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: haodehaode378/text-encoding-guard@v1
```

PR 有乱码自动拦截。

**可选参数：**

```yaml
- uses: haodehaode378/text-encoding-guard@v1
  with:
    root: './src'              # 扫描目录（默认 .）
    fix-gbk: 'true'            # 自动修复（默认 false）
    ext: '.sql,.cfg'           # 额外扩展名
```

### AI 助手集成

#### Claude Code（自动触发）

两步搞定，之后每次编辑自动扫描：

**Step 1** — 添加 PostToolUse hook 到 `.claude/settings.json`：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python scripts/check_mojibake.py --root ."
          }
        ]
      }
    ]
  }
}
```

**Step 2**（可选）— 安装 skill 到 `.claude/skills/`：

```bash
cp -r .claude/skills/text-encoding-guard/ /path/to/your/project/.claude/skills/text-encoding-guard/
```

效果：Claude 每次调用 `Edit` 或 `Write` 后，自动运行乱码检查。

### CLI 完整参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--root PATH` | 要扫描的根目录（必填） | `--root ./src` |
| `--json` | JSON 格式输出 | `--json` |
| `--fail-on-find` | 发现可疑文件时退出码 2（CI 用） | `--fail-on-find` |
| `--fix-gbk` | 尝试自动 GBK→UTF-8 修复 | `--fix-gbk` |
| `--ext` | 添加额外扩展名（可多次） | `--ext .sql --ext .cfg` |
| `--verbose` | 显示详细诊断信息 | `-v` |
| `--quiet` | 静默模式，仅输出必要信息 | `-q` |

### 扫描范围

**默认扫描 20 种扩展名：**
`.py` `.md` `.txt` `.json` `.yaml` `.yml` `.toml` `.ini` `.js` `.ts` `.tsx` `.jsx` `.vue` `.html` `.css` `.scss` `.sh` `.bat` `.ps1` `.xml`

**自动跳过：**
`.git` `node_modules` `dist` `build` `__pycache__` `.venv` `venv` `target` `.idea` `.vscode` `.claude`

### 为什么选这个

| 对比项 | 本工具 | 手动检查 | file/uchardet |
|--------|--------|----------|---------------|
| 精确检测乱码 | ✅ 评分制 | ❌ 肉眼看 | ❌ 只检测编码，不检测乱码 |
| 自动修复 | ✅ 保守策略+备份 | ❌ | ❌ |
| CI 集成 | ✅ 退出码 2 | ❌ | ❌ |
| AI 助手自动触发 | ✅ hooks/skill | ❌ | ❌ |
| 零依赖 | ✅ 纯 stdlib | N/A | 需要安装 |
| pip 安装 | ✅ | N/A | - |
| 双向修复 | ✅ UTF-8↔GBK | ❌ | ❌ |

---

## English

### The Problem

When AI coding assistants (Claude Code, Cursor, Copilot, Codex) edit files containing Chinese text, encoding corruption silently creeps in. UTF-8 bytes get misread as GBK, turning readable text into garbage:

```
Before (corrupted)              After (recovered)
─────────────────────           ──────────────────────
// 鐢ㄦ埛鐧诲綍鎴愬姛             // 用户登录成功
// 鏁版嵁搴撹繛鎺ュけ璐�           // 数据库连接失败
// 璁㈠崟鍒涘缓鎴愬姛              // 订单创建成功
```

Broken HTML tags are also caught:

```html
<!-- corrupted -->
<p>鐢ㄦ埛涓�績</p>
?/div>

<!-- recovered -->
<p>用户中心</p>
</div>
```

### Installation

```bash
pip install ai-text-encoding-guard
```

### Quick Start

```bash
# Scan a project
check-mojibake --root ./src

# Auto-fix (creates .bak files first)
check-mojibake --root ./src --fix-gbk

# JSON output
check-mojibake --root ./src --json

# CI gate: fail on findings
check-mojibake --root . --fail-on-find
```

Without installation:

```bash
python scripts/check_mojibake.py --root ./src
```

### CI Integration (GitHub Actions)

**One line:**

```yaml
name: Encoding Guard
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: haodehaode378/text-encoding-guard@v1
```

**Optional parameters:**

```yaml
- uses: haodehaode378/text-encoding-guard@v1
  with:
    root: './src'              # scan directory (default .)
    fix-gbk: 'true'            # auto-fix (default false)
    ext: '.sql,.cfg'           # extra extensions
```

### AI Agent Integration

#### Claude Code (auto-run on every edit)

Add a hook to `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python scripts/check_mojibake.py --root ."
          }
        ]
      }
    ]
  }
}
```

### How It Works

| Mojibake Type | Cause | Detection | Weight |
|---------------|-------|-----------|--------|
| Box chars | UTF-8 read as GBK | Unicode replacement `�` | +12/each |
| Broken tags | AI swallows `<` | Malformed end tags (`?/div>`) | +10/each |
| Ancient text | GBK read as UTF-8 | 18 known mojibake codepoints | +2/each |
| Kun-Kao | UTF-8→GBK→UTF-8 | `锟斤拷` pattern | +8/match |
| Tang-Tun | VC debug memory | `烫烫烫`/`屯屯屯` repeats | +6/match |
| Question code | Double conversion | `??` after CJK text | +8/match |
| Symbol code | ISO8859-1 read as UTF-8 | Latin diacritics (ç, æ, é) | +2/each |

### CLI Reference

| Flag | Description | Example |
|------|-------------|---------|
| `--root PATH` | Root directory to scan (required) | `--root ./src` |
| `--json` | JSON output | `--json` |
| `--fail-on-find` | Exit code 2 on findings (for CI) | `--fail-on-find` |
| `--fix-gbk` | Attempt GBK→UTF-8 auto-recovery | `--fix-gbk` |
| `--ext` | Extra extensions (repeatable) | `--ext .sql --ext .cfg` |
| `--verbose` | Show extra diagnostics | `-v` |
| `--quiet` | Suppress non-essential output | `-q` |

### Project Structure

```
src/check_mojibake/     # Python package (pip installable)
scripts/                # Standalone script (no install needed)
.github/workflows/      # CI pipeline
tests/                  # pytest test suite
action.yml              # GitHub Action definition
```

---

## Development

```bash
# Install dev dependencies
pip install -e ".[test]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/check_mojibake --cov-report=term-missing
```

## License

[MIT](LICENSE)
