#!/usr/bin/env python3
"""LVW V0 增量包工具（S3-PREP-B 冻结实施合同）。

职责：把 Git 候选 commit 中的 LVW_V0_RuntimePatch 生产 payload 打成可复算的离线
增量包，校验该包，并可在**显式隔离沙箱**中安装与回滚。

严格边界（与 stage-packet-preparation-b.md 一致）：

* 只读 Git 对象库，不打包脏工作树；构建绑定完整 commit SHA。
* 只做离线：���联网、不下载、不读媒体、不用模型/GPU、不起服务。
* 只写显式提供的沙箱父目录内的 target；生产宿主路径硬拒绝。
* 不含任何任意 shell 执行接口，不依赖第三方包。

四个冻结子命令：build / diagnose / install / rollback。
结构化 JSON 写 stdout，诊断写 stderr，非零退出码表示失败。
"""

from __future__ import annotations

import argparse
import hashlib
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
TOOL_VERSION = "1.0.0"

PACKAGE_FORMAT_VERSION = "lvw.v0-incremental-package/1"
MANIFEST_SCHEMA_VERSION = "lvw.v0-incremental-package-manifest/1"
RECEIPT_SCHEMA_VERSION = "lvw.v0-incremental-package-receipt/1"
DIAGNOSTIC_SCHEMA_VERSION = "lvw.v0-incremental-package-diagnostic/1"

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

安装后目标根目录下新增两个 owned 顶层目录：

```
<target>/
  custom_nodes/lvw_v0_bridge/   # 生产节点模块（含 web/*.js 前端脚本）
  workflows/lvw/                # 工作流 JSON
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
  重复成员、大小写冲突、symlink 与 zip bomb。
* install 只写 owned 路径；已有非 owned 冲突时拒绝且 0 写入。
* rollback 逐项比对安装时的 hash；用户改写过则报 `ROLLBACK_CONFLICT` 并保留字节。
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


def _validate_archive(package_path, expect_manifest=None):
    """完整归档校验。返回结构化结果；失败抛 PackageError。"""
    package_path = Path(package_path)
    if not package_path.is_file():
        _fail("BAD_INPUT", "package file does not exist", package=str(package_path))
    package_size = package_path.stat().st_size
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
        archive = zipfile.ZipFile(package_path, "r")
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
            case_groups.setdefault(name.lower(), set()).add(name)
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
            and archive_ratio <= ZIP_BOMB_RATIO_LIMIT
            and not member_ratio_offenders
        )
        record("size_limits_and_zip_bomb", size_ok, **size_detail)
        if package_size > SIZE_LIMIT_BYTES:
            _fail("SIZE_LIMIT", "compressed package exceeds the hard size limit", **size_detail)
        if payload_expanded > SIZE_LIMIT_BYTES:
            _fail("SIZE_LIMIT", "expanded payload exceeds the hard size limit", **size_detail)
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
            external = json.loads(Path(expect_manifest).read_text(encoding="utf-8"))
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
            "package_sha256": _sha256_file(package_path),
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

    # 冲突检查：owned 顶层目录已存在即拒绝，0 写入。
    conflicts = []
    for owned_dir in (BRIDGE_INSTALL_DIR, WORKFLOWS_INSTALL_DIR):
        candidate = target / owned_dir
        if candidate.exists():
            conflicts.append(str(owned_dir))
    if conflicts:
        _fail(
            "CONFLICT",
            "target already contains owned install paths; refusing to overwrite",
            target=str(target),
            conflicting_paths=conflicts,
        )

    preimage = _snapshot_tree(target)
    created_target_root = not target.exists()
    session_id = args.session_id or ("sess-" + uuid.uuid4().hex[:12])

    staging = Path(tempfile.mkdtemp(prefix=".lvw-v0-stage-", dir=str(sandbox_parent)))
    owned_files = []
    owned_dirs = []
    created_target_root_dirs = []
    committed = []
    failure_detail = {}
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

    except PackageError as exc:
        cleanup = _rollback_committed(target, committed, staging, created_target_root_dirs)
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
        cleanup = _rollback_committed(target, committed, staging, created_target_root_dirs)
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
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "command": "install",
        "status": "OK",
        "session_id": session_id,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
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
        "sandbox_marker": {"path": marker["path"], "sha256": marker["sha256"]},
        "target": str(target),
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
        "staging": {"path": str(staging), "removed": not staging.exists()},
        "checks": validation["checks"],
        "note": "sandbox install only; this is not a real-host acceptance",
    }
    if args.receipt_out:
        _write_receipt(args.receipt_out, receipt, args.redact_root)
    return receipt


def _rollback_committed(target, committed, staging, created_dirs=()):
    """安装中途失败时，移除已经 commit 的 owned 项，并测量清理结果。"""
    removed = []
    remaining = []
    for owned_dir in reversed(committed):
        path = target / owned_dir
        if path.exists():
            try:
                shutil.rmtree(path)
                removed.append(owned_dir)
            except OSError as exc:
                remaining.append({"path": owned_dir, "reason": str(exc)})
    for created in sorted({entry for entry in created_dirs if entry}, reverse=True):
        path = target / created
        if path.is_dir():
            try:
                path.rmdir()
                removed.append(created)
            except OSError as exc:
                remaining.append({"path": created, "reason": str(exc)})
    staging_removed = False
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
        staging_removed = not staging.exists()
    return {
        "removed_owned_paths": removed,
        "remaining_owned_paths": remaining,
        "staging_removed": staging_removed,
    }


# --------------------------------------------------------------------------- #
# 子命令：rollback
# --------------------------------------------------------------------------- #


def command_rollback(args):
    receipt_path = Path(args.receipt).expanduser()
    if not receipt_path.is_file():
        _fail("BAD_INPUT", "install receipt not found", receipt=str(receipt_path))
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _fail("BAD_INPUT", "install receipt is not readable JSON", reason=str(exc))
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

    target = Path(args.target).expanduser() if args.target else Path(receipt["target"])
    if not args.target and "<redacted-root>" in str(receipt.get("target", "")):
        _fail(
            "BAD_INPUT",
            "the install receipt was written with redacted paths; --target is required",
            receipt_target=receipt.get("target"),
        )
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()
    else:
        target = target.resolve()
    _require_not_production_host(target, "target")
    if receipt.get("target") and Path(receipt["target"]).name != target.name:
        _fail(
            "BAD_INPUT",
            "target does not match the install receipt",
            receipt_target=receipt["target"],
            requested_target=str(target),
        )

    owned_files = (receipt.get("owned") or {}).get("files") or []
    if not owned_files:
        _fail("BAD_INPUT", "install receipt carries no owned files")

    # --- 全量预检：逐项比对安装时的 hash ------------------------------- #
    drifted = []
    missing = []
    for owned in owned_files:
        path = target / owned["install_path"]
        if not path.is_file():
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
            "session_id": receipt.get("session_id"),
            "target": str(target),
            "drifted_owned_files": drifted,
            "missing_owned_files": missing,
            "preimage_drift": preimage_drift,
            "removed": [],
            "preserved": [owned["install_path"] for owned in owned_files],
            "note": "user modified the installed bytes; nothing was removed",
        }
        raise PackageError(
            "ROLLBACK_CONFLICT",
            "installed files were modified or removed; refusing to delete user bytes",
            report,
        )

    # --- 变更：只删本轮 owned 文件与目录 --------------------------------- #
    removed_files = []
    failed_removals = []
    for owned in owned_files:
        path = target / owned["install_path"]
        try:
            path.unlink()
            removed_files.append(owned["install_path"])
        except OSError as exc:
            failed_removals.append({"install_path": owned["install_path"], "reason": str(exc)})

    removed_dirs = []
    retained_dirs = []
    owned = receipt.get("owned") or {}
    owned_dirs = owned.get("directories") or []
    created_dirs = owned.get("created_directories") or []
    for relative in sorted(
        list(owned_dirs) + list(created_dirs),
        key=lambda value: value.count("/"),
        reverse=True,
    ):
        path = target / relative
        if not path.is_dir():
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

    if receipt.get("created_target_root"):
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

    staging_path = (receipt.get("staging") or {}).get("path")
    staging_removed = None
    if staging_path:
        staging = Path(staging_path)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        staging_removed = not staging.exists()

    postimage = _snapshot_tree(target)
    sentinel_unchanged = not preimage_drift
    remaining_owned = [
        owned["install_path"]
        for owned in owned_files
        if (target / owned["install_path"]).exists()
    ]
    # 目录未删除但仍存在非 owned 内容：这是保护用户字节的正确结果，不算回滚失败。
    blocking_dirs = [
        entry for entry in retained_dirs if not entry.get("non_empty")
    ]

    report = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "command": "rollback",
        "status": "FAILED"
        if (failed_removals or blocking_dirs or remaining_owned)
        else "OK",
        "session_id": receipt.get("session_id"),
        "target": str(target),
        "removed_files": removed_files,
        "removed_directories": removed_dirs,
        "failed_removals": failed_removals,
        "retained_directories": retained_dirs,
        "remaining_owned_files": remaining_owned,
        "preimage_drift": preimage_drift,
        "sentinel_unchanged": sentinel_unchanged,
        "postimage_files": postimage["files"],
        "staging_removed": staging_removed,
        "note": (
            "only files owned by this install session were removed; directories holding "
            "non-owned user bytes are kept and reported"
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
            "按安装收据绑定 session 与 installed hashes 逐项检查；无用户改写才移除本轮 owned "
            "文件/目录，有改写则报 ROLLBACK_CONFLICT 并保留用户字节。"
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
