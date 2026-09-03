"""桥命令集成测试：正向 + 反向错误场景（必须在 Blender 内跑）。

用法：
    blender -b --factory-startup --python scripts/test_bridge.py
    python scripts/run_ci_tests.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "assets" / "bridge"))

import bpy  # noqa: E402
import commands  # noqa: F401, E402
from registry import COMMANDS  # noqa: E402

# 核心功能错误场景目录（会上 95% 覆盖目标）。每条对应一个会抛错的路径。
CORE_ERRORS = [
    "object.not_found",
    "object.size_le_0",
    "object.location_bad",
    "object.name_empty",
    "object.move_no_name",
    "object.move_no_location",
    "object.delete_no_name",
    "object.cylinder_bad",
    "object.sphere_bad",
    "object.rotate_missing",
    "object.scale_missing",
    "object.scale_le_0",
    "object.duplicate_no_name",
    "mesh.not_found",
    "mesh.not_mesh",
    "mesh.subdivide_bad",
    "mesh.inset_bad",
    "mesh.bevel_bad",
    "mesh.extrude_bad",
    "mesh.quadriflow_bad",
    "mesh.stats_no_name",
    "modifier.no_name",
    "modifier.mirror_axis",
    "modifier.boolean_operand",
    "modifier.boolean_same",
    "modifier.boolean_op",
    "modifier.decimate_ratio",
    "modifier.remesh_voxel",
    "modifier.shrinkwrap_target",
    "modifier.shrinkwrap_same",
    "modifier.transfer_source",
    "modifier.transfer_same",
    "modifier.transfer_type",
    "material.no_name",
    "material.exists",
    "material.color_bad",
    "material.color_range",
    "material.assign_missing",
    "material.not_found",
    "light.bad_type",
    "light.energy_neg",
    "light.not_found",
    "light.not_light",
    "light.color_bad",
    "camera.lens_le_0",
    "camera.not_found",
    "camera.not_camera",
    "camera.look_at_no_name",
    "camera.look_at_same",
    "render.no_name",
    "render.obj_missing",
    "render.bad_view",
    "render.res_low",
    "render.views_empty",
    "render.validate_no_dir",
    "render.validate_missing_file",
    "view.bad_axis",
    "view.no_viewport",
]


class Runner:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []
        self.covered: set[str] = set()

    def _ok(self, name: str) -> None:
        self.passed += 1
        print(f"  PASS  {name}")

    def _fail(self, name: str, detail: str) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {detail}")
        print(f"  FAIL  {name}  {detail}")

    def cover(self, sid: str) -> None:
        self.covered.add(sid)

    def call(self, cmd: str, params: dict | None = None):
        return COMMANDS[cmd](params or {})

    def pos(self, name: str, cmd: str, params: dict | None = None, check=None) -> None:
        try:
            data = self.call(cmd, params)
            if check is not None:
                check(data)
            self._ok(name)
        except Exception as exc:
            self._fail(name, f"{type(exc).__name__}: {exc}")

    def neg(self, name: str, sid: str, cmd: str, params: dict | None, needle: str) -> None:
        try:
            self.call(cmd, params)
            self._fail(name, "应当抛错但成功了")
        except Exception as exc:
            text = str(exc)
            if needle.lower() in text.lower():
                self.cover(sid)
                self._ok(name)
            else:
                self._fail(name, f"错误文案不含 {needle!r}：{text}")


def reset() -> None:
    COMMANDS["scene.clear"]({})


def _has_obj(name: str) -> bool:
    return bpy.data.objects.get(name) is not None


def main() -> int:
    r = Runner()
    print("== 桥命令集成测试（无头 Blender）==")
    print(f"Blender {bpy.app.version_string}  background={bpy.app.background}")

    # --- 正向：旧功能还能用 ---
    print("\n[正向]")
    reset()
    r.pos("pos.scene_list_emptyish", "scene.list_objects", {}, lambda d: d.get("validated") is True)
    r.pos(
        "pos.add_cube",
        "object.add_cube",
        {"name": "Cube", "size": 2, "location": [0, 0, 0]},
        lambda d: d.get("validated") is True and _has_obj("Cube"),
    )
    r.pos(
        "pos.list_has_cube",
        "scene.list_objects",
        {},
        lambda d: any(o["name"] == "Cube" for o in d.get("objects", [])),
    )
    r.pos(
        "pos.move",
        "object.move",
        {"name": "Cube", "location": [1, 2, 3]},
        lambda d: d.get("location") == [1.0, 2.0, 3.0],
    )
    r.pos("pos.rotate", "object.rotate", {"name": "Cube", "rotation": [0, 0, 90]})
    r.pos("pos.scale", "object.scale", {"name": "Cube", "scale": [1, 2, 1]})
    r.pos(
        "pos.duplicate",
        "object.duplicate",
        {"name": "Cube", "new_name": "CubeCopy", "location": [4, 0, 0]},
        lambda d: _has_obj("Cube") and _has_obj("CubeCopy"),
    )
    r.pos("pos.mesh_stats", "mesh.stats", {"name": "Cube"}, lambda d: d.get("faces", 0) >= 1)
    r.pos(
        "pos.subdivide",
        "mesh.subdivide",
        {"name": "CubeCopy", "number_cuts": 1},
        lambda d: d.get("faces_after", 0) > d.get("faces_before", 0),
    )
    r.pos("pos.add_inset_cube", "object.add_cube", {"name": "InsetBox", "size": 2})
    r.pos(
        "pos.inset",
        "mesh.inset",
        {"name": "InsetBox", "thickness": 0.2},
        lambda d: d.get("faces_after", 0) > d.get("faces_before", 0),
    )
    r.pos("pos.bevel", "mesh.bevel", {"name": "CubeCopy", "offset": 0.02, "segments": 1})
    r.pos(
        "pos.extrude",
        "mesh.extrude_face",
        {"name": "Cube", "face": "top", "offset": [0, 0, 0.5]},
    )
    r.pos(
        "pos.mirror",
        "modifier.mirror",
        {"name": "Cube", "axis": "X", "apply": False},
        lambda d: d.get("applied") is False,
    )
    r.pos("pos.add_plane", "object.add_plane", {"name": "Floor", "size": 4})
    r.pos("pos.add_cylinder", "object.add_cylinder", {"name": "Cyl", "radius": 0.5, "depth": 1})
    r.pos("pos.add_sphere", "object.add_uv_sphere", {"name": "Ball", "radius": 0.5})
    r.pos("pos.mat_create", "material.create", {"name": "RedMat"})
    r.pos("pos.mat_color", "material.set_base_color", {"name": "RedMat", "color": [1, 0, 0]})
    r.pos("pos.mat_assign", "material.assign", {"object": "Cube", "material": "RedMat"})
    r.pos("pos.light_add", "light.add", {"name": "Key", "type": "POINT", "energy": 200})
    r.pos("pos.light_energy", "light.set_energy", {"name": "Key", "energy": 300})
    r.pos("pos.light_color", "light.set_color", {"name": "Key", "color": [1, 1, 0.5]})
    r.pos("pos.cam_add", "camera.add", {"name": "Shot", "location": [5, -5, 4], "lens": 50})
    r.pos("pos.cam_look", "camera.look_at", {"name": "Shot", "target": [0, 0, 0]})
    r.pos(
        "pos.boolean",
        "modifier.boolean",
        {"name": "Cube", "operand": "Ball", "operation": "DIFFERENCE", "apply": False},
    )
    r.pos("pos.decimate", "modifier.decimate", {"name": "Cyl", "ratio": 0.8, "apply": False})
    r.pos(
        "pos.shrinkwrap",
        "modifier.shrinkwrap",
        {"name": "Floor", "target": "Ball", "apply": False},
    )
    r.pos(
        "pos.data_transfer",
        "modifier.data_transfer",
        {"name": "Floor", "source": "Ball", "apply": False},
    )

    with tempfile.TemporaryDirectory(prefix="beep-ci-view-") as folder:
        try:
            r.call(
                "render.view",
                {
                    "name": "Cube",
                    "view": "front",
                    "resolution": 128,
                    "path": os.path.join(folder, "Cube_front.png"),
                },
            )
            can_render = True
        except Exception as exc:
            can_render = False
            print(f"  SKIP  渲染正例（无头环境无法出图：{exc}）")
        if can_render:
            r.pos(
                "pos.render_view",
                "render.view",
                {
                    "name": "Cube",
                    "view": "front",
                    "resolution": 128,
                    "path": os.path.join(folder, "Cube_front.png"),
                },
                lambda d: d.get("ok") is True and d.get("validated") is True,
            )
            r.pos(
                "pos.render_views",
                "render.views",
                {
                    "name": "Cube",
                    "views": ["front", "right"],
                    "resolution": 128,
                    "output_dir": folder,
                },
                lambda d: d.get("ok") is True,
            )
            r.pos(
                "pos.validate_views",
                "render.validate_views",
                {"output_dir": folder, "name": "Cube", "views": ["front", "right"]},
                lambda d: d.get("ok") is True,
            )
        gone = os.path.join(folder, "Cube_right.png")
        if os.path.isfile(gone):
            os.remove(gone)
        r.neg(
            "neg.render_validate_missing",
            "render.validate_missing_file",
            "render.validate_views",
            {"output_dir": folder, "name": "Cube", "views": ["front", "right"]},
            "验收",
        )

    r.pos("pos.delete", "object.delete", {"name": "CubeCopy"}, lambda d: not _has_obj("CubeCopy"))
    r.pos("pos.clear", "scene.clear", {}, lambda d: len(list(bpy.data.objects)) == 0)

    # --- 反向：核心错误场景 ---
    print("\n[反向]")
    reset()
    r.call("object.add_cube", {"name": "Cube"})
    r.call("object.add_uv_sphere", {"name": "Ball"})
    r.call("light.add", {"name": "Key"})
    r.call("camera.add", {"name": "Shot", "location": [3, -3, 2]})
    r.call("material.create", {"name": "MatA"})

    r.neg("neg.object_not_found", "object.not_found", "object.move", {"name": "NoSuch", "location": [0, 0, 0]}, "not found")
    r.neg("neg.size_le_0", "object.size_le_0", "object.add_cube", {"name": "Bad", "size": 0}, "greater than zero")
    r.neg("neg.location_bad", "object.location_bad", "object.add_cube", {"name": "Bad", "location": [1, 2]}, "exactly three")
    r.neg("neg.name_empty", "object.name_empty", "object.add_cube", {"name": "   "}, "cannot be empty")
    r.neg("neg.move_no_name", "object.move_no_name", "object.move", {"location": [0, 0, 0]}, "name")
    r.neg("neg.move_no_loc", "object.move_no_location", "object.move", {"name": "Cube"}, "location")
    r.neg("neg.delete_no_name", "object.delete_no_name", "object.delete", {}, "name")
    r.neg("neg.cyl_bad", "object.cylinder_bad", "object.add_cylinder", {"name": "C", "radius": 0}, "greater than zero")
    r.neg("neg.sphere_bad", "object.sphere_bad", "object.add_uv_sphere", {"name": "S", "segments": 2}, "at least 3")
    r.neg("neg.rotate_missing", "object.rotate_missing", "object.rotate", {"name": "Cube"}, "rotation")
    r.neg("neg.scale_missing", "object.scale_missing", "object.scale", {"name": "Cube"}, "scale")
    r.neg("neg.scale_le_0", "object.scale_le_0", "object.scale", {"name": "Cube", "scale": [1, 0, 1]}, "greater than zero")
    r.neg("neg.dup_no_name", "object.duplicate_no_name", "object.duplicate", {}, "name")

    r.neg("neg.mesh_not_found", "mesh.not_found", "mesh.stats", {"name": "Ghost"}, "not found")
    r.neg("neg.mesh_not_mesh", "mesh.not_mesh", "mesh.stats", {"name": "Key"}, "not a mesh")
    r.neg("neg.subdivide_bad", "mesh.subdivide_bad", "mesh.subdivide", {"name": "Cube", "number_cuts": 0}, "at least 1")
    r.neg("neg.inset_bad", "mesh.inset_bad", "mesh.inset", {"name": "Cube", "thickness": -1}, "not be negative")
    r.neg("neg.bevel_bad", "mesh.bevel_bad", "mesh.bevel", {"name": "Cube", "segments": 0}, "at least 1")
    r.neg("neg.extrude_bad", "mesh.extrude_bad", "mesh.extrude_face", {"name": "Cube", "face": "sideways", "offset": [0, 0, 1]}, "Unsupported")
    r.neg("neg.qflow_bad", "mesh.quadriflow_bad", "mesh.quadriflow_remesh", {"name": "Cube", "target_faces": 1}, "at least 4")
    r.neg("neg.stats_no_name", "mesh.stats_no_name", "mesh.stats", {}, "name")

    r.neg("neg.mod_no_name", "modifier.no_name", "modifier.mirror", {}, "name")
    r.neg("neg.mirror_axis", "modifier.mirror_axis", "modifier.mirror", {"name": "Cube", "axis": "W"}, "X, Y, or Z")
    r.neg("neg.bool_operand", "modifier.boolean_operand", "modifier.boolean", {"name": "Cube"}, "operand")
    r.neg("neg.bool_same", "modifier.boolean_same", "modifier.boolean", {"name": "Cube", "operand": "Cube"}, "different")
    r.neg("neg.bool_op", "modifier.boolean_op", "modifier.boolean", {"name": "Cube", "operand": "Ball", "operation": "XOR"}, "DIFFERENCE")
    r.neg("neg.decimate_ratio", "modifier.decimate_ratio", "modifier.decimate", {"name": "Cube", "ratio": 0}, "greater than 0")
    r.neg("neg.remesh_voxel", "modifier.remesh_voxel", "modifier.remesh", {"name": "Cube", "voxel_size": 0}, "greater than zero")
    r.neg("neg.sw_target", "modifier.shrinkwrap_target", "modifier.shrinkwrap", {"name": "Cube"}, "target")
    r.neg("neg.sw_same", "modifier.shrinkwrap_same", "modifier.shrinkwrap", {"name": "Cube", "target": "Cube"}, "different")
    r.neg("neg.dt_source", "modifier.transfer_source", "modifier.data_transfer", {"name": "Cube"}, "source")
    r.neg("neg.dt_same", "modifier.transfer_same", "modifier.data_transfer", {"name": "Cube", "source": "Cube"}, "different")
    r.neg("neg.dt_type", "modifier.transfer_type", "modifier.data_transfer", {"name": "Cube", "source": "Ball", "data_type": "UV"}, "CUSTOM_NORMAL")

    r.neg("neg.mat_no_name", "material.no_name", "material.create", {}, "name")
    r.neg("neg.mat_exists", "material.exists", "material.create", {"name": "MatA"}, "already exists")
    r.neg("neg.mat_color_bad", "material.color_bad", "material.set_base_color", {"name": "MatA", "color": [1]}, "R, G, B")
    r.neg("neg.mat_color_range", "material.color_range", "material.set_base_color", {"name": "MatA", "color": [2, 0, 0]}, "between 0 and 1")
    r.neg("neg.mat_assign", "material.assign_missing", "material.assign", {"object": "Cube"}, "material")
    r.neg("neg.mat_not_found", "material.not_found", "material.set_base_color", {"name": "NoMat", "color": [1, 0, 0]}, "not found")

    r.neg("neg.light_type", "light.bad_type", "light.add", {"name": "L", "type": "NEON"}, "POINT")
    r.neg("neg.light_energy", "light.energy_neg", "light.set_energy", {"name": "Key", "energy": -1}, "cannot be negative")
    r.neg("neg.light_missing", "light.not_found", "light.set_energy", {"name": "Ghost", "energy": 1}, "not found")
    r.neg("neg.light_not_light", "light.not_light", "light.set_energy", {"name": "Cube", "energy": 1}, "not a light")
    r.neg("neg.light_color", "light.color_bad", "light.set_color", {"name": "Key", "color": [1, 2]}, "R, G, B")

    r.neg("neg.cam_lens", "camera.lens_le_0", "camera.add", {"name": "BadCam", "lens": 0}, "greater than zero")
    r.neg("neg.cam_missing", "camera.not_found", "camera.look_at", {"name": "Ghost", "target": [0, 0, 0]}, "not found")
    r.neg("neg.cam_not_cam", "camera.not_camera", "camera.look_at", {"name": "Cube", "target": [0, 0, 0]}, "not a camera")
    r.neg("neg.cam_no_name", "camera.look_at_no_name", "camera.look_at", {"target": [0, 0, 0]}, "name")
    shot = bpy.data.objects.get("Shot")
    same = [float(v) for v in shot.location] if shot is not None else [3.0, -3.0, 2.0]
    r.neg("neg.cam_same", "camera.look_at_same", "camera.look_at", {"name": "Shot", "target": same}, "same location")

    r.neg("neg.render_no_name", "render.no_name", "render.view", {}, "name")
    r.neg("neg.render_missing", "render.obj_missing", "render.view", {"name": "Ghost"}, "找不到对象")
    r.neg("neg.render_view", "render.bad_view", "render.view", {"name": "Cube", "view": "diagonal"}, "未知视图")
    r.neg("neg.render_res", "render.res_low", "render.view", {"name": "Cube", "resolution": 8}, "至少 64")
    r.neg("neg.render_empty", "render.views_empty", "render.views", {"name": "Cube", "views": []}, "非空")
    r.neg("neg.validate_dir", "render.validate_no_dir", "render.validate_views", {}, "output_dir")

    r.neg("neg.view_axis", "view.bad_axis", "view.set_axis", {"view": "diagonal"}, "未知视图")
    try:
        r.call("view.set_axis", {"view": "front"})
        print("  SKIP  neg.view_no_vp（本环境有 3D 视口，无法复现）")
    except Exception as exc:
        if "3D 视口" in str(exc):
            r.cover("view.no_viewport")
            r._ok("neg.view_no_vp")
        else:
            r._fail("neg.view_no_vp", str(exc))

    missing = [s for s in CORE_ERRORS if s not in r.covered]
    coverage = 100.0 * len(r.covered) / len(CORE_ERRORS)

    print()
    print(f"通过 {r.passed}  失败 {r.failed}")
    print(f"核心错误场景覆盖 {len(r.covered)}/{len(CORE_ERRORS)} = {coverage:.1f}%")
    if missing:
        print("未覆盖：", ", ".join(missing))
    if r.errors:
        print("失败明细：")
        for line in r.errors:
            print("  -", line)

    if r.failed:
        return 1
    if coverage < 95:
        print("覆盖率低于会上 95% 目标")
        return 1
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        traceback.print_exc()
        code = 1
    # Blender 有时吞掉 SystemExit，写结果文件给外层 runner
    result = ROOT / "scripts" / ".ci-bridge-result.txt"
    result.write_text(str(code), encoding="utf-8")
    sys.exit(code)
