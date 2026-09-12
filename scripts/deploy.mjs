// 部署：dist/* → ../work-beep/plugins/blender/（Host 运行时加载器扫描的位置）。
// Blender 绿色版 runtime/ 用目录联接（junction）挂进插件目录的 assets/ 下，
// 避免复制数 GB；不存在则提示先跑 scripts/fetch_blender.py 下载。
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.resolve(here, "../dist");
const dst = path.resolve(here, "../../work-beep/plugins/blender");

if (!fs.existsSync(dist)) {
    console.error("dist/ 不存在，请先 pnpm build");
    process.exit(1);
}

fs.mkdirSync(dst, { recursive: true });
fs.cpSync(dist, dst, { recursive: true });

// 确保 fetch_blender.exe 在 assets/tools（Panel Managed 下载依赖）
const toolsDst = path.join(dst, "assets", "tools");
const toolsSrcCandidates = [
    path.resolve(here, "../assets/tools/fetch_blender.exe"),
    path.resolve(here, "../scripts/dist/fetch_blender.exe"),
];
fs.mkdirSync(toolsDst, { recursive: true });
const toolsExe = path.join(toolsDst, "fetch_blender.exe");
if (!fs.existsSync(toolsExe)) {
    const hit = toolsSrcCandidates.find((p) => fs.existsSync(p));
    if (hit) {
        fs.copyFileSync(hit, toolsExe);
        console.log("已放入 fetch_blender.exe <-", hit);
    } else {
        console.warn("警告：未找到 fetch_blender.exe，请先 pnpm build:fetch-blender");
    }
}

// 插件代码经 resolveAsset("runtime/...") 访问，锚点是 <部署目录>/assets/runtime
const runtimeLink = path.join(dst, "assets", "runtime");
const runtimeSrc = path.resolve(here, "../runtime");
if (!fs.existsSync(runtimeLink)) {
    if (fs.existsSync(runtimeSrc)) {
        fs.symlinkSync(runtimeSrc, runtimeLink, "junction");
        console.log("runtime 联接 ->", runtimeSrc);
    } else {
        fs.mkdirSync(runtimeLink, { recursive: true });
        console.log("已创建空的 assets/runtime，可在面板里下载绿色版");
    }
}
console.log("已部署到", dst);
