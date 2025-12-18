"""
Gate Validation Script - Run Outora Library through interior_library_v001 gate.

Validates the library against the Fab gate criteria:
- Geometry checks (bounds, triangle count, floor/ceiling detection)
- Structural rhythm (column spacing, bay regularity)
- Material coverage (no missing textures)
- Furniture presence (desks, chairs, shelves)
- Lighting quality (sufficient light sources)

Usage in Blender:
    exec(open("gate_validation.py").read())

Or:
    import gate_validation as gate
    report = gate.run_full_validation()
    gate.print_report(report)
"""

import bpy
from math import sqrt, pi
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
import json
from pathlib import Path
from datetime import datetime
from mathutils import Vector


# =============================================================================
# GATE CONFIGURATION (from interior_library_v001.yaml)
# =============================================================================

GATE_CONFIG = {
    "gate_config_id": "interior_library_v001",
    "category": "interior_architecture",
    # Geometry bounds (meters)
    "bounds": {
        "length": (10.0, 300.0),
        "width": (10.0, 300.0),
        "height": (3.0, 50.0),
    },
    "triangle_count": (10000, 5000000),
    "symmetry_min": 0.40,
    "manifold_tolerance": 0.25,
    "floor_coverage_min": 0.3,
    # Decision weights
    "weights": {
        "category": 0.20,
        "alignment": 0.25,
        "realism": 0.30,
        "geometry": 0.25,
    },
    "overall_pass_min": 0.60,
    "subscore_floors": {
        "category": 0.40,
        "geometry": 0.45,
        "realism": 0.50,
    },
    # Library-specific
    "expected_bay_size": 6.0,
    "column_spacing_tolerance": 0.3,
    "min_furniture_count": 5,
    "min_light_sources": 2,
    # Hard fail codes
    "hard_fail_codes": [
        "IMPORT_FAILED",
        "MESH_EMPTY",
        "SCALE_INVALID",
        "GEO_NO_FLOOR",
        "GEO_NO_CEILING",
        "REAL_MISSING_TEXTURES_SEVERE",
    ],
}


# =============================================================================
# VALIDATION RESULT CLASSES
# =============================================================================


class ValidationResult:
    """Result of a single validation check."""

    def __init__(
        self,
        name: str,
        passed: bool,
        score: float,
        details: str = "",
        fail_codes: List[str] = None,
    ):
        self.name = name
        self.passed = passed
        self.score = score  # 0.0 to 1.0
        self.details = details
        self.fail_codes = fail_codes or []

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "score": self.score,
            "details": self.details,
            "fail_codes": self.fail_codes,
        }


class GateReport:
    """Complete gate validation report."""

    def __init__(self):
        self.timestamp = datetime.now().isoformat()
        self.gate_config_id = GATE_CONFIG["gate_config_id"]
        self.checks: Dict[str, ValidationResult] = {}
        self.overall_score = 0.0
        self.overall_passed = False
        self.hard_fails: List[str] = []
        self.soft_fails: List[str] = []
        self.recommendations: List[str] = []

    def add_check(self, result: ValidationResult):
        self.checks[result.name] = result
        if result.fail_codes:
            for code in result.fail_codes:
                if code in GATE_CONFIG["hard_fail_codes"]:
                    self.hard_fails.append(code)
                else:
                    self.soft_fails.append(code)

    def calculate_overall(self):
        """Calculate overall score and pass/fail status."""
        weights = GATE_CONFIG["weights"]
        floors = GATE_CONFIG["subscore_floors"]

        # Map check names to weight categories
        category_map = {
            "category_detection": "category",
            "geometry_bounds": "geometry",
            "geometry_structure": "geometry",
            "material_coverage": "realism",
            "lighting_quality": "realism",
            "furniture_presence": "alignment",
            "structural_rhythm": "geometry",
        }

        # Aggregate scores by category
        category_scores = defaultdict(list)
        for check_name, result in self.checks.items():
            cat = category_map.get(check_name, "geometry")
            category_scores[cat].append(result.score)

        # Average within categories
        cat_averages = {}
        for cat, scores in category_scores.items():
            cat_averages[cat] = sum(scores) / len(scores) if scores else 0.5

        # Weighted overall
        total_weight = sum(weights.values())
        weighted_sum = 0.0
        for cat, weight in weights.items():
            weighted_sum += cat_averages.get(cat, 0.5) * weight

        self.overall_score = weighted_sum / total_weight

        # Check floors
        floor_pass = True
        for cat, floor in floors.items():
            if cat_averages.get(cat, 0) < floor:
                floor_pass = False
                self.recommendations.append(
                    f"⚠️ {cat.upper()} score ({cat_averages.get(cat, 0):.2f}) below floor ({floor})"
                )

        # Final verdict
        self.overall_passed = (
            len(self.hard_fails) == 0
            and self.overall_score >= GATE_CONFIG["overall_pass_min"]
            and floor_pass
        )

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "gate_config_id": self.gate_config_id,
            "overall_score": self.overall_score,
            "overall_passed": self.overall_passed,
            "hard_fails": self.hard_fails,
            "soft_fails": self.soft_fails,
            "checks": {k: v.to_dict() for k, v in self.checks.items()},
            "recommendations": self.recommendations,
        }


# =============================================================================
# GEOMETRY VALIDATION
# =============================================================================


def get_scene_bounds() -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Get the bounding box of all mesh objects in the scene."""
    min_co = [float("inf")] * 3
    max_co = [float("-inf")] * 3

    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue

        # Get world-space bounds
        bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        for co in bbox:
            for i in range(3):
                min_co[i] = min(min_co[i], co[i])
                max_co[i] = max(max_co[i], co[i])

    if min_co[0] == float("inf"):
        return ((0, 0, 0), (0, 0, 0))

    return (tuple(min_co), tuple(max_co))


def validate_geometry_bounds() -> ValidationResult:
    """Validate scene bounds against gate requirements."""
    min_co, max_co = get_scene_bounds()

    size_x = max_co[0] - min_co[0]
    size_y = max_co[1] - min_co[1]
    size_z = max_co[2] - min_co[2]

    length = max(size_x, size_y)
    width = min(size_x, size_y)
    height = size_z

    fail_codes = []
    details = []
    score = 1.0

    bounds = GATE_CONFIG["bounds"]

    # Check length
    if length < bounds["length"][0]:
        fail_codes.append("GEO_SCALE_TOO_SMALL")
        score -= 0.3
        details.append(f"Length {length:.1f}m < min {bounds['length'][0]}m")
    elif length > bounds["length"][1]:
        fail_codes.append("GEO_SCALE_TOO_LARGE")
        score -= 0.2
        details.append(f"Length {length:.1f}m > max {bounds['length'][1]}m")
    else:
        details.append(f"Length: {length:.1f}m ✓")

    # Check width
    if width < bounds["width"][0]:
        fail_codes.append("GEO_SCALE_TOO_SMALL")
        score -= 0.3
        details.append(f"Width {width:.1f}m < min {bounds['width'][0]}m")
    elif width > bounds["width"][1]:
        score -= 0.1
        details.append(f"Width {width:.1f}m > max {bounds['width'][1]}m")
    else:
        details.append(f"Width: {width:.1f}m ✓")

    # Check height
    if height < bounds["height"][0]:
        fail_codes.append("GEO_NO_CEILING")
        score -= 0.4
        details.append(
            f"Height {height:.1f}m < min {bounds['height'][0]}m - No ceiling?"
        )
    elif height > bounds["height"][1]:
        score -= 0.1
        details.append(f"Height {height:.1f}m > max {bounds['height'][1]}m")
    else:
        details.append(f"Height: {height:.1f}m ✓")

    # Check for floor (objects near z=0)
    has_floor = any(
        obj.type == "MESH" and abs(obj.location.z) < 1.0
        for obj in bpy.context.scene.objects
    )
    if not has_floor:
        fail_codes.append("GEO_NO_FLOOR")
        score -= 0.3
        details.append("No floor detected near z=0")
    else:
        details.append("Floor detected ✓")

    return ValidationResult(
        name="geometry_bounds",
        passed=len(fail_codes) == 0,
        score=max(0, score),
        details=" | ".join(details),
        fail_codes=fail_codes,
    )


def count_triangles() -> int:
    """Count total triangles in the scene."""
    total = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue

        # Get evaluated mesh (with modifiers applied)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(depsgraph)
        mesh = obj_eval.to_mesh()

        if mesh:
            mesh.calc_loop_triangles()
            total += len(mesh.loop_triangles)
            obj_eval.to_mesh_clear()

    return total


def validate_geometry_structure() -> ValidationResult:
    """Validate geometry structure (triangle count, components)."""
    tri_count = count_triangles()
    mesh_count = sum(1 for obj in bpy.context.scene.objects if obj.type == "MESH")

    fail_codes = []
    details = []
    score = 1.0

    min_tris, max_tris = GATE_CONFIG["triangle_count"]

    if tri_count < min_tris:
        fail_codes.append("GEO_TOO_SIMPLE")
        score -= 0.4
        details.append(f"Triangles: {tri_count:,} < min {min_tris:,}")
    elif tri_count > max_tris:
        fail_codes.append("GEO_TOO_COMPLEX")
        score -= 0.2
        details.append(f"Triangles: {tri_count:,} > max {max_tris:,}")
    else:
        details.append(f"Triangles: {tri_count:,} ✓")

    details.append(f"Mesh objects: {mesh_count}")

    if mesh_count == 0:
        fail_codes.append("MESH_EMPTY")
        score = 0.0
        details.append("No mesh objects in scene!")

    return ValidationResult(
        name="geometry_structure",
        passed=len(fail_codes) == 0,
        score=max(0, score),
        details=" | ".join(details),
        fail_codes=fail_codes,
    )


# =============================================================================
# STRUCTURAL RHYTHM VALIDATION
# =============================================================================


def validate_structural_rhythm() -> ValidationResult:
    """
    Validate column/pier spacing regularity.

    Gothic architecture has regular bay spacing - we check if
    structural elements follow a consistent rhythm.
    """
    expected_bay = GATE_CONFIG["expected_bay_size"]
    tolerance = GATE_CONFIG["column_spacing_tolerance"]

    # Find potential column/pier objects
    columns = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue

        name = obj.name.lower()
        if any(kw in name for kw in ["pier", "column", "pillar", "col_"]):
            columns.append(obj.location.copy())

    if len(columns) < 4:
        return ValidationResult(
            name="structural_rhythm",
            passed=True,
            score=0.5,
            details=f"Only {len(columns)} columns found - rhythm check skipped",
            fail_codes=[],
        )

    # Calculate spacings
    spacings = []
    for i, col1 in enumerate(columns):
        for col2 in columns[i + 1 :]:
            dist = (col1 - col2).length
            # Only consider reasonable spacings (not diagonals)
            if 2.0 < dist < expected_bay * 2.5:
                spacings.append(dist)

    if len(spacings) < 3:
        return ValidationResult(
            name="structural_rhythm",
            passed=True,
            score=0.6,
            details="Not enough spacing samples",
            fail_codes=[],
        )

    # Check regularity
    avg_spacing = sum(spacings) / len(spacings)
    variance = sum((s - avg_spacing) ** 2 for s in spacings) / len(spacings)
    std_dev = sqrt(variance)

    # Score based on regularity
    regularity = 1.0 - (std_dev / avg_spacing) if avg_spacing > 0 else 0

    # Check if close to expected bay
    bay_match = 1.0 - abs(avg_spacing - expected_bay) / expected_bay
    bay_match = max(0, min(1, bay_match))

    score = regularity * 0.6 + bay_match * 0.4

    details = [
        f"Columns found: {len(columns)}",
        f"Avg spacing: {avg_spacing:.2f}m (expected {expected_bay}m)",
        f"Regularity: {regularity:.0%}",
        f"Bay match: {bay_match:.0%}",
    ]

    fail_codes = []
    if regularity < 0.5:
        fail_codes.append("STRUCT_IRREGULAR_RHYTHM")

    return ValidationResult(
        name="structural_rhythm",
        passed=score >= 0.5,
        score=score,
        details=" | ".join(details),
        fail_codes=fail_codes,
    )


# =============================================================================
# MATERIAL VALIDATION
# =============================================================================


def validate_material_coverage() -> ValidationResult:
    """
    Validate that materials are applied to visible surfaces.

    Checks for:
    - Objects with no materials
    - Missing texture slots
    - Default/placeholder materials
    """
    no_material = []
    placeholder_material = []
    good_material = []

    placeholder_names = ["material", "default", "placeholder", "none", "mat_"]

    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue

        if not obj.data.materials or len(obj.data.materials) == 0:
            no_material.append(obj.name)
        else:
            has_real = False
            for mat in obj.data.materials:
                if mat is None:
                    continue
                name_lower = mat.name.lower()
                if any(p in name_lower for p in placeholder_names):
                    placeholder_material.append(obj.name)
                else:
                    has_real = True
            if has_real:
                good_material.append(obj.name)

    total = len(no_material) + len(placeholder_material) + len(good_material)
    if total == 0:
        return ValidationResult(
            name="material_coverage",
            passed=True,
            score=0.5,
            details="No mesh objects to check",
            fail_codes=[],
        )

    coverage = len(good_material) / total
    score = coverage

    fail_codes = []
    details = [
        f"Good materials: {len(good_material)}/{total}",
        f"No material: {len(no_material)}",
        f"Placeholder: {len(placeholder_material)}",
    ]

    if len(no_material) > total * 0.3:
        fail_codes.append("REAL_MISSING_TEXTURES_SEVERE")
        details.append("Too many objects without materials!")
    elif len(no_material) > 0:
        fail_codes.append("REAL_MISSING_TEXTURES")

    return ValidationResult(
        name="material_coverage",
        passed=coverage >= 0.7,
        score=score,
        details=" | ".join(details),
        fail_codes=fail_codes,
    )


# =============================================================================
# FURNITURE VALIDATION
# =============================================================================


def validate_furniture_presence() -> ValidationResult:
    """
    Validate presence of required furniture types.

    Libraries need desks, chairs, and shelves.
    """
    furniture_keywords = {
        "desk": ["desk", "table", "lectern"],
        "chair": ["chair", "seat", "stool", "bench"],
        "shelf": ["shelf", "bookshelf", "bookcase", "stack", "book"],
    }

    found = {ft: [] for ft in furniture_keywords}

    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue

        name_lower = obj.name.lower()
        for ft, keywords in furniture_keywords.items():
            if any(kw in name_lower for kw in keywords):
                found[ft].append(obj.name)

    total_furniture = sum(len(v) for v in found.values())
    min_required = GATE_CONFIG["min_furniture_count"]

    types_found = sum(1 for v in found.values() if len(v) > 0)

    score = min(1.0, total_furniture / min_required) * 0.7 + (types_found / 3) * 0.3

    details = [f"Total furniture: {total_furniture}"]
    for ft, items in found.items():
        status = "✓" if len(items) > 0 else "✗"
        details.append(f"{ft}: {len(items)} {status}")

    fail_codes = []
    if total_furniture < min_required:
        fail_codes.append("LIB_INSUFFICIENT_FURNITURE")
    if types_found < 2:
        fail_codes.append("LIB_MISSING_FURNITURE_TYPES")

    return ValidationResult(
        name="furniture_presence",
        passed=total_furniture >= min_required and types_found >= 2,
        score=score,
        details=" | ".join(details),
        fail_codes=fail_codes,
    )


# =============================================================================
# LIGHTING VALIDATION
# =============================================================================


def validate_lighting_quality() -> ValidationResult:
    """
    Validate lighting setup.

    Checks for:
    - Minimum number of light sources
    - Light energy distribution
    - Presence of practical lights (desk lamps)
    """
    lights = [obj for obj in bpy.context.scene.objects if obj.type == "LIGHT"]

    min_lights = GATE_CONFIG["min_light_sources"]

    if len(lights) < min_lights:
        return ValidationResult(
            name="lighting_quality",
            passed=False,
            score=len(lights) / min_lights,
            details=f"Only {len(lights)} lights (need {min_lights}+)",
            fail_codes=["LIB_INSUFFICIENT_LIGHTING"],
        )

    # Analyze light types
    light_types = defaultdict(int)
    total_energy = 0

    for light in lights:
        light_types[light.data.type] += 1
        total_energy += light.data.energy

    # Check for variety
    type_variety = len(light_types)
    has_practical = any(
        "desk" in obj.name.lower() or "lamp" in obj.name.lower() for obj in lights
    )

    score = min(1.0, len(lights) / 10)  # More lights = better, up to 10
    if type_variety >= 2:
        score += 0.1
    if has_practical:
        score += 0.1

    score = min(1.0, score)

    details = [
        f"Light count: {len(lights)}",
        f"Types: {dict(light_types)}",
        f"Total energy: {total_energy:.0f}W",
        f"Has practical lamps: {'✓' if has_practical else '✗'}",
    ]

    return ValidationResult(
        name="lighting_quality",
        passed=True,
        score=score,
        details=" | ".join(details),
        fail_codes=[],
    )


# =============================================================================
# CATEGORY DETECTION (Simplified)
# =============================================================================


def validate_category_detection() -> ValidationResult:
    """
    Simplified category validation based on object naming and structure.

    Full category detection would use ML models - this checks for
    interior-related object names and scene composition.
    """
    interior_keywords = [
        "floor",
        "wall",
        "ceiling",
        "door",
        "window",
        "arch",
        "column",
        "pier",
        "desk",
        "chair",
        "shelf",
        "lamp",
        "stair",
        "rail",
        "balustrade",
        "beam",
        "chandelier",
    ]

    matches = 0
    total_mesh = 0

    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        total_mesh += 1

        name_lower = obj.name.lower()
        if any(kw in name_lower for kw in interior_keywords):
            matches += 1

    if total_mesh == 0:
        return ValidationResult(
            name="category_detection",
            passed=False,
            score=0.0,
            details="No mesh objects",
            fail_codes=["MESH_EMPTY"],
        )

    ratio = matches / total_mesh
    score = min(1.0, ratio * 2)  # 50% matches = full score

    # Check for enclosed space indicators
    has_floor = any("floor" in obj.name.lower() for obj in bpy.context.scene.objects)
    has_walls = any("wall" in obj.name.lower() for obj in bpy.context.scene.objects)
    has_ceiling = any(
        kw in obj.name.lower()
        for obj in bpy.context.scene.objects
        for kw in ["ceiling", "vault", "roof", "rib"]
    )

    enclosure_score = (has_floor + has_walls + has_ceiling) / 3

    final_score = score * 0.6 + enclosure_score * 0.4

    details = [
        f"Interior keywords: {matches}/{total_mesh} ({ratio:.0%})",
        f"Floor: {'✓' if has_floor else '✗'}",
        f"Walls: {'✓' if has_walls else '✗'}",
        f"Ceiling: {'✓' if has_ceiling else '✗'}",
    ]

    fail_codes = []
    if final_score < 0.4:
        fail_codes.append("CAT_NOT_INTERIOR")

    return ValidationResult(
        name="category_detection",
        passed=final_score >= 0.4,
        score=final_score,
        details=" | ".join(details),
        fail_codes=fail_codes,
    )


# =============================================================================
# MAIN VALIDATION FUNCTION
# =============================================================================


def run_full_validation() -> GateReport:
    """
    Run all validation checks and produce a gate report.
    """
    print("\n" + "=" * 70)
    print("INTERIOR LIBRARY GATE VALIDATION")
    print("Gate: interior_library_v001")
    print("=" * 70)

    report = GateReport()

    # Run all checks
    checks = [
        ("Category Detection", validate_category_detection),
        ("Geometry Bounds", validate_geometry_bounds),
        ("Geometry Structure", validate_geometry_structure),
        ("Structural Rhythm", validate_structural_rhythm),
        ("Material Coverage", validate_material_coverage),
        ("Furniture Presence", validate_furniture_presence),
        ("Lighting Quality", validate_lighting_quality),
    ]

    print("\n🔍 Running validation checks...\n")

    for name, check_fn in checks:
        try:
            result = check_fn()
            report.add_check(result)

            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"   {name}: {status} ({result.score:.0%})")
            print(f"      {result.details}")
            if result.fail_codes:
                print(f"      Codes: {result.fail_codes}")
            print()
        except Exception as e:
            print(f"   {name}: ⚠️ ERROR - {e}")
            report.add_check(
                ValidationResult(
                    name=name.lower().replace(" ", "_"),
                    passed=False,
                    score=0.0,
                    details=f"Error: {str(e)}",
                    fail_codes=["VALIDATION_ERROR"],
                )
            )

    # Calculate overall
    report.calculate_overall()

    # Add recommendations
    if not report.overall_passed:
        if report.hard_fails:
            report.recommendations.insert(
                0,
                f"🚨 HARD FAILS: {', '.join(report.hard_fails)} - Must fix before retrying",
            )
        if report.soft_fails:
            report.recommendations.append(
                f"⚠️ Soft fails: {', '.join(report.soft_fails)}"
            )

    return report


def print_report(report: GateReport):
    """Print a formatted gate report."""
    print("\n" + "=" * 70)
    print("GATE VERDICT")
    print("=" * 70)

    verdict = "✅ PASS" if report.overall_passed else "❌ FAIL"
    print(f"\n   Overall: {verdict}")
    print(
        f"   Score: {report.overall_score:.0%} (threshold: {GATE_CONFIG['overall_pass_min']:.0%})"
    )

    if report.hard_fails:
        print(f"\n   🚨 Hard Fails: {', '.join(report.hard_fails)}")

    if report.soft_fails:
        print(f"\n   ⚠️ Soft Fails: {', '.join(report.soft_fails)}")

    print("\n   Subscores:")
    for name, result in report.checks.items():
        status = "✓" if result.passed else "✗"
        print(f"      {status} {name}: {result.score:.0%}")

    if report.recommendations:
        print("\n   📋 Recommendations:")
        for rec in report.recommendations:
            print(f"      {rec}")

    print("\n" + "=" * 70 + "\n")


def save_report(report: GateReport, filepath: str = None):
    """Save report to JSON file."""
    if filepath is None:
        filepath = "/tmp/gate_report.json"

    with open(filepath, "w") as f:
        json.dump(report.to_dict(), f, indent=2)

    print(f"📄 Report saved to: {filepath}")


# =============================================================================
# REPAIR RECOMMENDATIONS
# =============================================================================

REPAIR_PLAYBOOK = {
    "GEO_NO_FLOOR": {
        "priority": 1,
        "title": "Add Floor",
        "instructions": """
Add a floor plane to the interior:
1. Create plane at z=0
2. Scale to cover scene footprint
3. Apply stone/tile material
""",
    },
    "GEO_NO_CEILING": {
        "priority": 1,
        "title": "Add Ceiling/Vault",
        "instructions": """
Add ceiling structure:
1. For Gothic: Add vault ribs and ceiling panels
2. Use transverse_ribs from layout generator
3. Or add flat ceiling with beams
""",
    },
    "REAL_MISSING_TEXTURES_SEVERE": {
        "priority": 1,
        "title": "Apply Materials",
        "instructions": """
Run material assignment:
1. import gothic_materials as mats
2. mats.create_all_materials()
3. mats.apply_materials_to_scene()
""",
    },
    "LIB_INSUFFICIENT_FURNITURE": {
        "priority": 2,
        "title": "Add Furniture",
        "instructions": """
Add library furniture:
1. Desks at study_pod_positions
2. Chairs with desks
3. Bookshelves along walls
""",
    },
    "LIB_INSUFFICIENT_LIGHTING": {
        "priority": 2,
        "title": "Add Lighting",
        "instructions": """
Run lighting setup:
1. import gothic_lighting as lights
2. lights.create_lighting_setup()
3. Or use preset: lights.preset_dramatic()
""",
    },
}


def print_repair_instructions(report: GateReport):
    """Print repair instructions for failed checks."""
    all_codes = report.hard_fails + report.soft_fails

    if not all_codes:
        print("\n✅ No repairs needed!")
        return

    print("\n" + "=" * 70)
    print("REPAIR INSTRUCTIONS")
    print("=" * 70)

    # Sort by priority
    repairs = []
    for code in all_codes:
        if code in REPAIR_PLAYBOOK:
            repair = REPAIR_PLAYBOOK[code]
            repairs.append((repair["priority"], code, repair))

    repairs.sort(key=lambda x: x[0])

    for priority, code, repair in repairs:
        print(f"\n[P{priority}] {repair['title']} ({code})")
        print("-" * 40)
        print(repair["instructions"])

    print("\n" + "=" * 70 + "\n")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    report = run_full_validation()
    print_report(report)
    print_repair_instructions(report)
    save_report(report)
