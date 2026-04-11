from django.db import migrations


def make_legacy_vaccine_code_nullable(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        "ALTER TABLE medical_vaccinationlog "
        "ALTER COLUMN legacy_vaccine_code DROP NOT NULL;"
    )


def make_legacy_vaccine_code_not_nullable(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        "ALTER TABLE medical_vaccinationlog "
        "ALTER COLUMN legacy_vaccine_code SET NOT NULL;"
    )


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
