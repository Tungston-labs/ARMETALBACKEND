from django.urls import path
from .views import (
    DeliveryNoteKPICardView,
    DeliveryNoteListCreateView,
    DeliveryNoteDetailView,
    DeliveryNoteSalesOrderPrefillView,
)

urlpatterns = [
    path('', DeliveryNoteListCreateView.as_view(), name='deliverynote-list-create'),
    path('kpi/', DeliveryNoteKPICardView.as_view(), name='deliverynote-kpi'),
    path('<int:pk>/', DeliveryNoteDetailView.as_view(), name='deliverynote-detail'),
    path('so-prefill/<int:so_id>/', DeliveryNoteSalesOrderPrefillView.as_view(), name='deliverynote-so-prefill'),
]
