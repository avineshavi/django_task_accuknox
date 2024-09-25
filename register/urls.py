from django.urls import path

from .views import (
    UserRegistrationView,
    UserLoginView,
    UserSearchView,
    SendFriendRequestView,
    AcceptFriendRequestView,
    RejectFriendRequestView,
    BlockUserView,
    UnblockUserView,
    FriendsListView,
    PendingFriendRequestsView,
    UserActivityListView,
    UserLogoutView
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('api/signup/', UserRegistrationView.as_view(),name='api_user_register'),
    path('api/login/', UserLoginView.as_view(),name='user_login'),
    path('api/search/', UserSearchView.as_view(), name='user_search'),
    
    path('api/friend-request/send/', SendFriendRequestView.as_view(), name='send_friend_request'),
    path('api/friend-request/accept/', AcceptFriendRequestView.as_view(), name='accept_friend_request'),
    path('api/friend-request/reject/', RejectFriendRequestView.as_view(), name='reject_friend_request'),
    path('api/block-user/', BlockUserView.as_view(), name='block_user'),
    path('api/unblock-user/', UnblockUserView.as_view(), name='unblock_user'),
    path('api/friend-list/', FriendsListView.as_view(), name='friend_list'),
    path('api/pending-friend-requests/', PendingFriendRequestsView.as_view(), name='pending_friend_requests'),
    path('api/user-activity/', UserActivityListView.as_view(), name='user_activity'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('logout/', UserLogoutView.as_view(),name='user_logout'),
]
