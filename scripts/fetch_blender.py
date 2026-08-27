#!/usr/bin/env python3
"""下载 Blender 绿色版（免安装 zip）到本插件期望的位置。

独立脚本，只用标准库，与 assets/bridge/ 下的 IPC 桥无关，不在 Blender 里跑。

用法（在本插件根目录或 scripts/ 下执行均可，路径按脚本位置自动锚定）：
    python scripts/fetch_blender.py                    # 下载默认版本到 runtime/
    python scripts/fetch_blender.py --mirror aliyun    # 走国内镜像（快很多）
    python scripts/fetch_blender.py --version 5.2.0    # 指定版本
    python scripts/fetch_blender.py --force            # 已存在也重新下载
    python scripts/fetch_blender.py --keep-zip         # 保留下载的压缩包

产物路径（与 src/Panel.vue 里 resolveAsset 的路径一致）：
    runtime/blender-<版本>-windows-x64/blender-<版本>-windows-x64/blender.exe

双层同名目录不是笔误：外层是解压目标目录，内层是 zip 自带的顶层目录。
runtime/ 不进版本库；deploy 时会把它以 junction 挂进 Host 的插件目录。

特性：断点续传（服务端支持 Range）、SHA256 校验、失败重试、原子落盘
（先解压到临时目录，校验通过再移入最终位置）。
"""

import argparse
import hashlib
import os
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# src/Panel.vue 里写死的是 5.2.1，改这里请同步改 src/Panel.vue
DEFAULT_VERSION = "5.2.1"
PLATFORM = "windows-x64"

# 各下载源的 release 根地址（目录结构一致：<根>/Blender<主.次>/<文件名>）
MIRRORS = {
    "official": "https://download.blender.org/release",
    "aliyun": "https://mirrors.aliyun.com/blender/release",
    "freedif": "https://mirror.freedif.org/blender/release",
}

CHUNK = 1024 * 256
RETRIES = 5
TIMEOUT = 30
# 官方源在 Cloudflare 后面，会对 Python-urllib 的默认 UA 直接返回 403，必须伪装
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) fetch_blender.py"


def plugin_root() -> Path:
    """插件根目录 = 本脚本所在 scripts/ 的上一级。"""
    return Path(__file__).resolve().parent.parent


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def release_dir(base: str, version: str) -> str:
    """<根>/Blender5.2 —— 目录名只取主次版本号。"""
    major, minor = version.split(".")[:2]
    return f"{base}/Blender{major}.{minor}"


def http_get(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    ctx = ssl.create_default_context()
    return urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)


def fetch_expected_sha256(base: str, version: str, filename: str) -> str | None:
    """取官方 sha256 清单里对应文件的哈希；取不到返回 None（跳过校验）。"""
    url = f"{release_dir(base, version)}/blender-{version}.sha256"
    try:
        with http_get(url) as resp:
            text = resp.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        print(f"[警告] 拿不到校验清单（{exc}），将跳过 SHA256 校验")
        return None
    for line in text.splitlines():
        parts = line.split()
        # 清单格式：<hash>  <文件名>
        if len(parts) == 2 and parts[1] == filename:
            return parts[0]
    print(f"[警告] 清单里没有 {filename}，将跳过 SHA256 校验")
    return None


def download(url: str, dest: Path) -> None:
    """下载到 dest，支持断点续传；dest.part 为临时文件。"""
    part = dest.with_suffix(dest.suffix + ".part")
    part.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, RETRIES + 1):
        done = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={done}-"} if done else {}
        try:
            with http_get(url, headers) as resp:
                # 服务端不认 Range 会返回 200 并从头发，此时废弃已下载的部分
                if done and resp.status != 206:
                    print("[提示] 服务端不支持断点续传，从头下载")
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
                            speed = done / max(now - start, 1e-6)
                            pct = f"{done / total * 100:5.1f}%" if total else "  ?  "
                            sys.stdout.write(
                                f"\r  {pct}  {human(done)}/{human(total) if total else '?'}"
                                f"  {human(speed)}/s   "
                            )
                            sys.stdout.flush()
            sys.stdout.write("\r" + " " * 60 + "\r")
            part.replace(dest)
            return
        except (urllib.error.URLError, OSError) as exc:
            sys.stdout.write("\n")
            if attempt == RETRIES:
                raise SystemExit(f"[错误] 下载失败（已重试 {RETRIES} 次）：{exc}")
            wait = 2 * attempt
            print(f"[警告] 下载中断（{exc}），{wait}s 后续传（第 {attempt}/{RETRIES} 次重试）")
            time.sleep(wait)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    size = path.stat().st_size
    read = 0
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
            read += len(chunk)
            sys.stdout.write(f"\r  校验中 {read / size * 100:5.1f}%")
            sys.stdout.flush()
    sys.stdout.write("\r" + " " * 30 + "\r")
    return digest.hexdigest()


def extract(zip_path: Path, outer_dir: Path, force: bool) -> Path:
    """解压到 outer_dir 下。先解到临时目录，成功后再整体移入，避免半成品。

    返回 zip 顶层目录落地后的路径（即含 blender.exe 的目录）。
    """
    tmp = outer_dir.parent / f".tmp-extract-{os.getpid()}"
    if tmp.exists():
        shutil.rmtree(tmp)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        # zip 自带一层顶层目录（blender-5.2.0-windows-x64/），取出它的名字
        tops = {n.split("/")[0] for n in names if "/" in n}
        if len(tops) != 1:
            raise SystemExit(f"[错误] 压缩包结构不符合预期，顶层目录：{sorted(tops)}")
        top = tops.pop()

        total = len(names)
        for i, name in enumerate(names, 1):
            zf.extract(name, tmp)
            if i % 200 == 0 or i == total:
                sys.stdout.write(f"\r  解压中 {i}/{total}")
                sys.stdout.flush()
    sys.stdout.write("\r" + " " * 30 + "\r")

    final = outer_dir / top
    if final.exists():
        if not force:
            shutil.rmtree(tmp)
            raise SystemExit(f"[错误] 目标已存在：{final}（加 --force 覆盖）")
        shutil.rmtree(final)

    outer_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp / top), str(final))
    shutil.rmtree(tmp, ignore_errors=True)
    return final


def main() -> None:
    parser = argparse.ArgumentParser(description="下载 Blender 绿色版到本插件 runtime/")
    parser.add_argument("--version", default=DEFAULT_VERSION, help=f"Blender 版本（默认 {DEFAULT_VERSION}）")
    parser.add_argument("--mirror", choices=MIRRORS, default="official", help="下载源（国内建议 aliyun）")
    parser.add_argument("--dest", type=Path, help="解压目标目录（默认 runtime/blender-<版本>-windows-x64）")
    parser.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    parser.add_argument("--keep-zip", action="store_true", help="保留下载的压缩包")
    parser.add_argument("--skip-verify", action="store_true", help="跳过 SHA256 校验")
    args = parser.parse_args()

    root = plugin_root()
    version = args.version
    filename = f"blender-{version}-{PLATFORM}.zip"
    base = MIRRORS[args.mirror]
    url = f"{release_dir(base, version)}/{filename}"

    outer = args.dest or (root / "runtime" / f"blender-{version}-{PLATFORM}")
    exe = outer / f"blender-{version}-{PLATFORM}" / "blender.exe"

    if exe.exists() and not args.force:
        print(f"已存在，无需下载：{exe}")
        return

    if version != DEFAULT_VERSION:
        print(
            f"[警告] src/Panel.vue 里写死的是 {DEFAULT_VERSION} 的路径，"
            f"下载 {version} 后需同步改那里的路径才能被插件找到"
        )

    zip_path = root / "runtime" / filename
    print(f"下载源：{url}")

    if zip_path.exists():
        print(f"发现已下载的压缩包：{zip_path}（跳过下载，如需重下请先删除）")
    else:
        download(url, zip_path)
        print(f"下载完成：{zip_path}（{human(zip_path.stat().st_size)}）")

    if not args.skip_verify:
        expected = fetch_expected_sha256(base, version, filename)
        if expected:
            actual = sha256_of(zip_path)
            if actual != expected:
                zip_path.unlink(missing_ok=True)
                raise SystemExit(
                    f"[错误] SHA256 不匹配，已删除损坏的压缩包，请重跑本脚本\n"
                    f"  期望：{expected}\n  实际：{actual}"
                )
            print("SHA256 校验通过")

    final = extract(zip_path, outer, args.force)

    if not args.keep_zip:
        zip_path.unlink(missing_ok=True)

    if not exe.exists():
        raise SystemExit(f"[错误] 解压完成但没找到 blender.exe，实际解压到：{final}")
    print(f"完成：{exe}")


if __name__ == "__main__":
    main()
