from typing import Any

import bpy

import check
from registry import command


def _read_vector3(
    params: dict[str, Any],
    key: str,
    default: list[float],
):
    value = params.get(key, default)

    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(
            f'"{key}" must contain exactly three numbers.'
        )

    return (
        float(value[0]),
        float(value[1]),
        float(value[2]),
    )


def _get_light(name: str):
    obj = bpy.data.objects.get(name)

    if obj is None:
        raise ValueError(f'Light "{name}" was not found.')

    if obj.type != "LIGHT":
        raise ValueError(f'Object "{name}" is not a light.')

    return obj


@command("light.add")
def add_light(params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name", "Light")).strip()
    light_type = str(
        params.get("type", "POINT")
    ).strip().upper()

    if light_type not in {"POINT", "SUN", "SPOT", "AREA"}:
        raise ValueError(
            '"type" must be POINT, SUN, SPOT, or AREA.'
        )

    location = _read_vector3(
        params,
        "location",
        [4.0, 4.0, 6.0],
    )

    bpy.ops.object.light_add(
        type=light_type,
        location=location,
    )

    obj = bpy.context.active_object

    if obj is None:
        raise RuntimeError("Blender did not create the light.")

    obj.name = name

    energy = float(params.get("energy", 1000.0))

    if energy < 0:
        raise ValueError('"energy" cannot be negative.')

    obj.data.energy = energy

    check.object_exists(obj.name, "LIGHT")
    check.vec_close(obj.location, location, "location")
    if obj.data.type != light_type:
        check.fail(f'灯光类型应为 {light_type}，实际 {obj.data.type}')
    if abs(float(obj.data.energy) - energy) > 1e-3:
        check.fail(f'灯光能量不符：期望 {energy}，实际 {obj.data.energy}')
    return check.stamp({
        "name": obj.name,
        "type": light_type,
        "location": list(location),
        "energy": energy,
    })


@command("light.set_energy")
def set_light_energy(params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name", "")).strip()

    if not name:
        raise ValueError('"name" is required.')

    energy = float(params.get("energy", 1000.0))

    if energy < 0:
        raise ValueError('"energy" cannot be negative.')

    light = _get_light(name)
    light.data.energy = energy
    check.object_exists(light.name, "LIGHT")
    if abs(float(light.data.energy) - energy) > 1e-3:
        check.fail(f'灯光能量不符：期望 {energy}，实际 {light.data.energy}')
    return check.stamp({
        "name": light.name,
        "energy": float(light.data.energy),
    })


@command("light.set_color")
def set_light_color(params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name", "")).strip()

    if not name:
        raise ValueError('"name" is required.')

    color = params.get("color")

    if not isinstance(color, (list, tuple)) or len(color) != 3:
        raise ValueError(
            '"color" must be [R, G, B].'
        )

    rgb = tuple(float(v) for v in color)

    if any(v < 0 or v > 1 for v in rgb):
        raise ValueError(
            'Every value in "color" must be between 0 and 1.'
        )

    light = _get_light(name)
    light.data.color = rgb
    check.object_exists(light.name, "LIGHT")
    check.color_close(light.data.color, rgb)
    return check.stamp({
        "name": light.name,
        "color": list(rgb),
    })