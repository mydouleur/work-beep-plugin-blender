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

// 插件代码经 resolveAsset("runtime/...") 访问，锚点是 <部署目录>/assets/runtime
const runtimeLink = path.join(dst, "assets", "runtime");
if (!fs.existsSync(runtimeLink)) {
    const runtimeSrc = path.resolve(here, "../runtime");
    if (fs.existsSync(runtimeSrc)) {
        fs.symlinkSync(runtimeSrc, runtimeLink, "junction");
        console.log("runtime 联接 ->", runtimeSrc);
    } else {
        console.warn("runtime/ 不存在：请先运行 python scripts/fetch_blender.py 下载 Blender 绿色版，再重新 deploy");
    }
}
console.log("已部署到", dst);
