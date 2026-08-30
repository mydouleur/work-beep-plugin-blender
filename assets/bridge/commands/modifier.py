from typing import Any

import bpy

import check
from registry import command


def _get_mesh_object(name: str):
    """Find a mesh object by name."""

    obj = bpy.data.objects.get(name)

    if obj is None:
        raise ValueError(f'Object "{name}" was not found.')

    if obj.type != "MESH":
        raise ValueError(
            f'Object "{name}" must be a mesh object. '
            f"Found type: {obj.type}"
        )

    return obj


def _activate_object(obj) -> None:
    """Make an object active and selected."""

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")

    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _apply_modifier(obj, modifier_name: str) -> None:
    """Apply a modifier to an object."""

    _activate_object(obj)

    bpy.ops.object.modifier_apply(
        modifier=modifier_name
    )


@command("modifier.mirror")
def mirror_modifier(
    params: dict[str, Any]
) -> dict[str, Any]:
    """
    Add a Mirror modifier.

    Input example:
        {
            "name": "Cube",
            "axis": "X",
            "apply": false
        }
    """

    object_name = str(
        params.get("name", "")
    ).strip()

    if not object_name:
        raise ValueError('"name" is required.')

    axis = str(
        params.get("axis", "X")
    ).strip().upper()

    if axis not in {"X", "Y", "Z"}:
        raise ValueError(
            '"axis" must be X, Y, or Z.'
        )

    apply_modifier = bool(
        params.get("apply", False)
    )

    obj = _get_mesh_object(object_name)

    modifier = obj.modifiers.new(
        name="Agent Mirror",
        type="MIRROR",
    )

    modifier.use_axis[0] = axis == "X"
    modifier.use_axis[1] = axis == "Y"
    modifier.use_axis[2] = axis == "Z"

    modifier_name = modifier.name

    if apply_modifier:
        _apply_modifier(
            obj,
            modifier_name,
        )

    check.mesh_alive(obj.name)
    check.modifier_state(obj, modifier_name, apply_modifier)
    return check.stamp({
        "name": obj.name,
        "operation": "mirror",
        "axis": axis,
        "modifier": modifier_name,
        "applied": apply_modifier,
    })


@command("modifier.boolean")
def boolean_modifier(
    params: dict[str, Any]
) -> dict[str, Any]:
    """
    Apply a Boolean operation using another object.

    Input example:
        {
            "name": "Cube",
            "operand": "Cutter",
            "operation": "DIFFERENCE",
            "apply": true
        }
    """

    object_name = str(
        params.get("name", "")
    ).strip()

    operand_name = str(
        params.get("operand", "")
    ).strip()

    operation = str(
        params.get(
            "operation",
            "DIFFERENCE"
        )
    ).strip().upper()

    apply_modifier = bool(
        params.get("apply", True)
    )

    if not object_name:
        raise ValueError('"name" is required.')

    if not operand_name:
        raise ValueError(
            '"operand" is required.'
        )

    if operation not in {
        "DIFFERENCE",
        "UNION",
        "INTERSECT",
    }:
        raise ValueError(
            '"operation" must be DIFFERENCE, '
            "UNION, or INTERSECT."
        )

    obj = _get_mesh_object(object_name)
    operand = _get_mesh_object(operand_name)

    if obj == operand:
        raise ValueError(
            "Boolean object and operand "
            "must be different objects."
        )

    modifier = obj.modifiers.new(
        name="Agent Boolean",
        type="BOOLEAN",
    )

    modifier.operation = operation
    modifier.solver = "EXACT"
    modifier.object = operand

    modifier_name = modifier.name

    if apply_modifier:
        _apply_modifier(
            obj,
            modifier_name,
        )

    check.mesh_alive(obj.name)
    check.object_exists(operand.name, "MESH")
    check.modifier_state(obj, modifier_name, apply_modifier)
    return check.stamp({
        "name": obj.name,
        "operation": "boolean",
        "boolean_operation": operation,
        "operand": operand.name,
        "modifier": modifier_name,
        "applied": apply_modifier,
    })


@command("modifier.decimate")
def decimate_modifier(
    params: dict[str, Any]
) -> dict[str, Any]:
    """
    Reduce mesh polygon count.

    Input example:
        {
            "name": "HighPoly",
            "ratio": 0.5,
            "apply": true
        }
    """

    object_name = str(
        params.get("name", "")
    ).strip()

    if not object_name:
        raise ValueError('"name" is required.')

    ratio = float(
        params.get("ratio", 0.5)
    )

    if ratio <= 0 or ratio > 1:
        raise ValueError(
            '"ratio" must be greater than 0 '
            "and less than or equal to 1."
        )

    apply_modifier = bool(
        params.get("apply", True)
    )

    obj = _get_mesh_object(object_name)

    polygons_before = len(
        obj.data.polygons
    )

    modifier = obj.modifiers.new(
        name="Agent Decimate",
        type="DECIMATE",
    )

    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = ratio

    modifier_name = modifier.name

    if apply_modifier:
        _apply_modifier(
            obj,
            modifier_name,
        )

    check.mesh_alive(obj.name)
    check.modifier_state(obj, modifier_name, apply_modifier)
    if apply_modifier:
        polygons_after = check.faces_decreased(obj.name, polygons_before)
    else:
        polygons_after = check.faces_count(obj.name)
        if polygons_after != polygons_before:
            check.fail(
                f'未应用的 Decimate 不应改面数（{polygons_before} → {polygons_after}）'
            )

    return check.stamp({
        "name": obj.name,
        "operation": "decimate",
        "ratio": ratio,
        "polygons_before": polygons_before,
        "polygons_after": polygons_after,
        "modifier": modifier_name,
        "applied": apply_modifier,
    })


@command("modifier.remesh")
def remesh_modifier(
    params: dict[str, Any]
) -> dict[str, Any]:
    """
    Rebuild mesh topology using a Remesh modifier.

    Input example:
        {
            "name": "Cube",
            "voxel_size": 0.2,
            "apply": true
        }
    """

    object_name = str(
        params.get("name", "")
    ).strip()

    if not object_name:
        raise ValueError('"name" is required.')

    voxel_size = float(
        params.get("voxel_size", 0.2)
    )

    if voxel_size <= 0:
        raise ValueError(
            '"voxel_size" must be greater than zero.'
        )

    apply_modifier = bool(
        params.get("apply", True)
    )

    obj = _get_mesh_object(object_name)

    modifier = obj.modifiers.new(
        name="Agent Remesh",
        type="REMESH",
    )

    # Blender Remesh modifier uses octree depth rather
    # than voxel_size directly. Convert the requested
    # level into a simple bounded octree depth.
    if voxel_size <= 0.05:
        octree_depth = 8
    elif voxel_size <= 0.1:
        octree_depth = 7
    elif voxel_size <= 0.25:
        octree_depth = 6
    elif voxel_size <= 0.5:
        octree_depth = 5
    else:
        octree_depth = 4

    modifier.mode = "VOXEL"
    modifier.octree_depth = octree_depth

    modifier_name = modifier.name

    if apply_modifier:
        _apply_modifier(
            obj,
            modifier_name,
        )

    check.mesh_alive(obj.name)
    check.modifier_state(obj, modifier_name, apply_modifier)
    return check.stamp({
        "name": obj.name,
        "operation": "remesh",
        "requested_voxel_size": voxel_size,
        "octree_depth": octree_depth,
        "modifier": modifier_name,
        "applied": apply_modifier,
    })


@command("modifier.shrinkwrap")
def shrinkwrap_modifier(
    params: dict[str, Any]
) -> dict[str, Any]:
    """
    Shrinkwrap one mesh object onto another mesh surface.

    Input example:
        {
            "name": "LowPoly",
            "target": "HighPoly",
            "offset": 0.01,
            "apply": false
        }
    """

    object_name = str(
        params.get("name", "")
    ).strip()

    target_name = str(
        params.get("target", "")
    ).strip()

    if not object_name:
        raise ValueError('"name" is required.')

    if not target_name:
        raise ValueError('"target" is required.')

    obj = _get_mesh_object(object_name)
    target = _get_mesh_object(target_name)

    if obj == target:
        raise ValueError(
            "Shrinkwrap object and target must be different."
        )

    offset = float(
        params.get("offset", 0.0)
    )

    apply_modifier = bool(
        params.get("apply", False)
    )

    modifier = obj.modifiers.new(
        name="Agent Shrinkwrap",
        type="SHRINKWRAP",
    )

    modifier.target = target
    modifier.wrap_method = "NEAREST_SURFACEPOINT"
    modifier.offset = offset

    modifier_name = modifier.name

    if apply_modifier:
        _apply_modifier(
            obj,
            modifier_name,
        )

    check.mesh_alive(obj.name)
    check.object_exists(target.name, "MESH")
    check.modifier_state(obj, modifier_name, apply_modifier)
    return check.stamp({
        "name": obj.name,
        "operation": "shrinkwrap",
        "target": target.name,
        "offset": offset,
        "modifier": modifier_name,
        "applied": apply_modifier,
    })


@command("modifier.data_transfer")
def data_transfer_modifier(
    params: dict[str, Any]
) -> dict[str, Any]:
    """
    Transfer mesh data from a source object to a destination object.

    First version supports CUSTOM_NORMAL only.

    Input example:
        {
            "name": "LowPoly",
            "source": "HighPoly",
            "data_type": "CUSTOM_NORMAL",
            "apply": false
        }
    """

    object_name = str(
        params.get("name", "")
    ).strip()

    source_name = str(
        params.get("source", "")
    ).strip()

    data_type = str(
        params.get("data_type", "CUSTOM_NORMAL")
    ).strip().upper()

    apply_modifier = bool(
        params.get("apply", False)
    )

    if not object_name:
        raise ValueError('"name" is required.')

    if not source_name:
        raise ValueError('"source" is required.')

    if data_type not in {"CUSTOM_NORMAL"}:
        raise ValueError(
            '"data_type" currently only supports CUSTOM_NORMAL.'
        )

    obj = _get_mesh_object(object_name)
    source = _get_mesh_object(source_name)

    if obj == source:
        raise ValueError(
            "Destination object and source object must be different."
        )

    modifier = obj.modifiers.new(
        name="Agent Data Transfer",
        type="DATA_TRANSFER",
    )

    modifier.object = source

    # Transfer custom split normals.
    modifier.use_loop_data = True
    modifier.data_types_loops = {"CUSTOM_NORMAL"}

    # Nearest polygon interpolation is suitable when
    # LowPoly has already been shrinkwrapped close to HighPoly.
    modifier.loop_mapping = "POLYINTERP_NEAREST"

    modifier_name = modifier.name

    if apply_modifier:
        _apply_modifier(
            obj,
            modifier_name,
        )

    check.mesh_alive(obj.name)
    check.object_exists(source.name, "MESH")
    check.modifier_state(obj, modifier_name, apply_modifier)
    return check.stamp({
        "name": obj.name,
        "operation": "data_transfer",
        "source": source.name,
        "data_type": data_type,
        "modifier": modifier_name,
        "applied": apply_modifier,
    })