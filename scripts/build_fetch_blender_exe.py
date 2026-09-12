#!/usr/bin/env python3
"""用 PyInstaller 把 fetch_blender.py 打成 onefile EXE（用户机无需 Python）。

产物：scripts/dist/fetch_blender.exe
依赖：本机已装 Python，且能 pip install pyinstaller。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPT = HERE / "fetch_blender.py"
DIST = HERE / "dist"
NAME = "fetch_blender"


def main() -> int:
    if not SCRIPT.is_file():
        print(f"找不到 {SCRIPT}", file=sys.stderr)
        return 1

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("正在安装 pyinstaller…", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    DIST.mkdir(parents=True, exist_ok=True)
    work = HERE / ".pyinstaller-work"
    if work.exists():
        shutil.rmtree(work)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        f"--name={NAME}",
        f"--distpath={DIST}",
        f"--workpath={work}",
        f"--specpath={work}",
        str(SCRIPT),
    ]
    print("执行：", " ".join(cmd), file=sys.stderr)
    subprocess.check_call(cmd)

    exe = DIST / f"{NAME}.exe"
    if not exe.is_file():
        # 非 Windows 上产物无 .exe 后缀
        exe = DIST / NAME
    if not exe.is_file():
        print("打包失败：未找到产物", file=sys.stderr)
        return 1

    print(f"完成：{exe}", file=sys.stderr)

    # 同步到插件 assets，供 Host resolveAsset("tools/fetch_blender.exe")
    tools = ROOT / "assets" / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    dest = tools / exe.name
    shutil.copy2(exe, dest)
    print(f"已复制到：{dest}", file=sys.stderr)

    # 冒烟：list
    r = subprocess.run([str(exe), "list"], cwd=str(ROOT), capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        print(f"冒烟 list 失败，exit={r.returncode}", file=sys.stderr)
        return r.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
