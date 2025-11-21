# Blender glTF Lightmap & Occlusion Baker

This script automates **lightmap baking for glTF assets** in **Blender 4.x**:

- Creates **per-mesh lightmaps** using Cycles.
- Generates a **dedicated lightmap UV** for each mesh (without touching existing UVs).
- Bakes **diffuse lighting only (no albedo color)** to a PNG image per object.
- Wires each baked image into the **glTF occlusion channel** via a `glTF Material Output` node group.
- Keeps existing materials and texture wrapping **intact**.

The result is a scene that can be exported to **glTF/GLB** and used in engines like **Babylon.js**, **Three.js**, etc., with baked lighting encoded as `occlusionTexture`, while still allowing you to change base color / albedo at runtime.

---

## Features

- ✅ Processes **all mesh objects** in the current scene.
- ✅ Creates a **new UV map** per mesh for lightmaps (`LM_Lightmap` by default), without modifying existing UVs.
- ✅ Uses **Cycles** to bake diffuse lighting **without color** (pure lighting intensity).
- ✅ Exports lightmaps as **PNG files** to a configurable output directory.
- ✅ Automatically creates/uses a `glTF Material Output` node group and connects lightmaps to its **`Occlusion`** input.
- ✅ Automatically enables the **glTF 2.0 addon** if needed.
- ✅ Logs progress (`Processing mesh X/Y`) and **total elapsed time** at the end.

---

## Requirements

- **Blender**: 4.x (uses the new `node_tree.interface` API).
- **Render Engine**: Cycles (the script switches the scene render engine to `CYCLES`).
- **Addon**: `Import–Export: glTF 2.0 format`  
  The script calls `enable_gltf_2()` internally to ensure it is enabled.

---

## Installation

You can use the script in two common ways:

### Option 1: Paste into the Text Editor (quick usage)

1. Open your `.blend` file in **Blender**.
2. Switch to the **Scripting** workspace.
3. Create a new text block in the **Text Editor**.
4. Paste the entire script into the editor.
5. Press **`Run Script`**.

This will:

- Enable the glTF 2.0 addon (if not already enabled).
- Bake lightmaps for all meshes.
- Wire them into the glTF occlusion output.
- Print logs and total time in the system console / Blender console.

### Option 2: Add it to your repo and load in Blender

1. Save the script as something like:

   ```text
   blender_gltf_lightmap_baker.py
