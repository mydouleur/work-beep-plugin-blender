"""PNG 文件验收正反例（系统 Python，不依赖 Blender）。"""

from __future__ import annotations

import os
import struct
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "assets" / "bridge"))

from validate_png import PNG_MAGIC, validate_png  # noqa: E402


def _header(width: int, height: int) -> bytes:
    return PNG_MAGIC + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)


def _write(dir_path: str, name: str, data: bytes) -> str:
    path = os.path.join(dir_path, name)
    with open(path, "wb") as f:
        f.write(data)
    return path


def main() -> int:
    failed: list[str] = []

    def ok(name: str, cond: bool, detail: str = "") -> None:
        if cond:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name}  {detail}")
            failed.append(name)

    with tempfile.TemporaryDirectory(prefix="beep-png-") as folder:
        good = _write(folder, "ok.png", _header(16, 16))
        empty = _write(folder, "empty.png", b"")
        junk = _write(folder, "junk.png", b"not-a-png")
        tiny = _write(folder, "tiny.png", _header(4, 4))
        no_ihdr = _write(folder, "noihdr.png", PNG_MAGIC + b"xxxxxxxxxxxxxxxx")
        missing = os.path.join(folder, "gone.png")

        r = validate_png(good)
        ok("pos.valid_png", r.get("ok") is True and r.get("width") == 16)

        r = validate_png(missing)
        ok("neg.missing_file", r.get("ok") is False and r.get("error") == "文件不存在")

        r = validate_png(empty)
        ok("neg.empty_file", r.get("ok") is False and r.get("error") == "空文件")

        r = validate_png(junk)
        ok("neg.not_png", r.get("ok") is False and r.get("error") == "不是合法 PNG")

        r = validate_png(tiny)
        ok("neg.too_small", r.get("ok") is False and "分辨率过小" in str(r.get("error", "")))

        r = validate_png(no_ihdr)
        ok("neg.no_ihdr", r.get("ok") is False and r.get("error") == "PNG 缺少 IHDR")

    print()
    if failed:
        print(f"PNG 验收：{len(failed)} 失败")
        return 1
    print("PNG 验收：6 通过（1 正例 / 5 反例）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
