"""
Sverchok layout helpers.

Creates a Sverchok node tree (SV_LIB_LAYOUT) with a Scripted Node Lite that emits
bay-point matrices on a 6m grid for instancing walls/windows/arches.

The tree is meant for development; a separate bake helper will convert outputs
into meshes under OL_GOTHIC_LAYOUT so end users are not dependent on Sverchok.

Usage (from Blender Scripting):
    import importlib, sverchok_layout
    importlib.reload(sverchok_layout)
    sverchok_layout.ensure_layout_tree()
"""

import bpy

TREE_NAME = "SV_LIB_LAYOUT"
SCRIPT_NODE_NAME = "SV_BayGrid"
MESH_VIEWER_NAME = "SV_Viewer"

# Bay and shape parameters (reusing our 6m cadence)
BAY_SIZE = 6.0
GRID_BAYS_X = 6  # 36m span
GRID_BAYS_Y = 6  # 36m span
ARM_LENGTH = 1  # bays to extend arms from the core
ATRIUM_CLEAR = 2  # bays cleared at the core


def ensure_tree():
    """Create or return the Sverchok tree."""
    tree = bpy.data.node_groups.get(TREE_NAME)
    if not tree:
        tree = bpy.data.node_groups.new(TREE_NAME, "SverchCustomTreeType")
    return tree


def ensure_script_node(tree):
    node = tree.nodes.get(SCRIPT_NODE_NAME)
    if not node:
        node = tree.nodes.new("SvScriptNodeLite")
        node.name = SCRIPT_NODE_NAME
        node.label = "Bay Grid Matrices"
    return node


def ensure_viewer_node(tree):
    node = tree.nodes.get(MESH_VIEWER_NAME)
    if not node:
        node = tree.nodes.new("SvMeshViewer")
        node.name = MESH_VIEWER_NAME
        node.label = "Viewer"
    return node


def wire_nodes(tree, script_node, viewer_node):
    tree.links.clear()
    out_socket = script_node.outputs[0] if script_node.outputs else None
    if out_socket and viewer_node.inputs:
        tree.links.new(out_socket, viewer_node.inputs[0])


def build_script(sn):
    """
    Inject a script that generates a 'Mega Library' layout:
    - Cross shape (Nave + Transept)
    - Central Crossing (24m x 24m)
    - Mezzanine level at +5m
    - Logic for placing walls, columns, arches, and furniture
    """
    sn.script_name = "sv_mega_library.py"
    code = f"""\"\"\"
in bay s d={BAY_SIZE} n=0
in wing_bays s d=3 n=0
in mezz_h s d=5.0 n=0
out floor_ground m
out floor_mezz m
out walls m
out walls_solid m
out walls_solid m
out windows m
out arches_main m
out arches_aisle m
out columns m
out railings m
out stairs m
out shelves m
out desks m
out heroes m
\"\"\"
import mathutils
from math import  pi

def sv_main(bay={BAY_SIZE}, wing_bays=3, mezz_h=5.0):
    bay = float(bay)
    wing_bays = int(wing_bays)
    mezz_h = float(mezz_h)

    # Crossing radius (bays). 24m crossing = 4 bays wide -> +/- 2 bays from center
    cross_r = 2 
    # Total extent
    limit = cross_r + wing_bays

    floor_ground = []
    floor_mezz = []
    walls = []
    walls_solid = []
    windows = []
    arches_main = []
    arches_aisle = []
    columns = []
    railings = []
    stairs = []
    shelves = []
    desks = []
    heroes = []

    # Helper to add matrix
    def add(lst, x, y, z=0.0, rot_z=0.0):
        mat = mathutils.Matrix.Translation((x, y, z))
        if rot_z != 0.0:
            mat = mat @ mathutils.Matrix.Rotation(rot_z, 4, 'Z')
        lst.append(mat)

    # Scan the grid
    # Range covers -limit to +limit (inclusive)
    rng = range(-limit, limit + 1)
    
    for i in rng:
        for j in rng:
            x = i * bay
            y = j * bay
            
            # Logic to define the shape
            in_cross_x = abs(i) <= cross_r
            in_cross_y = abs(j) <= cross_r
            
            # Nave (North/South) is width 2 bays (cols at +/- 1)?? 
            # Concept: Nave/Transept 8m clear. 
            # Let's define the "Void" as the central strip.
            # If we use grid lines for columns, let's say columns are at +/- 1 bay (6m) from axis?
            # That gives 12m width. A bit wide but okay for "Mega".
            # Let's stick to the concept: "Nave Axis... 8m wide". 
            # If bay is 6m, then columns at +/- 4m? No, we are locked to bay grid.
            # Let's put columns at +/- 1 bay (6m radius) -> 12m center path.
            
            # Active area: The Cross
            # We want a central crossing box, plus arms.
            # Arms width: let's say 3 bays wide (-1, 0, 1)
            is_arm_x = abs(j) <= 1
            is_arm_y = abs(i) <= 1
            
            in_shape = (abs(i) <= limit and is_arm_x) or (abs(j) <= limit and is_arm_y) or (in_cross_x and in_cross_y)
            
            if not in_shape:
                continue

            # GROUND FLOOR: Everywhere in shape
            add(floor_ground, x, y, 0.0)
            
            # MEZZANINE: Everywhere in shape EXCEPT the central void (Nave/Transept axis)
            # Void is abs(i)==0 or abs(j)==0 ? No, that's too thin.
            # Let's say void is the central 1x1 bay strip? Or purely the axis lines?
            # Concept: "Mezzanine ring at +5m... overlooking crossing"
            # Let's remove the central 1-bay-radius box from mezzanine in the crossing,
            # and the central axis strip in wings.
            is_void = (abs(i) < 1) or (abs(j) < 1)
            if not is_void:
                add(floor_mezz, x, y, mezz_h)
            
            # WALLS: Perimeter of the shape
            # Check neighbors to see if we are on edge
            # Simply: if abs(i)==limit (endpoints) or (abs(i)>cross_r and abs(j)==1) ...
            
            # Let's use a simpler geometric check for "Edge"
            # Edge if next neighbor is NOT in shape
            is_perimeter = False
            rot = 0.0
            
            # Simple bounds check for our specific shape
            # Wing Ends
            if i == limit and is_arm_x: # East End
                add(windows, x, y, mezz_h + 2, rot_z=-pi/2) # Clerestory/Apse
                add(walls, x, y, 0.0, rot_z=-pi/2)
                is_perimeter = True
            elif i == -limit and is_arm_x: # West End
                add(windows, x, y, mezz_h + 2, rot_z=pi/2)
                add(walls, x, y, 0.0, rot_z=pi/2)
                is_perimeter = True
            elif j == limit and is_arm_y: # North End
                add(windows, x, y, mezz_h + 2, rot_z=pi) # Apse High
                add(walls, x, y, 0.0, rot_z=pi)
                is_perimeter = True
            elif j == -limit and is_arm_y: # South End
                add(windows, x, y, mezz_h + 2, rot_z=0)
                add(walls, x, y, 0.0, rot_z=0)
                is_perimeter = True
            
            # Wing Sides
            # If we are in an arm (but not crossing) and on the side
            # Arm width is abs(j)<=1. So j=1 or j=-1 are edges? 
            # Wait, if arm is 3 wide (-1, 0, 1), then +/-1 are the edges.
            elif (abs(i) > cross_r and abs(j) == 1) or (abs(j) > cross_r and abs(i) == 1):
                 # Side walls
                 # Determine rotation based on normal
                 r = 0
                 if abs(i) > cross_r: # East/West wings
                     r = 0 if j == -1 else pi
                 else: # North/South wings
                     r = -pi/2 if i == -1 else pi/2
                 
                 add(walls, x, y, 0.0, rot_z=r)
                 add(windows, x, y, mezz_h + 1, rot_z=r) # Clerestory
            
            # COLUMNS: 
            # Internal structural grid.
            # Place columns at the corners of the "Void" (the nave line)
            if abs(i) == 1 and abs(j) == 1: # Corners of the crossing void
                 add(columns, x, y, 0.0)
                 add(columns, x, y, mezz_h)
            elif (abs(i) == 1 and abs(j) > 1) or (abs(j) == 1 and abs(i) > 1):
                 # Along the nave/transept
                 add(columns, x, y, 0.0)
                 add(columns, x, y, mezz_h)

            # ARCHES:
            # 1. Crossing Arches (Huge) - Spanning the 2-bay void at the crossing edge
            # Located at +/- 2 bays? 
            # Concept: "Four colossal arches frame each cardinal wing"
            # These sit at the transition from Crossing to Wing.
            if (abs(i) == cross_r and abs(j) < 1): # East/West entry to crossing
                 # Span is Y direction? No, span is across the opening (Y axis)
                 # Actually Arch sits ON the point?
                 # Let's place arch at (cross_r, 0) facing inwards
                 # But our grid points are integers.
                 pass 
            
            # RAILINGS:
            # Along the void edge on Mezzanine
            if not is_void:
                # Check if neighbor towards center is void
                # Simple logic: if we are at abs() == 1
                if abs(i) == 1 and abs(j) >= 1:
                    # Facing X axis center
                    r = -pi/2 if i == -1 else pi/2
                    add(railings, x, y, mezz_h, rot_z=r)
                if abs(j) == 1 and abs(i) >= 1:
                    # Facing Y axis center
                    r = 0 if j == -1 else pi
                    add(railings, x, y, mezz_h, rot_z=r)

            # SHELVES:
            # Ground floor, in the side aisles (not void, not perimeter?)
            # Aisle is abs(i/j) == 1? No that's the column line.
            # If arm is 3 wide (-1, 0, 1), columns are at +/-1.
            # So the aisle is... wait.
            # If columns are at +/-1, and walls are at +/-1... there is no aisle!
            # We need to make the wings wider or the void narrower.
            # Let's make wings 5 wide (-2, -1, 0, 1, 2).
            # Columns at +/- 1 (defining 12m nave).
            # Aisle at +/- 2. Walls at +/- 2 edge?
            # Redoing shape logic slightly for "Wider Wings".
            
    # --- RESTART LOOP FOR WIDER WINGS (5 wide) ---
    pass # We will rely on the simpler loop below for the final string

    return floor_ground, floor_mezz, walls, windows, arches_main, arches_aisle, columns, railings, stairs, shelves, heroes

def sv_main_actual(bay={BAY_SIZE}, wing_bays=3, mezz_h=5.0):
    # WIDER WINGS LOGIC
    # Width = 5 bays (-2 to 2). Center 0 is void. +/- 1 are columns. +/- 2 are aisles/walls.
    
    bay = float(bay)
    wing_bays = int(wing_bays)
    mezz_h = float(mezz_h)

    cross_r = 2 # Crossing is still +/- 2 box
    limit = cross_r + wing_bays

    floor_ground = []
    floor_mezz = []
    walls = []
    walls_solid = []
    windows = []
    arches_main = []
    arches_aisle = []
    columns = []
    railings = []
    stairs = []
    shelves = []
    heroes = []

    def add(lst, x, y, z=0.0, rot_z=0.0):
        mat = mathutils.Matrix.Translation((x, y, z))
        if rot_z != 0.0:
            mat = mat @ mathutils.Matrix.Rotation(rot_z, 4, 'Z')
        lst.append(mat)

    rng = range(-limit, limit + 1)
    
    for i in rng:
        for j in rng:
            x = i * bay
            y = j * bay
            
            # Define Areas
            abs_i = abs(i)
            abs_j = abs(j)
            
            # Crossing Box
            in_crossing = (abs_i <= cross_r and abs_j <= cross_r)
            
            # Wings (extended axes) - now 5 bays wide (-2..2)
            in_wing_x = (abs_j <= 2 and abs_i <= limit)
            in_wing_y = (abs_i <= 2 and abs_j <= limit)
            
            if not (in_crossing or in_wing_x or in_wing_y):
                continue

            # Center Void (Nave)
            is_void = (abs_i == 0) or (abs_j == 0)
            # Wait, purely axial?
            # If we want a clear nave of 1 bay width? Let's say index 0 is clear.
            
            # FLOOR
            add(floor_ground, x, y, 0.0)
            
            if not is_void:
                add(floor_mezz, x, y, mezz_h)
            
            # WALLS (Perimeter at +/- 2)
            # Check if this node is an outer edge of the layout
            # Ends
            is_end = False
            if i == limit and abs_j <= 2: # East End
                add(walls, x, y, 0.0, -pi/2)
                add(windows, x, y, mezz_h + 2, -pi/2) # Apse
                is_end = True
            elif i == -limit and abs_j <= 2: # West
                add(walls, x, y, 0.0, pi/2)
                add(windows, x, y, mezz_h + 2, pi/2)
                is_end = True
            elif j == limit and abs_i <= 2: # North
                add(walls, x, y, 0.0, pi)
                add(windows, x, y, mezz_h + 2, pi)
                is_end = True
            elif j == -limit and abs_i <= 2: # South
                add(walls, x, y, 0.0, 0)
                add(windows, x, y, mezz_h + 2, 0)
                is_end = True
                
            # Side Walls (at +/- 2, excluding crossing/corners if open?)
            # For now, simplified: wrap the whole 5-bay width.
            if not is_end:
                if abs_j == 2 and not in_crossing: # Wing Sides X-axis
                    r = 0 if j == -2 else pi
                    add(walls_solid, x, y, 0.0, r)
                    # add(windows, x, y, 1.5, r) # Ground windows - REMOVED for solid shelf backing
                    add(windows, x, y, mezz_h + 1.5, r) # Clerestory
                    
                    # Shelves against the wall
                    add(shelves, x, y, 0.0, r + pi) # Face inward
                    
                    # Desks in the aisle (offset towards center)
                    # Wall is at +/- 2*bay (12m). Column at +/- 1*bay (6m).
                    # Place desk at +/- 1.5*bay (9m)
                    desk_y = y - (0.5 * bay if j == 2 else -0.5 * bay)
                    add(desks, x, desk_y, 0.0, r + pi) # Face inward

                if abs_i == 2 and not in_crossing: # Wing Sides Y-axis
                    r = -pi/2 if i == -2 else pi/2
                    add(walls_solid, x, y, 0.0, r)
                    # add(windows, x, y, 1.5, r) # Ground windows - REMOVED for solid shelf backing
                    add(windows, x, y, mezz_h + 1.5, r)
                    
                    add(shelves, x, y, 0.0, r + pi)
                    
                    # Desks in the aisle
                    desk_x = x - (0.5 * bay if i == 2 else -0.5 * bay)
                    add(desks, desk_x, y, 0.0, r + pi)

            # COLUMNS (at +/- 1)
            is_col_line = (abs_i == 1) or (abs_j == 1)
            # Avoid placing columns inside the very center of crossing?
            # Let's place them everywhere on the 1-line except the very center 0,0
            if is_col_line:
                # If inside crossing, we want the 4 corners of the nave intersection
                if in_crossing:
                    if abs_i == 1 and abs_j == 1: # The 4 grand pillars
                        add(columns, x, y, 0.0)
                        add(columns, x, y, mezz_h)
                else:
                    # In wings
                    if (in_wing_x and abs_j == 1) or (in_wing_y and abs_i == 1):
                         add(columns, x, y, 0.0)
                         add(columns, x, y, mezz_h)
                         
            # RAILINGS (Edge of Mezzanine, facing void)
            # At +/- 1, facing 0
            if abs_j == 1 and not is_void: # Inner edge of X-wing
                 r = pi if j == 1 else 0 # Face towards 0
                 add(railings, x, y, mezz_h, r)
            if abs_i == 1 and not is_void:
                 r = pi/2 if i == 1 else -pi/2
                 add(railings, x, y, mezz_h, r)
                 
    # SPECIAL FEATURES
    
    # Crossing Arches (The 4 big ones)
    # Located at +/- 2 on the axes?
    # Let's place them at (cross_r, 0) etc.
    # East Arch
    add(arches_main, cross_r * bay, 0, 0, -pi/2)
    # West Arch
    add(arches_main, -cross_r * bay, 0, 0, pi/2)
    # North
    add(arches_main, 0, cross_r * bay, 0, pi)
    # South
    add(arches_main, 0, -cross_r * bay, 0, 0)
    
    # Stairs (In the crossing corners, 1,1 is column... maybe 1.5, 1.5?)
    # Let's place them at (+/- 1.5, +/- 1.5) * bay? No, matrix needs integer grid usually for snapping
    # or we just emit the float.
    # Let's put stairs at (+/- 1, +/- 1) rotated? But columns are there.
    # Put stairs in the diagonal of crossing? 
    # Let's place them at (+/- 1, +/- 2) ?
    # Lets put them in the corners of the crossing area (1,1 is occupied).
    # Maybe (2, 2)? That's the corner of the crossing box.
    add(stairs, 1.5 * bay, 1.5 * bay, 0, -3*pi/4)
    add(stairs, -1.5 * bay, 1.5 * bay, 0, 3*pi/4)
    add(stairs, 1.5 * bay, -1.5 * bay, 0, -pi/4)
    add(stairs, -1.5 * bay, -1.5 * bay, 0, pi/4)

    # Hero
    add(heroes, 0, 0, mezz_h + 4.0) # Chandelier high up

    return floor_ground, floor_mezz, walls, walls_solid, windows, arches_main, arches_aisle, columns, railings, stairs, shelves, desks, heroes

# Bind to sv_main for execution
sv_main = sv_main_actual

floor_ground, floor_mezz, walls, walls_solid, windows, arches_main, arches_aisle, columns, railings, stairs, shelves, desks, heroes = sv_main(bay, wing_bays, mezz_h)
"""
    sn.script_str = code


def ensure_layout_tree():
    tree = ensure_tree()
    sn = ensure_script_node(tree)
    viewer = ensure_viewer_node(tree)
    build_script(sn)
    # Force socket creation/execution so outputs exist
    try:
        sn.update_sockets()
    except Exception:
        ...
    try:
        sn.process()
    except Exception:
        pass
    wire_nodes(tree, sn, viewer)
    print(f"Sverchok tree '{TREE_NAME}' ready with Scripted Node Lite")
    return tree


if __name__ == "__main__":
    ensure_layout_tree()
