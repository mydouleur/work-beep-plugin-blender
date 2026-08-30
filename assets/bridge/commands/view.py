"""视口类桥命令：view.* 系列（需要 GUI 模式的 3D 视口，无头模式会报错）。"""

import bpy

import check
from registry import command, find_view3d_context

# Blender view_axis 与多视图 2D 出图共用的方向名
AXIS = {
    "front": "FRONT",
    "back": "BACK",
    "left": "LEFT",
    "right": "RIGHT",
    "top": "TOP",
    "bottom": "BOTTOM",
}


def set_view_axis(view: str) -> str:
    key = view.strip().lower()
    if key not in AXIS:
        raise ValueError(f"未知视图: {view}（可选 {', '.join(AXIS)}）")
    ctx = find_view3d_context()
    if ctx is None:
        raise RuntimeError("找不到 3D 视口")
    with bpy.context.temp_override(**ctx):
        bpy.ops.view3d.view_axis(type=AXIS[key])
    if find_view3d_context() is None:
        check.fail("切视图后找不到 3D 视口")
    return key


@command("view.front")
def view_front(_params: dict) -> dict:
    """把 3D 视口切换到正视图。"""
    return check.stamp({"view": set_view_axis("front")})


@command("view.set_axis")
def view_set_axis(params: dict) -> dict:
    """把 3D 视口切到指定正交轴视图。"""
    return check.stamp({"view": set_view_axis(str(params.get("view", "")))})
