from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('upload/', views.upload, name='upload'),
    path('add/device/', views.add_device, name='add_device'),
    path('add/version/', views.add_version, name='add_version'),
    path('add/coeff/', views.add_coeff, name='add_coeff'),
    path('del/data/<int:id_datafile>/', views.del_data, name='del_data'),
    path('del/flights/<int:id_flightfile>/', views.del_flights, name='del_flights'),
    path('rate_/', views.rate_, name='rate_'),
    path('search_/', views.search_, name='search_'),
    path('search/', views.search, name='search'),
    path('view/devices/', views.view_devices, name='view_devices'),
    path('view/data/', views.view_datafiles, name='view_datafiles'),
    path('view/data/<int:id_datafile>/', views.view_data, name='view_data'),
    path('view/flights/', views.view_flightfiles, name='view_flightfiles'),
    path('view/flights/<int:id_flightfile>/', views.view_flights, name='view_flights'),
    path('view/flight/<int:id_flight>/', views.view_flight, name='view_flight'),
]
