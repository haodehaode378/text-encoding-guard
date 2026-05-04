# AI Text Encoding Guard

[中文](#中文) | [English](#english)

> AI 编码助手把中文搞成乱码了？自动检测，一键修复。
>
> AI agents corrupting your Chinese text? Detect it, fix it, ship it.

---

## 中文

### 问题

AI 编程助手（Claude Code、Cursor、Copilot、Codex）编辑含中文的文件时，编码损坏会悄悄发生。UTF-8 字节被误读为 GBK，正常的中文变成乱码：

```
修复前（乱码）                  修复后（正常）
─────────────────────           ──────────────────────
// 鐢ㄦ埛鐧诲綍鎴愬姛             // 用户登录成功
// 鏁版嵁搴撹繛鎺ュけ璐�           // 数据库连接失败
// 璁㈠崟鍒涘缓鎴愬姛              // 订单创建成功
```

HTML 标签损坏也能检测到：

```html
<!-- 乱码 -->
<p>鐢ㄦ埛涓�績</p>
?/div>

<!-- 修复后 -->
<p>用户中心</p>
</div>
```

### 快速开始

```bash
# 扫描项目
python check_mojibake.py --root ./src

# 自动修复明显的 UTF-8/GBK 混淆（会创建 .bak 备份）
python check_mojibake.py --root ./src --fix-gbk

# JSON 输出，方便 CI 集成
python check_mojibake.py --root ./src --json
```

### CI 集成（GitHub Actions）

创建 `.github/workflows/encoding-check.yml`：

```yaml
name: Encoding Guard
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.x"
      - name: Check for encoding corruption
        run: python check_mojibake.py --root . --fail-on-find
```

含有乱码的 PR 会自动失败。

### AI 助手集成

#### Claude Code（每次编辑后自动检查）

1. 复制 skill 到项目：

```bash
cp -r claude/text-encoding-guard/ .claude/skills/text-encoding-guard/
```

2. 在 `.claude/settings.json` 添加 hook：

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

之后 Claude 每次编辑文件都会自动扫描乱码。

#### OpenAI Codex

```bash
cp codex/text-encoding-guard/SKILL.md .codex/SKILL.md
cp codex/text-encoding-guard/agents/openai.yaml .codex/agents/openai.yaml
```

### 工作原理

| 检测信号 | 权重 | 示例 |
|----------|------|------|
| Unicode 替换字符 `�` | +12 | 解码失败 |
| 损坏的 HTML 闭合标签 (`?/div>`) | +10 | 尖括号损坏 |
| 已知乱码字符 | +2/个 | 鐢ㄦ埛, 鏁版嵁, 绛� |

使用 `--fix-gbk` 时，工具尝试 GB18030 → UTF-8 重新编码，仅在分数显著下降时才应用修复。

### CLI 参数

```
--root PATH        要扫描的根目录（必填）
--json             JSON 格式输出
--fail-on-find     发现可疑文件时返回退出码 2（用于 CI）
--fix-gbk          尝试自动 GBK→UTF-8 修复
--ext .sql         添加额外的文件扩展名
```

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

### Quick Start

```bash
# Scan a project
python check_mojibake.py --root ./src

# Auto-fix clear UTF-8/GBK corruption (creates .bak files)
python check_mojibake.py --root ./src --fix-gbk

# JSON output for CI integration
python check_mojibake.py --root ./src --json
```

### CI Integration (GitHub Actions)

Create `.github/workflows/encoding-check.yml`:

```yaml
name: Encoding Guard
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.x"
      - name: Check for encoding corruption
        run: python check_mojibake.py --root . --fail-on-find
```

PRs with mojibake will fail automatically.

### AI Agent Integration

#### Claude Code (auto-run on every edit)

1. Copy the skill into your project:

```bash
cp -r claude/text-encoding-guard/ .claude/skills/text-encoding-guard/
```

2. Add a hook to `.claude/settings.json`:

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

Claude will automatically scan for mojibake after every file edit.

#### OpenAI Codex

```bash
cp codex/text-encoding-guard/SKILL.md .codex/SKILL.md
cp codex/text-encoding-guard/agents/openai.yaml .codex/agents/openai.yaml
```

### How It Works

| Signal | Weight | Example |
|--------|--------|---------|
| Unicode replacement char `�` | +12 | Decoding failure |
| Broken HTML end tags (`?/div>`) | +10 | Angle bracket corruption |
| Known mojibake tokens | +2/char | 鐢ㄦ埛, 鏁版嵁, 绛� |

With `--fix-gbk`, the tool attempts recovery by re-encoding as GB18030 → UTF-8, only applying the fix if the score drops significantly.

### CLI Reference

```
--root PATH        Root directory to scan (required)
--json             Output results as JSON
--fail-on-find     Exit code 2 if suspicious files found (for CI)
--fix-gbk          Attempt automatic GBK→UTF-8 recovery
--ext .sql         Add extra file extensions to scan
```

### Project Layout

```
check_mojibake.py          # Core scanner (zero dependencies, Python 3 stdlib only)
claude/                    # Claude Code skill package
codex/                     # OpenAI Codex skill package
```

---

## License

MIT
