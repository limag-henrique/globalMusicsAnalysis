"""Draft rubric and blind human-review utilities, independent of provider calls."""

import hashlib
from collections import Counter, defaultdict, deque
from math import sqrt

RUBRIC_VERSION = "lyrics-rubric-v2-draft1"
PROMPT_VERSION = "lyrics-classification-prompt-v4-draft1"
PRESENCE_THRESHOLD = 2

# Existing 26 intensities only. Auxiliary markers are not extra ranked dimensions.
TOPICS = {
    "sexuality.sexual_explicitness": (
        "Explicitude sexual",
        "Clareza sexual do texto, não juízo moral.",
    ),
    "sexuality.sexual_desire": ("Desejo sexual", "Desejo não estabelece ato sexual ocorrido."),
    "sexuality.sexual_innuendo": (
        "Insinuação sexual",
        "Duplo sentido depende do contexto textual.",
    ),
    "sexuality.explicit_sexual_act": (
        "Ato sexual explícito",
        "Requer descrição de ato, não só desejo.",
    ),
    "sexuality.explicit_sexual_anatomy": (
        "Anatomia sexual explícita",
        "Exige referência anatômica sexual.",
    ),
    "relationships.romantic_affection": ("Afeto romântico", "Amor-próprio isolado não é romance."),
    "relationships.heartbreak": (
        "Desilusão amorosa",
        "Exige perda ou sofrimento de relação afetiva.",
    ),
    "relationships.infidelity": (
        "Infidelidade",
        "Não inferir compromisso ou traição ausente no texto.",
    ),
    "relationships.transactional_sex": (
        "Sexo transacional",
        "Exige troca ligada a sexo, não qualquer presente.",
    ),
    "relationships.casual_sex": (
        "Sexo casual",
        "Desejo ou romance sem compromisso não bastam sozinhos.",
    ),
    "relationships.jealousy_possession": ("Ciúme e posse", "Distinguir afeto de controle e posse."),
    "relationships.reciprocity": (
        "Reciprocidade",
        "Considerar mutualidade textual, não presumida.",
    ),
    "gender_representation.objectification": (
        "Objetificação",
        "Agência sexual não implica redução a objeto.",
    ),
    "gender_representation.misogyny": ("Misoginia", "Exige desprezo ou desumanização por gênero."),
    "gender_representation.sexual_agency": (
        "Agência sexual",
        "Autonomia e expressão de vontade sexual.",
    ),
    "gender_representation.status_symbolization": (
        "Pessoa como símbolo de status",
        "Pessoa usada como troféu.",
    ),
    "gender_representation.commodification": (
        "Mercantilização",
        "Pessoa tratada como mercadoria ou valor de troca.",
    ),
    "material_status.money_reference": (
        "Referência a dinheiro",
        "Menção não implica materialismo.",
    ),
    "material_status.materialism": (
        "Materialismo",
        "Prioridade dada à riqueza; não qualquer menção monetária.",
    ),
    "material_status.conspicuous_consumption": (
        "Consumo ostensivo",
        "Exibição de bens para reconhecimento.",
    ),
    "material_status.wealth_as_status": (
        "Riqueza como status",
        "Riqueza usada como sinal de posição social.",
    ),
    "antisocial.drugs_alcohol.intensity": (
        "Drogas e álcool",
        "Presença e postura são julgamentos separados.",
    ),
    "antisocial.crime.intensity": (
        "Crime",
        "Descrição, ficção ou citação não são endosso automático.",
    ),
    "antisocial.violence.intensity": (
        "Violência",
        "Codificar presença; registrar crítica ou aprovação à parte.",
    ),
    "antisocial.weapons.intensity": ("Armas", "Distinguir arma literal de metáfora contextual."),
    "territorial_identity": (
        "Identidade territorial",
        "Referência territorial, não nacionalidade inferida.",
    ),
}

AUXILIARY_MARKERS = (
    "languages",
    "code_switching",
    "recording_version",
    "textual_version",
    "negation",
    "quotation",
    "fiction",
    "satire",
    "metaphor",
    "stance",
    "ambiguity",
    "insufficient_evidence",
    "integrity",
    "provenance",
)

BOUNDARY_EXAMPLES = (
    {"text": "Pago o aluguel no fim do mês.", "boundary": "Dinheiro não prova materialismo."},
    {"text": "Quero ficar perto de você.", "boundary": "Desejo não estabelece ato explícito."},
    {
        "text": "Eu escolho com quem quero estar.",
        "boundary": "Agência não estabelece objetificação.",
    },
    {
        "text": "Aprendi a gostar de mim.",
        "boundary": "Amor-próprio não estabelece afeto romântico.",
    },
    {"text": "Não quero mais essa violência.", "boundary": "Violência mencionada com rejeição."},
)


def validate_assessment(result):
    status = result.get("classification_status")
    if status not in {
        "classified",
        "ambiguous",
        "insufficient_text",
        "instrumental",
        "language_unsupported",
        "blocked",
    }:
        raise ValueError("explicit classification status is required")
    scores = result.get("scores", {})
    if status == "classified":
        if set(scores) != set(TOPICS) or any(
            type(v) is not int or not 0 <= v <= 3 for v in scores.values()
        ):
            raise ValueError("classified assessment requires all 26 integer intensities")
    elif any(v is not None for v in scores.values()):
        raise ValueError("unscorable/instrumental text must not receive automatic zero scores")
    return result


def split_verified(rows, pilot_size=80, validation_size=240, seed="revision-v2"):
    """Round-robin private strata; confirmed equivalence groups never cross splits."""
    from chart_observatory.lyrics.revision_protocol import normalize_text

    accepted, parent, seen_tags, edition_hashes = [], [], {}, {}

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for row in rows:
        if (
            row.get("identity_confirmed") is not True
            or row.get("integrity_validated") is not True
            or not row.get("equivalence_group")
            or row.get("instrumental")
            or row.get("ai_exposed") is not False
            or row.get("historical_review") is not False
            or row.get("text_language_role") != "original"
            or not row.get("text", "").strip()
        ):
            continue
        digest = normalize_text(row["text"]).normalized_hash
        edition = row["text_identity_id"]
        if edition in edition_hashes and edition_hashes[edition] != digest:
            raise ValueError("one textual edition is bound to different texts")
        edition_hashes[edition] = digest
        index = len(accepted)
        accepted.append(row)
        parent.append(index)
        # Blocking for evaluation is not a musical-identity merge. Exact model
        # inputs must never appear in both sets, even under different entity IDs.
        tags = [("equivalence", row["equivalence_group"]), ("text", digest)]
        tags.extend((name, row[name]) for name in ("recording_id", "work_id") if row.get(name))
        for tag in tags:
            if tag in seen_tags:
                parent[root(index)] = root(seen_tags[tag])
            else:
                seen_tags[tag] = index
    components = defaultdict(list)
    for index, row in enumerate(accepted):
        components[root(index)].append(row)
    groups = {}
    for members in components.values():
        row = min(members, key=lambda r: (r["text_identity_id"], str(r.get("source"))))
        groups[row["text_identity_id"]] = row
    strata = defaultdict(list)
    for group, row in groups.items():
        stratum = tuple(row.get(k, "unknown") for k in ("language", "source", "period", "risk"))
        strata[stratum].append((hashlib.sha256(f"{seed}:{group}".encode()).hexdigest(), row))
    pools = [deque(row for _, row in sorted(items)) for _, items in sorted(strata.items())]
    ranked = []
    while any(pools):
        for pool in pools:
            if pool:
                ranked.append(pool.popleft())
    pilot = ranked[:pilot_size]
    validation = ranked[pilot_size : pilot_size + validation_size]
    return {
        "pilot": pilot,
        "validation": validation,
        "pilot_deficit": pilot_size - len(pilot),
        "validation_deficit": validation_size - len(validation),
    }


def blind_forms(rows, reviewer, secret):
    """Reviewer-specific IDs and order. Source and sample-selection metadata stay private."""
    import hmac

    cards, mapping = [], []
    for row in rows:
        token = hmac.new(
            secret.encode(), f"{reviewer}:{row['text_identity_id']}".encode(), "sha256"
        ).hexdigest()[:20]
        card = {
            "review_id": token,
            "title": row.get("title"),
            "artist": row.get("artist"),
            "text": row["text"],
            "identity_verdict": None,
            "integrity_verdict": None,
            "classification_status": None,
            "scores": dict.fromkeys(TOPICS),
            "markers": dict.fromkeys(AUXILIARY_MARKERS),
            "evidence_notes": None,
        }
        cards.append(card)
        mapping.append(
            {
                "review_id": token,
                "reviewer": reviewer,
                "text_identity_id": row["text_identity_id"],
                "equivalence_group": row.get("equivalence_group"),
                "original_hash": row.get("original_hash"),
                "normalized_hash": row.get("normalized_hash"),
            }
        )
    return sorted(cards, key=lambda r: r["review_id"]), mapping


def _wilson(success, total):
    if not total:
        return None
    z, proportion = 1.959963984540054, success / total
    center = (proportion + z * z / (2 * total)) / (1 + z * z / total)
    radius = (
        z
        * sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / (1 + z * z / total)
    )
    return [max(0, center - radius), min(1, center + radius)]


def compare_scores(reference, prediction, minimum_support=30):
    """Ordinal agreement and threshold confusion against an adjudicated reference.

    Pairs with unknown scores do not become negative examples. Report their loss
    explicitly. Metrics describe the evaluated sample, not corpus prevalence.
    """
    report = {}
    for topic in TOPICS:
        pairs = [(r.get(topic), p.get(topic)) for r, p in zip(reference, prediction, strict=True)]
        scored = [
            (a, b)
            for a, b in pairs
            if type(a) is int and type(b) is int and 0 <= a <= 3 and 0 <= b <= 3
        ]
        n = len(scored)
        tp = sum(a >= 2 and b >= 2 for a, b in scored)
        fp = sum(a < 2 <= b for a, b in scored)
        fn = sum(b < 2 <= a for a, b in scored)
        tn = n - tp - fp - fn
        left, right = Counter(a for a, _ in scored), Counter(b for _, b in scored)
        observed = sum((a - b) ** 2 for a, b in scored) / n if n else None
        expected = (
            sum(left[a] * right[b] * (a - b) ** 2 for a in range(4) for b in range(4)) / n**2
            if n
            else 0
        )
        report[topic] = {
            "support": n,
            "unscored_pairs": len(pairs) - n,
            "quadratic_weighted_kappa": 1 - observed / expected if expected else None,
            "confusion_at_2": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "precision": tp / (tp + fp) if tp + fp else None,
            "sensitivity": tp / (tp + fn) if tp + fn else None,
            "precision_95_interval": _wilson(tp, tp + fp),
            "sensitivity_95_interval": _wilson(tp, tp + fn),
            "support_warning": tp + fn < minimum_support or tn + fp < minimum_support,
        }
    return report
