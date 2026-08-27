<script setup lang="ts">
// Blender 面板：启动按钮 + 状态文本；启动后把 Blender 主窗口嵌入本面板。
// 所有能力经 inject(CTX_KEY) 拿到的 PluginContext 传导，插件不直接依赖 @tauri-apps/*。
import { inject, onBeforeUnmount, onMounted, ref } from "vue";
import { CTX_KEY } from "@beep/sdk";
import { state } from "./state";

const ctx = inject(CTX_KEY);
if (!ctx) throw new Error("Blender 面板必须在 Host 的插件容器内使用");

const status = ref("Blender 未启动");
const starting = ref(false);
// Blender 窗口是否已嵌入本面板
const embedded = ref(false);
const rootRef = ref<HTMLElement | null>(null);

async function startBlender() {
    if (starting.value || state.pid !== null) return;
    starting.value = true;
    status.value = "正在启动 Blender…";
    try {
        // 通用拉起：{port} 占位符由 Host 挑空闲端口替换并等桥就绪
        const info = await ctx.launch(
            ctx.resolveAsset("runtime/blender-5.2.1-windows-x64/blender-5.2.1-windows-x64/blender.exe"),
            ["--python", ctx.resolveAsset("bridge/blender_bridge.py"), "--", "--port", "{port}"],
        );
        state.pid = info.pid;
        state.port = info.port;
        status.value = `Blender 已启动，桥接端口 ${info.port}`;
        // 把 Blender 主窗口嵌入本面板
        const rect = rootRef.value ? ctx.rectOf(rootRef.value) : null;
        if (rect && state.pid !== null) {
            await ctx.embed(state.pid, rect);
            embedded.value = true;
        }
    } catch (e) {
        status.value = `启动失败：${e instanceof Error ? e.message : String(e)}`;
        state.pid = null;
        state.port = null;
    } finally {
        starting.value = false;
    }
}

let stopWatch: (() => void) | null = null;
onMounted(() => {
    // 面板尺寸变化（窗口缩放、分隔条拖动、应用窗口移动）时同步已嵌入窗口的位置
    if (rootRef.value) {
        stopWatch = ctx.watchRect(rootRef.value, (rect) => {
            if (embedded.value && state.pid !== null) {
                ctx.syncRect(state.pid, rect).catch((e) => console.error("同步 Blender 窗口失败：", e));
            }
        });
    }
});
onBeforeUnmount(() => stopWatch?.());
</script>

<template>
    <div ref="rootRef" class="blender-panel">
        <!-- 嵌入后 Blender 窗口覆盖本面板，隐藏启动控件 -->
        <template v-if="!embedded">
            <span class="status">{{ status }}</span>
            <button class="launch-btn" :disabled="starting" @click="startBlender">
                启动 Blender
            </button>
        </template>
    </div>
</template>

<style scoped>
.blender-panel {
    position: relative;
    height: 100%;
}

.status {
    position: absolute;
    top: 16px;
    left: 16px;
    font-size: 0.875rem;
    color: #ddd;
    opacity: 0.7;
}

/* 插件自带样式（不能用 Host 内部组件）：右下角实体按钮 */
.launch-btn {
    position: absolute;
    right: 32px;
    bottom: 32px;
    padding: 12px 28px;
    font-size: 1rem;
    color: #1a1a1a;
    background: #e8e8e8;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}

.launch-btn:hover {
    background: #ffffff;
}

.launch-btn:disabled {
    opacity: 0.5;
    cursor: default;
}
</style>
