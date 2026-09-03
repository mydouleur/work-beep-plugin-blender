from typing import Any

import check
from registry import command


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

    objects = list(bpy.data.objects)
    deleted_count = len(objects)

    # Remove objects directly from Blender data.
    # do_unlink=True also removes them from their collections.
    for obj in objects:
        bpy.data.objects.remove(obj, do_unlink=True)

    check.scene_empty()
    return check.stamp({
        "deleted_count": deleted_count,
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