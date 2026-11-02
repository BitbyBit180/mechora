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
    supervisor_dashboard,
)

app_name = "inspections_api"

urlpatterns = [
    path("dashboard/", inspection_dashboard, name="dashboard"),
    path("supervisor/", supervisor_dashboard, name="supervisor"),
    path("", inspection_collection, name="collection"),
    path("batch/", inspection_batch, name="batch"),
    path("statistics/", inspection_statistics, name="statistics"),
    path("evaluation/", inspection_evaluation, name="evaluation"),
    path("<uuid:inspection_id>/", inspection_detail, name="detail"),
    path("<uuid:inspection_id>/status/", inspection_status, name="status"),
    path("<uuid:inspection_id>/review/", inspection_review, name="review"),
    path("<uuid:inspection_id>/assign/", inspection_assign, name="assign"),
    path("batches/<uuid:batch_id>/", batch_detail, name="batch-detail"),
    path("batches/<uuid:batch_id>/items/", batch_items, name="batch-items"),
]
