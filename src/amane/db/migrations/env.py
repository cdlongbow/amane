from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, event, pool
from sqlmodel import SQLModel

# 导入全部 table 模型以填充 metadata (含分类索引 / 用户注解表)
import amane.db.models  # noqa: F401
from amane.db.sqlite_migrate import enable_sqlite_transactional_ddl

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """以离线模式运行迁移"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        transactional_ddl=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """以在线模式运行迁移.

    SQLite 使用事务性 DDL (见 sqlite_migrate.enable_sqlite_transactional_ddl):
    单次 revision 失败时 DDL 与 alembic_version 一并回滚.
    """
    # 支持通过 config.attributes 传入已有连接 (应用启动时调用)
    connectable = config.attributes.get("connection")

    if connectable is not None:
        context.configure(connection=connectable, target_metadata=target_metadata, transactional_ddl=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        # CLI 调用 (alembic upgrade/downgrade) - 自行创建连接
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
        )

        @event.listens_for(connectable, "connect")
        def _enable_txn_ddl(dbapi_connection, _connection_record) -> None:
            enable_sqlite_transactional_ddl(dbapi_connection)

        try:
            with connectable.connect() as connection:
                context.configure(connection=connection, target_metadata=target_metadata, transactional_ddl=True)
                with context.begin_transaction():
                    context.run_migrations()
                connection.commit()
        finally:
            connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
