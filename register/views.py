from django.contrib.auth import authenticate
# from django.contrib.auth.models import User
from .models import (
    User, UserActivity)
from django.db.models import Q
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response 
from rest_framework.views import APIView 
from rest_framework.permissions import IsAuthenticated 
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from .models import (FriendRequest, BlockedUser)
from register.utils import (
    set_jwt_token_cookie, add_access_token_validity_cookie, encrypt_email)

from django.contrib.postgres.search import SearchVector, TrigramSimilarity, SearchQuery
from django.core.cache import cache
from rest_framework import permissions, generics, status
from django.db import transaction
from datetime import timedelta
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
import logging

from rest_framework import(
    generics, permissions, status
)
from .serializers import(
    UserRegistrationSerializer, UserLoginSerializer, UserSearchSerializer,UserActivitySerializer
    
)


class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        serializer.save()


class UserLoginView(APIView):
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle] 

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        response_data = Response({
            'access': str(refresh.access_token),
        }, status=status.HTTP_200_OK)

        if refresh:
            set_jwt_token_cookie(
                response=response_data,
                refresh_token=refresh
            )
            add_access_token_validity_cookie(response_data,
                                                is_yc_user=True)
        return response_data
 

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        request.auth.delete()
        return Response({"detail":"Logout successful"},status=status.HTTP_200_OK)


class DynamicPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100 

    def get_max_page_size(self, total_records):
        """
        Dynamically set the max_page_size based on the number of records.
        If total records exceed 1000, set max_page_size to 10% of the total records.
        Ensure that max_page_size doesn't exceed 100.
        """
        if total_records > 1000:
            dynamic_max_page_size = total_records // 10
            return min(dynamic_max_page_size, 100)
        return 100 

    def paginate_queryset(self, queryset, request, view=None):
        total_records = queryset.count()
        self.max_page_size = self.get_max_page_size(total_records)
        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        return Response({
            'total_count': self.page.paginator.count,
            'records_count_per_page': len(data),
            'max_page_size': self.max_page_size,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })


class UserSearchView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSearchSerializer
    pagination_class = DynamicPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        search_term = self.request.query_params.get('search')
        cache_key = f"user_search_{search_term}_{self.request.query_params.get('page', 1)}"

        cached_results = cache.get(cache_key)
        if cached_results:
            return cached_results
        
        queryset = super().get_queryset()

        if search_term:
            encrypted_search_term = encrypt_email(email=search_term.lower())
            is_exist = User.objects.filter(email__iexact=encrypted_search_term).exists()
            if is_exist:
                queryset = queryset.filter(email__iexact=encrypted_search_term)
            else:
                search_query = SearchQuery(search_term, search_type='plain')
                queryset = queryset.annotate(
                    search=SearchVector('first_name', 'last_name'),
                    similarity=TrigramSimilarity('first_name', search_term) + TrigramSimilarity('last_name', search_term)
                ).filter(
                    Q(first_name__icontains=search_term) | Q(last_name__icontains=search_term) | Q(search=search_query)
                ).order_by('-similarity')

        cache.set(cache_key, list(queryset), timeout=60 * 5)
        return queryset


class SendFriendRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes= [ScopedRateThrottle]
    throttle_scope = 'frnd_request'

    def post(self, request, *args, **kwargs):
        receiver_id = request.data.get('receiver_id')
        if not receiver_id:
            return Response({"detail": "Receiver ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                receiver = User.objects.get(id=receiver_id)
            except User.DoesNotExist:
                return Response({"detail": "Receiver not found."}, status=status.HTTP_404_NOT_FOUND)
            
            sender = request.user

            is_blocked_exist = BlockedUser.objects.filter(blocker=receiver, blocked=sender).exists()
            if is_blocked_exist:
                return Response({"detail": "You are blocked by this user."}, status=status.HTTP_403_FORBIDDEN)

            friend_request = FriendRequest.objects.select_related('sender', 'receiver').filter(
                Q(sender=sender, receiver=receiver) |
                Q(sender=receiver, receiver=sender)
            ).first()

            if friend_request:
                if friend_request.status == 'PENDING':
                    return Response({"detail": "Friend request already exists."}, status=status.HTTP_400_BAD_REQUEST)

                if friend_request.cooldown_until and timezone.now() < friend_request.cooldown_until:
                    return Response({"detail": "Cannot send a request until the cooldown period ends."}, status=status.HTTP_403_FORBIDDEN)

                friend_request.status = 'PENDING'
                friend_request.cooldown_until = None
                friend_request.save()
            else:
                FriendRequest.objects.create(sender=sender, receiver=receiver)
            log_user_activity(request.user, 'FR_SENT', friend_request)
            return Response({"detail": "Friend request sent."}, status=status.HTTP_201_CREATED)


class AcceptFriendRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        friend_request_id = request.data.get('friend_request_id')
        if not friend_request_id:
            return Response({"detail": "Friend request ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                friend_request = FriendRequest.objects.select_related('sender', 'receiver').get(id=friend_request_id, receiver=request.user)
            except ObjectDoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)
            if friend_request.status != 'PENDING':
                return Response({"detail": "Friend request is no longer pending."}, status=status.HTTP_400_BAD_REQUEST)

            friend_request.status = 'ACCEPTED'
            friend_request.save()
            log_user_activity(request.user, 'FR_ACCEPTED', friend_request)
            return Response({"detail": "Friend request accepted."}, status=status.HTTP_200_OK)


class RejectFriendRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        friend_request_id = request.data.get('friend_request_id')
        if not friend_request_id:
            return Response({"detail": "Friend request ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            friend_request = FriendRequest.objects.select_related('sender', 'receiver').get(id=friend_request_id, receiver=request.user)

            if friend_request.status != 'PENDING':
                return Response({"detail": "Friend request is no longer pending."}, status=status.HTTP_400_BAD_REQUEST)

            friend_request.status = 'REJECTED'
            friend_request.cooldown_until = timezone.now() + timedelta(hours=24)
            friend_request.save()
            log_user_activity(request.user, 'FR_REJECTED', friend_request)
            return Response({"detail": "Friend request rejected."}, status=status.HTTP_200_OK)


class BlockUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        blocked_user_id = request.data.get('blocked_user_id')
        if not blocked_user_id:
            return Response({"detail": "Blocked user ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            blocked_user = User.objects.get(id=blocked_user_id)

            BlockedUser.objects.get_or_create(blocker=request.user, blocked=blocked_user)

            return Response({"detail": f"Blocked {blocked_user.first_name} {blocked_user.last_name}."}, status=status.HTTP_201_CREATED)


class UnblockUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        blocked_user_id = request.data.get('blocked_user_id')
        if not blocked_user_id:
            return Response({"detail": "Blocked user ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            blocked_user = User.objects.get(id=blocked_user_id)

            BlockedUser.objects.filter(blocker=request.user, blocked=blocked_user).delete()

            return Response({"detail": f"Unblocked {blocked_user.first_name} {blocked_user.last_name}."}, status=status.HTTP_200_OK)


class FriendsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        cache_key = f"friends_list_{user.id}"
        
        friends_list = cache.get(cache_key)
        if friends_list is None:
            friends = FriendRequest.objects.filter(
                Q(sender=user, status='ACCEPTED') | Q(receiver=user, status='ACCEPTED')
            ).select_related('sender', 'receiver')

            friends_list = [
                {
                    "user_id": friend.sender.id if friend.receiver == user \
                        else friend.receiver.id,
                    "full_name": f"{friend.sender.first_name} {friend.sender.last_name}" \
                        if friend.receiver == user \
                        else f"{friend.receiver.first_name} {friend.receiver.last_name}",
                }
                for friend in friends
            ]
            cache.set(cache_key, friends_list, timeout=60 * 5)

        return Response(friends_list, status=status.HTTP_200_OK)


class PendingFriendRequestsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = DynamicPagination

    def get(self, request, *args, **kwargs):
        user = request.user
        pending_requests = FriendRequest.objects.filter(
            receiver=user, status='PENDING'
        ).select_related('sender').order_by('created_at')
        
        # Paginate the results
        paginator = DynamicPagination()
        page = paginator.paginate_queryset(pending_requests, request)

        if page is not None:
            # Serialize the paginated data
            data = [
                {
                    "friend_request_id": friend_request.id,
                    "sender": {
                        "full_name": f"{friend_request.sender.first_name} {friend_request.sender.last_name}"
                    },
                    "sent_at": friend_request.created_at
                }
                for friend_request in page
            ]
            return paginator.get_paginated_response(data)

        return Response({"detail": "No pending requests found."}, status=status.HTTP_404_NOT_FOUND)


class UserActivityListView(generics.ListAPIView):
    serializer_class = UserActivitySerializer
    pagination_class = DynamicPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        cache_key = f'user_activity_{user.id}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        queryset = UserActivity.objects.filter(user=user).select_related('content_type').order_by('-timestamp')
        
        # Cache the result for 5 minutes
        cache.set(cache_key, queryset, timeout=300)
        return queryset


def log_user_activity(user, action_type, obj):
    UserActivity.objects.create(
        user=user,
        action_type=action_type,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.id
    )