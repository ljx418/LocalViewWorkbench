"""Pure state transitions isolating model callbacks from the human draft."""

from __future__ import annotations

import copy
import json

from .core import BridgeError, FROZEN_ERROR_CODES

OUTPUT_FIELDS = ("natural_zh", "natural_en", "image_prompt", "video_prompt", "tags", "negative", "edit_instruction")
FAILURE_CODES = frozenset({"MODEL_REFUSAL", "MODEL_TIMEOUT", "GPU_OOM", "NO_USABLE_OUTPUT"})
ACTIONS = ("start_run", "model_success", "model_failure", "partial", "cancel", "adopt")


def empty_state() -> dict:
    return {
        "run_token": None,
        "draft_epoch": 0,
        "raw_response": None,
        "suggestion": None,
        "draft": {key: ([] if key == "tags" else "") for key in OUTPUT_FIELDS},
        "analysis_status": "not_requested",
        "failure_code": None,
        "retry_count": 0,
    }


def _load_state(state_json: str) -> dict:
    if not isinstance(state_json, str):
        raise BridgeError("PARSE_PARTIAL", "state must be a JSON string", subcode="STATE_JSON_INVALID")
    if not state_json.strip():
        return empty_state()
    try:
        state = json.loads(state_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise BridgeError("PARSE_PARTIAL", "state is not valid JSON", subcode="STATE_JSON_INVALID") from exc
    if not isinstance(state, dict) or set(state) != set(empty_state()):
        raise BridgeError("PARSE_PARTIAL", "state shape is invalid", subcode="STATE_SCHEMA_INVALID")
    return copy.deepcopy(state)


def _current(state: dict, token: str) -> None:
    if not isinstance(token, str) or not token or token != state["run_token"]:
        raise BridgeError("ATTEMPT_STALE", "callback token is not current", subcode="RUN_TOKEN_STALE")


def _active(state: dict, token: str) -> None:
    _current(state, token)
    if state["analysis_status"] != "running":
        raise BridgeError("ATTEMPT_STALE", "run is no longer accepting callbacks", subcode="RUN_NOT_ACTIVE")


def _outputs(payload: str) -> dict:
    try:
        value = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise BridgeError("PARSE_PARTIAL", "draft payload is not valid JSON", subcode="DRAFT_JSON_INVALID") from exc
    if not isinstance(value, dict) or set(value) != set(OUTPUT_FIELDS):
        raise BridgeError("PARSE_PARTIAL", "draft payload fields are invalid", subcode="DRAFT_SCHEMA_INVALID")
    if any(not isinstance(value[key], str) for key in OUTPUT_FIELDS if key != "tags") or not isinstance(value["tags"], list) \
            or any(not isinstance(tag, str) for tag in value["tags"]):
        raise BridgeError("PARSE_PARTIAL", "draft payload values are invalid", subcode="DRAFT_SCHEMA_INVALID")
    return value


def transition(state_json: str, *, action: str, run_token: str, raw_response: str = "",
               suggestion_payload: str = "", draft_payload: str = "", error_code: str = "") -> dict:
    state = _load_state(state_json)
    next_state = copy.deepcopy(state)
    if action == "start_run":
        if not isinstance(run_token, str) or not run_token:
            raise BridgeError("CONTRACT_UNSUPPORTED", "run_token is required", subcode="RUN_TOKEN_REQUIRED")
        next_state.update(run_token=run_token, raw_response=None, suggestion=None,
                          analysis_status="running", failure_code=None, retry_count=0)
    elif action == "model_success":
        _active(state, run_token)
        try:
            suggestion = json.loads(suggestion_payload)
        except (TypeError, json.JSONDecodeError) as exc:
            raise BridgeError("PARSE_PARTIAL", "model callback is not valid JSON",
                              subcode="CALLBACK_JSON_INVALID") from exc
        if not isinstance(suggestion, dict):
            raise BridgeError("PARSE_PARTIAL", "model suggestion must be an object",
                              subcode="CALLBACK_SCHEMA_INVALID")
        if not isinstance(raw_response, str) or not raw_response or raw_response == suggestion_payload:
            raise BridgeError("PARSE_PARTIAL", "raw response and suggestion must be distinct non-empty values",
                              subcode="RAW_SUGGESTION_NOT_DISTINCT")
        next_state.update(raw_response=raw_response, suggestion=suggestion,
                          analysis_status="succeeded", failure_code=None)
    elif action in {"model_failure", "partial", "cancel"}:
        _active(state, run_token)
        if action == "cancel":
            code, status = "JOB_CANCELLED", "cancelled"
        else:
            code = error_code
            if code not in FROZEN_ERROR_CODES or (action == "model_failure" and code not in FAILURE_CODES):
                raise BridgeError("CONTRACT_UNSUPPORTED", "failure code is not allowed",
                                  subcode="STATE_FAILURE_CODE_UNSUPPORTED")
            status = "partial" if action == "partial" else "failed"
        next_state.update(analysis_status=status, failure_code=code)
        if raw_response:
            next_state["raw_response"] = raw_response
    elif action == "adopt":
        _current(state, run_token)
        if state["analysis_status"] != "succeeded":
            raise BridgeError("NO_USABLE_OUTPUT", "only a succeeded current suggestion can be adopted",
                              subcode="ADOPT_WITHOUT_SUCCESS")
        next_state["draft"] = _outputs(draft_payload)
        next_state["draft_epoch"] = state["draft_epoch"] + 1
    else:
        raise BridgeError("CONTRACT_UNSUPPORTED", "unknown state action", subcode="STATE_ACTION_UNSUPPORTED")
    return next_state
