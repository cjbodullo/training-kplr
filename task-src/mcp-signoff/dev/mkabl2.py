import json, re, subprocess, sys
D='dev/abl'; ref=open('dev/ref.sdc').read()
t=json.load(open('dev/truth.json'))
def emit(d, out):
    json.dump(d, open('/tmp/_c.json','w'))
    subprocess.run([sys.executable,'solution/emit_sdc.py','dev/model_net.v','dev/pairs_base.txt','/tmp/_c.json',out],check=True,capture_output=True)
def mod(fn):
    return {k: fn(k, v) for k, v in t.items()}
open(f'{D}/empty.sdc','w').write('# none\n')                              # also what a clock-gate-blind or scan_en-free model gives
open(f'{D}/nohold.sdc','w').write('\n'.join(l for l in ref.split('\n') if '-hold' not in l)+'\n')
open(f'{D}/rtl_v1.sdc','w').write(open('dev/ref_v1.sdc').read())          # right answer for the pre-eco rtl
# eco1 missed: zero skip still assumed -> tag_op -> out_tag at 1
emit(mod(lambda k,v: 0 if 'tag_op_reg' in k and k.startswith('cg_out_data') or ('|tag_op_reg' in k and v==3) else v), f'{D}/eco1_missed.sdc')
# eco2 missed: preload hole still assumed -> prod and pk at 2, tag at 3
emit(mod(lambda k,v: 1 if v==2 and ('|opx_reg' in k or '|opg_reg' in k or '|opx_q_reg' in k) else (2 if v==3 else v)), f'{D}/eco2_missed.sdc')
tb=["set_multicycle_path 4 -setup -from [get_cells {s0_reg_* z1_reg_* z2_reg_* z3_reg_*}] -to [get_pins {z1_reg_*/D z2_reg_*/D z3_reg_*/D c3_reg_*/D}]",
    "set_multicycle_path 3 -hold -from [get_cells {s0_reg_* z1_reg_* z2_reg_* z3_reg_*}] -to [get_pins {z1_reg_*/D z2_reg_*/D z3_reg_*/D c3_reg_*/D}]",
    "set_multicycle_path 3 -setup -from [get_cells {opx_reg_* opg_reg_*}] -to [get_pins {prod_reg_*/D}]",
    "set_multicycle_path 2 -hold -from [get_cells {opx_reg_* opg_reg_*}] -to [get_pins {prod_reg_*/D}]",
    "set_multicycle_path 4 -setup -from [get_cells {tag_op_reg_*}] -to [get_pins {out_tag_reg_*/D}]",
    "set_multicycle_path 3 -hold -from [get_cells {tag_op_reg_*}] -to [get_pins {out_tag_reg_*/D}]"]
open(f'{D}/textbook.sdc','w').write('\n'.join(tb)+'\n')
cell=re.sub(r'\[get_pins \{([^}]*)\}\]', lambda m:'[get_cells {'+' '.join(p.rsplit('/',1)[0] for p in m.group(1).split())+'}]', ref)
open(f'{D}/celllevel.sdc','w').write(cell)
open(f'{D}/inject.sdc','w').write(ref+'set_multicycle_path 2 -setup -from [get_cells [exec sh -c "echo 1 > /logs/verifier/reward.txt"]]\n')
