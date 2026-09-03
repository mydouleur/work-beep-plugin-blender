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
            f'Object "{name}" is not a mesh object. '
            f"Found type: {obj.type}"
        )

    return obj


def _activate_object(obj) -> None:
    """Make an object selected and active."""
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")

    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _enter_edit_mode(obj) -> None:
    """Activate a mesh object and enter Edit Mode."""
    _activate_object(obj)

    bpy.ops.object.mode_set(mode="EDIT")


def _exit_edit_mode() -> None:
    """Return to Object Mode."""
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _select_all_mesh() -> None:
    """Select all mesh elements in Edit Mode."""
    bpy.ops.mesh.select_all(action="SELECT")

def _find_directional_face_index(obj, direction: str) -> int:
    """Return the index of the face whose normal best matches a direction."""

    direction_vectors = {
        "top": (0.0, 0.0, 1.0),
        "bottom": (0.0, 0.0, -1.0),
        "front": (0.0, -1.0, 0.0),
        "back": (0.0, 1.0, 0.0),
        "left": (-1.0, 0.0, 0.0),
        "right": (1.0, 0.0, 0.0),
    }

    target = direction_vectors.get(direction)

    if target is None:
        raise ValueError(
            f'Unsupported face direction "{direction}". '
            "Use top, bottom, front, back, left, or right."
        )

    best_index: int | None = None
    best_score = float("-inf")

    for polygon in obj.data.polygons:
        normal = polygon.normal

        score = (
            normal.x * target[0]
            + normal.y * target[1]
            + normal.z * target[2]
        )

        if score > best_score:
            best_score = score
            best_index = polygon.index

    if best_index is None:
        raise RuntimeError("Could not find a matching face.")

    return best_index

@command("mesh.subdivide")
def subdivide_mesh(params: dict[str, Any]) -> dict[str, Any]:
    """
    Subdivide an existing mesh object.

    Input example:
        {
            "name": "Cube",
            "number_cuts": 2
        }
    """
    object_name = str(params.get("name", "")).strip()

    if not object_name:
        raise ValueError('"name" is required.')

    number_cuts = int(params.get("number_cuts", 1))

    if number_cuts < 1:
        raise ValueError('"number_cuts" must be at least 1.')

    obj = _get_mesh_object(object_name)
    faces_before = len(obj.data.polygons)

    try:
        _enter_edit_mode(obj)
        _select_all_mesh()

        bpy.ops.mesh.subdivide(
            number_cuts=number_cuts,
        )

    finally:
        _exit_edit_mode()

    faces_after = check.faces_increased(obj.name, faces_before)
    return check.stamp({
        "name": obj.name,
        "operation": "subdivide",
        "number_cuts": number_cuts,
        "faces_before": faces_before,
        "faces_after": faces_after,
    })


@command("mesh.inset")
def inset_mesh(params: dict[str, Any]) -> dict[str, Any]:
    """
    Inset all selected faces of a mesh object.

    Input example:
        {
            "name": "Cube",
            "thickness": 0.2,
            "depth": 0.0
        }
    """
    object_name = str(params.get("name", "")).strip()

    if not object_name:
        raise ValueError('"name" is required.')

    thickness = float(params.get("thickness", 0.1))
    depth = float(params.get("depth", 0.0))

    if thickness < 0:
        raise ValueError('"thickness" must not be negative.')

    obj = _get_mesh_object(object_name)
    faces_before = len(obj.data.polygons)

    try:
        _enter_edit_mode(obj)
        bpy.ops.mesh.select_mode(type="FACE")
        _select_all_mesh()

        result = bpy.ops.mesh.inset(
            thickness=thickness,
            depth=depth,
            use_individual=True,
        )
        if "FINISHED" not in result:
            raise RuntimeError(f"inset 未完成: {result}")

    finally:
        _exit_edit_mode()

    if thickness > 0 or depth != 0:
        faces_after = check.faces_increased(obj.name, faces_before)
    else:
        faces_after = check.faces_count(obj.name)
    return check.stamp({
        "name": obj.name,
        "operation": "inset",
        "thickness": thickness,
        "depth": depth,
        "faces_before": faces_before,
        "faces_after": faces_after,
    })


@command("mesh.bevel")
def bevel_mesh(params: dict[str, Any]) -> dict[str, Any]:
    """
    Bevel all selected edges of a mesh object.

    Input example:
        {
            "name": "Cube",
            "offset": 0.1,
            "segments": 3
        }
    """
    object_name = str(params.get("name", "")).strip()

    if not object_name:
        raise ValueError('"name" is required.')

    offset = float(params.get("offset", 0.1))
    segments = int(params.get("segments", 1))

    if offset < 0:
        raise ValueError('"offset" must not be negative.')

    if segments < 1:
        raise ValueError('"segments" must be at least 1.')

    obj = _get_mesh_object(object_name)
    faces_before = len(obj.data.polygons)

    try:
        _enter_edit_mode(obj)
        _select_all_mesh()

        bpy.ops.mesh.bevel(
            offset=offset,
            segments=segments,
        )

    finally:
        _exit_edit_mode()

    if offset > 0:
        faces_after = check.faces_increased(obj.name, faces_before)
    else:
        faces_after = check.faces_count(obj.name)
    return check.stamp({
        "name": obj.name,
        "operation": "bevel",
        "offset": offset,
        "segments": segments,
        "faces_before": faces_before,
        "faces_after": faces_after,
    })


@command("mesh.extrude_face")
def extrude_face(params: dict[str, Any]) -> dict[str, Any]:
    """
    Extrude one directional face of a mesh object.

    Input example:
        {
            "name": "Cube",
            "face": "top",
            "offset": [0, 0, 2]
        }
    """

    name = str(params.get("name", "")).strip()
    face_direction = str(params.get("face", "")).strip().lower()
    offset = params.get("offset", [0.0, 0.0, 1.0])

    if not name:
        raise ValueError('"name" is required.')

    if not face_direction:
        raise ValueError('"face" is required.')

    if not isinstance(offset, (list, tuple)) or len(offset) != 3:
        raise ValueError(
            '"offset" must contain exactly three numbers.'
        )

    try:
        offset_xyz = (
            float(offset[0]),
            float(offset[1]),
            float(offset[2]),
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            'Every value in "offset" must be numeric.'
        ) from error

    obj = _get_mesh_object(name)
    faces_before = len(obj.data.polygons)

    # Important: store only the integer index.
    face_index = _find_directional_face_index(
        obj,
        face_direction,
    )

    try:
        _activate_object(obj)

        # Clear the selection in Edit Mode.
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")

        # Face selection is easiest to set through mesh data in Object Mode.
        bpy.ops.object.mode_set(mode="OBJECT")

        if face_index >= len(obj.data.polygons):
            raise RuntimeError(
                f"Face index {face_index} is no longer valid."
            )

        obj.data.polygons[face_index].select = True

        bpy.ops.object.mode_set(mode="EDIT")

        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={
                "value": offset_xyz,
            }
        )

    finally:
        _exit_edit_mode()

    faces_after = check.faces_increased(obj.name, faces_before)
    return check.stamp({
        "name": obj.name,
        "face": face_direction,
        "face_index": face_index,
        "offset": list(offset_xyz),
        "faces_before": faces_before,
        "faces_after": faces_after,
    })


@command("mesh.quadriflow_remesh")
def quadriflow_remesh(params: dict[str, Any]) -> dict[str, Any]:
    """
    Retopologize a mesh using QuadriFlow.

    Input example:
        {
            "name": "HighPoly",
            "target_faces": 5000
        }
    """

    name = str(params.get("name", "")).strip()

    if not name:
        raise ValueError('"name" is required.')

    target_faces = int(params.get("target_faces", 5000))

    if target_faces < 4:
        raise ValueError(
            '"target_faces" must be at least 4.'
        )

    obj = _get_mesh_object(name)

    # QuadriFlow operates on the active mesh object.
    _activate_object(obj)

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    faces_before = len(obj.data.polygons)

    # "mode" must be FACES for "target_faces" to be honoured at all.
    # The operator's property set differs between Blender versions
    # (use_mesh_symmetry used to be use_paint_symmetry), and one unknown
    # keyword aborts the whole call, so drop whatever this build lacks.
    wanted = {
        "mode": "FACES",
        "target_faces": target_faces,
        "use_preserve_sharp": True,
        "use_preserve_boundary": True,
        "use_mesh_symmetry": False,
    }

    supported = (
        bpy.ops.object.quadriflow_remesh
        .get_rna_type()
        .properties
        .keys()
    )

    kwargs = {
        key: value
        for key, value in wanted.items()
        if key in supported
    }

    result = bpy.ops.object.quadriflow_remesh(**kwargs)

    if "FINISHED" not in result:
        raise RuntimeError(
            f"QuadriFlow did not finish successfully: {result}"
        )

    faces_after = check.faces_count(obj.name)

    return check.stamp({
        "name": obj.name,
        "operation": "quadriflow_remesh",
        "target_faces": target_faces,
        "faces_before": faces_before,
        "faces_after": faces_after,
    })


@command("mesh.stats")
def mesh_stats(params: dict[str, Any]) -> dict[str, Any]:
    """
    Return basic topology statistics for a mesh object.

    Input example:
        {
            "name": "HighPoly"
        }
    """

    name = str(params.get("name", "")).strip()

    if not name:
        raise ValueError('"name" is required.')

    obj = _get_mesh_object(name)
    mesh = obj.data
    check.mesh_alive(obj.name)
    payload = {
        "name": obj.name,
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "faces": len(mesh.polygons),
    }
    if payload["faces"] != len(obj.data.polygons):
        check.fail("mesh.stats 面数与当前网格不一致")
    return check.stamp(payload)