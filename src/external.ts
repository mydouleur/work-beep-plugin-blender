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

export type FoundBlender = {
    path: string;
    version: string;
    label: string;
};

const CMD_EXE = "C:\\Windows\\System32\\cmd.exe";
const WHERE_EXE = "C:\\Windows\\System32\\where.exe";

/** 安装器常用的「Blender x.y」目录名（不是完整补丁号） */
const INSTALL_FOLDERS = [
    "Blender",
    "Blender 5.2",
    "Blender 5.1",
    "Blender 5.0",
    "Blender 4.5",
    "Blender 4.4",
    "Blender 4.3",
    "Blender 4.2",
    "Blender 4.1",
    "Blender 4.0",
    "Blender 3.6",
    "Blender 3.3",
];

export function winPath(path: string): string {
    return path.replace(/\//g, "\\");
}

export function samePath(a: string, b: string): boolean {
    return winPath(a).toLowerCase() === winPath(b).toLowerCase();
}

function isBlenderExe(path: string): boolean {
    return /(?:^|[\\/])blender\.exe$/i.test(path.trim());
}

async function readEnv(ctx: HostCtx, name: string): Promise<string | null> {
    if (!(await ctx.exists(CMD_EXE))) return null;
    try {
        const cap = await ctx.runCapture(CMD_EXE, ["/c", `echo %${name}%`], { timeoutMs: 3000 });
        const v = (cap.stdout || "").trim();
        if (!v || v.toLowerCase() === `%${name}%`.toLowerCase()) return null;
        return v;
    } catch {
        return null;
    }
}

async function listBlenderExeUnder(ctx: HostCtx, root: string): Promise<string[]> {
    if (!(await ctx.exists(CMD_EXE))) return [];
    try {
        const cap = await ctx.runCapture(
            CMD_EXE,
            ["/c", `if exist "${root}" (dir /b /s /a-d "${root}\\blender.exe")`],
            { timeoutMs: 8000 },
        );
        return (cap.stdout || "")
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter(isBlenderExe);
    } catch {
        return [];
    }
}

/** 只扫常见安装位置与 PATH，不做全盘搜索 */
export async function collectCandidateExes(ctx: HostCtx): Promise<string[]> {
    const found = new Set<string>();
    const add = (path: string) => {
        const n = winPath(path.trim());
        if (isBlenderExe(n)) found.add(n);
    };

    const programFiles = (await readEnv(ctx, "ProgramFiles")) ?? "C:\\Program Files";
    const programFilesX86 =
        (await readEnv(ctx, "ProgramFiles(x86)")) ?? "C:\\Program Files (x86)";
    const localApp = await readEnv(ctx, "LOCALAPPDATA");
    const userProfile = await readEnv(ctx, "USERPROFILE");

    const foundationRoots = [
        `${programFiles}\\Blender Foundation`,
        `${programFilesX86}\\Blender Foundation`,
    ];

    for (const root of foundationRoots) {
        for (const folder of INSTALL_FOLDERS) {
            const exe = `${root}\\${folder}\\blender.exe`;
            if (await ctx.exists(exe)) add(exe);
        }
        for (const exe of await listBlenderExeUnder(ctx, root)) add(exe);
    }

    const extras = [
        `${programFilesX86}\\Steam\\steamapps\\common\\Blender\\blender.exe`,
        `${programFiles}\\Steam\\steamapps\\common\\Blender\\blender.exe`,
    ];
    if (localApp) extras.push(`${localApp}\\Programs\\Blender\\blender.exe`);
    if (userProfile) extras.push(`${userProfile}\\scoop\\apps\\blender\\current\\blender.exe`);
    for (const exe of extras) {
        if (await ctx.exists(exe)) add(exe);
    }

    if (await ctx.exists(WHERE_EXE)) {
        try {
            const cap = await ctx.runCapture(WHERE_EXE, ["blender"], { timeoutMs: 5000 });
            for (const line of (cap.stdout || "").split(/\r?\n/)) {
                if (isBlenderExe(line)) add(line);
            }
        } catch {
            /* PATH 里没有就跳过 */
        }
    }

    return [...found];
}

function isManagedRuntime(ctx: HostCtx, path: string): boolean {
    const root = winPath(ctx.resolveAsset("runtime")).toLowerCase();
    return winPath(path).toLowerCase().startsWith(root);
}

/** 扫描本机已装 Blender，排除托管绿色版与已添加路径 */
export async function scanLocalBlenders(
    ctx: HostCtx,
    excludePaths: string[] = [],
): Promise<FoundBlender[]> {
    const skip = excludePaths.map((p) => winPath(p).toLowerCase());
    const candidates = (await collectCandidateExes(ctx)).filter((path) => {
        const key = winPath(path).toLowerCase();
        return !skip.includes(key) && !isManagedRuntime(ctx, path);
    });

    const rows = await Promise.all(
        candidates.map(async (path) => {
            try {
                const probed = await probeExternalExe(ctx, path);
                return { path, ...probed } satisfies FoundBlender;
            } catch {
                return null;
            }
        }),
    );

    return rows
        .filter((row): row is FoundBlender => row !== null)
        .sort((a, b) => b.version.localeCompare(a.version, undefined, { numeric: true }));
}
