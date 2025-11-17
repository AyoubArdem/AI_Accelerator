from django.urls import path
from .views import RegisterUserView,ActivateAccountView,LoginView,LogoutView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
urlpatterns = [
   path('register/',RegisterUserView.as_view(),name='register'),
   path('activate/<uid>/<token>/',ActivateAccountView.as_view(),name='activate'),
   path('login/',LoginView.as_view(),name='login'),
   path('logout/', LogoutView.as_view(), name='logout'),
   path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
   path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
   path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

]
