"""Collection of data-quality findings raised during a run."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

SEVERITIES = ("ERROR", "WARNING", "NOTE")


@dataclass
class Finding:
    """One data-quality rule result."""

    rule_id: str
    domain: str
    severity: str
    message: str
    count: int
    examples: str = ""


@dataclass
class Findings:
    """An ordered list of findings with helpers for reporting."""

    items: list[Finding] = field(default_factory=list)

    def add(self, rule_id: str, domain: str, severity: str, message: str, ids=(), count: int | None = None) -> None:
        """Record a finding; ``ids`` are subject or record identifiers used as examples."""
        if severity not in SEVERITIES:
            raise ValueError(f"unknown severity {severity!r}")
        ids = [str(i) for i in ids]
        n = count if count is not None else len(ids)
        if n == 0:
            return
        self.items.append(Finding(rule_id, domain, severity, message, n, ", ".join(sorted(set(ids))[:5])))

    def to_frame(self) -> pd.DataFrame:
        """Return findings as a DataFrame sorted by severity then rule."""
        cols = ["rule_id", "domain", "severity", "message", "count", "examples"]
        if not self.items:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame([asdict(f) for f in self.items])[cols]
        order = {s: i for i, s in enumerate(SEVERITIES)}
        return df.sort_values(["severity", "rule_id"], key=lambda s: s.map(order) if s.name == "severity" else s)

    def count(self, severity: str) -> int:
        """Number of findings (not records) at a severity."""
        return sum(1 for f in self.items if f.severity == severity)
