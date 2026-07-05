from django.contrib import admin

from .models import FeeItem, FeeStructure, FeeStructureItem, InvoiceAdjustment, InvoiceLine, Payment, StudentInvoice

admin.site.register((FeeItem, FeeStructure, FeeStructureItem, StudentInvoice, InvoiceLine, InvoiceAdjustment, Payment))
