from django.db import models
from django.core.validators import RegexValidator
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("Telefon raqam kiritish majburiy")

        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(phone, password, **extra_fields)


class User(AbstractUser):
    CHOICE_ROLE = [
        ('client', 'Client'),
        ('master', 'Master'),
        ('owner', 'Owner'),
        ('admin', 'Admin'),

    ]

    phone = models.CharField(max_length=13, validators=[
        RegexValidator(regex=r"^\+998\d{9}$", message="Telefon raqam +998901234567 formatida bo'lishi kerak.")],
                             unique=True)
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    role = models.CharField(max_length=10, choices=CHOICE_ROLE, default='client')
    is_phone_verified = models.BooleanField(default=False)
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True)
    no_show_count = models.PositiveIntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.phone
