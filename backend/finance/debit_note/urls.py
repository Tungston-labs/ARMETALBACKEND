from django.urls import path
from .views import (
    DebitNoteListCreateView,
    DebitNoteDetailView,
    DebitNoteKPICardView,
    BillDebitNoteDetailsView,
    DebitNoteExportView,
)

app_name = "debit_note"

urlpatterns = [
    path("", DebitNoteListCreateView.as_view(), name="debit-note-list-create"),
    path("kpi/", DebitNoteKPICardView.as_view(), name="debit-note-kpi"),
    path("bill-details/", BillDebitNoteDetailsView.as_view(), name="debit-note-bill-details"),
    path("export/", DebitNoteExportView.as_view(), name="debit-note-export"),
    path("<int:pk>/", DebitNoteDetailView.as_view(), name="debit-note-detail"),
]
