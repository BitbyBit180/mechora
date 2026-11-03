from django.db import migrations


def create_pending_reviews(apps, schema_editor):
    QualityIncident = apps.get_model("inspections", "QualityIncident")
    IncidentReview = apps.get_model("inspections", "IncidentReview")
    for incident in QualityIncident.objects.all().iterator():
        IncidentReview.objects.get_or_create(
            incident_id=incident.pk,
            defaults={"status": "Pending"},
        )


class Migration(migrations.Migration):
    dependencies = [("inspections", "0004_incident_review_history")]
    operations = [migrations.RunPython(create_pending_reviews, migrations.RunPython.noop)]
