from django.db import migrations


SQLITE_REBUILD_SQL = [
    "PRAGMA foreign_keys=OFF;",
    """
    CREATE TABLE medical_vaccinationlog_new (
        id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
        legacy_vaccine_code varchar(100) NULL,
        batch_number varchar(50) NOT NULL,
        injected_by varchar(100) NOT NULL,
        injection_time datetime NOT NULL,
        dose_number smallint unsigned NOT NULL CHECK (dose_number >= 0),
        booking_id bigint NOT NULL UNIQUE REFERENCES booking_booking (id) DEFERRABLE INITIALLY DEFERRED,
        vaccine_id bigint NULL REFERENCES assets_vaccine (id) DEFERRABLE INITIALLY DEFERRED
    );
    """,
    """
    INSERT INTO medical_vaccinationlog_new (
        id,
        legacy_vaccine_code,
        batch_number,
        injected_by,
        injection_time,
        dose_number,
        booking_id,
        vaccine_id
    )
    SELECT
        id,
        legacy_vaccine_code,
        batch_number,
        injected_by,
        injection_time,
        dose_number,
        booking_id,
        vaccine_id
    FROM medical_vaccinationlog;
    """,
    "DROP TABLE medical_vaccinationlog;",
    "ALTER TABLE medical_vaccinationlog_new RENAME TO medical_vaccinationlog;",
    "CREATE INDEX medical_vaccinationlog_vaccine_id_3f2f9d75 ON medical_vaccinationlog (vaccine_id);",
    "PRAGMA foreign_keys=ON;",
]


SQLITE_REBUILD_REVERSE_SQL = [
    "PRAGMA foreign_keys=OFF;",
    """
    CREATE TABLE medical_vaccinationlog_old (
        id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
        legacy_vaccine_code varchar(100) NOT NULL,
        batch_number varchar(50) NOT NULL,
        injected_by varchar(100) NOT NULL,
        injection_time datetime NOT NULL,
        dose_number smallint unsigned NOT NULL CHECK (dose_number >= 0),
        booking_id bigint NOT NULL UNIQUE REFERENCES booking_booking (id) DEFERRABLE INITIALLY DEFERRED,
        vaccine_id bigint NULL REFERENCES assets_vaccine (id) DEFERRABLE INITIALLY DEFERRED
    );
    """,
    """
    INSERT INTO medical_vaccinationlog_old (
        id,
        legacy_vaccine_code,
        batch_number,
        injected_by,
        injection_time,
        dose_number,
        booking_id,
        vaccine_id
    )
    SELECT
        id,
        COALESCE(legacy_vaccine_code, ''),
        batch_number,
        injected_by,
        injection_time,
        dose_number,
        booking_id,
        vaccine_id
    FROM medical_vaccinationlog;
    """,
    "DROP TABLE medical_vaccinationlog;",
    "ALTER TABLE medical_vaccinationlog_old RENAME TO medical_vaccinationlog;",
    "CREATE INDEX medical_vaccinationlog_vaccine_id_3f2f9d75 ON medical_vaccinationlog (vaccine_id);",
    "PRAGMA foreign_keys=ON;",
]


def make_legacy_vaccine_code_nullable(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            "ALTER TABLE medical_vaccinationlog "
            "ALTER COLUMN legacy_vaccine_code DROP NOT NULL;"
        )
        return

    if vendor == "sqlite":
        for statement in SQLITE_REBUILD_SQL:
            schema_editor.execute(statement)


def make_legacy_vaccine_code_not_nullable(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            "ALTER TABLE medical_vaccinationlog "
            "ALTER COLUMN legacy_vaccine_code SET NOT NULL;"
        )
        return

    if vendor == "sqlite":
        for statement in SQLITE_REBUILD_REVERSE_SQL:
            schema_editor.execute(statement)


class Migration(migrations.Migration):

    dependencies = [
        ("medical", "0004_vaccinationlog_vaccine_fk"),
    ]

    operations = [
        migrations.RunPython(
            make_legacy_vaccine_code_nullable,
            make_legacy_vaccine_code_not_nullable,
        ),
    ]
