#!/usr/bin/env python3
"""Misread battery: rebuild a part under one wrong reading and grade it with the real verifier.
usage (in the dev image): variants.py <truth dir> <work dir> [name ...]"""
import os
import shutil
import sys
import time

sys.path.insert(0, "/w/solution")
sys.path.insert(0, "/w/tests")
import cadquery as cq  # noqa: E402
import check_models  # noqa: E402
import cut  # noqa: E402
import fanuc  # noqa: E402
import models  # noqa: E402

CNC = "/w/environment/data/cnc"


def edit(work, name, old, new):
    d = f"{work}/cnc_{name}"
    shutil.copytree(CNC, d, dirs_exist_ok=True)
    p = f"{d}/ALL-PROG.TXT"
    s = open(p).read()
    assert old in s, old
    open(p, "w").write(s.replace(old, new, 1))
    return d


def flip_y(part, contact=15.0):
    """wrong OP20 load: turned over about Y instead of X"""
    bb = part.BoundingBox()
    slab = cq.Solid.makeBox(bb.xlen + 20, bb.ylen + 20, contact + 5,
                            cq.Vector(bb.xmin - 10, bb.ymin - 10, bb.zmax - contact))
    wall = part.intersect(slab).BoundingBox()
    turned = part.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 180)
    # (x, y, z) -> (-x, y, -z): old right end now on the stop, back still on the jaw
    return turned.translate(cq.Vector(models.STOP_X + wall.xmax, 0, models.PAR_Z + bb.zmax))


def build(part, cnc=CNC, quirks=(), tools=None, flip=None):
    saved = dict(models.TOOLS)
    if tools:
        models.TOOLS.update(tools)
    try:
        if part == "MNF-0610":
            op10, op20 = fanuc.run_part(cnc, [1610, 1620], models.LENGTH, quirks)
            p = models.single(models.machine(models.block(124.0, 84.0, 31.0), op10, False))
            p = (flip or models.flip_over_x)(p)
            return models.single(models.machine(p, op20, False))
        if part == "BRG-1140":
            (b,) = fanuc.run_part(cnc, [1140], models.LENGTH, quirks)
            return models.single(models.machine(models.block(90.0, 60.0, 40.0), b, False))
        (c,) = fanuc.run_part(cnc, [2205], models.LENGTH, quirks)
        return models.single(models.machine(models.block(110.0, 45.0, 20.0), c, False))
    finally:
        models.TOOLS.clear()
        models.TOOLS.update(saved)


def variants(work):
    M, B, L = "MNF-0610", "BRG-1140", "LVR-2205"
    v = {
        # control semantics
        "ext_offset_ignored": [(p, dict(quirks={"no_ext"})) for p in (M, B, L)],
        "h_wear_ignored": [(p, dict(quirks={"no_hwear"})) for p in (M, B, L)],
        "h_taken_from_tool_not_program": [(M, dict(quirks={"h_is_tool"}))],
        "d_wear_ignored": [(M, dict(quirks={"no_dwear"}))],
        "m98_own_local_level": [(M, dict(quirks={"m98_new_level"}))],
        "mirror_keeps_arc_direction": [(M, dict(quirks={"mirror_keeps_arcs"}))],
        "g68_ignored": [(M, dict(quirks={"no_g68"}))],
        "g10_l2_ignored": [(M, dict(quirks={"no_g10"}))],
        "decimal_point_calculator_type": [(B, dict(quirks={"dpi1"}))],
        "vacant_argument_as_zero": [(B, dict(quirks={"vacant_is_zero"}))],
        "g52_accumulates": [(B, dict(quirks={"g52_adds"}))],
        "g91_cycle_z_from_initial": [(B, dict(quirks={"g91_z_from_init"})), (L, dict(quirks={"g91_z_from_init"}))],
        "m99_restores_g90": [(L, dict(quirks={"m99_restores_g90"}))],
        # program reading
        "drill_angle_step_B_missed": [(M, dict(cnc=edit(work, "b", "H5. B60. Z-15.", "H5. Z-15.")))],
        "stop_shift_g52_missed": [(B, dict(cnc=edit(work, "g52", "G52 X-0.4 Y0.3", "G52 X0. Y0.")))],
        "negative_r_read_as_positive": [(L, dict(cnc=edit(work, "negr", "R-12.", "R12.")))],
        "keyhole_floor_assumed_flat": [(L, dict(cnc=edit(work, "flat", "G01 Z-8. F120.\nG01 X60. F500.",
                                                         "G01 Z-8. F120.\nG01 X30. F500.\nG03 I-5. J0.\nG01 X60.")))],
        # setup / tooling reading
        "op20_flipped_about_y": [(M, dict(flip=flip_y))],
        "t6_point_118": [(M, dict(tools={6: cut.Tool("cone", 6.6, point=118.0)})),
                         (B, dict(tools={6: cut.Tool("cone", 6.6, point=118.0)}))],
        "bull_nose_as_flat": [(L, dict(tools={9: cut.Tool("flat", 8.0)}))],
        "chamfer_mill_sharp_tip": [(L, dict(tools={8: cut.Tool("cone", 12.0, point=90.0)}))],
    }
    return v


def main():
    truth, work = sys.argv[1], sys.argv[2]
    os.makedirs(work, exist_ok=True)
    only = set(sys.argv[3:])
    for name, runs in variants(work).items():
        if only and name not in only:
            continue
        for part, kw in runs:
            t = time.time()
            try:
                s = build(part, **kw)
                path = f"{work}/{name}__{part}.step"
                cq.exporters.export(cq.Workplane().add(s), path)
                try:
                    msg = "PASS(!) " + check_models.compare(path, f"{truth}/{part}.step")
                except check_models.Bad as e:
                    msg = f"FAIL {e}"
            except Exception as e:  # a reading the control would alarm on
                msg = f"BUILD ERROR {type(e).__name__}: {e}"
            print(f"{name:34s} {part:9s} {msg}  [{time.time() - t:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
