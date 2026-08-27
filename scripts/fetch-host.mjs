// 从 work-beep 的 GitHub Release 下载打包好的主程序，解压为 host-app/。
// 用法：node scripts/fetch-host.mjs [tag]   （默认 v0.1.0-dev；当前只有 prerelease，
// releases/latest 会忽略 prerelease，所以默认按固定 tag 拉）
// 仅依赖 Node 18+ 与 Windows 自带 PowerShell（解 zip）。
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const REPO = "mydouleur/work-beep";
const ASSET = "beep-host-windows-x64.zip";
const tag = process.argv[2] ?? "v0.1.0-dev";

const here = path.dirname(fileURLToPath(import.meta.url));
const dst = path.resolve(here, "../host-app");
const tmp = path.resolve(here, `../.download-${ASSET}`);

const url = `https://github.com/${REPO}/releases/download/${tag}/${ASSET}`;
console.log("下载：", url);
const res = await fetch(url, { redirect: "follow" });
if (!res.ok) {
    console.error(`下载失败：HTTP ${res.status}（tag "${tag}" 存在吗？）`);
    process.exit(1);
}
fs.writeFileSync(tmp, Buffer.from(await res.arrayBuffer()));

fs.rmSync(dst, { recursive: true, force: true });
fs.mkdirSync(dst, { recursive: true });
execFileSync("powershell", [
    "-NoProfile",
    "-Command",
    `Expand-Archive -LiteralPath '${tmp}' -DestinationPath '${dst}' -Force`,
]);
fs.rmSync(tmp);
// 空目录不进 zip，补建插件目录
fs.mkdirSync(path.join(dst, "plugins"), { recursive: true });

console.log("已就绪：", dst);
console.log("用法：把插件构建产物放进 host-app/plugins/<插件id>/，双击 beep-host.exe");
