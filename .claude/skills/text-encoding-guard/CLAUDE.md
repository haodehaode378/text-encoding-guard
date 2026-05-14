# Text Encoding Guard

Use this instruction whenever edits may touch Chinese text, markdown documentation, UI copy, Vue/HTML templates, JSON/YAML content, or shell-based rewrites.

After edits, run:

```bash
python scripts/check_mojibake.py --root <project_root>
```

If suspicious files are found:

1. Open and inspect the reported paths.
2. Fix small issues manually.
3. Use `--fix-gbk` only for clear UTF-8 bytes interpreted as GBK/GB18030.
4. Re-run the checker until findings are resolved or intentionally documented.

In the final response, report suspicious paths, whether auto-fix was used, and any file still requiring manual review.
