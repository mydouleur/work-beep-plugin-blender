"""CI 入口：系统 Python 跑 PNG 单测；找到绿色版后拉起无头 Blender 跑桥命令正反例。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
VERSION = "5.2.1"
DEFAULT_EXE = (
    ROOT
    / "runtime"
    / f"blender-{VERSION}-windows-x64"
    / f"blender-{VERSION}-windows-x64"
    / "blender.exe"
)
RESULT = ROOT / "scripts" / ".ci-bridge-result.txt"


def find_blender() -> Path | None:
    env = os.environ.get("BLENDER_EXE", "").strip()
    if env:
        path = Path(env)
        if path.is_file():
            return path
    if DEFAULT_EXE.is_file():
        return DEFAULT_EXE
    return None


def main() -> int:
    png = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "test_validate_png.py")],
        cwd=ROOT,
    )
    if png.returncode != 0:
        return png.returncode

    exe = find_blender()
    if exe is None:
        print(
            "找不到 blender.exe。请先运行：\n"
            "  python scripts/fetch_blender.py --mirror aliyun\n"
            "或设置环境变量 BLENDER_EXE。"
        )
        return 1

    RESULT.unlink(missing_ok=True)
    print(f"用 {exe} 跑桥命令集成测试")
    proc = subprocess.run(
        [
            str(exe),
            "-b",
            "--factory-startup",
            "--python",
            str(ROOT / "scripts" / "test_bridge.py"),
        ],
        cwd=ROOT,
    )
    if RESULT.is_file():
        code = int(RESULT.read_text(encoding="utf-8").strip() or "1")
        RESULT.unlink(missing_ok=True)
        return code
    if proc.returncode != 0:
        return proc.returncode
    print("Blender 未写出测试结果")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
