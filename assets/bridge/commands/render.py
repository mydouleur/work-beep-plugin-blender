"""多视图 2D 出图 + 文件验收：3D 物体 → 正交相机 → PNG。

Validation：每张图必须存在、非空、PNG 头合法；批次缺一张即失败（抛错，Host 回灌模型）。
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

import bpy
from mathutils import Vector

import check
from registry import command
from validate_png import validate_png

# 相机放在物体哪一侧（Blender：前视图从 -Y 看向原点）
VIEW_DIR = {
    "front": Vector((0.0, -1.0, 0.0)),
    "back": Vector((0.0, 1.0, 0.0)),
    "right": Vector((1.0, 0.0, 0.0)),
    "left": Vector((-1.0, 0.0, 0.0)),
    "top": Vector((0.0, 0.0, 1.0)),
    "bottom": Vector((0.0, 0.0, -1.0)),
}

DEFAULT_VIEWS = ("front", "right", "top", "back")


def _safe_name(name: str) -> str:
    keep = []
    for ch in name:
        keep.append(ch if ch.isalnum() or ch in "-_" else "_")
    return "".join(keep) or "object"


def _get_mesh_or_any(name: str):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f'找不到对象 "{name}"')
    return obj


def _world_bounds(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = Vector((
        min(c.x for c in corners),
        min(c.y for c in corners),
        min(c.z for c in corners),
    ))
    mx = Vector((
        max(c.x for c in corners),
        max(c.y for c in corners),
        max(c.z for c in corners),
    ))
    center = (mn + mx) * 0.5
    size = mx - mn
    span = max(size.x, size.y, size.z, 0.01)
    return center, span


def _visible_meshes():
    meshes = [
        obj for obj in bpy.context.scene.objects
        if obj.type == "MESH" and not obj.hide_viewport and not obj.hide_render
    ]
    if not meshes:
        raise ValueError("场景里没有可见网格")
    return meshes


def _union_world_bounds(objs):
    corners = []
    for obj in objs:
        corners.extend(obj.matrix_world @ Vector(c) for c in obj.bound_box)
    mn = Vector((
        min(c.x for c in corners),
        min(c.y for c in corners),
        min(c.z for c in corners),
    ))
    mx = Vector((
        max(c.x for c in corners),
        max(c.y for c in corners),
        max(c.z for c in corners),
    ))
    center = (mn + mx) * 0.5
    size = mx - mn
    span = max(size.x, size.y, size.z, 0.01)
    return center, span


def _pick_engine() -> str:
    current = bpy.context.scene.render.engine
    for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"):
        try:
            bpy.context.scene.render.engine = name
            return name
        except Exception:
            continue
    return current


def _place_ortho_camera(obj, view: str, center=None, span=None):
    if view not in VIEW_DIR:
        raise ValueError(f"未知视图: {view}（可选 {', '.join(VIEW_DIR)}）")
    if center is None or span is None:
        center, span = _world_bounds(obj)
    dist = span * 2.5
    cam_data = bpy.data.cameras.new("BeepViewCamData")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = span * 1.6
    cam_data.clip_end = max(dist * 4.0, 100.0)
    cam = bpy.data.objects.new("BeepViewCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = center + VIEW_DIR[view] * dist
    direction = center - cam.location
    if direction.length == 0:
        raise ValueError("相机与物体中心重合")
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return cam


def _render_one(obj, view: str, path: str, resolution: int, *, center=None, span=None, label: str | None = None) -> dict[str, Any]:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    scene = bpy.context.scene
    prev = {
        "engine": scene.render.engine,
        "filepath": scene.render.filepath,
        "res_x": scene.render.resolution_x,
        "res_y": scene.render.resolution_y,
        "pct": scene.render.resolution_percentage,
        "fmt": scene.render.image_settings.file_format,
        "camera": scene.camera,
    }
    cam = None
    try:
        cam = _place_ortho_camera(obj, view, center=center, span=span)
        scene.camera = cam
        scene.render.engine = _pick_engine()
        scene.render.resolution_x = resolution
        scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = path
        result = bpy.ops.render.render(write_still=True)
        if "FINISHED" not in result:
            raise RuntimeError(f"渲染未完成: {result}")
    finally:
        scene.render.engine = prev["engine"]
        scene.render.filepath = prev["filepath"]
        scene.render.resolution_x = prev["res_x"]
        scene.render.resolution_y = prev["res_y"]
        scene.render.resolution_percentage = prev["pct"]
        scene.render.image_settings.file_format = prev["fmt"]
        scene.camera = prev["camera"]
        if cam is not None:
            data = cam.data
            bpy.data.objects.remove(cam, do_unlink=True)
            if data is not None:
                bpy.data.cameras.remove(data)

    item = validate_png(path)
    item["view"] = view
    item["name"] = label or obj.name
    if not item["ok"]:
        raise RuntimeError(
            f"视图 {view} 验收失败: {item.get('error')}（{path}）"
        )
    return item


@command("render.view")
def render_view(params: dict[str, Any]) -> dict[str, Any]:
    """渲一张正交视图 PNG，并做文件验收。"""
    name = str(params.get("name", "")).strip()
    view = str(params.get("view", "front")).strip().lower()
    if not name:
        raise ValueError("缺少参数 name")
    obj = _get_mesh_or_any(name)
    resolution = int(params.get("resolution", 512))
    if resolution < 64:
        raise ValueError("resolution 至少 64")
    out = str(params.get("path", "")).strip()
    if not out:
        folder = tempfile.mkdtemp(prefix="beep-view-")
        out = os.path.join(folder, f"{_safe_name(obj.name)}_{view}.png")
    return check.stamp(_render_one(obj, view, out, resolution))


@command("render.views")
def render_views(params: dict[str, Any]) -> dict[str, Any]:
    """按顺序渲多张正交视图（默认前/右/顶/后），全部验收通过才返回 ok。"""
    name = str(params.get("name", "")).strip()
    if not name:
        raise ValueError("缺少参数 name")
    obj = _get_mesh_or_any(name)
    raw = params.get("views")
    if raw is None:
        raw = list(DEFAULT_VIEWS)
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError("views 必须是非空数组")
    views = [str(v).strip().lower() for v in raw]
    for v in views:
        if v not in VIEW_DIR:
            raise ValueError(f"未知视图: {v}")
    resolution = int(params.get("resolution", 512))
    if resolution < 64:
        raise ValueError("resolution 至少 64")
    folder = str(params.get("output_dir", "")).strip()
    if not folder:
        folder = tempfile.mkdtemp(prefix="beep-views-")
    os.makedirs(folder, exist_ok=True)

    results = []
    failed = []
    for view in views:
        path = os.path.join(folder, f"{_safe_name(obj.name)}_{view}.png")
        try:
            results.append(_render_one(obj, view, path, resolution))
        except Exception as e:
            failed.append({"view": view, "path": path, "ok": False, "error": str(e)})

    payload = {
        "ok": len(failed) == 0 and len(results) == len(views),
        "name": obj.name,
        "output_dir": folder,
        "expected": views,
        "views": results,
        "failed": failed,
    }
    if not payload["ok"]:
        raise RuntimeError(
            "多视图验收未通过："
            + ",".join(f"{x['view']}({x.get('error', '')})" for x in failed)
        )
    return check.stamp(payload)


@command("render.scene_views")
def render_scene_views(params: dict[str, Any]) -> dict[str, Any]:
    """按场景里所有可见网格的联合包围盒渲正交图。多物体不必布尔合并。"""
    meshes = _visible_meshes()
    center, span = _union_world_bounds(meshes)
    raw = params.get("views")
    if raw is None:
        raw = ["front", "right", "top"]
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError("views 必须是非空数组")
    views = [str(v).strip().lower() for v in raw]
    for v in views:
        if v not in VIEW_DIR:
            raise ValueError(f"未知视图: {v}")
    resolution = int(params.get("resolution", 512))
    if resolution < 64:
        raise ValueError("resolution 至少 64")
    folder = str(params.get("output_dir", "")).strip()
    if not folder:
        folder = tempfile.mkdtemp(prefix="beep-scene-views-")
    os.makedirs(folder, exist_ok=True)

    results = []
    failed = []
    for view in views:
        path = os.path.join(folder, f"scene_{view}.png")
        try:
            results.append(_render_one(
                meshes[0],
                view,
                path,
                resolution,
                center=center,
                span=span,
                label="scene",
            ))
        except Exception as e:
            failed.append({"view": view, "path": path, "ok": False, "error": str(e)})

    payload = {
        "ok": len(failed) == 0 and len(results) == len(views),
        "name": "scene",
        "objects": [obj.name for obj in meshes],
        "output_dir": folder,
        "expected": views,
        "views": results,
        "failed": failed,
    }
    if not payload["ok"]:
        raise RuntimeError(
            "场景多视图验收未通过："
            + ",".join(f"{x['view']}({x.get('error', '')})" for x in failed)
        )
    return check.stamp(payload)


@command("render.validate_views")
def validate_views(params: dict[str, Any]) -> dict[str, Any]:
    """只验收已有 PNG，不再渲染。缺图或坏图则失败。"""
    folder = str(params.get("output_dir", "")).strip()
    name = str(params.get("name", "")).strip()
    if not folder:
        raise ValueError("缺少参数 output_dir")
    raw = params.get("views") or list(DEFAULT_VIEWS)
    views = [str(v).strip().lower() for v in raw]
    stem = _safe_name(name) if name else None
    checks = []
    for view in views:
        if stem:
            path = os.path.join(folder, f"{stem}_{view}.png")
        else:
            path = os.path.join(folder, f"{view}.png")
        item = validate_png(path)
        item["view"] = view
        checks.append(item)
    failed = [c for c in checks if not c["ok"]]
    payload = {
        "ok": len(failed) == 0,
        "output_dir": folder,
        "checks": checks,
        "failed": failed,
    }
    if not payload["ok"]:
        raise RuntimeError(
            "视图文件验收未通过："
            + ",".join(f"{x['view']}({x.get('error', '')})" for x in failed)
        )
    return check.stamp(payload)
