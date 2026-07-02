from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from config.mixins import AcademicManagerRequiredMixin
from config.permissions import IsAcademicManager
from .forms import LoginForm, ProfileForm, UserCreateForm, UserUpdateForm
from .models import AuditLog, User
from .serializers import UserSerializer


class CustomTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["name"] = user.get_full_name() or user.username
        return token


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer


class CustomTokenRefreshView(TokenRefreshView):
    pass


class UserListView(generics.ListCreateAPIView):
    queryset = User.objects.filter(is_deleted=False).order_by("first_name", "last_name")
    serializer_class = UserSerializer
    permission_classes = [IsAcademicManager]
    search_fields = ["username", "first_name", "last_name", "email", "phone"]


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class PortalLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        if form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(60 * 60 * 24 * 30)
        else:
            self.request.session.set_expiry(0)
        return response


class PortalLogoutView(LogoutView):
    pass


class UserManagementListView(AcademicManagerRequiredMixin, ListView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 20

    def get_queryset(self):
        qs = User.objects.filter(is_deleted=False).order_by("first_name", "last_name")
        query = self.request.GET.get("q", "").strip()
        role = self.request.GET.get("role", "").strip()
        if query:
            qs = qs.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(email__icontains=query))
        if role:
            qs = qs.filter(role=role)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["roles"] = User.ROLE_CHOICES
        return context


class UserCreateView(AcademicManagerRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("accounts:user-list-page")
    extra_context = {"page_title": "Add user", "eyebrow": "Access control", "submit_label": "Create account"}

    def form_valid(self, form):
        response = super().form_valid(form)
        AuditLog.objects.create(actor=self.request.user, action="create", entity_type="User", entity_id=str(self.object.pk), description=f"Created account for {self.object}")
        messages.success(self.request, "User account created successfully.")
        return response


class UserUpdateView(AcademicManagerRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "shared/form.html"
    success_url = reverse_lazy("accounts:user-list-page")
    extra_context = {"page_title": "Edit user", "eyebrow": "Access control", "submit_label": "Save changes"}

    def form_valid(self, form):
        response = super().form_valid(form)
        AuditLog.objects.create(actor=self.request.user, action="update", entity_type="User", entity_id=str(self.object.pk), description=f"Updated account for {self.object}")
        messages.success(self.request, "User account updated.")
        return response


class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Your profile has been updated.")
        return super().form_valid(form)
