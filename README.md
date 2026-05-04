# AI Text Encoding Guard

[中文](#中文) | [English](#english)

> AI 编码助手把中文搞成乱码了？自动检测，一键修复。
>
> AI agents corrupting your Chinese text? Detect it, fix it, ship it.

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

### 三大检测维度

| 检测信号 | 权重 | 说明 |
|----------|------|------|
| Unicode 替换字符 `�` | +12/个 | 解码彻底失败，铁定乱码 |
| 损坏的 HTML 闭合标签 (`?/div>`) | +10/个 | 尖括号 `<` 被吞，页面结构崩塌 |
| 已知乱码字符 token | +2/个 | 鐢ㄦ埛、鏁版嵁、绛� 等 18 个典型乱码码点 |

文件总分 > 0 即标记为可疑。分数越高，乱码越严重。

### 修复机制

`--fix-gbk` 不是盲目替换。它遵循**三重安全门**：

```
1. 尝试 GB18030 编码 → UTF-8 解码（逆向还原）
2. 修复后分数必须 ≤ 原分数的 1/3
3. 绝对改善值必须 ≥ 8 分
   ↓
全部通过 → 写入修复 + 创建 .bak.mojibake 备份
任一失败 → 跳过，标记为需人工检查
```

### 快速开始

```bash
# 1. 扫描项目
python check_mojibake.py --root ./src

# 2. 看到可疑文件？自动修复
python check_mojibake.py --root ./src --fix-gbk

# 3. JSON 输出，方便程序处理
python check_mojibake.py --root ./src --json

# 4. CI 卡点：有乱码就失败
python check_mojibake.py --root . --fail-on-find
```

### CI 集成

创建 `.github/workflows/encoding-check.yml`，PR 有乱码自动拦截：

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

### AI 助手集成

#### Claude Code（推荐，自动触发）

两步搞定，之后每次编辑自动扫描：

**Step 1** — 复制 skill：
```bash
cp -r claude/text-encoding-guard/ .claude/skills/text-encoding-guard/
```

**Step 2** — 在 `.claude/settings.json` 添加 hook：
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

效果：Claude 每次调用 `Edit` 或 `Write` 后，自动运行乱码检查。发现可疑文件会在工具输出中提示，Claude 会自动处理。

#### OpenAI Codex

```bash
cp codex/text-encoding-guard/SKILL.md .codex/SKILL.md
cp codex/text-encoding-guard/agents/openai.yaml .codex/agents/openai.yaml
```

### CLI 完整参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--root PATH` | 要扫描的根目录（必填） | `--root ./src` |
| `--json` | JSON 格式输出 | `--json` |
| `--fail-on-find` | 发现可疑文件时退出码 2（CI 用） | `--fail-on-find` |
| `--fix-gbk` | 尝试自动 GBK→UTF-8 修复 | `--fix-gbk` |
| `--ext` | 添加额外扩展名（可多次） | `--ext .sql --ext .cfg` |

### 扫描范围

**默认扫描 20 种扩展名：**
`.py` `.md` `.txt` `.json` `.yaml` `.yml` `.toml` `.ini` `.js` `.ts` `.tsx` `.jsx` `.vue` `.html` `.css` `.scss` `.sh` `.bat` `.ps1` `.xml`

**自动跳过：**
`.git` `node_modules` `dist` `build` `__pycache__` `.venv` `venv` `target` `.idea` `.vscode`

### 为什么选这个

| 对比项 | 本工具 | 手动检查 | file/uchardet |
|--------|--------|----------|---------------|
| 精确检测乱码 | ✅ 评分制 | ❌ 肉眼看 | ❌ 只检测编码，不检测乱码 |
| 自动修复 | ✅ 保守策略+备份 | ❌ | ❌ |
| CI 集成 | ✅ 退出码 2 | ❌ | ❌ |
| AI 助手自动触发 | ✅ hooks/skill | ❌ | ❌ |
| 零依赖 | ✅ 纯 stdlib | N/A | 需要安装 |
| 中文特化 | ✅ 针对 UTF-8/GBK | ❌ | ❌ |

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

# CI gate: fail on findings
python check_mojibake.py --root . --fail-on-find
```

### CI Integration

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

### AI Agent Integration

#### Claude Code (auto-run on every edit)

1. Copy the skill:
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

#### OpenAI Codex

```bash
cp codex/text-encoding-guard/SKILL.md .codex/SKILL.md
cp codex/text-encoding-guard/agents/openai.yaml .codex/agents/openai.yaml
```

### How It Works

| Signal | Weight | Description |
|--------|--------|-------------|
| Unicode replacement char `�` | +12 | Decoding failure |
| Broken HTML end tags (`?/div>`) | +10 | Angle bracket corruption |
| Known mojibake tokens | +2/char | 18 specific codepoints from UTF-8/GBK misread |

### CLI Reference

| Flag | Description | Example |
|------|-------------|---------|
| `--root PATH` | Root directory to scan (required) | `--root ./src` |
| `--json` | JSON output | `--json` |
| `--fail-on-find` | Exit code 2 on findings (for CI) | `--fail-on-find` |
| `--fix-gbk` | Attempt GBK→UTF-8 auto-recovery | `--fix-gbk` |
| `--ext` | Extra extensions (repeatable) | `--ext .sql --ext .cfg` |

---

## License

MIT
