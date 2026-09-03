// 插件工具声明：工具名 ↔ 桥命令的映射收在这里（单一数据源）。
// 从旧项目 blenderBeep 的 tool 分支迁入；命名 blender.<cmd 点改下划线>，由 Host 强制前缀校验。
import type { PluginTool } from "@beep/sdk";
import { state } from "./state";

function bridgeTool(
    cmd: string,
    description: string,
    parameters: PluginTool["parameters"],
): PluginTool {
    return {
        name: `blender.${cmd.replace(/\./g, "_")}`,
        description,
        parameters,
        async run(args, ctx) {
            if (!state.port) throw new Error("Blender 未启动或桥未就绪");
            const data = await ctx.call(state.port, cmd, args ?? {});
            if (data && typeof data === "object") {
                const payload = data as { ok?: boolean; validated?: boolean };
                if (payload.ok === false || payload.validated === false) {
                    throw new Error(`验收未通过: ${JSON.stringify(data)}`);
                }
            }
            return JSON.stringify(data);
        },
    };
}

export const tools: PluginTool[] = [
    bridgeTool("scene.list_objects", "列出场景中所有物体的名称、类型、位置、旋转（弧度）、缩放。其他命令都要求传物体名，所以不确定要操作谁时先调它", {
        "type": "object",
        "properties": {},
        "additionalProperties": false
}),
    bridgeTool("scene.clear", "清空当前 Blender 场景，删除场景中的所有物体。当用户要求清空场景、删除全部对象、重新开始或创建全新场景时使用（不可撤销，执行前应先向用户确认）", {
        "type": "object",
        "properties": {},
        "additionalProperties": false
}),
    bridgeTool("object.add_cube", "新建一个立方体", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "新物体名称；必须显式取名，后续操作全靠它引用"
                },
                "size": {
                        "type": "number",
                        "description": "边长，默认 2.0，必须大于 0"
                },
                "location": {
                        "type": "array",
                        "description": "放置位置 [x, y, z]，默认世界原点",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("object.add_uv_sphere", "新建一个 UV 球体", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "新物体名称；必须显式取名，后续操作全靠它引用"
                },
                "radius": {
                        "type": "number",
                        "description": "半径，默认 1.0，必须大于 0"
                },
                "segments": {
                        "type": "integer",
                        "description": "经线段数，默认 32，至少 3"
                },
                "ring_count": {
                        "type": "integer",
                        "description": "纬线环数，默认 16，至少 3"
                },
                "location": {
                        "type": "array",
                        "description": "放置位置 [x, y, z]，默认世界原点",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("object.add_cylinder", "新建一个圆柱体", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "新物体名称；必须显式取名，后续操作全靠它引用"
                },
                "radius": {
                        "type": "number",
                        "description": "底面半径，默认 1.0，必须大于 0"
                },
                "depth": {
                        "type": "number",
                        "description": "高度，默认 2.0，必须大于 0"
                },
                "vertices": {
                        "type": "integer",
                        "description": "底面边数，默认 32，至少 3"
                },
                "location": {
                        "type": "array",
                        "description": "放置位置 [x, y, z]，默认世界原点",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("object.add_plane", "新建一个平面（常用来当地面/底板）", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "新物体名称；必须显式取名，后续操作全靠它引用"
                },
                "size": {
                        "type": "number",
                        "description": "边长，默认 2.0，必须大于 0"
                },
                "location": {
                        "type": "array",
                        "description": "放置位置 [x, y, z]，默认世界原点",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("object.move", "把物体移动到指定位置（绝对坐标，不是相对位移）", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "location": {
                        "type": "array",
                        "description": "目标位置 [x, y, z]（绝对坐标）",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                }
        },
        "required": [
                "name",
                "location"
        ],
        "additionalProperties": false
}),
    bridgeTool("object.rotate", "设置物体的欧拉旋转角，单位是度、且是绝对角度（不是在当前角度上叠加）。注意 scene_list_objects 返回的 rotation 是弧度，不能直接回填", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "rotation": {
                        "type": "array",
                        "description": "绕 XYZ 轴的角度（度）[rx, ry, rz]",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                }
        },
        "required": [
                "name",
                "rotation"
        ],
        "additionalProperties": false
}),
    bridgeTool("object.scale", "设置物体的 XYZ 缩放系数（绝对值，1 表示原始大小）", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "scale": {
                        "type": "array",
                        "description": "XYZ 缩放系数 [sx, sy, sz]，每一项都必须大于 0；等比缩放就填三个一样的值",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                }
        },
        "required": [
                "name",
                "scale"
        ],
        "additionalProperties": false
}),
    bridgeTool("object.delete", "按名称删除一个物体", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("object.duplicate", "复制一个物体（网格数据也会独立复制），可指定副本名称与位置", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "new_name": {
                        "type": "string",
                        "description": "副本名称，省略则由 Blender 自动命名"
                },
                "location": {
                        "type": "array",
                        "description": "副本的绝对位置 [x, y, z]，省略则与原物体重合",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("mesh.stats", "查看网格对象的拓扑统计，包括顶点数、边数和面数，常用于比较重拓扑前后的复杂度", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("mesh.subdivide", "细分网格：对物体的所有面加切分，增加面数（仅限网格物体）", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "number_cuts": {
                        "type": "integer",
                        "description": "每条边的切分次数，默认 1，至少 1"
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("mesh.bevel", "倒角：把物体的所有边磨成圆角（仅限网格物体）", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "offset": {
                        "type": "number",
                        "description": "倒角宽度，默认 0.1，不能为负"
                },
                "segments": {
                        "type": "integer",
                        "description": "倒角段数，默认 1；越大越圆滑"
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("mesh.inset", "内插面：在物体的所有面内部收一圈新面（仅限网格物体）", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "thickness": {
                        "type": "number",
                        "description": "内插厚度，默认 0.1，不能为负"
                },
                "depth": {
                        "type": "number",
                        "description": "内插面的凹凸深度，默认 0"
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("mesh.extrude_face", "挤出：把物体朝某个方向的那一面拉出去（仅限网格物体）", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "face": {
                        "type": "string",
                        "description": "要挤出的面朝向",
                        "enum": [
                                "top",
                                "bottom",
                                "front",
                                "back",
                                "left",
                                "right"
                        ]
                },
                "offset": {
                        "type": "array",
                        "description": "挤出位移 [x, y, z]，方向要和 face 对应，如顶面向上 2 单位传 [0, 0, 2]",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                }
        },
        "required": [
                "name",
                "face",
                "offset"
        ],
        "additionalProperties": false
}),
    bridgeTool("mesh.quadriflow_remesh", "使用 QuadriFlow 对复杂网格做自动重拓扑，生成较规整的四边形拓扑，可指定目标面数", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "target_faces": {
                        "type": "integer",
                        "description": "希望重拓扑后的目标面数，例如 5000，必须至少为 4"
                }
        },
        "required": [
                "name",
                "target_faces"
        ],
        "additionalProperties": false
}),
    bridgeTool("modifier.boolean", "布尔运算：用另一个物体对目标物体做差集/并集/交集，常用于挖洞、切槽。两个物体都必须是网格物体且不能是同一个", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "operand": {
                        "type": "string",
                        "description": "参与运算的另一个物体名称（切割体）"
                },
                "operation": {
                        "type": "string",
                        "description": "运算方式，默认 DIFFERENCE（从目标上减去切割体）",
                        "enum": [
                                "DIFFERENCE",
                                "UNION",
                                "INTERSECT"
                        ]
                },
                "apply": {
                        "type": "boolean",
                        "description": "是否立即应用修改器，默认 true"
                }
        },
        "required": [
                "name",
                "operand"
        ],
        "additionalProperties": false
}),
    bridgeTool("modifier.mirror", "镜像修改器：沿指定轴对称复制网格（仅限网格物体）", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "axis": {
                        "type": "string",
                        "description": "镜像轴，默认 X",
                        "enum": [
                                "X",
                                "Y",
                                "Z"
                        ]
                },
                "apply": {
                        "type": "boolean",
                        "description": "是否立即应用修改器，默认 false"
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("modifier.decimate", "减面：按比例降低网格面数以简化模型（仅限网格物体）", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "ratio": {
                        "type": "number",
                        "description": "保留比例，(0, 1]，默认 0.5"
                },
                "apply": {
                        "type": "boolean",
                        "description": "是否立即应用修改器，默认 true"
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("modifier.remesh", "重构网格：用体素方式重建拓扑，让布线均匀（仅限网格物体）", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "voxel_size": {
                        "type": "number",
                        "description": "体素大小，默认 0.2，越小越精细（桥端会换算成八叉树深度）"
                },
                "apply": {
                        "type": "boolean",
                        "description": "是否立即应用修改器，默认 true"
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("modifier.shrinkwrap", "Shrinkwrap：让一个低模网格贴合另一个目标高模的表面，常用于重拓扑工作流", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "target": {
                        "type": "string",
                        "description": "要贴合到的目标高模对象名称"
                },
                "offset": {
                        "type": "number",
                        "description": "与目标表面的偏移距离，默认 0，例如 0.01"
                },
                "apply": {
                        "type": "boolean",
                        "description": "是否立即应用 Shrinkwrap 修改器，默认 false"
                }
        },
        "required": [
                "name",
                "target"
        ],
        "additionalProperties": false
}),
    bridgeTool("modifier.data_transfer", "把高模网格的数据传递给低模。当前主要用于把 HighPoly 的自定义法线传给 LowPoly，常接在 QuadriFlow + Shrinkwrap 之后", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "目标物体名称，必须是场景中已存在的物体（不确定就先调 blender.scene_list_objects）"
                },
                "source": {
                        "type": "string",
                        "description": "数据来源对象名称，例如 HighPoly"
                },
                "data_type": {
                        "type": "string",
                        "enum": [
                                "CUSTOM_NORMAL"
                        ],
                        "description": "要传递的数据类型，当前支持 CUSTOM_NORMAL"
                },
                "apply": {
                        "type": "boolean",
                        "description": "是否立即应用 Data Transfer 修改器，默认 false"
                }
        },
        "required": [
                "name",
                "source"
        ],
        "additionalProperties": false
}),
    bridgeTool("material.create", "新建一个材质（同名材质已存在会报错）。给物体上色的完整流程：先 material_create 建材质，再 material_set_base_color 调色，最后 material_assign 挂到物体上", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "材质名称"
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("material.set_base_color", "设置材质的基础色。注意 name 传的是【材质名】而不是物体名，材质必须已存在；改完还要用 material_assign 才会作用到物体上", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "材质名称（不是物体名）"
                },
                "color": {
                        "type": "array",
                        "description": "颜色 [R, G, B] 或 [R, G, B, A]，每项取值 0~1，如红色 [1, 0, 0, 1]",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 4
                }
        },
        "required": [
                "name",
                "color"
        ],
        "additionalProperties": false
}),
    bridgeTool("material.assign", "把一个已存在的材质赋给物体（注意参数名是 object 和 material，不是 name）", {
        "type": "object",
        "properties": {
                "object": {
                        "type": "string",
                        "description": "物体名称"
                },
                "material": {
                        "type": "string",
                        "description": "材质名称"
                }
        },
        "required": [
                "object",
                "material"
        ],
        "additionalProperties": false
}),
    bridgeTool("light.add", "在场景中新建一盏灯（点光/日光/聚光/面光）", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "灯光名称，默认 Light"
                },
                "type": {
                        "type": "string",
                        "description": "灯光类型，默认 POINT",
                        "enum": [
                                "POINT",
                                "SUN",
                                "SPOT",
                                "AREA"
                        ]
                },
                "location": {
                        "type": "array",
                        "description": "灯光位置 [x, y, z]，默认 [4, 4, 6]",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                },
                "energy": {
                        "type": "number",
                        "description": "亮度（瓦），默认 1000，不能为负"
                }
        },
        "additionalProperties": false
}),
    bridgeTool("light.set_energy", "调整已有灯光的亮度", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "灯光物体名称"
                },
                "energy": {
                        "type": "number",
                        "description": "亮度（瓦），默认 1000，不能为负"
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("light.set_color", "调整已有灯光的颜色", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "灯光物体名称"
                },
                "color": {
                        "type": "array",
                        "description": "灯光颜色 [R, G, B]，每项取值 0~1",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                }
        },
        "required": [
                "name",
                "color"
        ],
        "additionalProperties": false
}),
    bridgeTool("camera.add", "新建一台相机，默认设为场景的活动相机", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "相机名称，默认 Camera"
                },
                "location": {
                        "type": "array",
                        "description": "相机位置 [x, y, z]，默认 [7, -7, 5]",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                },
                "lens": {
                        "type": "number",
                        "description": "焦距（毫米），默认 50，必须大于 0"
                },
                "set_active": {
                        "type": "boolean",
                        "description": "是否设为活动相机，默认 true"
                }
        },
        "additionalProperties": false
}),
    bridgeTool("camera.look_at", "旋转相机使其对准某个坐标点", {
        "type": "object",
        "properties": {
                "name": {
                        "type": "string",
                        "description": "相机物体名称"
                },
                "target": {
                        "type": "array",
                        "description": "要对准的目标坐标 [x, y, z]，默认世界原点",
                        "items": {
                                "type": "number"
                        },
                        "minItems": 3,
                        "maxItems": 3
                }
        },
        "required": [
                "name"
        ],
        "additionalProperties": false
}),
    bridgeTool("view.front", "把 3D 视口切换到正视图（前视图）", {
        "type": "object",
        "properties": {},
        "additionalProperties": false
}),
    bridgeTool("view.set_axis", "把 3D 视口切到指定正交视图", {
        type: "object",
        properties: {
            view: {
                type: "string",
                description: "front/right/top/back/left/bottom",
                enum: ["front", "right", "top", "back", "left", "bottom"],
            },
        },
        required: ["view"],
        additionalProperties: false,
    }),
    bridgeTool("render.view", "把指定物体渲成一张正交 PNG，并验收文件（存在/非空/PNG）", {
        type: "object",
        properties: {
            name: { type: "string", description: "物体名称" },
            view: {
                type: "string",
                description: "视图，默认 front",
                enum: ["front", "right", "top", "back", "left", "bottom"],
            },
            path: { type: "string", description: "输出 PNG 路径，省略则写临时目录" },
            resolution: { type: "number", description: "边长像素，默认 512" },
        },
        required: ["name"],
        additionalProperties: false,
    }),
    bridgeTool("render.views", "按名称渲单个物体的多张正交 PNG。多部件模型不要为此做布尔合并，改用 render.scene_views", {
        type: "object",
        properties: {
            name: { type: "string", description: "物体名称" },
            output_dir: { type: "string", description: "输出目录，省略则用临时目录" },
            views: {
                type: "array",
                description: "视图列表，默认 front,right,top,back",
            },
            resolution: { type: "number", description: "边长像素，默认 512" },
        },
        required: ["name"],
        additionalProperties: false,
    }),
    bridgeTool("render.scene_views", "渲整个场景所有可见网格的正交 PNG（联合包围盒）。椅子等多物体保持分开即可，不要布尔合并", {
        type: "object",
        properties: {
            output_dir: { type: "string", description: "输出目录，省略则用临时目录" },
            views: {
                type: "array",
                description: "视图列表，默认 front,right,top",
            },
            resolution: { type: "number", description: "边长像素，默认 512" },
        },
        additionalProperties: false,
    }),
    bridgeTool("render.validate_views", "只检查已有多视图 PNG 是否齐、是否合法，不重新渲染", {
        type: "object",
        properties: {
            output_dir: { type: "string", description: "图片所在目录" },
            name: { type: "string", description: "物体名，用于拼文件名 object_view.png" },
            views: { type: "array", description: "期望的视图列表" },
        },
        required: ["output_dir"],
        additionalProperties: false,
    }),
];
