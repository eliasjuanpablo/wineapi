from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from rest_framework import serializers
from django.utils import timezone
from django.db import models

from api.models import Winery, Country, Gender, Language
from api.serializers import WinerySerializer

from . import ADMIN, TOURIST, WINERY
import random
import string


USER_TYPE_CHOICES = [
    (TOURIST, 'TOURIST'),
    (WINERY, 'WINERY'),
    (ADMIN, 'ADMIN')
]


class WineUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifiers
    for authentication instead of usernames.
    """
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError('The Email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        if not password:
            password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=20))
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        try:
            extra_fields['country'] = Country.objects.get(id=extra_fields['country'])
            extra_fields['gender'] = Gender.objects.get(id=extra_fields['gender'])
            extra_fields['language'] = Language.objects.get(id=extra_fields['language'])
        except Exception:
            raise ValueError

        extra_fields['user_type'] = ADMIN

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)


class WineUser(AbstractBaseUser, PermissionsMixin):

    email = models.EmailField('email address', unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    # Custom fields
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    birth_date = models.DateField(null=True, blank=True)
    user_type = models.CharField(max_length=20, blank=True, choices=USER_TYPE_CHOICES, default=TOURIST)

    winery = models.ForeignKey('api.winery', null=True, blank=True, on_delete=models.CASCADE)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    gender = models.ForeignKey(Gender, on_delete=models.PROTECT)
    language = models.ForeignKey(Language, on_delete=models.PROTECT)
    phone = models.CharField(max_length=15)

    objects = WineUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'country', 'language', 'gender', 'phone']

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return '{} {}'.format(self.first_name, self.last_name)


class UserSerializer(serializers.ModelSerializer):
    """Serializes a user for the api endpoint"""

    id = serializers.ReadOnlyField()
    winery = WinerySerializer(required=False)
    user_type = serializers.ReadOnlyField()

    class Meta:
        model = get_user_model()
        fields = (
            'id',
            'email',
            'first_name',
            'last_name',
            'birth_date',
            'gender',
            'country',
            'language',
            'phone',
            'winery',
            'user_type',
        )

    def create(self, validated_data):
        """Create and return a new user"""
        winery_data = validated_data.pop('winery', None)
        user = WineUser.objects.create_user(**validated_data)
        if winery_data:
            winery = Winery.objects.create(**winery_data)
            user.winery = winery
            user.user_type = WINERY
        user.save()
        return user

    def update(self, instance, validated_data):
        """User update method"""
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.birth_date = validated_data.get('birth_date', instance.birth_date)
        instance.gender = validated_data.get('gender', instance.gender)
        instance.country = validated_data.get('country', instance.country)
        instance.language = validated_data.get('language', instance.language)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.save()
        return instance

    def validate_winery(self, winery):
        if self.instance:
            raise serializers.ValidationError({'winery': 'Winery can only be specified on creation'})
        return winery

    def to_representation(self, obj):
        self.fields['gender'] = serializers.SlugRelatedField(slug_field='name', read_only=True)
        self.fields['language'] = serializers.SlugRelatedField(slug_field='name', read_only=True)
        self.fields['country'] = serializers.SlugRelatedField(slug_field='name', read_only=True)
        return super().to_representation(obj)
