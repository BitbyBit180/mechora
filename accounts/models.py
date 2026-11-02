from django.db import models


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ADMINISTRATOR = "Administrator", "Administrator"
        ENGINEER = "Engineer", "Engineer"
        SUPERVISOR = "Supervisor", "Supervisor"

    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=32, choices=Role.choices)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
