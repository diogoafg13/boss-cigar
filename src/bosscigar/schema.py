"""Validação do seed curado (fonte de verdade editável por humanos)."""
from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

# Campos de um charuto cuja verificação pode ser declarada.
VERIFIABLE = {"country", "region", "strength", "vitola", "wrapper", "flavors"}


class Source(BaseModel):
    title: str
    url: HttpUrl


class Region(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str
    country: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    note: str


class Cigar(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    brand: str
    line: str
    country: str
    region: str
    strength: int = Field(ge=1, le=5)
    vitola: str
    wrapper: str
    flavors: list[str] = Field(min_length=1)
    notes: str = ""
    verified_fields: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)

    @field_validator("verified_fields")
    @classmethod
    def _known_fields(cls, v: list[str]) -> list[str]:
        unknown = set(v) - VERIFIABLE
        if unknown:
            raise ValueError(f"campos desconhecidos em verified_fields: {sorted(unknown)}")
        return v

    @model_validator(mode="after")
    def _verified_needs_source(self) -> "Cigar":
        if self.verified_fields and not self.sources:
            raise ValueError(f"{self.id}: verified_fields exige pelo menos uma fonte em 'sources'")
        return self
