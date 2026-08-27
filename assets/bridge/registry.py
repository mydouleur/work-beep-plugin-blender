"""桥命令注册表：name -> handler(params) -> JSON 可序列化结果。

新增命令的方式：在 commands/ 下的模块里写函数并用 @command("xxx.yyy") 装饰，
请求协议 {"cmd": "xxx.yyy", "params": {...}} 即会路由到该函数。
"""

from typing import Callable

import bpy

# 命令名 -> 处理函数（由 commands/ 各模块的装饰器副作用填充）
COMMANDS: dict[str, Callable[[dict], dict]] = {}


def command(name: str) -> Callable:
    """装饰器：把函数注册为桥命令。"""

    def decorator(fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
        COMMANDS[name] = fn
        return fn

    return decorator


def find_view3d_context() -> dict | None:
    """找一个 3D 视口的完整上下文。

    view3d/screen 系算子的 poll 需要 window/screen/area/region 四件套，
    所有视口类命令共用此辅助。
    """
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                if region is not None:
                    return {
                        "window": window,
                        "screen": window.screen,
                        "area": area,
                        "region": region,
                    }
    return None
