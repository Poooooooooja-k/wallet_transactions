from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomUser,Transaction

class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'name', 'phone_number', 'password']

    def validate(self, data):
        email = data.get('email')
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({'email': ['A user with this email already exists.']})
       
        phone_number = data.get('phone_number')
        if not phone_number.isnumeric() or len(phone_number) != 10:
            raise serializers.ValidationError({'phone_number': ['Phone number must be 10 digits.']})

        return data

    def create(self, validated_data):
        password = validated_data.pop('password')
        instance = self.Meta.model(**validated_data)

        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance
    

class LoginSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ['email', 'password']

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        if email and password:
            user = CustomUser.objects.filter(email=email).first()
            if user:
                if not user.check_password(password):
                    raise AuthenticationFailed({'error': 'Incorrect password!!'})
            else:
                raise AuthenticationFailed({'error': 'User not found!!'})
        else:
            raise AuthenticationFailed({'error': 'Email and password are required!!'})

class AddMoneySerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Your Amount should be greater than zero.")
        return value
    
class TransactionSerializer(serializers.ModelSerializer):
    sender_name=CustomUserSerializer(source='sender',read_only=True)
    recipient_name=CustomUserSerializer(source='recipient',read_only=True)
    class Meta:
        model =Transaction
        fields = ['id', 'sender', 'recipient', 'amount', 'timestamp','sender_name','recipient_name']


class MoneyTransactionSerializer(serializers.Serializer):
    recipient_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value
    
class RetrieveContactSerializer(serializers.ModelSerializer):
    class Meta:
        model=CustomUser
        fields=['id','name','phone_number']


class WithdrawalSerializer(serializers.Serializer):
    withdrawal_amount = serializers.DecimalField(max_digits=10, decimal_places=2)