import bpy
import os
import time


# ============================================
#   Activate glTF 2.0 addon
# ============================================

def enable_gltf_2():
    bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    bpy.ops.wm.save_userpref()


# ============================================
#   Ensure node group glTF Material Output (Blender 4.x)
# ============================================

def _ensure_gltf_material_output_group():
    """
    Returns a NodeGroup named 'glTF Material Output'.
    If it doesn't exist, it creates it with an 'Occlusion' input in the interface.
    """
    for ng in bpy.data.node_groups:
        if ng.name == "glTF Material Output":
            return ng

    ng = bpy.data.node_groups.new("glTF Material Output", 'ShaderNodeTree')

    iface = ng.interface
    iface.new_socket(
        name="Occlusion",
        in_out='INPUT',
        socket_type="NodeSocketColor"
    )

    return ng


# ============================================
# 1) Create lightmap UVs WITHOUT touching the existing UVs
# ============================================

def _create_lightmap_uv(obj, uvmap_name="LM_Lightmap"):
    """
    - Does NOT apply transformations.
    - ALWAYS creates a new UV map (doesn't reuse any).
    - Runs Smart UV Project on that UV map.
    - Returns:
        - name of the original active UV map
        - name of the created lightmap UV map
    """
    if obj.type != 'MESH':
        return None, None

    mesh = obj.data

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    if not mesh.uv_layers:
        base = mesh.uv_layers.new(name="UVMap")
        mesh.uv_layers.active = base

        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.02)
        bpy.ops.object.mode_set(mode='OBJECT')

    original_uv = mesh.uv_layers.active
    original_uv_name = original_uv.name

    lm_uv = mesh.uv_layers.new(name=uvmap_name)
    lm_uv_name = lm_uv.name 

    mesh.uv_layers.active = lm_uv
    if hasattr(lm_uv, "active_render"):
        lm_uv.active_render = False 

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')

    mesh.uv_layers.active = mesh.uv_layers[original_uv_name]

    return original_uv_name, lm_uv_name


# ============================================
# 2) BAKE on the lightmap UV
# ============================================

def _bake_lightmap_for_object(obj, output_dir, img_size, image_prefix, uvmap_name="LM_Lightmap"):
    """
    - Creates a new lightmap UV.
    - Bakes diffuse lighting (without color) using that UV.
    - Returns the lightmap Image and the name of the lightmap UV.
    """
    scene = bpy.context.scene

    if obj.type != 'MESH':
        return None, None

    mesh = obj.data

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    original_uv_name, lm_uv_name = _create_lightmap_uv(obj, uvmap_name=uvmap_name)
    if lm_uv_name is None:
        print(f"❌ Couldn't create lightmap UV for {obj.name}.")
        return None, None

    # Ajustes de bake
    scene.render.engine = 'CYCLES'
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.margin = 4
    scene.render.bake.use_clear = True
    scene.render.bake.use_pass_direct = True
    scene.render.bake.use_pass_indirect = True
    scene.render.bake.use_pass_color = False 

    os.makedirs(output_dir, exist_ok=True)

    base_name = f"{image_prefix}{obj.name}"

    if base_name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[base_name])

    img = bpy.data.images.new(
        base_name,
        width=img_size,
        height=img_size,
        alpha=False,
        float_buffer=False
    )
    img.colorspace_settings.name = 'Non-Color'

    safe_file = "".join(c if c.isalnum() or c in "._-" else "_" for c in base_name)
    img.file_format = 'PNG'
    img.filepath_raw = os.path.join(output_dir, safe_file + ".png")

    print(f"\n=== BAKE LIGHTMAP FOR: {obj.name} ===")
    print(f"  Image: {img.name} -> {img.filepath_raw}")
    print(f"  Lightmap UV: {lm_uv_name}")


    if not mesh.materials:
        mat = bpy.data.materials.new(obj.name + "_TempBakeMat")
        mat.use_nodes = True
        mesh.materials.append(mat)

    if obj.active_material is None:
        obj.active_material_index = 0

    mat = obj.active_material
    mat.use_nodes = True
    nt = mat.node_tree

    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.label = "BAKE_TARGET"

    for n in nt.nodes:
        n.select = False
    tex.select = True
    nt.nodes.active = tex

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    mesh.uv_layers.active = mesh.uv_layers[lm_uv_name]
    
    print("  Baking (DIFFUSE, no color, lightmap UV)...")
    bpy.ops.object.bake(type='DIFFUSE')

    img.save()
    print("  ✅ Saved:", img.filepath_raw)

    nt.nodes.remove(tex)
    mesh.uv_layers.active = mesh.uv_layers[original_uv_name]

    return img, lm_uv_name


# ============================================
# 3) Connect lightmap to glTF Occlusion using the lightmap UV
# ============================================

def _connect_lightmap_occlusion_for_object(obj, lm_image, gltf_group, lm_uv_name):
    """
    Connect lm_image as Occlusion in the glTF Material Output of all the object's materials,
    using the lm_uv_name UV (through a UV Map node → Image Texture node → glTF Occlusion).
    """
    if obj.type != 'MESH':
        return

    mesh = obj.data
    print(f"\n=== CONNECT {lm_image.name} AS OCCLUSION IN: {obj.name} (UV '{lm_uv_name}') ===")

    for slot_idx, mat in enumerate(mesh.materials):
        if mat is None:
            continue

        if mat.users > 1:
            new_mat = mat.copy()
            new_mat.name = f"{mat.name}_{obj.name}"
            mesh.materials[slot_idx] = new_mat
            mat = new_mat
            print(f"  Cloned shared material -> {mat.name}")

        mat.use_nodes = True
        nt = mat.node_tree

        tex_node = None
        for n in nt.nodes:
            if n.type == 'TEX_IMAGE' and n.image == lm_image:
                tex_node = n
                break

        if tex_node is None:
            tex_node = nt.nodes.new("ShaderNodeTexImage")
            tex_node.label = "LM_Occlusion"
            tex_node.interpolation = 'Smart'

        tex_node.image = lm_image
        tex_node.image.colorspace_settings.name = "Non-Color"

        uv_node = None
        for n in nt.nodes:
            if n.type == 'UVMAP' and getattr(n, "uv_map", "") == lm_uv_name:
                uv_node = n
                break

        if uv_node is None:
            uv_node = nt.nodes.new("ShaderNodeUVMap")
            uv_node.uv_map = lm_uv_name
            uv_node.label = "UV_Lightmap"

        if "Vector" in tex_node.inputs:
            for link in list(tex_node.inputs["Vector"].links):
                nt.links.remove(link)
            nt.links.new(uv_node.outputs["UV"], tex_node.inputs["Vector"])

        gltf_node = None
        for n in nt.nodes:
            if n.type == 'GROUP' and n.node_tree == gltf_group:
                gltf_node = n
                break

        if gltf_node is None:
            gltf_node = nt.nodes.new("ShaderNodeGroup")
            gltf_node.node_tree = gltf_group
            gltf_node.label = "glTF Material Output"

        occ_input = None
        for inp in gltf_node.inputs:
            if inp.name.lower() == "occlusion":
                occ_input = inp
                break

        if occ_input is None:
            print(f"  ⚠ The glTF group of {mat.name} has no 'Occlusion' input. Skipping.")
            continue

        for link in list(occ_input.links):
            nt.links.remove(link)
        nt.links.new(tex_node.outputs["Color"], occ_input)

        print(f"  [ {mat.name} ] -> {lm_image.name} connected to Occlusion with UV '{lm_uv_name}'.")

    print("  ✅ Occlusion configured for", obj.name)


# ============================================
# 4) PUBLIC API: ALL MESHES
# ============================================

def bake_and_connect_lightmap_occlusion_all_safe(
    output_dir="/tmp/lightmaps",
    img_size=256,
    uvmap_name="LM_Lightmap",
    image_prefix="LM_",
):
    """
    For ALL meshes in the scene:
      - Create a new lightmap UV (do not modify existing ones).
      - Bake diffuse light (no color) to LM_<obj>.png using that UV.
      - Connect that LM_ to Occlusion of the glTF Material Output using that UV.
      - Do NOT modify the UVs already used by the materials.
    """
    scene = bpy.context.scene
    gltf_group = _ensure_gltf_material_output_group()

    meshes = [o for o in scene.objects if o.type == 'MESH']
    total = len(meshes)

    print(f"\n=== BAKE + OCCLUSION (SAFE) FOR ALL MESHES ({total} Objects) ===")

    for idx, obj in enumerate(meshes, start=1):
        print(f"\n--- Processing mesh {idx}/{total}: {obj.name} ---")

        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        lm_img, lm_uv_name = _bake_lightmap_for_object(
            obj,
            output_dir=output_dir,
            img_size=img_size,
            image_prefix=image_prefix,
            uvmap_name=uvmap_name,
        )
        if lm_img is None or lm_uv_name is None:
            continue

        _connect_lightmap_occlusion_for_object(
            obj,
            lm_img,
            gltf_group,
            lm_uv_name=lm_uv_name,
        )

    print("\n✅ Process completed for all meshes (without breaking existing textures).")


def main():
    start_time = time.time()

    try:
        enable_gltf_2()

        print("\n▶ Starting bake + lightmaps...")
        bake_and_connect_lightmap_occlusion_all_safe()

    except Exception as e:
        print("\n❌ ERROR during bake lightmaps:")
        print(repr(e))

    finally:
        elapsed = time.time() - start_time
        mins, secs = divmod(int(elapsed), 60)
        print(f"\n⏱ Total time: {mins} min {secs} s ({elapsed:.1f} s).")


main()
