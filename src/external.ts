// 用户自装 Blender（External）：只存路径配置，不托管、不删除用户安装目录。
import type { HostCtx } from "./ctx";

export type ExternalBlender = {
    id: string;
    path: string;
    version: string;
    label: string;
};

type StoreFile = { externals: ExternalBlender[] };

const CONFIG_REL = "config/external.json";

/** bridge 最低兼容版本（主.次） */
export const MIN_BRIDGE_MAJOR = 3;
export const MIN_BRIDGE_MINOR = 6;

export function configPath(ctx: HostCtx): string {
    return ctx.resolveAsset(CONFIG_REL);
}

export async function loadExternals(ctx: HostCtx): Promise<ExternalBlender[]> {
    try {
        const text = await ctx.readText(configPath(ctx));
        const data = JSON.parse(text) as StoreFile;
        return Array.isArray(data.externals) ? data.externals : [];
    } catch {
        return [];
    }
}

export async function saveExternals(ctx: HostCtx, list: ExternalBlender[]): Promise<void> {
    const body: StoreFile = { externals: list };
    await ctx.writeText(configPath(ctx), JSON.stringify(body, null, 2));
}

/** 从 `blender --version` 输出解析版本号 */
export function parseBlenderVersion(text: string): string | null {
    const m = text.match(/Blender\s+(\d+\.\d+(?:\.\d+)?)/i);
    return m?.[1] ?? null;
}

export function isBridgeCompatible(version: string): boolean {
    const parts = version.split(".").map((x) => Number(x));
    const major = parts[0] ?? 0;
    const minor = parts[1] ?? 0;
    if (major > MIN_BRIDGE_MAJOR) return true;
    if (major < MIN_BRIDGE_MAJOR) return false;
    return minor >= MIN_BRIDGE_MINOR;
}

export function shortPath(path: string, max = 42): string {
    if (path.length <= max) return path;
    return "…" + path.slice(-(max - 1));
}

export async function probeExternalExe(
    ctx: HostCtx,
    path: string,
): Promise<{ version: string; label: string }> {
    const lower = path.replace(/\//g, "\\").toLowerCase();
    if (!lower.endsWith("\\blender.exe") && !lower.endsWith("/blender.exe")) {
        // 仍允许用户选其它名字的 exe，只要 --version 能解析
    }
    if (!(await ctx.exists(path))) {
        throw new Error("文件不存在");
    }
    const cap = await ctx.runCapture(path, ["--version"], { timeoutMs: 20_000 });
    const text = `${cap.stdout}\n${cap.stderr}`;
    const version = parseBlenderVersion(text);
    if (!version) {
        throw new Error("无法识别为 Blender（--version 无版本号）");
    }
    if (!isBridgeCompatible(version)) {
        throw new Error(
            `Blender ${version} 过旧，桥脚本需要 ≥ ${MIN_BRIDGE_MAJOR}.${MIN_BRIDGE_MINOR}`,
        );
    }
    return { version, label: `Blender ${version}` };
}

export function makeExternalId(path: string, version: string): string {
    // 稳定 id：路径 hash 简化为长度+末段
    const base = path.replace(/\\/g, "/").split("/").pop() ?? "blender.exe";
    return `ext-${version}-${base}-${path.length}`;
}
