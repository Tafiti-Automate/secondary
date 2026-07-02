from django.urls import path

from .views import CustomTokenObtainPairView, CustomTokenRefreshView, MeView, UserListView

app_name = "accounts_api"
urlpatterns = [
    path("auth/token/", CustomTokenObtainPairView.as_view(), name="token-obtain"),
    path("auth/token/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("users/", UserListView.as_view(), name="user-list"),
]
