from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError,AuthenticationFailed
from rest_framework.views import APIView
from .models import *
from rest_framework.permissions import IsAuthenticated 
from .serializer import *
from rest_framework import permissions,status
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from razorpay import Client as RazorpayClient
from django.conf import settings



class Signup(APIView):
    def post(self, request):
        data=request.data
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        if password != confirm_password:
            raise serializers.ValidationError({'confirm_password': ['Passwords do not match.']})
        serializer = CustomUserSerializer(data=data)
        if serializer.is_valid():
            user=serializer.save()
            Wallet.objects.create(user=user)
            return Response({'message': 'Registration successfull', 'data': serializer.data}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class Login(APIView):
    def post(self,request):
        data=request.data
        email=data.get('email')
        user=CustomUser.objects.filter(email=email).first()
        serializer=LoginSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data,status=status.HTTP_201_CREATED)
        refresh = RefreshToken.for_user(user)  
        return Response({'access_token': str(refresh.access_token), 'refresh': str(refresh)}, status=status.HTTP_200_OK)
    

class AddMoney(APIView):
    permission_classes = [IsAuthenticated] 
    def post(self, request):
        user = request.user 
        serializer = AddMoneySerializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data['amount']
            wallet, created = Wallet.objects.get_or_create(user=user)
            wallet.balance += amount
            wallet.save()
            return Response({'message': 'Money added successfully.', 'new_balance': wallet.balance}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class MoneyTransaction(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sender_wallet = Wallet.objects.get(user=request.user)
        serializer = MoneyTransactionSerializer(data=request.data)

        if serializer.is_valid():
            recipient_id = serializer.validated_data.get('recipient_id')
            amount = serializer.validated_data.get('amount')

            if recipient_id is None:
                return Response({'error': 'Recipient ID is required'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                with transaction.atomic():
                    sender_wallet_instance = Wallet.objects.select_for_update().get(user=request.user)
                    recipient_wallet_instance = Wallet.objects.select_for_update().get(user_id=recipient_id)

                    if sender_wallet_instance.balance >= amount:
                        sender_wallet_instance.balance -= amount
                        sender_wallet_instance.save()

                        recipient_wallet_instance.balance += amount
                        recipient_wallet_instance.save()

                        transaction_instance = Transaction.objects.create(sender=sender_wallet_instance.user, recipient=recipient_wallet_instance.user, amount=amount)
                        return Response({'message': 'Transaction successful', 'transaction_id': transaction_instance.id}, status=status.HTTP_200_OK)
                    else:
                        return Response({'error': 'Insufficient balance'}, status=status.HTTP_400_BAD_REQUEST)
            except Wallet.DoesNotExist:
                return Response({'error': 'Recipient not found'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class TransactionHistory(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        sent_transactions = Transaction.objects.filter(sender=user)
        received_transactions = Transaction.objects.filter(recipient=user)
        sent_transactions_data = TransactionSerializer(sent_transactions, many=True).data
        received_transactions_data = TransactionSerializer(received_transactions, many=True).data
        return Response({
            'sent_transactions': sent_transactions_data,
            'received_transactions': received_transactions_data
        }, status=status.HTTP_200_OK)

class RetriveBalance(APIView):
    def get(self,request):
        user=request.user
        try:
            wallet = Wallet.objects.get(user=user)
            balance = wallet.balance
            return Response({'balance': balance}, status=status.HTTP_200_OK)
        except Wallet.DoesNotExist:
            return Response({'error': 'Wallet not found for the user'}, status=status.HTTP_400_BAD_REQUEST)

class RetrieveContacts(APIView):
  def get(self, request):
    user = request.user
    print(user, "--------user----------")
    users = CustomUser.objects.exclude(id=user.id)
    serializer = RetrieveContactSerializer(users, many=True)
    return Response({'data': serializer.data, 'message': 'contacts retrieved successfully'}, status=status.HTTP_200_OK)
  
class WalletWithdrawal(APIView):
    def post(self, request):
        razorpay_key_id = settings.RAZORPAY_KEY_ID
        razorpay_key_secret = settings.RAZORPAY_KEY_SECRET
        razorpay_client = RazorpayClient(auth=(razorpay_key_id, razorpay_key_secret))
        serializer = WithdrawalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        withdrawal_amount = serializer.validated_data.get('withdrawal_amount')
        user_id = request.user.id
        try:
            wallet = Wallet.objects.get(user_id=user_id)
        except Wallet.DoesNotExist:
            return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)
        if withdrawal_amount > wallet.balance:
            return Response({"error": "Insufficient balance"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            withdrawal_response = razorpay_client.payment.create(
                {
                    "amount": withdrawal_amount * 100, 
                    "currency": "INR",  # Assuming currency is INR
                    "mode": "NEFT",
                    "purpose": "wallet withdrawal",
                    "fund_account_id": "YOUR_FUND_ACCOUNT_ID",  # Fund account ID from RazorpayX
                    "beneficiary_account": {
                        "name": request.user.name, 
                        "ifsc": "YOUR_IFSC_CODE",# bank IFSC code
                        "account_number": "USER_ACCOUNT_NUMBER"  # bank account number
                    }
                }
            )
            wallet.balance -= withdrawal_amount
            wallet.save()
            Transaction.objects.create(
                sender=request.user,
                recipient=request.user,
                amount=withdrawal_amount,
            )
            return Response({"message": "Withdrawal successful", "data": withdrawal_response}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)