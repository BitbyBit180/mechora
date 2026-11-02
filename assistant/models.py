from django.db import models


class Question(models.Model):
    class Status(models.TextChoices):
        ANSWERED = "ANSWERED", "Answered"
        INSUFFICIENT = "INSUFFICIENT", "Insufficient evidence"
        SYSTEM_ERROR = "SYSTEM_ERROR", "System error"

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="assistant_questions")
    machine = models.ForeignKey("machines.Machine", on_delete=models.PROTECT, related_name="questions")
    question_text = models.TextField()
    answer_text = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    citations = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.machine.machine_id}: {self.question_text[:60]}"
