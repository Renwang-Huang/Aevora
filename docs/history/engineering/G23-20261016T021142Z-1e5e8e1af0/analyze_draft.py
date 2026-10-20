from audit import *
import importlib.util
root=E/'04_live/S1_02';run=next((root/'runs').iterdir());m=json.loads((run/'runtime_metadata.json').read_text())
spec=importlib.util.spec_from_file_location('draft_native',E/'draft_native_rollout_trace.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
x=mod.analyze_native_rollouts(run.name,run,m['native_rollouts'],expected_parent_thread_id=m['thread_id'])
write(root/'NATIVE_PROTOCOL_REANALYSIS_DRAFT.json',{'source_sha256':sha(E/'draft_native_rollout_trace.py'),'source_note':'POST_RUN_PARSER_DIAGNOSTIC; original metadata/Outcome unchanged','analysis':x})
print(x['summary']['integrity']);print([(a['agent_id'],a['verified'],a['execution_verified'],a['completed'],a['task'][:60] if isinstance(a['task'],str) else a['task']) for a in x['summary']['subagents']['agents']])
