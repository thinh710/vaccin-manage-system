from django.db import migrations


def fix_sqlite_post_tracking_fk(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "sqlite":
        return

    table_name = "medical_postinjectiontracking"
    target_table = "medical_vaccinationlog"
    broken_target_table = "medical_vaccinationlog__old"
    quote_name = schema_editor.quote_name

    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA foreign_key_list({quote_name(table_name)})")
        foreign_keys = cursor.fetchall()

    if not any(row[2] == broken_target_table for row in foreign_keys):
        return

    new_table_name = f"{table_name}__new"
    quoted_table = quote_name(table_name)
    quoted_new_table = quote_name(new_table_name)

    constraints_disabled = connection.disable_constraint_checking()
    try:
        schema_editor.execute(f"DROP TABLE IF EXISTS {quoted_new_table}")
        schema_editor.execute(
            f"""
            CREATE TABLE {quoted_new_table} (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                "reaction_status" varchar(20) NOT NULL,
                "notes" text NULL,
                "created_at" datetime NOT NULL,
                "vaccination_log_id" bigint NOT NULL UNIQUE REFERENCES "{target_table}" ("id") DEFERRABLE INITIALLY DEFERRED
            )
            """
        )
        schema_editor.execute(
            f"""
            INSERT INTO {quoted_new_table} (
                "id",
                "reaction_status",
                "notes",
                "created_at",
                "vaccination_log_id"
            )
            SELECT
                "id",
                "reaction_status",
                "notes",
                "created_at",
                "vaccination_log_id"
            FROM {quoted_table}
            """
        )
        schema_editor.execute(f"DROP TABLE {quoted_table}")
        schema_editor.execute(f"ALTER TABLE {quoted_new_table} RENAME TO {quoted_table}")
    finally:
        if constraints_disabled:
            connection.enable_constraint_checking()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("medical", "0006_add_decision_to_screeningresult"),
    ]

    operations = [
        migrations.RunPython(fix_sqlite_post_tracking_fk, migrations.RunPython.noop),
    ]
