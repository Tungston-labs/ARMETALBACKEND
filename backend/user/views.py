from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from user.models import User
from django.contrib.auth import authenticate
from user.serializers import CustomTokenObtainPairSerializer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
from rest_framework.authentication import BasicAuthentication
from django.core.mail import send_mail
from django.conf import settings
from .models import OTP, User, generate_otp
from .serializers import SendOTPSerializer, VerifyOTPSerializer, ResetPasswordSerializer



class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response({"detail": "Logout successful"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": "Invalid or expired refresh token"}, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not user.check_password(old_password):
            return Response({"error": "Old password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        if old_password == new_password:
            return Response({"error": "New password cannot be same as old password."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)

class SendOTPView(APIView):
    authentication_classes = []  
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "This email is not registered."}, status=status.HTTP_404_NOT_FOUND)

        # Generate and save OTP
        otp_code = generate_otp()
        OTP.objects.create(user=user, otp_code=otp_code)

        send_mail(
            subject="Your OTP Code",
            message=f"Your OTP is: {otp_code}",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
        )

        return Response({"detail": "OTP sent to your email address."}, status=status.HTTP_200_OK)

class VerifyOTPView(APIView):
    authentication_classes = []  # Disable auth
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp_input = serializer.validated_data['otp']

        try:
            user = User.objects.get(email=email)
            otp = OTP.objects.filter(user=user, otp_code=otp_input, is_verified=False).last()
            if not otp or otp.is_expired():
                return Response({"detail": "Invalid or expired OTP."}, status=400)

            otp.is_verified = True
            otp.save()
            return Response({"detail": "OTP verified successfully."}, status=200)

        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)

class ResetPasswordView(APIView):
    authentication_classes = []  # Disable auth
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        new_password = serializer.validated_data['new_password']

        try:
            user = User.objects.get(email=email)
            otp = OTP.objects.filter(user=user, is_verified=True).last()
            if not otp:
                return Response({"detail": "OTP not verified."}, status=400)

            user.set_password(new_password)
            user.save()

            # Also update company default password if HR Admin
            if user.is_hr_admin and user.company:
                user.company.default_password = new_password
                user.company.save()

            return Response({"detail": "Password reset successfully."}, status=200)

        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)


class UpdateFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        fcm_token = request.data.get('fcm_token')
        if fcm_token:
            request.user.fcm_token = fcm_token
            request.user.save()
            return Response({"message": "FCM token updated"})
        return Response({"error": "fcm_token is required"}, status=400)
