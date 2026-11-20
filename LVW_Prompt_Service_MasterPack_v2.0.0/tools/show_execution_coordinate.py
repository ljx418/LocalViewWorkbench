#!/usr/bin/env python3
"""Render a compact view of the single authority; no second stored coordinate."""
import json
from pathlib import Path
p=Path(__file__).resolve().parents[1]
x=json.loads((p/'plans/execution-control.json').read_text())
view={k:x.get(k) for k in ['project_id','target_version','coordinate','current_blocking_gate','priority_interruption','next_owner','next_action','required_authorization','quota_restore_notice','delivery_efficiency_adoption']}
view['development_outline']=[{'stage_id':s['stage_id'],'completed':s['completed_substeps'],'total':s['total_substeps']} for s in x['development_outline']]
view['authority']='plans/execution-control.json'
print(json.dumps(view,ensure_ascii=False,indent=2))
