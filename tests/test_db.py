import inspect

from backend import db as db_mod


def test_existing_production_indexes_emit_no_ddl():
    assert db_mod.index_ddl_for({"ix_bridges_geog", "ix_bridges_bbox"}) == []


def test_missing_gist_index_is_the_only_create():
    ddl = db_mod.index_ddl_for({"ix_bridges_bbox"})
    assert len(ddl) == 1
    assert "ix_bridges_geog" in ddl[0]
    assert "GIST" in ddl[0].upper()
    assert "ix_bridges_bbox" not in ddl[0]


def test_ensure_indexes_skips_create_when_catalog_has_them():
    executed = []

    class Catalog:
        def execute(self, statement, params=None):
            sql = str(statement)
            executed.append(sql)
            if "to_regclass" in sql:
                return type("R", (), {"scalar": staticmethod(lambda: True)})()
            raise AssertionError(f"unexpected SQL: {sql}")

    db_mod.ensure_indexes(Catalog())
    assert executed
    assert all("CREATE INDEX" not in sql.upper() for sql in executed)


def test_ensure_indexes_creates_only_the_missing_gist():
    executed = []

    class Catalog:
        def execute(self, statement, params=None):
            sql = str(statement)
            executed.append(sql)
            params = params or {}
            if "to_regclass" in sql:
                present = params.get("reg") == "ix_bridges_bbox"
                return type("R", (), {"scalar": staticmethod(lambda: present)})()
            return type("R", (), {"scalar": staticmethod(lambda: None)})()

    db_mod.ensure_indexes(Catalog())
    creates = [sql for sql in executed if "CREATE INDEX" in sql.upper()]
    assert len(creates) == 1
    assert "ix_bridges_geog" in creates[0]


def test_ensure_extensions_skips_create_when_postgis_exists():
    executed = []

    class Catalog:
        def execute(self, statement, params=None):
            executed.append(str(statement))
            return type("R", (), {"scalar": staticmethod(lambda: 1)})()

    db_mod.ensure_extensions(Catalog())
    assert executed
    assert all("CREATE EXTENSION" not in sql.upper() for sql in executed)


def test_ensure_ingest_columns_skips_alter_when_present():
    executed = []

    class Catalog:
        def execute(self, statement, params=None):
            executed.append(str(statement))
            return type("R", (), {"scalar": staticmethod(lambda: 1)})()

    db_mod.ensure_ingest_columns(Catalog())
    assert executed
    assert all("ALTER TABLE" not in sql.upper() for sql in executed)


def test_init_db_indexes_bridges_in_a_separate_transaction():
    source = inspect.getsource(db_mod.init_db)
    ingest_at = source.index("ensure_ingest_columns")
    index_at = source.index("ensure_indexes")
    assert ingest_at < index_at
    between = source[ingest_at:index_at]
    assert "engine.begin" in between
