# Amane

![](https://img.shields.io/badge/License-GPLv3-blue.svg)

AI 时代的私人影库

## 功能特性

- **自动监控** — 实时监控磁盘文件变化并自动刮削
- **本地优先** — 持久化存储已获取数据, 构建个人影片仓库
- **多源择优** — 聚合多个数据源的元数据, 逐字段择优, 所有数据优先使用本地缓存, 无压力重复刮削
- **目录管理** — 自动关联并整理本地文件, 支持自定义命名规则, 目录结构随时可变
- **图片增强** — 内置超分工具优化低清海报图
- **AI 智能助理** — 深度集成智能体助理, 使用自然语言检索片库、批量整理、发起刮削
- **全功能 Web 界面** — 影片海报墙、任务队列、结构化日志、可视化设置

## 开始使用

### Docker

推荐使用 Docker Compose — [参考配置](compose.yaml)

也可直接运行:

```bash
docker run -d --name amane \
  --user "$(id -u):$(id -g)" \
  -p 8000:8000 \
  -v "$PWD/data:/data" \
  -v /path/to/media:/media \
  -e AMANE_DATA_DIR=/data \
  ghcr.io/sqzw-x/amane:latest
```

启动后访问 `http://localhost:8000`. 首次访问需输入 API token, 可从 `docker logs amane` 中查看。

更多说明见 [用户文档](https://sqzw-x.github.io/amane/).

### macOS 桌面应用

macOS 用户可以从 [GitHub Releases](https://github.com/sqzw-x/amane/releases) 下载桌面应用：常驻菜单栏，显示服务状态，一键打开 Web 界面或数据目录，随系统启动。

### Windows

Windows 用户可以从 [GitHub Releases](https://github.com/sqzw-x/amane/releases) 下载 zip：解压后运行 `Amane.exe`. 常驻托盘，显示服务状态，一键打开 Web 界面或数据目录。

## 参与开发

前置依赖:

- [uv](https://github.com/astral-sh/uv)
- [pnpm](https://pnpm.io/)
- [just](https://github.com/casey/just)

```bash
just setup   # 同步依赖
just dev     # 启动 API 与前端
```

Agent 开发文档见 [docs/dev/index.md](docs/dev/index.md).

## 相关项目

- [yoshiko2/Movie_Data_Capture](https://github.com/yoshiko2/Movie_Data_Capture)
- [moyy996/AVDC](https://github.com/moyy996/AVDC)
