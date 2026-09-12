// Host 已实现、SDK 包尚未发版时的补充方法。运行期从 inject 的 ctx 上取。
import type { PluginContext } from "@beep/sdk";

export type HostCtx = PluginContext & {
    exists(path: string): Promise<boolean>;
    /** @deprecated Managed 下载已改走 fetch_blender.exe + runProcess */
    download(
        url: string,
        dest: string,
        onProgress?: (done: number, total: number) => void,
    ): Promise<void>;
    /** @deprecated Managed 解压已改走 fetch_blender.exe */
    extractZip(zipPath: string, destDir: string): Promise<void>;
    removePath(path: string): Promise<void>;
    pickFile(opts?: {
        title?: string;
        filters?: { name: string; extensions: string[] }[];
    }): Promise<string | null>;
    runCapture(
        executable: string,
        args: string[],
        opts?: { timeoutMs?: number },
    ): Promise<{ code: number; stdout: string; stderr: string }>;
    readText(path: string): Promise<string>;
    writeText(path: string, contents: string): Promise<void>;
    runProcess(opts: {
        executable: string;
        args: string[];
        cwd?: string;
        onStdoutLine?: (line: string) => void;
        onStderrLine?: (line: string) => void;
    }): Promise<{ code: number }>;
};

export function hostCtx(ctx: PluginContext): HostCtx {
    return ctx as HostCtx;
}

/** Managed 绿色版：需要 runProcess（fetch_blender.exe） */
export function canManageRuntime(ctx: HostCtx): boolean {
    return typeof ctx.runProcess === "function" && typeof ctx.exists === "function";
}

export function canUseExternal(ctx: HostCtx): boolean {
    return (
        typeof ctx.pickFile === "function" &&
        typeof ctx.runCapture === "function" &&
        typeof ctx.readText === "function" &&
        typeof ctx.writeText === "function"
    );
}
