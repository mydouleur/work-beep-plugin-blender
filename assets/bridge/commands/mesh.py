"""网格类桥命令：mesh.* 系列（读 bpy 网格对象统计）。"""

from typing import Any

import bpy

from registry import command


def _get_mesh_object(name: str):
    obj = bpy.data.objects.get(name)

    if obj is None:
        raise ValueError(f'找不到对象 "{name}"')

    if obj.type != "MESH":
        raise ValueError(f'对象 "{name}" 不是网格（当前类型：{obj.type}）')

    return obj


@command("mesh.stats")
def mesh_stats(params: dict[str, Any]) -> dict[str, Any]:
    """返回指定网格对象的顶点 / 边 / 面数量。"""
    name = str(params.get("name", "")).strip()

    if not name:
        raise ValueError("缺少参数 name")

    obj = _get_mesh_object(name)
    mesh = obj.data

    return {
        "name": obj.name,
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "faces": len(mesh.polygons),
    }
