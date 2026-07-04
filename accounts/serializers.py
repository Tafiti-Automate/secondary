from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role", "phone", "preferred_language", "profile_picture", "is_active"]
        read_only_fields = ["id"]
