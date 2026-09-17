from django.urls import path
from .views import (
    DeliveryNoteKPICardView,
    DeliveryNoteListCreateView,
    DeliveryNoteDetailView,
)

urlpatterns = [
    path('', DeliveryNoteListCreateView.as_view(), name='deliverynote-list-create'),
    path('kpi/', DeliveryNoteKPICardView.as_view(), name='deliverynote-kpi'),
    path('<int:pk>/', DeliveryNoteDetailView.as_view(), name='deliverynote-detail'),
]
