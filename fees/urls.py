from django.urls import path

from .views import FeeDashboardView, FeeItemCreateView, FeeItemListView, FeeItemUpdateView, FeeStructureCreateView, FeeStructureDetailView, FeeStructureItemCreateView, FeeStructureListView, FeeStructureUpdateView, GenerateInvoicesView, InvoiceAdjustmentCreateView, InvoiceCreateView, InvoiceDetailView, InvoiceLineCreateView, InvoiceListView, MyFeesView, PaymentCreateView, ReceiptView, ReversePaymentView

app_name = "fees"

urlpatterns = [
    path("", FeeDashboardView.as_view(), name="dashboard"),
    path("items/", FeeItemListView.as_view(), name="item-list"),
    path("items/add/", FeeItemCreateView.as_view(), name="item-add"),
    path("items/<int:pk>/edit/", FeeItemUpdateView.as_view(), name="item-edit"),
    path("structures/", FeeStructureListView.as_view(), name="structure-list"),
    path("structures/add/", FeeStructureCreateView.as_view(), name="structure-add"),
    path("structures/<int:pk>/", FeeStructureDetailView.as_view(), name="structure-detail"),
    path("structures/<int:pk>/edit/", FeeStructureUpdateView.as_view(), name="structure-edit"),
    path("structures/<int:pk>/items/add/", FeeStructureItemCreateView.as_view(), name="structure-item-add"),
    path("structures/<int:pk>/generate/", GenerateInvoicesView.as_view(), name="structure-generate"),
    path("invoices/", InvoiceListView.as_view(), name="invoice-list"),
    path("invoices/add/", InvoiceCreateView.as_view(), name="invoice-add"),
    path("invoices/<int:pk>/", InvoiceDetailView.as_view(), name="invoice-detail"),
    path("invoices/<int:pk>/lines/add/", InvoiceLineCreateView.as_view(), name="invoice-line-add"),
    path("invoices/<int:pk>/adjustments/add/", InvoiceAdjustmentCreateView.as_view(), name="adjustment-add"),
    path("invoices/<int:pk>/payments/add/", PaymentCreateView.as_view(), name="payment-add"),
    path("payments/<int:pk>/receipt/", ReceiptView.as_view(), name="receipt"),
    path("payments/<int:pk>/reverse/", ReversePaymentView.as_view(), name="payment-reverse"),
    path("my-account/", MyFeesView.as_view(), name="my-fees"),
]
