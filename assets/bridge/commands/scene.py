from typing import Any

import check
from registry import command

from .material import SEMANTIC_GROUP_PROP, SEMANTIC_MATERIAL_PROP

# 同组颜色差超过它算不一致；不同组颜色差小于它算难以区分（RGB 欧氏距离，0~1 色域）
SAME_GROUP_COLOR_EPS = 0.05
DISTINCT_GROUP_COLOR_MIN = 0.25

_visibility_snapshot: dict[str, dict[str, bool]] | None = None


@command("scene.clear")
def clear_scene(params: dict[str, Any]) -> dict[str, Any]:
    """
    Delete all objects from the current Blender scene.

    Input:
        {}

    Output:
        {
            "deleted_count": 3
        }
    """
    import bpy

    global _visibility_snapshot

    objects = list(bpy.data.objects)
    deleted_count = len(objects)

    # Remove objects directly from Blender data.
    # do_unlink=True also removes them from their collections.
    for obj in objects:
        bpy.data.objects.remove(obj, do_unlink=True)

    # 快照里的物体已全部删除，留着会让之后同名新物体被错误恢复成旧可见性
    snapshot_cleared = _visibility_snapshot is not None
    _visibility_snapshot = None

    check.scene_empty()
    return check.stamp({
        "deleted_count": deleted_count,
        "visibility_snapshot_cleared": snapshot_cleared,
    })


@command("scene.list_objects")
def list_objects(params: dict[str, Any]) -> dict[str, Any]:
    """
    Return information about all objects in the current scene.

    Input:
        {}

    Output:
        {
            "count": 2,
            "objects": [
                {
                    "name": "Cube",
                    "type": "MESH",
                    "location": [0, 0, 0],
                    "rotation": [0, 0, 0],
                    "scale": [1, 1, 1]
                }
            ]
        }
    """
    import bpy

    objects: list[dict[str, Any]] = []

    for obj in bpy.context.scene.objects:
        objects.append(
            {
                "name": obj.name,
                "type": obj.type,
                "location": [float(value) for value in obj.location],
                "rotation": [float(value) for value in obj.rotation_euler],
                "scale": [float(value) for value in obj.scale],
                "visible": not obj.hide_viewport,
            }
        )

    check.list_matches_scene(objects)
    return check.stamp({
        "count": len(objects),
        "objects": objects,
    })

@command("scene.list_hierarchy")
def list_hierarchy(params: dict[str, Any]) -> dict[str, Any]:
    """
    Return the parent/child hierarchy and visibility state of objects
    in the current Blender scene.

    Input:
        {}

    Output:
        {
            "count": 3,
            "objects": [
                {
                    "name": "Chair",
                    "type": "EMPTY",
                    "parent": None,
                    "children": ["Seat", "Back"],
                    "visible": True
                }
            ]
        }
    """
    import bpy

    objects: list[dict[str, Any]] = []

    for obj in bpy.context.scene.objects:
        objects.append(
            {
                "name": obj.name,
                "type": obj.type,
                "parent": obj.parent.name if obj.parent else None,
                "children": [child.name for child in obj.children],
                "visible": not obj.hide_viewport,
            }
        )

    return check.stamp({
        "count": len(objects),
        "objects": objects,
    })



def _material_color(material) -> list[float] | None:
    if material is None:
        return None
    color = material.diffuse_color
    if material.use_nodes and material.node_tree is not None:
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is not None:
            color = principled.inputs["Base Color"].default_value
    return [round(float(v), 4) for v in color]


def _color_distance(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])) ** 0.5


@command("scene.semantic_inspect")
def semantic_inspect(params: dict[str, Any]) -> dict[str, Any]:
    """
    Read the current object → semantic group → material → color mapping
    and report deterministic consistency issues.

    Labels are the agent's own claims; this command only reports what the
    scene contains and where labels/colors contradict each other.
    """
    import bpy

    objects: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for obj in bpy.context.scene.objects:
        raw_group = obj.get(SEMANTIC_GROUP_PROP)
        group = str(raw_group).strip() if raw_group not in (None, "") else None
        material = obj.active_material if obj.data is not None and hasattr(obj.data, "materials") else None
        recorded = obj.get(SEMANTIC_MATERIAL_PROP)

        objects.append({
            "name": obj.name,
            "type": obj.type,
            "semantic_group": group,
            "material": material.name if material else None,
            "color": _material_color(material),
            "parent": obj.parent.name if obj.parent else None,
            "visible": not obj.hide_viewport and not obj.hide_render,
            "location": [round(float(v), 4) for v in obj.matrix_world.translation],
            "dimensions": [round(float(v), 4) for v in obj.dimensions],
        })

        if group is None:
            continue
        if material is None:
            issues.append({
                "code": "label_missing_material",
                "severity": "critical",
                "objects": [obj.name],
                "message": f'"{obj.name}" 标为 {group}，但没有材质（材质被删除或槽位为空）',
            })
        elif recorded and material.name != str(recorded):
            issues.append({
                "code": "label_material_changed",
                "severity": "warning",
                "objects": [obj.name],
                "message": f'"{obj.name}" 标为 {group} 时用的是 {recorded}，现在是 {material.name}',
            })

    groups: dict[str, dict[str, Any]] = {}
    for item in objects:
        group = item["semantic_group"]
        if group is None:
            continue
        entry = groups.setdefault(group, {"group": group, "objects": [], "materials": [], "colors": []})
        entry["objects"].append(item["name"])
        if item["material"] and item["material"] not in entry["materials"]:
            entry["materials"].append(item["material"])
        color = item["color"]
        if color is not None and all(_color_distance(color, c) > SAME_GROUP_COLOR_EPS for c in entry["colors"]):
            entry["colors"].append(color)

    for entry in groups.values():
        if len(entry["colors"]) > 1:
            issues.append({
                "code": "group_color_inconsistent",
                "severity": "critical",
                "objects": entry["objects"],
                "message": f'语义组 {entry["group"]} 内颜色不一致：{entry["colors"]}',
            })

    names = list(groups)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            a, b = groups[first]["colors"], groups[second]["colors"]
            if not a or not b:
                continue
            if _color_distance(a[0], b[0]) < DISTINCT_GROUP_COLOR_MIN:
                issues.append({
                    "code": "groups_share_color",
                    "severity": "critical",
                    "objects": groups[first]["objects"] + groups[second]["objects"],
                    "message": f"语义组 {first} 与 {second} 颜色过于接近，无法靠颜色区分",
                })

    annotated = bool(groups)
    unlabeled = [
        item["name"] for item in objects
        if annotated and item["type"] == "MESH" and item["visible"] and item["semantic_group"] is None
    ]
    if unlabeled:
        issues.append({
            "code": "unlabeled_meshes",
            "severity": "warning",
            "objects": unlabeled,
            "message": f"以下可见网格没有语义标签：{', '.join(unlabeled)}",
        })

    check.list_matches_scene(objects)
    return check.stamp({
        "annotated": annotated,
        "object_count": len(objects),
        "objects": objects,
        "groups": list(groups.values()),
        "issues": issues,
    })


@command("scene.isolate_objects")
def isolate_objects(params: dict[str, Any]) -> dict[str, Any]:
    """
    Temporarily isolate a set of objects.

    The selected objects remain visible. Other scene objects are hidden.
    The original visibility state is saved so it can later be restored.

    Input:
        {
            "names": ["Seat", "Back"]
        }
    """
    import bpy

    global _visibility_snapshot

    names = params.get("names")

    if not isinstance(names, list) or not names:
        raise ValueError("names must be a non-empty list")

    requested = set(names)

    missing = [
        name for name in requested
        if bpy.data.objects.get(name) is None
    ]

    if missing:
        raise ValueError(
            f"Objects not found: {', '.join(sorted(missing))}"
        )

    # Only take the snapshot when isolation starts.
    # Repeated isolate calls should keep the original state so that
    # restore_visibility can return to the state before isolation.
    if _visibility_snapshot is None:
        _visibility_snapshot = {
            obj.name: {
                "hide_viewport": bool(obj.hide_viewport),
                "hide_render": bool(obj.hide_render),
            }
            for obj in bpy.context.scene.objects
        }

    visible: list[str] = []
    hidden: list[str] = []

    for obj in bpy.context.scene.objects:
        should_show = obj.name in requested

        obj.hide_viewport = not should_show
        obj.hide_render = not should_show

        if should_show:
            visible.append(obj.name)
        else:
            hidden.append(obj.name)

    return check.stamp({
        "isolated": visible,
        "hidden": hidden,
        "isolated_count": len(visible),
        "hidden_count": len(hidden),
    })

@command("scene.isolate_hierarchy")
def isolate_hierarchy(params: dict[str, Any]) -> dict[str, Any]:
    """
    Temporarily isolate one object hierarchy.

    The root object and all of its descendants remain visible.
    Other scene objects are hidden.

    Input:
        {
            "root": "Chair"
        }
    """
    import bpy

    global _visibility_snapshot

    root_name = params.get("root")

    if not isinstance(root_name, str) or not root_name.strip():
        raise ValueError("root must be a non-empty string")

    root = bpy.data.objects.get(root_name)

    if root is None:
        raise ValueError(f"Object not found: {root_name}")

    # Traverse the complete descendant hierarchy.
    hierarchy: list = []
    stack = [root]

    while stack:
        obj = stack.pop()
        hierarchy.append(obj)
        stack.extend(list(obj.children))

    hierarchy_names = {obj.name for obj in hierarchy}

    # Preserve the visibility state from before isolation.
    if _visibility_snapshot is None:
        _visibility_snapshot = {
            obj.name: {
                "hide_viewport": bool(obj.hide_viewport),
                "hide_render": bool(obj.hide_render),
            }
            for obj in bpy.context.scene.objects
        }

    visible: list[str] = []
    hidden: list[str] = []

    for obj in bpy.context.scene.objects:
        should_show = obj.name in hierarchy_names

        obj.hide_viewport = not should_show
        obj.hide_render = not should_show

        if should_show:
            visible.append(obj.name)
        else:
            hidden.append(obj.name)

    return check.stamp({
        "root": root.name,
        "isolated": visible,
        "hidden": hidden,
        "isolated_count": len(visible),
        "hidden_count": len(hidden),
    })

@command("scene.restore_visibility")
def restore_visibility(params: dict[str, Any]) -> dict[str, Any]:
    """
    Restore the visibility state saved before the first
    scene.isolate_objects / scene.isolate_hierarchy call.
    scene.clear discards the snapshot.

    Input:
        {}
    """
    import bpy

    global _visibility_snapshot

    if _visibility_snapshot is None:
        return check.stamp({
            "restored": False,
            "restored_count": 0,
            "message": "No saved visibility state.",
        })

    restored: list[str] = []

    for name, state in _visibility_snapshot.items():
        obj = bpy.data.objects.get(name)

        # Object may have been deleted while editing.
        if obj is None:
            continue

        obj.hide_viewport = state["hide_viewport"]
        obj.hide_render = state["hide_render"]
        restored.append(name)

    _visibility_snapshot = None

    return check.stamp({
        "restored": True,
        "restored_count": len(restored),
        "objects": restored,
    })