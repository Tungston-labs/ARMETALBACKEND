from django.urls import path
from .views import (
    QuotationListCreateView,
    QuotationDetailView,
    QuotationKPICardView,
    QuotationConvertSOView,
)

urlpatterns = [
    path("", QuotationListCreateView.as_view(), name="quotation-list-create"),
    path("kpi/", QuotationKPICardView.as_view(), name="quotation-kpi"),
    path("summary/", QuotationKPICardView.as_view(), name="quotation-summary"),
    path("<int:pk>/", QuotationDetailView.as_view(), name="quotation-detail"),
    path("<int:pk>/convert_so/", QuotationConvertSOView.as_view(), name="quotation-convert-so"),
    path("<int:pk>/convert-so/", QuotationConvertSOView.as_view(), name="quotation-convert-so-alt"),
]
