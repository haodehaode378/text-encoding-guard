---
name: text-encoding-guard
description: Use this skill whenever Chinese text may become garbled during coding, refactors, README edits, Vue/HTML template edits, or shell-based file rewrites. It provides a mandatory post-edit encoding scan and a conservative UTF-8/GBK recovery flow.
---

# Text Encoding Guard

## Purpose
Prevent and repair Chinese text encoding corruption after edits.

## Required Behavior
- After editing files that may contain Chinese text, run the mojibake checker.
- Inspect every suspicious path before applying recovery.
- Prefer manual correction for small text changes.
- Use conservative recovery only when UTF-8/GBK corruption is clear.
- Re-run the checker after fixes and report the result.

## Commands

```bash
# If installed via pip:
check-mojibake --root <project_root>

# If running from repo checkout:
python scripts/check_mojibake.py --root <project_root>

# Auto-fix mode:
check-mojibake --root <project_root> --fix-gbk
```
