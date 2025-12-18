# Outora Mega Library — Concept Package

Revision: v0.1 (concept blockout)  
Author: Codex (with Connor)  
Context: Grow the single-room library into a cathedral-scale, multi-level knowledge palace inspired by Notre Dame + Great Library of Alexandria, grounded in the Outora universe (celestial skybox, warm stone + dark wood, luminous knowledge cores).

## 1) Design Goals

- Grand procession: enter through a nave-like axis, rise to a luminous void at the crossing, then disperse to specialized wings.
- Legible hierarchy: clear primary circulation spine, secondary mezzanine loops, tertiary study nooks.
- Sacred knowledge vibe: towering stone ribs, clerestory light shafts, cosmic windows, sculptural guardians, and floating stacks.
- Performance-aware: repeatable modular kit pieces, mirrored wings, instancing-friendly shelves/books/statuary.

## 1.1) Architectural Vocabulary (usable in Blender)

- Nave / Transept / Crossing: cross-shaped primary axes; keep widths consistent (nave/transept 8m clear).
- Bay rhythm: repeat structural bays every ~6m (pier-to-pier); align arches, buttresses, and windows to the same grid.
- Aisles / Side naves: parallel narrow corridors (2–3m clear) behind main colonnades.
- Piers & Buttresses: vertical supports every bay; buttresses thicken the outer wall and frame clerestory windows.
- Clerestory: upper band of windows above mezzanine balustrades; use stained/frosted glass for light shafts.
- Balustrade: railing at mezzanine edge (1.0–1.2m high); cap in dark wood or stone.
- Oculus: circular opening above the crossing; let skybox show through and add volumetric light.
- Apse: north terminal wall with the largest stained glass; treat as focal wall.
- Plinths: statue bases (0.6–0.8m high) to elevate guardians and avoid sunk feet.
- Vaulting (hinted): shallow barrel/rib cues by arranging arches in series; do not need full mesh, just rhythm and crest height.

## 2) Spatial Program (Plan Logic)

- **Crossing Atrium (Hero Volume)**: 24m x 24m, double-height (0–10m), central oculus opening to skybox; anchor the hero desk + lectern at center; four colossal arches frame each cardinal wing.
- **Nave Axis (North–South)**: 8m-wide processional path; statue-lined; long sightline to a stained-glass apse at the north end.
- **Transept Axis (East–West)**: connects research labs and rare stacks; framed by paired arches and balustrades.
- **Four Cardinal Wings (Repeatable Module)**: each ~18m deep; ground level stacks + side alcoves; mezzanine ring at +5m with railings and reading bays; terminate in tall window/buttress sets.
- **Core Vertical Circulation**: four grand stairs at cardinal sides of the crossing, rising to mezzanine; discrete service ladders tucked in corners for shelf access (can be implied).
- **Reading Nooks**: inset bays under clerestory arches; pair with lamplight pools and benches.
- **Vaulted Ceiling Bands**: intersecting barrel or shallow rib vault hints using the large arches; leave negative space for the cosmic skybox.

## 3) Vertical Section (Heights)

- Ground plane 0m; mezzanine deck +5m; upper cornice/clerestory ~9–10m.
- Arches scaled to 8–10m crest; statues at 2.5–3m on plinths; balustrades 1–1.2m.
- Hero oculus: 6–8m diameter opening above crossing; could be implied via skybox cutout if geometry is heavy.
- Deck thickness: mezzanine slab 0.4–0.6m; add underside beams/ribs every bay for believability.
- Stair proportions: riser ~0.17m, tread ~0.30m (keep ~30–32 steps to reach +5m with landings).

## 4) Circulation & Sightlines

- Primary loop: cross-shaped perimeter around the atrium + four mezzanine balconies that overlook the crossing.
- Secondary: per-wing lateral aisles behind columns; maintain 1.5–2m clear width.
- Vistas: lock hero camera(s) down the nave and across the transept; maintain consistent arch rhythm for parallax.

## 5) Focal Elements (Placements)

- **Hero Desk Stack**: center of crossing, under oculus; flanked by four statues.
- **Apse Window**: north terminal wall gets the most dramatic stained glass (Outora nebula palette).
- **Knowledge Cores**: two or four vertical light shafts (volumetric) rising at the corners of the crossing.
- **Guardians**: statue pairs at each wing threshold and near stair landings.
- **Grand Stairs**: at N/S/E/W edges of atrium, ascending to mezzanine; mirrored for symmetry.

## 6) Kitbash Mapping (Gothic Kit)

- **Arches**: use `GIK_Arch1` for main crossing arches; scale uniformly 2.2–2.6; align crest at ~8–9m.
- **Balustrades & UpperWalls**: `GIK_LongStair1` rail segments + `GIK_UpperWall.001` for mezzanine edges.
- **Walls & Buttresses**: `Wall2`, `Plane.006/008`, `Cube.006/012/014` as pier/buttress masses; repeat rhythmically.
- **Stairs**: `GIK_LongStair1` and `GIK_CornerStair1` for grand + half-turn variants.
- **Windows**: `GIK_Window`, `MinWindow` for clerestory/apse; integrate stained materials.
- **Statues**: `Statue1`, `Statue2` on custom plinths (simple cubes 0.6–0.8m tall).
- **Decks/Slabs**: use generated planes for mezzanine; add `Cube.*` strips beneath as beams aligned to the bay grid.
- **Buttress cadence**: every bay (6m) place a `Wall2`/`Cube.006` pillar; inset `GIK_Window` or `MinWindow` between piers.

## 7) Material & Lighting Intent

- Stone: warm limestone (existing `ol_mat_gothic_stone`), add subtle normals/roughness variation; darker trim for bases/caps.
- Wood: rich, dark walnut for shelves, desks, rail caps, benches.
- Metal: aged brass accents on lamps/rail finials.
- Glass: emissive stained panels with nebula hues; frosted clerestory for soft gradients.
- Lighting: single key “sun/moon” through apse + volumetric shafts at crossing; warm practical pools at reading bays; cooler rim from skybox spill to keep depth.
- Texture scale guides: stone texel density ~0.5–1m per UV unit; wood grain aligned with length of rails/shelves; glass emission bounded to panels only.

## 8) Phased Execution Plan (Blender)

1. **Layout Refinement**: lock atrium footprint (24x24), position four arches, enforce bay rhythm (buttress/wall/window pattern) along each wing; carve nave/transept clear widths.
2. **Verticals & Decks**: set mezzanine deck heights and cut central oculus; place balustrades and support columns at 6–8m spacing.
3. **Stairs & Access**: mirror grand stairs at N/S/E/W; ensure landings meet mezzanine; add implied ladders in nooks.
4. **Fenestration**: place stained-glass apse (north), clerestory windows on mezzanine level, smaller lower windows in wings.
5. **Dressing & Rhythm**: distribute statues (wing thresholds + crossing), re-instance shelves/books with density gradients (higher near nave, sparser at transept ends), add benches and lamps in bays.
6. **Lighting Pass**: rebalance suns/fill; add volumetric light columns at knowledge cores; practicals at reading bays.
7. **Optimization**: merge repeating modules, ensure instancing for shelves/books/statues; clean collisions and clearances.

## 9) Deliverables Checklist

- Updated blockout script variant for the principled layout (crossing + wings + mezzanine rhythm).
- Stained-glass material preset + placement on apse/clerestories.
- Hero camera set: nave shot, transept shot, crossing top-down, reading bay closeup.
- Lighting preset: sun/moon angle, volumetric shafts, practical pools.

## 10) Outora Flavor Anchors

- Cosmic skybox visible through oculus and apse; subtle parallax in stained-glass emission.
- “Knowledge cores” as softly glowing columns rising beside the central stacks.
- Quiet alcoves with warm pools of light, contrasting the cool cosmic spill from upper windows.

each section in the outora library is owned by a student, they get their own study pod, table desk etc, it's a massive procedurally generated library universe
