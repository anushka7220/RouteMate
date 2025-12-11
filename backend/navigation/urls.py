# navigation/urls.py
from django.urls import path
from .views import get_route_mapbox, index, get_ev_stations,register_face, identify_face
from django.urls import path
from .views import (
    get_route_mapbox,
    index,
    register_user,
    login_user,
    logout_user,
    me,
    voice_assistant,
)
urlpatterns = [ 
    path("", index, name="index"),
    path("api/route", get_route_mapbox, name="get_route_mapbox"), 
    path("api/ev-stations", get_ev_stations, name="get_ev_stations"),
     # 😎 Face ID (NEW official paths)
    path("api/face/register", register_face, name="face_register"),
    path("api/face/identify", identify_face, name="face_identify"),

    # 🔐 Auth
    path("api/auth/register", register_user, name="register_user"),
    path("api/auth/login", login_user, name="login_user"),
    path("api/auth/logout", logout_user, name="logout_user"),
    path("api/auth/me", me, name="me"),

    path("api/assistant", voice_assistant, name="voice_assistant"),
]
