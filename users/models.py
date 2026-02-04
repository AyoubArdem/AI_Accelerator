from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser,BaseUserManager,PermissionsMixin,Group, Permission

# Create your models here.

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True) 
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser,PermissionsMixin):
    ROLE_CHOICES=(
        ('admin','ADMIN'),
        ('developer','DEVELOPER'),
        ('client','CLIENT'),
    )
    email=models.EmailField(unique=True)
    username=models.CharField(max_length=150,unique=True)
    first_name=models.CharField(max_length=30, blank=True)
    last_name=models.CharField(max_length=30, blank=True)
    role=models.CharField(max_length=20,choices=ROLE_CHOICES,default='client')
    is_active=models.BooleanField(default=False)
    is_staff=models.BooleanField(default=False)
    date_joined=models.DateTimeField(default=timezone.now)

    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_groups',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )



    objects=UserManager()
    USERNAME_FIELD='email'
    REQUIRED_FIELDS=[]

    def __str__(self):
        return self.email
        