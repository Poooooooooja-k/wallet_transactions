from django.contrib import admin
from django.urls import path
from .views import *


urlpatterns = [
    path('signup/',Signup.as_view()),
    path('login/',Login.as_view()),
    path('addmoney/',AddMoney.as_view()),
    path('moneytransaction/',MoneyTransaction.as_view()),
    path('transaction/history/', TransactionHistory.as_view()),
]
