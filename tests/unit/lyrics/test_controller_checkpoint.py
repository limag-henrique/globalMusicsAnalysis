"""Checkpoint behavior with real Windows readers that deny atomic replacement."""

import ctypes
import json
import os
import runpy
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows sharing modes")


def deny_delete_reader(path: Path):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
    ]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW(str(path), 0x80000000, 3, None, 3, 0x80, None)
    assert handle != ctypes.c_void_p(-1).value
    return kernel, handle


def test_checkpoint_survives_a_temporary_windows_reader(tmp_path, monkeypatch):
    write_state = runpy.run_path("scripts/run_continuous_lyrics.py")["write_state"]
    path = tmp_path / "status.json"
    path.write_text('{"status": "old"}', encoding="utf-8")
    kernel, handle = deny_delete_reader(path)
    replace = os.replace
    blocked = False

    def release_reader_after_block(source, destination):
        nonlocal blocked, handle
        try:
            return replace(source, destination)
        except PermissionError:
            blocked = True
            kernel.CloseHandle(handle)
            handle = None
            raise

    monkeypatch.setattr(os, "replace", release_reader_after_block)
    try:
        write_state(path, {"status": "running", "retry_run_ids": ["persist-before-submit"]})
        assert blocked
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["status"] == "running"
        assert saved["retry_run_ids"] == ["persist-before-submit"]
    finally:
        if handle is not None:
            kernel.CloseHandle(handle)


def test_persistent_windows_reader_preserves_previous_checkpoint(tmp_path):
    write_state = runpy.run_path("scripts/run_continuous_lyrics.py")["write_state"]
    path = tmp_path / "status.json"
    original = '{"status": "old", "submission_attempted": false}'
    path.write_text(original, encoding="utf-8")
    kernel, handle = deny_delete_reader(path)
    try:
        with pytest.raises(PermissionError):
            write_state(path, {"status": "running", "submission_attempted": True})
        assert path.read_text(encoding="utf-8") == original
        assert json.loads(path.with_suffix(".continuous.tmp").read_text())["submission_attempted"]
    finally:
        kernel.CloseHandle(handle)
