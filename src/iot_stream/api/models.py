"""Request models for the runtime-only operator API."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PolicyConfig(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    spike_weight: float = Field(default=0.45, ge=0.0)
    drift_weight: float = Field(default=0.55, ge=0.0)
    monitor_threshold: float = Field(default=0.40, ge=0.0, le=1.0)
    recommend_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    persistence_step: float = Field(default=0.05, ge=0.0)
    max_persistence_bonus: float = Field(default=0.15, ge=0.0)
    data_quality_min_readings: int = Field(default=2, ge=1)

    @model_validator(mode="after")
    def validate_policy(self) -> "PolicyConfig":
        if self.spike_weight + self.drift_weight <= 0:
            raise ValueError("at least one detector weight must be positive")
        if self.monitor_threshold > self.recommend_threshold:
            raise ValueError("monitor threshold cannot exceed recommendation threshold")
        return self
