from audit import *
import ast,csv,collections
prior=json.loads((E/'00_environment/repo_integrity.json').read_text())['source547_sha256']
symbols=[];imports=[];calls=[];rows=[];queries=[]
def module(rel):
 n=rel.removeprefix('aevora_core/src/').removeprefix('console/src/').removesuffix('.py').replace('/','.')
 return n.removesuffix('.__init__')
def visibility(rel):
 if rel.startswith(('evaluator/','tests/','benchmark/','app/','aevora_maintainer/','integrations/','scripts/')):return 'MAINTAINER'
 if rel.startswith(('aevora_core/src/','console/src/','console/web/','h4/','tools/public_evidence/')):return 'PUBLIC_ALLOWLIST_REQUIRES_BUILD_CHECK'
 if rel.startswith(('AEVORA_','PHASE','M1_','GEN1_')):return 'HISTORICAL_DOCUMENT'
 return 'MAINTAINER_METADATA_OR_DOC'
for rel,expected in sorted(prior.items()):
 p=W/rel;actual=sha(p);assert actual==expected
 deps=[];own=[]
 if rel.endswith('.py'):
  tree=ast.parse(p.read_text(),filename=rel)
  class Visitor(ast.NodeVisitor):
   stack=[]
   def visit_ClassDef(self,n):
    symbols.append({'path':rel,'line':n.lineno,'end_line':n.end_lineno,'kind':'class','symbol':'.'.join(self.stack+[n.name])});self.stack.append(n.name);self.generic_visit(n);self.stack.pop()
   def visit_FunctionDef(self,n):
    symbols.append({'path':rel,'line':n.lineno,'end_line':n.end_lineno,'kind':'function','symbol':'.'.join(self.stack+[n.name])});self.stack.append(n.name);self.generic_visit(n);self.stack.pop()
   visit_AsyncFunctionDef=visit_FunctionDef
   def visit_Import(self,n):
    for x in n.names:imports.append({'path':rel,'line':n.lineno,'module':x.name,'level':0,'symbol':None});deps.append(x.name)
   def visit_ImportFrom(self,n):
    imports.append({'path':rel,'line':n.lineno,'module':n.module or '', 'level':n.level,'symbols':[x.name for x in n.names]});deps.append('.'*n.level+(n.module or ''))
   def visit_Call(self,n):
    calls.append({'path':rel,'line':n.lineno,'caller':'.'.join(self.stack) or '<module>','expression':ast.unparse(n.func),'resolution':'SYNTACTIC_REFERENCE; dynamic binding UNVERIFIED'});self.generic_visit(n)
   def visit_Constant(self,n):
    if isinstance(n.value,str) and any(n.value.lstrip().startswith(k) for k in ['MATCH','CREATE','MERGE','SELECT','UPDATE','INSERT','BEGIN','PRAGMA']):queries.append({'path':rel,'line':n.lineno,'literal':n.value})
  Visitor().visit(tree)
 rows.append({'path':rel,'current_sha256':actual,'g5_sha256':expected,'match':'YES','owner':rel.split('/')[0] if '/' in rel else 'ROOT_METADATA','module':module(rel) if rel.endswith('.py') else '', 'source_generated':'GENERATED' if '/vendor/' in rel or '/static/' in rel or rel in ['h4/verify_hero.py','h4/AI_DISCLOSURE.md'] else 'SOURCE_OR_DOCUMENT','visibility':visibility(rel),'imports':';'.join(deps),'test_ownership':'DEVELOPER' if 'tests/' in rel else 'SOURCE_TO_TEST_LINK_REQUIRES_SYMBOL_MATCH'})
write(E/'01_source/AST_SYMBOLS.json',symbols);write(E/'01_source/IMPORT_DEPENDENCIES.json',imports);write(E/'01_source/CALL_REFERENCES.json',calls);write(E/'01_source/DATABASE_STATEMENTS.json',queries)
with (E/'01_source/SOURCE_547_INVENTORY.csv').open('x') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
assert len(rows)==547
write(E/'01_source/INDEX_RECEIPT.json',{'at':now(),'status':'PASS','source_files':len(rows),'python_files':sum(x['path'].endswith('.py') for x in rows),'symbols':len(symbols),'syntactic_calls':len(calls),'imports':len(imports),'database_literals':len(queries),'scope':'Static AST indexing of all Python files; does not certify dynamic call dispatch nor all logic correct'})
print('V1 index',len(rows),len(symbols),len(calls))
