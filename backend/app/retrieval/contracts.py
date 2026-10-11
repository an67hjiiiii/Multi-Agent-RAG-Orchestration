from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request: str = Field(min_length=1)
    task_id: Identifier | None = None
    top_k: int = Field(default=5, ge=1)
    context_token_limit: int = Field(default=4096, ge=1)


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: Identifier
    chunk_id: Identifier
    locator: Identifier | None = None


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    evidence_id: Identifier
    text: str = Field(min_length=1)
    provenance: Provenance
    score: float | None = Field(default=None, allow_inf_nan=False)


class EvidencePackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: RetrievalQuery
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_evidence_ids(self) -> "EvidencePackage":
        ids = [item.evidence_id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("Evidence IDs must be unique within a package.")
        return self


class ContextAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: Identifier
    evidence_ids: list[Identifier] = Field(default_factory=list)
    token_count: int = Field(ge=0)
    token_budget: int = Field(ge=1)

    @model_validator(mode="after")
    def valid_allocation(self) -> "ContextAllocation":
        if self.token_count > self.token_budget:
            raise ValueError("Allocated context exceeds its token budget.")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Allocated evidence IDs must be unique.")
        return self
