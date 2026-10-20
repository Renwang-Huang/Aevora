from audit import *
import subprocess,stat
base=E.parent/'G22-20261015T174846Z-88fad40ffd';frozen=Path('/home/PRIVATE_MAINTAINER/data_storage/humble_workspace/aevora')
def tracked(root):
 names=subprocess.check_output(['git','--no-optional-locks','ls-files','-z'],cwd=root).split(b'\0')
 return {os.fsdecode(n):sha(root/os.fsdecode(n)) for n in names if n}
write(E/'00_baseline/SOURCE_IDENTITY.json',{'base_commit':'e9e7a7a422828e847b237fa8d3e0450b98a97804','base_tree':'b63c0dda2fc0451eba6ee76a9196aadb8c7bf2e7','g22_files':tracked(base/'worktree'),'frozen547':tracked(frozen),'g22_manifest_sha256':sha(base/'DELIVERY_MANIFEST.json'),'old_manifest_expected':'df86ab16050f5f6aad44bb1a1f53e17292f6a14348c8592b404021ed1f2c5870','git_alternates':(E/'repository.git/objects/info/alternates').exists()})
rows=[('S1_SOURCE','D','v01','Native parent plus at least two children; independent fresh repair and optional natural untrusted proposal','new empty v2 live graph plus separately labelled old-principle seed'),('S2_TRANSFER','D','v01','Fresh native session, fresh defective baseline; no S1 patch/rollout/context; graph is only transfer channel','S1 actually published graph, iff publication succeeds'),('NEGATIVE_TRANSFER','D','v01','Single-process synchronization scope cannot certify independent worker safety','separately pinned old source, not S1 output'),('PUBLISH_REVOCATION',None,None,'Mechanism controls on fresh independent graph; no alteration of sealed live evidence','HOST_CONTROLLED_GRAPH_TEST')]
registration={'version':'aevora.g23/1','registered_at':now(),'experiments':[dict(kind=a,episode=b,variant=c,task=d,input=e,challenge_id=__import__('uuid').uuid4().hex) for a,b,c,d,e in rows],'s1_s2_run_ids':'allocated by unchanged Runner at execution, official session IDs unavailable until real runtime starts','source_input_sha256':sha(E/'00_baseline/SOURCE_IDENTITY.json'),'seed':'NONE_YET; exact seed receipt required before any S1 launch','upstream_requests':None,'total_tokens':None,'financial_budget':None,'causal_benefit':'UNKNOWN','controls':'CONTROL_NOT_RUN until executed','first_failures':'preserved by exclusive command directories'}
write(E/'EXPERIMENT_REGISTRATION.json',registration);(E/'EXPERIMENT_REGISTRATION.json').chmod(0o400)
(E/'G23_SOURCE_AND_TRUST_BOUNDARY_MAP.md').write_text('''# G23 initial source and authority map

Participant is the existing outer bubblewrap user/PID/IPC/UTS/network namespace; native business commands additionally retain official workspace-write sandboxing. Only public app, issue/task/manifest, tests, role configs, independent Codex binary/helper, system toolchain and run-scoped model/MCP sockets are mounted. No maintainer root, hidden Oracle, reference, full archive or long-lived credentials are mounted. Same UID/shared kernel remains ISOLATION_PARTIAL.

Host and Oracle run in the separate trusted maintainer namespace: current owned source, private verifier and reference, private output, explicit read-only legacy mappings when required. They are never Participant tools. FalkorDB is a new authenticated loopback container on17751 with a new owned volume; prior DB containers/volumes remain untouched. Gateway long-term key exists only at host broker; model runtime receives scoped proxy identity; business command sandbox cannot use the channel. The existing physical probe is executed before model preflight, not inferred from configuration.

Runtime Aevora v1 bridge currently uses legacy graph; v2 public Broker/Core already exist. Needed integration: explicit Host-selected v2 configuration, exact official actor/tool/MCP/body/run/patch/outcome provenance. Public tool catalog stays four; no Host approval/verification/publication operation is exposed. The current G22 source explicitly writes proposal_actor_thread_id=UNAVAILABLE; G23 must not trust it as native actor proof.

S1/S2 grading is exclusively unchanged original Runner/Evaluator. New source must preserve protected app/Oracle/test bytes; postmortem grades remain separate. Provider label does not attest model weights, and query/decision/action correlation does not establish causal benefit.
''')
print('registered',sha(E/'EXPERIMENT_REGISTRATION.json'))
