from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from .views import (
    CustomTokenObtainPairView, CustomTokenRefreshView, MeView, PortalLoginView,
    PortalLogoutView, ProfileView, UserCreateView, UserListView,
    UserManagementListView, UserUpdateView,
)

app_name = "accounts"

urlpatterns = [
    path("auth/token/", CustomTokenObtainPairView.as_view(), name="token-obtain"),
    path("auth/token/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("users/", UserListView.as_view(), name="user-list"),
    path("login/", PortalLoginView.as_view(), name="login"),
    path("logout/", PortalLogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("password-reset/", auth_views.PasswordResetView.as_view(template_name="accounts/password_reset_form.html", email_template_name="accounts/password_reset_email.txt", subject_template_name="accounts/password_reset_subject.txt", success_url=reverse_lazy("accounts:password-reset-done")), name="password-reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"), name="password-reset-done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name="accounts/password_reset_confirm.html", success_url=reverse_lazy("accounts:password-reset-complete")), name="password-reset-confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"), name="password-reset-complete"),
    path("manage/", UserManagementListView.as_view(), name="user-list-page"),
    path("manage/add/", UserCreateView.as_view(), name="user-add"),
    path("manage/<int:pk>/edit/", UserUpdateView.as_view(), name="user-edit"),
]
