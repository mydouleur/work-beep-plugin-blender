from typing import Any

import bpy

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

    return {
        "name": material.name,
        "created": True,
    }


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

    return {
        "name": material.name,
        "color": list(color),
    }


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

    return {
        "object": obj.name,
        "material": material.name,
        "assigned": True,
    }