from typing import Any

import check
from registry import command


def _get_object(object_name: str):
    """Find a Blender object by name or raise a clear error."""
    import bpy

    obj = bpy.data.objects.get(object_name)

    if obj is None:
        raise ValueError(f'Object "{object_name}" was not found.')

    return obj


def _read_vector3(
    params: dict[str, Any],
    key: str,
    default: list[float],
) -> tuple[float, float, float]:
    """
    Read a three-number vector from command parameters.
    """
    value = params.get(key, default)

    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(
            f'"{key}" must be an array containing exactly three numbers.'
        )

    try:
        return (
            float(value[0]),
            float(value[1]),
            float(value[2]),
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            f'Every value in "{key}" must be numeric.'
        ) from error


@command("object.add_plane")
def add_plane(params: dict[str, Any]) -> dict[str, Any]:
    """
    Add a plane to the Blender scene.

    Input example:
        {
            "name": "Floor",
            "size": 10,
            "location": [0, 0, 0]
        }
    """
    import bpy

    size = float(params.get("size", 2.0))
    location = _read_vector3(
        params=params,
        key="location",
        default=[0.0, 0.0, 0.0],
    )

    if size <= 0:
        raise ValueError('"size" must be greater than zero.')

    bpy.ops.mesh.primitive_plane_add(
        size=size,
        location=location,
    )

    obj = bpy.context.active_object

    if obj is None:
        raise RuntimeError("Blender did not create the plane.")

    requested_name = params.get("name")

    if requested_name is not None:
        requested_name = str(requested_name).strip()

        if not requested_name:
            raise ValueError('"name" cannot be empty.')

        obj.name = requested_name

    check.mesh_alive(obj.name)
    check.vec_close(obj.location, location, "location")
    return check.stamp({
        "name": obj.name,
        "type": obj.type,
        "size": size,
        "location": [float(value) for value in obj.location],
    })


@command("object.move")
def move_object(params: dict[str, Any]) -> dict[str, Any]:
    """
    Move an existing object to an absolute location.

    Input example:
        {
            "name": "Floor",
            "location": [2, 0, 1]
        }
    """
    object_name = str(params.get("name", "")).strip()

    if not object_name:
        raise ValueError('"name" is required.')

    if "location" not in params:
        raise ValueError('"location" is required.')

    location = _read_vector3(
        params=params,
        key="location",
        default=[0.0, 0.0, 0.0],
    )

    obj = _get_object(object_name)
    obj.location = location
    check.vec_close(obj.location, location, "location")
    return check.stamp({
        "name": obj.name,
        "location": [float(value) for value in obj.location],
    })


@command("object.delete")
def delete_object(params: dict[str, Any]) -> dict[str, Any]:
    """
    Delete an object by name.

    Input example:
        {
            "name": "Floor"
        }
    """
    import bpy

    object_name = str(params.get("name", "")).strip()

    if not object_name:
        raise ValueError('"name" is required.')

    obj = _get_object(object_name)
    actual_name = obj.name
    object_type = obj.type

    bpy.data.objects.remove(obj, do_unlink=True)
    check.object_gone(actual_name)
    return check.stamp({
        "deleted": True,
        "name": actual_name,
        "type": object_type,
    })


@command("object.add_cube")
def add_cube(params: dict[str, Any]) -> dict[str, Any]:
    """Add a cube to the Blender scene."""
    import bpy

    size = float(params.get("size", 2.0))
    location = _read_vector3(
        params=params,
        key="location",
        default=[0.0, 0.0, 0.0],
    )

    if size <= 0:
        raise ValueError('"size" must be greater than zero.')

    bpy.ops.mesh.primitive_cube_add(
        size=size,
        location=location,
    )

    obj = bpy.context.active_object

    if obj is None:
        raise RuntimeError("Blender did not create the cube.")

    requested_name = params.get("name")

    if requested_name is not None:
        requested_name = str(requested_name).strip()

        if not requested_name:
            raise ValueError('"name" cannot be empty.')

        obj.name = requested_name

    check.mesh_alive(obj.name)
    check.vec_close(obj.location, location, "location")
    return check.stamp({
        "name": obj.name,
        "type": obj.type,
        "size": size,
        "location": [float(value) for value in obj.location],
    })


@command("object.add_cylinder")
def add_cylinder(params: dict[str, Any]) -> dict[str, Any]:
    """Add a cylinder to the Blender scene."""
    import bpy

    radius = float(params.get("radius", 1.0))
    depth = float(params.get("depth", 2.0))
    vertices = int(params.get("vertices", 32))
    location = _read_vector3(
        params=params,
        key="location",
        default=[0.0, 0.0, 0.0],
    )

    if radius <= 0:
        raise ValueError('"radius" must be greater than zero.')

    if depth <= 0:
        raise ValueError('"depth" must be greater than zero.')

    if vertices < 3:
        raise ValueError('"vertices" must be at least 3.')

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=location,
    )

    obj = bpy.context.active_object

    if obj is None:
        raise RuntimeError("Blender did not create the cylinder.")

    requested_name = params.get("name")

    if requested_name is not None:
        requested_name = str(requested_name).strip()

        if not requested_name:
            raise ValueError('"name" cannot be empty.')

        obj.name = requested_name

    check.mesh_alive(obj.name)
    check.vec_close(obj.location, location, "location")
    return check.stamp({
        "name": obj.name,
        "type": obj.type,
        "radius": radius,
        "depth": depth,
        "vertices": vertices,
        "location": [float(value) for value in obj.location],
    })


@command("object.add_uv_sphere")
def add_uv_sphere(params: dict[str, Any]) -> dict[str, Any]:
    """Add a UV sphere to the Blender scene."""
    import bpy

    radius = float(params.get("radius", 1.0))
    segments = int(params.get("segments", 32))
    ring_count = int(params.get("ring_count", 16))
    location = _read_vector3(
        params=params,
        key="location",
        default=[0.0, 0.0, 0.0],
    )

    if radius <= 0:
        raise ValueError('"radius" must be greater than zero.')

    if segments < 3:
        raise ValueError('"segments" must be at least 3.')

    if ring_count < 3:
        raise ValueError('"ring_count" must be at least 3.')

    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=ring_count,
        radius=radius,
        location=location,
    )

    obj = bpy.context.active_object

    if obj is None:
        raise RuntimeError("Blender did not create the UV sphere.")

    requested_name = params.get("name")

    if requested_name is not None:
        requested_name = str(requested_name).strip()

        if not requested_name:
            raise ValueError('"name" cannot be empty.')

        obj.name = requested_name

    check.mesh_alive(obj.name)
    check.vec_close(obj.location, location, "location")
    return check.stamp({
        "name": obj.name,
        "type": obj.type,
        "radius": radius,
        "segments": segments,
        "ring_count": ring_count,
        "location": [float(value) for value in obj.location],
    })


@command("object.rotate")
def rotate_object(params: dict[str, Any]) -> dict[str, Any]:
    """
    Set an object's absolute Euler rotation in degrees.

    Input example:
        {
            "name": "Cube",
            "rotation": [0, 0, 90]
        }
    """
    import math

    object_name = str(params.get("name", "")).strip()

    if not object_name:
        raise ValueError('"name" is required.')

    if "rotation" not in params:
        raise ValueError('"rotation" is required.')

    rotation_degrees = _read_vector3(
        params=params,
        key="rotation",
        default=[0.0, 0.0, 0.0],
    )

    obj = _get_object(object_name)

    obj.rotation_euler = tuple(
        math.radians(value)
        for value in rotation_degrees
    )

    check.object_exists(obj.name)
    check.vec_close(
        obj.rotation_euler,
        [math.radians(v) for v in rotation_degrees],
        "rotation",
    )
    return check.stamp({
        "name": obj.name,
        "rotation_degrees": list(rotation_degrees),
        "rotation_radians": [
            float(value)
            for value in obj.rotation_euler
        ],
    })


@command("object.scale")
def scale_object(params: dict[str, Any]) -> dict[str, Any]:
    """
    Set an object's absolute XYZ scale.

    Input example:
        {
            "name": "Cube",
            "scale": [2, 1, 0.5]
        }
    """
    object_name = str(params.get("name", "")).strip()

    if not object_name:
        raise ValueError('"name" is required.')

    if "scale" not in params:
        raise ValueError('"scale" is required.')

    scale = _read_vector3(
        params=params,
        key="scale",
        default=[1.0, 1.0, 1.0],
    )

    if any(value <= 0 for value in scale):
        raise ValueError(
            'Every value in "scale" must be greater than zero.'
        )

    obj = _get_object(object_name)
    obj.scale = scale
    check.vec_close(obj.scale, scale, "scale")
    return check.stamp({
        "name": obj.name,
        "scale": [float(value) for value in obj.scale],
    })


@command("object.duplicate")
def duplicate_object(params: dict[str, Any]) -> dict[str, Any]:
    """
    Duplicate an existing object.

    Input example:
        {
            "name": "Cube",
            "new_name": "CubeCopy",
            "location": [3, 0, 0]
        }
    """
    import bpy

    object_name = str(params.get("name", "")).strip()

    if not object_name:
        raise ValueError('"name" is required.')

    source = _get_object(object_name)

    duplicate = source.copy()

    # Mesh data is copied as well so the new object can be edited independently.
    if source.data is not None:
        duplicate.data = source.data.copy()

    bpy.context.collection.objects.link(duplicate)

    requested_name = params.get("new_name")

    if requested_name is not None:
        requested_name = str(requested_name).strip()

        if not requested_name:
            raise ValueError('"new_name" cannot be empty.')

        duplicate.name = requested_name

    requested_location = None
    if "location" in params:
        requested_location = _read_vector3(
            params=params,
            key="location",
            default=[
                float(value)
                for value in source.location
            ],
        )
        duplicate.location = requested_location

    check.object_exists(source.name)
    check.object_exists(duplicate.name)
    if source.name == duplicate.name:
        check.fail("复制对象与源对象同名")
    if requested_location is not None:
        check.vec_close(duplicate.location, requested_location, "location")
    return check.stamp({
        "source": source.name,
        "name": duplicate.name,
        "location": [
            float(value)
            for value in duplicate.location
        ],
        "rotation": [
            float(value)
            for value in duplicate.rotation_euler
        ],
        "scale": [
            float(value)
            for value in duplicate.scale
        ],
    })