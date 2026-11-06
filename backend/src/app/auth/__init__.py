"""Authentication helpers.

Submodules are imported directly. Importing the JWT validator here pulled
PyJWT and cryptography into the partner API-key authorizer, which never
verifies a JWT. That authorizer ships the search dependency profile and
does not include PyJWT.
"""
