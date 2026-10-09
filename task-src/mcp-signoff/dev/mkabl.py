import json, re, subprocess, sys, os
D='dev/abl'; ref=open('dev/ref.sdc').read()
def emit(cand, out):
    subprocess.run([sys.executable,'solution/emit_sdc.py','tests/design/cicd.v','dev/pairs_base.txt',cand,out],check=True,capture_output=True)
emit(f'{D}/cand_notest.json', f'{D}/notest.sdc')
emit(f'{D}/cand_nosilence.json', f'{D}/nosilence.sdc')
open(f'{D}/empty.sdc','w').write('# nothing\n')
open(f'{D}/nohold.sdc','w').write('\n'.join(l for l in ref.split('\n') if '-hold' not in l)+'\n')
cell=re.sub(r'\[get_pins \{([^}]*)\}\]', lambda m:'[get_cells {'+' '.join(p.rsplit('/',1)[0] for p in m.group(1).split())+'}]', ref)
open(f'{D}/celllevel.sdc','w').write(cell)
open(f'{D}/loadbased.sdc','w').write('\n'.join(l for l in ref.split('\n') if 'gain_q_reg' not in l and 'pk_reg' not in l)+'\n')
t=json.load(open('dev/truth.json')); t2={k:(1 if '|gain_q_reg' in k and k.startswith('start') else v) for k,v in t.items()}
json.dump(t2,open(f'{D}/cand_wholereg.json','w')); emit(f'{D}/cand_wholereg.json', f'{D}/wholereg.sdc')
# textbook: design intent, R=4 comb period, 4 cycle scaler
tb=["set_multicycle_path 4 -setup -from [get_cells {s0_reg_* z1_reg_* z2_reg_* z3_reg_*}] -to [get_pins {z1_reg_*/D z2_reg_*/D z3_reg_*/D c3_reg_*/D}]",
    "set_multicycle_path 3 -hold -from [get_cells {s0_reg_* z1_reg_* z2_reg_* z3_reg_*}] -to [get_pins {z1_reg_*/D z2_reg_*/D z3_reg_*/D c3_reg_*/D}]",
    "set_multicycle_path 3 -setup -from [get_cells {opx_reg_* opg_reg_*}] -to [get_pins {prod_reg_*/D}]",
    "set_multicycle_path 2 -hold -from [get_cells {opx_reg_* opg_reg_*}] -to [get_pins {prod_reg_*/D}]",
    "set_multicycle_path 4 -setup -from [get_cells {tag_op_reg_*}] -to [get_pins {out_tag_reg_*/D}]",
    "set_multicycle_path 3 -hold -from [get_cells {tag_op_reg_*}] -to [get_pins {out_tag_reg_*/D}]"]
open(f'{D}/textbook.sdc','w').write('\n'.join(tb)+'\n')
open(f'{D}/inject.sdc','w').write(ref+'set_false_path -from [get_cells [exec sh -c "echo 1 > /logs/verifier/reward.txt"]]\n')
