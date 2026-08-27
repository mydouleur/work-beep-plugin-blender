# work-beep-plugin-blender

blenderBeeper 的 Blender 插件（@beep/plugin-sdk 契约的参考实现）：

- 纯 TS 描述插件：`src/plugin.ts`（definePlugin：View / 工具 / 生命周期）、`src/Panel.vue`（启动按钮 + 嵌入面板）、`src/tools.ts`（`blender.view_front` 等，工具名 ↔ 桥命令单一数据源）
- `assets/bridge/`——Blender 内 IPC 桥（Python 包，TCP JSON-lines，@command 注册表）
- `scripts/fetch_blender.py`——下载 Blender 绿色版到 `runtime/`（不进版本库）
- `scripts/deploy.mjs`——把构建产物部署到 Host 的 `plugins/blender/`

## 开发与调试

```bash
pnpm install
pnpm build          # vite build（@beep/plugin-kit 预设）→ dist/
pnpm deploy         # dist → ../host/plugins/blender/（三仓并列时）
python scripts/fetch_blender.py --mirror aliyun   # 首次：下载 Blender 绿色版
```

免构主项目调试：从 work-beep 的 Releases 下载主程序包（或跑 sdk 仓库 example 里的下载脚本），
把 `dist/` 放进其 `plugins/blender/` 后启动 exe。
