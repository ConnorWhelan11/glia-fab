# Import Playbook — External Gothic Library Asset

Goal: Pull inspiration and selective components from `blender/gothic_library_2_cycles.blend` without cloning the scene, keeping Outora unique and license-safe.

## 0) License & Hygiene
- Confirm rights: derivative use, redistribution limits, attribution. Note it in `licenses/` if any material/texture is used.
- Work on a copy of the source blend; never edit the original download.
- Keep imported bits small and auditable (materials/props), not the full scene.

## 1) Triage the Source (open solo)
- Open `blender/gothic_library_2_cycles.blend` in isolation (not linked to our main file).
- Catalog candidates to study/rebuild: stained glass material, wood (floor/trim), stone displacement, cast-iron (rail/chandelier), spiral stair motif, vaulted rib detail.
- Note scene organization: collections, probe setup (irradiance volumes, reflection cubes), Eevee/Cycles settings.

## 2) Decide What to Recreate vs. Reference
- Materials: recreate the look in our own node groups (tint/roughness/normal tweaks). Do not ship their textures if licensing forbids; swap with our or public PBRs.
- Geometry: use their spiral stair/chandelier as proportion references; re-model or kitbash variants (change profiles, counts, and details).
- Lighting: study their probe placement; rebuild probes in our layout (no baked data reuse).
- Floors/wood: replicate herringbone pattern scale and gloss, but re-author textures/UV scale to our dimensions.
- Glass: recreate the procedural stained glass with Outora nebula palette and emission; do not copy 1:1.

## 3) Safe Extraction Workflow
1) In the source blend, append a tiny subset into a scratch file (e.g., one stair, one chandelier, one stained glass material) to inspect nodes/geometry.
2) Rebuild materials in our scene (new names) with our textures/colors; avoid linking to their images unless license allows and we copy them into `assets/` with attribution.
3) Re-model or heavily modify any borrowed mesh: change tread count, railing pattern, thickness, and silhouette; keep only proportions as inspiration.
4) Recreate probe setup (irradiance volumes, reflection cubes) sized to our atrium/wings; do not reuse baked caches.
5) Keep everything instanced and modular; snap to our bay grid (6m rhythm) and heights.

## 4) Integration Targets (Outora flavor)
- Stone: warm limestone with subtle normals; our `ol_mat_gothic_stone` as base; add trim variants.
- Wood: dark walnut caps/rails/floor; set texel density ~0.5–1m/UV; align grain to direction of travel.
- Glass: nebula/stars emission for apse/clerestory; colored shafts through oculus; parallax-friendly patterns.
- Metal: aged brass/iron for rails, chandeliers, lamps.
- Lighting: rebuild sun/moon + volumetric “knowledge cores”; practical pools at reading bays.

## 5) Validation Checklist
- No direct scene merge; only curated materials/props.
- No reliance on their baked lighting; ours is rebaked/rebuilt.
- Textures we ship are licensed and stored under our tree with attribution.
- New assets named with `ol_` prefix and placed in our collections.
- Performance: keep instancing for books/statues; avoid pulling their whole 1M-vert set.

## 6) Next Actions (if executing now)
- Append a scratch set (stained glass mat, one wood mat, one metal mat, one stair ref) into a temp file. ✅ `blender/scratchpad.blend` → collection `OL_KIT_REF` holds chandeliers, stained glass/window frames, and rail parts (renamed with `ol_` prefix).
- Rebuild materials in our blend with Outora colors and our/no-texture PBR sources.
- Kitbash/re-model a unique spiral stair and chandelier; integrate into the blockout script.
- Add probe layout to our scene and rebake for Eevee; keep Cycles settings aligned to our denoise/adaptive sampling.
- Document any reused assets in `licenses/` and update `architecture/mega_library_concept.md` with the translation notes.
