# 开始使用

## Docker

推荐 [Docker Compose 配置](https://github.com/sqzw-x/amane/blob/main/compose.yaml).

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

启动后访问 `http://localhost:8000`. 首次访问需输入 API token, 从 `docker logs amane` 查看.

## macOS 桌面应用

从 [GitHub Releases](https://github.com/sqzw-x/amane/releases) 下载: 常驻菜单栏, 显示服务状态, 一键打开 Web 界面或数据目录, 随系统启动.

## Windows

从 [GitHub Releases](https://github.com/sqzw-x/amane/releases) 下载 zip, 解压后运行 `Amane.exe`: 常驻托盘, 显示服务状态, 一键打开 Web 界面或数据目录.

## 插件

支持使用 Python 开发刮削插件, 见 [插件](plugins.md).
