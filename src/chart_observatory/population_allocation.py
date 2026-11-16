"""Population-led allocation of a single total budget across country/year cells."""

from __future__ import annotations

from decimal import Decimal, localcontext

TOTAL_POSITIONS = 150_000


def allocate(weights, budget, *, minimum=1, maximum=500):
    """Capped Hamilton allocation with deterministic tie-breaking and exact totals."""
    keys = sorted(weights)
    if budget < len(keys) * minimum or budget > len(keys) * maximum:
        raise ValueError("budget outside minimum/maximum capacity")
    if any(not Decimal(str(weights[k])).is_finite() or Decimal(str(weights[k])) <= 0 for k in keys):
        raise ValueError("positive finite weights required")
    quotas = dict.fromkeys(keys, minimum)
    remaining = budget - len(keys) * minimum
    active = set(keys)
    with localcontext() as context:
        context.prec = 40
        while remaining:
            total = sum(Decimal(str(weights[k])) for k in active)
            ideal = {k: Decimal(remaining) * Decimal(str(weights[k])) / total for k in active}
            capped = [k for k in active if ideal[k] >= maximum - quotas[k]]
            if capped:
                for key in capped:
                    remaining -= maximum - quotas[key]
                    quotas[key] = maximum
                    active.remove(key)
                continue
            for key in active:
                amount = int(ideal[key])
                quotas[key] += amount
                remaining -= amount
            for key in sorted(active, key=lambda k: (-(ideal[k] - int(ideal[k])), k))[:remaining]:
                quotas[key] += 1
            remaining = 0
    assert sum(quotas.values()) == budget
    return quotas


def weight(population, relevance, need):
    """Population dominates; each documented research adjustment is at most 10%."""
    if population <= 0 or not 0 <= relevance <= 1 or not 0 <= need <= 1:
        raise ValueError("invalid demographic/research inputs")
    return Decimal(str(population)).sqrt() * (
        Decimal(1)
        + Decimal("0.10") * Decimal(str(relevance))
        + Decimal("0.10") * Decimal(str(need))
    )
