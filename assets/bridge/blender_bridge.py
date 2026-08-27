"""Blender 内 IPC 桥：入口 + 传输层（TCP JSON-lines），不含具体命令。

启动方式（由启动器拉起）：
    blender --python blender_bridge.py -- --port 12345        # GUI 模式
    blender -b --python blender_bridge.py -- --port 12345     # 无头模式（批处理）

协议：TCP，每行一个 JSON。
    主通道  {"cmd": "<name>", "params": {...}}   -> 路由到 registry.COMMANDS（见 commands/）
    逃生舱  {"type": "ping"}                     -> {"ok": true, "result": "pong", ...}
            {"type": "exec", "code": "..."}      -> 主线程执行任意 bpy 代码（调试用）
    响应    {"ok": true, "data"/"result": ...} 或 {"ok": false, "error": ...}

并发模型：
- GUI 模式：socket 在子线程收发；bpy 非线程安全，
  所有命令经 bpy.app.timers 投递回 Blender 主线程执行。
- 无头模式：脚本返回 Blender 即退出（timer 不会续命），
  因此直接在主线程跑 accept 循环、同步执行命令——
  此时本线程就是主线程，bpy 调用安全，代价是一次只服务一个连接。
"""

import argparse
import contextlib
import io
import json
import os
import queue
import socket
import sys
import threading
import traceback
from typing import Callable

import bpy

# --python 启动时脚本目录不一定在 sys.path，补上才能 import 同包模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import commands  # noqa: F401  # 副作用：各命令模块经装饰器填充注册表
from registry import COMMANDS

# 待执行命令队列：(命令 dict, 结果 queue)，由 timer 在主线程消费（仅 GUI 模式）
_pending: queue.Queue = queue.Queue()


def _parse_args() -> argparse.Namespace:
    # blender --python xxx.py -- 之后的参数才属于本脚本
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    return parser.parse_args(argv)


def _execute(cmd: dict) -> dict:
    """在 Blender 主线程执行一条命令。"""
    # 结构化命令（CLI 主通道）
    if "cmd" in cmd:
        name = cmd["cmd"]
        handler = COMMANDS.get(name)
        if handler is None:
            return {"ok": False, "error": f"unknown command: {name!r}"}
        try:
            return {"ok": True, "data": handler(cmd.get("params") or {})}
        except Exception:
            return {"ok": False, "error": traceback.format_exc()}
    # 调试逃生舱
    cmd_type = cmd.get("type")
    if cmd_type == "ping":
        return {"ok": True, "result": "pong", "blender": bpy.app.version_string}
    if cmd_type == "exec":
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(cmd.get("code", ""), {"bpy": bpy})
            return {"ok": True, "result": buf.getvalue()}
        except Exception:
            return {"ok": False, "error": traceback.format_exc()}
    return {"ok": False, "error": f"unknown command type: {cmd_type!r}"}


def _pump():
    """timer 回调：在主线程把队列里的命令执行完，然后重新注册自己。"""
    while True:
        try:
            cmd, result_q = _pending.get_nowait()
        except queue.Empty:
            break
        result_q.put(_execute(cmd))
    return 0.05  # 50ms 后再次执行


def _handle_conn(conn: socket.socket, execute: Callable[[dict], dict]) -> None:
    """处理一条客户端连接：逐行收 JSON、执行、回写结果。"""
    with conn:
        file = conn.makefile("rw", encoding="utf-8", newline="\n")
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line)
            except json.JSONDecodeError as exc:
                resp = {"ok": False, "error": f"bad json: {exc}"}
            else:
                resp = execute(cmd)
            file.write(json.dumps(resp, ensure_ascii=False) + "\n")
            file.flush()


def _execute_on_main_thread(cmd: dict) -> dict:
    """GUI 模式用：把命令投递给主线程 timer，阻塞等结果。"""
    result_q: queue.Queue = queue.Queue()
    _pending.put((cmd, result_q))
    return result_q.get()


def main() -> None:
    args = _parse_args()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(4)
    print(f"[bridge] listening on {args.host}:{args.port}", flush=True)

    if bpy.app.background:
        # 无头模式：主线程直接跑服务循环（脚本返回进程即退出，不能交给子线程）
        while True:
            conn, _ = server.accept()
            _handle_conn(conn, _execute)
    else:
        # GUI 模式：timer 主循环续命，子线程收发网络
        bpy.app.timers.register(_pump, first_interval=0.1)

        def accept_loop() -> None:
            while True:
                conn, _ = server.accept()
                threading.Thread(
                    target=_handle_conn,
                    args=(conn, _execute_on_main_thread),
                    daemon=True,
                ).start()

        threading.Thread(target=accept_loop, daemon=True).start()


main()
