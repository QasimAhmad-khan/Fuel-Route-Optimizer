from django.urls import path
from planner.views import health, map_viewer, plan_route

urlpatterns = [
    path("health/", health),
    path("map/", map_viewer),
    path("api/v1/plan/", plan_route),
]
