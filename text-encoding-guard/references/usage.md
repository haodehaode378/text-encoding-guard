# Encoding Guard Notes

## Recommended command

```bash
python C:/Users/36366/.codex/skills/text-encoding-guard/scripts/check_mojibake.py --root <project_root>
```

## Typical symptoms
- Chinese text appears as mojibake after UTF-8 and GBK/GB18030 mixups.
- Unicode replacement characters appear in source files.
- Template tags become malformed, for example a closing tag starts with a question mark.

## Fix strategy
1. Prefer manual correction for small files.
2. Use `--fix-gbk` only when corruption pattern is consistent.
3. Keep `.bak.mojibake` backups until build/tests pass.
