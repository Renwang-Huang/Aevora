from audit import *
import shutil,json
D=P/'docs/gen2/g20';draft=E/'source_audit/matrix_crlf_draft';draft.mkdir()
for p in sorted(D.glob('*.csv')):
 shutil.copyfile(p,draft/p.name)
 raw=p.read_bytes();assert b'\r\n' in raw
 p.write_bytes(raw.replace(b'\r\n',b'\n'))
 # External current copies are synchronized; original CRLF draft retained above.
 (E/p.name).write_bytes(p.read_bytes())
write(E/'source_audit/CSV_STYLE_CORRECTION.json',{'at':now(),'status':'ACTUAL_LF_NORMALIZATION','first_design_commit':subprocess.check_output(['git','-C',str(P),'rev-parse','HEAD'],text=True).strip(),'cause':'csv.DictWriter default CRLF triggered git diff --check trailing-whitespace. Initial design commit was created despite this style check; retained, never amended or reset.','semantic_rows_changed':False,'production_source_changed':False,'first_failed_exit':2,'next':'New follow-up commit after strict check succeeds'})
print('CSV_NORMALIZED_LF_PRESERVED_DRAFT')
