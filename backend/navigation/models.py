# navigation/models.py
from django.db import models
from django.contrib.auth.models import User


class Driver(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # store the face embedding as JSON (list of floats)
    face_embedding = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class DriverProfile(models.Model):
    """
    Links a Django auth User to driving-related data.
    Right now it's minimal, but later you can add:
    - preferred_vehicle
    - last_trip
    - EV settings, etc.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="driver_profile",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.email or self.user.username


class FaceProfile(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True, unique=True)
    # descriptor is a list[float] of length 128
    descriptor = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or f"FaceProfile {self.id}"
