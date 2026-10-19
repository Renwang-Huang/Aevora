from pathlib import Path
from aevora.graph_repository import GraphRepository
from aevora.historical_import import import_verified_history
import json
r=GraphRepository.from_environment();r.initialize(schema_version='aevora.graph/1.2')
root=Path('/home/PRIVATE_MAINTAINER/data_storage/humble_workspace/orderflow_incident_lab')
archive=root/'m1_validation'/((root/'m1_validation/CURRENT').read_text().strip())
print(json.dumps(import_verified_history(r,archive),indent=2));print(r.state_fingerprint());r.close()
