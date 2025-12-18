"""
Fab Vote Pack - Extended verification for uncertain verdicts.

When a gate score falls within the uncertainty band of the threshold,
this module runs additional verification to increase confidence:

1. Additional turntable frames (e.g., +12 frames at different angles)
2. Alternate HDRI lighting (versioned, fixed)
3. Ensemble model voting (multiple detector/classifier models)

The vote pack produces a final verdict via median/majority voting.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class VotePackConfig:
    """Configuration for vote pack verification."""

    enabled: bool = True
    uncertainty_band: float = 0.03  # Score within ±0.03 of threshold
    additional_turntable_frames: int = 12
    additional_angles_deg: List[float] = field(
        default_factory=lambda: [15.0, 45.0, 75.0]
    )
    alternate_hdri: Optional[str] = None
    ensemble_models: List[str] = field(
        default_factory=lambda: ["ViT-L/14", "ViT-B/32"]
    )
    voting_strategy: str = "median"  # "median", "majority", "mean"
    min_agreement_ratio: float = 0.6  # 60% of votes must agree


@dataclass
class VoteResult:
    """Result from a single vote in the pack."""

    vote_id: str
    variant: str  # "baseline", "alt_hdri", "extra_frames", "ensemble_X"
    score: float
    passed: bool
    confidence: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VotePackResult:
    """Aggregated result from vote pack verification."""

    triggered: bool  # Whether vote pack was triggered
    trigger_reason: str = ""
    original_score: float = 0.0
    original_verdict: str = ""
    final_score: float = 0.0
    final_verdict: str = ""  # "pass", "fail", "escalate"
    confidence: float = 0.0
    votes: List[VoteResult] = field(default_factory=list)
    agreement_ratio: float = 0.0
    voting_strategy: str = ""
    timing: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triggered": self.triggered,
            "trigger_reason": self.trigger_reason,
            "original_score": self.original_score,
            "original_verdict": self.original_verdict,
            "final_score": self.final_score,
            "final_verdict": self.final_verdict,
            "confidence": self.confidence,
            "votes": [
                {
                    "vote_id": v.vote_id,
                    "variant": v.variant,
                    "score": v.score,
                    "passed": v.passed,
                    "confidence": v.confidence,
                    "details": v.details,
                }
                for v in self.votes
            ],
            "agreement_ratio": self.agreement_ratio,
            "voting_strategy": self.voting_strategy,
            "timing": self.timing,
        }


class VotePackRunner:
    """
    Runs extended verification when gate score is uncertain.

    The vote pack provides additional confidence by:
    1. Rendering additional views at different angles
    2. Using alternate lighting (HDRI variants)
    3. Running ensemble models for voting
    """

    def __init__(
        self,
        config: VotePackConfig,
        gate_config_id: str,
    ):
        self.config = config
        self.gate_config_id = gate_config_id

    def should_trigger(
        self,
        score: float,
        threshold: float,
        has_hard_fails: bool = False,
    ) -> Tuple[bool, str]:
        """
        Determine if vote pack should be triggered.

        Args:
            score: Current gate score
            threshold: Pass threshold
            has_hard_fails: Whether there are hard failures

        Returns:
            Tuple of (should_trigger, reason)
        """
        if not self.config.enabled:
            return False, "vote_pack_disabled"

        # Don't trigger on hard fails
        if has_hard_fails:
            return False, "hard_fail_present"

        # Check uncertainty band
        distance = abs(score - threshold)
        if distance <= self.config.uncertainty_band:
            return True, f"score_in_uncertainty_band ({score:.3f} vs {threshold:.3f})"

        return False, "score_outside_band"

    def run_vote_pack(
        self,
        asset_path: Path,
        render_dir: Path,
        current_scores: Dict[str, float],
        current_verdict: str,
        threshold: float,
    ) -> VotePackResult:
        """
        Run vote pack verification.

        Args:
            asset_path: Path to asset file
            render_dir: Directory with existing renders
            current_scores: Scores from initial evaluation
            current_verdict: Current verdict
            threshold: Pass threshold

        Returns:
            VotePackResult with final verdict
        """
        start_time = datetime.now(timezone.utc)

        original_score = current_scores.get("overall", 0.0)
        should_run, reason = self.should_trigger(
            original_score, threshold, has_hard_fails=False
        )

        if not should_run:
            return VotePackResult(
                triggered=False,
                trigger_reason=reason,
                original_score=original_score,
                original_verdict=current_verdict,
                final_score=original_score,
                final_verdict=current_verdict,
                confidence=1.0,
            )

        logger.info(f"Vote pack triggered: {reason}")

        votes: List[VoteResult] = []

        # Vote 1: Baseline (existing evaluation)
        votes.append(
            VoteResult(
                vote_id="baseline",
                variant="baseline",
                score=original_score,
                passed=current_verdict == "pass",
                confidence=0.8,
                details={"scores": current_scores},
            )
        )

        # Vote 2: Additional turntable frames
        extra_frames_result = self._run_extra_frames_vote(
            asset_path, render_dir, current_scores
        )
        if extra_frames_result:
            votes.append(extra_frames_result)

        # Vote 3: Alternate lighting (simulated)
        alt_lighting_result = self._run_alt_lighting_vote(
            asset_path, render_dir, current_scores
        )
        if alt_lighting_result:
            votes.append(alt_lighting_result)

        # Vote 4+: Ensemble models
        for model_name in self.config.ensemble_models[1:]:  # Skip first (already used)
            ensemble_result = self._run_ensemble_vote(
                model_name, render_dir, current_scores
            )
            if ensemble_result:
                votes.append(ensemble_result)

        # Aggregate votes
        final_score, final_verdict, confidence, agreement = self._aggregate_votes(
            votes, threshold
        )

        end_time = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return VotePackResult(
            triggered=True,
            trigger_reason=reason,
            original_score=original_score,
            original_verdict=current_verdict,
            final_score=final_score,
            final_verdict=final_verdict,
            confidence=confidence,
            votes=votes,
            agreement_ratio=agreement,
            voting_strategy=self.config.voting_strategy,
            timing={
                "started_at": start_time.isoformat(),
                "completed_at": end_time.isoformat(),
                "duration_ms": duration_ms,
            },
        )

    def _run_extra_frames_vote(
        self,
        asset_path: Path,
        render_dir: Path,
        current_scores: Dict[str, float],
    ) -> Optional[VoteResult]:
        """
        Simulate additional turntable frames vote.

        In production, this would render additional frames and run critics.
        Here we simulate with slight score variation.
        """
        try:
            # Simulate: slight variation from baseline
            import random

            random.seed(42)  # Deterministic
            base_score = current_scores.get("overall", 0.5)

            # Add small random variation (±0.02)
            variation = random.uniform(-0.02, 0.02)
            score = max(0.0, min(1.0, base_score + variation))

            return VoteResult(
                vote_id="extra_frames",
                variant="extra_turntable_frames",
                score=score,
                passed=score >= 0.75,
                confidence=0.85,
                details={
                    "additional_frames": self.config.additional_turntable_frames,
                    "simulated": True,
                },
            )
        except Exception as e:
            logger.warning(f"Extra frames vote failed: {e}")
            return None

    def _run_alt_lighting_vote(
        self,
        asset_path: Path,
        render_dir: Path,
        current_scores: Dict[str, float],
    ) -> Optional[VoteResult]:
        """
        Simulate alternate lighting vote.

        In production, this would re-render with different HDRI and evaluate.
        """
        try:
            import random

            random.seed(43)  # Different seed
            base_score = current_scores.get("overall", 0.5)

            # Lighting changes can affect realism score more
            variation = random.uniform(-0.03, 0.02)
            score = max(0.0, min(1.0, base_score + variation))

            return VoteResult(
                vote_id="alt_lighting",
                variant="alternate_hdri",
                score=score,
                passed=score >= 0.75,
                confidence=0.75,
                details={
                    "hdri": self.config.alternate_hdri or "studio_small_08",
                    "simulated": True,
                },
            )
        except Exception as e:
            logger.warning(f"Alt lighting vote failed: {e}")
            return None

    def _run_ensemble_vote(
        self,
        model_name: str,
        render_dir: Path,
        current_scores: Dict[str, float],
    ) -> Optional[VoteResult]:
        """
        Simulate ensemble model vote.

        In production, this would run a different CLIP model variant.
        """
        try:
            import random

            # Use model name as seed for reproducibility
            random.seed(hash(model_name) % 2**32)
            base_score = current_scores.get("category", 0.5)

            # Different models have different biases
            variation = random.uniform(-0.05, 0.05)
            score = max(0.0, min(1.0, base_score + variation))

            return VoteResult(
                vote_id=f"ensemble_{model_name.replace('/', '_')}",
                variant=f"ensemble_model",
                score=score,
                passed=score >= 0.75,
                confidence=0.70,
                details={
                    "model": model_name,
                    "simulated": True,
                },
            )
        except Exception as e:
            logger.warning(f"Ensemble vote failed: {e}")
            return None

    def _aggregate_votes(
        self,
        votes: List[VoteResult],
        threshold: float,
    ) -> Tuple[float, str, float, float]:
        """
        Aggregate votes to determine final verdict.

        Returns:
            Tuple of (final_score, verdict, confidence, agreement_ratio)
        """
        if not votes:
            return 0.0, "fail", 0.0, 0.0

        scores = [v.score for v in votes]
        passed_votes = sum(1 for v in votes if v.passed)
        total_votes = len(votes)

        # Calculate agreement
        agreement_ratio = passed_votes / total_votes

        # Calculate final score based on strategy
        if self.config.voting_strategy == "median":
            sorted_scores = sorted(scores)
            mid = len(sorted_scores) // 2
            if len(sorted_scores) % 2 == 0:
                final_score = (sorted_scores[mid - 1] + sorted_scores[mid]) / 2
            else:
                final_score = sorted_scores[mid]
        elif self.config.voting_strategy == "mean":
            final_score = sum(scores) / len(scores)
        else:  # majority
            final_score = sum(scores) / len(scores)

        # Determine verdict
        if agreement_ratio >= self.config.min_agreement_ratio:
            if passed_votes > total_votes / 2:
                verdict = "pass"
            else:
                verdict = "fail"
        else:
            # Disagreement → escalate
            verdict = "escalate"

        # Calculate confidence based on agreement
        confidence = agreement_ratio

        return final_score, verdict, confidence, agreement_ratio


def create_vote_pack_config(gate_config: Any) -> VotePackConfig:
    """Create vote pack config from gate config."""
    iteration = getattr(gate_config, "iteration", None)

    if iteration is None:
        return VotePackConfig()

    return VotePackConfig(
        enabled=getattr(iteration, "vote_pack_on_uncertainty", True),
        uncertainty_band=getattr(iteration, "uncertainty_band", 0.03),
    )


def run_vote_pack_if_needed(
    asset_path: Path,
    render_dir: Path,
    scores: Dict[str, float],
    verdict: str,
    threshold: float,
    gate_config: Any,
) -> Optional[VotePackResult]:
    """
    Run vote pack if score is in uncertainty band.

    Args:
        asset_path: Path to asset
        render_dir: Render output directory
        scores: Current critic scores
        verdict: Current verdict
        threshold: Pass threshold
        gate_config: Gate configuration

    Returns:
        VotePackResult if triggered, None otherwise
    """
    config = create_vote_pack_config(gate_config)
    runner = VotePackRunner(config, gate_config.gate_config_id)

    overall = scores.get("overall", 0.0)
    should_run, reason = runner.should_trigger(overall, threshold)

    if not should_run:
        return None

    return runner.run_vote_pack(
        asset_path=asset_path,
        render_dir=render_dir,
        current_scores=scores,
        current_verdict=verdict,
        threshold=threshold,
    )

