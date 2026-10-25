# Profile generator

布局参考 [mufanc/mufanc](https://github.com/mufanc/mufanc)，使用 Python 标准库生成自包含 SVG。

```sh
# 使用 2026-10-25 的公开数据与贡献动画快照，无需联网。
python scripts/generate-profile.py --offline

# 获取最新公开仓库数据，使用 snake Action 生成的动画。
python scripts/generate-profile.py --snakes dist
```

README 直接引用 `assets/profile-light.svg` 与 `assets/profile-dark.svg`，首次推送即可展示。
GitHub Actions 每天生成贡献动画、获取公开仓库统计，校验后更新这两个文件。
也可以手动运行 **Generate profile**。仅需内置 `GITHUB_TOKEN`，无需额外密钥。
原有 `output` 分支的独立 snake 文件仍会更新。

语言分布继续使用原来的 API 和参数：

```
https://readme-stats.mufanc.xyz/api/top-langs/?username=noionion&layout=compact&langs_count=8&hide_title=true&hide_border=true&hide=css,stylus,html,javascript,pug
```

从 API 返回的 SVG 提取语言名称、百分比和颜色，保持原统计口径，排除 CSS、Stylus、HTML、JavaScript、Pug。
`scripts/inputs/languages.svg` 是该接口的离线快照。Stars 仅统计非 fork 公开仓库。
离线快照不会自动刷新，在线请求失败会停止发布，保留现有卡片。
修改介绍和布局请编辑 `scripts/generate-profile.py` 后重新生成两张 SVG。

## Codex token 统计

`data/codex-usage.json` 保存当前 Codex 登录账号通过官方 `account/usage/read` 返回的统计快照。
卡片展示官方累计 token、近 30 天已返回的每日记录合计、单日峰值、连续使用天数和近一年热力图。
官方累计值独立于每日记录合计；没有返回的指标显示 `N/A`，没有记录的日期显示灰格，不补零。
接口可能延迟返回每日记录，卡片会显示最新日记录日期及同步时间。

在登录该账号的电脑上刷新数据并重新生成卡片：

```powershell
.\scripts\update-codex-usage.ps1
```

脚本优先使用本机 Codex 附带的 Python，也支持 `-Python <路径>` 和 `-Codex <路径>`。
或者分别执行：

```sh
python scripts/sync-codex-usage.py
python scripts/generate-profile.py --offline
python scripts/test_codex_usage.py
```

同步通过已安装的 `codex app-server` 和现有 ChatGPT 登录状态读取，不需要 API key。
导出文件仅包含白名单中的汇总计数、每日日期/token 及同步时间，不包含凭据、邮箱、账号 ID 或对话。
脚本不会提交或推送；将数据和图片随仓库提交后，线上 Profile 才会更新。
GitHub Actions 使用最后一次同步进仓库的数据，不会在 GitHub 服务器上读取你的本机登录状态。
当前没有安装本机定时同步任务。

接口说明：[官方 Codex App Server 文档](https://learn.chatgpt.com/docs/app-server#7-token-usage-chatgpt)。
