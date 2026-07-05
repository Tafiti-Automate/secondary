from django.urls import path

from .views import StaffBankDetailView, StaffCreateView, StaffDeleteView, StaffDetailView, StaffDocumentCreateView, StaffListView, StaffUpdateView

app_name = "staff"

urlpatterns = [
    path("", StaffListView.as_view(), name="list"),
    path("add/", StaffCreateView.as_view(), name="add"),
    path("<int:pk>/", StaffDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", StaffUpdateView.as_view(), name="edit"),
    path("<int:pk>/archive/", StaffDeleteView.as_view(), name="delete"),
    path("<int:pk>/bank-details/", StaffBankDetailView.as_view(), name="bank-detail"),
    path("<int:pk>/documents/add/", StaffDocumentCreateView.as_view(), name="document-add"),
]
