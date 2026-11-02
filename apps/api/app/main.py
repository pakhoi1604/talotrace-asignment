from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import candidate, health, hr_actions, hr_review, hr_session


def _first_error_detail(exc: RequestValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "body: invalid request"
    err = errors[0]
    loc = err.get("loc") or ("body",)
    field = str(loc[-1])
    msg = err.get("msg", "invalid request")
    # Unwrap pydantic's "Value error, <msg>" so the detail stays readable.
    if msg.startswith("Value error, "):
        msg = msg.removeprefix("Value error, ")
    return f"{field}: {msg}"


def create_app() -> FastAPI:
    app = FastAPI(title="TaloTrace API")

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Contract: every error body is {"detail": <string>}, 422 included.
        return JSONResponse(status_code=422, content={"detail": _first_error_detail(exc)})

    app.include_router(health.router, prefix="/api")
    app.include_router(candidate.router, prefix="/api")
    app.include_router(hr_session.router, prefix="/api")
    app.include_router(hr_review.router, prefix="/api")
    app.include_router(hr_actions.router, prefix="/api")
    return app


app = create_app()
