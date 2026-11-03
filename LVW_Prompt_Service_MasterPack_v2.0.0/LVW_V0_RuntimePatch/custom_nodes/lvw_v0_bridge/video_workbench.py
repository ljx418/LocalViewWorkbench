"""CPU-only presentation of manual fields and explicit current-run adoption."""
import json

from .core import BridgeError
from .manual import ManualDraftOwner, result_txt
from .state import OUTPUT_FIELDS

MAX_BODY_BYTES = 2 * 1024 * 1024


def project(body, owner=None):
    if not isinstance(body, dict):
        raise ValueError('workbench request must be an object')
    action = body.get('action')
    if action == 'preview' and set(body) == {'action', 'fields'}:
        fields = body['fields']
        if not isinstance(fields, dict) or set(fields) != set(OUTPUT_FIELDS):
            raise ValueError('exact manual fields required')
        draft, payload, _ = ManualDraftOwner().execute(action='preview_json', filename='lvw-video', **fields)
        return {'result': json.loads(payload), 'txt': result_txt(draft)}
    if action == 'adopt' and set(body) == {'action', 'run_token'}:
        token = body['run_token']
        if not isinstance(token, str) or not 1 <= len(token) <= 128:
            raise ValueError('bounded run token required')
        if owner is None:
            raise BridgeError('ATTEMPT_STALE', 'no successful current video run', subcode='VIDEO_RUN_STALE')
        run = owner.completed_result(token)
        spec = json.loads(run['suggestion'])
        fields = dict.fromkeys(OUTPUT_FIELDS, '')
        fields.update(natural_zh=spec['text_zh'], natural_en=spec['text_en'],
                      image_prompt=spec['text_en'], video_prompt=spec['text_en'],
                      tags=', '.join(spec['tags']), negative=spec['negative'])
        value = project({'action': 'preview', 'fields': fields})
        value['result'].update(source_type='video', run_id=token, analysis_status='succeeded',
            source=run['source'], model_tag=run['model_tag'], raw_response=run['raw_response'],
            suggestion=spec, draft_origin='model_adopted',
            warnings=['Only four sampled frames were observed; unsampled events and continuous motion are unverified.'])
        return value
    raise ValueError('unsupported workbench action or fields')
