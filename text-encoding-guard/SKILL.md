---
name: text-encoding-guard
description: Use this skill whenever Chinese text may become garbled during coding, refactors, README edits, Vue/HTML template edits, or shell-based file rewrites. It provides a mandatory post-edit encoding scan and a conservative UTF-8/GBK recovery flow.
---

# Text Encoding Guard

## Overview
This skill prevents and repairs text encoding corruption, especially Chinese mojibake caused by UTF-8 and GBK/GB18030 mixups.
After any code edit that may affect Chinese text, run the checker before finishing the response.

## Mandatory Workflow
1. After file edits, run:
```bash
python C:/Users/36366/.codex/skills/text-encoding-guard/scripts/check_mojibake.py --root <project_root>
```
2. If suspicious files are reported:
- Open and inspect those files immediately.
- Fix text manually, or run conservative recovery mode on specific files.
3. Re-run checker until it prints no suspicious files, or until every remaining finding is confirmed as an intentional detector example.
4. Only then send final response.

## Conservative Recovery
For common UTF-8 bytes interpreted as GBK/GB18030 corruption:
```bash
python C:/Users/36366/.codex/skills/text-encoding-guard/scripts/check_mojibake.py --root <project_root> --fix-gbk
```

Safety behavior:
- Creates `.bak.mojibake` backup before overwrite.
- Applies only when score improves significantly.
- Skips files when confidence is low.

## When To Trigger This Skill
- User says Chinese text is corrupted, garbled, or affected by mojibake.
- Editing README/docs/UI copy with Chinese text.
- Large scripted rewrites (`Set-Content`, mass replacements).
- Vue/HTML templates where broken tags and quotes often appear with corruption.

## Output Contract
- Report exact suspicious file paths.
- Report whether auto-fix was applied or skipped.
- If skipped, provide manual next file to fix first.
