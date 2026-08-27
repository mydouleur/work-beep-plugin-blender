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
src/Panel.vue     # 面板：启动按钮 + 嵌入容器（watchRect 跟随分隔条/窗口移动）
src/tools.ts      # 插件工具声明：工具名 ↔ 桥命令映射的单一数据源
src/state.ts      # 运行期状态单例（pid / port）
assets/bridge/    # Blender 内 IPC 桥（Python 包，TCP JSON-lines，@command 注册表）
scripts/fetch_blender.py  # 下载 Blender 绿色版到 runtime/（标准库，断点续传 + SHA256）
scripts/start.mjs         # 一键调试：拉主程序 Release → 组装 host-app/ → 启动 exe
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
pnpm build                            # beep-plugin build（@beep/sdk 自带打包命令）→ dist/
python scripts/fetch_blender.py --mirror aliyun   # 首次且 runtime/ 缺失时：下载 Blender 绿色版
pnpm start                            # 一键调试：拉主程序 Release → 组装 host-app/ → 启动 exe
pnpm deploy                           # 维护者本地三仓并列时：dist → ../work-beep/plugins/blender/
```

`runtime/` 布局（`src/Panel.vue` 里 resolveAsset 写死的路径，双层同名目录不是笔误）：

```
runtime/blender-5.2.1-windows-x64/blender-5.2.1-windows-x64/blender.exe
```

deploy 时 `runtime/` 以 junction 挂到 `<Host插件目录>/assets/runtime`，不复制数 GB 文件。
当前 5.2.1 绿色版已就位，`fetch_blender.py` 会检出已存在并跳过下载。

## 约定

- 代码注释与文档用中文；commit message 按 Conventional Commits、中文撰写。
- 新增工具：`src/tools.ts` 加声明（名字必须带 `blender.` 前缀，描述写短——schema 是
  token 大头）+ `assets/bridge/commands/` 加对应 Python 命令，两边同步。
- 改 Blender 版本号要**同步三处**：`scripts/fetch_blender.py` 的 `DEFAULT_VERSION`、
  `src/Panel.vue` 的 resolveAsset 路径。
- 共享依赖约束：`vue` / `@beep/sdk` 只用具名导入或命名空间导入（构建期被 kit 改写为
  全局解构，与 Host 共用实例）。
- 桥脚本跑在 Blender 内嵌 Python 里，只用标准库；`fetch_blender.py` 跑在系统 Python，
  也只准用标准库。

## 安全

- `runtime/`、`host-app/`、`dist/`、`node_modules/` 不进版本库（.gitignore 已配）。
- 桥服务只监听 `127.0.0.1`，端口由 Host 的 `{port}` 占位符挑选。
