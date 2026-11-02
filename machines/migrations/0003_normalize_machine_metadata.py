from django.db import migrations


def normalize_machine_metadata(apps, schema_editor):
    Machine = apps.get_model("machines", "Machine")
    defaults = {
        "M-HP200": {"model": "HP-200", "machine_name": "Hydraulic forming press"},
        "M-AC90": {"model": "AC-90", "machine_name": "Air conditioning unit"},
    }
    for machine_id, values in defaults.items():
        Machine.objects.filter(machine_id=machine_id).update(**values)


class Migration(migrations.Migration):
    dependencies = [
        ("machines", "0002_alter_machine_machine_name_alter_machine_model"),
    ]

    operations = [
        migrations.RunPython(normalize_machine_metadata, migrations.RunPython.noop),
    ]
