"""
Sverchok Layout V2 - Hyper-Realistic Gothic Library

Architectural principles based on real Gothic cathedrals (Notre Dame, Chartres):
- Bay system: 6m structural modules
- Nave proportions: 1:2 width:height ratio
- Proper structural hierarchy: main piers → arcade → infill
- Clerestory/triforium/arcade vertical zoning
- Realistic buttress rhythm

Usage:
    import importlib, sverchok_layout_v2 as sv2
    importlib.reload(sv2)
    sv2.ensure_layout_tree()
"""

import bpy
from math import pi, sqrt
from typing import List, Tuple, Dict, Any
import mathutils

# =============================================================================
# ARCHITECTURAL CONSTANTS (Based on Gothic Proportions)
# =============================================================================

# Bay module - the fundamental unit (like Notre Dame's ~5-6m bays)
BAY = 6.0

# Plan dimensions (in bays)
CROSSING_BAYS = 4          # 24m x 24m crossing (4x4 bays)
NAVE_WIDTH_BAYS = 2        # 12m clear nave width
AISLE_WIDTH_BAYS = 1       # 6m aisles on each side
WING_LENGTH_BAYS = 4       # 24m deep wings beyond crossing

# Vertical dimensions (meters)
GROUND_LEVEL = 0.0
ARCADE_HEIGHT = 6.0        # Main arcade arches
TRIFORIUM_LEVEL = 5.0      # Gallery/mezzanine floor level
TRIFORIUM_HEIGHT = 2.5     # Triforium zone height
CLERESTORY_BASE = 8.0      # Where clerestory windows start
VAULT_SPRING = 10.0        # Where vaults spring from
VAULT_CREST = 14.0         # Crown of the vault
OCULUS_HEIGHT = 16.0       # Central oculus opening

# Structural element dimensions
MAIN_PIER_RADIUS = 0.8     # Clustered pier base radius
ARCADE_COLUMN_RADIUS = 0.4 # Smaller arcade columns
BUTTRESS_DEPTH = 1.2       # External buttress projection
BUTTRESS_WIDTH = 0.8       # Buttress width
WALL_THICKNESS = 0.6       # Wall thickness
ARCH_THICKNESS = 0.5       # Arch rib thickness

# Mezzanine/Triforium
MEZZANINE_DEPTH = 4.0      # How far mezzanine extends from walls
BALUSTRADE_HEIGHT = 1.1    # Railing height
BEAM_WIDTH = 0.3           # Underslung beam width
BEAM_DEPTH = 0.4           # Underslung beam depth

# Window proportions (Gothic lancets are tall and narrow)
LANCET_WIDTH = 1.2         # Narrow lancet windows
LANCET_HEIGHT_RATIO = 3.5  # Height = width * ratio
ROSE_WINDOW_RADIUS = 3.0   # Large rose windows at wing ends

# =============================================================================
# TREE AND NODE MANAGEMENT
# =============================================================================

TREE_NAME = "SV_LIB_LAYOUT_V2"
SCRIPT_NODE_NAME = "SV_GothicLayout"


def ensure_tree():
    """Create or return the Sverchok tree."""
    tree = bpy.data.node_groups.get(TREE_NAME)
    if not tree:
        tree = bpy.data.node_groups.new(TREE_NAME, "SverchCustomTreeType")
    return tree


def ensure_script_node(tree):
    """Create or return the script node."""
    node = tree.nodes.get(SCRIPT_NODE_NAME)
    if not node:
        node = tree.nodes.new("SvScriptNodeLite")
        node.name = SCRIPT_NODE_NAME
        node.label = "Gothic Library Layout V2"
    return node


# =============================================================================
# LAYOUT GENERATION LOGIC
# =============================================================================

class GothicLayoutGenerator:
    """
    Generates placement matrices for a Gothic library following
    proper architectural principles.
    """
    
    def __init__(self, 
                 bay: float = BAY,
                 crossing_bays: int = CROSSING_BAYS,
                 nave_width_bays: int = NAVE_WIDTH_BAYS,
                 aisle_width_bays: int = AISLE_WIDTH_BAYS,
                 wing_length_bays: int = WING_LENGTH_BAYS):
        
        self.bay = bay
        self.crossing_bays = crossing_bays
        self.nave_width_bays = nave_width_bays
        self.aisle_width_bays = aisle_width_bays
        self.wing_length_bays = wing_length_bays
        
        # Derived dimensions
        self.half_crossing = (crossing_bays * bay) / 2  # 12m
        self.nave_half_width = (nave_width_bays * bay) / 2  # 6m
        self.total_wing_width = (nave_width_bays + 2 * aisle_width_bays) * bay  # 24m
        self.wing_extent = self.half_crossing + wing_length_bays * bay  # 36m from center
        
        # Output lists
        self.reset_outputs()
    
    def reset_outputs(self):
        """Reset all output lists."""
        # Structural
        self.main_piers = []           # Large clustered piers at bay intersections
        self.arcade_columns = []        # Smaller columns in arcades
        self.buttresses = []            # External buttresses
        
        # Arches
        self.crossing_arches = []       # The 4 great arches at crossing
        self.nave_arches = []           # Main nave arcade arches
        self.aisle_arches = []          # Smaller aisle arches
        self.transverse_ribs = []       # Vault transverse ribs
        
        # Walls
        self.exterior_walls = []        # Outer walls
        self.clerestory_walls = []      # Upper walls with windows
        self.apse_walls = []            # Focal end walls
        
        # Windows
        self.lancet_windows_ground = [] # Ground floor lancets
        self.lancet_windows_clerestory = []  # Clerestory lancets
        self.rose_windows = []          # Rose windows at wing ends
        self.oculus = []                # Central oculus
        
        # Floors
        self.ground_floor = []          # Main floor tiles
        self.mezzanine_floor = []       # Gallery floor
        self.mezzanine_beams = []       # Underslung support beams
        
        # Railings
        self.balustrades = []           # Mezzanine railings
        
        # Circulation
        self.grand_stairs = []          # Main stairs at crossing corners
        self.spiral_stairs = []         # Service stairs in corners
        
        # Furniture zones (matrices for placing furniture groups)
        self.study_pod_positions = []   # Where study pods go
        self.shelf_wall_positions = []  # Wall-mounted shelf positions
        self.reading_alcove_positions = []  # Reading nook positions
        
        # Decorative
        self.statue_positions = []      # Guardian statues
        self.chandelier_positions = []  # Lighting fixtures
        self.plinth_positions = []      # Statue bases
    
    def mat(self, x: float, y: float, z: float = 0.0, rot_z: float = 0.0, 
            scale: float = 1.0) -> mathutils.Matrix:
        """Create a transformation matrix."""
        mat = mathutils.Matrix.Translation((x, y, z))
        if rot_z != 0.0:
            mat = mat @ mathutils.Matrix.Rotation(rot_z, 4, 'Z')
        if scale != 1.0:
            mat = mat @ mathutils.Matrix.Scale(scale, 4)
        return mat
    
    def is_in_plan(self, bx: int, by: int) -> bool:
        """
        Check if a bay coordinate is within the cruciform plan.
        Plan is a cross shape: central crossing + 4 arms.
        """
        # Crossing zone
        if abs(bx) <= self.crossing_bays // 2 and abs(by) <= self.crossing_bays // 2:
            return True
        
        # North/South wings (along Y axis)
        wing_half_width = self.nave_width_bays // 2 + self.aisle_width_bays
        if abs(bx) <= wing_half_width and abs(by) <= self.crossing_bays // 2 + self.wing_length_bays:
            return True
        
        # East/West wings (along X axis)
        if abs(by) <= wing_half_width and abs(bx) <= self.crossing_bays // 2 + self.wing_length_bays:
            return True
        
        return False
    
    def get_zone(self, bx: int, by: int) -> str:
        """Determine which architectural zone a bay belongs to."""
        half_cross = self.crossing_bays // 2
        wing_half = self.nave_width_bays // 2 + self.aisle_width_bays
        
        # Crossing (central hub)
        if abs(bx) <= half_cross and abs(by) <= half_cross:
            if abs(bx) <= self.nave_width_bays // 2 and abs(by) <= self.nave_width_bays // 2:
                return "crossing_nave"  # The open void
            else:
                return "crossing_aisle"
        
        # Wing terminations (apse-like ends)
        max_extent = half_cross + self.wing_length_bays
        if abs(bx) == max_extent and abs(by) <= wing_half:
            return "apse_x"
        if abs(by) == max_extent and abs(bx) <= wing_half:
            return "apse_y"
        
        # Wings
        if abs(by) > half_cross:
            if abs(bx) <= self.nave_width_bays // 2:
                return "nave_y"  # Main nave in Y direction
            else:
                return "aisle_y"  # Side aisles in Y direction
        
        if abs(bx) > half_cross:
            if abs(by) <= self.nave_width_bays // 2:
                return "nave_x"  # Main nave in X direction
            else:
                return "aisle_x"  # Side aisles in X direction
        
        return "unknown"
    
    def is_on_nave_axis(self, bx: int, by: int) -> bool:
        """Check if position is on the main nave/transept axes."""
        return abs(bx) <= self.nave_width_bays // 2 or abs(by) <= self.nave_width_bays // 2
    
    def is_exterior_edge(self, bx: int, by: int) -> Tuple[bool, float]:
        """
        Check if a bay is on the exterior edge.
        Returns (is_edge, outward_rotation).
        """
        wing_half = self.nave_width_bays // 2 + self.aisle_width_bays
        max_extent = self.crossing_bays // 2 + self.wing_length_bays
        
        # Wing ends
        if bx == max_extent and abs(by) <= wing_half:
            return True, -pi/2  # East end
        if bx == -max_extent and abs(by) <= wing_half:
            return True, pi/2   # West end
        if by == max_extent and abs(bx) <= wing_half:
            return True, pi     # North end
        if by == -max_extent and abs(bx) <= wing_half:
            return True, 0      # South end
        
        # Wing sides
        half_cross = self.crossing_bays // 2
        
        # Y-wing sides
        if abs(by) > half_cross and abs(bx) == wing_half:
            if bx > 0:
                return True, -pi/2
            else:
                return True, pi/2
        
        # X-wing sides
        if abs(bx) > half_cross and abs(by) == wing_half:
            if by > 0:
                return True, pi
            else:
                return True, 0
        
        return False, 0.0
    
    def generate(self):
        """Generate the complete layout."""
        self.reset_outputs()
        
        # Define bay ranges
        max_extent = self.crossing_bays // 2 + self.wing_length_bays
        
        # =================================================================
        # PASS 1: Structural Grid (Piers, Columns)
        # =================================================================
        for bx in range(-max_extent, max_extent + 1):
            for by in range(-max_extent, max_extent + 1):
                if not self.is_in_plan(bx, by):
                    continue
                
                x = bx * self.bay
                y = by * self.bay
                zone = self.get_zone(bx, by)
                
                # Main piers at structural intersections
                is_main_pier_line_x = abs(bx) == self.nave_width_bays // 2 + 1
                is_main_pier_line_y = abs(by) == self.nave_width_bays // 2 + 1
                
                # The 4 great crossing piers
                if abs(bx) == 1 and abs(by) == 1:
                    self.main_piers.append(self.mat(x, y, 0, scale=1.5))
                    self.main_piers.append(self.mat(x, y, TRIFORIUM_LEVEL, scale=1.2))
                
                # Pier lines along nave edges
                elif (is_main_pier_line_x or is_main_pier_line_y) and self.is_in_plan(bx, by):
                    if zone not in ["crossing_nave", "nave_x", "nave_y"]:
                        self.arcade_columns.append(self.mat(x, y, 0))
                        self.arcade_columns.append(self.mat(x, y, TRIFORIUM_LEVEL, scale=0.8))
        
        # =================================================================
        # PASS 2: Floors
        # =================================================================
        for bx in range(-max_extent, max_extent + 1):
            for by in range(-max_extent, max_extent + 1):
                if not self.is_in_plan(bx, by):
                    continue
                
                x = bx * self.bay
                y = by * self.bay
                zone = self.get_zone(bx, by)
                
                # Ground floor everywhere
                self.ground_floor.append(self.mat(x, y, GROUND_LEVEL))
                
                # Mezzanine in aisles only (not over main nave void)
                if zone in ["aisle_x", "aisle_y", "crossing_aisle"]:
                    self.mezzanine_floor.append(self.mat(x, y, TRIFORIUM_LEVEL))
                    
                    # Underslung beams along bay lines
                    self.mezzanine_beams.append(self.mat(x, y, TRIFORIUM_LEVEL - BEAM_DEPTH/2))
        
        # =================================================================
        # PASS 3: Walls and Windows
        # =================================================================
        for bx in range(-max_extent, max_extent + 1):
            for by in range(-max_extent, max_extent + 1):
                if not self.is_in_plan(bx, by):
                    continue
                
                x = bx * self.bay
                y = by * self.bay
                zone = self.get_zone(bx, by)
                is_edge, rot = self.is_exterior_edge(bx, by)
                
                if is_edge:
                    # Exterior wall
                    self.exterior_walls.append(self.mat(x, y, 0, rot))
                    self.clerestory_walls.append(self.mat(x, y, CLERESTORY_BASE, rot))
                    
                    # Buttress at this position
                    self.buttresses.append(self.mat(x, y, 0, rot))
                    
                    # Windows between buttresses
                    # Ground floor lancets
                    self.lancet_windows_ground.append(self.mat(x, y, 1.5, rot))
                    
                    # Clerestory lancets
                    self.lancet_windows_clerestory.append(self.mat(x, y, CLERESTORY_BASE + 1.0, rot))
                    
                    # Apse/terminal walls get special treatment
                    if zone in ["apse_x", "apse_y"]:
                        self.apse_walls.append(self.mat(x, y, 0, rot))
                        # Rose window at wing terminus
                        if abs(bx) == max_extent and by == 0:
                            self.rose_windows.append(self.mat(x, y, VAULT_SPRING, rot))
                        elif abs(by) == max_extent and bx == 0:
                            self.rose_windows.append(self.mat(x, y, VAULT_SPRING, rot))
        
        # =================================================================
        # PASS 4: Arches and Vault Ribs
        # =================================================================
        
        # Crossing arches (the 4 great ones)
        cross_offset = (self.nave_width_bays // 2 + 1) * self.bay
        self.crossing_arches.append(self.mat(cross_offset, 0, ARCADE_HEIGHT, -pi/2))
        self.crossing_arches.append(self.mat(-cross_offset, 0, ARCADE_HEIGHT, pi/2))
        self.crossing_arches.append(self.mat(0, cross_offset, ARCADE_HEIGHT, pi))
        self.crossing_arches.append(self.mat(0, -cross_offset, ARCADE_HEIGHT, 0))
        
        # Nave arcade arches (between columns along nave)
        nave_col_x = (self.nave_width_bays // 2 + 1) * self.bay
        for by in range(-max_extent + 1, max_extent):
            if abs(by) > self.crossing_bays // 2:  # Only in wing sections
                y = (by + 0.5) * self.bay
                # East side arches
                self.nave_arches.append(self.mat(nave_col_x, y, ARCADE_HEIGHT, -pi/2))
                # West side arches
                self.nave_arches.append(self.mat(-nave_col_x, y, ARCADE_HEIGHT, pi/2))
        
        # Same for X-wings
        nave_col_y = (self.nave_width_bays // 2 + 1) * self.bay
        for bx in range(-max_extent + 1, max_extent):
            if abs(bx) > self.crossing_bays // 2:
                x = (bx + 0.5) * self.bay
                self.nave_arches.append(self.mat(x, nave_col_y, ARCADE_HEIGHT, pi))
                self.nave_arches.append(self.mat(x, -nave_col_y, ARCADE_HEIGHT, 0))
        
        # Transverse vault ribs (across the nave at each bay)
        for by in range(-max_extent, max_extent + 1):
            y = by * self.bay
            if self.is_in_plan(0, by):
                self.transverse_ribs.append(self.mat(0, y, VAULT_SPRING, 0))
        
        for bx in range(-max_extent, max_extent + 1):
            x = bx * self.bay
            if self.is_in_plan(bx, 0):
                self.transverse_ribs.append(self.mat(x, 0, VAULT_SPRING, pi/2))
        
        # =================================================================
        # PASS 5: Balustrades (Mezzanine railings)
        # =================================================================
        
        # Railings along the mezzanine edge (facing the nave void)
        for bx in range(-max_extent, max_extent + 1):
            for by in range(-max_extent, max_extent + 1):
                if not self.is_in_plan(bx, by):
                    continue
                
                x = bx * self.bay
                y = by * self.bay
                zone = self.get_zone(bx, by)
                
                # Inner edge of mezzanine (facing nave)
                if zone in ["aisle_x", "aisle_y", "crossing_aisle"]:
                    # Check if adjacent to nave
                    nave_edge_x = self.nave_width_bays // 2 + 1
                    nave_edge_y = self.nave_width_bays // 2 + 1
                    
                    if abs(bx) == nave_edge_x:
                        rot = -pi/2 if bx > 0 else pi/2
                        self.balustrades.append(self.mat(x, y, TRIFORIUM_LEVEL, rot))
                    
                    if abs(by) == nave_edge_y:
                        rot = pi if by > 0 else 0
                        self.balustrades.append(self.mat(x, y, TRIFORIUM_LEVEL, rot))
        
        # =================================================================
        # PASS 6: Stairs
        # =================================================================
        
        # Grand stairs at the 4 corners of crossing
        stair_offset = (self.crossing_bays // 2) * self.bay
        stair_positions = [
            (stair_offset, stair_offset, -3*pi/4),
            (-stair_offset, stair_offset, 3*pi/4),
            (stair_offset, -stair_offset, -pi/4),
            (-stair_offset, -stair_offset, pi/4),
        ]
        for x, y, rot in stair_positions:
            self.grand_stairs.append(self.mat(x, y, 0, rot))
        
        # Spiral stairs at wing corners (service access)
        wing_half = (self.nave_width_bays // 2 + self.aisle_width_bays) * self.bay
        for sign_x in [-1, 1]:
            for sign_y in [-1, 1]:
                # North/South wing corners
                self.spiral_stairs.append(self.mat(
                    sign_x * wing_half, 
                    sign_y * (self.half_crossing + self.wing_length_bays * self.bay * 0.8),
                    0
                ))
        
        # =================================================================
        # PASS 7: Furniture and Study Positions
        # =================================================================
        
        # Study pods in the aisles (between columns and walls)
        for bx in range(-max_extent, max_extent + 1):
            for by in range(-max_extent, max_extent + 1):
                if not self.is_in_plan(bx, by):
                    continue
                
                x = bx * self.bay
                y = by * self.bay
                zone = self.get_zone(bx, by)
                
                # Study pods in aisle zones at regular intervals
                if zone in ["aisle_x", "aisle_y"]:
                    # Every other bay for spacing
                    if (bx + by) % 2 == 0:
                        # Determine facing direction (towards nave)
                        if zone == "aisle_y":
                            rot = -pi/2 if bx > 0 else pi/2
                        else:
                            rot = pi if by > 0 else 0
                        
                        self.study_pod_positions.append(self.mat(x, y, 0, rot))
                
                # Shelf walls along exterior (but not at windows)
                is_edge, rot = self.is_exterior_edge(bx, by)
                if is_edge and zone in ["aisle_x", "aisle_y"]:
                    self.shelf_wall_positions.append(self.mat(x, y, 0, rot + pi))
        
        # Reading alcoves at wing terminations
        alcove_positions = [
            (self.wing_extent - self.bay, 0, -pi/2),
            (-self.wing_extent + self.bay, 0, pi/2),
            (0, self.wing_extent - self.bay, pi),
            (0, -self.wing_extent + self.bay, 0),
        ]
        for x, y, rot in alcove_positions:
            self.reading_alcove_positions.append(self.mat(x, y, 0, rot))
        
        # =================================================================
        # PASS 8: Decorative Elements
        # =================================================================
        
        # Statues at wing thresholds (where wings meet crossing)
        threshold_offset = (self.crossing_bays // 2 + 1) * self.bay
        statue_positions = [
            # Wing entrances
            (threshold_offset, self.nave_half_width, -pi/2),
            (threshold_offset, -self.nave_half_width, -pi/2),
            (-threshold_offset, self.nave_half_width, pi/2),
            (-threshold_offset, -self.nave_half_width, pi/2),
            (self.nave_half_width, threshold_offset, pi),
            (-self.nave_half_width, threshold_offset, pi),
            (self.nave_half_width, -threshold_offset, 0),
            (-self.nave_half_width, -threshold_offset, 0),
        ]
        for x, y, rot in statue_positions:
            self.statue_positions.append(self.mat(x, y, 0, rot))
            self.plinth_positions.append(self.mat(x, y, 0, rot))
        
        # Central oculus
        self.oculus.append(self.mat(0, 0, OCULUS_HEIGHT))
        
        # Chandeliers
        # Central chandelier under oculus
        self.chandelier_positions.append(self.mat(0, 0, VAULT_CREST - 2))
        
        # Chandeliers along nave axes
        for mult in [-2, -1, 1, 2]:
            offset = mult * self.bay * 2
            self.chandelier_positions.append(self.mat(offset, 0, ARCADE_HEIGHT + 2))
            self.chandelier_positions.append(self.mat(0, offset, ARCADE_HEIGHT + 2))
        
        return self.get_outputs()
    
    def get_outputs(self) -> Dict[str, List]:
        """Return all outputs as a dictionary."""
        return {
            # Structural
            "main_piers": self.main_piers,
            "arcade_columns": self.arcade_columns,
            "buttresses": self.buttresses,
            
            # Arches
            "crossing_arches": self.crossing_arches,
            "nave_arches": self.nave_arches,
            "aisle_arches": self.aisle_arches,
            "transverse_ribs": self.transverse_ribs,
            
            # Walls
            "exterior_walls": self.exterior_walls,
            "clerestory_walls": self.clerestory_walls,
            "apse_walls": self.apse_walls,
            
            # Windows
            "lancet_windows_ground": self.lancet_windows_ground,
            "lancet_windows_clerestory": self.lancet_windows_clerestory,
            "rose_windows": self.rose_windows,
            "oculus": self.oculus,
            
            # Floors
            "ground_floor": self.ground_floor,
            "mezzanine_floor": self.mezzanine_floor,
            "mezzanine_beams": self.mezzanine_beams,
            
            # Railings
            "balustrades": self.balustrades,
            
            # Stairs
            "grand_stairs": self.grand_stairs,
            "spiral_stairs": self.spiral_stairs,
            
            # Furniture zones
            "study_pod_positions": self.study_pod_positions,
            "shelf_wall_positions": self.shelf_wall_positions,
            "reading_alcove_positions": self.reading_alcove_positions,
            
            # Decorative
            "statue_positions": self.statue_positions,
            "chandelier_positions": self.chandelier_positions,
            "plinth_positions": self.plinth_positions,
        }


# =============================================================================
# SVERCHOK SCRIPT NODE CODE
# =============================================================================

def build_sverchok_script() -> str:
    """
    Generate the Sverchok script string for the layout node.
    This embeds the GothicLayoutGenerator logic.
    """
    
    return '''"""
in bay s d=6.0 n=0
in wing_bays s d=4 n=0
out main_piers m
out arcade_columns m
out buttresses m
out crossing_arches m
out nave_arches m
out transverse_ribs m
out exterior_walls m
out clerestory_walls m
out lancet_ground m
out lancet_clerestory m
out rose_windows m
out ground_floor m
out mezzanine_floor m
out mezzanine_beams m
out balustrades m
out grand_stairs m
out study_pods m
out shelf_walls m
out statues m
out chandeliers m
"""
import mathutils
from math import pi

def sv_main(bay=6.0, wing_bays=4):
    bay = float(bay)
    wing_bays = int(wing_bays)
    
    # Architectural constants
    CROSSING_BAYS = 4
    NAVE_WIDTH_BAYS = 2
    AISLE_WIDTH_BAYS = 1
    
    # Vertical dimensions
    GROUND_LEVEL = 0.0
    ARCADE_HEIGHT = 6.0
    TRIFORIUM_LEVEL = 5.0
    CLERESTORY_BASE = 8.0
    VAULT_SPRING = 10.0
    VAULT_CREST = 14.0
    
    # Derived
    half_crossing = (CROSSING_BAYS * bay) / 2
    nave_half_width = (NAVE_WIDTH_BAYS * bay) / 2
    wing_extent = half_crossing + wing_bays * bay
    max_extent = CROSSING_BAYS // 2 + wing_bays
    
    # Outputs
    main_piers = []
    arcade_columns = []
    buttresses = []
    crossing_arches = []
    nave_arches = []
    transverse_ribs = []
    exterior_walls = []
    clerestory_walls = []
    lancet_ground = []
    lancet_clerestory = []
    rose_windows = []
    ground_floor = []
    mezzanine_floor = []
    mezzanine_beams = []
    balustrades = []
    grand_stairs = []
    study_pods = []
    shelf_walls = []
    statues = []
    chandeliers = []
    
    def mat(x, y, z=0.0, rot_z=0.0, scale=1.0):
        m = mathutils.Matrix.Translation((x, y, z))
        if rot_z != 0.0:
            m = m @ mathutils.Matrix.Rotation(rot_z, 4, 'Z')
        if scale != 1.0:
            m = m @ mathutils.Matrix.Scale(scale, 4)
        return m
    
    def in_plan(bx, by):
        half = CROSSING_BAYS // 2
        wing_half = NAVE_WIDTH_BAYS // 2 + AISLE_WIDTH_BAYS
        if abs(bx) <= half and abs(by) <= half:
            return True
        if abs(bx) <= wing_half and abs(by) <= half + wing_bays:
            return True
        if abs(by) <= wing_half and abs(bx) <= half + wing_bays:
            return True
        return False
    
    def get_zone(bx, by):
        half = CROSSING_BAYS // 2
        nave_half = NAVE_WIDTH_BAYS // 2
        if abs(bx) <= half and abs(by) <= half:
            if abs(bx) <= nave_half and abs(by) <= nave_half:
                return "crossing_nave"
            return "crossing_aisle"
        if abs(by) > half:
            if abs(bx) <= nave_half:
                return "nave_y"
            return "aisle_y"
        if abs(bx) > half:
            if abs(by) <= nave_half:
                return "nave_x"
            return "aisle_x"
        return "unknown"
    
    # Generate grid
    for bx in range(-max_extent, max_extent + 1):
        for by in range(-max_extent, max_extent + 1):
            if not in_plan(bx, by):
                continue
            
            x = bx * bay
            y = by * bay
            zone = get_zone(bx, by)
            
            # Ground floor
            ground_floor.append(mat(x, y, GROUND_LEVEL))
            
            # Mezzanine (aisles only)
            if "aisle" in zone:
                mezzanine_floor.append(mat(x, y, TRIFORIUM_LEVEL))
                mezzanine_beams.append(mat(x, y, TRIFORIUM_LEVEL - 0.2))
            
            # Main piers (crossing corners)
            if abs(bx) == 1 and abs(by) == 1:
                main_piers.append(mat(x, y, 0, scale=1.5))
                main_piers.append(mat(x, y, TRIFORIUM_LEVEL, scale=1.2))
            
            # Arcade columns
            is_pier_x = abs(bx) == NAVE_WIDTH_BAYS // 2 + 1
            is_pier_y = abs(by) == NAVE_WIDTH_BAYS // 2 + 1
            if (is_pier_x or is_pier_y) and zone not in ["crossing_nave", "nave_x", "nave_y"]:
                arcade_columns.append(mat(x, y, 0))
                arcade_columns.append(mat(x, y, TRIFORIUM_LEVEL, scale=0.8))
            
            # Exterior edges
            wing_half = NAVE_WIDTH_BAYS // 2 + AISLE_WIDTH_BAYS
            half = CROSSING_BAYS // 2
            
            is_edge = False
            rot = 0
            
            # Wing ends
            if bx == max_extent and abs(by) <= wing_half:
                is_edge, rot = True, -pi/2
            elif bx == -max_extent and abs(by) <= wing_half:
                is_edge, rot = True, pi/2
            elif by == max_extent and abs(bx) <= wing_half:
                is_edge, rot = True, pi
            elif by == -max_extent and abs(bx) <= wing_half:
                is_edge, rot = True, 0
            # Wing sides
            elif abs(by) > half and abs(bx) == wing_half:
                is_edge = True
                rot = -pi/2 if bx > 0 else pi/2
            elif abs(bx) > half and abs(by) == wing_half:
                is_edge = True
                rot = pi if by > 0 else 0
            
            if is_edge:
                exterior_walls.append(mat(x, y, 0, rot))
                clerestory_walls.append(mat(x, y, CLERESTORY_BASE, rot))
                buttresses.append(mat(x, y, 0, rot))
                lancet_ground.append(mat(x, y, 1.5, rot))
                lancet_clerestory.append(mat(x, y, CLERESTORY_BASE + 1.0, rot))
            
            # Balustrades (mezzanine inner edge)
            if "aisle" in zone:
                nave_edge = NAVE_WIDTH_BAYS // 2 + 1
                if abs(bx) == nave_edge:
                    r = -pi/2 if bx > 0 else pi/2
                    balustrades.append(mat(x, y, TRIFORIUM_LEVEL, r))
                if abs(by) == nave_edge:
                    r = pi if by > 0 else 0
                    balustrades.append(mat(x, y, TRIFORIUM_LEVEL, r))
            
            # Study pods (aisles, alternating)
            if "aisle" in zone and (bx + by) % 2 == 0:
                if zone == "aisle_y":
                    r = -pi/2 if bx > 0 else pi/2
                else:
                    r = pi if by > 0 else 0
                study_pods.append(mat(x, y, 0, r))
                shelf_walls.append(mat(x, y, 0, r + pi))
    
    # Crossing arches
    cross_off = (NAVE_WIDTH_BAYS // 2 + 1) * bay
    crossing_arches.append(mat(cross_off, 0, ARCADE_HEIGHT, -pi/2))
    crossing_arches.append(mat(-cross_off, 0, ARCADE_HEIGHT, pi/2))
    crossing_arches.append(mat(0, cross_off, ARCADE_HEIGHT, pi))
    crossing_arches.append(mat(0, -cross_off, ARCADE_HEIGHT, 0))
    
    # Nave arches
    for by in range(-max_extent + 1, max_extent):
        if abs(by) > half:
            y = (by + 0.5) * bay
            nave_arches.append(mat(cross_off, y, ARCADE_HEIGHT, -pi/2))
            nave_arches.append(mat(-cross_off, y, ARCADE_HEIGHT, pi/2))
    
    for bx in range(-max_extent + 1, max_extent):
        if abs(bx) > half:
            x = (bx + 0.5) * bay
            nave_arches.append(mat(x, cross_off, ARCADE_HEIGHT, pi))
            nave_arches.append(mat(x, -cross_off, ARCADE_HEIGHT, 0))
    
    # Transverse ribs
    for b in range(-max_extent, max_extent + 1):
        if in_plan(0, b):
            transverse_ribs.append(mat(0, b * bay, VAULT_SPRING, 0))
        if in_plan(b, 0):
            transverse_ribs.append(mat(b * bay, 0, VAULT_SPRING, pi/2))
    
    # Rose windows at wing ends
    rose_windows.append(mat(wing_extent, 0, VAULT_SPRING, -pi/2))
    rose_windows.append(mat(-wing_extent, 0, VAULT_SPRING, pi/2))
    rose_windows.append(mat(0, wing_extent, VAULT_SPRING, pi))
    rose_windows.append(mat(0, -wing_extent, VAULT_SPRING, 0))
    
    # Grand stairs at crossing corners
    stair_off = half * bay
    grand_stairs.append(mat(stair_off, stair_off, 0, -3*pi/4))
    grand_stairs.append(mat(-stair_off, stair_off, 0, 3*pi/4))
    grand_stairs.append(mat(stair_off, -stair_off, 0, -pi/4))
    grand_stairs.append(mat(-stair_off, -stair_off, 0, pi/4))
    
    # Statues at wing thresholds
    thresh = (half + 1) * bay
    nave_half = (NAVE_WIDTH_BAYS // 2) * bay
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            statues.append(mat(thresh * sx, nave_half * sy, 0, -pi/2 * sx))
            statues.append(mat(nave_half * sx, thresh * sy, 0, pi if sy > 0 else 0))
    
    # Chandeliers
    chandeliers.append(mat(0, 0, VAULT_CREST - 2))
    for m in [-2, -1, 1, 2]:
        chandeliers.append(mat(m * bay * 2, 0, ARCADE_HEIGHT + 2))
        chandeliers.append(mat(0, m * bay * 2, ARCADE_HEIGHT + 2))
    
    return (main_piers, arcade_columns, buttresses, crossing_arches, nave_arches, 
            transverse_ribs, exterior_walls, clerestory_walls, lancet_ground,
            lancet_clerestory, rose_windows, ground_floor, mezzanine_floor,
            mezzanine_beams, balustrades, grand_stairs, study_pods, shelf_walls,
            statues, chandeliers)

(main_piers, arcade_columns, buttresses, crossing_arches, nave_arches, 
 transverse_ribs, exterior_walls, clerestory_walls, lancet_ground,
 lancet_clerestory, rose_windows, ground_floor, mezzanine_floor,
 mezzanine_beams, balustrades, grand_stairs, study_pods, shelf_walls,
 statues, chandeliers) = sv_main(bay, wing_bays)
'''


def ensure_layout_tree():
    """Create or update the Sverchok layout tree."""
    tree = ensure_tree()
    sn = ensure_script_node(tree)
    
    # Set the script
    sn.script_name = "sv_gothic_layout_v2.py"
    sn.script_str = build_sverchok_script()
    
    # Update
    try:
        sn.update_sockets()
    except Exception:
        pass
    
    try:
        sn.process()
    except Exception:
        pass
    
    print(f"✅ Sverchok tree '{TREE_NAME}' ready with Gothic Layout V2")
    return tree


# =============================================================================
# STANDALONE EXECUTION (Direct Blender Python without Sverchok)
# =============================================================================

def create_layout_directly():
    """
    Create the layout directly in Blender without Sverchok.
    Useful for testing or when Sverchok is not available.
    """
    generator = GothicLayoutGenerator()
    outputs = generator.generate()
    
    # Create collections
    root_col = bpy.data.collections.get("OL_Gothic_V2")
    if not root_col:
        root_col = bpy.data.collections.new("OL_Gothic_V2")
        bpy.context.scene.collection.children.link(root_col)
    
    # Clear existing
    for obj in list(root_col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    
    for child in list(root_col.children):
        for obj in list(child.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(child)
    
    # Create debug visualizations (simple empties showing positions)
    def create_empties(name: str, matrices: List, parent_col, display_type='PLAIN_AXES', size=0.5):
        col = bpy.data.collections.new(name)
        parent_col.children.link(col)
        
        for i, mat in enumerate(matrices):
            empty = bpy.data.objects.new(f"{name}_{i:03d}", None)
            empty.empty_display_type = display_type
            empty.empty_display_size = size
            empty.matrix_world = mat
            col.objects.link(empty)
        
        return col
    
    # Create empties for each output type
    create_empties("MainPiers", outputs["main_piers"], root_col, 'CUBE', 0.8)
    create_empties("ArcadeColumns", outputs["arcade_columns"], root_col, 'CIRCLE', 0.4)
    create_empties("Buttresses", outputs["buttresses"], root_col, 'SINGLE_ARROW', 1.0)
    create_empties("CrossingArches", outputs["crossing_arches"], root_col, 'SPHERE', 1.5)
    create_empties("NaveArches", outputs["nave_arches"], root_col, 'SPHERE', 1.0)
    create_empties("ExteriorWalls", outputs["exterior_walls"], root_col, 'PLAIN_AXES', 3.0)
    create_empties("GroundFloor", outputs["ground_floor"], root_col, 'PLAIN_AXES', 0.3)
    create_empties("MezzanineFloor", outputs["mezzanine_floor"], root_col, 'PLAIN_AXES', 0.3)
    create_empties("Balustrades", outputs["balustrades"], root_col, 'SINGLE_ARROW', 1.1)
    create_empties("GrandStairs", outputs["grand_stairs"], root_col, 'ARROWS', 2.0)
    create_empties("StudyPods", outputs["study_pod_positions"], root_col, 'CUBE', 1.5)
    create_empties("Statues", outputs["statue_positions"], root_col, 'CONE', 1.0)
    create_empties("Chandeliers", outputs["chandelier_positions"], root_col, 'SPHERE', 0.8)
    create_empties("RoseWindows", outputs["rose_windows"], root_col, 'CIRCLE', 3.0)
    
    print(f"✅ Created Gothic Layout V2 with {len(outputs['ground_floor'])} floor bays")
    print(f"   - Main piers: {len(outputs['main_piers'])}")
    print(f"   - Arcade columns: {len(outputs['arcade_columns'])}")
    print(f"   - Study pod positions: {len(outputs['study_pod_positions'])}")
    print(f"   - Exterior walls: {len(outputs['exterior_walls'])}")
    
    return outputs


def print_layout_summary():
    """Print a summary of the layout configuration."""
    print("\n" + "="*60)
    print("GOTHIC LIBRARY V2 - ARCHITECTURAL SUMMARY")
    print("="*60)
    print(f"\n📐 MODULE:")
    print(f"   Bay size: {BAY}m")
    print(f"   Crossing: {CROSSING_BAYS}x{CROSSING_BAYS} bays ({CROSSING_BAYS*BAY}m x {CROSSING_BAYS*BAY}m)")
    print(f"   Nave width: {NAVE_WIDTH_BAYS} bays ({NAVE_WIDTH_BAYS*BAY}m clear)")
    print(f"   Aisle width: {AISLE_WIDTH_BAYS} bay ({AISLE_WIDTH_BAYS*BAY}m)")
    print(f"   Wing length: {WING_LENGTH_BAYS} bays ({WING_LENGTH_BAYS*BAY}m beyond crossing)")
    
    total_width = (NAVE_WIDTH_BAYS + 2*AISLE_WIDTH_BAYS) * BAY
    total_length = (CROSSING_BAYS + 2*WING_LENGTH_BAYS) * BAY
    print(f"\n📏 TOTAL FOOTPRINT:")
    print(f"   Width: {total_width}m")
    print(f"   Length: {total_length}m")
    
    print(f"\n🏛️ VERTICAL:")
    print(f"   Ground: {GROUND_LEVEL}m")
    print(f"   Mezzanine: {TRIFORIUM_LEVEL}m")
    print(f"   Arcade arch height: {ARCADE_HEIGHT}m")
    print(f"   Clerestory base: {CLERESTORY_BASE}m")
    print(f"   Vault spring: {VAULT_SPRING}m")
    print(f"   Vault crest: {VAULT_CREST}m")
    print(f"   Oculus: {OCULUS_HEIGHT}m")
    
    print("\n" + "="*60 + "\n")


# =============================================================================
# ENTRY POINTS
# =============================================================================

if __name__ == "__main__":
    print_layout_summary()
    
    # Try Sverchok first, fall back to direct creation
    try:
        tree = ensure_layout_tree()
    except Exception as e:
        print(f"Sverchok not available ({e}), creating layout directly...")
        create_layout_directly()

