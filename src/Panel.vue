<script setup lang="ts">
// Blender 面板：托管版本卡（fetch_blender.exe）+ 本机 External + Tripo 占位；启动后嵌入。
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { CTX_KEY } from "@beep/sdk";
import { canManageRuntime, canUseExternal, hostCtx } from "./ctx";
import {
    loadExternals,
    makeExternalId,
    probeExternalExe,
    saveExternals,
    shortPath,
    type ExternalBlender,
} from "./external";
import { fetchDownload, fetchList } from "./fetchClient";
import { state } from "./state";
import {
    BLENDER_CATALOG,
    blenderExeRel,
    humanBytes,
    type CatalogEntry,
    type MirrorId,
} from "./runtime";

const raw = inject(CTX_KEY);
if (!raw) throw new Error("Blender 面板必须在 Host 的插件容器内使用");
const ctx = hostCtx(raw);

type CardStatus =
    | "checking"
    | "installed"
    | "not_installed"
    | "downloading"
    | "verifying"
    | "extracting"
    | "coming_soon"
    | "error";

type CardState = {
    status: CardStatus;
    progressDone: number;
    progressTotal: number;
    message: string;
};

const cards = reactive<Record<string, CardState>>(
    Object.fromEntries(
        BLENDER_CATALOG.map((e) => [
            e.id,
            {
                status: e.downloadable ? ("checking" as CardStatus) : ("coming_soon" as CardStatus),
                progressDone: 0,
                progressTotal: 0,
                message: "",
            },
        ]),
    ),
);

const externals = ref<ExternalBlender[]>([]);
const status = ref("正在检查绿色版…");
const starting = ref(false);
const hostOk = ref(true);
const externalOk = ref(true);
const picking = ref(false);
const mirror = ref<MirrorId>("aliyun");
const embedded = ref(false);
const rootRef = ref<HTMLElement | null>(null);

const anyDownloading = computed(() =>
    Object.values(cards).some(
        (c) => c.status === "downloading" || c.status === "verifying" || c.status === "extracting",
    ),
);

function exePath(version: string) {
    return ctx.resolveAsset(blenderExeRel(version));
}

function progressPct(c: CardState) {
    if (c.progressTotal <= 0) return 0;
    return Math.min(100, Math.round((c.progressDone / c.progressTotal) * 100));
}

function tagLabel(e: CatalogEntry): string | null {
    if (e.tags.includes("recommended")) return "Recommended";
    if (e.tags.includes("lts")) return "LTS";
    return null;
}

function applyListToCards(versions: { id: string; status: string; downloadable: boolean }[]) {
    const byId = new Map(versions.map((v) => [v.id, v]));
    for (const e of BLENDER_CATALOG) {
        const c = cards[e.id];
        const row = byId.get(e.id);
        if (!e.downloadable) {
            c.status = "coming_soon";
            continue;
        }
        if (!row) {
            c.status = "not_installed";
            continue;
        }
        if (row.status === "installed") c.status = "installed";
        else if (row.status === "coming_soon") c.status = "coming_soon";
        else c.status = "not_installed";
        c.message = "";
    }
}

async function probeManaged() {
    if (!canManageRuntime(ctx)) {
        hostOk.value = false;
        for (const e of BLENDER_CATALOG) {
            if (e.downloadable) {
                cards[e.id].status = "error";
                cards[e.id].message = "Host 无 runProcess";
            }
        }
        status.value = "当前 Host 不支持 fetch_blender.exe，请用 work-beep 源码 pnpm tauri dev";
        return;
    }
    hostOk.value = true;
    try {
        const versions = await fetchList(ctx);
        applyListToCards(versions);
    } catch (e) {
        console.warn("fetch_blender list 失败，回退 exists：", e);
        await Promise.all(
            BLENDER_CATALOG.map(async (entry) => {
                const c = cards[entry.id];
                if (!entry.downloadable) {
                    c.status = "coming_soon";
                    return;
                }
                c.status = (await ctx.exists(exePath(entry.id))) ? "installed" : "not_installed";
            }),
        );
        status.value = `list 失败（已回退探测）：${e instanceof Error ? e.message : String(e)}`;
        return;
    }
}

async function probeExternals() {
    if (!canUseExternal(ctx)) {
        externalOk.value = false;
        externals.value = [];
        return;
    }
    externalOk.value = true;
    const list = await loadExternals(ctx);
    const kept: ExternalBlender[] = [];
    for (const item of list) {
        if (await ctx.exists(item.path)) kept.push(item);
    }
    if (kept.length !== list.length) {
        await saveExternals(ctx, kept);
    }
    externals.value = kept;
}

async function probe() {
    await probeManaged();
    await probeExternals();
    if (state.pid !== null) {
        status.value = `Blender 已启动，桥接端口 ${state.port}`;
        return;
    }
    if (hostOk.value) {
        status.value = "选择托管版本，或使用本机已安装的 Blender";
    }
}

async function launchExe(exe: string, label: string) {
    if (starting.value || anyDownloading.value || state.pid !== null) return;
    if (!(await ctx.exists(exe))) {
        status.value = `未找到：${exe}`;
        return;
    }
    starting.value = true;
    status.value = `正在启动 ${label}…`;
    try {
        const info = await ctx.launch(exe, [
            "--python",
            ctx.resolveAsset("bridge/blender_bridge.py"),
            "--",
            "--port",
            "{port}",
        ]);
        state.pid = info.pid;
        state.port = info.port;
        status.value = `${label} 已启动，桥接端口 ${info.port}`;
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

async function startManaged(version: string) {
    await launchExe(exePath(version), `Blender ${version}`);
}

async function startExternal(item: ExternalBlender) {
    await launchExe(item.path, item.label);
}

/** 下载/重装前结束面板拉起的 Blender，避免 DLL 被占用 */
async function stopManagedIfRunning() {
    if (state.pid === null) return;
    status.value = "正在结束已启动的 Blender…";
    try {
        await ctx.kill(state.pid);
    } catch (e) {
        console.warn("结束 Blender 失败：", e);
    }
    state.pid = null;
    state.port = null;
    embedded.value = false;
    await new Promise((r) => setTimeout(r, 800));
}

async function installBlender(version: string, force = false) {
    const entry = BLENDER_CATALOG.find((e) => e.id === version);
    if (!entry?.downloadable) return;
    if (anyDownloading.value || starting.value) return;
    if (!hostOk.value) return;

    await stopManagedIfRunning();

    // 非强制：已装好就别再解压覆盖
    if (!force && (await ctx.exists(exePath(version)))) {
        cards[version].status = "installed";
        cards[version].message = "";
        status.value = `已安装 Blender ${version}，可以启动`;
        try {
            applyListToCards(await fetchList(ctx));
        } catch {
            /* ignore */
        }
        return;
    }

    const c = cards[version];
    c.status = "downloading";
    c.progressDone = 0;
    c.progressTotal = 0;
    c.message = "";
    status.value = `正在通过 fetch_blender.exe 下载 Blender ${version}…`;

    try {
        await fetchDownload(ctx, version, mirror.value, force, (ev) => {
            if (!("status" in ev)) return;
            if (ev.status === "downloading") {
                c.status = "downloading";
                c.progressDone = ev.downloaded_bytes ?? 0;
                c.progressTotal = ev.total_bytes ?? 0;
                if (c.progressTotal > 0) {
                    status.value = `${version} 下载中 ${humanBytes(c.progressDone)} / ${humanBytes(c.progressTotal)}`;
                } else {
                    status.value = `${version} 下载中 ${humanBytes(c.progressDone)}`;
                }
            } else if (ev.status === "verifying") {
                c.status = "verifying";
                status.value = `${version} 校验中…`;
            } else if (ev.status === "extracting") {
                c.status = "extracting";
                status.value = `${version} 解压中…`;
            } else if (ev.status === "installed") {
                c.status = "installed";
                status.value = `已安装 Blender ${ev.version}，可以启动`;
            } else if (ev.status === "error") {
                c.status = "error";
                c.message = ev.message;
                status.value = `下载失败：${ev.message}`;
            }
        });
        try {
            const versions = await fetchList(ctx);
            applyListToCards(versions);
        } catch {
            c.status = "installed";
        }
        if (c.status !== "error") {
            status.value = `已安装 Blender ${version}，可以启动`;
        }
    } catch (e) {
        c.status = "error";
        c.message = e instanceof Error ? e.message : String(e);
        status.value = `下载失败：${c.message}`;
    }
}

async function reinstallBlender(version: string) {
    if (anyDownloading.value || starting.value) return;
    if (!confirm(`将重新下载并覆盖平台托管的 Blender ${version}，确定？`)) return;
    await installBlender(version, true);
}

async function addExternal() {
    if (!externalOk.value || picking.value || starting.value || anyDownloading.value) return;
    picking.value = true;
    status.value = "请选择本机 blender.exe…";
    try {
        const path = await ctx.pickFile({
            title: "选择本机 Blender（blender.exe）",
            filters: [{ name: "Blender", extensions: ["exe"] }],
        });
        if (!path) {
            status.value = "已取消选择";
            return;
        }
        status.value = "正在探测 Blender 版本…";
        const { version, label } = await probeExternalExe(ctx, path);
        const id = makeExternalId(path, version);
        const next = externals.value.filter((e) => e.path.toLowerCase() !== path.toLowerCase());
        next.push({ id, path, version, label });
        await saveExternals(ctx, next);
        externals.value = next;
        status.value = `已添加本机 ${label}（External，仅启动，不卸载）`;
    } catch (e) {
        status.value = `添加失败：${e instanceof Error ? e.message : String(e)}`;
    } finally {
        picking.value = false;
    }
}

async function removeExternal(item: ExternalBlender) {
    if (starting.value || anyDownloading.value) return;
    if (!confirm(`从列表移除「${item.label}」？\n不会删除本机安装：\n${item.path}`)) return;
    const next = externals.value.filter((e) => e.id !== item.id);
    await saveExternals(ctx, next);
    externals.value = next;
    status.value = `已从列表移除 ${item.label}`;
}

let stopWatch: (() => void) | null = null;
onMounted(() => {
    probe();
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
        <template v-if="!embedded">
            <div class="manager">
                <p class="status">{{ status }}</p>

                <label class="mirror" v-if="hostOk">
                    镜像
                    <select v-model="mirror" :disabled="anyDownloading">
                        <option value="aliyun">阿里云（国内）</option>
                        <option value="official">官方</option>
                        <option value="freedif">Freedif</option>
                    </select>
                </label>

                <section class="section">
                    <h2 class="section-title">Blender Runtime</h2>
                    <div class="row">
                        <article
                            v-for="entry in BLENDER_CATALOG"
                            :key="entry.id"
                            class="card"
                            :class="{
                                disabled: cards[entry.id].status === 'coming_soon',
                                busy: cards[entry.id].status === 'downloading',
                            }"
                        >
                            <div class="card-head">
                                <h3 class="card-title">{{ entry.label }}</h3>
                                <span v-if="tagLabel(entry)" class="badge">{{ tagLabel(entry) }}</span>
                            </div>
                            <p class="card-meta">Managed by Work Beep</p>
                            <p class="card-status">
                                <template v-if="cards[entry.id].status === 'checking'">检查中…</template>
                                <template v-else-if="cards[entry.id].status === 'installed'">已安装</template>
                                <template v-else-if="cards[entry.id].status === 'not_installed'">未安装</template>
                                <template v-else-if="cards[entry.id].status === 'downloading'">
                                    下载中 {{ progressPct(cards[entry.id]) }}%
                                </template>
                                <template v-else-if="cards[entry.id].status === 'verifying'">校验中…</template>
                                <template v-else-if="cards[entry.id].status === 'extracting'">解压中…</template>
                                <template v-else-if="cards[entry.id].status === 'coming_soon'">Coming soon</template>
                                <template v-else>失败</template>
                            </p>
                            <div
                                v-if="cards[entry.id].status === 'downloading'"
                                class="bar"
                            >
                                <div
                                    class="bar-fill"
                                    :style="{ width: progressPct(cards[entry.id]) + '%' }"
                                />
                            </div>
                            <p v-if="cards[entry.id].message" class="card-err">{{ cards[entry.id].message }}</p>
                            <div class="card-actions">
                                <template v-if="cards[entry.id].status === 'coming_soon'">
                                    <button class="ghost-btn" disabled>Coming soon</button>
                                </template>
                                <template v-else-if="cards[entry.id].status === 'installed'">
                                    <button
                                        class="launch-btn"
                                        :disabled="starting || anyDownloading || state.pid !== null"
                                        @click="startManaged(entry.id)"
                                    >
                                        {{ starting ? "启动中…" : "启动" }}
                                    </button>
                                    <button
                                        class="ghost-btn"
                                        :disabled="starting || anyDownloading || state.pid !== null"
                                        @click="reinstallBlender(entry.id)"
                                    >
                                        重装
                                    </button>
                                </template>
                                <template v-else>
                                    <button
                                        class="launch-btn"
                                        :disabled="!hostOk || anyDownloading || starting || state.pid !== null"
                                        @click="installBlender(entry.id, false)"
                                    >
                                        {{ anyDownloading && cards[entry.id].status !== "not_installed" && cards[entry.id].status !== "error" && cards[entry.id].status !== "installed" ? "进行中…" : "下载" }}
                                    </button>
                                </template>
                            </div>
                        </article>

                        <article
                            v-for="item in externals"
                            :key="item.id"
                            class="card external"
                        >
                            <div class="card-head">
                                <h3 class="card-title">{{ item.label }}</h3>
                                <span class="badge">External</span>
                            </div>
                            <p class="card-meta" :title="item.path">{{ shortPath(item.path) }}</p>
                            <p class="card-status">本机安装 · 仅启动</p>
                            <div class="card-actions">
                                <button
                                    class="launch-btn"
                                    :disabled="starting || anyDownloading || state.pid !== null"
                                    @click="startExternal(item)"
                                >
                                    {{ starting ? "启动中…" : "启动" }}
                                </button>
                                <button
                                    class="ghost-btn"
                                    :disabled="starting || anyDownloading || state.pid !== null"
                                    @click="removeExternal(item)"
                                >
                                    移除
                                </button>
                            </div>
                        </article>

                        <article class="card add-card" v-if="externalOk">
                            <div class="card-head">
                                <h3 class="card-title">Use Existing…</h3>
                            </div>
                            <p class="card-status">选择本机 blender.exe</p>
                            <p class="card-hint">注入 bridge，无需装 addon</p>
                            <div class="card-actions">
                                <button
                                    class="launch-btn"
                                    :disabled="picking || starting || anyDownloading || state.pid !== null"
                                    @click="addExternal"
                                >
                                    {{ picking ? "选择中…" : "浏览…" }}
                                </button>
                            </div>
                        </article>
                        <article class="card disabled" v-else>
                            <div class="card-head">
                                <h3 class="card-title">Use Existing…</h3>
                            </div>
                            <p class="card-status">需要更新 Host</p>
                            <p class="card-hint">pickFile / runCapture 未就绪</p>
                        </article>
                    </div>
                </section>

                <section class="section">
                    <h2 class="section-title">3D Generation</h2>
                    <div class="row">
                        <article class="card disabled tripo">
                            <div class="card-head">
                                <h3 class="card-title">Tripo</h3>
                            </div>
                            <p class="card-status">Coming soon</p>
                            <p class="card-hint">Text / Image → 3D</p>
                            <div class="card-actions">
                                <button class="ghost-btn" disabled>Generate</button>
                            </div>
                        </article>
                    </div>
                </section>
            </div>
        </template>
    </div>
</template>

<style scoped>
.blender-panel {
    position: relative;
    height: 100%;
    overflow: auto;
}

.manager {
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.status {
    margin: 0;
    font-size: 0.875rem;
    color: #ddd;
    opacity: 0.85;
    line-height: 1.5;
}

.mirror {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.8125rem;
    color: #ccc;
}

.mirror select {
    padding: 4px 8px;
    color: #1a1a1a;
    background: #e8e8e8;
    border: none;
    border-radius: 4px;
}

.section {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.section-title {
    margin: 0;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: #999;
}

.row {
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    gap: 12px;
    overflow-x: auto;
    padding-bottom: 4px;
}

.card {
    flex: 0 0 200px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 14px;
    border: 1px solid #444;
    border-radius: 6px;
    background: #1e1e1e;
}

.card.external {
    border-color: #5a6a7a;
}

.card.add-card {
    border-style: dashed;
}

.card.disabled {
    opacity: 0.55;
}

.card-head {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.card-title {
    margin: 0;
    font-size: 0.9375rem;
    font-weight: 600;
    color: #eee;
}

.badge {
    font-size: 0.65rem;
    padding: 2px 6px;
    border-radius: 3px;
    background: #3a3a3a;
    color: #ccc;
    text-transform: uppercase;
}

.card-meta,
.card-status {
    margin: 0;
    font-size: 0.8125rem;
    color: #bbb;
}

.card-meta {
    font-size: 0.7rem;
    color: #888;
    word-break: break-all;
}

.card-hint,
.card-err {
    margin: 0;
    font-size: 0.75rem;
    color: #888;
}

.card-err {
    color: #e88;
}

.bar {
    height: 6px;
    background: #333;
    border-radius: 3px;
    overflow: hidden;
}

.bar-fill {
    height: 100%;
    background: #e8e8e8;
    transition: width 0.2s linear;
}

.card-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: auto;
    padding-top: 4px;
}

.launch-btn,
.ghost-btn {
    padding: 8px 14px;
    font-size: 0.875rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}

.launch-btn {
    color: #1a1a1a;
    background: #e8e8e8;
}

.launch-btn:hover:not(:disabled) {
    background: #ffffff;
}

.ghost-btn {
    color: #ddd;
    background: transparent;
    border: 1px solid #666;
}

.ghost-btn:hover:not(:disabled) {
    border-color: #aaa;
}

.launch-btn:disabled,
.ghost-btn:disabled {
    opacity: 0.5;
    cursor: default;
}
</style>
