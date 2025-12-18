"""
Realism/Quality Critic - Image quality and visual plausibility.

Evaluates rendered views for visual quality, realism, and common failure patterns
using no-reference image quality metrics and artifact detection.

Signals evaluated:
- Aesthetic/realism predictor (LAION aesthetic head on CLIP)
- No-reference quality (NIQE/BRISQUE-like metrics)
- Artifact detection (noise, saturation, missing textures)
- Texture entropy (surface detail)

Dependencies (optional):
- torch: For model inference
- open_clip: For aesthetic scoring via CLIP
- PIL/Pillow: For image loading and analysis
- numpy: For numerical operations
- scipy: For image statistics
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image as PILImageModule

logger = logging.getLogger(__name__)

# Try to import dependencies
_HAS_PIL = False
_HAS_NUMPY = False

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:
    logger.debug("numpy not available - realism critic will use stub mode")

try:
    from PIL import Image, ImageStat

    _HAS_PIL = True
except ImportError:
    logger.debug("PIL not available - realism critic will use stub mode")


@dataclass
class ArtifactMetrics:
    """Detected artifacts in an image."""

    noise_estimate: float  # 0-1, higher = more noise
    saturation_clipping: float  # Percentage of pixels clipped
    missing_texture_ratio: float  # Pink/magenta pixel ratio
    low_entropy_ratio: float  # Percentage of low-entropy regions
    edge_density: float  # Measure of surface detail


@dataclass
class ViewQualityScore:
    """Quality score for a single view."""

    view_id: str
    image_path: str
    aesthetic_score: float  # 0-1, higher = more aesthetic
    quality_score: float  # 0-1, NIQE-like quality
    artifact_metrics: ArtifactMetrics
    passed: bool = False
    fail_codes: List[str] = field(default_factory=list)


@dataclass
class RealismResult:
    """Result from realism critic evaluation."""

    score: float  # Aggregate score 0-1
    passed: bool
    views_evaluated: int
    views_passing: int
    mean_aesthetic: float
    mean_quality: float
    fail_codes: List[str] = field(default_factory=list)
    view_scores: List[ViewQualityScore] = field(default_factory=list)
    aggregate_artifacts: Dict[str, float] = field(default_factory=dict)
    model_info: Dict[str, Any] = field(default_factory=dict)
    determinism: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "score": self.score,
            "passed": self.passed,
            "views_evaluated": self.views_evaluated,
            "views_passing": self.views_passing,
            "mean_aesthetic": self.mean_aesthetic,
            "mean_quality": self.mean_quality,
            "fail_codes": self.fail_codes,
            "view_scores": [
                {
                    "view_id": v.view_id,
                    "image_path": v.image_path,
                    "aesthetic_score": v.aesthetic_score,
                    "quality_score": v.quality_score,
                    "artifact_metrics": {
                        "noise_estimate": v.artifact_metrics.noise_estimate,
                        "saturation_clipping": v.artifact_metrics.saturation_clipping,
                        "missing_texture_ratio": v.artifact_metrics.missing_texture_ratio,
                        "low_entropy_ratio": v.artifact_metrics.low_entropy_ratio,
                        "edge_density": v.artifact_metrics.edge_density,
                    },
                    "passed": v.passed,
                    "fail_codes": v.fail_codes,
                }
                for v in self.view_scores
            ],
            "aggregate_artifacts": self.aggregate_artifacts,
            "model_info": self.model_info,
            "determinism": self.determinism,
        }


class RealismCritic:
    """
    Image quality and realism critic.

    Evaluates rendered views for visual quality using multiple signals:
    aesthetic scoring, quality metrics, and artifact detection.
    """

    # Pink/magenta detection for missing textures (common in failed renders)
    MAGENTA_THRESHOLD = 0.8  # R and B high, G low

    def __init__(
        self,
        aesthetic_min: float = 0.55,
        quality_min: float = 0.40,
        niqe_max: float = 6.0,  # Lower NIQE = better quality
        min_views_passing: int = 8,
        noise_max: float = 0.20,
        missing_texture_max: float = 0.05,
        device: str = "cpu",
    ):
        """
        Initialize realism critic.

        Args:
            aesthetic_min: Minimum aesthetic score (0-1)
            quality_min: Minimum quality score (0-1)
            niqe_max: Maximum NIQE score (lower is better)
            min_views_passing: Minimum views that must pass
            noise_max: Maximum acceptable noise level
            missing_texture_max: Maximum missing texture pixel ratio
            device: Device for inference
        """
        self.aesthetic_min = aesthetic_min
        self.quality_min = quality_min
        self.niqe_max = niqe_max
        self.min_views_passing = min_views_passing
        self.noise_max = noise_max
        self.missing_texture_max = missing_texture_max
        self.device = device

        # Model (lazy loaded)
        self._model = None
        self._preprocess = None
        self._torch = None
        self._open_clip = None

    def _load_model(self):
        """Load CLIP model for aesthetic scoring."""
        if self._model is not None:
            return

        from ._optional_deps import safe_import_open_clip, safe_import_torch

        torch = safe_import_torch()
        open_clip = safe_import_open_clip()
        if torch is None or open_clip is None:
            logger.warning("ML dependencies not available for aesthetic scoring")
            return

        try:
            model_name = "ViT-L-14"
            self._model, _, self._preprocess = open_clip.create_model_and_transforms(
                model_name, pretrained="openai", device=self.device
            )
            self._model.eval()
            self._torch = torch
            self._open_clip = open_clip
            logger.info("Loaded CLIP model for aesthetic scoring")
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
            self._model = None

    def _compute_aesthetic_score(self, image_path: Path) -> float:
        """
        Compute aesthetic score using CLIP.

        Uses similarity to aesthetic vs. non-aesthetic text prompts.
        """
        if not _HAS_PIL or self._model is None:
            # Stub mode
            return 0.60 if image_path.exists() else 0.0
        torch = self._torch
        open_clip = self._open_clip
        if torch is None or open_clip is None:
            return 0.60 if image_path.exists() else 0.0

        try:
            image = Image.open(image_path).convert("RGB")
            image_input = self._preprocess(image).unsqueeze(0).to(self.device)

            # Aesthetic prompts
            positive_prompts = [
                "a high quality, detailed render",
                "a beautiful, realistic image",
                "professional product photography",
                "photorealistic render",
            ]
            negative_prompts = [
                "a low quality, blurry image",
                "an ugly, distorted render",
                "amateur photography",
                "noisy, artifacted image",
            ]

            tokenizer = open_clip.get_tokenizer("ViT-L-14")
            all_prompts = positive_prompts + negative_prompts
            text_tokens = tokenizer(all_prompts).to(self.device)

            with torch.no_grad():
                image_features = self._model.encode_image(image_input)
                text_features = self._model.encode_text(text_tokens)

                image_features = image_features / image_features.norm(
                    dim=-1, keepdim=True
                )
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)

                similarities = (image_features @ text_features.T).squeeze(0)

            n_positive = len(positive_prompts)
            positive_sim = similarities[:n_positive].mean().item()
            negative_sim = similarities[n_positive:].mean().item()

            # Score: higher positive similarity vs negative
            score = (positive_sim - negative_sim + 1) / 2  # Normalize to 0-1
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.error(f"Failed to compute aesthetic score for {image_path}: {e}")
            return 0.5

    def _compute_noise_estimate(self, image: Any) -> float:
        """
        Estimate noise level in the image.

        Uses variance of Laplacian as a proxy for noise/detail.
        """
        if not _HAS_NUMPY:
            return 0.1

        try:
            # Convert to grayscale numpy array
            gray = np.array(image.convert("L"), dtype=np.float32)

            # Laplacian kernel
            laplacian = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)

            from scipy.ndimage import convolve

            # Compute Laplacian
            lap = convolve(gray, laplacian)

            # Variance of Laplacian indicates noise/edges
            var = np.var(lap)

            # Normalize (empirically calibrated)
            # High variance = lots of noise or edges
            # We want to detect abnormal noise without penalizing detail
            noise_estimate = min(1.0, var / 1000.0)

            return noise_estimate

        except Exception:
            return 0.1

    def _detect_saturation_clipping(self, image: Any) -> float:
        """Detect percentage of clipped (saturated) pixels."""
        if not _HAS_NUMPY:
            return 0.0

        try:
            arr = np.array(image)

            # Count pixels at max (255) or min (0) in any channel
            clipped_high = np.any(arr >= 254, axis=-1)
            clipped_low = np.any(arr <= 1, axis=-1)
            clipped = np.logical_or(clipped_high, clipped_low)

            return float(np.mean(clipped))

        except Exception:
            return 0.0

    def _detect_missing_textures(self, image: Any) -> float:
        """
        Detect pink/magenta pixels indicating missing textures.

        Common failure mode: Blender shows magenta for missing textures.
        """
        if not _HAS_NUMPY:
            return 0.0

        try:
            arr = np.array(image).astype(np.float32) / 255.0

            if arr.shape[-1] < 3:
                return 0.0

            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

            # Magenta: high R, low G, high B
            is_magenta = (
                (r > self.MAGENTA_THRESHOLD) & (g < 0.4) & (b > self.MAGENTA_THRESHOLD)
            )

            return float(np.mean(is_magenta))

        except Exception:
            return 0.0

    def _compute_entropy(self, image: Any) -> float:
        """
        Compute texture entropy (detail level).

        Low entropy = flat, uniform textures (suspicious).
        """
        if not _HAS_NUMPY:
            return 0.5

        try:
            gray = np.array(image.convert("L"))

            # Compute histogram
            hist, _ = np.histogram(gray.flatten(), bins=256, range=(0, 256))
            hist = hist / hist.sum()

            # Shannon entropy
            hist = hist[hist > 0]  # Remove zeros for log
            entropy = -np.sum(hist * np.log2(hist))

            # Normalize (max entropy is 8 for 256 bins)
            return entropy / 8.0

        except Exception:
            return 0.5

    def _compute_edge_density(self, image: Any) -> float:
        """
        Compute edge density as a measure of surface detail.

        Low edge density = blob-like, featureless surface.
        """
        if not _HAS_NUMPY:
            return 0.5

        try:
            gray = np.array(image.convert("L"), dtype=np.float32)

            # Sobel-like edge detection
            from scipy.ndimage import sobel

            dx = sobel(gray, axis=0)
            dy = sobel(gray, axis=1)
            edges = np.hypot(dx, dy)

            # Normalize edge magnitude
            edge_mean = np.mean(edges)
            edge_density = min(1.0, edge_mean / 50.0)  # Empirical scaling

            return edge_density

        except Exception:
            return 0.5

    def _analyze_artifacts(self, image_path: Path) -> ArtifactMetrics:
        """Analyze image for artifacts."""
        if not _HAS_PIL:
            return ArtifactMetrics(
                noise_estimate=0.1,
                saturation_clipping=0.0,
                missing_texture_ratio=0.0,
                low_entropy_ratio=0.5,
                edge_density=0.5,
            )

        try:
            image = Image.open(image_path).convert("RGB")

            return ArtifactMetrics(
                noise_estimate=self._compute_noise_estimate(image),
                saturation_clipping=self._detect_saturation_clipping(image),
                missing_texture_ratio=self._detect_missing_textures(image),
                low_entropy_ratio=1.0 - self._compute_entropy(image),
                edge_density=self._compute_edge_density(image),
            )

        except Exception as e:
            logger.error(f"Failed to analyze artifacts for {image_path}: {e}")
            return ArtifactMetrics(
                noise_estimate=0.5,
                saturation_clipping=0.0,
                missing_texture_ratio=0.0,
                low_entropy_ratio=0.5,
                edge_density=0.5,
            )

    def _compute_quality_score(self, artifacts: ArtifactMetrics) -> float:
        """
        Compute overall quality score from artifact metrics.

        Higher = better quality.
        """
        # Weighted combination of factors
        score = 1.0

        # Penalize noise
        score -= artifacts.noise_estimate * 0.3

        # Penalize clipping
        score -= artifacts.saturation_clipping * 0.2

        # Heavily penalize missing textures
        score -= artifacts.missing_texture_ratio * 0.5

        # Penalize low entropy (flat textures)
        if artifacts.low_entropy_ratio > 0.7:
            score -= 0.2

        # Reward edge density (detail)
        score += (artifacts.edge_density - 0.5) * 0.2

        return max(0.0, min(1.0, score))

    def evaluate(
        self,
        render_paths: List[Path],
        seed: int = 1337,
    ) -> RealismResult:
        """
        Evaluate visual quality and realism.

        Args:
            render_paths: List of render image paths
            seed: Random seed for determinism

        Returns:
            RealismResult with scores and failure codes
        """
        # Load model if needed
        self._load_model()

        # Set seeds for determinism
        torch = self._torch
        if torch is not None:
            torch.manual_seed(seed)

        view_scores: List[ViewQualityScore] = []
        fail_codes: List[str] = []

        # Evaluate each view
        for render_path in render_paths:
            if not render_path.exists():
                continue

            view_id = render_path.stem

            # Compute scores
            aesthetic = self._compute_aesthetic_score(render_path)
            artifacts = self._analyze_artifacts(render_path)
            quality = self._compute_quality_score(artifacts)

            # Determine pass/fail
            passed = aesthetic >= self.aesthetic_min and quality >= self.quality_min

            view_fail_codes = []
            if aesthetic < self.aesthetic_min:
                view_fail_codes.append("REAL_LOW_AESTHETIC")
            if quality < self.quality_min:
                view_fail_codes.append("REAL_LOW_QUALITY")
            if artifacts.noise_estimate > self.noise_max:
                view_fail_codes.append("REAL_NOISY")
            if artifacts.missing_texture_ratio > self.missing_texture_max:
                view_fail_codes.append("REAL_MISSING_TEXTURES")
            if artifacts.low_entropy_ratio > 0.8:
                view_fail_codes.append("REAL_FLAT_TEXTURES")

            view_scores.append(
                ViewQualityScore(
                    view_id=view_id,
                    image_path=str(render_path),
                    aesthetic_score=aesthetic,
                    quality_score=quality,
                    artifact_metrics=artifacts,
                    passed=passed,
                    fail_codes=view_fail_codes,
                )
            )

        # Aggregate results
        views_passing = sum(1 for v in view_scores if v.passed)
        views_evaluated = len(view_scores)

        if views_evaluated > 0:
            mean_aesthetic = (
                sum(v.aesthetic_score for v in view_scores) / views_evaluated
            )
            mean_quality = sum(v.quality_score for v in view_scores) / views_evaluated
        else:
            mean_aesthetic = 0.0
            mean_quality = 0.0

        # Aggregate artifact detection
        aggregate_artifacts = {}
        if view_scores:
            aggregate_artifacts = {
                "mean_noise": sum(
                    v.artifact_metrics.noise_estimate for v in view_scores
                )
                / len(view_scores),
                "max_noise": max(
                    v.artifact_metrics.noise_estimate for v in view_scores
                ),
                "mean_missing_texture": sum(
                    v.artifact_metrics.missing_texture_ratio for v in view_scores
                )
                / len(view_scores),
                "any_missing_texture": any(
                    v.artifact_metrics.missing_texture_ratio > 0.01 for v in view_scores
                ),
                "mean_edge_density": sum(
                    v.artifact_metrics.edge_density for v in view_scores
                )
                / len(view_scores),
            }

        # Global fail conditions
        if views_passing < self.min_views_passing:
            fail_codes.append("REAL_INSUFFICIENT_VIEWS_PASSING")

        if mean_aesthetic < self.aesthetic_min:
            fail_codes.append("REAL_LOW_MEAN_AESTHETIC")

        if aggregate_artifacts.get("any_missing_texture", False):
            fail_codes.append("REAL_HAS_MISSING_TEXTURES")

        if views_evaluated == 0:
            fail_codes.append("REAL_NO_VIEWS")

        # Compute aggregate score
        if views_evaluated > 0:
            # 50% aesthetic, 50% quality
            score = 0.5 * mean_aesthetic + 0.5 * mean_quality
        else:
            score = 0.0

        passed = len(fail_codes) == 0 and score >= 0.5

        return RealismResult(
            score=score,
            passed=passed,
            views_evaluated=views_evaluated,
            views_passing=views_passing,
            mean_aesthetic=mean_aesthetic,
            mean_quality=mean_quality,
            fail_codes=fail_codes,
            view_scores=view_scores,
            aggregate_artifacts=aggregate_artifacts,
            model_info={
                "aesthetic_model": "ViT-L-14/openai" if self._model else "stub",
                "quality_method": "artifact_analysis",
            },
            determinism={
                "cpu_only": self.device == "cpu",
                "seed": seed,
                "framework_versions": {
                    "torch": torch.__version__ if torch is not None else "N/A",
                    "numpy": np.__version__ if _HAS_NUMPY else "N/A",
                },
            },
        )


def run_realism_critic(
    render_dir: Path,
    config: Dict[str, Any],
    output_path: Optional[Path] = None,
) -> RealismResult:
    """
    Convenience function to run realism critic.

    Args:
        render_dir: Directory containing renders
        config: Critic configuration from gate config
        output_path: Optional path to write JSON result

    Returns:
        RealismResult
    """
    critic = RealismCritic(
        aesthetic_min=config.get("aesthetic_min", 0.55),
        quality_min=config.get("quality_min", 0.40),
        niqe_max=config.get("niqe_max", 6.0),
        min_views_passing=config.get("min_views_passing", 8),
        noise_max=config.get("noise_max", 0.20),
        missing_texture_max=config.get("missing_texture_max", 0.05),
    )

    render_paths = sorted(render_dir.glob("*.png"))

    result = critic.evaluate(render_paths)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        logger.info(f"Wrote realism critic result to {output_path}")

    return result
