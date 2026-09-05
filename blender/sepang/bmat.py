"""
Shared Blender material library for the Sepang scene.

Every surface that has to react to the monsoon exposes a Value node named
"Wetness" (0 = bone dry, 1 = standing water). The weather engine keyframes those
nodes, so rain visually changes the track instead of only changing numbers.
"""

import bpy

WET_NODE = "Wetness"


def _set(node, names, value):
    """Set the first input socket that exists out of `names`."""
    if isinstance(names, str):
        names = [names]
    for nm in names:
        if nm in node.inputs:
            try:
                node.inputs[nm].default_value = value
                return True
            except (TypeError, ValueError):
                pass
    return False


def get_wetness_node(mat):
    if not mat or not mat.use_nodes:
        return None
    return mat.node_tree.nodes.get(WET_NODE)


def _new(name):
    """
    Reuse an existing material datablock and rebuild its node tree in place.
    Removing and recreating it would unlink it from every mesh that already
    references it, silently leaving the track untextured.
    """
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat, nt, bsdf


def simple(name, color, roughness=0.6, metallic=0.0, emission=None,
           emission_strength=0.0):
    mat, nt, bsdf = _new(name)
    _set(bsdf, "Base Color", (*color, 1.0))
    _set(bsdf, "Roughness", roughness)
    _set(bsdf, "Metallic", metallic)
    if emission:
        _set(bsdf, ["Emission Color", "Emission"], (*emission, 1.0))
        _set(bsdf, "Emission Strength", emission_strength)
    return mat


def wet_capable(name, dry_color, dry_rough, wet_rough=0.06, darken=0.45,
                metallic=0.0, patch_scale=0.0, patch_tint=1.5, patch_amount=0.5,
                grain_scale=0.0, bump=0.0):
    """
    Surface whose roughness/colour are driven by a "Wetness" Value node.
    Wet asphalt goes dark and mirror-like, which is what sells rain on camera.

    UVs on the track meshes are in METRES, so texture scales are given as
    cycles per metre: patch_scale ~0.03 gives ~30 m colour patches, and
    grain_scale ~25 gives ~4 cm surface grain.
    """
    mat, nt, bsdf = _new(name)
    wet = nt.nodes.new("ShaderNodeValue")
    wet.name = wet.label = WET_NODE
    wet.location = (-800, -300)
    wet.outputs[0].default_value = 0.0

    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.location = (-560, -260)
    rough.inputs["From Min"].default_value = 0.0
    rough.inputs["From Max"].default_value = 1.0
    rough.inputs["To Min"].default_value = dry_rough
    rough.inputs["To Max"].default_value = wet_rough
    nt.links.new(wet.outputs[0], rough.inputs["Value"])

    dark = nt.nodes.new("ShaderNodeMixRGB")
    dark.location = (-560, 40)
    dark.blend_type = 'MIX'
    dark.inputs["Color1"].default_value = (*dry_color, 1.0)
    dark.inputs["Color2"].default_value = (dry_color[0] * darken,
                                          dry_color[1] * darken,
                                          dry_color[2] * darken, 1.0)
    nt.links.new(wet.outputs[0], dark.inputs["Fac"])

    uv = None
    if patch_scale > 0.0 or grain_scale > 0.0:
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.location = (-1600, 200)

    if patch_scale > 0.0:
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.location = (-1400, 240)
        noise.inputs["Scale"].default_value = patch_scale
        noise.inputs["Detail"].default_value = 4.0
        noise.inputs["Roughness"].default_value = 0.6
        nt.links.new(uv.outputs["UV"], noise.inputs["Vector"])
        fac = nt.nodes.new("ShaderNodeMath")
        fac.location = (-1200, 300)
        fac.operation = 'MULTIPLY'
        fac.inputs[1].default_value = patch_amount
        nt.links.new(noise.outputs["Fac"], fac.inputs[0])
        tint = nt.nodes.new("ShaderNodeMixRGB")
        tint.location = (-1000, 160)
        tint.blend_type = 'MIX'
        tint.inputs["Color1"].default_value = (*dry_color, 1.0)
        tint.inputs["Color2"].default_value = (min(1.0, dry_color[0] * patch_tint),
                                              min(1.0, dry_color[1] * patch_tint),
                                              min(1.0, dry_color[2] * patch_tint), 1.0)
        nt.links.new(fac.outputs[0], tint.inputs["Fac"])
        nt.links.new(tint.outputs["Color"], dark.inputs["Color1"])

    if grain_scale > 0.0 and bump > 0.0:
        grain = nt.nodes.new("ShaderNodeTexNoise")
        grain.location = (-1400, -240)
        grain.inputs["Scale"].default_value = grain_scale
        grain.inputs["Detail"].default_value = 3.0
        nt.links.new(uv.outputs["UV"], grain.inputs["Vector"])
        bp = nt.nodes.new("ShaderNodeBump")
        bp.location = (-300, -420)
        bp.inputs["Distance"].default_value = 1.0
        nt.links.new(grain.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
        # standing water fills the surface texture in, so fade the bump when wet
        fade = nt.nodes.new("ShaderNodeMapRange")
        fade.location = (-520, -460)
        fade.inputs["To Min"].default_value = bump
        fade.inputs["To Max"].default_value = bump * 0.15
        nt.links.new(wet.outputs[0], fade.inputs["Value"])
        nt.links.new(fade.outputs["Result"], bp.inputs["Strength"])

    nt.links.new(dark.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    _set(bsdf, "Metallic", metallic)
    return mat


def kerb(name="SEP_Kerb", stripe_m=1.0):
    """Red/white kerb striped along the track using UV.u = distance in metres."""
    mat, nt, bsdf = _new(name)
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.location = (-1000, 0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-820, 0)
    nt.links.new(uv.outputs["UV"], sep.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.location = (-620, 0)
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'X'
    wave.wave_profile = 'SAW'
    wave.inputs["Scale"].default_value = 1.0
    combine = nt.nodes.new("ShaderNodeCombineXYZ")
    combine.location = (-780, -200)
    div = nt.nodes.new("ShaderNodeMath")
    div.location = (-900, -260)
    div.operation = 'DIVIDE'
    div.inputs[1].default_value = stripe_m * 2.0
    nt.links.new(sep.outputs["X"], div.inputs[0])
    nt.links.new(div.outputs[0], combine.inputs["X"])
    nt.links.new(combine.outputs["Vector"], wave.inputs["Vector"])

    step = nt.nodes.new("ShaderNodeMath")
    step.location = (-440, 0)
    step.operation = 'GREATER_THAN'
    step.inputs[1].default_value = 0.5
    nt.links.new(wave.outputs["Fac"], step.inputs[0])

    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.location = (-240, 0)
    mix.inputs["Color1"].default_value = (0.85, 0.85, 0.85, 1.0)
    mix.inputs["Color2"].default_value = (0.65, 0.05, 0.04, 1.0)
    nt.links.new(step.outputs[0], mix.inputs["Fac"])
    nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])

    wet = nt.nodes.new("ShaderNodeValue")
    wet.name = wet.label = WET_NODE
    wet.location = (-440, -240)
    wet.outputs[0].default_value = 0.0
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.location = (-240, -240)
    rough.inputs["To Min"].default_value = 0.45
    rough.inputs["To Max"].default_value = 0.08
    nt.links.new(wet.outputs[0], rough.inputs["Value"])
    nt.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    return mat


def _make_transparent(mat, alpha):
    """Catch fencing reads as mesh, not a solid wall."""
    bsdf = None
    for nd in mat.node_tree.nodes:
        if nd.type == 'BSDF_PRINCIPLED':
            bsdf = nd
    if bsdf:
        _set(bsdf, "Alpha", alpha)
    for attr, vals in (("surface_render_method", ('BLENDED',)),
                       ("blend_method", ('BLEND', 'HASHED'))):
        if hasattr(mat, attr):
            for v in vals:
                try:
                    setattr(mat, attr, v)
                    break
                except (TypeError, ValueError):
                    continue
    try:
        mat.show_transparent_back = False
    except AttributeError:
        pass
    return mat


def build_all():
    """(Re)create the whole material set. Returns a name -> material dict."""
    m = {}
    m["asphalt"] = wet_capable("SEP_Asphalt", (0.030, 0.031, 0.034), 0.60,
                               wet_rough=0.045, darken=0.35,
                               patch_scale=0.022, patch_tint=1.9, patch_amount=0.55,
                               grain_scale=22.0, bump=0.30)
    m["runoff"] = wet_capable("SEP_Runoff", (0.085, 0.076, 0.070), 0.74,
                              wet_rough=0.11, darken=0.5,
                              patch_scale=0.05, patch_tint=1.5, patch_amount=0.6,
                              grain_scale=14.0, bump=0.45)
    m["kerb"] = kerb()
    m["grass"] = wet_capable("SEP_Grass", (0.038, 0.098, 0.026), 0.88,
                             wet_rough=0.32, darken=0.62,
                             patch_scale=0.012, patch_tint=2.2, patch_amount=0.8,
                             grain_scale=1.2, bump=0.6)
    m["line"] = simple("SEP_Line", (0.92, 0.92, 0.90), 0.35)
    m["wall"] = simple("SEP_Wall", (0.72, 0.72, 0.70), 0.55)
    m["wall_red"] = simple("SEP_WallRed", (0.55, 0.06, 0.05), 0.5)
    m["armco"] = simple("SEP_Armco", (0.62, 0.63, 0.66), 0.35, metallic=0.85)
    m["fence"] = simple("SEP_Fence", (0.18, 0.19, 0.21), 0.55, metallic=0.4)
    _make_transparent(m["fence"], 0.28)
    m["grandstand"] = simple("SEP_Grandstand", (0.30, 0.32, 0.36), 0.65)
    m["roof"] = simple("SEP_Roof", (0.80, 0.81, 0.83), 0.40, metallic=0.55)
    m["roof_petronas"] = simple("SEP_RoofPetronas", (0.03, 0.42, 0.36), 0.45)
    m["pit_building"] = simple("SEP_PitBuilding", (0.55, 0.56, 0.58), 0.5)
    m["glass"] = simple("SEP_Glass", (0.05, 0.09, 0.12), 0.12, metallic=0.6)
    m["gantry"] = simple("SEP_Gantry", (0.14, 0.14, 0.16), 0.45, metallic=0.7)
    m["led"] = simple("SEP_LED", (0.02, 0.02, 0.02), 0.3,
                      emission=(0.9, 0.15, 0.05), emission_strength=6.0)
    return m
