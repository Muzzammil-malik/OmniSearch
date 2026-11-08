"""Tests for recursive folder scanning and exclusions."""

from pathlib import Path
from app.ingestion.scanner import FolderScanner


def test_scanner_discovers_supported_and_unsupported(tmp_path: Path) -> None:
    # Set up directory tree
    (tmp_path / "doc.txt").write_text("Hello text", encoding="utf-8")
    (tmp_path / "script.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "data.csv").write_text("a,b\n1,2", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02")
    (tmp_path / "archive.zip").write_bytes(b"PK\x03\x04")

    sub_dir = tmp_path / "subdir"
    sub_dir.mkdir()
    (sub_dir / "nested.md").write_text("# Markdown", encoding="utf-8")

    scanner = FolderScanner()
    report = scanner.scan(tmp_path)

    assert report.total_discovered == 7
    supported_filenames = {f.filename for f in report.supported_files}
    unsupported_filenames = {f.filename for f in report.unsupported_files}

    assert "doc.txt" in supported_filenames
    assert "script.py" in supported_filenames
    assert "data.csv" in supported_filenames
    assert "nested.md" in supported_filenames
    assert "image.png" in supported_filenames

    assert "archive.zip" in unsupported_filenames
    assert "binary.bin" in unsupported_filenames
    assert len(report.scan_errors) == 0


def test_scanner_prunes_excluded_directories(tmp_path: Path) -> None:
    # Create files in root and inside excluded dirs
    (tmp_path / "keep.txt").write_text("Keep me", encoding="utf-8")

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config.txt").write_text("Git config", encoding="utf-8")

    node_dir = tmp_path / "node_modules"
    node_dir.mkdir()
    (node_dir / "package.json").write_text("{}", encoding="utf-8")

    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text("home = ...", encoding="utf-8")

    scanner = FolderScanner()
    report = scanner.scan(tmp_path)

    # Only keep.txt should be discovered
    discovered_filenames = {f.filename for f in report.supported_files + report.unsupported_files}
    assert "keep.txt" in discovered_filenames
    assert "config.txt" not in discovered_filenames
    assert "package.json" not in discovered_filenames
    assert "pyvenv.cfg" not in discovered_filenames
    assert len(report.skipped_paths) >= 3


def test_scanner_handles_nonexistent_directory(tmp_path: Path) -> None:
    missing_dir = tmp_path / "nonexistent_subfolder"
    scanner = FolderScanner()
    report = scanner.scan(missing_dir)

    assert report.total_discovered == 0
    assert len(report.scan_errors) == 1
    assert "does not exist" in report.scan_errors[0]

