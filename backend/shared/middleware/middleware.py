from channels.auth import AuthMiddlewareStack
from urllib.parse import parse_qs
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
# Ensure this imports your custom or built-in User model
from user.models import User 

@database_sync_to_async
def get_user(scope):
    """
    Retrieves the user based on the JWT token in the query string.
    """
    try:
        # Get the token from the query string
        query_string = scope['query_string'].decode()
        token = parse_qs(query_string).get('token', [None])[0]
        
        if not token:
            return AnonymousUser()
            
        # Validate the token
        access_token = AccessToken(token)
        user_id = access_token['user_id']
        
        # Retrieve and return the User object
        return User.objects.get(id=user_id)
        
    except Exception:
        # Token invalid, expired, or user not found
        return AnonymousUser()

class TokenAuthMiddleware:
    """
    Custom middleware that populates the scope with the user object 
    retrieved via JWT token.
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # Authenticate and set the user in the scope
        scope['user'] = await get_user(scope)
        return await self.inner(scope, receive, send)

# Wrapper to stack the middlewares correctly
def JWTAuthMiddlewareStack(inner):
    return TokenAuthMiddleware(AuthMiddlewareStack(inner))