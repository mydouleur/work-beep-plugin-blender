# AGENTS.md — work-beep-plugin-blender（Blender 插件）

## 项目概览

blenderBeeper 的 **Blender 插件**（`@beep/plugin-blender`），是 `@beep/sdk` 契约的参考实现：
Blender 绿色版拉起、窗口嵌入（仅 Windows）、bpy 桥命令工具（`blender.view_front` 等）。

- 纯 TS 描述插件，能力全经 `PluginContext` 传导（`inject(CTX_KEY)`），**不 import
  `@tauri-apps/*`**。
- 窗口嵌入/进程拉起/桥转发都不在插件内实现——调 ctx，由 Host 的 Rust 侧执行。

## 目录结构

```
src/plugin.ts     # definePlugin 入口：View / 工具 / 生命周期（stop 杀 Blender 子进程）
src/Panel.vue     # 面板：横向 Blender 版本卡 + Tripo 占位 + 嵌入容器
src/runtime.ts    # 版本目录 BLENDER_CATALOG（与 fetch_blender.py CATALOG 同步）
src/tools.ts      # 插件工具声明：工具名 ↔ 桥命令映射的单一数据源
src/state.ts      # 运行期状态单例（pid / port）
assets/bridge/    # Blender 内 IPC 桥（Python 包，TCP JSON-lines，@command 注册表）
scripts/fetch_blender.py           # CLI：list / download，stdout = JSON/JSONL
scripts/build_fetch_blender_exe.py # PyInstaller → scripts/dist/fetch_blender.exe
scripts/start.mjs         # 一键调试：旁边有 work-beep 则 deploy + tauri dev；否则拉 Release exe
scripts/deploy.mjs        # dist → ../work-beep/plugins/blender/ + runtime junction（维护者本地）
scripts/fetch-host.mjs    # 从 work-beep Release 拉主程序包到 host-app/（start.mjs 自动调用）
runtime/          # Blender 绿色版（不进版本库，见下）
```

## 构建与调试

**只克隆本仓库即可开发**：`@beep/sdk` 走 GitHub 依赖（`github:mydouleur/work-beep-plugin-sdk#main`），
安装时自动跑 prepare 构建。注意 pnpm-workspace.yaml 的 `allowBuilds` 键含 sdk 提交哈希，
升级 sdk（lockfile 哈希变化）后需按 pnpm 报错提示同步更新该键。

```bash
pnpm install
pnpm build                            # beep-plugin build → dist/
python scripts/fetch_blender.py list
python scripts/fetch_blender.py download --version 5.2.1 --mirror aliyun
pnpm build:fetch-blender              # 可选：打 fetch_blender.exe（用户机无需 Python）
pnpm start                            # 旁边有 ../work-beep：deploy + pnpm tauri dev（最新 Host）
                                      # 只克隆本仓：拉 GitHub Release exe（不含未发布的 Host 改动）
pnpm deploy                           # 仅把 dist 拷到 ../work-beep/plugins/blender/（不启动）
```

**本轮 / 下轮边界**：Managed 下载经 Host `runProcess` 调用 `assets/tools/fetch_blender.exe`
（JSONL 进度）；`--root` 指向 `assets/`（与 `assets/runtime` 对齐）。External 仍走
pickFile / runCapture。旧的 Panel `ctx.download` / `extractZip` 路径已弃用。

`runtime/` 布局（双层同名目录不是笔误）：

```
runtime/blender-5.2.1-windows-x64/blender-5.2.1-windows-x64/blender.exe
runtime/blender-4.5.13-windows-x64/blender-4.5.13-windows-x64/blender.exe
```

deploy 时 `runtime/` 以 junction 挂到 `<Host插件目录>/assets/runtime`，不复制数 GB 文件。

## 约定

- 代码注释与文档用中文；commit message 按 Conventional Commits、中文撰写。
- 新增工具：`src/tools.ts` 加声明（名字必须带 `blender.` 前缀，描述写短——schema 是
  token 大头）+ `assets/bridge/commands/` 加对应 Python 命令，两边同步。
- 改 Blender 版本目录要**同步两处**：`scripts/fetch_blender.py` 的 `CATALOG`、
  `src/runtime.ts` 的 `BLENDER_CATALOG`。
- 共享依赖约束：`vue` / `@beep/sdk` 只用具名导入或命名空间导入（构建期被 kit 改写为
  全局解构，与 Host 共用实例）。
- 桥脚本跑在 Blender 内嵌 Python 里，只用标准库；`fetch_blender.py` 跑在系统 Python，
  也只准用标准库（PyInstaller 打包除外）。

## 安全

- `runtime/`、`host-app/`、`dist/`、`node_modules/`、`scripts/dist/` 不进版本库（.gitignore 已配）。
- 桥服务只监听 `127.0.0.1`，端口由 Host 的 `{port}` 占位符挑选。
