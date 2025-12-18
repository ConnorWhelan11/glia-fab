# Fab Critics Stack

## Overview

Critics are deterministic analysis modules that evaluate canonical renders and mesh data against category-specific criteria. All critics must be:

- **Deterministic**: CPU inference, fixed seeds, deterministic ops
- **Versioned**: Model name + weight hash recorded
- **Auditable**: Inputs/outputs recorded, per-view results preserved

## Critic Output Contract

Every critic emits a standardized result:

```python
@dataclass
class CriticResult:
    critic_name: str
    score: float  # [0.0, 1.0] normalized
    fail_codes: List[str]  # Stable identifiers
    evidence: Dict[str, Any]  # Per-view details, metrics
    passed: bool  # score >= threshold
```

## Critics Overview

| Critic        | Purpose                          | Inputs                  | Key Metrics                           |
| ------------- | -------------------------------- | ----------------------- | ------------------------------------- |
| **Category**  | Reject blobs, wrong object types | Beauty + Clay renders   | Detection confidence, CLIP margins    |
| **Alignment** | Match prompt semantics           | Beauty renders + prompt | CLIP similarity, attribute probes     |
| **Realism**   | Penalize synthetic artifacts     | Beauty renders          | Aesthetic score, NIQE, artifact flags |
| **Geometry**  | Validate mesh sanity             | GLB mesh file           | Bounds, tri count, symmetry, wheels   |

---

## Category Correctness Critic

### Purpose

Reject blobs and wrong categories even if renders are "pretty."

### Inputs

- Beauty renders (fixed + turntable views)
- Clay renders (same views)
- Mask pass (optional, for sanity check)

### Method

```python
class CategoryCritic:
    def __init__(self, config: CategoryConfig):
        self.detector = load_yolo_model("yolov8n")  # COCO car class
        self.clip = load_clip_model("ViT-L/14")
        self.config = config

    def evaluate(self, views: List[ViewData]) -> CriticResult:
        results = []
        for view in views:
            # Object detection
            detections = self.detector.detect(view.beauty_image)
            car_det = max(
                (d for d in detections if d.class_name == "car"),
                key=lambda d: d.confidence,
                default=None
            )

            # CLIP classification
            clip_scores = self.clip.classify(
                view.beauty_image,
                prompts=["a photo of a car", "a blob", "a chair", "a truck"]
            )
            car_margin = clip_scores["car"] - max(
                clip_scores[k] for k in clip_scores if k != "car"
            )

            # Clay agreement (detect on clay too)
            clay_detections = self.detector.detect(view.clay_image)
            clay_car = any(d.class_name == "car" and d.confidence > 0.3
                          for d in clay_detections)

            results.append({
                "view_id": view.id,
                "car_detect_conf": car_det.confidence if car_det else 0,
                "bbox_area_ratio": self._bbox_ratio(car_det, view.beauty_image),
                "clip_car_margin": car_margin,
                "clay_agreement": clay_car,
                "pass_view": self._passes(car_det, car_margin, clay_car)
            })

        return self._aggregate(results)
```

### Failure Codes

| Code                     | Condition                          |
| ------------------------ | ---------------------------------- |
| `CAT_NO_CAR_DETECTED`    | No car detection in >50% of views  |
| `CAT_LOW_CONFIDENCE`     | Average car confidence < 0.6       |
| `CAT_CLIP_MARGIN_LOW`    | CLIP car margin < 0.08             |
| `CAT_CLAY_DISAGREEMENT`  | Clay views don't agree with beauty |
| `CAT_UNSTABLE_DETECTION` | Turntable detections inconsistent  |

### Why It Catches Blobs

- Blobs fail detector confidence across multiple views
- Unstable detections across turntable frames
- Clay views remove texture cheating; blob geometry exposed
- CLIP margins low for ambiguous objects

### Model Selection Criteria

| Requirement     | Options                            |
| --------------- | ---------------------------------- |
| Object Detector | YOLOv8, YOLOv5, DETR, Faster R-CNN |
| CLIP Model      | OpenCLIP ViT-L/14, ViT-B/32        |
| License         | Permissive (Apache 2.0, MIT)       |
| Inference       | CPU-feasible, deterministic        |

---

## Prompt Alignment Critic

### Purpose

Ensure asset matches the generation prompt (e.g., "red 1990s sedan with silver rims").

### Inputs

- Beauty fixed views (subset, e.g., 6 views)
- Prompt string
- Optional: negative prompt, decoy prompts

### Method

```python
class AlignmentCritic:
    def __init__(self, config: AlignmentConfig):
        self.clip = load_clip_model(config.clip_model)
        self.config = config

    def evaluate(
        self,
        views: List[ViewData],
        prompt: str,
        decoys: List[str] = None
    ) -> CriticResult:
        decoys = decoys or self._default_decoys(prompt)

        # Embed prompt and decoys
        text_embeddings = self.clip.encode_text([prompt] + decoys)
        prompt_emb = text_embeddings[0]
        decoy_embs = text_embeddings[1:]

        view_scores = []
        for view in views:
            img_emb = self.clip.encode_image(view.beauty_image)

            # Cosine similarity
            prompt_sim = cosine_similarity(img_emb, prompt_emb)
            decoy_sims = [cosine_similarity(img_emb, d) for d in decoy_embs]
            margin = prompt_sim - max(decoy_sims)

            view_scores.append({
                "view_id": view.id,
                "prompt_similarity": prompt_sim,
                "margin": margin,
                "pass_view": margin >= self.config.margin_min
            })

        return self._aggregate(view_scores)

    def _default_decoys(self, prompt: str) -> List[str]:
        """Generate contrastive decoys"""
        return [
            "a different car",
            "a truck",
            "a motorcycle",
            "a blob",
            "an empty scene"
        ]
```

### Attribute Probes

For detailed attribute verification:

```python
def check_attributes(self, views: List[ViewData], attributes: Dict):
    """Check specific attributes like color, style"""
    probes = []

    if "color" in attributes:
        color = attributes["color"]
        probes.append({
            "positive": f"a {color} car",
            "negative": f"a car that is not {color}"
        })

    # Evaluate probes across views
    return self._probe_attributes(views, probes)
```

### Failure Codes

| Code                       | Condition                             |
| -------------------------- | ------------------------------------- |
| `ALIGN_LOW_SIMILARITY`     | Average prompt similarity < threshold |
| `ALIGN_MARGIN_LOW`         | Margin vs decoys < 0.08               |
| `ALIGN_ATTRIBUTE_MISMATCH` | Specific attribute check failed       |

---

## Realism / Image Quality Critic

### Purpose

Penalize obviously synthetic outputs and common failure patterns (noise, flat shading, missing textures).

### Inputs

- Beauty renders (fixed + limited turntable)
- Optional: material metadata from export

### Method

```python
class RealismCritic:
    def __init__(self, config: RealismConfig):
        self.aesthetic_model = load_aesthetic_predictor()
        self.config = config

    def evaluate(self, views: List[ViewData]) -> CriticResult:
        metrics = []

        for view in views:
            img = view.beauty_image

            # Aesthetic/realism predictor
            aesthetic_score = self.aesthetic_model.predict(img)

            # No-reference quality (BRISQUE/NIQE)
            niqe_score = compute_niqe(img)

            # Artifact checks
            artifacts = self._check_artifacts(img)

            metrics.append({
                "view_id": view.id,
                "aesthetic_score": aesthetic_score,
                "niqe_score": niqe_score,
                "artifacts": artifacts,
                "pass_view": self._passes(aesthetic_score, niqe_score, artifacts)
            })

        return self._aggregate(metrics)

    def _check_artifacts(self, img: np.ndarray) -> Dict:
        """Check for common render artifacts"""
        return {
            "noise_estimate": self._estimate_noise(img),
            "saturation_clipping": self._check_saturation(img),
            "magenta_pixels": self._detect_missing_texture(img),
            "low_entropy_ratio": self._check_entropy(img)
        }

    def _detect_missing_texture(self, img: np.ndarray) -> float:
        """Detect magenta/pink pixels indicating missing textures"""
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        magenta_mask = (hsv[:,:,0] > 140) & (hsv[:,:,0] < 180)
        return magenta_mask.sum() / img.size
```

### Signals

| Signal              | Method                       | Threshold   |
| ------------------- | ---------------------------- | ----------- |
| Aesthetic Score     | LAION aesthetic head on CLIP | > 0.55      |
| NIQE Score          | No-reference quality (piq)   | < 6.0       |
| Noise Estimate      | Variance in flat regions     | < threshold |
| Saturation Clipping | % over/under exposed         | < 5%        |
| Missing Texture     | Magenta pixel ratio          | < 0.1%      |
| Texture Entropy     | Per-region entropy           | > threshold |

### Failure Codes

| Code                   | Condition                        |
| ---------------------- | -------------------------------- |
| `REAL_LOW_AESTHETIC`   | Aesthetic score below threshold  |
| `REAL_HIGH_NIQE`       | NIQE score indicates low quality |
| `REAL_NOISY_RENDER`    | High noise in render             |
| `REAL_MISSING_TEXTURE` | Magenta pixels detected          |
| `REAL_LOW_ENTROPY`     | Overly uniform materials         |
| `REAL_CLIPPING`        | Saturation/exposure clipping     |

---

## Geometry Sanity Critic

### Purpose

Reject "car-looking textures on nonsense geometry" and catch 3D-unusable meshes.

### Inputs

- Mesh file (`.glb` preferred)
- Mask/depth/normal passes (optional cross-check)

### Method

```python
class GeometryCritic:
    def __init__(self, config: GeometryConfig):
        self.config = config

    def evaluate(self, mesh_path: Path) -> CriticResult:
        mesh = trimesh.load(mesh_path)

        metrics = {}
        fail_codes = []

        # Scale plausibility
        bounds = mesh.bounding_box.extents
        metrics["bounds_m"] = {
            "length": bounds[1],  # Y in Blender
            "width": bounds[0],   # X
            "height": bounds[2]   # Z
        }
        if not self._check_bounds(bounds):
            fail_codes.append("GEO_SCALE_IMPLAUSIBLE")

        # Triangle/vertex counts
        metrics["triangle_count"] = len(mesh.faces)
        metrics["vertex_count"] = len(mesh.vertices)
        if metrics["triangle_count"] < self.config.min_triangles:
            fail_codes.append("GEO_TRI_COUNT_LOW")
        if metrics["triangle_count"] > self.config.max_triangles:
            fail_codes.append("GEO_TRI_COUNT_HIGH")

        # Connected components
        components = mesh.split(only_watertight=False)
        metrics["component_count"] = len(components)

        # Symmetry check
        metrics["symmetry_score"] = self._compute_symmetry(mesh)
        if metrics["symmetry_score"] < self.config.symmetry_min:
            fail_codes.append("GEO_ASYMMETRIC")

        # Ground contact analysis
        metrics["ground_clusters"] = self._analyze_ground_contact(mesh)

        # Wheel detection
        metrics["wheel_candidates"] = self._detect_wheels(mesh)
        if len(metrics["wheel_candidates"]) < self.config.wheel_clusters_min:
            fail_codes.append("GEO_WHEEL_COUNT_LOW")

        # Manifold checks
        metrics["manifold_stats"] = self._check_manifold(mesh)

        # Material sanity
        metrics["material_stats"] = self._check_materials(mesh)

        score = self._compute_score(metrics, fail_codes)
        return CriticResult(
            critic_name="geometry",
            score=score,
            fail_codes=fail_codes,
            evidence=metrics,
            passed=len([c for c in fail_codes if c.startswith("GEO_")]) == 0
        )

    def _compute_symmetry(self, mesh: trimesh.Trimesh) -> float:
        """Compute bilateral symmetry across X plane"""
        # Mirror vertices across X=0
        mirrored = mesh.vertices.copy()
        mirrored[:, 0] *= -1

        # Find nearest neighbor distances
        tree = KDTree(mesh.vertices)
        distances, _ = tree.query(mirrored)

        # Normalize by bounding box diagonal
        diagonal = np.linalg.norm(mesh.bounding_box.extents)
        symmetry = 1.0 - (np.mean(distances) / diagonal)
        return max(0, symmetry)

    def _detect_wheels(self, mesh: trimesh.Trimesh) -> List[Dict]:
        """Detect wheel candidates by shape analysis"""
        candidates = []
        components = mesh.split(only_watertight=False)

        for comp in components:
            # Check if component is wheel-like (cylindrical, near ground)
            bounds = comp.bounding_box.extents
            aspect = max(bounds) / min(bounds) if min(bounds) > 0 else 0

            center = comp.centroid
            min_z = comp.vertices[:, 2].min()

            if aspect < 3 and min_z < 0.1:  # Near ground, not too elongated
                candidates.append({
                    "center": center.tolist(),
                    "radius_estimate": max(bounds[:2]) / 2,
                    "ground_contact": min_z
                })

        return candidates
```

### Geometry Metrics

| Metric              | Car Defaults | Purpose                       |
| ------------------- | ------------ | ----------------------------- |
| Length              | 3.0–6.0m     | Realistic car dimensions      |
| Width               | 1.4–2.5m     | Realistic car dimensions      |
| Height              | 1.0–2.5m     | Realistic car dimensions      |
| Triangle Count      | 5k–500k      | Not trivial, not excessive    |
| Symmetry Score      | > 0.70       | Bilateral symmetry expected   |
| Wheel Clusters      | ≥ 3          | At least 3 wheel-like regions |
| Non-manifold Edges  | < 5%         | Mesh integrity                |
| Normals Consistency | > 95%        | Proper surface orientation    |

### Failure Codes

| Code                       | Condition                          |
| -------------------------- | ---------------------------------- |
| `GEO_SCALE_IMPLAUSIBLE`    | Dimensions outside plausible range |
| `GEO_TRI_COUNT_LOW`        | Too few triangles (trivial blob)   |
| `GEO_TRI_COUNT_HIGH`       | Too many triangles (impractical)   |
| `GEO_ASYMMETRIC`           | Low symmetry score                 |
| `GEO_WHEEL_COUNT_LOW`      | Fewer than expected wheel regions  |
| `GEO_NON_MANIFOLD`         | Excessive non-manifold edges       |
| `GEO_NORMALS_INCONSISTENT` | Normals pointing wrong direction   |
| `MAT_MISSING_TEXTURES`     | Texture references not resolved    |
| `MAT_NO_UVS`               | UVs missing when textures used     |

---

## Recommended Libraries

| Purpose          | Library                         | License          |
| ---------------- | ------------------------------- | ---------------- |
| Mesh Analysis    | trimesh, meshio, open3d         | MIT, MIT, MIT    |
| Object Detection | ultralytics (YOLO), torchvision | AGPL-3.0, BSD    |
| CLIP Embeddings  | open_clip                       | MIT              |
| Image Quality    | piq (NIQE, BRISQUE)             | Apache 2.0       |
| Image Processing | OpenCV, Pillow                  | Apache 2.0, HPND |

## Configuration

```yaml
critics:
  category:
    detector_model: "yolov8n"
    clip_model: "ViT-L/14"
    min_views_passing: 10
    per_view_car_conf_min: 0.60
    clip_margin_min: 0.08
    require_clay_agreement: true

  alignment:
    clip_model: "ViT-L/14"
    margin_min: 0.08
    use_attribute_probes: true

  realism:
    aesthetic_min: 0.55
    niqe_max: 6.0
    magenta_threshold: 0.001

  geometry:
    bounds_m:
      length: [3.0, 6.0]
      width: [1.4, 2.5]
      height: [1.0, 2.5]
    triangle_count: [5000, 500000]
    symmetry_min: 0.70
    wheel_clusters_min: 3
    non_manifold_max_ratio: 0.05
```

## Related Documents

- [Fab Overview](./fab-overview.md) - High-level architecture
- [Render Harness](./fab-render-harness.md) - How renders are produced
- [Gate Decision Logic](./fab-gate-logic.md) - How critic scores become verdicts
