# AI Text Encoding Guard

<p align="center">
  <img src="docs/images/hero-banner.png" alt="AI Text Encoding Guard — Detect & Fix Chinese Mojibake" width="100%">
</p>

<p align="center">
  <strong>AI 编码助手把中文搞成乱码了？自动检测，一键修复。</strong><br/>
  <em>AI agents corrupting your Chinese text? Detect it, fix it, ship it.</em>
</p>

<p align="center">
  <a href="https://github.com/haodehaode378/text-encoding-guard/actions/workflows/ci.yml"><img src="https://github.com/haodehaode378/text-encoding-guard/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/ai-text-encoding-guard/"><img src="https://img.shields.io/pypi/v/ai-text-encoding-guard" alt="PyPI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://pypi.org/project/ai-text-encoding-guard/"><img src="https://img.shields.io/pypi/pyversions/ai-text-encoding-guard" alt="Python"></a>
  <img src="https://img.shields.io/badge/dependencies-zero-brightgreen" alt="Zero Dependencies">
</p>

<p align="center">
  <a href="#中文">中文</a> &nbsp;|&nbsp; <a href="#english">English</a>
</p>

---

## The Problem

<p align="center">
  <img src="docs/images/workflow.png" alt="Workflow: Detect → Analyze → Fix → Protect" width="100%">
</p>

When AI coding assistants (Claude, Cursor, Copilot, Codex) edit files with Chinese text, encoding corruption silently creeps in. UTF-8 bytes get misread as GBK — and you don't notice until users see garbage.

```
 Before (corrupted)              After (recovered)
 ─────────────────────           ─────────────────────
 // 鐢ㄦ埛鐧诲綍鎴愬姛             // 用户登录成功
 // 鏁版嵁搴撹繛鎺ュけ璐�           // 数据库连接失败
 // 璁㈠崟鍒涘缓鎴愬姛              // 订单创建成功
```

Broken HTML tags are also caught:

```html
<!-- AI 编辑后 → 标签损坏 -->
<p>鐢ㄦ埛涓�績</p>
?/div>              <!-- ← </div> 的 < 被吃掉了 -->

<!-- 修复后 → 完整恢复 -->
<p>用户中心</p>
</div>
```

### Who gets hit?

<table>
  <tr>
    <th>场景 / Scenario</th>
    <th>中招概率 / Risk</th>
    <th>后果 / Impact</th>
  </tr>
  <tr>
    <td>Claude Code 编辑含中文的 Vue/React 组件</td>
    <td><strong><span style="color:#f85149">极高</span></strong></td>
    <td>UI 文案全变乱码，用户直接看到</td>
  </tr>
  <tr>
    <td>Cursor 批量重构中文注释</td>
    <td><strong><span style="color:#d29922">高</span></strong></td>
    <td>代码可读性归零，新人看不懂</td>
  </tr>
  <tr>
    <td>Copilot 生成中文文档</td>
    <td><strong><span style="color:#d29922">中</span></strong></td>
    <td>README / CHANGELOG 变天书</td>
  </tr>
  <tr>
    <td>CI/CD 自动化脚本处理中文文件</td>
    <td><strong><span style="color:#d29922">中</span></strong></td>
    <td>静默损坏，上线后才发现</td>
  </tr>
</table>

---

## Installation

```bash
pip install ai-text-encoding-guard
```

<details>
<summary>从源码安装 / Install from source</summary>

```bash
git clone https://github.com/haodehaode378/text-encoding-guard.git
cd text-encoding-guard
pip install -e ".[test]"
```

</details>

---

## Quick Start

```bash
# 扫描项目 / Scan a project
check-mojibake --root ./src

# 自动修复（创建 .bak 备份）/ Auto-fix (creates .bak backup)
check-mojibake --root ./src --fix-gbk

# JSON 输出 / JSON output
check-mojibake --root ./src --json

# CI 卡点：有乱码就失败 / CI gate: fail on findings
check-mojibake --root . --fail-on-find
```

<details>
<summary>不安装直接用 / Run without installation</summary>

```bash
python scripts/check_mojibake.py --root ./src
# 或 / or
python -m check_mojibake --root ./src
```

</details>

---

## How It Works

### 七大检测维度 / 7 Detection Types

| 乱码类型 | 产生原因 | 检测信号 | 权重 |
|:---------|:---------|:---------|:----:|
| **口字码** Box chars | UTF-8 读 GBK | Unicode 替换字符 `�` | `+12` |
| **破标签** Broken tags | AI 编辑吞尖括号 | 损坏的 HTML 闭合标签 | `+10` |
| **古文码** Ancient text | GBK 读 UTF-8 | 18 个已知乱码码点 | `+2` |
| **锟拷码** Kun-Kao | UTF-8→GBK→UTF-8 双重转换 | `锟斤拷` 模式匹配 | `+8` |
| **烫屯码** Tang-Tun | VC 调试未初始化内存 | `烫烫烫` / `屯屯屯` 重复 | `+6` |
| **问句码** Question code | 双重转换 | 中文后连续 `??` | `+8` |
| **符号码** Symbol code | ISO8859-1 读 UTF-8 | 拉丁扩展字符密集出现 | `+2` |

> 文件总分 > 0 即标记为可疑。分数越高，乱码越严重。
>
> Any file with score > 0 is flagged. Higher score = worse corruption.

### 修复机制 / Fix Mechanism

`--fix-gbk` 不是盲目替换，遵循 **三重安全门**：

```
 ① 尝试 GB18030 编码 → UTF-8 解码（逆向还原）
    也尝试反方向：UTF-8 编码 → GB18030 解码
         ↓
 ② 修复后分数必须 ≤ 原分数的 1/3
         ↓
 ③ 绝对改善值必须 ≥ 8 分
         ↓
   ┌─ 全部通过 → 写入修复 + 创建 .bak.mojibake 备份
   └─ 任一失败 → 跳过，标记为需人工检查
```

---

## Integration

### GitHub Actions — 一行搞定 / One Line

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

PR 有乱码自动拦截。PRs with mojibake get blocked automatically.

<details>
<summary>可选参数 / Optional parameters</summary>

```yaml
- uses: haodehaode378/text-encoding-guard@v1
  with:
    root: './src'              # 扫描目录（默认 .）
    fix-gbk: 'true'            # 自动修复（默认 false）
    ext: '.sql,.cfg'           # 额外扩展名
```

</details>

### Claude Code — 自动触发 / Auto-run on Every Edit

**Step 1** — 添加 PostToolUse hook：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "command": "python scripts/check_mojibake.py --root .",
        "description": "Check for Chinese mojibake after file edits"
      }
    ]
  }
}
```

**Step 2**（可选）— 安装 skill：

```bash
cp -r .claude/skills/text-encoding-guard/ /path/to/your/project/.claude/skills/
```

---

## CLI Reference

| 参数 / Flag | 说明 / Description | 示例 / Example |
|:------------|:-------------------|:---------------|
| `--root PATH` | 要扫描的根目录（必填） | `--root ./src` |
| `--json` | JSON 格式输出 | `--json` |
| `--fail-on-find` | 发现可疑文件时退出码 2 | `--fail-on-find` |
| `--fix-gbk` | 尝试自动 GBK→UTF-8 修复 | `--fix-gbk` |
| `--ext` | 添加额外扩展名（可多次） | `--ext .sql --ext .cfg` |
| `--verbose` | 显示详细诊断信息 | `-v` |
| `--quiet` | 静默模式 | `-q` |

### 扫描范围 / Scan Scope

**默认 20 种扩展名：**
`.py` `.md` `.txt` `.json` `.yaml` `.yml` `.toml` `.ini` `.js` `.ts` `.tsx` `.jsx` `.vue` `.html` `.css` `.scss` `.sh` `.bat` `.ps1` `.xml`

**自动跳过：**
`.git` `node_modules` `dist` `build` `__pycache__` `.venv` `venv` `target` `.idea` `.vscode` `.claude`

---

## Why This Tool?

| 对比项 | 本工具 | 手动检查 | file/uchardet |
|:-------|:------:|:--------:|:-------------:|
| 精确检测乱码 | :white_check_mark: 评分制 | :x: 肉眼看 | :x: 只检测编码 |
| 自动修复 | :white_check_mark: 保守+备份 | :x: | :x: |
| CI 集成 | :white_check_mark: 退出码 2 | :x: | :x: |
| AI 助手触发 | :white_check_mark: hooks | :x: | :x: |
| 零依赖 | :white_check_mark: 纯 stdlib | N/A | 需要安装 |
| 双向修复 | :white_check_mark: UTF-8↔GBK | :x: | :x: |

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
