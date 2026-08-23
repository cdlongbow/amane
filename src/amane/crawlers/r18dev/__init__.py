"""r18.dev 离线 PostgreSQL 镜像数据源.

特殊数据源: r18.dev 不提供逐番号 HTTP 接口, 而是发布完整 PG dump. 本子包负责:
- importer: 下载 dump → 临时库 → schema 校验 → 原子换名 (R18Importer)
- database: 只读 asyncpg 引擎 (R18Database, 注入 R18DevCrawler)
- repository: 固定显式列 SQL 查询契约 (R18Repository)
- mapper: 查询结果 → MediaMetadata

爬虫实现见 ../sites/r18dev.py.
"""

from .database import R18Database
from .importer import R18Importer, RemoteMeta
from .mapper import to_metadata
from .repository import R18Repository, content_id_candidates

__all__ = [
    "R18Database",
    "R18Importer",
    "R18Repository",
    "RemoteMeta",
    "content_id_candidates",
    "to_metadata",
]
