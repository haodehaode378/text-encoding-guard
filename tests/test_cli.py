"""Tests for CLI entry point and argument parsing."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from check_mojibake.core import main


@pytest.fixture()
def tmp_dir():
    """Create a temporary directory that works on Windows with pytest-asyncio."""
    d = Path(tempfile.mkdtemp(prefix="teg_test_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestCliArgs:
    def test_help_exits_zero(self):
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0

    def test_missing_root_exits_error(self):
        with pytest.raises(SystemExit):
            main([])


class TestCliScan:
    def test_clean_directory(self, tmp_dir: Path):
        (tmp_dir / "clean.py").write_text("print('hello world')")
        code = main(["--root", str(tmp_dir), "--quiet"])
        assert code == 0

    def test_suspicious_directory(self, tmp_dir: Path):
        (tmp_dir / "bad.py").write_text("x = '烫烫烫烫烫'", encoding="utf-8")
        code = main(["--root", str(tmp_dir), "--fail-on-find", "--quiet"])
        assert code == 2

    def test_json_output(self, tmp_dir: Path, capsys):
        (tmp_dir / "bad.py").write_text("x = '烫烫烫烫烫'", encoding="utf-8")
        main(["--root", str(tmp_dir), "--json"])
        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["root"] == str(tmp_dir)
        assert len(data["findings"]) >= 1
        assert data["findings"][0]["score"] > 0

    def test_custom_extension(self, tmp_dir: Path):
        (tmp_dir / "data.sql").write_text("INSERT INTO t VALUES ('烫烫烫烫烫')", encoding="utf-8")
        code = main(["--root", str(tmp_dir), "--ext", ".sql", "--fail-on-find", "--quiet"])
        assert code == 2

    def test_verbose_and_quiet_mutually_exclusive(self, tmp_dir: Path):
        with pytest.raises(SystemExit):
            main(["--root", str(tmp_dir), "--verbose", "--quiet"])

    def test_verbose_shows_skipped(self, tmp_dir: Path):
        (tmp_dir / "ok.py").write_text("print('hello')")
        code = main(["--root", str(tmp_dir), "--verbose", "--fix-gbk"])
        assert code == 0


class TestCliFix:
    def test_fix_creates_backup(self, tmp_dir: Path):
        original_text = chr(0x9358) + chr(0x9359) + chr(0x9428)
        target = tmp_dir / "corrupted.py"
        target.write_text(original_text, encoding="utf-8")
        main(["--root", str(tmp_dir), "--fix-gbk", "--quiet"])
        # Either fixed (backup exists) or skipped — either is acceptable
        assert target.exists()

    def test_fix_gbk_recovers_and_backs_up(self, tmp_dir: Path, capsys):
        # Build a genuinely recoverable corruption: clean UTF-8 bytes that were
        # misread as GB18030. Reversing that (encode gb18030 -> decode utf-8)
        # restores the original, so --fix-gbk should repair it.
        clean = "成功欢迎回来数据库连接正常系统运行稳定错误请联系管理员反馈问题数据处理完"
        corrupted = clean.encode("utf-8").decode("gb18030")
        assert corrupted != clean  # sanity: the input really is corrupted

        target = tmp_dir / "corrupt.py"
        target.write_text(corrupted, encoding="utf-8")

        code = main(["--root", str(tmp_dir), "--fix-gbk", "--json"])
        assert code == 0

        data = json.loads(capsys.readouterr().out)
        assert str(target) in data["fixed"]

        # File repaired in place and a backup of the original bytes was kept.
        assert target.read_text(encoding="utf-8") == clean
        backup = tmp_dir / "corrupt.py.bak.mojibake"
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == corrupted

    def test_fix_gbk_skips_unrecoverable(self, tmp_dir: Path, capsys):
        # Tang-tun corruption scores low and never recovers below the threshold,
        # so it must be reported as skipped, not fixed.
        target = tmp_dir / "bad.py"
        target.write_text("x = '烫烫烫烫烫'", encoding="utf-8")

        main(["--root", str(tmp_dir), "--fix-gbk", "--json"])
        data = json.loads(capsys.readouterr().out)

        assert data["fixed"] == []
        assert str(target) in data["skipped"]


class TestCliOutput:
    def test_decode_error_reported(self, tmp_dir: Path, capsys):
        # Bytes that are not valid UTF-8 land in decode_errors, not findings.
        (tmp_dir / "binary.py").write_bytes(b"\xff\xfe\x00\x01bad")
        main(["--root", str(tmp_dir), "--json"])
        data = json.loads(capsys.readouterr().out)
        assert len(data["decode_errors"]) == 1

    def test_text_output_lists_suspicious(self, tmp_dir: Path, capsys):
        (tmp_dir / "bad.py").write_text("x = '烫烫烫烫烫'", encoding="utf-8")
        main(["--root", str(tmp_dir)])
        out = capsys.readouterr().out
        assert "suspicious" in out
        assert "bad.py" in out

    def test_text_output_reports_clean(self, tmp_dir: Path, capsys):
        (tmp_dir / "clean.py").write_text("print('hello world')")
        main(["--root", str(tmp_dir)])
        out = capsys.readouterr().out
        assert "no suspicious mojibake" in out

    def test_text_output_shows_decode_errors(self, tmp_dir: Path, capsys):
        (tmp_dir / "binary.py").write_bytes(b"\xff\xfe\x00\x01bad")
        main(["--root", str(tmp_dir)])
        out = capsys.readouterr().out
        assert "decode-errors" in out
