// Managed Blender：经 Host runProcess 调用插件自带 fetch_blender.exe（JSON/JSONL）。
import type { HostCtx } from "./ctx";
import type { MirrorId } from "./runtime";

export const FETCH_BLENDER_REL = "tools/fetch_blender.exe";

export type FetchListVersion = {
    id: string;
    label: string;
    tags: string[];
    status: string;
    path: string | null;
    downloadable: boolean;
};

export type FetchEvent =
    | {
          status: "downloading";
          progress?: number;
          downloaded_bytes?: number;
          total_bytes?: number;
      }
    | { status: "verifying" }
    | { status: "extracting" }
    | { status: "installed"; version: string; path: string }
    | { status: "error"; message: string }
    | { ok: true; versions: FetchListVersion[] };

/** assets 目录：resolveAsset("runtime") 的父路径，作为 fetch_blender --root */
export function managedRoot(ctx: HostCtx): string {
    const runtime = ctx.resolveAsset("runtime").replace(/[/\\]+$/, "");
    const idx = Math.max(runtime.lastIndexOf("\\"), runtime.lastIndexOf("/"));
    if (idx <= 0) throw new Error("无法解析 managed root");
    return runtime.slice(0, idx);
}

export function fetchBlenderExe(ctx: HostCtx): string {
    return ctx.resolveAsset(FETCH_BLENDER_REL);
}

function parseJsonLine(line: string, where: string): unknown {
    const t = line.trim();
    if (!t) throw new Error(`${where}: 空行`);
    try {
        return JSON.parse(t);
    } catch (e) {
        throw new Error(
            `${where}: JSON 解析失败：${e instanceof Error ? e.message : String(e)}；原文：${t.slice(0, 200)}`,
        );
    }
}

export async function fetchList(ctx: HostCtx): Promise<FetchListVersion[]> {
    const exe = fetchBlenderExe(ctx);
    if (!(await ctx.exists(exe))) {
        throw new Error(`找不到 ${FETCH_BLENDER_REL}，请先 pnpm build:fetch-blender 并 deploy`);
    }
    const root = managedRoot(ctx);
    let last: FetchListVersion[] | null = null;
    const { code } = await ctx.runProcess({
        executable: exe,
        args: ["--root", root, "list"],
        cwd: root,
        onStdoutLine: (line) => {
            const obj = parseJsonLine(line, "fetch_blender list") as FetchEvent;
            if (obj && typeof obj === "object" && "ok" in obj && (obj as { ok: boolean }).ok) {
                last = (obj as { versions: FetchListVersion[] }).versions;
            }
        },
        onStderrLine: (line) => console.warn("[fetch_blender list]", line),
    });
    if (code !== 0) {
        throw new Error(`fetch_blender list 退出码 ${code}`);
    }
    if (!last) {
        throw new Error("fetch_blender list 未返回 versions JSON");
    }
    return last;
}

export async function fetchDownload(
    ctx: HostCtx,
    version: string,
    mirror: MirrorId,
    force: boolean,
    onEvent: (ev: FetchEvent) => void,
): Promise<void> {
    const exe = fetchBlenderExe(ctx);
    if (!(await ctx.exists(exe))) {
        throw new Error(`找不到 ${FETCH_BLENDER_REL}，请先 pnpm build:fetch-blender 并 deploy`);
    }
    const root = managedRoot(ctx);
    const args = ["--root", root, "download", "--version", version, "--mirror", mirror];
    if (force) args.push("--force");

    let sawError: string | null = null;
    let sawInstalled = false;
    const stderrLines: string[] = [];

    const { code } = await ctx.runProcess({
        executable: exe,
        args,
        cwd: root,
        onStdoutLine: (line) => {
            const obj = parseJsonLine(line, "fetch_blender download") as FetchEvent;
            onEvent(obj);
            if (obj && typeof obj === "object" && "status" in obj) {
                const st = (obj as { status: string }).status;
                if (st === "error") {
                    sawError = (obj as { message?: string }).message ?? "未知错误";
                } else if (st === "installed") {
                    sawInstalled = true;
                }
            }
        },
        onStderrLine: (line) => {
            stderrLines.push(line);
            console.warn("[fetch_blender download]", line);
        },
    });

    if (sawError) throw new Error(sawError);
    if (code !== 0) {
        const hint = stderrLines
            .filter((l) => /PermissionError|拒绝访问|被占用|Error|Traceback/i.test(l))
            .slice(-3)
            .join(" | ");
        throw new Error(
            hint
                ? `fetch_blender download 退出码 ${code}：${hint}`
                : `fetch_blender download 退出码 ${code}`,
        );
    }
    if (!sawInstalled) throw new Error("download 结束但未收到 installed 事件");
}
