from django.db import migrations


def make_legacy_vaccine_code_nullable(apps, schema_editor):
    connection = schema_editor.connection
    table_name = "medical_vaccinationlog"
    column_name = "legacy_vaccine_code"
    quote_name = schema_editor.quote_name

    with connection.cursor() as cursor:
        existing_columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

    if column_name not in existing_columns:
        return

    if connection.vendor == "postgresql":
        schema_editor.execute(
            f"ALTER TABLE {quote_name(table_name)} "
            f"ALTER COLUMN {quote_name(column_name)} DROP NOT NULL"
        )
        return

    if connection.vendor != "sqlite":
        return

    quoted_table = quote_name(table_name)
    new_table_name = f"{table_name}__new"
    quoted_new_table = quote_name(new_table_name)

    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({quoted_table})")
        columns = {row[1]: row for row in cursor.fetchall()}

    if column_name not in columns or columns[column_name][3] == 0:
        return

    constraints_disabled = connection.disable_constraint_checking()
    try:
        schema_editor.execute(f"DROP TABLE IF EXISTS {quoted_new_table}")
        schema_editor.execute(
            """
            CREATE TABLE "medical_vaccinationlog__new" (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                "legacy_vaccine_code" varchar(100) NULL,
                "batch_number" varchar(50) NOT NULL,
                "injected_by" varchar(100) NOT NULL,
                "injection_time" datetime NOT NULL,
                "dose_number" smallint unsigned NOT NULL CHECK ("dose_number" >= 0),
                "booking_id" bigint NOT NULL UNIQUE REFERENCES "booking_booking" ("id") DEFERRABLE INITIALLY DEFERRED,
                "vaccine_id" bigint NULL REFERENCES "assets_vaccine" ("id") DEFERRABLE INITIALLY DEFERRED
            )
            """
        )
        schema_editor.execute(
            """
            INSERT INTO "medical_vaccinationlog__new" (
                "id",
                "legacy_vaccine_code",
                "batch_number",
                "injected_by",
                "injection_time",
                "dose_number",
                "booking_id",
                "vaccine_id"
            )
            SELECT
                "id",
                "legacy_vaccine_code",
                "batch_number",
                "injected_by",
                "injection_time",
                "dose_number",
                "booking_id",
                "vaccine_id"
            FROM "medical_vaccinationlog"
            """
        )
        schema_editor.execute(f"DROP TABLE {quoted_table}")
        schema_editor.execute(f"ALTER TABLE {quoted_new_table} RENAME TO {quoted_table}")
        schema_editor.execute(
            """
            CREATE INDEX "medical_vaccinationlog_vaccine_id_9b015adb"
            ON "medical_vaccinationlog" ("vaccine_id")
            """
        )
    finally:
        if constraints_disabled:
            connection.enable_constraint_checking()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("medical", "0004_vaccinationlog_vaccine_fk"),
    ]

    operations = [
        migrations.RunPython(make_legacy_vaccine_code_nullable, migrations.RunPython.noop),
    ]
