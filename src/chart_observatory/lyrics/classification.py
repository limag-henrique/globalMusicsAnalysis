"""Immutable structured contract for automatic lyric classification."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

TAXONOMY_VERSION = "lyrics-classification-v1"
PROMPT_VERSION = "lyrics-classification-prompt-v1"

Intensity = Annotated[int, Field(ge=0, le=3)]


class ClassificationStatus(StrEnum):
    CLASSIFIED = "classified"
    AMBIGUOUS = "ambiguous"
    BLOCKED = "blocked"
    LANGUAGE_UNSUPPORTED = "language_unsupported"
    INSUFFICIENT_TEXT = "insufficient_text"
    INSTRUMENTAL = "instrumental"
    ERROR = "error"


class Stance(StrEnum):
    CONDEMNED = "condemned"
    NEUTRAL = "neutral"
    AMBIVALENT = "ambivalent"
    NORMALIZED = "normalized"
    GLORIFIED = "glorified"


class Consent(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    EXPLICIT_MUTUAL = "explicit_mutual"
    IMPLICIT_MUTUAL = "implicit_mutual"
    AMBIGUOUS = "ambiguous"
    COERCIVE = "coercive"
    NONCONSENSUAL = "nonconsensual"


class TargetGender(StrEnum):
    WOMEN = "women"
    MEN = "men"
    NONBINARY = "nonbinary"
    MULTIPLE = "multiple"
    UNSPECIFIED = "unspecified"
    NOT_APPLICABLE = "not_applicable"


class RepresentationRole(StrEnum):
    SUBJECT = "subject"
    OBJECT = "object"
    AGENT = "agent"
    RECIPIENT = "recipient"
    NARRATOR = "narrator"
    OTHER = "other"


class ThinkingLevel(StrEnum):
    MINIMAL = "MINIMAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TaxonomyModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class Sexuality(TaxonomyModel):
    sexual_explicitness: Intensity
    sexual_desire: Intensity
    sexual_innuendo: Intensity
    explicit_sexual_act: Intensity
    explicit_sexual_anatomy: Intensity


class Relationships(TaxonomyModel):
    romantic_affection: Intensity
    heartbreak: Intensity
    infidelity: Intensity
    transactional_sex: Intensity
    casual_sex: Intensity
    jealousy_possession: Intensity
    reciprocity: Intensity
    consent: Consent


class GenderRepresentation(TaxonomyModel):
    objectification: Intensity
    misogyny: Intensity
    sexual_agency: Intensity
    status_symbolization: Intensity
    commodification: Intensity
    target_gender: TargetGender
    representation_roles: tuple[RepresentationRole, ...] = ()


class MaterialStatus(TaxonomyModel):
    money_reference: Intensity
    materialism: Intensity
    conspicuous_consumption: Intensity
    wealth_as_status: Intensity


class AntisocialDimension(TaxonomyModel):
    intensity: Intensity
    stance: Stance


class Antisocial(TaxonomyModel):
    drugs_alcohol: AntisocialDimension
    crime: AntisocialDimension
    violence: AntisocialDimension
    weapons: AntisocialDimension


class LyricsClassification(TaxonomyModel):
    classification_status: ClassificationStatus
    confidence: Annotated[float, Field(ge=0, le=1)]
    sexuality: Sexuality
    relationships: Relationships
    gender_representation: GenderRepresentation
    material_status: MaterialStatus
    antisocial: Antisocial
    territorial_identity: Intensity
    romantic_summary: str | None = Field(default=None, max_length=2_000)


class GenerationPolicy(TaxonomyModel):
    """Provider-safe generation overrides for a configured model family."""

    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    thinking_level: ThinkingLevel | None = None

    @classmethod
    def for_model(
        cls, model_id: str, thinking_level: ThinkingLevel | str = ThinkingLevel.MINIMAL
    ) -> GenerationPolicy:
        if model_id.startswith("gemini-3"):
            return cls(thinking_level=ThinkingLevel(thinking_level))
        if model_id.startswith("gemini-2"):
            return cls(temperature=0.0)
        return cls()


class UsageTelemetry(TaxonomyModel):
    input_tokens: Annotated[int, Field(ge=0)] | None = None
    output_tokens: Annotated[int, Field(ge=0)] | None = None
    thought_tokens: Annotated[int, Field(ge=0)] | None = None
    total_tokens: Annotated[int, Field(ge=0)] | None = None


class CostRateCard(TaxonomyModel):
    """Configured USD rates per million tokens for a single model's billing classes."""

    input_usd_per_million_tokens: Annotated[Decimal, Field(ge=0)] | None = None
    output_usd_per_million_tokens: Annotated[Decimal, Field(ge=0)] | None = None
    thought_usd_per_million_tokens: Annotated[Decimal, Field(ge=0)] | None = None

    def calculate(self, usage: UsageTelemetry | None) -> Decimal | None:
        """Return a reliable cost only when all billed token classes are known and priced."""
        if (
            usage is None
            or usage.input_tokens is None
            or usage.output_tokens is None
            or usage.thought_tokens is None
            or self.input_usd_per_million_tokens is None
            or self.output_usd_per_million_tokens is None
            or self.thought_usd_per_million_tokens is None
        ):
            return None
        million = Decimal(1_000_000)
        return (
            Decimal(usage.input_tokens) * self.input_usd_per_million_tokens
            + Decimal(usage.output_tokens) * self.output_usd_per_million_tokens
            + Decimal(usage.thought_tokens) * self.thought_usd_per_million_tokens
        ) / million
