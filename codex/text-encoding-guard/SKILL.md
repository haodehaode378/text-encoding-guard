---
name: text-encoding-guard
description: Use this skill whenever Chinese text may become garbled during coding, refactors, README edits, Vue/HTML template edits, or shell-based file rewrites. It provides a mandatory post-edit encoding scan and a conservative UTF-8/GBK recovery flow.
---

# Text Encoding Guard

## Purpose
Prevent and repair Chinese text encoding corruption after edits.

## Mandatory Workflow
1. After edits, run:
```bash
python scripts/check_mojibake.py --root <project_root>
```
2. If suspicious files are reported, open and inspect them.
3. Fix manually first when the affected text is small.
4. Use conservative recovery only for files that clearly match UTF-8 bytes misread as GBK:
```bash
python scripts/check_mojibake.py --root <project_root> --fix-gbk
```
5. Re-run the checker until the remaining findings are either fixed or explicitly confirmed as intentional detector examples.

## Reporting Contract
- Report exact suspicious paths.
- Report whether auto-fix was applied or skipped.
- If skipped, name the next file that needs manual review.
