from logging import getLogger
from logging.config import fileConfig
from collections import defaultdict
from typing import Optional, Sequence, Union

from alembic import context
from alembic.operations import ops
from alembic.autogenerate import rewriter
from alembic.script import ScriptDirectory
from sqlalchemy import engine_from_config, pool, MetaData

from sqlalchemy import BigInteger, Column, Identity, Table

SYSTEM_COLUMN = 'row_id'
CREATE_VERSION_TRIGGER_KEY = 'CREATE_VERSION_TRIGGER_KEY'
DELETE_VERSION_TRIGGER_KEY = 'DELETE_VERSION_TRIGGER_KEY'

logger = getLogger(__name__)
config = context.config

writer_rename_migration = rewriter.Rewriter()
writer_add_version_trigger = rewriter.Rewriter()
writer_del_version_trigger = rewriter.Rewriter()

writer_chain = writer_rename_migration.chain(
    writer_add_version_trigger.chain(
        writer_del_version_trigger
    ))

OPERATIONS_WITH_TRIGGER_RECREATION = (
    ops.AddColumnOp,
    ops.DropColumnOp,
)


class VersionsTable(Table):
    def __new__(cls, table_name: str, source_table: Table):
        version_table = super().__new__(
            cls,
            table_name,
            source_table.metadata,
            Column(
                SYSTEM_COLUMN,
                BigInteger,
                Identity(always=True, start=1, cycle=False),
                primary_key=True,
                nullable=False,
            ),
            *[cls._copy_column(x) for x in source_table.c],
        )
        version_table.source_table = source_table
        version_table.info = {
            CREATE_VERSION_TRIGGER_KEY: version_table.get_recreate_version_trigger_sql(),
            DELETE_VERSION_TRIGGER_KEY: version_table.get_delete_version_trigger_sql(),
        }
        return version_table

    def generate_trigger_name(self) -> tuple:
        trigger_name = f'tg_{self.source_table.name}_versions'
        function_name = f'process_{trigger_name}'
        return trigger_name, function_name

    def get_delete_version_trigger_sql(self):
        trigger_name, function_name = self.generate_trigger_name()
        return (f"drop function if exists {function_name}() cascade; "
                f"drop trigger if exists  {trigger_name} on {self.source_table.schema}.{self.source_table.name};")

    def get_create_version_trigger_sql(self, columns=None):
        trigger_name, function_name = self.generate_trigger_name()
        old_sql = f"""
           create or replace function {function_name}()
           returns trigger as ${trigger_name}$
           declare
           main_table_columns text;

           begin
               select  string_agg(column_name, ',')
               into    main_table_columns
               from information_schema.columns
               where table_schema = '{self.source_table.schema}'
                 and table_name   = '{self.source_table.name}';

               execute format(
                   'insert into {self.schema}.{self.name} ( %s ) VALUES ($1.*) ',
                    main_table_columns
               ) using OLD;

               RETURN NEW;
           end;
           ${trigger_name}$ language plpgsql;


           create trigger {trigger_name}
           after update or delete on {self.source_table.schema}.{self.source_table.name}
           for each row execute procedure {function_name}();
        """

        columns = columns or [column.name for column in self.source_table.c]
        if columns:
            formatted_log_columns = ', '.join(columns)
            formatted_old_columns = ', '.join(f'old.{column_name}' for column_name in columns)

            return f"""
               create or replace function {function_name}()
               returns trigger as ${trigger_name}$

               begin
                   insert into {self.schema}.{self.name} ( {formatted_log_columns} )
                   values ( {formatted_old_columns} );
                   return NEW;
               end;
               ${trigger_name}$ language plpgsql;

               create trigger {trigger_name}
               after update or delete on {self.source_table.schema}.{self.source_table.name}
               for each row execute procedure {function_name}();
            """

        return old_sql

    def get_recreate_version_trigger_sql(self, columns=None):
        sql = self.get_delete_version_trigger_sql()
        sql += self.get_create_version_trigger_sql(columns)
        return sql

    @staticmethod
    def _copy_column(col):
        col = col.copy()
        col.unique = False
        col.default = col.server_default = None
        col.autoincrement = False
        col.nullable = True
        col._user_defined_nullable = col.nullable
        col.primary_key = False
        return col


def declare_version_table(table: Table, version_table_name: str):
    """
    Declare new table for store historical data of original table
    :param table: Original table
    :param version_table_name: Name for new table
    :return: Table with same columns as `table` plus `version` integer column
    """
    return VersionsTable(version_table_name, source_table=table)


@writer_rename_migration.rewrites(ops.MigrationScript)
def rename_migration_script(migration_context, revision, migration_script):
    # extract current head revision
    head_revision = ScriptDirectory.from_config(migration_context.config).get_current_head()
    if head_revision is None:
        # edge case with first migration
        new_rev_id = 1
    else:
        # default branch with incrementation
        last_rev_id = int(head_revision.lstrip('0'))
        new_rev_id = last_rev_id + 1
    # fill zeros up to 4 digits: 1 -> 0001
    migration_script.rev_id = '{0:04}'.format(new_rev_id)
    return migration_script


@writer_add_version_trigger.rewrites(ops.CreateTableOp)
def add_version_trigger(migration_context, revision, create_table_op):
    if create_table_op.info.get(CREATE_VERSION_TRIGGER_KEY):
        create_trigger_op = ops.ExecuteSQLOp(create_table_op.info[CREATE_VERSION_TRIGGER_KEY])
        return [create_table_op, create_trigger_op]
    return create_table_op


@writer_del_version_trigger.rewrites(ops.DropTableOp)
def del_version_trigger(migration_context, revision, drop_table_op):
    if drop_table_op.info.get(DELETE_VERSION_TRIGGER_KEY):
        del_trigger_op = ops.ExecuteSQLOp(drop_table_op.info[DELETE_VERSION_TRIGGER_KEY])
        return [drop_table_op, del_trigger_op]
    return drop_table_op


@writer_add_version_trigger.rewrites(ops.ModifyTableOps)
def check_modify_operations(migration_context, revision, modify_ops):
    recreate_trigger_op = None
    table_columns = defaultdict(list)
    for operation in modify_ops.ops:
        if type(operation) not in OPERATIONS_WITH_TRIGGER_RECREATION:
            continue

        table = _get_table_from_migration_context(migration_context, operation.schema, operation.table_name)

        if table is None:
            logger.warning(f'Table {operation.table_name} not found in metadata. Probably model was deleted')
            continue

        if isinstance(table, VersionsTable):
            if not table_columns.get(table):
                table_columns[table] = [column.name for column in table.c if column.name != SYSTEM_COLUMN]

            if isinstance(operation, ops.DropColumnOp):
                table_columns[table] = [column_name for column_name in table_columns[table]
                                        if column_name not in {operation.column_name, SYSTEM_COLUMN}]
            elif operation.column.name not in {*table_columns[table], SYSTEM_COLUMN}:
                table_columns[table].append(operation.column.name)

            recreate_trigger_op = ops.ExecuteSQLOp(
                table.get_recreate_version_trigger_sql(columns=table_columns[table]),
            )

    if recreate_trigger_op:
        modify_ops.ops.append(recreate_trigger_op)

    return modify_ops


def _get_table_from_migration_context(migration_context, schema: str, table_name: str):
    """Get table from migration context.

    Getting from context useful for cases when alembic generates model without an info parameter.

    """
    table_key = f'{schema}.{table_name}'
    metadata = migration_context.opts['target_metadata']
    if isinstance(metadata, MetaData):
        metadata = [migration_context.opts['target_metadata']]

    for metadata_item in metadata:
        original_tables = metadata_item.tables
        table = original_tables.get(table_key)
        if table is not None:
            return table


def run_migrations_offline(target_metadata, version_table_schema):
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        version_table_schema=version_table_schema,
        process_revision_directives=writer_chain,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        if version_table_schema:
            context.execute(f'create schema if not exists {version_table_schema}')
        context.run_migrations()


def run_migrations_online(target_metadata, version_table_schema):
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=version_table_schema,
            process_revision_directives=writer_chain,
            include_schemas=True,
        )

        with context.begin_transaction():
            if version_table_schema:
                context.execute(f'create schema if not exists {version_table_schema}')
            context.run_migrations()


def run_alembic(
    sqlalchemy_url: str,
    target_metadata: Union[MetaData, Sequence[MetaData]],
    version_table_schema: Optional[str] = None,
):
    # this is the Alembic Config object, which provides
    # access to the values within the .ini file in use.

    # Interpret the config file for Python logging.
    # This line sets up loggers basically.
    fileConfig(config.config_file_name)

    config.set_main_option('sqlalchemy.url', sqlalchemy_url)

    if context.is_offline_mode():
        run_migrations_offline(target_metadata, version_table_schema)
    else:
        run_migrations_online(target_metadata, version_table_schema)


from app.models import base
from settings.config import AppConfig

run_alembic(sqlalchemy_url=AppConfig.TEST_DB_URL or AppConfig.DB_URL, target_metadata=base.meta)
