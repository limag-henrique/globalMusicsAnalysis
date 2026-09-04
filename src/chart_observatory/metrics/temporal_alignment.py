from dataclasses import dataclass
from datetime import date

from chart_observatory.domain.enums import TemporalAlignmentPolicy
from chart_observatory.domain.errors import TemporalAlignmentRequired


@dataclass(frozen=True)
class NativePeriod:
    start: date
    end: date
    frequency: str


def align_periods(
    left: list[NativePeriod], right: list[NativePeriod], policy: TemporalAlignmentPolicy | None
) -> tuple[tuple[NativePeriod, NativePeriod], ...]:
    frequencies = {period.frequency for period in left + right}
    if len(frequencies) > 1 and policy is None:
        raise TemporalAlignmentRequired("mixed frequencies require an explicit temporal policy")
    selected = policy or TemporalAlignmentPolicy.SAME_NATIVE_FREQUENCY
    if selected is TemporalAlignmentPolicy.SAME_NATIVE_FREQUENCY:
        if len(frequencies) > 1:
            raise TemporalAlignmentRequired("SAME_NATIVE_FREQUENCY cannot align unlike frequencies")
        return tuple((a, b) for a in left for b in right if a.start == b.start and a.end == b.end)
    return tuple((a, b) for a in left for b in right if a.start <= b.end and b.start <= a.end)
