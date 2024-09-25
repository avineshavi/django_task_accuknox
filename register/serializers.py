from rest_framework import serializers
from .models import User
from .models import (FriendRequest, BlockedUser, UserActivity)
from django.contrib.auth import authenticate
from cryptography.fernet import Fernet
from django.conf import settings
from .utils import encrypt_email


class UserRegistrationSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password', 'confirm_password']
        extra_kwargs = {
            'password': {'write_only': True}
        }
    
    def validate_email(self, value):
        """Check if the email already exists in the system."""
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        return data

    def create(self, validated_data):
        email = validated_data['email'].lower()
        user = User.objects.create_user(
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            email=email,  
            username=email,
            password=validated_data['password']
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    fernet = Fernet(settings.FERNET_KEY)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email').lower()
        password = data.get('password')
        
        if email and password:
            
            try:
                user = User.objects.get(username=email)
                
                encrypted_email = encrypt_email(email=email)
                if user.email == encrypted_email:
                    authenticated_user = authenticate(username=email, password=password)
                    if authenticated_user:
                        return {'user': authenticated_user}
                else:
                    raise serializers.ValidationError('Invalid credentials')   
            except User.DoesNotExist:
                raise serializers.ValidationError('Invalid credentials')
            raise serializers.ValidationError('Invalid credentials')
        raise serializers.ValidationError('Email and password required')


class UserSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name')

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        search_term = request.query_params.get('search', None) if request else None

        if search_term:
            encrypted_search_term = encrypt_email(email=search_term)
            is_exist = User.objects.filter(email=encrypted_search_term).exists()
            print(is_exist)
            if is_exist:
                return {
                    'message': 'Email has found',
                    'id': representation['id'], 
                    'first_name': representation['first_name'],
                    'last_name': representation.get('last_name', '')
                }
        return {
            'message': 'Search term contains the following names.',
            'id': representation['id'], 
            'first_name': representation['first_name'],
            'last_name': representation.get('last_name', '')
        }
        

class FriendRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = FriendRequest
        fields = ['sender', 'receiver', 'status', 'created_at', 'cooldown_until']


class BlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockedUser
        fields = ['user', 'blocked_user', 'created_at']


class UserActivitySerializer(serializers.ModelSerializer):
    content_object = serializers.SerializerMethodField()

    class Meta:
        model = UserActivity
        fields = ['user', 'action_type', 'content_object', 'timestamp']

    def get_content_object(self, obj):
        if isinstance(obj.content_object, FriendRequest):
            return {
                'id': obj.content_object.id,
                'sender': obj.content_object.sender.username,  # sender is from the FriendRequest model
                'receiver': obj.content_object.receiver.username,  # receiver is from the FriendRequest model
                'status': obj.content_object.status,
                'created_at': obj.content_object.created_at,
                'updated_at': obj.content_object.updated_at,
            }
        return str(obj.content_object)