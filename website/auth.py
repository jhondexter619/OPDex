"""OPDex — Authentication helpers (Supabase JWT verification)."""

import os
from functools import wraps

import jwt
from flask import g, jsonify, request

SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")


def require_auth(f):
    """Decorator that verifies the Supabase JWT from the Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not token:
            return jsonify({"error": "Missing token"}), 401
        try:
            payload = jwt.decode(
                token, SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                leeway=30,
            )
            g.user_id = payload["sub"]
            g.user_email = payload.get("email", "")
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Decorator that checks the authenticated user is an admin.

    Must be used AFTER @require_auth so that g.user_email is set.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        admin_emails = [
            e.strip() for e in os.environ.get("OPDEX_ADMIN_EMAILS", "").split(",") if e.strip()
        ]
        if g.user_email not in admin_emails:
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return decorated
