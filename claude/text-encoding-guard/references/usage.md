# Claude Code Integration

## Setup

1. Copy this skill folder into your project:

```bash
cp -r claude/text-encoding-guard/ .claude/skills/text-encoding-guard/
```

2. Create or update `.claude/settings.json` to auto-run the check after every edit:

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

Claude will now automatically scan for encoding corruption after every `Edit` or `Write` call.

## Manual Usage

```bash
# Scan only
python scripts/check_mojibake.py --root <project_root>

# Auto-fix (creates .bak files first)
python scripts/check_mojibake.py --root <project_root> --fix-gbk
```

## How It Works

When the hook detects suspicious files, the output appears in the tool result. Claude will inspect reported paths and fix issues manually or with `--fix-gbk` for clear UTF-8/GBK corruption.
