from django.urls import path

from .views import chat_page, supervisor_dashboard, supervisor_history, supervisor_question_detail


app_name = "assistant"

urlpatterns = [
    path("", chat_page, name="chat"),
    path("supervisor/", supervisor_dashboard, name="supervisor_dashboard"),
    path("supervisor/history/", supervisor_history, name="supervisor_history"),
    path("supervisor/history/<int:question_id>/", supervisor_question_detail, name="supervisor_question_detail"),
]
