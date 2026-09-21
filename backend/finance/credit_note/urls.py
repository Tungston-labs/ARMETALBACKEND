from django.urls import path
from .views import (
    CreditNoteKPICardView,
    CreditNoteListCreateView,
    CreditNoteDetailView,
)

urlpatterns = [
    path('', CreditNoteListCreateView.as_view(), name='creditnote-list-create'),
    path('kpi/', CreditNoteKPICardView.as_view(), name='creditnote-kpi'),
    path('<int:pk>/', CreditNoteDetailView.as_view(), name='creditnote-detail'),
]
