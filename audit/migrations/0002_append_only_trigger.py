from django.db import migrations

CREATE_SQL = """
CREATE OR REPLACE FUNCTION audit_block_changes() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_auditentry is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_auditentry
    FOR EACH ROW EXECUTE FUNCTION audit_block_changes();

CREATE TRIGGER audit_no_truncate
    BEFORE TRUNCATE ON audit_auditentry
    FOR EACH STATEMENT EXECUTE FUNCTION audit_block_changes();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS audit_no_update_delete ON audit_auditentry;
DROP TRIGGER IF EXISTS audit_no_truncate ON audit_auditentry;
DROP FUNCTION IF EXISTS audit_block_changes();
"""


def add_triggers(apps, schema_editor):
    # Database-level protection exists only on PostgreSQL (production). SQLite (local
    # development and tests) relies on the model-level protection and the hash chain.
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREATE_SQL)


def drop_triggers(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(DROP_SQL)


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [migrations.RunPython(add_triggers, drop_triggers)]
