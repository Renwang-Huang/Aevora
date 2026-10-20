from pathlib import Path
import importlib.util,sys
p=Path(__file__).resolve().parent/'01_root_cause/baseline_mcp_server.py';spec=importlib.util.spec_from_file_location('aevora.pinned_pre_projection_server',p);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);raise SystemExit(m.main())
