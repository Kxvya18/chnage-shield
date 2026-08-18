from rest_framework import authentication, exceptions
from .models import Runner


class RunnerTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode().split()
        if not header or header[0] != self.keyword or len(header) != 2:
            return None
        try:
            runner = Runner.objects.get(token_hash=Runner.hash_token(header[1]), enabled=True)
        except Runner.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed("Invalid or revoked runner token") from exc
        return runner, header[1]

