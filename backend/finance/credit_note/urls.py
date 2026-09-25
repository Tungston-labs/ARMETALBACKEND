from django.urls import path
from .views import (
    CreditNoteKPICardView,
    CreditNoteListCreateView,
    CreditNoteDetailView,
    InvoiceCreditNoteDetailsView,
)

urlpatterns = [
    path('', CreditNoteListCreateView.as_view(), name='creditnote-list-create'),
    path('kpi/', CreditNoteKPICardView.as_view(), name='creditnote-kpi'),
    path('invoice-details/', InvoiceCreditNoteDetailsView.as_view(), name='creditnote-invoice-details'),
    path('<int:pk>/', CreditNoteDetailView.as_view(), name='creditnote-detail'),
]
