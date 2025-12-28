from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from matches import views as match_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/matches/<int:match_id>/state/", match_views.match_state),
    path(
        "api/matches/<int:match_id>/max-turn/",
        match_views.set_max_turn_override,
    ),
    path(
        "api/matches/<int:match_id>/queue-orders/",
        match_views.queue_orders,
    ),
    path("api/matches/<int:match_id>/orders/", match_views.submit_order),
    path(
        "api/matches/<int:match_id>/chunks/<int:chunk_q>/<int:chunk_r>/",
        match_views.chunk_detail,
    ),
]
