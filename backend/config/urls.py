from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Scalar is an alternative API docs viewer. It reads the same OpenAPI schema
# as Swagger UI, so it needs no extra Python package, just this small page.
SCALAR_HTML = """<!doctype html>
<html><head><title>Nirbhoy API</title><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body><script id="api-reference" data-url="/api/schema/"
 data-configuration='{"theme":"default","layout":"modern"}'></script>
<script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference@1.25.0"></script>
</body></html>"""


def scalar_view(request):
    return HttpResponse(SCALAR_HTML)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("reports.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", template_name="nirbhoy/swagger_ui.html"),
        name="docs",
    ),
    path("api/scalar/", scalar_view, name="scalar"),
    path("", RedirectView.as_view(url="/api/docs/", permanent=False)),
]
