from django.urls import path

from .views import inspection_dashboard, supervisor_dashboard, supervisor_question_history

app_name = "inspections"

urlpatterns = [
    path("", inspection_dashboard, name="dashboard"),
    path("supervisor/", supervisor_dashboard, name="supervisor"),
    path("supervisor/questions/", supervisor_question_history, name="supervisor_questions"),
]
