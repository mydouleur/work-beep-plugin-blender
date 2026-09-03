"""PNG 文件级验收（标准库，可在系统 Python 里单测）。"""

from __future__ import annotations

import os
import struct
from typing import Any

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def validate_png(path: str) -> dict[str, Any]:
    """存在、非空、PNG 签名、IHDR 宽高。"""
    check: dict[str, Any] = {"path": path, "ok": False}
    if not os.path.isfile(path):
        check["error"] = "文件不存在"
        return check
    size = os.path.getsize(path)
    check["bytes"] = size
    if size <= 0:
        check["error"] = "空文件"
        return check
    with open(path, "rb") as f:
        header = f.read(8)
        if header != PNG_MAGIC:
            check["error"] = "不是合法 PNG"
            return check
        ihdr = f.read(16)
    if len(ihdr) < 16 or ihdr[4:8] != b"IHDR":
        check["error"] = "PNG 缺少 IHDR"
        return check
    check["width"] = struct.unpack(">I", ihdr[8:12])[0]
    check["height"] = struct.unpack(">I", ihdr[12:16])[0]
    if check["width"] < 8 or check["height"] < 8:
        check["error"] = f"分辨率过小 {check['width']}x{check['height']}"
        return check
    check["ok"] = True
    return check
