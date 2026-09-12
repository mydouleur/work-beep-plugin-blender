// 一键调试：
// - 旁边有 work-beep（或 BEEP_HOST_DIR）：deploy 插件后跑 Host 的 `pnpm tauri dev`（本地最新）
// - 否则：拉 GitHub Release 到 host-app/，启动打包好的 exe（不含未发布的 Host 改动）
// 前置：本仓已 pnpm install；并列 Host 还需在 work-beep 里 pnpm install
import { execFileSync, spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const dist = path.join(root, "dist");
const hostRepo = path.resolve(process.env.BEEP_HOST_DIR ?? path.join(root, "../work-beep"));
const siblingHost = fs.existsSync(path.join(hostRepo, "package.json"))
    && fs.existsSync(path.join(hostRepo, "src-tauri"));

function ensureDist() {
    if (fs.existsSync(dist)) return;
    console.log("dist/ 不存在，先 pnpm build…");
    const r = spawnSync("pnpm", ["build"], { cwd: root, stdio: "inherit", shell: true });
    if (r.status !== 0) process.exit(r.status ?? 1);
}

if (siblingHost) {
    ensureDist();
    execFileSync(process.execPath, [path.join(here, "deploy.mjs")], { stdio: "inherit" });
    if (!fs.existsSync(path.join(hostRepo, "node_modules"))) {
        console.error(`Host 未安装依赖：请先在 ${hostRepo} 执行 pnpm install`);
        process.exit(1);
    }
    console.log("检测到并列 Host，启动 pnpm tauri dev（本地源码，不是 Release exe）…");
    console.log("  ", hostRepo);
    const r = spawnSync("pnpm", ["tauri", "dev"], { cwd: hostRepo, stdio: "inherit", shell: true });
    process.exit(r.status ?? 1);
}

// —— 单克隆回退：GitHub Release 里的旧 exe ——
const hostApp = path.join(root, "host-app");
const exe = path.join(hostApp, "beep-host.exe");

ensureDist();

if (!fs.existsSync(exe)) {
    console.log("host-app/ 不在位，拉取主程序 Release…");
    execFileSync(process.execPath, [path.join(here, "fetch-host.mjs")], { stdio: "inherit" });
}

const dst = path.join(hostApp, "plugins", "blender");
fs.mkdirSync(dst, { recursive: true });
fs.cpSync(dist, dst, { recursive: true });

const runtimeLink = path.join(dst, "assets", "runtime");
const runtimeSrc = path.join(root, "runtime");
if (!fs.existsSync(runtimeLink)) {
    if (fs.existsSync(runtimeSrc)) {
        fs.symlinkSync(runtimeSrc, runtimeLink, "junction");
        console.log("runtime 联接 ->", runtimeSrc);
    } else {
        fs.mkdirSync(runtimeLink, { recursive: true });
        console.log("已创建空的 assets/runtime，可在面板里下载绿色版（需新版 Host）");
    }
}

if (!fs.existsSync(exe)) {
    console.error(`未找到主程序：${exe}（Release 包结构与预期不符？）`);
    process.exit(1);
}
console.warn("启动的是 GitHub Release exe，不含本地 work-beep 未发布改动。");
console.warn("要跑最新 Host：把 work-beep 放在本仓旁边（或设 BEEP_HOST_DIR）再 pnpm start。");
console.log("启动：", exe);
spawn(exe, { detached: true, stdio: "ignore" }).unref();
