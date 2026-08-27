// definePlugin 入口：纯 TS 描述插件（View、工具、生命周期）。
// 窗口嵌入与进程拉起不在此实现——经 ctx 由 Host 传导执行（SDK 契约）。
// Blender 绿色版定位与桥脚本路径是插件自己的配置（assets 内 resolveAsset 解析）。
import { definePlugin } from "@beep/sdk";
import Panel from "./Panel.vue";
import { tools } from "./tools";
import { state } from "./state";

export default definePlugin({
    id: "blender",
    name: "Blender",
    view: Panel,
    tools,
    // 停用时清理：杀掉 Blender 子进程（Host 退出也会兜底杀全部子进程）
    async stop(ctx) {
        if (state.pid !== null) {
            await ctx.kill(state.pid);
            state.pid = null;
            state.port = null;
        }
    },
});
