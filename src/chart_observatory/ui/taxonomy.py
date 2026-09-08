from dataclasses import dataclass

TAXONOMY_VERSION = "content-v1"


@dataclass(frozen=True, slots=True)
class ContentDimension:
    code: str
    label: str
    levels: tuple[str, str, str, str]


CONTENT_TAXONOMY: tuple[ContentDimension, ...] = (
    ContentDimension(
        "sexual_explicitness",
        "Explicitude sexual",
        ("ausente", "sugestivo", "explícito", "gráfico"),
    ),
    ContentDimension("objectification", "Objetificação", ("ausente", "leve", "clara", "dominante")),
    ContentDimension(
        "transactional_sex", "Sexo transacional", ("ausente", "—", "presente", "central")
    ),
    ContentDimension("materialism", "Materialismo", ("ausente", "menção", "ostentação", "central")),
    ContentDimension("drugs", "Drogas", ("ausente", "menção", "consumo positivo", "glorificação")),
    ContentDimension("crime", "Crime", ("ausente", "menção", "participação", "glorificação")),
    ContentDimension("violence", "Violência", ("ausente", "menção", "descrição", "celebração")),
    ContentDimension(
        "romantic_affection", "Afeto romântico", ("ausente", "secundária", "relevante", "central")
    ),
    ContentDimension(
        "heartbreak", "Desilusão amorosa", ("ausente", "secundário", "relevante", "central")
    ),
)


def taxonomy_codes() -> tuple[str, ...]:
    return tuple(dimension.code for dimension in CONTENT_TAXONOMY)


def level_label(code: str, score: int | None) -> str:
    try:
        dimension = next(dimension for dimension in CONTENT_TAXONOMY if dimension.code == code)
    except StopIteration as error:
        raise KeyError(code) from error
    if score is None:
        return "Sem anotação"
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 3:
        raise ValueError(f"invalid score: {score!r}")
    return dimension.levels[score]
