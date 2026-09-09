from django.urls import path
from .views import CategoryListCreateView, CategoryDetailView, CategoryKPICardView

urlpatterns = [
    path("", CategoryListCreateView.as_view(), name="category-list-create"),
    path("kpi/", CategoryKPICardView.as_view(), name="category-kpi"),
    path("<int:pk>/", CategoryDetailView.as_view(), name="category-detail"),
]