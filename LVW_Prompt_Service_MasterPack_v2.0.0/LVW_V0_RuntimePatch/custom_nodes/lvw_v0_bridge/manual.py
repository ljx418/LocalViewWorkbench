"""Pure-CPU manual draft, copy, and controlled export owner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from .core import BridgeError


MAX_DRAFT_CHARACTERS = 20_000
MANUAL_ACTIONS = ("preview_json", "copy_txt", "copy_json", "export_txt", "export_json")


def _text(value, field: str) -> str:
    if not isinstance(value, str):
        raise BridgeError("CONTRACT_UNSUPPORTED", f"{field} must be a string",
                          subcode="MANUAL_FIELD_TYPE")
    if len(value) > MAX_DRAFT_CHARACTERS:
        raise BridgeError("MEDIA_LIMIT_EXCEEDED",
                          f"{field} exceeds {MAX_DRAFT_CHARACTERS} characters",
                          subcode="MANUAL_DRAFT_CHARACTER_LIMIT",
                          details={"field": field, "maximum": MAX_DRAFT_CHARACTERS,
                                   "actual": len(value)})
    return value


def _tags(value: str) -> tuple[str, ...]:
    raw = _text(value, "tags")
    return tuple(item.strip() for line in raw.splitlines() for item in line.split(",") if item.strip())


@dataclass(frozen=True)
class ManualDraft:
    natural_zh: str
    natural_en: str
    image_prompt: str
    video_prompt: str
    tags: tuple[str, ...]
    negative: str
    edit_instruction: str

    @classmethod
    def from_inputs(cls, *, natural_zh: str, natural_en: str, image_prompt: str,
                    video_prompt: str, tags: str, negative: str,
                    edit_instruction: str) -> "ManualDraft":
        return cls(
            natural_zh=_text(natural_zh, "natural_zh"),
            natural_en=_text(natural_en, "natural_en"),
            image_prompt=_text(image_prompt, "image_prompt"),
            video_prompt=_text(video_prompt, "video_prompt"),
            tags=_tags(tags),
            negative=_text(negative, "negative"),
            edit_instruction=_text(edit_instruction, "edit_instruction"),
        )

    def outputs(self) -> dict:
        return {
            "natural_zh": self.natural_zh,
            "natural_en": self.natural_en,
            "image_prompt": self.image_prompt,
            "video_prompt": self.video_prompt,
            "tags": list(self.tags),
            "negative": self.negative,
            "edit_instruction": self.edit_instruction,
        }


def manual_result(draft: ManualDraft, *, created_at: str | None = None) -> dict:
    return {
        "schema_version": "lvw.v0.result/1",
        "source_type": "manual",
        "run_id": None,
        "analysis_status": "not_requested",
        "source": None,
        "model_tag": None,
        "model_digest": None,
        "raw_response": None,
        "suggestion": None,
        "draft": draft.outputs(),
        "draft_origin": "manual",
        "warnings": [],
        "created_at": created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def result_json(draft: ManualDraft, *, created_at: str | None = None) -> str:
    return json.dumps(manual_result(draft, created_at=created_at), ensure_ascii=False,
                      indent=2, sort_keys=True) + "\n"


def result_txt(draft: ManualDraft) -> str:
    fields = (
        ("Natural Chinese", draft.natural_zh),
        ("Natural English", draft.natural_en),
        ("Image Prompt", draft.image_prompt),
        ("Video Prompt", draft.video_prompt),
        ("Tags", ", ".join(draft.tags)),
        ("Negative", draft.negative),
        ("Edit Instruction", draft.edit_instruction),
    )
    return "\n\n".join(f"## {label}\n{value}" for label, value in fields) + "\n"


def _safe_filename(value: str, suffix: str) -> str:
    name = _text(value, "filename").strip()
    reserved = name.split(".", 1)[0].upper()
    if (not name or name in {".", ".."} or len(name) > 128 or
            any(character in name for character in "/\\:\0") or
            any(ord(character) < 32 for character in name) or
            value.endswith((".", " ")) or
            reserved in {"CON", "PRN", "AUX", "NUL"} or
            reserved in {f"COM{index}" for index in range(1, 10)} or
            reserved in {f"LPT{index}" for index in range(1, 10)}):
        raise BridgeError("PATH_FORBIDDEN", "export filename must be one safe basename",
                          subcode="MANUAL_EXPORT_PATH_FORBIDDEN")
    return name + suffix


def atomic_write(root: Path, filename: str, payload: str, *, parent_root: Path) -> Path:
    root = Path(root)
    parent_root = Path(parent_root)
    temporary = None
    try:
        authority = parent_root.resolve(strict=True)
        if not authority.is_dir() or root.is_symlink():
            raise OSError("invalid export boundary")
        resolved_root = root.resolve(strict=False)
        if resolved_root == authority or not resolved_root.is_relative_to(authority):
            raise OSError("export root escapes configured parent")
    except OSError as exc:
        raise BridgeError("PATH_FORBIDDEN", "export root is outside the configured output boundary",
                          subcode="MANUAL_EXPORT_ROOT_FORBIDDEN") from exc
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n",
                                         prefix=".lvw-manual-", suffix=".tmp",
                                         dir=root, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        target = root / filename
        os.replace(temporary, target)
        return target
    except OSError as exc:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        raise BridgeError("DISK_FULL", "atomic manual export failed",
                          subcode="MANUAL_ATOMIC_EXPORT_FAILED") from exc


class TkClipboard:
    def write(self, payload: str) -> None:
        root = None
        try:
            import tkinter
            root = tkinter.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(payload)
            root.update()
        except Exception as exc:
            raise BridgeError("NO_USABLE_OUTPUT", "clipboard write failed",
                              subcode="CLIPBOARD_WRITE_FAILED") from exc
        finally:
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    pass


class ManualDraftOwner:
    """Explicit action owner; formatting and view changes never call a model."""

    def __init__(self, *, export_root: Path | None = None, export_parent: Path | None = None,
                 clipboard=None, clock=None):
        self._export_root = Path(export_root) if export_root is not None else None
        self._export_parent = (Path(export_parent) if export_parent is not None else
                               self._export_root.parent if self._export_root is not None else None)
        self._clipboard = clipboard or TkClipboard()
        self._clock = clock
        self.model_calls = 0

    def _roots(self) -> tuple[Path, Path]:
        if self._export_root is not None:
            return self._export_parent, self._export_root
        try:
            import folder_paths
            parent = Path(folder_paths.get_output_directory())
            return parent, parent / "lvw_manual"
        except Exception as exc:
            raise BridgeError("PATH_FORBIDDEN", "Comfy output root is unavailable",
                              subcode="COMFY_OUTPUT_ROOT_UNAVAILABLE") from exc

    def execute(self, *, action: str, filename: str, natural_zh: str, natural_en: str,
                image_prompt: str, video_prompt: str, tags: str, negative: str,
                edit_instruction: str):
        if action not in MANUAL_ACTIONS:
            raise BridgeError("CONTRACT_UNSUPPORTED", "unsupported manual action",
                              subcode="MANUAL_ACTION_UNSUPPORTED")
        draft = ManualDraft.from_inputs(
            natural_zh=natural_zh, natural_en=natural_en,
            image_prompt=image_prompt, video_prompt=video_prompt,
            tags=tags, negative=negative, edit_instruction=edit_instruction,
        )
        created_at = self._clock() if self._clock else None
        json_payload = result_json(draft, created_at=created_at)
        txt_payload = result_txt(draft)
        payload = txt_payload if action.endswith("txt") else json_payload
        status = {"action": action, "model_calls": self.model_calls, "exported_filename": None}
        if action.startswith("copy_"):
            try:
                self._clipboard.write(payload)
            except BridgeError:
                raise
            except Exception as exc:
                raise BridgeError("NO_USABLE_OUTPUT", "clipboard write failed",
                                  subcode="CLIPBOARD_WRITE_FAILED") from exc
        elif action.startswith("export_"):
            suffix = ".txt" if action.endswith("txt") else ".json"
            parent, root = self._roots()
            target = atomic_write(root, _safe_filename(filename, suffix), payload,
                                  parent_root=parent)
            status["exported_filename"] = target.name
        return draft, payload, json.dumps(status, ensure_ascii=False, sort_keys=True)
