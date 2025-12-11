# navigation/views.py
import os
import json
import math
import requests
import numpy as np

from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User

from .models import FaceProfile, DriverProfile
from .face_utils import encode_face, face_distance

# ============================================================
#                       EV STATION SUPPORT
# ============================================================

EV_STATIONS_PATH = os.path.join(os.path.dirname(__file__), "ev_stations.json")

try:
    with open(EV_STATIONS_PATH, "r", encoding="utf-8") as f:
        EV_STATIONS = json.load(f)
except Exception as e:
    print("Failed to load ev_stations.json:", e)
    EV_STATIONS = []


def haversine_km(lat1, lon1, lat2, lon2):
    """Compute distance between two lat/lon points."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_nearby_ev_stations(lat, lon, radius_km=15.0):
    results = []
    for s in EV_STATIONS:
        s_lat = s.get("lat")
        s_lon = s.get("lon")
        if s_lat is None or s_lon is None:
            continue

        dist = haversine_km(lat, lon, s_lat, s_lon)
        if dist <= radius_km:
            entry = dict(s)
            entry["distance_km"] = round(dist, 2)
            results.append(entry)

    results.sort(key=lambda x: x.get("distance_km", 9999))
    return results


# ============================================================
#                       ROUTE
# ============================================================

def index(request):
    return HttpResponse("RouteMate backend running ✅")


@csrf_exempt
def get_route_mapbox(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        # 🔍 DEBUG LOG
        print("DEBUG get_route_mapbox body:", body)
        src = body.get("source")
        dst = body.get("destination")
        mode = body.get("mode", "fastest")
        preference = body.get("preference")
        print("DEBUG get_route_mapbox mode:", mode, "preference:", preference)
    except:
        return HttpResponseBadRequest(json.dumps({"error": "Invalid JSON"}))

    if not src or not dst:
        return HttpResponseBadRequest(
            json.dumps({"error": "source and destination required"})
        )

    lat1, lon1 = float(src["lat"]), float(src["lon"])
    lat2, lon2 = float(dst["lat"]), float(dst["lon"])

    if mode == "preference":
        if not preference:
            return HttpResponseBadRequest(
                json.dumps({"error": "preference point required"})
            )
        pref_lat = float(preference["lat"])
        pref_lon = float(preference["lon"])
        coords_part = f"{lon1},{lat1};{pref_lon},{pref_lat};{lon2},{lat2}"
    else:
        coords_part = f"{lon1},{lat1};{lon2},{lat2}"

    print("DEBUG get_route_mapbox coords_part:", coords_part)

    token = os.environ.get("MAPBOX_TOKEN", "")
    if not token:
        return HttpResponseBadRequest(json.dumps({"error": "MAPBOX_TOKEN not set"}))

    url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{coords_part}"
    params = {
        "geometries": "geojson",
        "overview": "full",
        "steps": "true",
        "access_token": token,
    }

    try:
        resp = requests.get(url, params=params, timeout=12)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("routes"):
            return HttpResponseBadRequest(json.dumps({"error": "no routes found"}))

        r0 = data["routes"][0]
        coords = r0["geometry"]["coordinates"]

        route = [{"lat": c[1], "lon": c[0]} for c in coords]

        return JsonResponse({
            "route": route,
            "distance_m": r0["distance"],
            "duration_s": r0["duration"],
        })

    except Exception as e:
        return HttpResponseBadRequest(json.dumps({"error": str(e)}))


# ============================================================
#                       EV API
# ============================================================

@csrf_exempt
def get_ev_stations(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        lat = float(body["lat"])
        lon = float(body["lon"])
        rad = float(body.get("radius_km", 15.0))
    except:
        return HttpResponseBadRequest(json.dumps({"error": "Invalid payload"}))

    stations = get_nearby_ev_stations(lat, lon, rad)
    return JsonResponse({"stations": stations})


# ============================================================
#                       FACE ID (Descriptor-based)
# ============================================================

@csrf_exempt
def register_face(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
        name = body.get("name")
        email = body.get("email")  # 👈
        descriptor = body.get("descriptor")
    except:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not name or not descriptor:
        return JsonResponse({"error": "name and descriptor required"}, status=400)

    embedding = encode_face(descriptor)

    profile, created = FaceProfile.objects.update_or_create(
        email=email,                    # 👈 key on email if you want
        defaults={
            "name": name,
            "descriptor": embedding.tolist(),
        }
    )

    return JsonResponse({"ok": True, "name": profile.name, "email": profile.email})


@csrf_exempt
def identify_face(request):
    """
    POST JSON:
    { "descriptor": [...] }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        descriptor = body.get("descriptor")
    except:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not descriptor:
        return JsonResponse({"error": "descriptor required"}, status=400)

    candidate = encode_face(descriptor)

    profiles = FaceProfile.objects.all()
    if not profiles:
        return JsonResponse({"matched": False, "name": None})

    best_profile = None
    best_dist = 999

    for p in profiles:
        dist = face_distance(p.descriptor, candidate)
        if dist < best_dist:
            best_dist = dist
            best_profile = p

    THRESHOLD = 0.45  # best for face-api.js

    if best_dist < THRESHOLD:
        return JsonResponse({
            "matched": True,
            "name": best_profile.name,
            "distance": float(best_dist),
        })

    return JsonResponse({"matched": False, "name": None, "distance": float(best_dist)})


# ============================================================
#                       AUTH (Email + Password)
# ============================================================

def current_user_to_dict(user):
    if not user or not user.is_authenticated:
        return None
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
    }


@csrf_exempt
def register_user(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        email = (body.get("email") or "").lower()
        password = body.get("password") or ""
    except:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not email or not password:
        return JsonResponse({"error": "email and password required"}, status=400)

    if User.objects.filter(username=email).exists():
        return JsonResponse({"error": "User already exists"}, status=400)

    user = User.objects.create_user(username=email, email=email, password=password)
    DriverProfile.objects.create(user=user)

    login(request, user)

    return JsonResponse({"ok": True, "user": current_user_to_dict(user)})


@csrf_exempt
def login_user(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        email = (body.get("email") or "").lower()
        password = body.get("password") or ""
    except:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    user = authenticate(request, username=email, password=password)

    if not user:
        return JsonResponse({"error": "invalid credentials"}, status=400)

    login(request, user)
    return JsonResponse({"ok": True, "user": current_user_to_dict(user)})


def me(request):
    if not request.user.is_authenticated:
        return JsonResponse({"isAuthenticated": False, "user": None})

    return JsonResponse({
        "isAuthenticated": True,
        "user": current_user_to_dict(request.user)
    })


@csrf_exempt
def logout_user(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    logout(request)
    return JsonResponse({"ok": True})


@csrf_exempt
def voice_assistant(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        print("DEBUG voice_assistant request body:", body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    payload = {
        "message": body.get("message", ""),
        "battery": body.get("battery"),
        "distanceKm": body.get("distanceKm"),
        "etaMin": body.get("etaMin"),
        "speed": body.get("speed"),
        "lat": body.get("lat"),
        "lon": body.get("lon"),
    }

    n8n_url = os.environ.get(
        "N8N_ROUTEMATE_WEBHOOK",
        "http://localhost:5678/webhook/routemate-assistant",
    )

    try:
        resp = requests.post(n8n_url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        print("DEBUG voice_assistant n8n response:", data)
    except Exception as e:
        return JsonResponse(
            {
                "error": "n8n request failed",
                "details": str(e),
            },
            status=502,
        )

    return JsonResponse(data)
