# Blender glTF Lightmap & Occlusion Baker

This script automates lightmap baking for glTF assets in **Blender 4.x.x** using **Python 3.4.x**.

It:

- Creates per-mesh lightmaps using Cycles.
- Generates a dedicated lightmap UV for each mesh without modifying existing UV maps.
- Bakes diffuse lighting only (no albedo color) into a PNG per object.
- Connects each baked image to the glTF occlusion channel via a `glTF Material Output` node group.
- Preserves existing materials and texture wrapping.

The result is a scene ready to export to **glTF/GLB** and use in engines such as Babylon.js or Three.js, with baked lighting stored as `occlusionTexture` while base color / albedo remains editable at runtime.

---

## Compatibility

- **Blender**: 4.x.x  
- **Python**: 3.4.x  
- **Render engine**: Cycles  
- **Addon**: `Import–Export: glTF 2.0 format` (enabled automatically by the script)

---

## Features

- Processes all mesh objects in the current scene in one run.
- Creates a new UV map per mesh for lightmaps (`LM_Lightmap` by default), leaving existing UVs untouched.
- Uses Cycles to bake diffuse lighting (with direct and indirect contributions) as a greyscale lightmap.
- Exports lightmaps as PNG files to a configurable directory.
- Creates or reuses a `glTF Material Output` node group and connects lightmaps to its `Occlusion` input.
- Enables the glTF 2.0 addon if needed.
- Logs progress (`Processing mesh X/Y`) and prints total elapsed time at the end.

---

## Configuration

At the top of the script there are configuration constants:

```python
LIGHTMAP_OUTPUT_DIR = "/tmp/lightmaps"
LIGHTMAP_IMG_SIZE = 256
LIGHTMAP_UVMAP_NAME = "LM_Lightmap"
LIGHTMAP_IMAGE_PREFIX = "LM_"
LIGHTMAP_SMART_ANGLE_LIMIT = 66
LIGHTMAP_SMART_ISLAND_MARGIN = 0.02
LIGHTMAP_BAKE_MARGIN = 4
LIGHTMAP_BAKE_USE_DIRECT = True
LIGHTMAP_BAKE_USE_INDIRECT = True
LIGHTMAP_BAKE_USE_COLOR = False


Overview of the most relevant ones:

- `LIGHTMAP_OUTPUT_DIR`  
  Directory where baked PNG files are written.

- `LIGHTMAP_IMG_SIZE`  
  Lightmap resolution (e.g. 256, 512, 1024, 2048). Higher values give better quality but increase bake time and memory.

- `LIGHTMAP_UVMAP_NAME`  
  Name of the UV map created for lightmaps. Blender may append `.001`, `.002`, etc. if the name already exists.

- `LIGHTMAP_IMAGE_PREFIX`  
  Prefix used in generated image names and filenames (`LM_<ObjectName>.png` by default).

- `LIGHTMAP_SMART_ANGLE_LIMIT`, `LIGHTMAP_SMART_ISLAND_MARGIN`  
  Parameters passed to Smart UV Project when creating the lightmap UV.

- `LIGHTMAP_BAKE_MARGIN`  
  Pixel margin for the bake to reduce visible seams.

- `LIGHTMAP_BAKE_USE_DIRECT`, `LIGHTMAP_BAKE_USE_INDIRECT`, `LIGHTMAP_BAKE_USE_COLOR`  
  Control which components are baked:
  - Direct lighting
  - Indirect lighting (global illumination)
  - Color (albedo).  
  By default color is disabled, so the resulting lightmap encodes only lighting intensity.

---
```

## Usage

### Basic usage from Blender

1. Open your `.blend` file in Blender 4.x.
2. Switch to the **Scripting** workspace.
3. In the **Text Editor**, create a new text block or open the script file.
4. Paste or load the full script.
5. Make sure the scene contains your meshes, materials and lights.
6. Press **Run Script**.

The script:

- Enables the glTF 2.0 addon (`io_scene_gltf2`).
- Bakes lightmaps for all mesh objects.
- Connects each baked lightmap to the glTF occlusion output.
- Prints per-mesh progress and total time at the end.



## How it Works
------------

### 1\. Enabling glTF 2.0

The function:

    enable_gltf_2()

calls `bpy.ops.preferences.addon_enable(module="io_scene_gltf2")` and saves user preferences. This ensures glTF export and the required node group support are available.

### 2\. Ensuring the `glTF Material Output` Node Group

`_ensure_gltf_material_output_group()`:

*   Searches for a node group named `glTF Material Output` in `bpy.data.node_groups`.
*   If it does not exist, creates a new `ShaderNodeTree` with a single `Occlusion` input socket.

The glTF exporter recognizes this node group by name and uses the texture connected to `Occlusion` as the `occlusionTexture`.

### 3\. Creating Lightmap UVs

For each mesh object, `_create_lightmap_uv(obj)`:

*   Ensures the object is active and in OBJECT mode.
*   If the mesh has no UV maps, creates a base `UVMap` and runs Smart UV Project on it.
*   Stores the name of the currently active UV map.
*   Creates a new UV map (default name `LM_Lightmap`).
*   Runs Smart UV Project only on that new UV map using the configured angle limit and island margin.
*   Restores the original active UV map.

This avoids modifying any UV map currently used by the materials.

### 4\. Baking Lightmaps

`_bake_lightmap_for_object(...)`:

*   Switches the scene render engine to Cycles.
*   Applies the configured bake settings (margin, direct/indirect/color).
*   Creates a new image for the object (`LM_<ObjectName>`), with the configured size, stored under `LIGHTMAP_OUTPUT_DIR`.
*   Ensures the mesh has at least one material.
*   Creates a temporary `Image Texture` node, assigns the lightmap image to it, and sets it as the active node.
*   Activates the lightmap UV on the mesh.
*   Calls `bpy.ops.object.bake(type='DIFFUSE')`.
*   Saves the image to disk.
*   Removes the temporary node and restores the original active UV.

The result is a greyscale lightmap per object, aligned with its lightmap UV.

### 5\. Connecting Lightmaps to glTF Occlusion

`_connect_lightmap_occlusion_for_object(...)`:

*   Iterates over materials assigned to the mesh.
*   If a material is shared across multiple objects (`mat.users > 1`), duplicates it so that wiring changes affect only the current object.
*   Ensures the material uses a node tree.
*   Finds or creates:
    *   A `UV Map` node pointing to the lightmap UV.
    *   An `Image Texture` node using the baked lightmap.
    *   A `glTF Material Output` group node using the node group created earlier.
*   Connects:
    *   `UV Map` → `Image Texture` (Vector input)
    *   `Image Texture` (Color output) → `glTF Material Output` (Occlusion input)

This setup is compatible with the glTF exporter’s interpretation of occlusion textures.

* * *

Exporting to glTF / GLB
-----------------------

After running the script:

1.  Inspect your materials in the Shader Editor:
    *   You should see a UV Map node referencing the lightmap UV.
    *   An Image Texture node using `LM_<ObjectName>.png`.
    *   A `glTF Material Output` group node with the Occlusion input connected.
2.  Export via **File → Export → glTF 2.0**.
3.  In the resulting `.gltf` / `.glb`:
    *   Materials will have an `occlusionTexture` using the baked lightmaps.
    *   The dedicated lightmap UV will be used as the occlusion UV set.

In the target engine (Babylon.js, Three.js, etc.) the occlusionTexture will behave as an AO/lightmap while base color can still be modified at runtime.

* * *

Notes and Limitations
---------------------

*   Designed for **Blender 4.x.x** and **Python 3.4.x**.
*   Uses Cycles for baking; Eevee is not supported by this script.
*   Baking many high-resolution maps can be slow and memory-heavy.
*   Smart UV Project is used for the lightmap UV layout. If you require custom unwrap or packing, you can adapt `_create_lightmap_uv`.
*   Shared materials are duplicated per object when connecting lightmaps. This avoids side effects between different objects but increases the number of material instances.

* * *


