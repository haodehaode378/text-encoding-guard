# Encoding Guard Notes

## Install

Copy this folder to:

```text
$CODEX_HOME/skills/text-encoding-guard
```

## Use

Run the checker from the skill directory, or replace `scripts/check_mojibake.py` with an absolute path.

```bash
python scripts/check_mojibake.py --root <project_root>
```

Use `--fix-gbk` only after inspecting findings.
