from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator


def _attach_utc_if_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


# SQLite returns naive datetimes; the API contract promises every timestamp
# carries a UTC offset, so responses go through this type.
UtcDatetime = Annotated[datetime, AfterValidator(_attach_utc_if_naive)]
