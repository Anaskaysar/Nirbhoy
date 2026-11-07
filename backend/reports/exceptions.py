"""
Every error the API returns has the same shape, so clients only need one
error handler:

{
  "error": {
    "status": 400,
    "code": "validation_error",
    "message": "Some fields are invalid.",
    "details": {"description": ["Ensure this field has at least 30 characters."]}
  }
}
"""

import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class Conflict(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"
    default_detail = "This action conflicts with the current state of the resource."


def _error(status_code, code, message, details=None):
    body = {"error": {"status": status_code, "code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)

    if response is None:
        # Unexpected crash: log it on the server, never leak internals to the client.
        logger.exception("Unhandled API error", exc_info=exc)
        return Response(
            _error(500, "server_error", "Something went wrong on our side. Please try again."),
            status=500,
        )

    if isinstance(exc, exceptions.ValidationError):
        details = response.data if isinstance(response.data, dict) else {"non_field_errors": response.data}
        response.data = _error(400, "validation_error", "Some fields are invalid.", details)
    elif isinstance(exc, exceptions.Throttled):
        wait = int(exc.wait or 0)
        response.data = _error(
            429, "rate_limited", f"Too many requests. Please try again in {wait} seconds."
        )
    else:
        detail = response.data.get("detail", str(exc)) if isinstance(response.data, dict) else str(exc)
        code = getattr(exc, "default_code", "error")
        if isinstance(getattr(exc, "detail", None), exceptions.ErrorDetail):
            code = exc.detail.code or code
        response.data = _error(response.status_code, code, str(detail))
    return response
