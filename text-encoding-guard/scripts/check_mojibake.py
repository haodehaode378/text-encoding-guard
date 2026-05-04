#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_EXTS = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".js", ".ts", ".tsx", ".jsx", ".vue", ".html", ".css", ".scss",
    ".sh", ".bat", ".ps1", ".xml",
}
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", "target", ".idea", ".vscode"
}

MOJIBAKE_TOKENS = [
    "\u9358", "\u9359", "\u9428", "\u93b4", "\u5bee", "\u7f01", "\u93c2", "\u93c3", "\u934a",
    "\u95c3", "\u93ba", "\u59af", "\u7481", "\u7487", "\uff1b", "\u9286", "\u951f", "\u9225",
]

BAD_TAG_RE = re.compile(r"\?/([A-Za-z][\w-]*)>")


@dataclass
class Finding:
    path: str
    score: int
    reasons: list[str]
    preview: list[str]


def safe_print(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        safe = message.encode(enc, errors="replace").decode(enc, errors="replace")
        print(safe)


def iter_files(root: Path, exts: set[str]) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in exts:
            continue
        yield p


def score_text(text: str) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0

    repl = text.count("\ufffd")
    if repl:
        score += repl * 12
        reasons.append(f"replacement-char={repl}")

    bad_tags = len(BAD_TAG_RE.findall(text))
    if bad_tags:
        score += bad_tags * 10
        reasons.append(f"broken-end-tag={bad_tags}")

    token_hits = 0
    for tok in MOJIBAKE_TOKENS:
        token_hits += text.count(tok)
    if token_hits:
        score += token_hits * 2
        reasons.append(f"mojibake-token-hits={token_hits}")

    return score, reasons


def preview_lines(text: str) -> list[str]:
    lines = text.splitlines()
    out: list[str] = []
    for i, ln in enumerate(lines, start=1):
        if "\ufffd" in ln or BAD_TAG_RE.search(ln) or any(tok in ln for tok in MOJIBAKE_TOKENS):
            out.append(f"L{i}: {ln[:180]}")
        if len(out) >= 4:
            break
    return out


def try_gbk_recover(text: str) -> str | None:
    try:
        return text.encode("gb18030").decode("utf-8")
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect and optionally repair mojibake in text files.")
    ap.add_argument("--root", required=True, help="Root folder to scan")
    ap.add_argument("--json", action="store_true", help="Output JSON")
    ap.add_argument("--fail-on-find", action="store_true", help="Exit non-zero when suspicious files exist")
    ap.add_argument("--fix-gbk", action="store_true", help="Try conservative GBK->UTF-8 recovery")
    ap.add_argument("--ext", action="append", default=[], help="Additional extension, e.g. --ext .sql")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    exts = set(DEFAULT_EXTS)
    for e in args.ext:
        exts.add(e if e.startswith(".") else f".{e}")

    findings: list[Finding] = []
    fixed: list[str] = []
    decode_errors: list[str] = []

    for fp in iter_files(root, exts):
        raw = fp.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            decode_errors.append(str(fp))
            continue

        old_score, old_reasons = score_text(text)
        if old_score <= 0:
            continue

        if args.fix_gbk:
            recovered = try_gbk_recover(text)
            if recovered is not None:
                new_score, _ = score_text(recovered)
                if new_score <= max(0, old_score // 3) and old_score - new_score >= 8:
                    bak = fp.with_suffix(fp.suffix + ".bak.mojibake")
                    if not bak.exists():
                        bak.write_bytes(raw)
                    fp.write_text(recovered, encoding="utf-8", newline="")
                    fixed.append(str(fp))
                    text = recovered
                    old_score, old_reasons = new_score, ["auto-fixed-gbk"]

        findings.append(Finding(str(fp), old_score, old_reasons, preview_lines(text)))

    findings.sort(key=lambda x: x.score, reverse=True)

    if args.json:
        safe_print(json.dumps({
            "root": str(root),
            "findings": [f.__dict__ for f in findings],
            "fixed": fixed,
            "decode_errors": decode_errors,
        }, ensure_ascii=False, indent=2))
    else:
        safe_print(f"[encoding-guard] root={root}")
        if fixed:
            safe_print("[fixed]")
            for p in fixed:
                safe_print(f"- {p}")
        if decode_errors:
            safe_print("[decode-errors]")
            for p in decode_errors:
                safe_print(f"- {p}")
        if findings:
            safe_print(f"[suspicious] {len(findings)} files")
            for f in findings[:50]:
                safe_print(f"- {f.path} (score={f.score}; {', '.join(f.reasons)})")
                for line in f.preview:
                    safe_print(f"    {line}")
        else:
            safe_print("[ok] no suspicious mojibake patterns found")

    if args.fail_on_find and findings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
