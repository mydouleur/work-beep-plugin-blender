from typing import Any

import bpy

import check
from registry import command


def _get_object(name: str):
    obj = bpy.data.objects.get(name)

    if obj is None:
        raise ValueError(f'Object "{name}" was not found.')

    return obj


def _get_material(name: str):
    material = bpy.data.materials.get(name)

    if material is None:
        raise ValueError(f'Material "{name}" was not found.')

    return material


def _read_color(params: dict[str, Any], key: str):
    value = params.get(key)

    if not isinstance(value, (list, tuple)) or len(value) not in {3, 4}:
        raise ValueError(
            f'"{key}" must be [R, G, B] or [R, G, B, A].'
        )

    values = [float(v) for v in value]

    if len(values) == 3:
        values.append(1.0)

    if any(v < 0 or v > 1 for v in values):
        raise ValueError(
            f'Every value in "{key}" must be between 0 and 1.'
        )

    return tuple(values)


@command("material.create")
def create_material(params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name", "")).strip()

    if not name:
        raise ValueError('"name" is required.')

    if bpy.data.materials.get(name):
        raise ValueError(f'Material "{name}" already exists.')

    material = bpy.data.materials.new(name=name)
    material.use_nodes = True

    check.material_exists(material.name)
    return check.stamp({
        "name": material.name,
        "created": True,
    })


@command("material.set_base_color")
def set_base_color(params: dict[str, Any]) -> dict[str, Any]:
    material_name = str(params.get("name", "")).strip()

    if not material_name:
        raise ValueError('"name" is required.')

    color = _read_color(params, "color")

    material = _get_material(material_name)
    material.diffuse_color = color

    material.use_nodes = True

    principled = material.node_tree.nodes.get("Principled BSDF")

    if principled is not None:
        principled.inputs["Base Color"].default_value = color
        check.color_close(principled.inputs["Base Color"].default_value, color)
    else:
        check.color_close(material.diffuse_color, color)

    check.material_exists(material.name)
    return check.stamp({
        "name": material.name,
        "color": list(color),
    })


@command("material.assign")
def assign_material(params: dict[str, Any]) -> dict[str, Any]:
    object_name = str(params.get("object", "")).strip()
    material_name = str(params.get("material", "")).strip()

    if not object_name:
        raise ValueError('"object" is required.')

    if not material_name:
        raise ValueError('"material" is required.')

    obj = _get_object(object_name)
    material = _get_material(material_name)

    if material.name not in [m.name for m in obj.data.materials if m]:
        obj.data.materials.append(material)

    obj.active_material = material

    check.object_exists(obj.name)
    check.material_exists(material.name)
    if obj.active_material is None or obj.active_material.name != material.name:
        check.fail(f'物体 "{obj.name}" 的活动材质应为 "{material.name}"')
    slot_names = [m.name for m in obj.data.materials if m]
    if material.name not in slot_names:
        check.fail(f'材质 "{material.name}" 不在物体 "{obj.name}" 的材质槽中')
    return check.stamp({
        "object": obj.name,
        "material": material.name,
        "assigned": True,
    })


# 语义标签存在物体自定义属性上：随物体改名保留、随物体删除消失、可存进 .blend
SEMANTIC_GROUP_PROP = "beep_semantic_group"
SEMANTIC_MATERIAL_PROP = "beep_semantic_material"


def _apply_base_color(material, color) -> None:
    # Workbench 的 MATERIAL 着色读 diffuse_color，EEVEE/Cycles 读 Principled Base Color，两处都写
    material.diffuse_color = color
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is not None:
        principled.inputs["Base Color"].default_value = color


@command("material.assign_semantic")
def assign_semantic(params: dict[str, Any]) -> dict[str, Any]:
    """
    Batch-assign semantic groups and colors.

    Input example:
        {
            "groups": [
                {"group": "Seat", "color": [0.9, 0.2, 0.2], "objects": ["Seat"]},
                {"group": "Legs", "color": [0.2, 0.8, 0.3],
                 "objects": ["Leg_FL", "Leg_FR", "Leg_BL", "Leg_BR"]}
            ]
        }

    Every listed object gets exactly one material slot (Semantic_<group>
    unless "material" is given) and the custom property beep_semantic_group.
    All input is validated before the scene is changed.
    """
    groups = params.get("groups")

    if not isinstance(groups, list) or not groups:
        raise ValueError('"groups" must be a non-empty array.')

    owner_by_object: dict[str, str] = {}
    owner_by_data: dict[str, str] = {}
    material_names: set[str] = set()
    parsed = []

    for raw in groups:
        if not isinstance(raw, dict):
            raise ValueError('Every item in "groups" must be an object.')

        group = str(raw.get("group", "")).strip()
        if not group:
            raise ValueError('"group" cannot be empty.')
        if any(item[0] == group for item in parsed):
            raise ValueError(f'Semantic group "{group}" is listed twice.')

        color = _read_color(raw, "color")

        material_name = str(raw.get("material") or f"Semantic_{group}").strip()
        if material_name in material_names:
            raise ValueError(f'Material "{material_name}" is used by two groups.')
        material_names.add(material_name)

        names = raw.get("objects")
        if not isinstance(names, list) or not names:
            raise ValueError(f'Group "{group}" needs a non-empty "objects" array.')

        objects = []
        for name in names:
            obj = _get_object(str(name).strip())
            if obj.name in owner_by_object:
                raise ValueError(
                    f'Object "{obj.name}" is listed in both '
                    f'"{owner_by_object[obj.name]}" and "{group}".'
                )
            if obj.data is None or not hasattr(obj.data, "materials"):
                raise ValueError(
                    f'Object "{obj.name}" ({obj.type}) cannot hold materials.'
                )
            # 共享网格数据的两个物体只能有同一组材质，分到不同组会互相覆盖
            data_owner = owner_by_data.get(obj.data.name)
            if data_owner is not None and data_owner != group:
                raise ValueError(
                    f'Object "{obj.name}" shares mesh data with an object in '
                    f'"{data_owner}"; duplicate it before assigning another group.'
                )
            owner_by_object[obj.name] = group
            owner_by_data[obj.data.name] = group
            objects.append(obj)

        parsed.append((group, color, material_name, objects))

    results = []
    for group, color, material_name, objects in parsed:
        material = bpy.data.materials.get(material_name)
        if material is None:
            material = bpy.data.materials.new(name=material_name)
        _apply_base_color(material, color)

        for obj in objects:
            obj.data.materials.clear()
            obj.data.materials.append(material)
            obj[SEMANTIC_GROUP_PROP] = group
            obj[SEMANTIC_MATERIAL_PROP] = material.name

        check.material_exists(material.name)
        check.color_close(material.diffuse_color, color)
        for obj in objects:
            if obj.active_material is None or obj.active_material.name != material.name:
                check.fail(f'物体 "{obj.name}" 的材质应为 "{material.name}"')
            if obj.get(SEMANTIC_GROUP_PROP) != group:
                check.fail(f'物体 "{obj.name}" 的语义组应为 "{group}"')

        results.append({
            "group": group,
            "material": material.name,
            "color": [round(float(v), 4) for v in color],
            "objects": [obj.name for obj in objects],
        })

    return check.stamp({
        "groups": results,
        "group_count": len(results),
        "object_count": sum(len(item["objects"]) for item in results),
    })