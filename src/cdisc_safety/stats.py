"""Small, dependency-free interval estimators for safety proportions.

Wilson score intervals behave well for the small counts typical of adverse
events, and Newcombe's hybrid score method (method 10, Newcombe 1998) gives a
confidence interval for a difference of two independent proportions without the
coverage problems of the Wald interval.
"""

from __future__ import annotations

import math

Z95 = 1.959963984540054


def wilson(x: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion x/n."""
    if n <= 0:
        return (math.nan, math.nan)
    if not 0 <= x <= n:
        raise ValueError("x must be between 0 and n")
    p = x / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe_diff(x1: int, n1: int, x2: int, n2: int, z: float = Z95) -> tuple[float, float, float]:
    """Difference p1 - p2 with Newcombe's hybrid score 95% CI; returns (diff, lower, upper)."""
    if n1 <= 0 or n2 <= 0:
        return (math.nan, math.nan, math.nan)
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = wilson(x1, n1, z)
    l2, u2 = wilson(x2, n2, z)
    d = p1 - p2
    lower = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    upper = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (d, max(-1.0, lower), min(1.0, upper))
