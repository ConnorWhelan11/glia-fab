import bpy
import os
import sys

script_path = "/Users/connor/Medica/outora-library/blender/integrate_assets.py"

with open(script_path, 'r') as file:
    exec(file.read())

bpy.context.view_layer.update()
bpy.ops.wm.save_mainfile()

