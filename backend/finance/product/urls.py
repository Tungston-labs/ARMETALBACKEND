from django.urls import path
from .views import ProductListCreateView, ProductDetailView, ProductKPICardView

urlpatterns = [
    path("", ProductListCreateView.as_view(), name="product-list-create"),
    path("kpi/", ProductKPICardView.as_view(), name="product-kpi"),
    path("<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
]
