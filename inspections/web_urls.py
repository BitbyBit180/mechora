from django.urls import path

from .views import inspection_dashboard, model_evaluation_page, quality_incident_detail_page, quality_incidents_page, supervisor_dashboard, supervisor_question_history

app_name = "inspections"

urlpatterns = [
    path("", inspection_dashboard, name="dashboard"),
    path("supervisor/", supervisor_dashboard, name="supervisor"),
    path("supervisor/questions/", supervisor_question_history, name="supervisor_questions"),
    path("evaluation/", model_evaluation_page, name="evaluation"),
    path("incidents/", quality_incidents_page, name="quality_incidents"),
    path("incidents/<int:incident_id>/", quality_incident_detail_page, name="quality_incident_detail"),
]
