"""Scoring and Elo/BT ranking updates."""
from __future__ import annotations

from image_rater.db_model import Comparison, ImageRanking, Rating, Task

BASE_POINTS: float = 1.0
ELO_K: float = 32.0


def _reliability_score(consistency: float | None, inter_rater: float | None) -> float:
    """Combined reliability score in [0, 1].  Defaults to 1.0 for new users."""
    values = [v for v in (consistency, inter_rater) if v is not None]
    return sum(values) / len(values) if values else 1.0


def compute_points(task: Task, consistency: float | None, inter_rater: float | None) -> float:
    rel = _reliability_score(consistency, inter_rater)
    return BASE_POINTS * task.bonus_multiplier * (0.5 + 0.5 * rel)


def update_elo(winner_ranking: ImageRanking, loser_ranking: ImageRanking) -> None:
    """Update Elo scores in-place after a comparison.  K=32."""
    ra, rb = winner_ranking.score, loser_ranking.score
    ea = 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))
    winner_ranking.score = ra + ELO_K * (1.0 - ea)
    loser_ranking.score = rb + ELO_K * (0.0 - (1.0 - ea))
    winner_ranking.comparisons += 1
    winner_ranking.wins += 1
    loser_ranking.comparisons += 1
