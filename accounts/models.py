from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # Use your spelling: name_spase
    name_spase = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.username