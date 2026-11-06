"""API layer package.

Import the handler you need (`app.api.search`, `app.api.admin`). Importing
search from this package loaded the public search stack into every admin
and partner cold start, and nothing else imported that re-export.
"""
