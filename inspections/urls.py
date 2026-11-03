from django.urls import path

from .views import (
    batch_detail,
    batch_items,
    inspection_batch,
    inspection_collection,
    inspection_detail,
    inspection_assign,
    inspection_review,
    inspection_statistics,
    inspection_status,
    inspection_evaluation,
    inspection_dashboard,
    model_integrity,
    supervisor_dashboard,
    quality_incident_collection,
    quality_incident_detail,
    quality_incident_inspections,
    quality_incident_review,
    quality_incident_source,
    quality_incident_batch_create,
    quality_incident_batch_detail,
)

app_name = "inspections_api"

urlpatterns = [
    path("dashboard/", inspection_dashboard, name="dashboard"),
    path("supervisor/", supervisor_dashboard, name="supervisor"),
    path("", inspection_collection, name="collection"),
    path("batch/", inspection_batch, name="batch"),
    path("statistics/", inspection_statistics, name="statistics"),
    path("evaluation/", inspection_evaluation, name="evaluation"),
    path("model-integrity/", model_integrity, name="model-integrity"),
    path("incidents/", quality_incident_collection, name="quality-incidents"),
    path("incidents/inspections/", quality_incident_inspections, name="quality-incident-inspections"),
    path("incidents/batch/", quality_incident_batch_create, name="quality-incident-batch-create"),
    path("incidents/batch/<uuid:batch_id>/", quality_incident_batch_detail, name="quality-incident-batch-detail"),
    path("incidents/sources/<str:document_id>/pdf/", quality_incident_source, name="quality-incident-source"),
    path("incidents/<int:incident_id>/", quality_incident_detail, name="quality-incident-detail"),
    path("incidents/<int:incident_id>/review/", quality_incident_review, name="quality-incident-review"),
    path("<uuid:inspection_id>/", inspection_detail, name="detail"),
    path("<uuid:inspection_id>/status/", inspection_status, name="status"),
    path("<uuid:inspection_id>/review/", inspection_review, name="review"),
    path("<uuid:inspection_id>/assign/", inspection_assign, name="assign"),
    path("batches/<uuid:batch_id>/", batch_detail, name="batch-detail"),
    path("batches/<uuid:batch_id>/items/", batch_items, name="batch-items"),
]
