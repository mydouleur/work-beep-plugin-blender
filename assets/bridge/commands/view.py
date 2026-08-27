"""视口类桥命令：view.* 系列（需要 GUI 模式的 3D 视口，无头模式会报错）。"""

import bpy

from registry import command, find_view3d_context


@command("view.front")
def view_front(_params: dict) -> dict:
    """把 3D 视口切换到正视图（bpy.ops.view3d.view_axis 的封装）。"""
    ctx = find_view3d_context()
    if ctx is None:
        raise RuntimeError("找不到 3D 视口")
    with bpy.context.temp_override(**ctx):
        bpy.ops.view3d.view_axis(type="FRONT")
    return {"view": "front"}
