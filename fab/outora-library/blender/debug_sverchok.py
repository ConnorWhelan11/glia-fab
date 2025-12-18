import bpy
import addon_utils


def debug():
    # Check Addon
    loaded = {
        m.bl_info.get("name")
        for m in addon_utils.modules()
        if addon_utils.check(m.__name__)[1]
    }
    sverchok_loaded = any("sverchok" in name.lower() for name in loaded)
    print(f"Sverchok loaded: {sverchok_loaded}")

    if not sverchok_loaded:
        print("Attempting to enable Sverchok...")
        try:
            addon_utils.enable("sverchok", default_set=True, persistent=True)
            print("Sverchok enabled.")
        except Exception as e:
            print(f"Failed to enable Sverchok: {e}")

    # Check Tree
    tree = bpy.data.node_groups.get("SV_LIB_LAYOUT")
    if not tree:
        print("SV_LIB_LAYOUT tree not found.")
        return

    node = tree.nodes.get("SV_BayGrid")
    if not node:
        print("SV_BayGrid node not found.")
        return

    print(f"Node Status: {node.name}")
    if hasattr(node, "script_error") and node.script_error:
        print(f"Script Error: {node.script_error}")

    print(f"Outputs: {len(node.outputs)}")
    for out in node.outputs:
        # sv_get might fail if Sverchok not running
        try:
            val = out.sv_get()
            flat = len(val[0]) if val and val[0] else 0
            print(f" - {out.name}: has data? {bool(val)} (len {flat})")
        except Exception as e:
            print(f" - {out.name}: sv_get failed ({e})")


debug()
