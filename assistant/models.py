from django.db import models


class Question(models.Model):
    class Status(models.TextChoices):
        ANSWERED = "ANSWERED", "Answered"
        INSUFFICIENT = "INSUFFICIENT", "Insufficient evidence"
        SYSTEM_ERROR = "SYSTEM_ERROR", "System error"

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="assistant_questions")
    machine = models.ForeignKey("machines.Machine", on_delete=models.PROTECT, related_name="questions")
    question_text = models.TextField()
    title = models.CharField(max_length=255, blank=True, default="")
    answer_text = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    citations = models.JSONField(default=list)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def display_title(self):
        return self.title.strip() if self.title.strip() else self.question_text

    def __str__(self):
        return f"{self.machine.machine_id}: {self.display_title()[:60]}"
