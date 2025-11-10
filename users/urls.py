from django.urls import path
from .views import RegisterUserView,ActivateAccountView,LoginView,LogoutView
urlpatterns = [
   path('register/',RegisterUserView.as_view(),name='register'),
   path('activate/<uid>/<token>/',ActivateAccountView.as_view(),name='activate'),
   path('login/',LoginView.as_view(),name='login'),
   path('logout/', LogoutView.as_view(), name='logout'),
]
