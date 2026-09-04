from django.urls import path
from superadmin import views

urlpatterns = [
    path('create-company/', views.CompanyCreateView.as_view(), name='create-company'),
    path('companies/list/', views.CompanyListView.as_view(), name='company-list'),           # GET (list)
    path('companies/<int:pk>/', views.CompanyDetailUpdateDeleteView.as_view(), name='company-detail'),   # GET, PUT, DELETE (detail)
    path('subscriptions/<int:company_id>/', views.CompanySubscriptionListCreateView.as_view(), name='subscription-list'),
    path('subscriptions/mark-paid/<int:pk>/', views.MarkSubscriptionPaidView.as_view(), name='mark-paid'),
    path("invoice/send-email/",views.SendInvoiceEmailView.as_view(), name="send-invoice-email"),
    path("companies/overview/", views.CompanyOverviewView.as_view(), name="company-overview"),
    path("company/self/", views.CompanySelfView.as_view(), name="company-self"),
    path("subscription/company-status/",views.CompanySubscriptionStatusAPIView.as_view(),name="company-status"),
    path("subscription/send-reminder/",views.SendSubscriptionReminderAPIView.as_view(),name="subscription-reminder"),
    path("subscription/send-reminder-email/",views.SendSubscriptionReminderMailAPIView.as_view(),name="send-reminder-email"),
    path("subscription-features/",views.SubscriptionFeatureCreateListAPIView.as_view(),name="subscription-feature-create-list"),
    path("subscription-features/<int:pk>/",views.SubscriptionFeatureRetrieveUpdateDeleteAPIView.as_view(),name="subscription-feature-detail"),
    path("plans/",views.SubscriptionPlanCreateListAPIView.as_view(),name="subscription-plan-create-list"),
    path("plans/<int:pk>/",views.SubscriptionPlanRetrieveUpdateDeleteAPIView.as_view(),name="subscription-plan-detail"),
    path(
    "plans/summary/",
    views.SubscriptionPlanSummaryAPIView.as_view(),
    name="subscription-plan-summary",
),

]


