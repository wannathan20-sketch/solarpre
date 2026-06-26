from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LegacyPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[dict[str, Any]] = Field(..., min_length=1)


class RegionalPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region_id: str
    DATE_TIME: str
    AMBIENT_TEMPERATURE: float = Field(..., ge=-50.0, le=60.0)
    RELATIVE_HUMIDITY: float = Field(70.0, ge=0.0, le=100.0)
    WIND_SPEED: float = Field(2.0, ge=0.0, le=80.0)
    IRRADIATION: float = Field(..., ge=0.0)
    MODULE_TEMPERATURE: Optional[float] = Field(None, ge=-50.0, le=100.0)
    storage_soc_percent: float = Field(50.0, ge=0.0, le=100.0)

    @field_validator("DATE_TIME")
    @classmethod
    def validate_date_time(cls, value):
        from pandas import to_datetime

        if to_datetime(value, errors="coerce") is None:
            raise ValueError("DATE_TIME must be parseable as a datetime")
        if to_datetime(value, errors="coerce").__class__.__name__ == "NaTType":
            raise ValueError("DATE_TIME must be parseable as a datetime")
        return value


def payload_to_dict(payload):
    if hasattr(payload, "model_dump"):
        return payload.model_dump(exclude_none=True)
    return payload
