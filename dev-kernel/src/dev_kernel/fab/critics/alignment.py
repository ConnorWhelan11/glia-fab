"""
Alignment Critic - Text-to-image semantic similarity.

Evaluates how well rendered views match the asset's prompt/description using
CLIP embeddings to compute text↔image similarity and margin over decoys.

Purpose: Ensure the asset matches the run's prompt (e.g., "red 1990s sedan with
silver rims"), not just that it's a valid car.

Dependencies (optional):
- torch: For tensor operations
- open_clip: For CLIP model and embeddings
- PIL/Pillow: For image loading
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_HAS_PIL = False

try:
    from PIL import Image

    _HAS_PIL = True
except ImportError:
    logger.debug("PIL not available - alignment critic will use stub mode")


@dataclass
class ViewAlignmentScore:
    """Alignment score for a single view."""

    view_id: str
    image_path: str
    prompt_similarity: float  # Similarity to main prompt
    decoy_max_similarity: float  # Max similarity to any decoy
    margin: float  # prompt_similarity - decoy_max_similarity
    attribute_scores: Dict[str, float] = field(default_factory=dict)  # Per-attribute
    passed: bool = False
    fail_codes: List[str] = field(default_factory=list)


@dataclass
class AttributeProbe:
    """Probe for a specific attribute in the prompt."""

    attribute: str  # e.g., "color", "style", "body_type"
    positive_text: str  # e.g., "a red car"
    negative_texts: List[str]  # e.g., ["a blue car", "a green car"]
    score: float = 0.0
    confidence: float = 0.0


@dataclass
class AlignmentResult:
    """Result from alignment critic evaluation."""

    score: float  # Aggregate score 0-1
    passed: bool
    prompt: str
    views_evaluated: int
    views_passing: int
    mean_similarity: float
    mean_margin: float
    fail_codes: List[str] = field(default_factory=list)
    view_scores: List[ViewAlignmentScore] = field(default_factory=list)
    attribute_probes: List[AttributeProbe] = field(default_factory=list)
    model_info: Dict[str, Any] = field(default_factory=dict)
    determinism: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "score": self.score,
            "passed": self.passed,
            "prompt": self.prompt,
            "views_evaluated": self.views_evaluated,
            "views_passing": self.views_passing,
            "mean_similarity": self.mean_similarity,
            "mean_margin": self.mean_margin,
            "fail_codes": self.fail_codes,
            "view_scores": [
                {
                    "view_id": v.view_id,
                    "image_path": v.image_path,
                    "prompt_similarity": v.prompt_similarity,
                    "decoy_max_similarity": v.decoy_max_similarity,
                    "margin": v.margin,
                    "attribute_scores": v.attribute_scores,
                    "passed": v.passed,
                    "fail_codes": v.fail_codes,
                }
                for v in self.view_scores
            ],
            "attribute_probes": [
                {
                    "attribute": p.attribute,
                    "positive_text": p.positive_text,
                    "negative_texts": p.negative_texts,
                    "score": p.score,
                    "confidence": p.confidence,
                }
                for p in self.attribute_probes
            ],
            "model_info": self.model_info,
            "determinism": self.determinism,
        }


class AlignmentCritic:
    """
    Text-to-image alignment critic using CLIP.

    Computes semantic similarity between rendered views and the asset's prompt,
    with margin verification against decoy prompts to ensure specificity.
    """

    # Default decoy prompts for margin computation
    DEFAULT_DECOYS = [
        "a random object",
        "a generic vehicle",
        "a truck",
        "a bus",
        "a motorcycle",
        "a boat",
        "a plane",
        "an abstract shape",
        "a blob",
    ]

    # Attribute extractors for car prompts
    COLOR_PROMPTS = {
        "red": "a red car",
        "blue": "a blue car",
        "green": "a green car",
        "black": "a black car",
        "white": "a white car",
        "silver": "a silver car",
        "yellow": "a yellow car",
        "orange": "an orange car",
        "gray": "a gray car",
    }

    STYLE_PROMPTS = {
        "modern": "a modern car",
        "vintage": "a vintage car",
        "classic": "a classic car",
        "sporty": "a sporty car",
        "luxury": "a luxury car",
        "futuristic": "a futuristic car",
    }

    BODY_TYPE_PROMPTS = {
        "sedan": "a sedan car",
        "suv": "an SUV",
        "coupe": "a coupe car",
        "hatchback": "a hatchback car",
        "convertible": "a convertible car",
        "truck": "a pickup truck",
        "van": "a van",
    }

    def __init__(
        self,
        clip_model: str = "ViT-L/14",
        similarity_min: float = 0.25,
        margin_min: float = 0.08,
        min_views_passing: int = 4,
        use_attribute_probes: bool = True,
        device: str = "cpu",
    ):
        """
        Initialize alignment critic.

        Args:
            clip_model: CLIP model to use
            similarity_min: Minimum prompt similarity score
            margin_min: Minimum margin over decoys
            min_views_passing: Minimum views that must pass
            use_attribute_probes: Whether to run attribute-specific probes
            device: Device for inference ("cpu" for determinism)
        """
        self.clip_model_name = clip_model
        self.similarity_min = similarity_min
        self.margin_min = margin_min
        self.min_views_passing = min_views_passing
        self.use_attribute_probes = use_attribute_probes
        self.device = device

        # Model (lazy loaded)
        self._model = None
        self._preprocess = None
        self._tokenizer = None
        self._torch = None
        self._open_clip = None

    def _load_model(self):
        """Load CLIP model lazily."""
        if self._model is not None:
            return

        from ._optional_deps import safe_import_open_clip, safe_import_torch

        torch = safe_import_torch()
        open_clip = safe_import_open_clip()
        if torch is None or open_clip is None:
            logger.warning("ML dependencies not available, using stub mode")
            return

        try:
            model_name = self.clip_model_name.replace("/", "-")
            self._model, _, self._preprocess = open_clip.create_model_and_transforms(
                model_name, pretrained="openai", device=self.device
            )
            self._tokenizer = open_clip.get_tokenizer(model_name)
            self._model.eval()
            self._torch = torch
            self._open_clip = open_clip
            logger.info(f"Loaded CLIP model for alignment: {self.clip_model_name}")
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
            self._model = None

    def _encode_image(self, image_path: Path) -> Optional[Any]:
        """Encode an image to CLIP embedding."""
        if not _HAS_PIL or self._model is None:
            return None
        torch = self._torch
        if torch is None:
            return None

        try:
            image = Image.open(image_path).convert("RGB")
            image_input = self._preprocess(image).unsqueeze(0).to(self.device)

            with torch.no_grad():
                image_features = self._model.encode_image(image_input)
                image_features = image_features / image_features.norm(
                    dim=-1, keepdim=True
                )

            return image_features

        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            return None

    def _encode_texts(self, texts: List[str]) -> Optional[Any]:
        """Encode texts to CLIP embeddings."""
        if self._model is None:
            return None
        torch = self._torch
        if torch is None:
            return None

        try:
            text_tokens = self._tokenizer(texts).to(self.device)

            with torch.no_grad():
                text_features = self._model.encode_text(text_tokens)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            return text_features

        except Exception as e:
            logger.error(f"Failed to encode texts: {e}")
            return None

    def _compute_similarity(
        self, image_features: Any, text_features: Any
    ) -> List[float]:
        """Compute cosine similarity between image and texts."""
        torch = self._torch
        if torch is None:
            return []
        with torch.no_grad():
            similarities = (image_features @ text_features.T).squeeze(0)
            return similarities.cpu().tolist()

    def _extract_attributes_from_prompt(self, prompt: str) -> Dict[str, str]:
        """Extract attribute hints from the prompt."""
        prompt_lower = prompt.lower()
        attributes = {}

        # Check for colors
        for color in self.COLOR_PROMPTS.keys():
            if color in prompt_lower:
                attributes["color"] = color
                break

        # Check for styles
        for style in self.STYLE_PROMPTS.keys():
            if style in prompt_lower:
                attributes["style"] = style
                break

        # Check for body types
        for body_type in self.BODY_TYPE_PROMPTS.keys():
            if body_type in prompt_lower:
                attributes["body_type"] = body_type
                break

        return attributes

    def _create_attribute_probes(self, prompt: str) -> List[AttributeProbe]:
        """Create attribute probes based on prompt."""
        probes = []
        attributes = self._extract_attributes_from_prompt(prompt)

        if "color" in attributes:
            color = attributes["color"]
            positive = self.COLOR_PROMPTS[color]
            negatives = [v for k, v in self.COLOR_PROMPTS.items() if k != color]
            probes.append(
                AttributeProbe(
                    attribute="color",
                    positive_text=positive,
                    negative_texts=negatives[:5],  # Limit negatives
                )
            )

        if "style" in attributes:
            style = attributes["style"]
            positive = self.STYLE_PROMPTS[style]
            negatives = [v for k, v in self.STYLE_PROMPTS.items() if k != style]
            probes.append(
                AttributeProbe(
                    attribute="style",
                    positive_text=positive,
                    negative_texts=negatives,
                )
            )

        if "body_type" in attributes:
            body = attributes["body_type"]
            positive = self.BODY_TYPE_PROMPTS[body]
            negatives = [v for k, v in self.BODY_TYPE_PROMPTS.items() if k != body]
            probes.append(
                AttributeProbe(
                    attribute="body_type",
                    positive_text=positive,
                    negative_texts=negatives,
                )
            )

        return probes

    def _evaluate_view_stub(
        self, image_path: Path, prompt: str, decoys: List[str]
    ) -> Tuple[float, float]:
        """Stub evaluation when ML dependencies unavailable."""
        # Return moderate scores in stub mode
        if image_path.exists():
            return 0.30, 0.05  # similarity, margin
        return 0.0, 0.0

    def _evaluate_view(
        self, image_path: Path, prompt: str, decoys: List[str]
    ) -> Tuple[float, float, Dict[str, float]]:
        """
        Evaluate a single view's alignment.

        Returns:
            Tuple of (prompt_similarity, margin, attribute_scores)
        """
        if self._model is None:
            sim, margin = self._evaluate_view_stub(image_path, prompt, decoys)
            return sim, margin, {}

        # Encode image
        image_features = self._encode_image(image_path)
        if image_features is None:
            return 0.0, 0.0, {}

        # Encode prompt and decoys
        all_texts = [prompt] + decoys
        text_features = self._encode_texts(all_texts)
        if text_features is None:
            return 0.0, 0.0, {}

        # Compute similarities
        similarities = self._compute_similarity(image_features, text_features)

        prompt_sim = similarities[0]
        decoy_sims = similarities[1:]
        margin = prompt_sim - max(decoy_sims) if decoy_sims else prompt_sim

        # Attribute scores (if probes available)
        attribute_scores = {}

        return prompt_sim, margin, attribute_scores

    def evaluate(
        self,
        prompt: str,
        render_paths: List[Path],
        decoys: Optional[List[str]] = None,
        negative_prompt: Optional[str] = None,
        seed: int = 1337,
    ) -> AlignmentResult:
        """
        Evaluate alignment between renders and prompt.

        Args:
            prompt: The asset's prompt/description
            render_paths: List of render image paths (beauty views)
            decoys: Optional custom decoy prompts
            negative_prompt: Optional negative prompt to penalize
            seed: Random seed for determinism

        Returns:
            AlignmentResult with scores and failure codes
        """
        # Load model if needed
        self._load_model()

        # Set seeds for determinism
        torch = self._torch
        if torch is not None:
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)

        # Build decoy list
        decoy_list = decoys or self.DEFAULT_DECOYS
        if negative_prompt:
            decoy_list = [negative_prompt] + decoy_list

        # Create attribute probes
        attribute_probes = []
        if self.use_attribute_probes:
            attribute_probes = self._create_attribute_probes(prompt)

        view_scores: List[ViewAlignmentScore] = []
        fail_codes: List[str] = []

        # Evaluate each view
        for render_path in render_paths:
            if not render_path.exists():
                continue

            prompt_sim, margin, attr_scores = self._evaluate_view(
                render_path, prompt, decoy_list
            )

            view_id = render_path.stem

            # Determine pass/fail for this view
            passed = prompt_sim >= self.similarity_min and margin >= self.margin_min

            view_fail_codes = []
            if prompt_sim < self.similarity_min:
                view_fail_codes.append("ALIGN_LOW_SIMILARITY")
            if margin < self.margin_min:
                view_fail_codes.append("ALIGN_LOW_MARGIN")

            view_scores.append(
                ViewAlignmentScore(
                    view_id=view_id,
                    image_path=str(render_path),
                    prompt_similarity=prompt_sim,
                    decoy_max_similarity=prompt_sim - margin,
                    margin=margin,
                    attribute_scores=attr_scores,
                    passed=passed,
                    fail_codes=view_fail_codes,
                )
            )

        # Evaluate attribute probes using first view with good similarity
        if attribute_probes and view_scores and self._model is not None:
            # Find best view for attribute evaluation
            best_view = max(view_scores, key=lambda v: v.prompt_similarity)
            best_path = Path(best_view.image_path)

            image_features = self._encode_image(best_path)
            if image_features is not None:
                for probe in attribute_probes:
                    all_texts = [probe.positive_text] + probe.negative_texts
                    text_features = self._encode_texts(all_texts)

                    if text_features is not None:
                        similarities = self._compute_similarity(
                            image_features, text_features
                        )
                        probe.score = similarities[0]
                        probe.confidence = similarities[0] - max(similarities[1:])

        # Aggregate results
        views_passing = sum(1 for v in view_scores if v.passed)
        views_evaluated = len(view_scores)

        if views_evaluated > 0:
            mean_similarity = (
                sum(v.prompt_similarity for v in view_scores) / views_evaluated
            )
            mean_margin = sum(v.margin for v in view_scores) / views_evaluated
        else:
            mean_similarity = 0.0
            mean_margin = 0.0

        # Check minimum views passing
        if views_passing < self.min_views_passing:
            fail_codes.append("ALIGN_INSUFFICIENT_VIEWS_PASSING")

        # Check mean similarity
        if mean_similarity < self.similarity_min:
            fail_codes.append("ALIGN_LOW_MEAN_SIMILARITY")

        # Check attribute alignment
        for probe in attribute_probes:
            if probe.confidence < 0.05:  # Attribute not clearly detected
                fail_codes.append(f"ALIGN_WEAK_{probe.attribute.upper()}")

        # Check for complete alignment failure
        if views_passing == 0 and views_evaluated > 0:
            fail_codes.append("ALIGN_NO_VIEWS_PASSING")

        # No views to evaluate
        if views_evaluated == 0:
            fail_codes.append("ALIGN_NO_VIEWS")

        # Compute aggregate score
        if views_evaluated > 0:
            # Weight: 60% similarity, 40% margin
            score = 0.6 * (mean_similarity / 0.5) + 0.4 * (mean_margin / 0.2)
            score = max(0.0, min(1.0, score))
        else:
            score = 0.0

        passed = len(fail_codes) == 0 and score >= 0.5

        return AlignmentResult(
            score=score,
            passed=passed,
            prompt=prompt,
            views_evaluated=views_evaluated,
            views_passing=views_passing,
            mean_similarity=mean_similarity,
            mean_margin=mean_margin,
            fail_codes=fail_codes,
            view_scores=view_scores,
            attribute_probes=attribute_probes,
            model_info={
                "name": self.clip_model_name,
                "version": "openai",
                "weights_sha256": "N/A",
            },
            determinism={
                "cpu_only": self.device == "cpu",
                "seed": seed,
                "framework_versions": {
                    "torch": torch.__version__ if torch is not None else "N/A",
                    "open_clip": "N/A",
                },
            },
        )


def run_alignment_critic(
    prompt: str,
    render_dir: Path,
    config: Dict[str, Any],
    output_path: Optional[Path] = None,
    decoys: Optional[List[str]] = None,
) -> AlignmentResult:
    """
    Convenience function to run alignment critic.

    Args:
        prompt: Asset prompt/description
        render_dir: Directory containing beauty renders
        config: Critic configuration from gate config
        output_path: Optional path to write JSON result
        decoys: Optional custom decoy prompts

    Returns:
        AlignmentResult
    """
    critic = AlignmentCritic(
        clip_model=config.get("clip_model", "ViT-L/14"),
        similarity_min=config.get("similarity_min", 0.25),
        margin_min=config.get("margin_min", 0.08),
        min_views_passing=config.get("min_views_passing", 4),
        use_attribute_probes=config.get("use_attribute_probes", True),
    )

    render_paths = sorted(render_dir.glob("*.png"))

    result = critic.evaluate(
        prompt=prompt,
        render_paths=render_paths,
        decoys=decoys,
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        logger.info(f"Wrote alignment critic result to {output_path}")

    return result
