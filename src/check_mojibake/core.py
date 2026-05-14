#!/usr/bin/env python3
"""Detect and optionally repair mojibake (encoding corruption) in text files.

Single-source-of-truth module for the text-encoding-guard tool.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_EXTS: set[str] = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".js", ".ts", ".tsx", ".jsx", ".vue", ".html", ".css", ".scss",
    ".sh", ".bat", ".ps1", ".xml",
}

SKIP_DIRS: set[str] = {
    ".git", "node_modules", "dist", "build", "__pycache__",
    ".venv", "venv", "target", ".idea", ".vscode", ".claude",
}

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

# Known mojibake codepoints produced when GBK misreads UTF-8 bytes.
# Use \u escapes to avoid the tool flagging its own source code.
MOJIBAKE_TOKENS: list[str] = [
    # Ancient-text code (GBK misreading UTF-8)
    "\u9358", "\u9359", "\u9428", "\u93b4", "\u5bee", "\u7f01",
    "\u93c2", "\u93c3", "\u934a", "\u95c3", "\u93ba", "\u59af",
    "\u7481", "\u7487", "\uff1b", "\u9286", "\u951f", "\u9225",
    # Kun-Kao triple (UTF-8 -> GBK -> UTF-8)
    "\u9518", "\u65a4", "\u62f7",
]

# Kun-Jin-Kao pattern: classic triple-character mojibake
KUN_KAO_RE = re.compile(r"\u951f.{0,2}\u65a4.{0,2}\u62f7")

# Tang-Tun pattern: VC debug uninitialized memory (3+ repeated)
TANG_TUN_RE = re.compile(r"[\u70eb\u5c6f]{3,}")

# Conservative question-code: only flag CJK + 2+ consecutive ?
# A single trailing "?" after CJK is normal punctuation and must NOT trigger.
# Use \u escapes to avoid self-detection.
QUESTION_CODE_RE = re.compile(r"[\u4e00-\u9fff]\?{2,}")

BAD_TAG_RE = re.compile(r"\?/([A-Za-z][\w-]*)>")

# ISO-8859-1 diacritics that appear when UTF-8/GBK bytes are misread.
# Use \u escapes to avoid the tool flagging its own source code.
_ISO_LOWER = (
    "\u00e7\u00e6\u0153\u00e5\u00e0\u00e1\u00e2\u00e3\u00e4"
    "\u00e8\u00e9\u00ea\u00eb\u00ec\u00ed\u00ee\u00ef\u00f2"
    "\u00f3\u00f4\u00f5\u00f6\u00f9\u00fa\u00fb\u00fc\u00fd"
    "\u00ff\u00f1"
)
_ISO_UPPER = (
    "\u00c7\u00c6\u0152\u00c5\u00c0\u00c1\u00c2\u00c3\u00c4"
    "\u00c8\u00c9\u00ca\u00cb\u00cc\u00cd\u00ce\u00cf\u00d2"
    "\u00d3\u00d4\u00d5\u00d6\u00d9\u00da\u00db\u00dc\u00dd"
    "\u0178\u00d1"
)
ISO_DIACRITICS: set[str] = set(_ISO_LOWER + _ISO_UPPER)

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------

_NO_COLOR = os.environ.get("NO_COLOR") is not None or not sys.stdout.isatty()


def _c(code: str) -> str:
    return "" if _NO_COLOR else f"\033[{code}m"


C_RED = _c("31")
C_GREEN = _c("32")
C_YELLOW = _c("33")
C_BOLD = _c("1")
C_RESET = _c("0")

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    path: str
    score: int
    reasons: list[str]
    preview: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def safe_print(message: str) -> None:
    """Print with fallback for terminals that cannot encode every character."""
    try:
        print(message)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        safe = message.encode(enc, errors="replace").decode(enc, errors="replace")
        print(safe)


def iter_files(root: Path, exts: set[str]) -> Iterable[Path]:
    """Yield files under *root* matching *exts*, skipping SKIP_DIRS and symlinks."""
    for p in root.rglob("*"):
        if p.is_symlink():
            continue
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in exts:
            continue
        yield p


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_text(text: str) -> tuple[int, list[str]]:
    """Return *(score, reasons)* for *text*.  Score 0 = clean."""
    reasons: list[str] = []
    score = 0

    # Replacement characters (U+FFFD)
    repl = text.count("\ufffd")
    if repl:
        score += repl * 12
        reasons.append(f"replacement-char={repl}")

    # Broken HTML end tags
    bad_tags = len(BAD_TAG_RE.findall(text))
    if bad_tags:
        score += bad_tags * 10
        reasons.append(f"broken-end-tag={bad_tags}")

    # Ancient-text + Kun-Kao tokens
    token_hits = sum(text.count(t) for t in MOJIBAKE_TOKENS)
    if token_hits:
        score += token_hits * 2
        reasons.append(f"mojibake-token-hits={token_hits}")

    # Kun-Jin-Kao triple pattern
    kun_kao = len(KUN_KAO_RE.findall(text))
    if kun_kao:
        score += kun_kao * 8
        reasons.append(f"kun-kao-pattern={kun_kao}")

    # Tang-Tun (VC debug memory)
    tang_tun = len(TANG_TUN_RE.findall(text))
    if tang_tun:
        score += tang_tun * 6
        reasons.append(f"tang-tun-pattern={tang_tun}")

    # Question-code (2+ consecutive ? after CJK)
    question_code = len(QUESTION_CODE_RE.findall(text))
    if question_code:
        score += question_code * 8
        reasons.append(f"question-code={question_code}")

    # Symbol/Pinyin (ISO-8859-1 diacritics)
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


def preview_lines(text: str, max_chars: int = 180) -> list[str]:
    """Return up to 4 suspicious lines with line numbers."""
    lines = text.splitlines()
    out: list[str] = []
    for i, ln in enumerate(lines, start=1):
        if _line_has_mojibake(ln):
            truncated = ln[:max_chars]
            suffix = " ..." if len(ln) > max_chars else ""
            out.append(f"L{i}: {truncated}{suffix}")
        if len(out) >= 4:
            break
    return out


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------


def try_gbk_recover(text: str) -> str | None:
    """Try to reverse common UTF-8-as-GBK corruption.

    Direction 1 (most common): re-encode as gb18030, decode as utf-8.
    Direction 2 (fallback): try the reverse direction (GBK bytes misread as UTF-8).
    """
    # Direction 1: UTF-8 bytes misread as GBK/GB18030
    try:
        recovered = text.encode("gb18030").decode("utf-8")
        if recovered != text:
            return recovered
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    # Direction 2: GBK bytes misread as UTF-8
    try:
        raw = text.encode("utf-8")
        recovered = raw.decode("gb18030")
        if recovered != text:
            return recovered
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="check-mojibake",
        description="Detect and optionally repair mojibake in text files.",
    )
    ap.add_argument("--root", required=True, help="Root folder to scan")
    ap.add_argument("--json", action="store_true", dest="as_json", help="Output JSON")
    ap.add_argument(
        "--fail-on-find", action="store_true",
        help="Exit non-zero (2) when suspicious files exist",
    )
    ap.add_argument(
        "--fix-gbk", action="store_true",
        help="Try conservative GBK -> UTF-8 recovery",
    )
    ap.add_argument(
        "--ext", action="append", default=[],
        help="Additional extension, e.g. --ext .sql",
    )
    ap.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print extra diagnostic info",
    )
    ap.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress non-essential output",
    )
    args = ap.parse_args(argv)

    if args.verbose and args.quiet:
        ap.error("--verbose and --quiet are mutually exclusive")

    root = Path(args.root).resolve()
    exts = set(DEFAULT_EXTS)
    for e in args.ext:
        exts.add(e if e.startswith(".") else f".{e}")

    findings: list[Finding] = []
    fixed: list[str] = []
    decode_errors: list[str] = []
    skipped: list[str] = []
    scanned = 0

    for fp in iter_files(root, exts):
        scanned += 1
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
                else:
                    skipped.append(str(fp))
            else:
                skipped.append(str(fp))

        findings.append(Finding(str(fp), old_score, old_reasons, preview_lines(text)))

    findings.sort(key=lambda x: x.score, reverse=True)

    if args.as_json:
        safe_print(json.dumps({
            "root": str(root),
            "scanned": scanned,
            "findings": [f.__dict__ for f in findings],
            "fixed": fixed,
            "skipped": skipped,
            "decode_errors": decode_errors,
        }, ensure_ascii=False, indent=2))
    elif not args.quiet:
        safe_print(f"[encoding-guard] root={root}  scanned={scanned}")
        if fixed:
            safe_print(f"{C_GREEN}{C_BOLD}[fixed]{C_RESET}")
            for p in fixed:
                safe_print(f"  {C_GREEN}+ {p}{C_RESET}")
        if skipped and args.verbose:
            safe_print(f"{C_YELLOW}[skipped-fix]{C_RESET}")
            for p in skipped:
                safe_print(f"  {C_YELLOW}~ {p}{C_RESET}")
        if decode_errors:
            safe_print(f"{C_YELLOW}[decode-errors]{C_RESET}")
            for p in decode_errors:
                safe_print(f"  {C_YELLOW}! {p}{C_RESET}")
        if findings:
            safe_print(f"{C_RED}{C_BOLD}[suspicious] {len(findings)} files{C_RESET}")
            for f in findings[:50]:
                color = C_RED if f.score >= 20 else C_YELLOW
                safe_print(
                    f"  {color}- {f.path} "
                    f"(score={f.score}; {', '.join(f.reasons)}){C_RESET}"
                )
                for line in f.preview:
                    safe_print(f"      {line}")
        else:
            safe_print(
                f"{C_GREEN}{C_BOLD}[ok] no suspicious mojibake patterns found{C_RESET}"
            )

    if args.fail_on_find and findings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
