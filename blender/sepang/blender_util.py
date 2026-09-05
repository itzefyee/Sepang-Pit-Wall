"""Small Blender helpers shared by the Sepang scene builders."""

import bpy
import bmesh
import math


def get_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def clear_collection(name):
    """Delete a collection and everything in it (rebuilds stay idempotent)."""
    col = bpy.data.collections.get(name)
    if col is None:
        return
    for ob in list(col.objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)
    for child in list(col.children):
        clear_collection(child.name)
    bpy.data.collections.remove(col)


def make_mesh(name, verts, faces, collection, materials=None,
              mat_indices=None, face_uvs=None, shade_smooth=False):
    """
    verts: [(x,y,z)]  faces: [(i,j,k[,l])]
    materials: list of bpy materials; mat_indices: per-face index into it
    face_uvs: per-face list of (u,v) matching that face's vertex order
    """
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate(verbose=False)

    if materials:
        for m in materials:
            me.materials.append(m)
        if mat_indices:
            for poly, mi in zip(me.polygons, mat_indices):
                poly.material_index = mi

    if face_uvs:
        uvl = me.uv_layers.new(name="UVMap")
        for poly, fuv in zip(me.polygons, face_uvs):
            for k, li in enumerate(poly.loop_indices):
                uvl.data[li].uv = fuv[k]

    if shade_smooth:
        for poly in me.polygons:
            poly.use_smooth = True

    me.update()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


def box(name, size, location, collection, material=None, rotation_z=0.0):
    sx, sy, sz = size
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    ob.rotation_euler = (0.0, 0.0, rotation_z)
    if material:
        me.materials.append(material)
    collection.objects.link(ob)
    return ob


def cylinder(name, radius, depth, location, collection, material=None,
             segments=16, rotation=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=radius, radius2=radius, depth=depth)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    ob.rotation_euler = rotation
    if material:
        me.materials.append(material)
    collection.objects.link(ob)
    return ob


def join(objects, name=None):
    """Join a list of mesh objects into the first one."""
    objects = [o for o in objects if o and o.type == 'MESH']
    if len(objects) < 2:
        return objects[0] if objects else None
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    if name:
        ob.name = name
    return ob


def smooth_closed(vals, sigma):
    if sigma <= 0:
        return list(vals)
    r = max(1, int(math.ceil(sigma * 3)))
    k = [math.exp(-0.5 * (d / sigma) ** 2) for d in range(-r, r + 1)]
    s = sum(k)
    k = [x / s for x in k]
    n = len(vals)
    return [sum(vals[(i + j - r) % n] * kk for j, kk in enumerate(k)) for i in range(n)]
