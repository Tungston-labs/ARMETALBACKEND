"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf.urls.static import static
from django.conf import settings
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="Armetal Backend API",
      default_version='v1',
      description="API documentation for Armetal Backend system including Warehouse & Product module",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('admin/', admin.site.urls),
    path('api/',include('user.urls')),
    path('api/',include('superadmin.urls')),
    path('api/',include('hr.departments.urls')),
    path('api/', include('hr.employee.urls')),
    path('api/',include('hr.leave.urls')),
    path('api/',include('hr.task.urls')),
    path('api/',include('hr.attendance.urls')),
    path('api/',include('hr.holidays.urls')),
    path('api/',include('hr.payroll.urls')),
    path('api/reimbursements/',include('hr.reimbursement.urls')),
    path('api/project/',include('hr.project.urls')),
    path('api/admindashboard/',include('hr.dashboard.urls')),
    path('api/finance/',include('hr.finance.urls')),
    path('api/finance/category/', include('finance.category.urls')),
    path('api/finance/warehouse/', include('finance.warehouse.urls')),
    path('api/finance/product/', include('finance.product.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    