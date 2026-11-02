"""Enumerate every APIRoute in the app with its full mounted path.

Starlette >=1.10 wraps included routers in an ``_IncludedRouter`` object
exposing ``original_router`` and ``include_context.prefix``; this walks
into them recursively so tests see the real route table.
"""

from fastapi.routing import APIRoute


def api_routes(app) -> list[tuple[str, APIRoute]]:
    """Return (full_path, route) pairs for every APIRoute in the app."""
    found: list[tuple[str, APIRoute]] = []

    def walk(routes, prefix: str) -> None:
        for route in routes:
            if isinstance(route, APIRoute):
                found.append((prefix + route.path, route))
            elif hasattr(route, "original_router"):
                sub_prefix = route.include_context.prefix or ""
                walk(route.original_router.routes, prefix + sub_prefix)

    walk(app.routes, "")
    return found
