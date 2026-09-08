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

urlpatterns = [
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


    path(
        "api/schema/",
        SpectacularAPIView.as_view(),
        name="schema"
    ),

    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema"
        ),
        name="swagger-ui"
    ),

    path(
        "api/redoc/",
        SpectacularRedocView.as_view(
            url_name="schema"
        ),
        name="redoc"
    ),









]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
