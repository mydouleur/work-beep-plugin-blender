// 插件工具声明：工具名 ↔ 桥命令的映射收在这里（单一数据源）。
// 命名空间前缀 "blender." 由 Host 注册表强制校验。
import type { PluginTool } from "@beep/sdk";
import { state } from "./state";

export const tools: PluginTool[] = [
    {
        name: "blender.view_front",
        description: "把 Blender 的 3D 视口切换到正视图",
        parameters: { type: "object", properties: {}, additionalProperties: false },
        async run(_args, ctx) {
            if (!state.port) throw new Error("Blender 未启动或桥未就绪");
            const data = await ctx.call(state.port, "view.front", {});
            return JSON.stringify(data);
        },
    },
    {
        name: "blender.mesh_stats",
        description: "查看指定网格对象的顶点数、边数和面数",
        parameters: {
            type: "object",
            properties: {
                name: { type: "string", description: "网格对象名称" },
            },
            required: ["name"],
            additionalProperties: false,
        },
        async run(args, ctx) {
            if (!state.port) throw new Error("Blender 未启动或桥未就绪");
            const data = await ctx.call(state.port, "mesh.stats", args);
            return JSON.stringify(data);
        },
    },
];
