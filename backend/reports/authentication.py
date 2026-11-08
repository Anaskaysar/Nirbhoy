from rest_framework.authentication import TokenAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed


class FlexibleTokenAuthentication(TokenAuthentication):
    """
    Standard DRF token authentication, but the "Token " prefix is optional.

    Accepts both:
        Authorization: Token 9944b09199c62bcf...
        Authorization: 9944b09199c62bcf...

    People testing in Swagger often paste only the token into "Authorize",
    which would otherwise fail with a confusing 401.
    """

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if len(parts) == 1 and parts[0].lower() != self.keyword.lower().encode():
            try:
                key = parts[0].decode()
            except UnicodeError:
                raise AuthenticationFailed("Invalid token header.")
            return self.authenticate_credentials(key)
        return super().authenticate(request)
