from typing import Any
import math

import bpy
from mathutils import Vector

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


def _get_camera(name: str):
    obj = bpy.data.objects.get(name)

    if obj is None:
        raise ValueError(f'Camera "{name}" was not found.')

    if obj.type != "CAMERA":
        raise ValueError(f'Object "{name}" is not a camera.')

    return obj


@command("camera.add")
def add_camera(params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name", "Camera")).strip()

    location = _read_vector3(
        params,
        "location",
        [7.0, -7.0, 5.0],
    )

    bpy.ops.object.camera_add(location=location)

    obj = bpy.context.active_object

    if obj is None:
        raise RuntimeError("Blender did not create the camera.")

    obj.name = name

    lens = float(params.get("lens", 50.0))

    if lens <= 0:
        raise ValueError('"lens" must be greater than zero.')

    obj.data.lens = lens

    set_active = bool(params.get("set_active", True))
    if set_active:
        bpy.context.scene.camera = obj

    check.object_exists(obj.name, "CAMERA")
    check.vec_close(obj.location, location, "location")
    if abs(float(obj.data.lens) - lens) > 1e-3:
        check.fail(f'镜头焦距不符：期望 {lens}，实际 {obj.data.lens}')
    if set_active and bpy.context.scene.camera != obj:
        check.fail(f'场景活动相机应为 "{obj.name}"')
    return check.stamp({
        "name": obj.name,
        "location": list(location),
        "lens": lens,
        "active": bpy.context.scene.camera == obj,
    })


@command("camera.look_at")
def camera_look_at(params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name", "")).strip()

    if not name:
        raise ValueError('"name" is required.')

    target = _read_vector3(
        params,
        "target",
        [0.0, 0.0, 0.0],
    )

    camera = _get_camera(name)

    direction = Vector(target) - camera.location

    if direction.length == 0:
        raise ValueError(
            "Camera and target cannot have the same location."
        )

    camera.rotation_euler = direction.to_track_quat(
        "-Z",
        "Y",
    ).to_euler()

    expected = (Vector(target) - camera.location).to_track_quat(
        "-Z",
        "Y",
    ).to_euler()
    check.object_exists(camera.name, "CAMERA")
    check.vec_close(camera.rotation_euler, expected, "rotation")
    return check.stamp({
        "name": camera.name,
        "target": list(target),
        "rotation": [
            math.degrees(v)
            for v in camera.rotation_euler
        ],
    })