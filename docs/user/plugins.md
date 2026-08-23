# 插件

插件是可用于扩展 amane 能力的 Python 包, 有以下限制:

- 只支持影片元数据
- 只能使用已有依赖
- 单插件只能实现单刮削源

插件会在运行时使用 `importlib` 动态加载, 和 amane 在同一进程内, 共享 Python 环境. 因此**插件可以在服务端执行任意代码. 不要安装未经安全审查的插件, 否则可能导致非常严重的后果**.

目前没有计划开发官方插件市场, 社区可以自行开发和分发插件, amane 不对插件的安全性和可用性负责.

## 安装和使用

插件安装入口在「刮削插件」页, 有两种方式:

- 上传 zip
- 选择服务器插件目录或 zip 文件

安装是热加载的, 成功后插件立即出现在列表里, 不需要重启. 安全起见, 不提供任何远程加载安装插件的方法.

在「刮削插件」页可以控制每个插件是否启用, 以及插件开发者定义的配置项.

安装后「设置 → 影片刮削」的内容路由/优先级等相关项中会出现插件 ID, 配置后即会在刮削时调用.

更新插件只需覆盖安装.

## 开发插件

插件本质上是一个 Python 包, 通过继承 `FilmSourcePlugin` 声明身份和能力, 并实现 `build()` 构造 `FilmSourceProvider` 实例. 其余的抓取逻辑都在 provider 内实现.

插件会在运行时加载到 amane 进程中, 因此其语法应当兼容 amane 使用的 Python 版本.

插件可以导入 amane 的依赖库以及任何标准库. 鉴于插件实现的机制, 实际上可以导入 amane 中的任意模块, 但 `amane.plugin` 是唯一公开的接口, 其它模块不保证兼容性. 插件开发者应当只使用 `amane.plugin` 中暴露的类型和函数, 不要依赖 amane 内部实现.

### 约定

插件必须包含一个 `plugin.py` 文件, 且此文件需包含名为 `Plugin` 的 `FilmSourcePlugin` 子类. 如果有多个模块, 必须使用相对导入

```
my_plugin/
  plugin.py
  utils.py
  ...
```

### 插件 ID

ID 是插件的唯一身份标识, 格式为 `namespace.local` (如 `alice.example`), 有以下要求:

- 至少两段, 多段也合法 (如 `alice.foo.bar`)
- 每段只包含小写字母 / 数字 / `-` / `_`, 且必须以字母或数字开头
- namespace 不能是保留字 `amane` / `plugin` / `official` / `builtin`, 也不能与任何内置站点重名

### 示例

以下代码实现了一个最简单的单文件插件

```python
# plugin.py
from typing import override

from pydantic import BaseModel, ConfigDict

from amane.plugin import (
    FetchOptions,
    FilmSourcePlugin,
    FilmSourceProvider,
    MediaMetadata,
    PluginContext,
    SearchQuery,
    SourceCapability,
    SourceDescriptor,
)


class ExampleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_token: str = ""


class ExampleProvider(FilmSourceProvider):
    def __init__(self, context: PluginContext, config: ExampleConfig) -> None:
        self._http = context.http_client
        self._token = config.api_token

    @override
    async def fetch(self, query: SearchQuery, options: FetchOptions | None = None) -> MediaMetadata | None:
        if not query.number:
            return None
        data = await self._http.get_json(
            "https://example.test/api/movie",
            headers={"Authorization": f"Bearer {self._token}"} if self._token else None,
        )
        if not isinstance(data, dict):
            return None
        title = data.get("title")
        if not isinstance(title, str) or not title:
            return None
        return MediaMetadata(number=query.number, title=title)


class Plugin(FilmSourcePlugin):
    config_model = ExampleConfig

    @classmethod
    @override
    def descriptor(cls) -> SourceDescriptor:
        return SourceDescriptor(
            id="alice.example",
            name="Alice Example",
            version="0.1.0",
            capabilities=frozenset({SourceCapability.FILM_METADATA.value}),
            urls=("https://example.test",),
        )

    @override
    def build(self, context: PluginContext, config: BaseModel) -> FilmSourceProvider:
        if not isinstance(config, ExampleConfig):
            raise TypeError("unexpected config type")
        return ExampleProvider(context, config)
```

要点:

- 未命中返回 `None`: 请求成功但没有得到元数据 (或番号不匹配), 这是「没有找到」, 不是失败
- 网络失败、拦截页、可分类业务失败抛 `SourceError`, 交给 amane 分类记录, 任务不会崩, 报告里能看到原因. 它的子类 `RequestError` 表示出站请求重试用尽后仍失败. 不要 `except RequestError: return None`, 也不要 `except Exception`, 吞掉异常只会让报告变成「没拿到元数据」
- 业务失败也用 `SourceError`: `FailureReason` 给原因, 人类可读的句子放 `detail`
- 网络请求必须走 `context.http_client`: 获取 HTML 用 `get_html`, JSON API 用 `get_json`. 它共享 amane 的代理、重试、按 host 限速, 并记入任务记录, 不要自建客户端
- `descriptor.urls` 填插件需访问的站点, 会用于请求限速; 可用 `rate_limit` (每秒请求数) 覆盖默认限速
- 落盘只写 `context.data_dir` (插件自己的 `{data_dir}/plugins/<id>/`), 卸载时也保留, 适合放缓存
- 来源支持多语言时, descriptor 声明 `multi_language=True`, fetch `options.language` 拿到当前语言. 不设则语言信息不会传给插件, 插件也不该自行猜测

### 配置

插件配置是 Pydantic 模型 (`config_model`), 保存在 amane 配置的 `plugins` 段, 与内置刮削配置相互独立. 界面根据模型的 JSON Schema 自动渲染表单, 因此:

- 用 `extra="forbid"` 防止未知字段
- 密钥字段 (字段名含 `token` / `api_key` / `secret` / `password` / `cookie` / `credential` / `dsn`) 在任务快照中自动脱敏
- 校验失败时界面直接显示模型校验消息

如果不需要自定义配置则不必设 `ExampleConfig` 和 `config_model`

### 分发

将代码打包成 zip, 保证可在根目录或单一顶层目录内搜索到 `plugin.py` 即可. 注意不要将 `__pycache__` 或 `.git` 等无关内容打包到 zip 中.
