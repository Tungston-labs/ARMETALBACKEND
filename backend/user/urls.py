from django.urls import path
from .views import CustomTokenObtainPairView,LogoutView,ChangePasswordView,SendOTPView,VerifyOTPView,ResetPasswordView,UpdateFCMTokenView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='common-logout'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('forgot-password/send-otp/', SendOTPView.as_view()),
    path('forgot-password/verify-otp/', VerifyOTPView.as_view()),
    path('forgot-password/reset/', ResetPasswordView.as_view()),
    path('update-fcm-token/', UpdateFCMTokenView.as_view(), name='update-fcm-token'),

]
