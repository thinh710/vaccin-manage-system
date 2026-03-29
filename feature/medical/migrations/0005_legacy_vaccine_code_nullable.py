from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("medical", "0004_vaccinationlog_vaccine_fk"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE medical_vaccinationlog "
                        "ALTER COLUMN legacy_vaccine_code DROP NOT NULL;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE medical_vaccinationlog "
                        "ALTER COLUMN legacy_vaccine_code SET NOT NULL;"
                    ),
                ),
            ],
            state_operations=[],
        ),
    ]
