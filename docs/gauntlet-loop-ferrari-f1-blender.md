# Gauntlet Loop: Ferrari SF-26 F1 3D Model with Blender MCP in Kiro

## Goal

Build a **Ferrari SF-26 (2026 season) F1 car 3D model** using **Blender MCP in Kiro**, with:
- Accurate 2026 regulation dimensions (wheelbase 3400mm, width 1900mm, reduced front wing overhang)
- Authentic Ferrari livery and sponsor decals (Leclerc #16, Hamilton #44)
- PBR materials (metallic/roughness workflow, 4K textures)
- Functional components (front/rear wings, suspension, wheels, cockpit, halo)
- LOD variants (61k base, 490k sub1, 1.96M sub2)

## Quality Bar (Concrete, Inspectable)

**Primary bar**: [Ferrari SF-26 PBR 3D model on TurboSquid](https://www.turbosquid.com/3d-models/red-f1-team-2026-formula-1-race-car-2546351) — a production-ready Blender 4.4 model with 61,323 polygons (no n-gons), 7 PBR materials with 4K textures (AO, BaseColor, Metallic, Roughness, Normal, Emissive), metric scale, and functional part grouping. The critic can import both models side by side, compare polygon counts, texture resolutions, material fidelity, and dimensional accuracy against 2026 regulation specs. [cite:35]

**Secondary bar**: Official 2026 F1 dimension summary — wheelbase 3400mm (−200mm), width 1900mm (−100mm), front wing overhang −50mm, Pirelli tire width −30mm, diameter −10mm. The model must match these specs within 1% tolerance. [cite:38][cite:39]

**Tertiary bar**: Ferrari SF-26 official photos and technical specs — carbon fibre chassis, double wishbone push-rod suspension, 770kg total weight, 18-inch Pirelli wheels, Shell V-Power livery. [cite:32][cite:33][cite:34][cite:45]

## One-Sentence Bar Statement

The model must match or exceed the TurboSquid Ferrari SF-26's polygon efficiency (61k base, 490k sub1, 1.96M sub2), PBR material completeness (7 materials, 4K AO/BaseColor/Metallic/Roughness/Normal/Emissive maps), and 2026 regulation dimensions (3400mm wheelbase, 1900mm width) within 1% tolerance. [cite:35][cite:38][cite:39]

## Gauntlet Loop Prompt (Paste-Ready)

```text
Build a Ferrari SF-26 (2026 season) F1 car 3D model using Blender MCP in Kiro, with accurate 2026 regulation dimensions, authentic Ferrari livery (Leclerc #16, Hamilton #44), PBR materials (4K textures, metallic/roughness workflow), and functional components (wings, suspension, wheels, cockpit, halo).

Quality bar: Match or exceed the TurboSquid Ferrari SF-26 PBR model — 61,323 base polygons (no n-gons), 7 PBR materials with 4K textures (AO, BaseColor, Metallic, Roughness, Normal, Emissive), metric scale, functional part grouping — while matching 2026 F1 regulation dimensions (3400mm wheelbase, 1900mm width, −50mm front wing overhang, −30mm tire width) within 1% tolerance.

Divide it into the smallest pieces that can be improved and judged independently. For each important piece, fan out a builder and a separate, harsh critic with fresh context. The critic must inspect the real output, compare it directly with the bar—blind A/B when possible—pick a winner, and identify the single biggest remaining gap. Send losses back for another round and keep looping until ours wins or I stop the run.

Maintain a simple live progress page showing the evolving work, comparisons, verdicts, and remaining gaps. Use subagents and ultracode. Choose the approach yourself.
```

## Decomposition Hints (for the Lead Agent)

The lead agent may choose to split into independent, judgeable pieces such as:

1. **Blockout & proportions**: 2026 regulation dimensions (3400mm wheelbase, 1900mm width, 960mm height, 770kg weight) [cite:38][cite:39][cite:41][cite:45]
2. **Chassis & bodywork**: Carbon fibre survival cell, honeycomb structure, nose cone, sidepods, engine cover, shark fin [cite:32][cite:35]
3. **Front wing**: 2026 reduced overhang (−50mm), multi-element design, endplates, DRS actuator [cite:38][cite:39]
4. **Rear wing**: Narrower beam wing, DRS flap, endplate geometry, exhaust outlet [cite:38][cite:39]
5. **Suspension**: Double wishbone push-rod (front/rear), carbon fibre wishbones, dampers, anti-roll bars [cite:32][cite:45]
6. **Wheels & tyres**: 18-inch Pirelli rims, 305/705R18 front, 405/705R18 rear, tire tread patterns (slick/wet compounds) [cite:32][cite:38][cite:41][cite:45]
7. **Cockpit & halo**: Driver seating position, steering wheel, halo safety device, mirror mounts [cite:35][cite:43]
8. **Livery & materials**: Ferrari Rosso Corsa red, Shell V-Power sponsors, Leclerc #16 / Hamilton #44, PBR workflow (metallic 0.6-0.9, roughness 0.2-0.4) [cite:33][cite:34][cite:35]
9. **Texture maps**: 4K AO, BaseColor, Metallic, Roughness, Normal, Emissive for each material (Body, Bottom, Helmet, Wheels, Driver) [cite:35]
10. **LOD variants**: Base (61k polys), Sub1 (490k), Sub2 (1.96M) for game/mobile vs. broadcast use [cite:35]
11. **Validation**: Import TurboSquid model side by side, compare polygon counts, texture resolutions, dimensional accuracy [cite:35][cite:38]

Each piece gets its own builder/critic pair with blind A/B against the TurboSquid reference or 2026 regulation specs.

## References

- [TurboSquid Ferrari SF-26 PBR Model](https://www.turbosquid.com/3d-models/red-f1-team-2026-formula-1-race-car-2546351) — 61k polys, 7 PBR materials, 4K textures [cite:35]
- [2026 F1 Dimension Summary](https://www.giorgiopioladesign.com/news/2301/dimension-summary-of-the-2026-cars/) — 3400mm wheelbase, 1900mm width, reduced overhangs [cite:38][cite:39]
- [Ferrari SF-26 Technical Specs](https://en.wikipedia.org/wiki/Ferrari_SF-26) — 770kg, 1.6L V6 turbo, 18-inch wheels [cite:32][cite:45]
- [Ferrari SF-26 Gallery](https://www.formula1.com/en/latest/article/gallery-check-out-every-angle-of-ferraris-2026-f1-car.7HdOPtJJwN5VHJ8XAWVtuS) — Official photos, livery reference [cite:33][cite:34]
- [Blender MCP + Kiro workflow](https://www.youtube.com/watch?v=YN6Jpy7zaVU) — Claude Code remote-controls Blender via MCP for parametric modeling [cite:40]