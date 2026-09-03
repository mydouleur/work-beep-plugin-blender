"""事后验收：命令执行后再对照 bpy 状态，失败抛 RuntimeError（桥 ok=false，Host 回灌）。"""

from __future__ import annotations

from typing import Any, Iterable

import bpy


def fail(msg: str) -> None:
    raise RuntimeError(f"验收失败: {msg}")


def stamp(payload: dict[str, Any]) -> dict[str, Any]:
    payload["validated"] = True
    return payload


def object_exists(name: str, expected_type: str | None = None):
    obj = bpy.data.objects.get(name)
    if obj is None:
        fail(f'找不到对象 "{name}"')
    if expected_type and obj.type != expected_type:
        fail(f'对象 "{name}" 类型应为 {expected_type}，实际 {obj.type}')
    return obj


def object_gone(name: str) -> None:
    if bpy.data.objects.get(name) is not None:
        fail(f'对象 "{name}" 应已删除，但仍在场景中')


def vec_close(actual: Iterable[float], expected: Iterable[float], label: str, eps: float = 1e-3) -> None:
    a = [float(x) for x in actual]
    b = [float(x) for x in expected]
    if len(a) != len(b):
        fail(f"{label} 维度不一致")
    if any(abs(x - y) > eps for x, y in zip(a, b)):
        fail(f"{label} 不符：期望 {b}，实际 {a}")


def mesh_alive(name: str):
    obj = object_exists(name, "MESH")
    if obj.data is None or len(obj.data.polygons) < 1:
        fail(f'网格 "{name}" 没有面')
    return obj


def faces_increased(name: str, before: int) -> int:
    obj = mesh_alive(name)
    after = len(obj.data.polygons)
    if after <= before:
        fail(f'网格 "{name}" 面数未增加（{before} → {after}）')
    return after


def material_exists(name: str):
    mat = bpy.data.materials.get(name)
    if mat is None:
        fail(f'找不到材质 "{name}"')
    return mat


def modifier_state(obj, modifier_name: str, applied: bool) -> None:
    names = [m.name for m in obj.modifiers]
    if applied:
        if modifier_name in names:
            fail(f'修改器 "{modifier_name}" 应已应用并从栈中移除')
    elif modifier_name not in names:
        fail(f'修改器 "{modifier_name}" 不在对象 "{obj.name}" 上')


def scene_empty() -> None:
    left = list(bpy.data.objects)
    if left:
        fail(f"场景应已清空，仍有 {len(left)} 个对象")


def color_close(actual: Iterable[float], expected: Iterable[float], label: str = "color") -> None:
    a = [float(x) for x in actual]
    b = [float(x) for x in expected]
    n = min(len(a), len(b), 3)
    vec_close(a[:n], b[:n], label)


def faces_count(name: str) -> int:
    return len(mesh_alive(name).data.polygons)


def faces_decreased(name: str, before: int) -> int:
    after = faces_count(name)
    if after > before:
        fail(f'网格 "{name}" 面数应减少或持平（{before} → {after}）')
    return after


def list_matches_scene(items: list[dict[str, Any]]) -> None:
    live = [obj.name for obj in bpy.context.scene.objects]
    names = [str(item.get("name", "")) for item in items]
    if len(items) != len(live):
        fail(f"列表数量 {len(items)} 与场景物体数 {len(live)} 不一致")
    if sorted(names) != sorted(live):
        fail(f"列表物体名与场景不一致：期望 {live}，实际 {names}")
    for name in names:
        object_exists(name)
