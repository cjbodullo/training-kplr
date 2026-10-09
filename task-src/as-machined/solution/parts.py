#!/usr/bin/env python3
"""Forward model: one part machined on a given control state with a given tool crib and setup."""
import cadquery as cq

import cut
import fanuc

# /app/shop/TOOL-LIST.TXT (as of today)
TOOLS = {
    1: cut.Tool("flat", 50.0),
    2: cut.Tool("flat", 16.0),
    3: cut.Tool("flat", 10.0),
    4: cut.Tool("cone", 12.0, point=90.0),
    5: cut.Tool("cone", 6.8, point=118.0),
    6: cut.Tool("cone", 6.6, point=140.0),
    7: cut.Tool("flat", 12.0),
    8: cut.Tool("cone", 12.0, point=90.0, tip_flat=2.0),
    9: cut.Tool("bull", 8.0, corner=1.0),
    10: cut.Tool("flat", 11.0),
}
LENGTH = {1: 98.412, 2: 110.250, 3: 102.775, 4: 95.300, 5: 124.640, 6: 121.115, 7: 108.880,
          8: 101.505, 9: 99.730, 10: 96.210}
# the T6 that came out on 09-22 (TOOL-LIST note)
OLD_T6 = (cut.Tool("cone", 6.8, point=118.0), 126.690)

# /app/shop/VISE-SETUP.TXT
STOP_X, JAW_Y, PAR_Z = -612.0, -208.0, -455.0


def block(dx, dy, dz):
    """stock square in the vise: left end on the stop, back on the fixed jaw, bottom on parallels"""
    return cq.Solid.makeBox(dx, dy, dz, cq.Vector(STOP_X, JAW_Y - dy, PAR_Z))


def _walls(part, contact):
    bb = part.BoundingBox()
    slab = cq.Solid.makeBox(bb.xlen + 20, bb.ylen + 20, contact + 5,
                            cq.Vector(bb.xmin - 10, bb.ymin - 10, bb.zmax - contact))
    return bb, part.intersect(slab).BoundingBox()


def turn_over(part, axis="X", contact=15.0):
    """OP20 load: finished top down on the parallels, jaw and stop on the profiled walls within
    `contact` of the top. axis X (setup sheet): OP10 front face to the jaw, left end to the stop.
    axis Y: OP10 back face stays on the jaw, OP10 right end goes to the stop."""
    bb, wall = _walls(part, contact)
    if axis == "X":     # (x, y, z) -> (x, -y, -z)
        turned = part.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 180)
        return turned.translate(cq.Vector(STOP_X - wall.xmin, JAW_Y + wall.ymin, PAR_Z + bb.zmax))
    turned = part.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 180)    # (x, y, z) -> (-x, y, -z)
    return turned.translate(cq.Vector(STOP_X + wall.xmax, JAW_Y - wall.ymax, PAR_Z + bb.zmax))


def to_print(part, solid, axis="X"):
    """put a finished part in print orientation (OP10 top up, OP10 front toward -Y)"""
    if part != "MNF-0610":
        return solid
    if axis == "X":
        return solid.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 180)
    return solid.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 180)


def machine(stock, moves, tools, check=False):
    out = cut.cut(stock, cut.sweeps(moves, tools, ztop=stock.BoundingBox().zmax))
    if check:
        cut.rapid_hits(moves, tools, out)
    return out


def single(solid):
    solids = [s for s in solid.Solids() if abs(s.Volume()) > 1e-6]   # drop zero volume BOP debris
    if len(solids) != 1:
        raise RuntimeError(f"expected one solid, got {len(solids)}")
    if not solids[0].isValid():
        raise RuntimeError("machined solid is not valid")
    s = solids[0].clean()
    if not s.isValid():
        raise RuntimeError("cleaned solid is not valid")
    return s


def build(part, cnc, tools=None, lengths=None, axis="X", quirks=(), check=False):
    """the finished part, in its last setup's machine frame"""
    tools = tools or TOOLS
    lengths = lengths or LENGTH
    if part == "MNF-0610":
        op10, op20 = fanuc.run_part(cnc, [1610, 1620], lengths, quirks)
        p = single(machine(block(124.0, 84.0, 31.0), op10, tools, check))
        p = turn_over(p, axis)
        return single(machine(p, op20, tools, check))
    if part == "BRG-1140":
        (b,) = fanuc.run_part(cnc, [1140], lengths, quirks)
        return single(machine(block(90.0, 60.0, 40.0), b, tools, check))
    (c,) = fanuc.run_part(cnc, [2205], lengths, quirks)
    return single(machine(block(110.0, 45.0, 20.0), c, tools, check))


def crib(old_t6):
    tools, lengths = dict(TOOLS), dict(LENGTH)
    if old_t6:
        tools[6], lengths[6] = OLD_T6
    return tools, lengths
