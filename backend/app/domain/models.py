from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    projectId: str = Field(min_length=1)
    memberIds: list[str] = Field(default_factory=list)

