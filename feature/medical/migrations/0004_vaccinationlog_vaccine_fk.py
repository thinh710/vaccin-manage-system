# Generated manually for VaccinationLog vaccine FK update.

import django.db.models.deletion
from django.db import migrations, models


def populate_vaccine_fk(apps, schema_editor):
    VaccinationLog = apps.get_model("medical", "VaccinationLog")
    Vaccine = apps.get_model("assets", "Vaccine")

    for vaccination in VaccinationLog.objects.all().iterator():
        legacy_value = (getattr(vaccination, "legacy_vaccine_code", "") or "").strip()
        if not legacy_value:
            continue

        vaccine = None
        if legacy_value.isdigit():
            vaccine = Vaccine.objects.filter(pk=int(legacy_value)).first()

        if vaccine is None:
            vaccine = Vaccine.objects.filter(batch_number=legacy_value).first()

        if vaccine is not None:
            vaccination.vaccine_id = vaccine.id
            vaccination.save(update_fields=["vaccine"])


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0001_initial"),
        ("medical", "0003_prescreeningdeclaration"),
    ]

    operations = [
        migrations.RenameField(
            model_name="vaccinationlog",
            old_name="vaccine_id",
            new_name="legacy_vaccine_code",
        ),
        migrations.AddField(
            model_name="vaccinationlog",
            name="vaccine",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="vaccination_logs",
                to="assets.vaccine",
            ),
        ),
        migrations.AlterField(
            model_name="vaccinationlog",
            name="batch_number",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.RunPython(populate_vaccine_fk, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name="vaccinationlog",
                    name="legacy_vaccine_code",
                ),
            ],
        ),
    ]
