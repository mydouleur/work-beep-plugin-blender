# work-beep-plugin-blender

blenderBeeper 的 Blender 插件（@beep/sdk 契约的参考实现）：

- 纯 TS 描述插件：`src/plugin.ts`（definePlugin：View / 工具 / 生命周期）、`src/Panel.vue`（启动按钮 + 嵌入面板）、`src/tools.ts`（`blender.view_front` 等，工具名 ↔ 桥命令单一数据源）
- `assets/bridge/`——Blender 内 IPC 桥（Python 包，TCP JSON-lines，@command 注册表）
- `scripts/fetch_blender.py`——下载 Blender 绿色版到 `runtime/`（不进版本库）
- `scripts/fetch-host.mjs`——从 work-beep 的 Release 拉主程序包到 `host-app/`（免构主项目）

**只克隆本仓库即可开发**：`@beep/sdk` 走 GitHub 依赖（package.json），无需拉取其他仓库。

## 开发与调试

```bash
pnpm install        # 从 GitHub 拉 @beep/sdk 并自动构建（allowBuilds 已配）
pnpm build          # beep-plugin build（sdk 自带打包命令）→ dist/
python scripts/fetch_blender.py --mirror aliyun # 首次：下载 Blender 绿色版到 runtime/
pnpm start          # 一键调试：自动拉主程序 Release → 组装 host-app/plugins/blender/ → 启动 exe
```

`pnpm start` 首次会从 work-beep 的 GitHub Release 下载主程序到 `host-app/`（免构主项目），
之后重复执行只做增量组装并启动。维护者本地有三仓并列时，也可 `pnpm deploy` 部署到
`../work-beep/plugins/blender/` 配合 Host 源码开发。
