"""Tests for text-encoding-guard core detection logic."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from check_mojibake.core import (
    score_text,
    _line_has_mojibake,
    preview_lines,
    iter_files,
    try_gbk_recover,
    Finding,
)


# ---------------------------------------------------------------------------
# score_text — box-char detection
# ---------------------------------------------------------------------------

class TestBoxCharDetection:
    def test_no_replacement_char_returns_zero(self):
        score, reasons = score_text("Hello, world! 你好世界")
        assert "replacement-char=" not in " ".join(reasons)

    def test_single_replacement_char(self):
        score, reasons = score_text("Hello � world")
        assert score == 12
        assert "replacement-char=1" in reasons

    def test_multiple_replacement_chars(self):
        score, reasons = score_text("� � �")
        assert score == 36
        assert "replacement-char=3" in reasons

    def test_clean_text_zero_score(self):
        score, _ = score_text("The quick brown fox jumps over the lazy dog.")
        assert score == 0


# ---------------------------------------------------------------------------
# score_text — broken HTML tags
# ---------------------------------------------------------------------------

class TestBrokenTagDetection:
    def test_broken_closing_tag(self):
        score, reasons = score_text("<div>hello</div>\n?/div>")
        assert score >= 10
        assert "broken-end-tag=1" in reasons

    def test_multiple_broken_tags(self):
        text = "?/p>\n?/span>\n?/div>"
        score, reasons = score_text(text)
        assert "broken-end-tag=3" in reasons

    def test_intact_tags_not_flagged(self):
        score, reasons = score_text("<div>content</div>")
        assert "broken-end-tag" not in " ".join(reasons)


# ---------------------------------------------------------------------------
# score_text — ancient-text tokens
# ---------------------------------------------------------------------------

class TestAncientTextTokens:
    def test_known_mojibake_tokens(self):
        # Use a character that is actually in MOJIBAKE_TOKENS (0x9358)
        token = chr(0x9358)
        score, reasons = score_text(f"这里有{token}{token}{token}乱码")
        assert score > 0
        assert "mojibake-token-hits" in " ".join(reasons)

    def test_clean_chinese_no_tokens(self):
        score, reasons = score_text("用户登录成功，欢迎回来！")
        assert "mojibake-token-hits" not in " ".join(reasons)


# ---------------------------------------------------------------------------
# score_text — Kun-Kao pattern
# ---------------------------------------------------------------------------

class TestKunKaoPattern:
    def test_classic_kun_kao(self):
        score, reasons = score_text("锟斤拷锟斤拷")
        assert score >= 8
        assert "kun-kao-pattern" in " ".join(reasons)

    def test_kun_kao_with_separator(self):
        score, reasons = score_text("锟X斤Y拷")
        assert "kun-kao-pattern" in " ".join(reasons)

    def test_no_kun_kao(self):
        score, reasons = score_text("正常的中文文本")
        assert "kun-kao-pattern" not in " ".join(reasons)


# ---------------------------------------------------------------------------
# score_text — Tang-Tun pattern
# ---------------------------------------------------------------------------

class TestTangTunPattern:
    def test_tang_tang_tang(self):
        score, reasons = score_text("烫烫烫烫烫")
        assert score >= 6
        assert "tang-tun-pattern" in " ".join(reasons)

    def test_tun_tun_tun(self):
        score, reasons = score_text("屯屯屯屯")
        assert "tang-tun-pattern" in " ".join(reasons)

    def test_mixed_tang_tun(self):
        score, reasons = score_text("烫屯烫屯烫")
        assert "tang-tun-pattern" in " ".join(reasons)

    def test_two_chars_not_flagged(self):
        score, reasons = score_text("烫烫")
        assert "tang-tun-pattern" not in " ".join(reasons)


# ---------------------------------------------------------------------------
# score_text — question-code pattern
# ---------------------------------------------------------------------------

class TestQuestionCodePattern:
    def test_double_question_after_cjk(self):
        score, reasons = score_text("用户中心??")
        assert score >= 8
        assert "question-code" in " ".join(reasons)

    def test_single_question_not_flagged(self):
        # Single ? after CJK is normal punctuation
        score, reasons = score_text("请确认?")
        assert "question-code" not in " ".join(reasons)

    def test_ternary_not_flagged(self):
        # JS ternary: "中文" ? value : other
        score, reasons = score_text('const x = "中文" ? value : other')
        assert "question-code" not in " ".join(reasons)


# ---------------------------------------------------------------------------
# score_text — ISO diacritics
# ---------------------------------------------------------------------------

class TestIsoDiacritics:
    def test_few_diacritics_not_flagged(self):
        score, reasons = score_text("cafe resume")
        # No diacritics at all
        assert "iso-mojibake" not in " ".join(reasons)

    def test_many_diacritics_flagged(self):
        score, reasons = score_text("çæéîôüñàáâãä")
        assert "iso-mojibake" in " ".join(reasons)

    def test_clean_ascii_no_iso(self):
        score, reasons = score_text("Hello World 123")
        assert "iso-mojibake" not in " ".join(reasons)


# ---------------------------------------------------------------------------
# _line_has_mojibake
# ---------------------------------------------------------------------------

class TestLineHasMojibake:
    def test_clean_line(self):
        assert not _line_has_mojibake("Hello, world!")

    def test_line_with_replacement_char(self):
        assert _line_has_mojibake("Hello � world")

    def test_line_with_broken_tag(self):
        assert _line_has_mojibake("?/div>")

    def test_line_with_tang_tun(self):
        assert _line_has_mojibake("烫烫烫烫烫")


# ---------------------------------------------------------------------------
# preview_lines
# ---------------------------------------------------------------------------

class TestPreviewLines:
    def test_no_mojibake_returns_empty(self):
        result = preview_lines("Line one\nLine two\nLine three")
        assert result == []

    def test_returns_mojibake_lines(self):
        text = "Good line\n烫烫烫烫烫\nAnother good\n?/div>"
        result = preview_lines(text)
        assert len(result) >= 1
        assert "烫烫烫烫烫" in result[0]

    def test_truncation_indicator(self):
        long_line = "烫" * 200
        result = preview_lines(long_line)
        assert len(result) == 1
        assert "..." in result[0]

    def test_max_lines_limit(self):
        lines = "\n".join(f"烫烫烫烫烫 line {i}" for i in range(10))
        result = preview_lines(lines)
        assert len(result) <= 4

    def test_line_numbers(self):
        text = "Good\nBad 烫烫烫烫烫\nGood again"
        result = preview_lines(text)
        assert result[0].startswith("L2:")


# ---------------------------------------------------------------------------
# iter_files
@pytest.fixture()
def tmp_dir():
    """Create a temp directory (works around Windows pytest-asyncio issues)."""
    d = Path(tempfile.mkdtemp(prefix="teg_test_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestIterFiles:
    def test_finds_matching_extensions(self, tmp_dir: Path):
        (tmp_dir / "test.py").write_text("hello")
        (tmp_dir / "test.md").write_text("hello")
        (tmp_dir / "test.bin").write_text("hello")
        files = list(iter_files(tmp_dir, {".py", ".md"}))
        names = {f.name for f in files}
        assert "test.py" in names
        assert "test.md" in names
        assert "test.bin" not in names

    def test_skips_hidden_dirs(self, tmp_dir: Path):
        hidden = tmp_dir / ".git"
        hidden.mkdir()
        (hidden / "config.py").write_text("hello")
        files = list(iter_files(tmp_dir, {".py"}))
        assert len(files) == 0

    def test_skips_node_modules(self, tmp_dir: Path):
        nm = tmp_dir / "node_modules"
        nm.mkdir()
        (nm / "index.js").write_text("hello")
        files = list(iter_files(tmp_dir, {".js"}))
        assert len(files) == 0

    def test_empty_directory(self, tmp_dir: Path):
        files = list(iter_files(tmp_dir, {".py"}))
        assert files == []

    def test_skips_symlinks(self, tmp_dir: Path):
        target = tmp_dir / "target.py"
        target.write_text("hello")
        link = tmp_dir / "link.py"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not supported on this platform")
        files = list(iter_files(tmp_dir, {".py"}))
        names = {f.name for f in files}
        assert "target.py" in names
        assert "link.py" not in names


# ---------------------------------------------------------------------------
# try_gbk_recover
# ---------------------------------------------------------------------------

class TestGbkRecover:
    def test_returns_none_for_clean_text(self):
        assert try_gbk_recover("Hello, world!") is None

    def test_returns_none_for_already_corrupted(self):
        # Text that is truly corrupted beyond recovery
        assert try_gbk_recover("� � �") is None

    def test_recovers_common_corruption(self):
        # Simulate: take valid UTF-8 Chinese, encode as if GBK was misread
        original = "用户登录成功"
        raw_bytes = original.encode("utf-8")
        # Misread UTF-8 bytes as GBK
        corrupted = raw_bytes.decode("gb18030", errors="replace")
        # The corrupted text should be different
        assert corrupted != original
        # try_gbk_recover should recover it
        recovered = try_gbk_recover(corrupted)
        assert recovered is not None


# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------

class TestFinding:
    def test_creation(self):
        f = Finding(path="test.py", score=10, reasons=["test"], preview=["L1: x"])
        assert f.path == "test.py"
        assert f.score == 10

    def test_as_dict(self):
        f = Finding(path="test.py", score=10, reasons=["test"], preview=[])
        d = f.__dict__
        assert d == {"path": "test.py", "score": 10, "reasons": ["test"], "preview": []}


# ---------------------------------------------------------------------------
# Integration — real corruption patterns
# ---------------------------------------------------------------------------

class TestRealWorldPatterns:
    def test_utf8_as_gbk_corruption(self):
        # This is what "用户登录成功" looks like when UTF-8 bytes
        # are misread as GBK
        corrupted = "鐢ㄦ埛鐧诲綍鎴愬姛"
        score, reasons = score_text(corrupted)
        assert score > 0

    def test_clean_chinese_passes(self):
        clean = "用户登录成功，欢迎回来！数据库连接正常。"
        score, reasons = score_text(clean)
        assert score == 0

    def test_mixed_content(self):
        text = """
        # 用户管理模块
        def login(user: str, password: str) -> bool:
            '''用户登录验证'''
            return True
        """
        score, _ = score_text(text)
        assert score == 0

    def test_html_with_corruption(self):
        text = '<div class="card">\n  <p>鐢ㄦ埛涓�績</p>\n  ?/div>'
        score, reasons = score_text(text)
        assert score > 0
        assert "broken-end-tag" in " ".join(reasons) or "mojibake-token-hits" in " ".join(reasons)
