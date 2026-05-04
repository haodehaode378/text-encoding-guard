#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
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
    ".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", "target", ".idea", ".vscode", ".claude"
}

MOJIBAKE_TOKENS = [
    # Ancient-text code (GBK misreading UTF-8)
    "\u9358", "\u9359", "\u9428", "\u93b4", "\u5bee", "\u7f01", "\u93c2", "\u93c3", "\u934a",
    "\u95c3", "\u93ba", "\u59af", "\u7481", "\u7487", "\uff1b", "\u9286", "\u951f", "\u9225",
    # Kun-Kao code (UTF-8 -> GBK -> UTF-8 double conversion)
    "\u9518", "\u65a4", "\u62f7",
]

# Kun-Jin-Kao pattern: classic triple-character mojibake
KUN_KAO_RE = re.compile(r"\u951f.{0,2}\u65a4.{0,2}\u62f7")

# Tang-Tun pattern: VC debug uninitialized memory (3+ repeated)
TANG_TUN_RE = re.compile(r"[\u70eb\u5c6f]{3,}")

# Question-code: trailing odd number of ? after CJK text
QUESTION_CODE_RE = re.compile(r"[\u4e00-\u9fff].*\?{1,3}(?!\?)")

# Symbol/Pinyin code: ISO8859-1 misread produces Latin extended chars
# Use \u escapes to avoid the tool flagging its own source code
_ISO_LOWER = "\u00e7\u00e6\u0153\u00e5\u00e0\u00e1\u00e2\u00e3\u00e4\u00e8\u00e9\u00ea\u00eb\u00ec\u00ed\u00ee\u00ef\u00f2\u00f3\u00f4\u00f5\u00f6\u00f9\u00fa\u00fb\u00fc\u00fd\u00ff\u00f1"
_ISO_UPPER = "\u00c7\u00c6\u0152\u00c5\u00c0\u00c1\u00c2\u00c3\u00c4\u00c8\u00c9\u00ca\u00cb\u00cc\u00cd\u00ce\u00cf\u00d2\u00d3\u00d4\u00d5\u00d6\u00d9\u00da\u00db\u00dc\u00dd\u0178\u00d1"
ISO_DIACRITICS = set(_ISO_LOWER + _ISO_UPPER)

BAD_TAG_RE = re.compile(r"\?/([A-Za-z][\w-]*)>")

# --- ANSI color support ---
_NO_COLOR = os.environ.get("NO_COLOR") is not None or not sys.stdout.isatty()


def _c(code: str) -> str:
    return "" if _NO_COLOR else f"\033[{code}m"


C_RED = _c("31")
C_GREEN = _c("32")
C_YELLOW = _c("33")
C_BOLD = _c("1")
C_RESET = _c("0")


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

    # Box-char code: replacement characters
    repl = text.count("\ufffd")
    if repl:
        score += repl * 12
        reasons.append(f"replacement-char={repl}")

    # Broken HTML end tags
    bad_tags = len(BAD_TAG_RE.findall(text))
    if bad_tags:
        score += bad_tags * 10
        reasons.append(f"broken-end-tag={bad_tags}")

    # Ancient-text + Kun-Kao: known mojibake tokens
    token_hits = 0
    for tok in MOJIBAKE_TOKENS:
        token_hits += text.count(tok)
    if token_hits:
        score += token_hits * 2
        reasons.append(f"mojibake-token-hits={token_hits}")

    # Kun-Jin-Kao pattern (extra weight for the classic triple)
    kun_kao = len(KUN_KAO_RE.findall(text))
    if kun_kao:
        score += kun_kao * 8
        reasons.append(f"kun-kao-pattern={kun_kao}")

    # Tang-Tun (VC debug patterns)
    tang_tun = len(TANG_TUN_RE.findall(text))
    if tang_tun:
        score += tang_tun * 6
        reasons.append(f"tang-tun-pattern={tang_tun}")

    # Question-code (odd trailing ?)
    question_code = len(QUESTION_CODE_RE.findall(text))
    if question_code:
        score += question_code * 8
        reasons.append(f"question-code={question_code}")

    # Symbol/Pinyin code (ISO8859-1 diacritics)
    iso_count = sum(1 for c in text if c in ISO_DIACRITICS)
    if iso_count >= 3:
        score += iso_count * 2
        reasons.append(f"iso-mojibake={iso_count}")

    return score, reasons


def _line_has_mojibake(ln: str) -> bool:
    if "\ufffd" in ln:
        return True
    if BAD_TAG_RE.search(ln):
        return True
    if any(tok in ln for tok in MOJIBAKE_TOKENS):
        return True
    if KUN_KAO_RE.search(ln):
        return True
    if TANG_TUN_RE.search(ln):
        return True
    if QUESTION_CODE_RE.search(ln):
        return True
    if sum(1 for c in ln if c in ISO_DIACRITICS) >= 3:
        return True
    return False


def preview_lines(text: str) -> list[str]:
    lines = text.splitlines()
    out: list[str] = []
    for i, ln in enumerate(lines, start=1):
        if _line_has_mojibake(ln):
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
            safe_print(f"{C_GREEN}{C_BOLD}[fixed]{C_RESET}")
            for p in fixed:
                safe_print(f"  {C_GREEN}+ {p}{C_RESET}")
        if decode_errors:
            safe_print(f"{C_YELLOW}[decode-errors]{C_RESET}")
            for p in decode_errors:
                safe_print(f"  {C_YELLOW}! {p}{C_RESET}")
        if findings:
            safe_print(f"{C_RED}{C_BOLD}[suspicious] {len(findings)} files{C_RESET}")
            for f in findings[:50]:
                color = C_RED if f.score >= 20 else C_YELLOW
                safe_print(f"  {color}- {f.path} (score={f.score}; {', '.join(f.reasons)}){C_RESET}")
                for line in f.preview:
                    safe_print(f"      {line}")
        else:
            safe_print(f"{C_GREEN}{C_BOLD}[ok] no suspicious mojibake patterns found{C_RESET}")

    if args.fail_on_find and findings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
