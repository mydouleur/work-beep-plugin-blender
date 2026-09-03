// 校验 src/tools.ts 声明的桥命令与 assets/bridge/commands/ 的 @command 一一对应。
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const toolsSrc = fs.readFileSync(path.join(root, "src/tools.ts"), "utf8");
const tsCmds = new Set(
    [...toolsSrc.matchAll(/bridgeTool\(\s*"([^"]+)"/g)].map((m) => m[1]),
);
for (const m of toolsSrc.matchAll(/ctx\.call\(\s*[^,]+,\s*"([^"]+)"/g)) {
    tsCmds.add(m[1]);
}

const commandsDir = path.join(root, "assets/bridge/commands");
const pyCmds = new Set();
for (const name of fs.readdirSync(commandsDir)) {
    if (!name.endsWith(".py") || name === "__init__.py") continue;
    const text = fs.readFileSync(path.join(commandsDir, name), "utf8");
    for (const m of text.matchAll(/@command\(\s*"([^"]+)"/g)) {
        pyCmds.add(m[1]);
    }
}

const missingPy = [...tsCmds].filter((c) => !pyCmds.has(c)).sort();
const missingTs = [...pyCmds].filter((c) => !tsCmds.has(c)).sort();
if (missingPy.length || missingTs.length) {
    console.error("工具声明与桥命令不同步");
    if (missingPy.length) console.error("TS 有、Python 无：", missingPy.join(", "));
    if (missingTs.length) console.error("Python 有、TS 无：", missingTs.join(", "));
    process.exit(1);
}
console.log(`同步检查通过：${tsCmds.size} 条命令`);
