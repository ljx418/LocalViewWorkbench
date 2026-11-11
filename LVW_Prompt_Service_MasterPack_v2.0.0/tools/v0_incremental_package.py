#!/usr/bin/env python3
"""LVW V0 增量包工具（S3-PREP-B 冻结实施合同 + correction-01 安全纠偏）。

职责：把 Git 候选 commit 中的 LVW_V0_RuntimePatch 生产 payload 打成可复算的离线
增量包，校验该包，并可在**显式隔离沙箱**中安装与回滚。

严格边界（与 stage-packet-preparation-b.md 一致）：

* 只读 Git 对象库，不打包脏工作树；构建绑定完整 commit SHA。
* 只做离线：不联网、不下载、不读媒体、不用模型/GPU、不起服务。
* 只写显式提供的沙箱父目录内的 target；生产宿主路径硬拒绝。
* 不含任何任意 shell 执行接口，不依赖第三方包。

四个冻结子命令：build / diagnose / install / rollback。
结构化 JSON 写 stdout，诊断写 stderr，非零退出码表示失败。

correction-01 纠偏要点（针对独审 F-01 / F-02 / M-01）：

* 安装成功时在**目标内部**落一份本轮所有权记录（ownership record），绑定规范化
  target 身份、沙箱 marker 身份、不可碰撞 session、源 candidate/manifest/payload
  集合与安装 hash；回滚必须读取这份目标内真实记录，并与外部收据、沙箱 marker
  交叉核对。外部收据里的任何路径字段都**不是**删除授权。
* 回滚先做全量预检（路径合法性、唯一性、symlink 逃逸、session/marker/target
  绑定、逐项 hash），任何一项不通过就零写入零删除并稳定非零退出。
* 不再以收据里的 staging 路径做递归删除；成功安装时 staging 已在同一事务内
  清理，回滚只确认其终态。
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath

# --------------------------------------------------------------------------- #
# 冻结常量
# --------------------------------------------------------------------------- #

TOOL_NAME = "v0_incremental_package.py"
TOOL_VERSION = "1.1.0"

PACKAGE_FORMAT_VERSION = "lvw.v0-incremental-package/1"
MANIFEST_SCHEMA_VERSION = "lvw.v0-incremental-package-manifest/1"
#: correction-01：收据 schema 升到 /2（新增所有权绑定字段）。
RECEIPT_SCHEMA_VERSION = "lvw.v0-incremental-package-receipt/2"
DIAGNOSTIC_SCHEMA_VERSION = "lvw.v0-incremental-package-diagnostic/1"
#: correction-01：目标内所有权记录的 schema 版本（工具内部 schema，不是产品公共 schema）。
OWNERSHIP_SCHEMA_VERSION = "lvw.v0-incremental-package-ownership/1"

#: 目标内所有权记录的文件名（相对 target 根，不含目录前缀）。
OWNERSHIP_FILE_NAME = ".lvw_v0_incremental_ownership.json"

#: 暂存目录前缀（安装事务自建，回滚只确认终态、绝不按路径递归删除）。
STAGING_DIR_PREFIX = ".lvw-v0-stage-"

#: 压缩包与展开 payload 各自适用的硬上限（20 MiB）。
SIZE_LIMIT_BYTES = 20 * 1024 * 1024

#: zip bomb 判定：展开总大小 / 压缩总大小 的上限。
ZIP_BOMB_RATIO_LIMIT = 200
#: 单个成员允许的最大展开/压缩比。
ZIP_BOMB_MEMBER_RATIO_LIMIT = 500

#: 沙箱 marker：文件名固定，magic 固定，内容由沙箱拥有者写好。
SANDBOX_MARKER_NAME = ".lvw_v0_incremental_sandbox.json"
SANDBOX_MARKER_MAGIC = "lvw.v0-incremental-sandbox/1"

#: 生产宿主路径硬拒绝（大小写不敏感的路径组件）。
PRODUCTION_HOST_COMPONENTS = frozenset(
    {"comfyui", "comfyui-aki-v2", "comfyui_windows_portable", "comfyui-aki"}
)

#: payload 来源（Git 路径前缀）。
BRIDGE_SOURCE_DIR = "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge"
WORKFLOWS_SOURCE_DIR = "LVW_V0_RuntimePatch/workflows"

#: 目标安装布局（相对 install root）。
BRIDGE_INSTALL_DIR = "custom_nodes/lvw_v0_bridge"
WORKFLOWS_INSTALL_DIR = "workflows/lvw"

#: owned 安装顶层目录（安装事务会创建，回滚按记录逐层 rmdir）。
OWNED_TOP_LEVEL_DIRS = ("custom_nodes", "workflows")
#: owned 安装文件前缀：任何 owned 文件路径必须落在其中之一之下。
OWNED_INSTALL_PREFIXES = (BRIDGE_INSTALL_DIR + "/", WORKFLOWS_INSTALL_DIR + "/")

#: 包内固定成员前缀与名字。
PAYLOAD_PREFIX = "payload/"
META_PREFIX = "meta/"
MANIFEST_MEMBER = META_PREFIX + "manifest.json"
TOOL_MEMBER = META_PREFIX + TOOL_NAME
USAGE_MEMBER = META_PREFIX + "使用说明.md"

#: ZIP 固定时间戳（最早可表示时间），保证同候选重复构建字节一致。
ZIP_FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_FIXED_MODE = 0o100644

EXIT_CODES = {
    "OK": 0,
    "BAD_INPUT": 2,
    "INTEGRITY_MISMATCH": 3,
    "PATH_REJECTED": 4,
    "SIZE_LIMIT": 5,
    "CONFLICT": 6,
    "INSTALL_FAILED": 7,
    "ROLLBACK_CONFLICT": 8,
    "INTERNAL_ERROR": 9,
}

#: payload 内容中禁止出现的机器绑定/绝对路径模式（fail closed）。
_FORBIDDEN_CONTENT_PATTERNS = (
    ("windows_absolute_path", re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]")),
    ("posix_home_absolute_path", re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users|mnt|root)/")),
    ("private_key_block", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("openai_style_key", re.compile(r"sk-[A-Za-z0-9]{16,}")),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
)

#: 排除规则（命中即不进入 payload）。
_EXCLUSION_RULES = (
    ("test_tree", re.compile(r"(^|/)(tests?|testing)(/|$)")),
    ("fixture_tree", re.compile(r"(^|/)fixtures?(/|$)")),
    ("pycache_tree", re.compile(r"(^|/)__pycache__(/|$)")),
    ("compiled_bytecode", re.compile(r"\.py[co]$")),
    ("raw_log", re.compile(r"\.log$")),
    ("report_tree", re.compile(r"(^|/)reports?(/|$)")),
)


# --------------------------------------------------------------------------- #
# 错误类型
# --------------------------------------------------------------------------- #


class PackageError(Exception):
    """带稳定错误码的失败。"""

    def __init__(self, code, message, detail=None):
        if code not in EXIT_CODES:
            raise ValueError(f"unknown error code: {code}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}

    def to_dict(self):
        return {
            "error_code": self.code,
            "message": self.message,
            "detail": self.detail,
        }


def _fail(code, message, **detail):
    raise PackageError(code, message, detail or None)


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dump_json(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _emit(obj):
    sys.stdout.write(_dump_json(obj))
    sys.stdout.flush()


def _diag(message):
    text = message.rstrip("\n")
    if _ACTIVE_REDACT_ROOTS:
        text = _redact_text(text, _ACTIVE_REDACT_ROOTS)
    sys.stderr.write(text + "\n")
    sys.stderr.flush()


def _root_variants(roots):
    """脱敏根的原始与解析形式，按长度降序，便于先替换更长的前缀。"""
    variants = set()
    for root in roots or []:
        if not root:
            continue
        variants.add(str(root))
        try:
            variants.add(str(Path(root).resolve()))
        except OSError:
            continue
    return sorted(variants, key=len, reverse=True)


def _redact_text(text, roots):
    """按脱敏根做前缀替换；可正确处理含中文与空格的路径。"""
    result = str(text)
    for variant in _root_variants(roots):
        result = result.replace(variant, "<redacted-root>")
    return result


def _git(repo, args, stdin=None):
    """在指定仓库执行 git 命令，返回 CompletedProcess（不 shell）。"""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc


def _git_text(repo, args, what):
    proc = _git(repo, args)
    if proc.returncode != 0:
        _fail(
            "BAD_INPUT",
            f"git {what} failed",
            git_args=list(args),
            returncode=proc.returncode,
            stderr=proc.stderr.decode("utf-8", "replace").strip(),
        )
    return proc.stdout.decode("utf-8", "replace")


def _is_hex_sha(value):
    return bool(re.fullmatch(r"[0-9a-f]{40}", value or ""))


def _posix_parts(name):
    return PurePosixPath(name).parts


# --------------------------------------------------------------------------- #
# Windows 路径语义与 owned 相对路径校验
# --------------------------------------------------------------------------- #

#: Windows 保留设备名（stem 命中即拒绝，避免在 Windows 上别名成设备）。
_WINDOWS_RESERVED_STEMS = frozenset(
    ["con", "prn", "aux", "nul"]
    + [f"com{number}" for number in range(1, 10)]
    + [f"lpt{number}" for number in range(1, 10)]
)


def _windows_component_key(component):
    """Windows 归一化后的单段名：去掉段尾随点与空格并小写。

    Windows 上 ``zz.py`` 与 ``zz.py.`` 归一化成同一个文件名，段尾随空格同理。
    只做 ``lower()`` 不足以防冲突（独审 m-01）。
    """
    return component.rstrip(" .").lower()


def _windows_path_key(name):
    """整条 POSIX 相对路径的 Windows 归一化键（用于冲突检测）。"""
    return "/".join(_windows_component_key(part) for part in name.split("/"))


def _path_component_problems(component):
    """返回该路径段在 Windows 语义下的问题列表。"""
    problems = []
    if component != component.rstrip(" ."):
        problems.append("windows_trailing_dot_or_space")
    if not component.strip():
        problems.append("blank_path_component")
    stem = component.split(".", 1)[0].lower()
    if stem in _WINDOWS_RESERVED_STEMS:
        problems.append("windows_reserved_device_name")
    return problems


def _validate_owned_relative_path(value, role, kind):
    """校验一条 owned 相对路径。

    kind 为 ``"file"`` 或 ``"directory"``。必须是规范 POSIX 相对路径、落在本轮
    owned 安装前缀之内，并拒绝 ``..``、绝对路径、盘符、反斜杠、Windows 尾随
    点/空格与保留设备名。任何一项不合法即以 ``PATH_REJECTED`` 稳定拒绝。
    """
    if not isinstance(value, str) or not value:
        _fail(
            "PATH_REJECTED",
            f"{role} is not a non-empty relative path",
            role=role,
            kind=kind,
            value=value if isinstance(value, str) else repr(value),
        )
    problems = []
    if "\\" in value:
        problems.append("backslash_separator")
    if value.startswith("//"):
        problems.append("unc_path")
    elif value.startswith("/"):
        problems.append("absolute_path")
    if re.match(r"^[A-Za-z]:", value):
        problems.append("drive_letter")
    if value.endswith("/"):
        problems.append("directory_entry")
    parts = value.split("/")
    if any(part == "" for part in parts):
        problems.append("empty_path_component")
    if any(part == "." for part in parts):
        problems.append("dot_path_component")
    if any(part == ".." for part in parts):
        problems.append("path_traversal")
    for part in parts:
        for problem in _path_component_problems(part):
            problems.append(problem)
    if not problems and PurePosixPath(value).as_posix() != value:
        problems.append("non_canonical_relative_path")
    if not problems:
        if kind == "file":
            if not any(value.startswith(prefix) for prefix in OWNED_INSTALL_PREFIXES):
                problems.append("outside_owned_install_prefix")
        else:
            head = parts[0]
            if head not in OWNED_TOP_LEVEL_DIRS:
                problems.append("outside_owned_install_prefix")
    if problems:
        _fail(
            "PATH_REJECTED",
            f"{role} is not a canonical owned relative path",
            role=role,
            kind=kind,
            value=value,
            problems=problems,
        )
    return value


def _assert_no_symlink_escape(target, relative, role):
    """相对路径解析后必须仍在 target 之内，且沿途没有任何 symlink 段。"""
    try:
        target_resolved = Path(target).resolve()
    except OSError as exc:
        _fail("PATH_REJECTED", f"cannot resolve the install target for {role}", reason=str(exc))
    current = target_resolved
    for part in relative.split("/"):
        current = current / part
        try:
            is_link = current.is_symlink()
        except OSError as exc:
            _fail("PATH_REJECTED", f"cannot inspect {role} path component", reason=str(exc))
        if is_link:
            _fail(
                "PATH_REJECTED",
                f"{role} traverses a symlink",
                role=role,
                relative=relative,
                component=part,
            )
    try:
        resolved = (target_resolved / relative).resolve()
    except OSError as exc:
        _fail("PATH_REJECTED", f"cannot resolve {role}", relative=relative, reason=str(exc))
    if resolved != target_resolved and target_resolved not in resolved.parents:
        _fail(
            "PATH_REJECTED",
            f"{role} escapes the install target",
            role=role,
            relative=relative,
        )
    return resolved


# --------------------------------------------------------------------------- #
# 沙箱 / 宿主路径判定
# --------------------------------------------------------------------------- #


def _path_problem(path):
    """返回该路径被生产宿主硬拒绝的原因；None 表示未命中。"""
    try:
        resolved = Path(path).resolve()
    except OSError:
        resolved = Path(path)
    for part in resolved.parts:
        lowered = part.lower()
        if lowered in PRODUCTION_HOST_COMPONENTS:
            return {
                "reason": "production_host_path_component",
                "component": part,
                "path": str(resolved),
            }
    return None


def _require_not_production_host(path, role):
    problem = _path_problem(path)
    if problem is not None:
        _fail(
            "PATH_REJECTED",
            f"{role} resolves to a rejected production host path",
            role=role,
            **problem,
        )


def _is_within(child, parent):
    """child 是否位于 parent 之内（含相等）。"""
    try:
        child_resolved = Path(child).resolve()
        parent_resolved = Path(parent).resolve()
    except OSError:
        return False
    if child_resolved == parent_resolved:
        return True
    return parent_resolved in child_resolved.parents


def _read_sandbox_marker(sandbox_parent):
    marker_path = Path(sandbox_parent) / SANDBOX_MARKER_NAME
    if not marker_path.is_file():
        _fail(
            "BAD_INPUT",
            "sandbox parent does not carry the sandbox marker file",
            sandbox_parent=str(sandbox_parent),
            marker_path=str(marker_path),
            marker_name=SANDBOX_MARKER_NAME,
            required_magic=SANDBOX_MARKER_MAGIC,
            required_json={"magic": SANDBOX_MARKER_MAGIC, "tool": TOOL_NAME},
        )
    try:
        content = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _fail(
            "BAD_INPUT",
            "sandbox marker file is not readable JSON",
            marker_path=str(marker_path),
            reason=str(exc),
        )
    if not isinstance(content, dict) or content.get("magic") != SANDBOX_MARKER_MAGIC:
        _fail(
            "BAD_INPUT",
            "sandbox marker magic mismatch",
            marker_path=str(marker_path),
            expected_magic=SANDBOX_MARKER_MAGIC,
            found_magic=content.get("magic") if isinstance(content, dict) else None,
        )
    if content.get("tool") != TOOL_NAME:
        _fail(
            "BAD_INPUT",
            "sandbox marker was not issued by this tool",
            marker_path=str(marker_path),
            expected_tool=TOOL_NAME,
            found_tool=content.get("tool") if isinstance(content, dict) else None,
        )
    return {"path": str(marker_path), "sha256": _sha256_file(marker_path), "content": content}


# --------------------------------------------------------------------------- #
# Git 只读访问
# --------------------------------------------------------------------------- #


def _resolve_commit(repo, commit):
    repo_root = _git_text(repo, ["rev-parse", "--show-toplevel"], "rev-parse --show-toplevel").strip()
    spec = f"{commit}^{{commit}}"
    resolved = _git_text(repo, ["rev-parse", "--verify", spec], "rev-parse --verify").strip()
    if not _is_hex_sha(resolved):
        _fail(
            "BAD_INPUT",
            "git did not resolve the candidate to a full commit sha",
            requested=commit,
            resolved=resolved,
        )
    kind = _git_text(repo, ["cat-file", "-t", resolved], "cat-file -t").strip()
    if kind != "commit":
        _fail(
            "BAD_INPUT",
            "candidate object is not a commit",
            commit=resolved,
            object_type=kind,
        )
    return repo_root, resolved


def _list_tree(repo, sha, paths):
    proc = _git(repo, ["ls-tree", "-r", "-z", "--full-tree", sha, "--", *paths])
    if proc.returncode != 0:
        _fail(
            "BAD_INPUT",
            "git ls-tree failed for the candidate commit",
            commit=sha,
            paths=list(paths),
            stderr=proc.stderr.decode("utf-8", "replace").strip(),
        )
    entries = []
    for record in proc.stdout.split(b"\0"):
        if not record:
            continue
        meta, _tab, raw_path = record.partition(b"\t")
        parts = meta.decode("utf-8", "replace").split()
        if len(parts) != 3:
            _fail(
                "INTEGRITY_MISMATCH",
                "unexpected git ls-tree record",
                record=record.decode("utf-8", "replace"),
            )
        mode, object_type, object_id = parts
        entries.append(
            {
                "mode": mode,
                "object_type": object_type,
                "object_id": object_id,
                "path": raw_path.decode("utf-8"),
            }
        )
    return entries


def _read_blobs(repo, sha, paths):
    """一次 cat-file --batch 读取全部 blob，返回 {path: (object_id, bytes)}。"""
    if not paths:
        return {}
    request = "".join(f"{sha}:{path}\n" for path in paths).encode("utf-8")
    proc = _git(repo, ["cat-file", "--batch"], stdin=request)
    if proc.returncode != 0:
        _fail(
            "BAD_INPUT",
            "git cat-file --batch failed",
            commit=sha,
            stderr=proc.stderr.decode("utf-8", "replace").strip(),
        )
    data = proc.stdout
    offset = 0
    results = {}
    for path in paths:
        newline = data.find(b"\n", offset)
        if newline < 0:
            _fail("INTEGRITY_MISMATCH", "truncated git cat-file output", path=path)
        header = data[offset:newline].decode("utf-8", "replace")
        offset = newline + 1
        parts = header.split()
        if len(parts) != 3 or parts[1] == "missing":
            _fail(
                "BAD_INPUT",
                "git object missing for payload path",
                path=path,
                cat_file_header=header,
            )
        object_id, object_type, size_text = parts
        size = int(size_text)
        content = data[offset:offset + size]
        offset += size + 1
        if len(content) != size:
            _fail("INTEGRITY_MISMATCH", "short read from git object", path=path, expected=size)
        results[path] = (object_id, object_type, content)
    return results


def _exclusion_reason(path):
    for name, pattern in _EXCLUSION_RULES:
        if pattern.search(path):
            return name
    return None


def _screen_payload_content(path, content):
    """payload 内容不得携带机器绑定绝对路径或凭据。"""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return None  # 二进制文件不做文本扫描（本合同 payload 只有文本）
    findings = []
    for name, pattern in _FORBIDDEN_CONTENT_PATTERNS:
        match = pattern.search(text)
        if match:
            findings.append(
                {
                    "rule": name,
                    "match": match.group(0)[:80],
                    "offset": match.start(),
                }
            )
    if findings:
        _fail(
            "PATH_REJECTED",
            "payload content carries a machine-bound absolute path or credential",
            source_path=path,
            findings=findings,
        )
    return None


def _git_prefix(repo_root):
    """payload 源目录相对 Git 根的前缀（MasterPack 可能是仓库的子目录）。"""
    pack_root = Path(__file__).resolve().parent.parent
    try:
        relative = pack_root.relative_to(Path(repo_root).resolve())
    except ValueError:
        _fail(
            "BAD_INPUT",
            "the MasterPack directory is not inside the resolved git repository",
            pack_root=str(pack_root),
            repo_root=str(repo_root),
        )
    return relative.as_posix()


def _git_source_path(git_prefix, relative):
    return f"{git_prefix}/{relative}" if git_prefix else relative


def _strip_prefix(path, git_prefix):
    if git_prefix and path.startswith(git_prefix + "/"):
        return path[len(git_prefix) + 1:]
    return path


def _collect_payload(repo, sha, git_prefix=""):
    """选出生产 payload，并记录被排除条目的审计原因。"""
    bridge_dir = _git_source_path(git_prefix, BRIDGE_SOURCE_DIR)
    workflows_dir = _git_source_path(git_prefix, WORKFLOWS_SOURCE_DIR)
    entries = _list_tree(repo, sha, [bridge_dir, workflows_dir])
    selected = []
    excluded = []

    for entry in entries:
        path = entry["path"]
        reason = _exclusion_reason(path)
        if reason is not None:
            excluded.append({"path": path, "reason": reason})
            continue
        if entry["object_type"] != "blob":
            excluded.append({"path": path, "reason": f"not_a_blob:{entry['object_type']}"})
            continue
        if entry["mode"] == "120000":
            excluded.append({"path": path, "reason": "symlink_entry"})
            continue
        if entry["mode"] == "160000":
            excluded.append({"path": path, "reason": "gitlink_entry"})
            continue
        if entry["mode"] not in ("100644", "100755"):
            excluded.append({"path": path, "reason": f"unsupported_mode:{entry['mode']}"})
            continue

        if path.startswith(bridge_dir + "/"):
            rest = path[len(bridge_dir) + 1:]
            if rest.endswith(".py"):
                install_path = f"{BRIDGE_INSTALL_DIR}/{rest}"
            elif rest.startswith("web/") and rest.endswith(".js"):
                if "/" in rest[len("web/"):]:
                    excluded.append({"path": path, "reason": "web_js_not_direct_child"})
                    continue
                install_path = f"{BRIDGE_INSTALL_DIR}/{rest}"
            else:
                excluded.append({"path": path, "reason": "bridge_payload_rule_mismatch"})
                continue
        elif path.startswith(workflows_dir + "/"):
            rest = path[len(workflows_dir) + 1:]
            if not rest.endswith(".json") or "/" in rest:
                excluded.append({"path": path, "reason": "workflow_payload_rule_mismatch"})
                continue
            install_path = f"{WORKFLOWS_INSTALL_DIR}/{rest}"
        else:
            excluded.append({"path": path, "reason": "outside_payload_allowlist"})
            continue

        selected.append(
            {
                "source_path": _strip_prefix(path, git_prefix),
                "git_path": path,
                "install_path": install_path,
                "mode": entry["mode"],
                "object_id": entry["object_id"],
            }
        )

    if not selected:
        _fail("BAD_INPUT", "candidate commit yields an empty payload", commit=sha)

    blobs = _read_blobs(repo, sha, [item["git_path"] for item in selected])
    for item in selected:
        object_id, object_type, content = blobs[item["git_path"]]
        if object_type != "blob":
            _fail(
                "INTEGRITY_MISMATCH",
                "git object type changed between ls-tree and cat-file",
                source_path=item["source_path"],
                expected="blob",
                found=object_type,
            )
        if object_id != item["object_id"]:
            _fail(
                "INTEGRITY_MISMATCH",
                "git object identity mismatch between ls-tree and cat-file",
                source_path=item["source_path"],
                expected_object_id=item["object_id"],
                found_object_id=object_id,
            )
        _screen_payload_content(item["source_path"], content)
        item["content"] = content
        item["length"] = len(content)
        item["sha256"] = _sha256_bytes(content)

    selected.sort(key=lambda item: item["install_path"])
    excluded.sort(key=lambda item: item["path"])
    return selected, excluded


# --------------------------------------------------------------------------- #
# manifest / 包成员
# --------------------------------------------------------------------------- #


def _dependency_notes():
    return [
        "打包工具本身只依赖 Python 3.8+ 标准库：不需要 clone 仓库、不需要 pip、不需要 npm。",
        "安装目标必须是一个带本工具沙箱 marker 的隔离沙箱目录，而不是真实 ComfyUI 宿主。",
        "目标沙箱需要可写，且需要能容纳 custom_nodes/ 与 workflows/ 两个顶层目录。",
        "lvw_v0_bridge 在宿主内运行时会 import numpy 与 Pillow；本离线包不携带也不验证这两个依赖。",
        "视频解码需要宿主内可用的 ffmpeg 可执行文件或 PyAV；本离线包不携带也不验证。",
        "Ollama 端点由 bridge 在运行时通过 http://127.0.0.1:11434 访问；本离线包不携带也不验证。",
    ]


def _non_goal_notes():
    return [
        "不携带模型、权重、媒体、用户稿、凭据或真实宿主配置。",
        "不安装到、不修改真实 ComfyUI 宿主；安装只允许发生在显式沙箱内。",
        "不启动服务、不调用模型、不使用 GPU、不联网、不下载。",
        "不声称可在任意机器使用：只声明在本机已验证宿主上复用宿主既有依赖。",
        "不覆盖已有安装做升级；已有非 owned 内容一律拒绝。",
        "离线包链路不是产品 Gate0，也不是 V0.2 / V1 的验收结论。",
    ]


def _build_manifest(selected, source_commit, tool_info, expanded_bytes):
    tool_manifest_info = {
        "name": tool_info["name"],
        "version": tool_info["version"],
        "sha256": tool_info["sha256"],
        "provenance": tool_info["provenance"],
        "provenance_detail": tool_info["provenance_detail"],
    }
    items = []
    for item in selected:
        items.append(
            {
                "install_path": item["install_path"],
                "package_path": PAYLOAD_PREFIX + item["install_path"],
                "source_path": item["source_path"],
                "source_blob_id": item["object_id"],
                "source_mode": item["mode"],
                "length": item["length"],
                "sha256": item["sha256"],
            }
        )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "package_format_version": PACKAGE_FORMAT_VERSION,
        "source_commit": source_commit,
        "tool": tool_manifest_info,
        "size_limit_bytes": SIZE_LIMIT_BYTES,
        "payload_root": PAYLOAD_PREFIX,
        "payload_item_count": len(items),
        "payload_expanded_bytes": expanded_bytes,
        "items": items,
        "dependencies": _dependency_notes(),
        "non_goals": _non_goal_notes(),
    }


def _fingerprint(items):
    """固定集合 fingerprint：对排序后的 install_path:sha256 求 sha256。"""
    digest = hashlib.sha256()
    for item in sorted(items, key=lambda entry: entry["install_path"]):
        digest.update(f"{item['install_path']}:{item['sha256']}\n".encode("utf-8"))
    return digest.hexdigest()


def _usage_text(source_commit, item_count, expanded_bytes, tool_version):
    return f"""# LVW V0 增量包使用说明（离线，随包分发）

本文件与增量包一同分发，内容由构建工具确定性生成，请勿手工编辑。

## 1. 这是什么

本包是 LVW V0 RuntimePatch 生产 payload 的**离线增量包**，来源是 Git 候选提交
`{source_commit}`。包内只有生产模块与工作流，没有模型、媒体、用户稿或凭据。

* 工具版本：`v0_incremental_package.py` v{tool_version}
* 包格式版本：`{PACKAGE_FORMAT_VERSION}`
* 收据 schema 版本：`{RECEIPT_SCHEMA_VERSION}`
* 目标内所有权记录 schema 版本：`{OWNERSHIP_SCHEMA_VERSION}`
* payload 条目数：{item_count}
* 展开 payload 字节数：{expanded_bytes}
* 体积硬上限：{SIZE_LIMIT_BYTES} 字节（压缩包与展开 payload 分别检查）

## 2. 环境前提

* Python 3.8+，只用标准库。**不需要** clone 仓库、pip 或 npm。
* 包内 `meta/{TOOL_NAME}` 是工具自身的版本化副本，可直接执行：
  `python3 meta/{TOOL_NAME} --help`
* 安装目标必须是**隔离沙箱**，且沙箱父目录必须带本工具的沙箱 marker 文件
  `{SANDBOX_MARKER_NAME}`，内容为：
  `{{"magic": "{SANDBOX_MARKER_MAGIC}", "tool": "{TOOL_NAME}"}}`
* 真实 ComfyUI 宿主路径被硬拒绝，本工具不会写生产宿主。

## 3. 目录布局

安装后目标根目录下新增两个 owned 顶层目录与一份所有权记录：

```
<target>/
  custom_nodes/lvw_v0_bridge/   # 生产节点模块（含 web/*.js 前端脚本）
  workflows/lvw/                # 工作流 JSON
  {OWNERSHIP_FILE_NAME}  # 本轮安装的所有权记录（回滚据此判定所有权）
```

除此之外目标里的其它内容一律不读不写。

## 4. 常用命令

```bash
# 校验包（不写任何文件）
python3 meta/{TOOL_NAME} diagnose --package <包.zip> --target <沙箱目标>

# 安装到显式沙箱
python3 meta/{TOOL_NAME} install --package <包.zip> \\
    --sandbox-parent <沙箱父目录> --target <沙箱目标> --receipt-out <收据.json>

# 按安装收据回滚
python3 meta/{TOOL_NAME} rollback --receipt <收据.json> --target <沙箱目标>
```

三个命令都把结构化 JSON 写到 stdout，诊断信息写到 stderr，非零退出码表示失败。
稳定错误码：`BAD_INPUT`、`INTEGRITY_MISMATCH`、`PATH_REJECTED`、`SIZE_LIMIT`、
`CONFLICT`、`INSTALL_FAILED`、`ROLLBACK_CONFLICT`。

## 5. 安全边界

* build 从显式 Git commit 读字节，不打包脏工作树，绑定完整 commit SHA。
* diagnose 不使用 `extractall`，逐成员检查路径穿越、绝对路径、盘符、反斜杠、
  重复成员、大小写冲突（含 Windows 尾随点/空格归一化）、symlink 与 zip bomb。
* install 只写 owned 路径；已有非 owned 冲突时拒绝且 0 写入；成功时在同一事务内
  写入目标内所有权记录 `{OWNERSHIP_FILE_NAME}`。
* rollback 只承认目标内所有权记录所绑定的安装：逐项比对安装时的 hash；用户改写过
  则报 `ROLLBACK_CONFLICT` 并保留字节。外部收据里的任何路径字段都不是删除授权。
* 工具不含任何任意 shell 执行接口。

## 6. 不是产品验收

本包链路是 S3-PREP-B 的离线准备证据，不构成产品 Gate0、V0.2 或 V1 的验收结论，
也不代表真实宿主已安装或已验证。
"""


def _tool_identity(repo, sha, script_path, git_prefix=""):
    """工具自身的候选身份：优先取 commit 中的字节，否则退回工作树并明确标注。"""
    git_tool_path = _git_source_path(git_prefix, f"tools/{TOOL_NAME}")
    committed = _git(repo, ["cat-file", "blob", f"{sha}:{git_tool_path}"])
    if committed.returncode == 0 and committed.stdout:
        content = committed.stdout
        return {
            "name": TOOL_NAME,
            "version": TOOL_VERSION,
            "sha256": _sha256_bytes(content),
            "provenance": "git_commit",
            "provenance_detail": f"bytes read from commit {sha} at {git_tool_path}",
            "content": content,
        }
    try:
        content = Path(script_path).read_bytes()
    except OSError as exc:
        _fail(
            "BAD_INPUT",
            "cannot read the tool source for packaging",
            path=str(script_path),
            reason=str(exc),
        )
    return {
        "name": TOOL_NAME,
        "version": TOOL_VERSION,
        "sha256": _sha256_bytes(content),
        "provenance": "working_tree_uncommitted",
        "provenance_detail": (
            "tools/" + TOOL_NAME + " is not present in commit " + sha +
            "; these bytes come from the working tree and are NOT claimed to come from that commit"
        ),
        "content": content,
    }


def _zip_write(path, members):
    """确定性 ZIP：固定成员顺序、固定时间戳、固定权限。"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in members:
            info = zipfile.ZipInfo(name, date_time=ZIP_FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ZIP_FIXED_MODE << 16
            info.create_system = 3
            info.file_size = len(data)
            archive.writestr(info, data)


# --------------------------------------------------------------------------- #
# 归档校验（diagnose / install 共用）
# --------------------------------------------------------------------------- #


def _member_name_problems(name):
    problems = []
    if not name:
        return ["empty_member_name"]
    if "\x00" in name:
        problems.append("nul_byte_in_name")
    if "\\" in name:
        problems.append("backslash_separator")
    if name.startswith("/"):
        problems.append("absolute_path")
    if re.match(r"^[A-Za-z]:", name):
        problems.append("drive_letter")
    if name.startswith("//"):
        problems.append("unc_path")
    parts = name.split("/")
    if any(part == "" for part in parts):
        problems.append("empty_path_component")
    if any(part == "." for part in parts):
        problems.append("dot_path_component")
    if any(part == ".." for part in parts):
        problems.append("path_traversal")
    if name.endswith("/"):
        problems.append("directory_entry")
    for part in parts:
        for problem in _path_component_problems(part):
            problems.append(problem)
    return problems


def _member_kind(info):
    """返回成员类型：regular / symlink / other。"""
    if info.create_system == 3:
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            return "symlink"
        if stat.S_ISDIR(mode):
            return "directory"
        return "regular"
    if info.external_attr & 0x10:
        return "directory"
    return "regular"



class _SealedArchive:
    """Private bounded byte source; always runs the complete archive validator."""
    def __init__(self, path, data):
        self.path, self.data = str(path), bytes(data)


_PROTECTED_SUPPORT = (os.name == 'posix' and hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY') and hasattr(os, 'O_NONBLOCK')
            and {os.open, os.mkdir, os.stat, os.rename, os.unlink, os.rmdir}.issubset(os.supports_dir_fd)
            and os.stat in os.supports_follow_symlinks and os.listdir in os.supports_fd)


def _protected_supported():
    return _PROTECTED_SUPPORT


class ProtectedInstall:
    """Finite internal S3 handoff, not a CLI mode or a validation bypass.

    Pins namespace ancestors and preparation directories before validation. All
    target/staging mutations use no-follow, descriptor-relative operations.
    Failure retains both trees, without pathname rollback. POSIX only; native
    Windows is unsupported. A malicious actor moving an already-open inode at
    the syscall boundary can move our owned object; descriptors prevent writing
    through its replacement, not arbitrary relocation of the owned inode.
    """
    def __init__(self, *, target, sandbox_parent, package_path, package_sha256,
                 manifest_sha256, candidate_sha):
        self.target, self.parent, self.package_path = map(Path, (target, sandbox_parent, package_path))
        self.expected = package_sha256, manifest_sha256, candidate_sha
        self.fds, self.edges = [], []
        self.active = self.used = False
        self.stage = None
        self.committed = []

    @staticmethod
    def _identity(info):
        return info.st_dev, info.st_ino

    @staticmethod
    def _file_identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    def _open_dir(self, parent, name, *, track=False):
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        self.fds.append(fd)
        if track:
            self.edges.append((parent, name, fd, self._identity(os.fstat(fd))))
        return fd

    def _chain(self, path):
        if not path.is_absolute() or '..' in path.parts:
            _fail('PATH_REJECTED', 'protected path must be canonical absolute')
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.fds.append(fd)
        for name in path.parts[1:]:
            fd = self._open_dir(fd, name, track=True)
        return fd

    def __enter__(self):
        if not _protected_supported():
            _fail('PATH_REJECTED', 'protected install requires POSIX no-follow directory descriptors')
        try:
            if self.target.parent != self.parent:
                _fail('PATH_REJECTED', 'protected target must be a direct sandbox child')
            for path in (self.parent, self.target):
                _require_not_production_host(path, 'protected install')
            self.parent_fd = self._chain(self.parent)
            self.target_fd = self._open_dir(self.parent_fd, self.target.name, track=True)
            expected = {'input', 'output', 'temp', 'custom_nodes'}
            if set(os.listdir(self.target_fd)) != expected:
                _fail('CONFLICT', 'protected install requires fresh preparation directories')
            self.parents = {}
            for name in sorted(expected):
                fd = self._open_dir(self.target_fd, name, track=True)
                if os.listdir(fd):
                    _fail('CONFLICT', 'protected preparation directory is not empty')
                self.parents[name] = fd
            self.package_parent_fd = self._chain(self.package_path.parent)
            fd = os.open(self.package_path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=self.package_parent_fd)
            self.fds.append(fd)
            self.archive_fd = fd
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > SIZE_LIMIT_BYTES:
                _fail('SIZE_LIMIT', 'protected archive must be regular and bounded')
            self.archive_identity = self._file_identity(before)
            chunks = []; remaining = before.st_size
            while remaining:
                chunk = os.read(fd, min(remaining, 1024 * 1024))
                if not chunk:
                    _fail('INTEGRITY_MISMATCH', 'protected archive truncated')
                chunks.append(chunk); remaining -= len(chunk)
            self.archive = _SealedArchive(self.package_path, b''.join(chunks))
            marker_raw = self._read(self.parent_fd, SANDBOX_MARKER_NAME)
            content = json.loads(marker_raw)
            if content.get('magic') != SANDBOX_MARKER_MAGIC or content.get('tool') != TOOL_NAME:
                _fail('BAD_INPUT', 'protected sandbox marker mismatch')
            self.marker = {'path': str(self.parent / SANDBOX_MARKER_NAME),
                           'sha256': _sha256_bytes(marker_raw), 'content': content}
            self.active = True
            self.check()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *unused):
        self.active = False
        for fd in reversed(self.fds):
            os.close(fd)
        self.fds.clear()

    def check(self):
        if not self.active:
            _fail('BAD_INPUT', 'protected handoff is closed')
        self._check_directories()
        current = os.stat(self.package_path.name, dir_fd=self.package_parent_fd, follow_symlinks=False)
        if (not stat.S_ISREG(current.st_mode) or self._file_identity(current) != self.archive_identity
                or self._file_identity(os.fstat(self.archive_fd)) != self.archive_identity):
            _fail('PATH_REJECTED', 'protected archive identity drift')
        if _sha256_bytes(self._read(self.parent_fd, SANDBOX_MARKER_NAME)) != self.marker['sha256']:
            _fail('PATH_REJECTED', 'protected marker drift')

    def _check_directories(self):
        for parent, name, fd, identity in self.edges:
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(current.st_mode) or self._identity(current) != identity or self._identity(os.fstat(fd)) != identity:
                _fail('PATH_REJECTED', 'protected directory identity drift', component=name)

    def save_receipt(self, name, receipt):
        if not self.active or Path(name).name != name:
            _fail('BAD_INPUT', 'protected receipt name/context invalid')
        self._check_directories()
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.parent_fd)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(_dump_json(receipt).encode('utf-8'))
            stream.flush(); os.fsync(stream.fileno())
        self._check_directories()

    def validate(self):
        self.check()
        validation = _validate_archive(self.archive)
        if (validation['package_sha256'], validation['manifest_sha256'], validation['source_commit']) != self.expected:
            _fail('INTEGRITY_MISMATCH', 'protected candidate/package/manifest binding mismatch')
        for item in validation['items']:
            _validate_owned_relative_path(item['install_path'], 'protected payload', 'file')
        self.check()
        return validation

    def _read(self, parent, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > SIZE_LIMIT_BYTES:
                _fail('SIZE_LIMIT', 'protected file must be regular and bounded')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                data = stream.read(SIZE_LIMIT_BYTES + 1)
            if len(data) != info.st_size or self._file_identity(os.fstat(fd)) != self._file_identity(info):
                _fail('INTEGRITY_MISMATCH', 'protected file drift during read')
            return data
        finally:
            os.close(fd)

    def _write(self, parent, name, data):
        self.check()
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(data); stream.flush(); os.fsync(fd)
        finally:
            os.close(fd)
        self.check()

    def install(self, args):
        if (not self.active or self.used or Path(args.target) != self.target
                or Path(args.sandbox_parent) != self.parent or Path(args.package) != self.package_path
                or args.manifest is not None or args.receipt_out is not None):
            _fail('BAD_INPUT', 'protected handoff arguments/replay rejected')
        self.used = True
        try:
            return self._install(args)
        except BaseException as error:
            # No path-based rollback or deletion follows a failed mutation.
            # The caller also fences inherited archival for this uncertain root.
            detail = error.to_dict() if isinstance(error, PackageError) else {'type': type(error).__name__, 'message': str(error)}
            raise PackageError('INSTALL_FAILED', 'protected install failed; owned trees retained', {
                'original_failure': detail, 'cleanup': {'proven': False,
                'policy': 'RETAIN_NO_PATHNAME_ROLLBACK', 'target': str(self.target),
                'staging': str(self.stage) if self.stage else None,
                'committed': list(self.committed)}}) from error

    def _install(self, args):
        validation = self.validate()  # Never accepts a caller-supplied validation dict.
        items = validation['items']; manifest = validation['manifest']
        preimage = {'files': [], 'directories': sorted(self.parents)}
        self.check()
        name = STAGING_DIR_PREFIX + uuid.uuid4().hex
        os.mkdir(name, 0o700, dir_fd=self.parent_fd)
        self.stage = self.parent / name
        stage_fd = self._open_dir(self.parent_fd, name)
        stage_identity = self._identity(os.fstat(stage_fd))
        dirs = {'': stage_fd}
        owned_files = []
        for item in items:
            parts = item['install_path'].split('/')
            for index in range(1, len(parts)):
                relative = '/'.join(parts[:index])
                if relative not in dirs:
                    self.check()
                    parent_fd = dirs['/'.join(parts[:index - 1])]
                    os.mkdir(parts[index - 1], 0o700, dir_fd=parent_fd)
                    dirs[relative] = self._open_dir(parent_fd, parts[index - 1])
            data = validation['contents'][item['package_path']]
            self._write(dirs['/'.join(parts[:-1])], parts[-1], data)
            if self._read(dirs['/'.join(parts[:-1])], parts[-1]) != data:
                _fail('INTEGRITY_MISMATCH', 'protected staged payload changed')
            owned_files.append({'install_path': item['install_path'], 'sha256': item['sha256'], 'length': item['length']})
        self.check()
        os.mkdir('workflows', 0o700, dir_fd=self.target_fd)
        self.parents['workflows'] = self._open_dir(self.target_fd, 'workflows', track=True)
        for relative in (BRIDGE_INSTALL_DIR, WORKFLOWS_INSTALL_DIR):
            parent, leaf = relative.split('/')
            self.check()
            if os.listdir(self.parents[parent]):
                _fail('CONFLICT', 'protected destination is no longer empty')
            source_identity = self._identity(os.fstat(dirs[relative]))
            current = os.stat(leaf, dir_fd=dirs[parent], follow_symlinks=False)
            if not stat.S_ISDIR(current.st_mode) or self._identity(current) != source_identity:
                _fail('PATH_REJECTED', 'protected staged directory replaced')
            os.rename(leaf, leaf, src_dir_fd=dirs[parent], dst_dir_fd=self.parents[parent])
            self.committed.append(relative)
            self.check()
            current = os.stat(leaf, dir_fd=self.parents[parent], follow_symlinks=False)
            if self._identity(current) != source_identity:
                _fail('PATH_REJECTED', 'protected installed directory replaced')
            self.edges.append((self.parents[parent], leaf, dirs[relative], source_identity))
        for item in items:
            parts = item['install_path'].split('/')
            if _sha256_bytes(self._read(dirs['/'.join(parts[:-1])], parts[-1])) != item['sha256']:
                _fail('INTEGRITY_MISMATCH', 'protected installed payload changed')
        self.check()
        # Staging now contains only the two empty parent dirs. Remove only
        # entries whose inode matches the open original, relative to pinned fds.
        for parent in ('custom_nodes', 'workflows'):
            current = os.stat(parent, dir_fd=stage_fd, follow_symlinks=False)
            if self._identity(current) != self._identity(os.fstat(dirs[parent])):
                _fail('PATH_REJECTED', 'protected staging parent replaced')
            os.rmdir(parent, dir_fd=stage_fd)
        current = os.stat(name, dir_fd=self.parent_fd, follow_symlinks=False)
        if self._identity(current) != stage_identity:
            _fail('PATH_REJECTED', 'protected staging root replaced')
        os.rmdir(name, dir_fd=self.parent_fd)
        session_id = args.session_id or ('sess-' + uuid.uuid4().hex)
        owned_dirs = sorted(relative for relative in dirs if '/' in relative)
        record = _build_ownership_record(session_id=session_id, target=self.target,
            sandbox_parent=self.parent, marker=self.marker, package_sha256=validation['package_sha256'],
            manifest_sha256=validation['manifest_sha256'], source_commit=manifest['source_commit'],
            payload_fingerprint=_fingerprint(items), owned_files=owned_files, owned_dirs=owned_dirs,
            created_dirs=['workflows'], installed_top_level=self.committed, created_target_root=False, staging=self.stage)
        raw = _dump_json(record).encode('utf-8')
        self._write(self.target_fd, OWNERSHIP_FILE_NAME, raw)
        self.check()
        if self._read(self.target_fd, OWNERSHIP_FILE_NAME) != raw:
            _fail('INTEGRITY_MISMATCH', 'protected owner bytes changed')
        return {'schema_version': RECEIPT_SCHEMA_VERSION, 'command': 'install', 'status': 'OK',
            'session_id': session_id, 'tool': {'name': TOOL_NAME, 'version': TOOL_VERSION},
            'ownership_schema_version': OWNERSHIP_SCHEMA_VERSION, 'source_commit': manifest['source_commit'],
            'package': {'path': str(self.package_path), 'sha256': validation['package_sha256'], 'size_bytes': validation['package_size_bytes']},
            'manifest': {'sha256': validation['manifest_sha256'], 'member': MANIFEST_MEMBER, 'content': manifest},
            'sandbox_parent': str(self.parent), 'sandbox_parent_sha256': _sha256_bytes(str(self.parent).encode()),
            'sandbox_marker': {'path': self.marker['path'], 'sha256': self.marker['sha256']},
            'target': str(self.target), 'target_identity_sha256': _sha256_bytes(str(self.target).encode()),
            'created_target_root': False, 'preimage': preimage,
            'owned': {'files': owned_files, 'directories': owned_dirs, 'created_directories': ['workflows']},
            'installed_top_level': list(self.committed),
            'staging': {'path': str(self.stage), 'path_sha256': _sha256_bytes(str(self.stage).encode()), 'removed': True},
            'ownership': {'schema_version': OWNERSHIP_SCHEMA_VERSION, 'path': OWNERSHIP_FILE_NAME,
                          'sha256': _sha256_bytes(raw), 'install_hash': record['install_hash']},
            'checks': validation['checks'], 'protected_source': {'path': str(self.package_path),
                'file_identity': list(self.archive_identity), 'sha256': _sha256_bytes(self.archive.data),
                'bytes': len(self.archive.data), 'mode': 'BOUNDED_NOFOLLOW_SNAPSHOT_POSIX'},
            'note': 'Protected deployment only; no real-host or rollback acceptance.'}


def _validate_archive(package_path, expect_manifest=None):
    """完整归档校验。返回结构化结果；失败抛 PackageError。"""
    sealed = package_path if isinstance(package_path, _SealedArchive) else None
    package_path = Path(sealed.path if sealed else package_path)
    if sealed is None and not package_path.is_file():
        _fail("BAD_INPUT", "package file does not exist", package=str(package_path))
    package_size = len(sealed.data) if sealed else package_path.stat().st_size
    if package_size > SIZE_LIMIT_BYTES:
        _fail(
            "SIZE_LIMIT",
            "compressed package exceeds the hard size limit",
            package=str(package_path),
            package_size=package_size,
            limit=SIZE_LIMIT_BYTES,
        )

    checks = []

    def record(name, passed, **detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    try:
        archive = zipfile.ZipFile(io.BytesIO(sealed.data) if sealed else package_path, "r")
    except (zipfile.BadZipFile, OSError) as exc:
        _fail(
            "INTEGRITY_MISMATCH",
            "package is not a readable zip archive",
            package=str(package_path),
            reason=str(exc),
        )

    with archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]

        # --- 成员名安全性 -------------------------------------------------- #
        name_problems = []
        for info in infos:
            problems = _member_name_problems(info.filename)
            if problems:
                name_problems.append({"member": info.filename, "problems": problems})
        record("member_path_safety", not name_problems, problems=name_problems)
        if name_problems:
            _fail(
                "PATH_REJECTED",
                "package contains unsafe member names",
                package=str(package_path),
                problems=name_problems,
            )

        # --- 重复成员 / 大小写冲突（Windows 语义） ------------------------- #
        duplicates = sorted({name for name in names if names.count(name) > 1})
        case_groups = {}
        for name in names:
            case_groups.setdefault(_windows_path_key(name), set()).add(name)
        case_collisions = sorted(
            sorted(group) for group in case_groups.values() if len(group) > 1
        )
        record(
            "member_uniqueness",
            not duplicates and not case_collisions,
            duplicates=duplicates,
            case_insensitive_collisions=case_collisions,
        )
        if duplicates or case_collisions:
            _fail(
                "PATH_REJECTED",
                "package contains duplicate or case-colliding members",
                package=str(package_path),
                duplicates=duplicates,
                case_insensitive_collisions=case_collisions,
            )

        # --- symlink / reparse --------------------------------------------- #
        non_regular = [
            {"member": info.filename, "kind": _member_kind(info)}
            for info in infos
            if _member_kind(info) != "regular"
        ]
        record("member_kind_regular_files", not non_regular, offenders=non_regular)
        if non_regular:
            _fail(
                "PATH_REJECTED",
                "package contains symlink or directory members",
                package=str(package_path),
                offenders=non_regular,
            )

        # --- 体积上限与 zip bomb ------------------------------------------ #
        payload_members = {info.filename for info in infos if info.filename.startswith(PAYLOAD_PREFIX)}
        total_expanded = sum(info.file_size for info in infos)
        payload_expanded = sum(
            info.file_size for info in infos if info.filename in payload_members
        )
        total_compressed = sum(info.compress_size for info in infos)
        archive_ratio = (total_expanded / total_compressed) if total_compressed else float("inf")
        member_ratio_offenders = []
        for info in infos:
            if info.compress_size == 0:
                if info.file_size > 0:
                    member_ratio_offenders.append({"member": info.filename, "ratio": None})
                continue
            ratio = info.file_size / info.compress_size
            if ratio > ZIP_BOMB_MEMBER_RATIO_LIMIT:
                member_ratio_offenders.append(
                    {"member": info.filename, "ratio": round(ratio, 2)}
                )
        size_detail = {
            "package_size_bytes": package_size,
            "payload_expanded_bytes": payload_expanded,
            "total_expanded_bytes": total_expanded,
            "total_compressed_bytes": total_compressed,
            "archive_ratio": round(archive_ratio, 2) if total_expanded else 0,
            "archive_ratio_limit": ZIP_BOMB_RATIO_LIMIT,
            "member_ratio_offenders": member_ratio_offenders,
            "limit_bytes": SIZE_LIMIT_BYTES,
        }
        size_ok = (
            package_size <= SIZE_LIMIT_BYTES
            and payload_expanded <= SIZE_LIMIT_BYTES
            and (sealed is None or total_expanded <= SIZE_LIMIT_BYTES)
            and archive_ratio <= ZIP_BOMB_RATIO_LIMIT
            and not member_ratio_offenders
        )
        record("size_limits_and_zip_bomb", size_ok, **size_detail)
        if package_size > SIZE_LIMIT_BYTES:
            _fail("SIZE_LIMIT", "compressed package exceeds the hard size limit", **size_detail)
        if payload_expanded > SIZE_LIMIT_BYTES:
            _fail("SIZE_LIMIT", "expanded payload exceeds the hard size limit", **size_detail)
        if sealed is not None and total_expanded > SIZE_LIMIT_BYTES:
            _fail("SIZE_LIMIT", "protected archive total expansion exceeds limit", **size_detail)
        if archive_ratio > ZIP_BOMB_RATIO_LIMIT or member_ratio_offenders:
            _fail("SIZE_LIMIT", "package looks like a zip bomb", **size_detail)

        # --- 读出成员内容并核对声明长度 ----------------------------------- #
        contents = {}
        length_mismatch = []
        for info in infos:
            try:
                data = archive.read(info.filename)
            except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
                _fail(
                    "INTEGRITY_MISMATCH",
                    "member cannot be decompressed",
                    member=info.filename,
                    reason=str(exc),
                )
            if len(data) != info.file_size:
                length_mismatch.append(
                    {"member": info.filename, "declared": info.file_size, "actual": len(data)}
                )
            contents[info.filename] = data
        record("member_declared_length", not length_mismatch, offenders=length_mismatch)
        if length_mismatch:
            _fail(
                "INTEGRITY_MISMATCH",
                "member length does not match the zip declaration",
                offenders=length_mismatch,
            )

        # --- 成员集合 ------------------------------------------------------- #
        for required in (MANIFEST_MEMBER, TOOL_MEMBER, USAGE_MEMBER):
            if required not in contents:
                _fail(
                    "INTEGRITY_MISMATCH",
                    "package is missing a required member",
                    member=required,
                    present=sorted(contents),
                )
        payload_members = {name for name in contents if name.startswith(PAYLOAD_PREFIX)}
        meta_members = {name for name in contents if name.startswith(META_PREFIX)}
        stray = sorted(set(contents) - payload_members - meta_members)
        record("member_set_layout", not stray, stray_members=stray)
        if stray:
            _fail(
                "PATH_REJECTED",
                "package contains members outside the payload/meta layout",
                stray_members=stray,
            )

        # --- manifest ------------------------------------------------------- #
        manifest_bytes = contents[MANIFEST_MEMBER]
        try:
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            _fail(
                "INTEGRITY_MISMATCH",
                "manifest member is not valid UTF-8 JSON",
                reason=str(exc),
            )
        if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            _fail(
                "INTEGRITY_MISMATCH",
                "manifest schema_version mismatch",
                expected=MANIFEST_SCHEMA_VERSION,
                found=manifest.get("schema_version"),
            )
        if manifest.get("package_format_version") != PACKAGE_FORMAT_VERSION:
            _fail(
                "INTEGRITY_MISMATCH",
                "manifest package_format_version mismatch",
                expected=PACKAGE_FORMAT_VERSION,
                found=manifest.get("package_format_version"),
            )
        if expect_manifest is not None:
            try:
                external_text = Path(expect_manifest).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                _fail(
                    "BAD_INPUT",
                    "external manifest file is not readable UTF-8 text",
                    external_manifest=str(expect_manifest),
                    reason=str(exc),
                )
            try:
                external = json.loads(external_text)
            except ValueError as exc:
                _fail(
                    "BAD_INPUT",
                    "external manifest file is not valid JSON",
                    external_manifest=str(expect_manifest),
                    reason=str(exc),
                )
            if not isinstance(external, dict):
                _fail(
                    "BAD_INPUT",
                    "external manifest file is not a JSON object",
                    external_manifest=str(expect_manifest),
                )
            if _sha256_bytes(_dump_json(external).encode("utf-8")) != _sha256_bytes(
                _dump_json(manifest).encode("utf-8")
            ):
                _fail(
                    "INTEGRITY_MISMATCH",
                    "external manifest does not match the manifest inside the package",
                    external_manifest=str(expect_manifest),
                )

        items = manifest.get("items")
        if not isinstance(items, list) or not items:
            _fail("INTEGRITY_MISMATCH", "manifest carries no items")

        manifest_paths = []
        integrity_problems = []
        for item in items:
            install_path = item.get("install_path")
            package_path_member = item.get("package_path")
            if not isinstance(install_path, str) or not isinstance(package_path_member, str):
                _fail("INTEGRITY_MISMATCH", "manifest item is malformed", item=item)
            problems = _member_name_problems(package_path_member)
            if problems:
                _fail(
                    "PATH_REJECTED",
                    "manifest item points at an unsafe package path",
                    install_path=install_path,
                    problems=problems,
                )
            if package_path_member != PAYLOAD_PREFIX + install_path:
                _fail(
                    "INTEGRITY_MISMATCH",
                    "manifest item package_path is inconsistent with install_path",
                    install_path=install_path,
                    package_path=package_path_member,
                )
            data = contents.get(package_path_member)
            if data is None:
                integrity_problems.append(
                    {"install_path": install_path, "problem": "missing_package_member"}
                )
                continue
            if item.get("length") != len(data):
                integrity_problems.append(
                    {
                        "install_path": install_path,
                        "problem": "length_mismatch",
                        "manifest_length": item.get("length"),
                        "actual_length": len(data),
                    }
                )
            digest = _sha256_bytes(data)
            if item.get("sha256") != digest:
                integrity_problems.append(
                    {
                        "install_path": install_path,
                        "problem": "sha256_mismatch",
                        "manifest_sha256": item.get("sha256"),
                        "actual_sha256": digest,
                    }
                )
            manifest_paths.append(package_path_member)
        record("manifest_item_integrity", not integrity_problems, problems=integrity_problems)
        if integrity_problems:
            _fail(
                "INTEGRITY_MISMATCH",
                "manifest does not match the packaged payload",
                problems=integrity_problems,
            )

        extra_payload = sorted(payload_members - set(manifest_paths))
        missing_payload = sorted(set(manifest_paths) - payload_members)
        record(
            "manifest_entry_set",
            not extra_payload and not missing_payload,
            extra_payload_members=extra_payload,
            missing_payload_members=missing_payload,
        )
        if extra_payload or missing_payload:
            _fail(
                "INTEGRITY_MISMATCH",
                "packaged payload member set does not equal the manifest item set",
                extra_payload_members=extra_payload,
                missing_payload_members=missing_payload,
            )

        declared_expanded = manifest.get("payload_expanded_bytes")
        if declared_expanded is not None and declared_expanded != payload_expanded:
            _fail(
                "INTEGRITY_MISMATCH",
                "manifest payload_expanded_bytes does not match the packaged payload",
                manifest_payload_expanded_bytes=declared_expanded,
                actual_payload_expanded_bytes=payload_expanded,
            )
        if manifest.get("payload_item_count") not in (None, len(items)):
            _fail(
                "INTEGRITY_MISMATCH",
                "manifest payload_item_count does not match the manifest items",
                manifest_payload_item_count=manifest.get("payload_item_count"),
                actual_item_count=len(items),
            )

        # --- 工具副本与使用说明 -------------------------------------------- #
        tool_info = manifest.get("tool") or {}
        tool_bytes = contents[TOOL_MEMBER]
        tool_digest = _sha256_bytes(tool_bytes)
        tool_ok = tool_info.get("sha256") == tool_digest and tool_info.get("name") == TOOL_NAME
        record("tool_copy_matches_manifest", tool_ok, manifest=tool_info, actual_sha256=tool_digest)
        if not tool_ok:
            _fail(
                "INTEGRITY_MISMATCH",
                "packaged tool copy does not match the manifest tool identity",
                manifest=tool_info,
                actual_sha256=tool_digest,
            )
        usage_bytes = contents[USAGE_MEMBER]
        try:
            usage_text = usage_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            _fail("INTEGRITY_MISMATCH", "usage document is not valid UTF-8", reason=str(exc))
        usage_ok = manifest.get("source_commit", "") in usage_text
        record("usage_document_present", usage_ok, member=USAGE_MEMBER, length=len(usage_bytes))
        if not usage_ok:
            _fail(
                "INTEGRITY_MISMATCH",
                "usage document does not reference the manifest source commit",
                source_commit=manifest.get("source_commit"),
            )

        return {
            "package_path": str(package_path),
            "package_sha256": _sha256_bytes(sealed.data) if sealed else _sha256_file(package_path),
            "package_size_bytes": package_size,
            "manifest": manifest,
            "manifest_sha256": _sha256_bytes(manifest_bytes),
            "contents": contents,
            "items": items,
            "payload_expanded_bytes": payload_expanded,
            "checks": checks,
            "source_commit": manifest.get("source_commit"),
        }


# --------------------------------------------------------------------------- #
# 脱敏
# --------------------------------------------------------------------------- #


def _redact(path, roots):
    if path is None:
        return None
    text = str(path)
    if not roots:
        return "<abs-path-redacted>"
    for root in roots:
        try:
            root_resolved = Path(root).resolve()
            candidate = Path(text).resolve()
        except OSError:
            continue
        if candidate == root_resolved:
            return "<redacted-root>"
        try:
            relative = candidate.relative_to(root_resolved)
        except ValueError:
            continue
        return "<redacted-root>/" + relative.as_posix()
    return "<abs-path-redacted>"


def _redact_tree(node, roots):
    """递归替换 dict 中的绝对路径字符串。"""
    if isinstance(node, dict):
        return {key: _redact_tree(value, roots) for key, value in node.items()}
    if isinstance(node, list):
        return [_redact_tree(value, roots) for value in node]
    if isinstance(node, str) and (node.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", node)):
        return _redact(node, roots)
    return node


#: 当前生效的脱敏根（main() 设置）；影响 stderr 诊断行。
_ACTIVE_REDACT_ROOTS = []


# --------------------------------------------------------------------------- #
# 子命令：build
# --------------------------------------------------------------------------- #


def command_build(args):
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        _fail("BAD_INPUT", "repository path is not a directory", repo=str(repo))
    _require_not_production_host(repo, "repo")

    repo_root, sha = _resolve_commit(repo, args.commit)
    git_prefix = _git_prefix(repo_root)
    _diag(f"[build] candidate commit {sha} (requested {args.commit})")
    _diag(f"[build] payload git prefix: {git_prefix or '<repo root>'}")

    status = _git_text(repo, ["status", "--porcelain"], "status --porcelain").strip()
    dirty_paths = [line for line in status.splitlines() if line.strip()]
    _diag(f"[build] worktree dirty paths: {len(dirty_paths)} (payload bytes are read from git objects)")

    selected, excluded = _collect_payload(repo, sha, git_prefix)
    _diag(f"[build] payload items: {len(selected)}; excluded entries: {len(excluded)}")

    tool_info = _tool_identity(repo, sha, Path(__file__).resolve(), git_prefix)
    _diag(f"[build] tool provenance: {tool_info['provenance']}")

    expanded_bytes = sum(item["length"] for item in selected)
    if expanded_bytes > SIZE_LIMIT_BYTES:
        _fail(
            "SIZE_LIMIT",
            "expanded payload exceeds the hard size limit",
            payload_expanded_bytes=expanded_bytes,
            limit=SIZE_LIMIT_BYTES,
        )

    manifest = _build_manifest(selected, sha, tool_info, expanded_bytes)
    manifest_bytes = _dump_json(manifest).encode("utf-8")
    usage_bytes = _usage_text(sha, len(selected), expanded_bytes, TOOL_VERSION).encode("utf-8")

    members = [(MANIFEST_MEMBER, manifest_bytes), (TOOL_MEMBER, tool_info["content"]),
               (USAGE_MEMBER, usage_bytes)]
    for item in selected:
        members.append((PAYLOAD_PREFIX + item["install_path"], item["content"]))
    members.sort(key=lambda entry: entry[0])

    out_path = Path(args.out).expanduser()
    if out_path.exists():
        _fail(
            "CONFLICT",
            "output package already exists; refusing to overwrite",
            output=str(out_path),
        )
    if not out_path.parent.is_dir():
        _fail(
            "BAD_INPUT",
            "output parent directory does not exist",
            output_parent=str(out_path.parent),
        )

    handle, temp_name = tempfile.mkstemp(
        dir=str(out_path.parent), prefix=".lvw-v0-package-", suffix=".tmp"
    )
    os.close(handle)
    temp_path = Path(temp_name)
    try:
        _zip_write(temp_path, members)
        temp_size = temp_path.stat().st_size
        if temp_size > SIZE_LIMIT_BYTES:
            _fail(
                "SIZE_LIMIT",
                "compressed package exceeds the hard size limit",
                package_size=temp_size,
                limit=SIZE_LIMIT_BYTES,
            )
        validation = _validate_archive(temp_path)
        _diag(f"[build] self-verification passed ({len(validation['checks'])} checks)")

        payload_fingerprint = _fingerprint(
            [{"install_path": item["install_path"], "sha256": item["sha256"]} for item in selected]
        )
        os.replace(str(temp_path), str(out_path))
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    package_sha256 = _sha256_file(out_path)
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "command": "build",
        "status": "OK",
        "tool": {
            "name": TOOL_NAME,
            "version": TOOL_VERSION,
            "sha256": tool_info["sha256"],
            "provenance": tool_info["provenance"],
        },
        "repo": str(repo_root),
        "source_commit": sha,
        "requested_commit": args.commit,
        "worktree_dirty_path_count": len(dirty_paths),
        "package": {
            "path": str(out_path),
            "sha256": package_sha256,
            "size_bytes": out_path.stat().st_size,
        },
        "manifest": {
            "sha256": _sha256_bytes(manifest_bytes),
            "member": MANIFEST_MEMBER,
            "item_count": len(selected),
        },
        "payload": {
            "expanded_bytes": expanded_bytes,
            "fingerprint_sha256": payload_fingerprint,
            "items": [
                {
                    "install_path": item["install_path"],
                    "source_path": item["source_path"],
                    "source_blob_id": item["object_id"],
                    "length": item["length"],
                    "sha256": item["sha256"],
                }
                for item in selected
            ],
        },
        "excluded_entries": excluded,
        "checks": validation["checks"],
        "limits": {"size_limit_bytes": SIZE_LIMIT_BYTES},
    }
    if args.receipt_out:
        _write_receipt(args.receipt_out, receipt, args.redact_root)
    return receipt


def _write_receipt(path, receipt, redact_roots=None):
    target = Path(path).expanduser()
    if not target.parent.is_dir():
        target.parent.mkdir(parents=True, exist_ok=True)
    payload = receipt
    if redact_roots:
        payload = _redact_tree(receipt, redact_roots)
    target.write_text(_dump_json(payload), encoding="utf-8")
    _diag(f"[receipt] written to {target}")


# --------------------------------------------------------------------------- #
# 子命令：diagnose
# --------------------------------------------------------------------------- #


def command_diagnose(args):
    validation = _validate_archive(args.package, args.manifest)
    _diag(
        f"[diagnose] package validated: {len(validation['checks'])} checks, "
        f"{len(validation['items'])} payload items, "
        f"manifest sha256 {validation['manifest_sha256']}"
    )
    target_report = None
    if args.target:
        target_report = _inspect_target(Path(args.target), args.sandbox_parent)
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "command": "diagnose",
        "status": "OK",
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "package": {
            "path": validation["package_path"],
            "sha256": validation["package_sha256"],
            "size_bytes": validation["package_size_bytes"],
        },
        "manifest": {
            "sha256": validation["manifest_sha256"],
            "source_commit": validation["source_commit"],
            "item_count": len(validation["items"]),
        },
        "payload_expanded_bytes": validation["payload_expanded_bytes"],
        "checks": validation["checks"],
        "target": target_report,
        "note": (
            "diagnose only verifies; it never writes to the target and never extracts "
            "with extractall"
        ),
    }
    if args.receipt_out:
        _write_receipt(args.receipt_out, receipt, args.redact_root)
    return receipt


def _inspect_target(target, sandbox_parent):
    """只读检查 target：可写性、隔离 marker、生产宿主拒绝。"""
    report = {"path": str(target), "checks": []}

    def record(name, passed, **detail):
        report["checks"].append({"name": name, "passed": bool(passed), "detail": detail})

    problem = _path_problem(target)
    record(
        "target_not_production_host",
        problem is None,
        problem=problem,
    )
    if problem is not None:
        _fail(
            "PATH_REJECTED",
            "target resolves to a rejected production host path",
            **problem,
        )

    if sandbox_parent:
        if not _is_within(target, sandbox_parent):
            _fail(
                "PATH_REJECTED",
                "target is not inside the explicitly provided sandbox parent",
                target=str(target),
                sandbox_parent=str(sandbox_parent),
            )
        marker = _read_sandbox_marker(sandbox_parent)
        record("sandbox_marker_present", True, marker_path=marker["path"])
    else:
        record("sandbox_marker_checked", False, reason="no --sandbox-parent given")

    exists = target.exists()
    writable = os.access(target, os.W_OK) if exists else os.access(target.parent, os.W_OK)
    record(
        "target_writable",
        writable,
        exists=exists,
        is_directory=target.is_dir() if exists else None,
    )
    if exists and not target.is_dir():
        _fail("BAD_INPUT", "target exists and is not a directory", target=str(target))
    report["exists"] = exists
    report["writable"] = bool(writable)
    return report


# --------------------------------------------------------------------------- #
# 目标内所有权记录（correction-01）
# --------------------------------------------------------------------------- #


def _owned_files_signature(entries):
    """owned 文件集合的稳定签名；格式不合法时返回 None。"""
    if not isinstance(entries, list):
        return None
    signature = []
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        signature.append(
            (entry.get("install_path"), entry.get("sha256"), entry.get("length"))
        )
    return signature


def _ownership_core(record):
    """参与 install_hash 计算的身份字段（不含 install_hash 自身）。"""
    return {
        "schema_version": record["schema_version"],
        "session_id": record["session_id"],
        "target_identity": record["target_identity"],
        "sandbox_parent": record["sandbox_parent"],
        "sandbox_marker_sha256": record["sandbox_marker"]["sha256"],
        "source_commit": record["source_commit"],
        "manifest_sha256": record["manifest_sha256"],
        "package_sha256": record["package_sha256"],
        "payload_fingerprint_sha256": record["payload_fingerprint_sha256"],
        "owned": {
            "files": [
                {
                    "install_path": entry["install_path"],
                    "sha256": entry["sha256"],
                    "length": entry["length"],
                }
                for entry in record["owned"]["files"]
            ],
            "directories": list(record["owned"]["directories"]),
            "created_directories": list(record["owned"]["created_directories"]),
        },
        "installed_top_level": list(record["installed_top_level"]),
        "created_target_root": bool(record["created_target_root"]),
        "staging_path_sha256": record["staging"]["path_sha256"],
    }


def _ownership_install_hash(core):
    """所有权记录的安装 hash：对身份字段的规范化 JSON 求 sha256。"""
    return _sha256_bytes(_dump_json(core).encode("utf-8"))


def _build_ownership_record(*, session_id, target, sandbox_parent, marker,
                            package_sha256, manifest_sha256, source_commit,
                            payload_fingerprint, owned_files, owned_dirs, created_dirs,
                            installed_top_level, created_target_root, staging):
    """构造目标内所有权记录（先算 install_hash，再落盘）。"""
    record = {
        "schema_version": OWNERSHIP_SCHEMA_VERSION,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "session_id": session_id,
        "target_identity": str(target),
        "target_identity_sha256": _sha256_bytes(str(target).encode("utf-8")),
        "sandbox_parent": str(sandbox_parent),
        "sandbox_parent_sha256": _sha256_bytes(str(sandbox_parent).encode("utf-8")),
        "sandbox_marker": {
            "name": SANDBOX_MARKER_NAME,
            "magic": SANDBOX_MARKER_MAGIC,
            "sha256": marker["sha256"],
        },
        "source_commit": source_commit,
        "manifest_sha256": manifest_sha256,
        "package_sha256": package_sha256,
        "payload_fingerprint_sha256": payload_fingerprint,
        "owned": {
            "files": [
                {
                    "install_path": entry["install_path"],
                    "sha256": entry["sha256"],
                    "length": entry["length"],
                }
                for entry in owned_files
            ],
            "directories": sorted({entry for entry in owned_dirs if entry}),
            "created_directories": sorted({entry for entry in created_dirs if entry}),
        },
        "installed_top_level": list(installed_top_level),
        "created_target_root": bool(created_target_root),
        "staging": {
            "path": str(staging),
            "path_sha256": _sha256_bytes(str(staging).encode("utf-8")),
            "removed": True,
        },
        "note": (
            "本记录由本工具在安装事务内写入目标内部，是本轮安装的真实所有权凭据；"
            "回滚必须读取并核对它，外部收据不构成删除授权。"
        ),
    }
    record["install_hash"] = _ownership_install_hash(_ownership_core(record))
    return record


def _write_ownership_record(target, record):
    """把所有权记录原子写入目标内部；绝不覆盖已存在的用户文件。"""
    final = Path(target) / OWNERSHIP_FILE_NAME
    if final.exists() or final.is_symlink():
        _fail(
            "CONFLICT",
            "the ownership record path already exists; refusing to overwrite a user file",
            path=OWNERSHIP_FILE_NAME,
        )
    payload = _dump_json(record).encode("utf-8")
    temp = Path(target) / (OWNERSHIP_FILE_NAME + ".tmp-" + uuid.uuid4().hex)
    try:
        handle = os.open(str(temp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if final.exists() or final.is_symlink():
            _fail(
                "CONFLICT",
                "the ownership record path appeared while installing; refusing to overwrite",
                path=OWNERSHIP_FILE_NAME,
            )
        os.replace(str(temp), str(final))
    except BaseException:
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass
        raise
    return {
        "path": OWNERSHIP_FILE_NAME,
        "sha256": _sha256_bytes(payload),
        "bytes": len(payload),
    }


def _read_ownership_record(target):
    """读取并校验目标内所有权记录；缺失/被改写都稳定非零拒绝。"""
    path = Path(target) / OWNERSHIP_FILE_NAME
    if path.is_symlink():
        _fail(
            "ROLLBACK_CONFLICT",
            "the ownership record path is a symlink; refusing to use it",
            path=OWNERSHIP_FILE_NAME,
        )
    if not path.is_file():
        _fail(
            "ROLLBACK_CONFLICT",
            "the install target carries no ownership record; ownership cannot be established",
            path=OWNERSHIP_FILE_NAME,
            target=str(target),
        )
    try:
        raw = path.read_bytes()
        record = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        _fail(
            "ROLLBACK_CONFLICT",
            "the ownership record is not readable JSON",
            path=OWNERSHIP_FILE_NAME,
            reason=str(exc),
        )
    if not isinstance(record, dict):
        _fail(
            "ROLLBACK_CONFLICT",
            "the ownership record is not a JSON object",
            path=OWNERSHIP_FILE_NAME,
        )
    if record.get("schema_version") != OWNERSHIP_SCHEMA_VERSION:
        _fail(
            "ROLLBACK_CONFLICT",
            "ownership record schema mismatch",
            expected=OWNERSHIP_SCHEMA_VERSION,
            found=record.get("schema_version"),
        )
    try:
        core = _ownership_core(record)
    except (KeyError, TypeError) as exc:
        _fail(
            "ROLLBACK_CONFLICT",
            "the ownership record is missing identity fields",
            path=OWNERSHIP_FILE_NAME,
            reason=str(exc),
        )
    expected_hash = record.get("install_hash")
    actual_hash = _ownership_install_hash(core)
    if not isinstance(expected_hash, str) or expected_hash != actual_hash:
        _fail(
            "ROLLBACK_CONFLICT",
            "the ownership record install_hash does not match its own content",
            path=OWNERSHIP_FILE_NAME,
            expected=expected_hash,
            actual=actual_hash,
        )
    return record, _sha256_bytes(raw)


# --------------------------------------------------------------------------- #
# 子命令：install
# --------------------------------------------------------------------------- #


def _snapshot_tree(root):
    """记录目录树中已存在的文件/目录（preimage）。"""
    files = []
    directories = []
    if not root.is_dir():
        return {"files": files, "directories": directories}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(dirnames):
            full = Path(dirpath) / name
            directories.append(str(full.relative_to(root).as_posix()))
        for name in sorted(filenames):
            full = Path(dirpath) / name
            relative = full.relative_to(root).as_posix()
            if full.is_symlink():
                files.append({"path": relative, "kind": "symlink", "sha256": None, "length": None})
                continue
            files.append(
                {
                    "path": relative,
                    "kind": "file",
                    "length": full.stat().st_size,
                    "sha256": _sha256_file(full),
                }
            )
    files.sort(key=lambda entry: entry["path"])
    directories.sort()
    return {"files": files, "directories": directories}


def command_install(args):
    protected = getattr(args, '_protected_handoff', None)
    if protected is not None:
        if type(protected) is not ProtectedInstall:
            _fail('BAD_INPUT', 'invalid protected install handoff')
        return protected.install(args)
    sandbox_parent = Path(args.sandbox_parent).expanduser().resolve()
    target = Path(args.target).expanduser()
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()
    else:
        target = target.resolve()

    if not sandbox_parent.is_dir():
        _fail(
            "BAD_INPUT",
            "sandbox parent is not an existing directory",
            sandbox_parent=str(sandbox_parent),
        )
    _require_not_production_host(sandbox_parent, "sandbox_parent")
    _require_not_production_host(target, "target")
    if not _is_within(target, sandbox_parent):
        _fail(
            "PATH_REJECTED",
            "target is not inside the explicitly provided sandbox parent",
            target=str(target),
            sandbox_parent=str(sandbox_parent),
        )
    if target == sandbox_parent:
        _fail(
            "PATH_REJECTED",
            "target must be a subdirectory of the sandbox parent, not the parent itself",
            target=str(target),
            sandbox_parent=str(sandbox_parent),
        )
    marker = _read_sandbox_marker(sandbox_parent)
    _diag(f"[install] sandbox marker verified: {marker['path']}")

    # 完整校验在写 target 之前完成；失败时 target 0 写入、不留空目录。
    validation = _validate_archive(args.package, args.manifest)
    _diag(f"[install] package validation passed ({len(validation['checks'])} checks)")

    manifest = validation["manifest"]
    items = validation["items"]

    # 冲突检查：owned 顶层目录或所有权记录已存在即拒绝，0 写入。
    conflicts = []
    for owned_dir in (BRIDGE_INSTALL_DIR, WORKFLOWS_INSTALL_DIR):
        candidate = target / owned_dir
        if candidate.exists():
            conflicts.append(str(owned_dir))
    ownership_path = target / OWNERSHIP_FILE_NAME
    if ownership_path.exists() or ownership_path.is_symlink():
        conflicts.append(OWNERSHIP_FILE_NAME)
    if conflicts:
        _fail(
            "CONFLICT",
            "target already contains owned install paths; refusing to overwrite",
            target=str(target),
            conflicting_paths=conflicts,
        )

    preimage = _snapshot_tree(target)
    created_target_root = not target.exists()
    # correction-01：session 不可碰撞（完整 uuid4 hex）。
    session_id = args.session_id or ("sess-" + uuid.uuid4().hex)

    staging = Path(tempfile.mkdtemp(prefix=STAGING_DIR_PREFIX, dir=str(sandbox_parent)))
    owned_files = []
    owned_dirs = []
    created_target_root_dirs = []
    committed = []
    failure_detail = {}
    ownership_written = None
    top_level_parents = sorted(
        {owned_dir.split("/")[0] for owned_dir in (BRIDGE_INSTALL_DIR, WORKFLOWS_INSTALL_DIR)}
    )

    try:
        # --- stage：逐成员严格解包（不使用 extractall） -------------------- #
        for item in items:
            member = item["package_path"]
            data = validation["contents"][member]
            if len(data) != item["length"] or _sha256_bytes(data) != item["sha256"]:
                _fail(
                    "INTEGRITY_MISMATCH",
                    "staged member does not match the manifest",
                    member=member,
                )
            destination = staging / item["install_path"]
            resolved = destination.resolve()
            if not _is_within(resolved, staging.resolve()):
                _fail(
                    "PATH_REJECTED",
                    "staged member would escape the staging root",
                    member=member,
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            owned_files.append(
                {
                    "install_path": item["install_path"],
                    "sha256": item["sha256"],
                    "length": item["length"],
                }
            )

        # stage 后再全量校验一次，确认落盘字节一致。
        for owned in owned_files:
            staged_path = staging / owned["install_path"]
            if _sha256_file(staged_path) != owned["sha256"]:
                _fail(
                    "INTEGRITY_MISMATCH",
                    "staged file hash mismatch after writing",
                    install_path=owned["install_path"],
                )

        # 记录 staged 树里的 owned 目录；顶层父目录另计入 created_directories。
        staged_dirs = []
        for dirpath, dirnames, _filenames in os.walk(staging):
            dirnames.sort()
            for name in dirnames:
                full = Path(dirpath) / name
                staged_dirs.append(full.relative_to(staging).as_posix())
        owned_dirs.extend(
            sorted(
                relative
                for relative in staged_dirs
                if relative not in top_level_parents
            )
        )

        # --- commit：原子 rename ------------------------------------------ #
        if created_target_root:
            target.mkdir(parents=True, exist_ok=True)
            created_target_root_dirs.append("")
        for parent_relative in top_level_parents:
            parent = target / parent_relative
            if not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
                created_target_root_dirs.append(parent_relative)
        for owned_dir in (BRIDGE_INSTALL_DIR, WORKFLOWS_INSTALL_DIR):
            source = staging / owned_dir
            destination = target / owned_dir
            os.rename(str(source), str(destination))
            committed.append(owned_dir)
        _diag(f"[install] committed owned paths: {committed}")

        # --- 安装后校验 --------------------------------------------------- #
        for owned in owned_files:
            installed = target / owned["install_path"]
            if not installed.is_file():
                _fail(
                    "INSTALL_FAILED",
                    "installed file is missing after commit",
                    install_path=owned["install_path"],
                )
            if _sha256_file(installed) != owned["sha256"]:
                _fail(
                    "INSTALL_FAILED",
                    "installed file hash mismatch after commit",
                    install_path=owned["install_path"],
                )

        # --- staging 清理（同一事务内，只针对本次自建且身份已确认的目录） -- #
        if not _remove_owned_staging(staging, sandbox_parent):
            _fail(
                "INSTALL_FAILED",
                "the staging directory of this install could not be removed cleanly",
                staging_prefix=STAGING_DIR_PREFIX,
            )

        # --- 目标内所有权记录（与安装同一事务边界） ------------------------ #
        # 记录落盘是本事务的最后一步：落盘失败会连带回退已 commit 的 owned 项，
        # 因此绝不留下「已安装但无法安全回滚」的无记录终态。
        record = _build_ownership_record(
            session_id=session_id,
            target=target,
            sandbox_parent=sandbox_parent,
            marker=marker,
            package_sha256=validation["package_sha256"],
            manifest_sha256=validation["manifest_sha256"],
            source_commit=manifest.get("source_commit"),
            payload_fingerprint=_fingerprint(
                [
                    {"install_path": item["install_path"], "sha256": item["sha256"]}
                    for item in items
                ]
            ),
            owned_files=owned_files,
            owned_dirs=owned_dirs,
            created_dirs=created_target_root_dirs,
            installed_top_level=committed,
            created_target_root=created_target_root,
            staging=staging,
        )
        ownership_written = _write_ownership_record(target, record)
        _diag(f"[install] ownership record written: {OWNERSHIP_FILE_NAME}")

    except PackageError as exc:
        cleanup = _rollback_committed(
            target, committed, staging, created_target_root_dirs, ownership_written
        )
        failure_detail = {
            "original_failure": exc.to_dict(),
            "cleanup": cleanup,
        }
        raise PackageError(
            exc.code,
            f"install failed and committed owned paths were reverted: {exc.message}",
            failure_detail,
        )
    except Exception as exc:  # noqa: BLE001
        cleanup = _rollback_committed(
            target, committed, staging, created_target_root_dirs, ownership_written
        )
        failure_detail = {
            "original_failure": {"error_code": "INTERNAL_ERROR", "message": str(exc)},
            "cleanup": cleanup,
        }
        raise PackageError(
            "INSTALL_FAILED",
            "install failed with an unexpected error and committed owned paths were reverted",
            failure_detail,
        )
    finally:
        # 兜底：staging 只在仍是本次自建目录时才清；身份不符则保留并记录。
        if staging.exists():
            _remove_owned_staging(staging, sandbox_parent)

    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "command": "install",
        "status": "OK",
        "session_id": session_id,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "ownership_schema_version": OWNERSHIP_SCHEMA_VERSION,
        "source_commit": manifest.get("source_commit"),
        "package": {
            "path": validation["package_path"],
            "sha256": validation["package_sha256"],
            "size_bytes": validation["package_size_bytes"],
        },
        "manifest": {
            "sha256": validation["manifest_sha256"],
            "member": MANIFEST_MEMBER,
            "content": manifest,
        },
        "sandbox_parent": str(sandbox_parent),
        "sandbox_parent_sha256": _sha256_bytes(str(sandbox_parent).encode("utf-8")),
        "sandbox_marker": {"path": marker["path"], "sha256": marker["sha256"]},
        "target": str(target),
        "target_identity_sha256": _sha256_bytes(str(target).encode("utf-8")),
        "created_target_root": created_target_root,
        "preimage": preimage,
        "owned": {
            "files": sorted(owned_files, key=lambda entry: entry["install_path"]),
            "directories": sorted({entry for entry in owned_dirs if entry}),
            "created_directories": sorted(
                {entry for entry in created_target_root_dirs if entry}
            ),
        },
        "installed_top_level": committed,
        "staging": {
            "path": str(staging),
            "path_sha256": _sha256_bytes(str(staging).encode("utf-8")),
            "removed": not staging.exists(),
        },
        "ownership": {
            "schema_version": OWNERSHIP_SCHEMA_VERSION,
            "path": OWNERSHIP_FILE_NAME,
            "sha256": ownership_written["sha256"],
            "install_hash": record["install_hash"],
        },
        "checks": validation["checks"],
        "note": (
            "sandbox install only; this is not a real-host acceptance. The in-target "
            "ownership record is the authoritative proof of this install's ownership; "
            "this receipt alone never authorises any deletion."
        ),
    }
    if args.receipt_out:
        _write_receipt(args.receipt_out, receipt, args.redact_root)
    return receipt


def _remove_owned_staging(staging, sandbox_parent):
    """只删除本次调用真正创建、身份已确认的 staging 目录。

    身份确认：目录名带本工具的暂存前缀、位于本轮沙箱父目录之内、且不是 symlink。
    任一条不满足就拒绝删除（返回 False），绝不按路径字符串授予递归删除权。
    """
    staging = Path(staging)
    try:
        if staging.is_symlink():
            return False
        resolved = staging.resolve()
        parent = Path(sandbox_parent).resolve()
    except OSError:
        return False
    if not resolved.name.startswith(STAGING_DIR_PREFIX):
        return False
    if parent == resolved or parent not in resolved.parents:
        return False
    if not resolved.is_dir():
        return not staging.exists()
    try:
        shutil.rmtree(staging)
    except OSError:
        return False
    return not staging.exists()


def _rollback_committed(target, committed, staging, created_dirs=(), ownership_written=None):
    """安装中途失败时，移除已经 commit 的 owned 项，并测量清理结果。

    只删本轮 owned 的、位于 target 之内的路径；不碰任何非 owned 内容。
    """
    removed = []
    remaining = []
    try:
        target_resolved = Path(target).resolve()
    except OSError:
        target_resolved = Path(target)
    for owned_dir in reversed(committed):
        path = Path(target) / owned_dir
        if path.is_symlink():
            remaining.append({"path": owned_dir, "reason": "symlink_not_removed"})
            continue
        if not path.exists():
            continue
        try:
            if target_resolved not in path.resolve().parents:
                remaining.append({"path": owned_dir, "reason": "outside_install_target"})
                continue
            shutil.rmtree(path)
            removed.append(owned_dir)
        except OSError as exc:
            remaining.append({"path": owned_dir, "reason": str(exc)})
    for created in sorted({entry for entry in created_dirs if entry}, reverse=True):
        path = Path(target) / created
        if path.is_dir() and not path.is_symlink():
            try:
                path.rmdir()
                removed.append(created)
            except OSError as exc:
                remaining.append({"path": created, "reason": str(exc)})
    ownership_removed = False
    if ownership_written:
        record_path = Path(target) / OWNERSHIP_FILE_NAME
        try:
            if record_path.is_file() and not record_path.is_symlink():
                record_path.unlink()
                ownership_removed = True
        except OSError as exc:
            remaining.append({"path": OWNERSHIP_FILE_NAME, "reason": str(exc)})
    staging_removed = False
    if staging.exists():
        staging_removed = _remove_owned_staging(staging, staging.parent)
    return {
        "removed_owned_paths": removed,
        "remaining_owned_paths": remaining,
        "staging_removed": staging_removed,
        "ownership_record_removed": ownership_removed,
    }


# --------------------------------------------------------------------------- #
# 子命令：rollback
# --------------------------------------------------------------------------- #


def _validate_relative_within_target(value, role, target, check_containment=True):
    """校验一条相对目标根的路径（preimage 等非 owned 路径字段也用它）。

    ``check_containment=False`` 时只做语法校验：preimage 只用于只读的漂移检测，
    目标内本来就可能有用户自建的 symlink，不应因此拒绝回滚。
    """
    if not isinstance(value, str) or not value:
        _fail("PATH_REJECTED", f"{role} is not a non-empty relative path", role=role)
    problems = []
    if "\\" in value:
        problems.append("backslash_separator")
    if value.startswith("//"):
        problems.append("unc_path")
    elif value.startswith("/"):
        problems.append("absolute_path")
    if re.match(r"^[A-Za-z]:", value):
        problems.append("drive_letter")
    if value.endswith("/"):
        problems.append("directory_entry")
    parts = value.split("/")
    if any(part == "" for part in parts):
        problems.append("empty_path_component")
    if any(part == "." for part in parts):
        problems.append("dot_path_component")
    if any(part == ".." for part in parts):
        problems.append("path_traversal")
    for part in parts:
        for problem in _path_component_problems(part):
            problems.append(problem)
    if not problems and PurePosixPath(value).as_posix() != value:
        problems.append("non_canonical_relative_path")
    if problems:
        _fail(
            "PATH_REJECTED",
            f"{role} is not a canonical relative path",
            role=role,
            value=value,
            problems=problems,
        )
    if check_containment:
        _assert_no_symlink_escape(target, value, role)
    return value


def _validate_preimage_entries(preimage, target):
    """校验 preimage 的路径字段：规范相对路径、位于目标内、不属于 owned 前缀。"""
    if not isinstance(preimage, dict):
        _fail("PATH_REJECTED", "the preimage section is malformed")
    files = preimage.get("files")
    directories = preimage.get("directories")
    if not isinstance(files, list) or not isinstance(directories, list):
        _fail("PATH_REJECTED", "the preimage section is malformed")
    for index, entry in enumerate(files):
        role = f"preimage.files[{index}].path"
        if not isinstance(entry, dict):
            _fail("PATH_REJECTED", f"{role} is not an object")
        relative = _validate_relative_within_target(
            entry.get("path"), role, target, check_containment=False
        )
        if any(relative.startswith(prefix) for prefix in OWNED_INSTALL_PREFIXES):
            _fail(
                "PATH_REJECTED",
                "the preimage claims an owned install path; the preimage is pre-install content",
                role=role,
                value=relative,
            )
        if entry.get("kind") == "symlink":
            continue
        digest = entry.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            _fail(
                "INTEGRITY_MISMATCH",
                f"preimage.files[{index}] carries a malformed sha256",
                path=relative,
            )
    for index, value in enumerate(directories):
        role = f"preimage.directories[{index}]"
        relative = _validate_relative_within_target(
            value, role, target, check_containment=False
        )
        if any(relative.startswith(prefix) for prefix in OWNED_INSTALL_PREFIXES):
            _fail(
                "PATH_REJECTED",
                "the preimage claims an owned install directory",
                role=role,
                value=relative,
            )
    return preimage


def _validate_owned_entries(entries, source, target):
    """严格校验 owned 条目的类型、路径合法性与唯一性；返回归一化条目列表。"""
    if not isinstance(entries, list) or not entries:
        _fail(
            "PATH_REJECTED",
            f"{source} owned file list is missing or malformed",
            source=source,
        )
    normalized = []
    seen = {}
    for index, entry in enumerate(entries):
        role = f"{source}.owned.files[{index}].install_path"
        if not isinstance(entry, dict):
            _fail("PATH_REJECTED", f"{role} is not an object", source=source, index=index)
        install_path = _validate_owned_relative_path(entry.get("install_path"), role, "file")
        digest = entry.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            _fail(
                "INTEGRITY_MISMATCH",
                f"{source} owned file entry carries a malformed sha256",
                source=source,
                install_path=install_path,
            )
        length = entry.get("length")
        if not isinstance(length, int) or isinstance(length, bool) or length < 0:
            _fail(
                "INTEGRITY_MISMATCH",
                f"{source} owned file entry carries a malformed length",
                source=source,
                install_path=install_path,
            )
        key = _windows_path_key(install_path)
        if key in seen:
            _fail(
                "PATH_REJECTED",
                f"{source} owned file set contains colliding install paths",
                source=source,
                first=seen[key],
                second=install_path,
            )
        seen[key] = install_path
        _assert_no_symlink_escape(target, install_path, role)
        normalized.append(
            {"install_path": install_path, "sha256": digest, "length": length}
        )
    return normalized


def _validate_owned_directory_entries(entries, source, target):
    """校验 owned 目录条目：类型、路径合法性与唯一性。"""
    if not isinstance(entries, list):
        _fail(
            "PATH_REJECTED",
            f"{source} owned directory list is missing or malformed",
            source=source,
        )
    normalized = []
    seen = set()
    for index, value in enumerate(entries):
        role = f"{source}.owned.directories[{index}]"
        relative = _validate_owned_relative_path(value, role, "directory")
        key = _windows_path_key(relative)
        if key in seen:
            _fail(
                "PATH_REJECTED",
                f"{source} owned directory set contains duplicate entries",
                source=source,
                duplicate=relative,
            )
        seen.add(key)
        _assert_no_symlink_escape(target, relative, role)
        normalized.append(relative)
    return normalized


def _cross_check_receipt_against_ownership(receipt, record):
    """外部收据与目标内所有权记录的逐项交叉核对；返回不一致清单。"""
    mismatches = []
    receipt_owned = receipt.get("owned") or {}
    record_owned = record.get("owned") or {}

    def compare(label, left, right):
        if left != right:
            mismatches.append({"field": label, "receipt": left, "ownership_record": right})

    def compare_path(label, left, right):
        """路径字段比较：收据侧被脱敏时跳过字符串比较，由各自的 sha256 绑定负责。"""
        if isinstance(left, str) and (
            "<redacted-root>" in left or "<abs-path-redacted>" in left
        ):
            return
        compare(label, left, right)

    compare(
        "owned.files",
        _owned_files_signature(receipt_owned.get("files")),
        _owned_files_signature(record_owned.get("files")),
    )
    compare(
        "owned.directories",
        sorted(receipt_owned.get("directories") or []),
        sorted(record_owned.get("directories") or []),
    )
    compare(
        "owned.created_directories",
        sorted(receipt_owned.get("created_directories") or []),
        sorted(record_owned.get("created_directories") or []),
    )
    compare("source_commit", receipt.get("source_commit"), record.get("source_commit"))
    compare(
        "manifest.sha256",
        (receipt.get("manifest") or {}).get("sha256"),
        record.get("manifest_sha256"),
    )
    compare(
        "package.sha256",
        (receipt.get("package") or {}).get("sha256"),
        record.get("package_sha256"),
    )
    compare(
        "target_identity_sha256",
        receipt.get("target_identity_sha256"),
        record.get("target_identity_sha256"),
    )
    compare(
        "sandbox_parent_sha256",
        receipt.get("sandbox_parent_sha256"),
        record.get("sandbox_parent_sha256"),
    )
    compare(
        "sandbox_marker.sha256",
        (receipt.get("sandbox_marker") or {}).get("sha256"),
        (record.get("sandbox_marker") or {}).get("sha256"),
    )
    compare(
        "installed_top_level",
        sorted(receipt.get("installed_top_level") or []),
        sorted(record.get("installed_top_level") or []),
    )
    compare(
        "created_target_root",
        receipt.get("created_target_root"),
        record.get("created_target_root"),
    )
    # 路径字段：脱敏的收据跳过字符串比较，由 sha256 绑定负责。
    compare_path("target", receipt.get("target"), record.get("target_identity"))
    compare_path(
        "sandbox_parent", receipt.get("sandbox_parent"), record.get("sandbox_parent")
    )
    compare_path(
        "staging.path",
        (receipt.get("staging") or {}).get("path"),
        (record.get("staging") or {}).get("path"),
    )
    return mismatches


def command_rollback(args):
    receipt_path = Path(args.receipt).expanduser()
    if not receipt_path.is_file():
        _fail("BAD_INPUT", "install receipt not found", receipt=str(receipt_path))
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _fail("BAD_INPUT", "install receipt is not readable JSON", reason=str(exc))
    if not isinstance(receipt, dict):
        _fail("BAD_INPUT", "install receipt is not a JSON object")
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        _fail(
            "INTEGRITY_MISMATCH",
            "install receipt schema mismatch",
            expected=RECEIPT_SCHEMA_VERSION,
            found=receipt.get("schema_version"),
        )
    if receipt.get("command") != "install" or receipt.get("status") != "OK":
        _fail(
            "BAD_INPUT",
            "install receipt does not describe a successful install",
            command=receipt.get("command"),
            status=receipt.get("status"),
        )

    # --- 目标解析：脱敏收据必须显式给 --target ---------------------------- #
    receipt_target = receipt.get("target")
    if args.target:
        target = Path(args.target).expanduser()
    else:
        if not isinstance(receipt_target, str) or not receipt_target:
            _fail(
                "BAD_INPUT",
                "install receipt carries no target path; --target is required",
            )
        if "<redacted-root>" in receipt_target or "<abs-path-redacted>" in receipt_target:
            _fail(
                "BAD_INPUT",
                "the install receipt was written with redacted paths; --target is required",
                receipt_target=receipt_target,
            )
        target = Path(receipt_target)
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()
    else:
        target = target.resolve()
    _require_not_production_host(target, "target")

    # --- 本地所有权记录：唯一的所有权来源 --------------------------------- #
    record, record_file_sha256 = _read_ownership_record(target)

    # 目标身份绑定：目标内记录必须就是本目标，绝不靠 basename 认定同一目标。
    target_identity = record.get("target_identity")
    if not isinstance(target_identity, str) or target_identity != str(target):
        _fail(
            "PATH_REJECTED",
            "the ownership record is bound to a different install target",
            record_target=target_identity,
            requested_target=str(target),
        )
    identity_digest = _sha256_bytes(str(target).encode("utf-8"))
    if record.get("target_identity_sha256") != identity_digest:
        _fail(
            "PATH_REJECTED",
            "the ownership record target identity digest does not match the target",
            expected=record.get("target_identity_sha256"),
            actual=identity_digest,
        )

    # 沙箱绑定：沙箱父目录之内 + 沙箱 marker 身份一致。
    sandbox_parent = record.get("sandbox_parent")
    if not isinstance(sandbox_parent, str) or not sandbox_parent:
        _fail("ROLLBACK_CONFLICT", "the ownership record carries no sandbox parent")
    sandbox_parent_path = Path(sandbox_parent)
    if not sandbox_parent_path.is_dir():
        _fail(
            "ROLLBACK_CONFLICT",
            "the recorded sandbox parent no longer exists",
            sandbox_parent=sandbox_parent,
        )
    if not _is_within(target, sandbox_parent_path):
        _fail(
            "PATH_REJECTED",
            "the install target is not inside the recorded sandbox parent",
            target=str(target),
            sandbox_parent=sandbox_parent,
        )
    try:
        marker = _read_sandbox_marker(sandbox_parent_path)
    except PackageError as exc:
        _fail(
            "ROLLBACK_CONFLICT",
            "the sandbox marker of this install could not be verified",
            marker_error=exc.to_dict(),
        )
    if marker["sha256"] != (record.get("sandbox_marker") or {}).get("sha256"):
        _fail(
            "ROLLBACK_CONFLICT",
            "the sandbox marker identity does not match the ownership record",
            expected=(record.get("sandbox_marker") or {}).get("sha256"),
            actual=marker["sha256"],
        )

    # session 绑定：不可碰撞的 session 必须与收据一致。
    record_session = record.get("session_id")
    receipt_session = receipt.get("session_id")
    if not isinstance(record_session, str) or not record_session:
        _fail("ROLLBACK_CONFLICT", "the ownership record carries no session id")
    if not isinstance(receipt_session, str) or not receipt_session:
        _fail("BAD_INPUT", "the install receipt carries no session id")
    if record_session != receipt_session:
        _fail(
            "ROLLBACK_CONFLICT",
            "the install receipt session does not match the ownership record session",
            receipt_session=receipt_session,
            record_session=record_session,
        )

    # --- 收据路径字段合法性（先于交叉核对：路径穿越直接按路径错误拒绝） ---- #
    receipt_files = _validate_owned_entries(
        (receipt.get("owned") or {}).get("files"), "receipt", target
    )
    _validate_owned_directory_entries(
        (receipt.get("owned") or {}).get("directories"), "receipt", target
    )
    _validate_owned_directory_entries(
        (receipt.get("owned") or {}).get("created_directories"), "receipt", target
    )
    _validate_preimage_entries(receipt.get("preimage") or {}, target)

    # 收据与本地记录的交叉核对：任何不一致都拒绝，零删除。
    mismatches = _cross_check_receipt_against_ownership(receipt, record)
    ownership_block = receipt.get("ownership") or {}
    if isinstance(ownership_block.get("sha256"), str) and ownership_block["sha256"] != record_file_sha256:
        mismatches.append(
            {
                "field": "ownership.sha256",
                "receipt": ownership_block["sha256"],
                "ownership_record": record_file_sha256,
            }
        )
    if mismatches:
        _fail(
            "ROLLBACK_CONFLICT",
            "the install receipt does not match the in-target ownership record",
            mismatches=mismatches,
        )

    # --- 本地记录的 owned 路径合法性 -------------------------------------- #
    record_files = _validate_owned_entries(
        (record.get("owned") or {}).get("files"), "ownership_record", target
    )
    _validate_owned_directory_entries(
        (record.get("owned") or {}).get("directories"), "ownership_record", target
    )
    _validate_owned_directory_entries(
        (record.get("owned") or {}).get("created_directories"), "ownership_record", target
    )
    if not record_files:
        _fail("BAD_INPUT", "the ownership record carries no owned files")

    # --- 全量预检：逐项比对安装时的 hash --------------------------------- #
    drifted = []
    missing = []
    for owned in record_files:
        path = target / owned["install_path"]
        if path.is_symlink() or not path.is_file():
            missing.append(owned["install_path"])
            continue
        digest = _sha256_file(path)
        if digest != owned["sha256"]:
            drifted.append(
                {
                    "install_path": owned["install_path"],
                    "expected_sha256": owned["sha256"],
                    "actual_sha256": digest,
                }
            )
    preimage_drift = _preimage_drift(target, receipt.get("preimage") or {})

    if drifted or missing:
        report = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "command": "rollback",
            "status": "ROLLBACK_CONFLICT",
            "session_id": receipt_session,
            "target": str(target),
            "drifted_owned_files": drifted,
            "missing_owned_files": missing,
            "preimage_drift": preimage_drift,
            "removed": [],
            "preserved": [owned["install_path"] for owned in record_files],
            "note": "user modified the installed bytes; nothing was removed",
        }
        raise PackageError(
            "ROLLBACK_CONFLICT",
            "installed files were modified or removed; refusing to delete user bytes",
            report,
        )

    # --- staging 终态：只确认，绝不按路径递归删除 ------------------------- #
    record_staging = record.get("staging") or {}
    record_staging_path = record_staging.get("path")
    record_staging_digest = record_staging.get("path_sha256")
    if not isinstance(record_staging_path, str) or not record_staging_path:
        _fail("ROLLBACK_CONFLICT", "the ownership record carries no staging binding")
    if record_staging_digest != _sha256_bytes(record_staging_path.encode("utf-8")):
        _fail(
            "ROLLBACK_CONFLICT",
            "the ownership record staging binding is inconsistent",
            expected=record_staging_digest,
        )
    staging_path = Path(record_staging_path)
    if not staging_path.name.startswith(STAGING_DIR_PREFIX):
        _fail(
            "ROLLBACK_CONFLICT",
            "the recorded staging path is not a staging directory of this tool",
            staging_name=staging_path.name,
        )
    if not _is_within(staging_path, sandbox_parent_path):
        _fail(
            "ROLLBACK_CONFLICT",
            "the recorded staging path is not inside the recorded sandbox parent",
            sandbox_parent=sandbox_parent,
        )
    receipt_staging = receipt.get("staging") or {}
    if receipt_staging.get("path_sha256") != record_staging_digest:
        _fail(
            "ROLLBACK_CONFLICT",
            "the install receipt staging binding does not match the ownership record",
            receipt_staging_sha256=receipt_staging.get("path_sha256"),
            record_staging_sha256=record_staging_digest,
        )
    staging_present = staging_path.exists()
    if staging_present:
        # 残留/不符：稳定失败并保留诊断，绝不清理未知目录。
        _fail(
            "ROLLBACK_CONFLICT",
            "the staging directory of this install is still present; "
            "refusing to delete an unverified path",
            staging_name=staging_path.name,
            staging_state="present",
        )

    # --- 变更：只删本轮 owned 文件与目录 --------------------------------- #
    removed_files = []
    failed_removals = []
    for owned in record_files:
        path = target / owned["install_path"]
        try:
            if path.is_symlink() or not path.is_file():
                failed_removals.append(
                    {
                        "install_path": owned["install_path"],
                        "reason": "not_a_regular_owned_file",
                    }
                )
                continue
            path.unlink()
            removed_files.append(owned["install_path"])
        except OSError as exc:
            failed_removals.append({"install_path": owned["install_path"], "reason": str(exc)})

    removed_dirs = []
    retained_dirs = []
    owned_dirs = (record.get("owned") or {}).get("directories") or []
    created_dirs = (record.get("owned") or {}).get("created_directories") or []
    for relative in sorted(
        list(owned_dirs) + list(created_dirs),
        key=lambda value: (value.count("/"), value),
        reverse=True,
    ):
        path = target / relative
        if path.is_symlink() or not path.is_dir():
            continue
        try:
            path.rmdir()
            removed_dirs.append(relative)
        except OSError as exc:
            retained_dirs.append(
                {
                    "path": relative,
                    "reason": str(exc),
                    "non_empty": _dir_has_entries(path),
                    "entries": sorted(entry.name for entry in path.iterdir())
                    if path.is_dir()
                    else [],
                }
            )

    remaining_owned = [
        owned["install_path"]
        for owned in record_files
        if (target / owned["install_path"]).exists()
    ]

    # 所有权记录本身也是本轮 owned：回滚安全移除它；失败则保留以便重试。
    ownership_removed = False
    ownership_removal_error = None
    if not failed_removals and not remaining_owned:
        record_path = target / OWNERSHIP_FILE_NAME
        try:
            if record_path.is_symlink() or not record_path.is_file():
                ownership_removal_error = "ownership_record_missing_or_not_a_regular_file"
            else:
                record_path.unlink()
                ownership_removed = True
        except OSError as exc:
            ownership_removal_error = str(exc)

    if record.get("created_target_root"):
        try:
            target.rmdir()
            removed_dirs.append("")
        except OSError as exc:
            retained_dirs.append(
                {
                    "path": str(target),
                    "reason": str(exc),
                    "non_empty": _dir_has_entries(target),
                    "entries": sorted(entry.name for entry in target.iterdir())
                    if target.is_dir()
                    else [],
                }
            )

    postimage = _snapshot_tree(target)
    sentinel_unchanged = not preimage_drift
    # 目录未删除但仍存在非 owned 内容：这是保护用户字节的正确结果，不算回滚失败。
    blocking_dirs = [
        entry for entry in retained_dirs if not entry.get("non_empty")
    ]

    report = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "command": "rollback",
        "status": "FAILED"
        if (
            failed_removals
            or blocking_dirs
            or remaining_owned
            or not ownership_removed
        )
        else "OK",
        "session_id": receipt_session,
        "target": str(target),
        "removed_files": removed_files,
        "removed_directories": removed_dirs,
        "failed_removals": failed_removals,
        "retained_directories": retained_dirs,
        "remaining_owned_files": remaining_owned,
        "preimage_drift": preimage_drift,
        "sentinel_unchanged": sentinel_unchanged,
        "postimage_files": postimage["files"],
        "ownership_record": {
            "path": OWNERSHIP_FILE_NAME,
            "schema_version": OWNERSHIP_SCHEMA_VERSION,
            "install_hash": record.get("install_hash"),
            "removed": ownership_removed,
            "removal_error": ownership_removal_error,
        },
        "staging_removed": not staging_present,
        "staging_state": "absent_before_rollback",
        "staging_deleted_by_rollback": False,
        "note": (
            "only files owned by this bound install session were removed; directories "
            "holding non-owned user bytes are kept and reported; the staging directory "
            "was already cleaned by the install transaction and this rollback performed "
            "no recursive deletion"
        ),
    }
    if report["status"] != "OK":
        raise PackageError("INSTALL_FAILED", "rollback could not fully clean up", report)
    if args.receipt_out:
        _write_receipt(args.receipt_out, report, args.redact_root)
    return report


def _dir_has_entries(path):
    try:
        return any(Path(path).iterdir())
    except OSError:
        return False


def _preimage_drift(target, preimage):
    drift = []
    for entry in preimage.get("files") or []:
        path = target / entry["path"]
        if entry.get("kind") == "symlink":
            if not path.is_symlink():
                drift.append({"path": entry["path"], "problem": "symlink_removed"})
            continue
        if not path.is_file():
            drift.append({"path": entry["path"], "problem": "missing"})
            continue
        digest = _sha256_file(path)
        if digest != entry.get("sha256"):
            drift.append(
                {
                    "path": entry["path"],
                    "problem": "sha256_changed",
                    "expected_sha256": entry.get("sha256"),
                    "actual_sha256": digest,
                }
            )
    return drift


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

_MARKER_EPILOG = f"""\
沙箱要求：
  1) --sandbox-parent 指向一个显式给出的隔离沙箱父目录；
  2) 该父目录下必须存在 marker 文件 {SANDBOX_MARKER_NAME}，内容为
     JSON: {{"magic": "{SANDBOX_MARKER_MAGIC}", "tool": "{TOOL_NAME}"}}
  3) --target 必须位于该沙箱父目录之内；
  4) 真实 ComfyUI 宿主路径（路径组件含 comfyui / ComfyUI-aki-v2 等）被硬拒绝。

所有权边界：
  * install 成功时在目标内部写入所有权记录 {OWNERSHIP_FILE_NAME}
    （schema {OWNERSHIP_SCHEMA_VERSION}），绑定目标身份、沙箱 marker、session、
    源 candidate/manifest/payload 集合与安装 hash。
  * rollback 只承认该记录所绑定的安装，并与外部收据交叉核对；收据里的路径字段
    一律不是删除授权。回滚只确认暂存目录终态，不做基于路径的递归删除。

稳定错误码：{", ".join(sorted(k for k in EXIT_CODES if k != "OK"))}
退出码：{", ".join(f"{k}={v}" for k, v in sorted(EXIT_CODES.items(), key=lambda kv: kv[1]))}
"""


def _add_common(parser):
    parser.add_argument(
        "--receipt-out",
        help="把结构化收据写到该路径（JSON）。",
    )
    parser.add_argument(
        "--redact-root",
        action="append",
        default=[],
        help=(
            "可重复。收据与 stdout 中该目录下的绝对路径会被替换为 "
            "<redacted-root>/... 以便提交脱敏证据。"
        ),
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description=(
            "LVW V0 离线增量包工具：从显式 Git 候选 commit 构建增量包，"
            "校验该包，并在隔离沙箱中安装与回滚。"
        ),
        epilog=_MARKER_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser(
        "build",
        help="从显式 Git 候选 commit 构建确定性离线增量包。",
        description=(
            "从显式 Git 候选 commit 读取字节（不打包脏工作树），构建带 manifest、"
            "工具版本化副本和中文使用说明的离线增量包。"
        ),
        epilog=_MARKER_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    build.add_argument("--repo", required=True, help="Git 仓库根目录。")
    build.add_argument("--commit", required=True, help="显式候选 commit（SHA 或可解析引用）。")
    build.add_argument("--out", required=True, help="输出 .zip 路径（不得已存在）。")
    _add_common(build)
    build.set_defaults(func=command_build)

    diagnose = subparsers.add_parser(
        "diagnose",
        help="校验离线包（不写任何文件）。",
        description=(
            "在不写安装目标的前提下校验完整 archive/manifest、长度与 hash、条目集合与体积上限；"
            "拒绝路径穿越、绝对路径、盘符、反斜杠、重复成员、大小写冲突、symlink 与 zip bomb。"
        ),
        epilog=_MARKER_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    diagnose.add_argument("--package", required=True, help="待校验的 .zip 路径。")
    diagnose.add_argument("--manifest", help="可选：外部 manifest JSON，用于交叉比对。")
    diagnose.add_argument("--target", help="可选：只读检查该安装目标的可写性与隔离 marker。")
    diagnose.add_argument("--sandbox-parent", help="可选：与 --target 一起给出时做隔离校验。")
    _add_common(diagnose)
    diagnose.set_defaults(func=command_diagnose)

    install = subparsers.add_parser(
        "install",
        help="把离线包安装到显式隔离沙箱。",
        description=(
            "只在显式给出的 sandbox parent 之内、且带本工具沙箱 marker 的 target 上安装；"
            "安装为同根隔离 Comfy 目录布局：custom_nodes/lvw_v0_bridge + workflows/lvw/。"
        ),
        epilog=_MARKER_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    install.add_argument("--package", required=True, help="待安装的 .zip 路径。")
    install.add_argument("--sandbox-parent", required=True, help="隔离沙箱父目录。")
    install.add_argument("--target", required=True, help="安装目标（必须在 sandbox parent 内）。")
    install.add_argument("--manifest", help="可选：外部 manifest JSON，用于交叉比对。")
    install.add_argument("--session-id", help="可选：自定义 session ID（默认随机生成）。")
    _add_common(install)
    install.set_defaults(func=command_install)

    rollback = subparsers.add_parser(
        "rollback",
        help="按安装收据回滚本轮 owned 文件。",
        description=(
            "按目标内所有权记录绑定 target 身份、沙箱 marker、session 与 installed hashes "
            "逐项检查；外部收据只作交叉核对，其路径字段不是删除授权。无用户改写才移除本轮 "
            "owned 文件/目录，有改写则报 ROLLBACK_CONFLICT 并保留用户字节。"
        ),
        epilog=_MARKER_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rollback.add_argument("--receipt", required=True, help="install 产生的收据 JSON 路径。")
    rollback.add_argument("--target", help="可选：安装目标（默认取自收据）。")
    _add_common(rollback)
    rollback.set_defaults(func=command_rollback)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    redact_roots = list(getattr(args, "redact_root", []) or [])
    global _ACTIVE_REDACT_ROOTS
    _ACTIVE_REDACT_ROOTS = redact_roots
    try:
        result = args.func(args)
    except PackageError as exc:
        payload = {
            "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "command": getattr(args, "command", "unknown"),
            "status": "FAILED",
            "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
            **exc.to_dict(),
        }
        if redact_roots:
            payload = _redact_tree(payload, redact_roots)
        _emit(payload)
        _diag(f"[{payload['command']}] ERROR {exc.code}: {exc.message}")
        return EXIT_CODES[exc.code]
    except Exception as exc:  # noqa: BLE001
        payload = {
            "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "command": getattr(args, "command", "unknown"),
            "status": "FAILED",
            "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
            "error_code": "INTERNAL_ERROR",
            "message": f"{type(exc).__name__}: {exc}",
            "detail": {},
        }
        if redact_roots:
            payload = _redact_tree(payload, redact_roots)
        _emit(payload)
        _diag(f"[{payload['command']}] ERROR INTERNAL_ERROR: {payload['message']}")
        return EXIT_CODES["INTERNAL_ERROR"]
    if redact_roots:
        result = _redact_tree(result, redact_roots)
    _emit(result)
    return EXIT_CODES["OK"]


if __name__ == "__main__":
    sys.exit(main())
