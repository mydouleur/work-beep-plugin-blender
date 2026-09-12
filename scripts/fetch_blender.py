#!/usr/bin/env python3
"""下载 / 探测 Blender 绿色版（免安装 zip）。

独立脚本，只用标准库，与 assets/bridge/ 下的 IPC 桥无关，不在 Blender 里跑。
stdout 只输出机器可读 JSON / JSONL；人读提示走 stderr。

用法：
    python scripts/fetch_blender.py list
    python scripts/fetch_blender.py download --version 5.2.1 --mirror aliyun
    python scripts/fetch_blender.py download --version 4.5.13 --force

产物路径（与 src/runtime.ts 一致，双层同名目录不是笔误）：
    runtime/blender-<版本>-windows-x64/blender-<版本>-windows-x64/blender.exe

版本目录与 src/runtime.ts 的 BLENDER_CATALOG 同步。
打成 EXE：pnpm build:fetch-blender → scripts/dist/fetch_blender.exe
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

PLATFORM = "windows-x64"

# 与 src/runtime.ts BLENDER_CATALOG 同步。downloadable=False 的条目 list 标 coming_soon。
CATALOG: list[dict[str, Any]] = [
    {
        "id": "5.2.1",
        "label": "Blender 5.2.1",
        "tags": ["recommended"],
        "downloadable": True,
    },
    {
        "id": "4.5.13",
        "label": "Blender 4.5 LTS",
        "tags": ["lts"],
        "downloadable": True,
    },
    {
        "id": "5.1.0",
        "label": "Blender 5.1.0",
        "tags": [],
        "downloadable": True,
    },
    {
        "id": "4.3.2",
        "label": "Blender 4.3.2",
        "tags": [],
        "downloadable": True,
    },
]

DEFAULT_VERSION = next(e["id"] for e in CATALOG if "recommended" in e["tags"])

MIRRORS = {
    "official": "https://download.blender.org/release",
    "aliyun": "https://mirrors.aliyun.com/blender/release",
    "freedif": "https://mirror.freedif.org/blender/release",
}

CHUNK = 1024 * 256
RETRIES = 5
TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) fetch_blender.py"


def plugin_root() -> Path:
    """插件根目录。源码：scripts/ 上一级；冻结 EXE：scripts/dist/ 上两级。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent.parent
    return Path(__file__).resolve().parent.parent


def emit(obj: dict[str, Any]) -> None:
    """stdout 一行 JSON（list 最终结果或 download 的 JSONL 事件）。"""
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    try:
        sys.stdout.buffer.write(line.encode("utf-8"))
        sys.stdout.buffer.flush()
    except Exception:
        sys.stdout.write(line)
        sys.stdout.flush()


def log(msg: str) -> None:
    data = (msg + "\n").encode("utf-8", errors="replace")
    try:
        sys.stderr.buffer.write(data)
        sys.stderr.buffer.flush()
    except Exception:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()


def _stop_blender_using(path: Path) -> None:
    """结束可执行路径落在 path 下的 blender.exe（覆盖安装前避免 WinError 5）。"""
    if os.name != "nt":
        return
    try:
        needle = str(path.resolve()).replace("'", "''").replace("/", "\\").lower()
    except OSError:
        needle = str(path).replace("'", "''").replace("/", "\\").lower()
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name = 'blender.exe'\" | "
        f"Where-Object {{ $_.ExecutablePath -and $_.ExecutablePath.ToLower().StartsWith('{needle}') }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        time.sleep(0.8)
    except Exception as exc:
        log(f"[警告] 结束占用进程失败：{exc}")


def _rmtree_retry(path: Path) -> None:
    """Windows 上常见「拒绝访问」：先停占用进程，再短暂重试。"""
    _stop_blender_using(path)
    last: OSError | None = None
    for attempt in range(1, 8):
        try:
            shutil.rmtree(path)
            return
        except OSError as exc:
            last = exc
            if attempt in (2, 4):
                _stop_blender_using(path)
            time.sleep(0.5 * attempt)
    # 最后手段：改名挪走，让新安装能就位
    trash = path.with_name(f"{path.name}.old-{os.getpid()}")
    try:
        path.rename(trash)
        log(f"[提示] 无法立即删除，已改名为 {trash}，可稍后手动删")
        return
    except OSError:
        pass
    raise RuntimeError(
        f"无法删除已有安装（文件被占用，请先结束 Blender 再下载或重装）: {path} ({last})"
    ) from last


def extract(zip_path: Path, outer: Path, force: bool) -> Path:
    tmp = outer.parent / f".tmp-extract-{os.getpid()}"
    if tmp.exists():
        _rmtree_retry(tmp)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        tops = {n.split("/")[0] for n in names if "/" in n}
        if len(tops) != 1:
            raise RuntimeError(f"压缩包结构不符合预期，顶层目录：{sorted(tops)}")
        top = tops.pop()
        for name in names:
            zf.extract(name, tmp)

    final = outer / top
    if final.exists():
        if not force:
            shutil.rmtree(tmp, ignore_errors=True)
            raise RuntimeError(f"目标已存在：{final}（加 --force 覆盖）")
        _rmtree_retry(final)

    outer.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp / top), str(final))
    shutil.rmtree(tmp, ignore_errors=True)
    return final


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def pack_name(version: str) -> str:
    return f"blender-{version}-{PLATFORM}"


def exe_path(root: Path, version: str) -> Path:
    pack = pack_name(version)
    return root / "runtime" / pack / pack / "blender.exe"


def outer_dir(root: Path, version: str) -> Path:
    return root / "runtime" / pack_name(version)


def release_dir(base: str, version: str) -> str:
    major, minor = version.split(".")[:2]
    return f"{base}/Blender{major}.{minor}"


def http_get(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    ctx = ssl.create_default_context()
    return urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)


def fetch_expected_sha256(base: str, version: str, filename: str) -> str | None:
    url = f"{release_dir(base, version)}/blender-{version}.sha256"
    try:
        with http_get(url) as resp:
            text = resp.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        log(f"[警告] 拿不到校验清单（{exc}），将跳过 SHA256 校验")
        return None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == filename:
            return parts[0]
    log(f"[警告] 清单里没有 {filename}，将跳过 SHA256 校验")
    return None


def download(url: str, dest: Path) -> None:
    """下载到 dest；进度经 emit(JSONL)。dest.part 为临时文件。"""
    part = dest.with_suffix(dest.suffix + ".part")
    part.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, RETRIES + 1):
        done = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={done}-"} if done else {}
        try:
            with http_get(url, headers) as resp:
                if done and resp.status != 206:
                    log("[提示] 服务端不支持断点续传，从头下载")
                    done = 0
                total = int(resp.headers.get("Content-Length", 0)) + done
                mode = "ab" if done else "wb"
                start, last_shown = time.monotonic(), 0.0

                with open(part, mode) as fh:
                    while True:
                        chunk = resp.read(CHUNK)
                        if not chunk:
                            break
                        fh.write(chunk)
                        done += len(chunk)
                        now = time.monotonic()
                        if now - last_shown >= 0.2:
                            last_shown = now
                            progress = (done / total) if total else 0.0
                            emit(
                                {
                                    "status": "downloading",
                                    "progress": round(progress, 4),
                                    "downloaded_bytes": done,
                                    "total_bytes": total,
                                }
                            )
            part.replace(dest)
            return
        except (urllib.error.URLError, OSError) as exc:
            if attempt == RETRIES:
                raise RuntimeError(f"下载失败（已重试 {RETRIES} 次）：{exc}") from exc
            wait = 2 * attempt
            log(f"[警告] 下载中断（{exc}），{wait}s 后续传（第 {attempt}/{RETRIES} 次重试）")
            time.sleep(wait)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def catalog_entry(version: str) -> dict[str, Any] | None:
    for e in CATALOG:
        if e["id"] == version:
            return e
    return None


def cmd_list(root: Path) -> int:
    versions = []
    for e in CATALOG:
        path = exe_path(root, e["id"])
        installed = path.is_file()
        if not e["downloadable"]:
            status = "coming_soon"
            out_path = None
        elif installed:
            status = "installed"
            out_path = str(path)
        else:
            status = "not_installed"
            out_path = None
        versions.append(
            {
                "id": e["id"],
                "label": e["label"],
                "tags": list(e["tags"]),
                "status": status,
                "path": out_path,
                "downloadable": bool(e["downloadable"]),
            }
        )
    emit({"ok": True, "versions": versions})
    return 0


def cmd_download(
    root: Path,
    version: str,
    mirror: str,
    dest: Path | None,
    force: bool,
    keep_zip: bool,
    skip_verify: bool,
) -> int:
    entry = catalog_entry(version)
    if entry is not None and not entry["downloadable"]:
        emit({"status": "error", "message": f"版本 {version} 尚未开放下载（coming soon）"})
        return 1

    filename = f"{pack_name(version)}.zip"
    base = MIRRORS[mirror]
    url = f"{release_dir(base, version)}/{filename}"
    outer = dest or outer_dir(root, version)
    exe = outer / pack_name(version) / "blender.exe"

    if exe.is_file() and not force:
        emit({"status": "installed", "version": version, "path": str(exe)})
        return 0

    zip_path = root / "runtime" / filename
    try:
        if zip_path.exists() and not force:
            log(f"发现已下载的压缩包：{zip_path}（跳过下载）")
        else:
            if force and zip_path.exists():
                zip_path.unlink()
            download(url, zip_path)

        if not skip_verify:
            emit({"status": "verifying"})
            expected = fetch_expected_sha256(base, version, filename)
            if expected:
                actual = sha256_of(zip_path)
                if actual != expected:
                    zip_path.unlink(missing_ok=True)
                    raise RuntimeError(
                        f"SHA256 不匹配\n  期望：{expected}\n  实际：{actual}"
                    )

        emit({"status": "extracting"})
        # 已通过「exe 存在且非 force」早退；此处覆盖半成品目录
        extract(zip_path, outer, force=True)

        if not keep_zip:
            zip_path.unlink(missing_ok=True)

        if not exe.is_file():
            raise RuntimeError(f"解压完成但没找到 blender.exe：{exe}")

        emit({"status": "installed", "version": version, "path": str(exe)})
        return 0
    except Exception as exc:
        emit({"status": "error", "message": str(exc)})
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Blender 绿色版探测 / 下载（stdout = JSON/JSONL）"
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="插件根目录（默认按脚本/EXE 位置推断）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="列出版本目录与本机安装状态（一行 JSON）")

    p_dl = sub.add_parser("download", help="下载并解压指定版本（JSONL 进度）")
    p_dl.add_argument("--version", default=DEFAULT_VERSION, help=f"默认 {DEFAULT_VERSION}")
    p_dl.add_argument("--mirror", choices=MIRRORS, default="aliyun", help="下载源")
    p_dl.add_argument("--dest", type=Path, help="解压外层目录（默认 runtime/blender-…）")
    p_dl.add_argument("--force", action="store_true", help="已存在也重新下载/覆盖")
    p_dl.add_argument("--keep-zip", action="store_true", help="保留 zip")
    p_dl.add_argument("--skip-verify", action="store_true", help="跳过 SHA256")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = (args.root or plugin_root()).resolve()

    if args.command == "list":
        return cmd_list(root)
    if args.command == "download":
        return cmd_download(
            root,
            version=args.version,
            mirror=args.mirror,
            dest=args.dest,
            force=args.force,
            keep_zip=args.keep_zip,
            skip_verify=args.skip_verify,
        )
    parser.error(f"未知命令：{args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
