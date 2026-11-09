from django.db import models


class CreatedAtAbstract(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class UpdatedAtAbstract(models.Model):
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TimestampedAbstract(CreatedAtAbstract, UpdatedAtAbstract):
    class Meta:
        abstract = True
