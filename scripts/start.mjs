// 一键调试（单克隆流程）：确保 host-app/ 主程序在位（缺失则自动拉 GitHub Release），
// 把 dist/ 组装进 host-app/plugins/blender/（runtime 用 junction 挂入），然后启动 beep-host.exe。
// 前置：已 pnpm install && pnpm build（dist/ 不存在会直接提示）。
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const dist = path.join(root, "dist");
const hostApp = path.join(root, "host-app");
const exe = path.join(hostApp, "beep-host.exe");

if (!fs.existsSync(dist)) {
    console.error("dist/ 不存在，请先 pnpm build");
    process.exit(1);
}

// 主程序不在位则自动拉 Release（默认 tag 见 fetch-host.mjs，可手动重跑覆盖）
if (!fs.existsSync(exe)) {
    console.log("host-app/ 不在位，拉取主程序 Release…");
    execFileSync(process.execPath, [path.join(here, "fetch-host.mjs")], { stdio: "inherit" });
}

// 组装插件：dist → host-app/plugins/blender/
const dst = path.join(hostApp, "plugins", "blender");
fs.mkdirSync(dst, { recursive: true });
fs.cpSync(dist, dst, { recursive: true });

// runtime（Blender 绿色版）以 junction 挂进 assets/，不存在则提示下载
const runtimeLink = path.join(dst, "assets", "runtime");
if (!fs.existsSync(runtimeLink)) {
    const runtimeSrc = path.join(root, "runtime");
    if (fs.existsSync(runtimeSrc)) {
        fs.symlinkSync(runtimeSrc, runtimeLink, "junction");
        console.log("runtime 联接 ->", runtimeSrc);
    } else {
        console.warn("runtime/ 不存在：请先运行 python scripts/fetch_blender.py 下载 Blender 绿色版");
    }
}

if (!fs.existsSync(exe)) {
    console.error(`未找到主程序：${exe}（Release 包结构与预期不符？）`);
    process.exit(1);
}
console.log("启动：", exe);
spawn(exe, { detached: true, stdio: "ignore" }).unref();
