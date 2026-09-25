from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    RecurringServiceViewSet,
    RecurringBillingViewSet,
    RecurringCreateView,
    RecurringSummaryView,
)


router = DefaultRouter()

router.register(
    "services",
    RecurringServiceViewSet,
    basename="recurring-service",
)

router.register(
    "billing",
    RecurringBillingViewSet,
    basename="recurring-billing",
)


urlpatterns = [
    path(
        "create/",
        RecurringCreateView.as_view(),
        name="recurring-create",
    ),

    path(
        "summary/",
        RecurringSummaryView.as_view(),
        name="recurring-summary",
    ),
]

urlpatterns += router.urls