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


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/',include('user.urls')),
    path('api/',include('superadmin.urls')),
    path('api/',include('departments.urls')),
    path('api/', include('employee.urls')),
    path('api/',include('leave.urls')),
    path('api/',include('task.urls')),
    path('api/',include('attendance.urls')),
    path('api/',include('holidays.urls')),
    path('api/',include('payroll.urls')),
    path('api/reimbursements/',include('reimbursement.urls')),
    path('api/project/',include('project.urls')),
    path('api/admindashboard/',include('dashboard.urls')),
    path('api/finance/',include('finance.urls')),



    





]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
