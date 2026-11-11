#!/usr/bin/env python3
"""tools/test_v0_incremental_package.py — S3-PREP-B 增量包工具定向测试。

覆盖（对应 stage-packet-preparation-b.md 第 3 条）：

* 真实固定 commit 构建 → hash 集合校验 → 中文/空格隔离 target 安装 → 诊断 → 回滚 →
  原有哨兵不变；
* 被篡改包、路径穿越、绝对路径/盘符/反斜杠、重复成员、大小写冲突、symlink、
  exact/one-over 体积边界、已有冲突、安装中途故障、用户改写后回滚拒绝及清理；
* CLI 契约：--help、结构化 JSON stdout、诊断 stderr、nonzero 退出、稳定错误码。

真实链路来自真实 Git 候选 commit；合成故障注入只用于错误分支，不替代真正常链。
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import stat
import subprocess
import sys
import warnings
import zipfile
from pathlib import Path

import pytest

TOOL_PATH = Path(__file__).resolve().parent / "v0_incremental_package.py"

#: 本任务冻结的 root 基准 commit：真实固定候选，payload 完整存在于该提交。
FIXED_CANDIDATE_COMMIT = "2db2fa81e34479e08ea33df7c90a179d1fd99936"

SIZE_LIMIT_BYTES = 20 * 1024 * 1024

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

SANDBOX_MARKER_NAME = ".lvw_v0_incremental_sandbox.json"
SANDBOX_MARKER_MAGIC = "lvw.v0-incremental-sandbox/1"
TOOL_NAME = "v0_incremental_package.py"

MANIFEST_SCHEMA = "lvw.v0-incremental-package-manifest/1"
PACKAGE_FORMAT = "lvw.v0-incremental-package/1"

BRIDGE_INSTALL_DIR = "custom_nodes/lvw_v0_bridge"
WORKFLOWS_INSTALL_DIR = "workflows/lvw"


# --------------------------------------------------------------------------- #
# 通用辅助
# --------------------------------------------------------------------------- #


def repo_root():
    proc = subprocess.run(
        ["git", "-C", str(TOOL_PATH.parent), "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise AssertionError("cannot resolve the git repository root")
    return Path(proc.stdout.decode("utf-8").strip())


def git(*args, cwd=None):
    proc = subprocess.run(
        ["git", "-C", str(cwd or repo_root()), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace')}"
        )
    return proc.stdout


def run_cli(*args, cwd=None):
    """运行公共 CLI，返回 (returncode, stdout_json, stderr_text)。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd or repo_root()),
        env=env,
    )
    stdout_text = proc.stdout.decode("utf-8", "replace")
    stderr_text = proc.stderr.decode("utf-8", "replace")
    try:
        payload = json.loads(stdout_text)
    except ValueError:
        payload = None
    return proc.returncode, payload, stdout_text, stderr_text


def make_sandbox(root, name="隔离 沙箱根", marker=True):
    """建一个带中文与空格的隔离沙箱：父目录 + 目标目录 + 哨兵文件。"""
    sandbox_parent = root / name
    sandbox_parent.mkdir(parents=True, exist_ok=True)
    if marker:
        (sandbox_parent / SANDBOX_MARKER_NAME).write_text(
            json.dumps({"magic": SANDBOX_MARKER_MAGIC, "tool": TOOL_NAME}),
            encoding="utf-8",
        )
    target = sandbox_parent / "隔离 目标 目录"
    target.mkdir(parents=True, exist_ok=True)
    sentinel = target / "哨兵 文件.txt"
    sentinel.write_bytes(b"SENTINEL-ORIGINAL-BYTES\n")
    return sandbox_parent, target, sentinel


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_snapshot(root):
    """目标目录的文件快照（相对路径 -> sha256）。"""
    snapshot = {}
    root = Path(root)
    if not root.exists():
        return snapshot
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snapshot[path.relative_to(root).as_posix()] = sha256_file(path)
    return snapshot


def expected_payload_from_git(commit):
    """独立地从 Git 计算 payload 集合与内容哈希（不经过工具实现）。"""
    prefix = "LVW_Prompt_Service_MasterPack_v2.0.0"
    raw = git(
        "ls-tree",
        "-r",
        "--full-tree",
        commit,
        "--",
        f"{prefix}/LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge",
        f"{prefix}/LVW_V0_RuntimePatch/workflows",
    ).decode("utf-8")
    expected = {}
    for line in raw.splitlines():
        meta, _tab, path = line.partition("\t")
        mode, object_type, _object_id = meta.split()
        if object_type != "blob" or mode == "120000":
            continue
        relative = path[len(prefix) + 1:]
        if relative.startswith("LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/"):
            rest = relative.split("custom_nodes/lvw_v0_bridge/", 1)[1]
            if rest.endswith(".py"):
                install = f"{BRIDGE_INSTALL_DIR}/{rest}"
            elif rest.startswith("web/") and rest.endswith(".js") and "/" not in rest[len("web/"):]:
                install = f"{BRIDGE_INSTALL_DIR}/{rest}"
            else:
                continue
        elif relative.startswith("LVW_V0_RuntimePatch/workflows/") and relative.endswith(".json"):
            rest = relative[len("LVW_V0_RuntimePatch/workflows/"):]
            if "/" in rest:
                continue
            install = f"{WORKFLOWS_INSTALL_DIR}/{rest}"
        else:
            continue
        content = git("cat-file", "blob", f"{commit}:{path}")
        expected[install] = hashlib.sha256(content).hexdigest()
    return expected


# --------------------------------------------------------------------------- #
# 合成包（错误分支用；不替代真实链路）
# --------------------------------------------------------------------------- #


def _write_zip(path, members):
    """写 ZIP；members 为 (name, bytes|None, external_attr|None) 列表。"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for member in members:
                name, data = member[0], member[1]
                external_attr = member[2] if len(member) > 2 else None
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (
                    external_attr if external_attr is not None else (0o100644 << 16)
                )
                archive.writestr(info, data)


def synthetic_package(path, payload_items, *, extra_members=(), member_names=None,
                      manifest_mutator=None, source_commit="0" * 40):
    """按公开 manifest 合同独立构造一个包（不经过工具实现）。"""
    tool_bytes = TOOL_PATH.read_bytes()
    tool_sha = hashlib.sha256(tool_bytes).hexdigest()
    items = []
    payload_members = []
    for install_path, data in payload_items:
        items.append(
            {
                "install_path": install_path,
                "package_path": "payload/" + install_path,
                "source_path": "synthetic/" + install_path,
                "source_blob_id": "0" * 40,
                "source_mode": "100644",
                "length": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
        payload_members.append(("payload/" + install_path, data))
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "package_format_version": PACKAGE_FORMAT,
        "source_commit": source_commit,
        "tool": {
            "name": TOOL_NAME,
            "version": "1.0.0",
            "sha256": tool_sha,
            "provenance": "synthetic_test",
            "provenance_detail": "synthetic package built by the test suite",
        },
        "size_limit_bytes": SIZE_LIMIT_BYTES,
        "payload_root": "payload/",
        "payload_item_count": len(items),
        "payload_expanded_bytes": sum(len(data) for _path, data in payload_items),
        "items": items,
        "dependencies": ["synthetic"],
        "non_goals": ["synthetic test package"],
    }
    if manifest_mutator is not None:
        manifest_mutator(manifest)
    usage = (
        "# 合成测试包\n\n"
        f"source_commit: {manifest.get('source_commit')}\n"
    ).encode("utf-8")
    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"
    members = [
        ("meta/manifest.json", manifest_bytes),
        ("meta/" + TOOL_NAME, tool_bytes),
        ("meta/使用说明.md", usage),
    ]
    members.extend(payload_members)
    members.extend(extra_members)
    if member_names is not None:
        members = [
            (member_names.get(name, name), data, *rest)
            for (name, data, *rest) in members
        ]
    _write_zip(path, members)
    return manifest


SIMPLE_PAYLOAD = [
    (f"{BRIDGE_INSTALL_DIR}/core.py", b"# synthetic core\nprint('ok')\n"),
    (f"{BRIDGE_INSTALL_DIR}/web/video_controls.js", b"// synthetic js\n"),
    (f"{WORKFLOWS_INSTALL_DIR}/demo.ui.json", b'{"nodes": []}\n'),
]


# --------------------------------------------------------------------------- #
# 真实链路
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def fixed_candidate():
    """确认冻结的固定候选 commit 在本仓库可用。"""
    try:
        git("cat-file", "-e", f"{FIXED_CANDIDATE_COMMIT}^{{commit}}")
    except AssertionError as exc:
        pytest.fail(f"frozen candidate commit is not available: {exc}")
    return FIXED_CANDIDATE_COMMIT


def test_build_binds_full_commit_sha_and_expected_hash_set(tmp_path, fixed_candidate):
    """真实固定 commit 构建：绑定完整 SHA，payload hash 集合与 Git 独立计算一致。"""
    out = tmp_path / "pkg.zip"
    code, payload, _stdout, stderr = run_cli(
        "build",
        "--repo",
        str(repo_root()),
        "--commit",
        fixed_candidate,
        "--out",
        str(out),
    )
    assert code == EXIT_CODES["OK"], stderr
    assert payload["status"] == "OK"
    assert payload["source_commit"] == fixed_candidate
    assert len(payload["source_commit"]) == 40

    expected = expected_payload_from_git(fixed_candidate)
    assert expected, "independent git payload set is empty"
    built = {
        entry["install_path"]: entry["sha256"]
        for entry in payload["payload"]["items"]
    }
    assert built == expected

    # payload 只允许生产模块与工作流；不含 tests / fixtures / 日志。
    for install_path in built:
        assert "tests/" not in install_path
        assert "fixtures" not in install_path
        assert "__pycache__" not in install_path
        assert not install_path.endswith(".pyc")
    assert payload["payload"]["expanded_bytes"] <= SIZE_LIMIT_BYTES


def test_build_reads_git_objects_not_dirty_worktree(tmp_path, fixed_candidate):
    """包内字节必须等于 Git 对象字节，不得取自工作树。"""
    out = tmp_path / "pkg.zip"
    code, payload, _stdout, stderr = run_cli(
        "build", "--repo", str(repo_root()), "--commit", fixed_candidate, "--out", str(out)
    )
    assert code == EXIT_CODES["OK"], stderr
    expected = expected_payload_from_git(fixed_candidate)
    with zipfile.ZipFile(out) as archive:
        for install_path, digest in expected.items():
            member = "payload/" + install_path
            assert archive.read(member) == git("cat-file", "blob", f"{fixed_candidate}:"
                                               + _git_path_for(install_path))
            assert hashlib.sha256(archive.read(member)).hexdigest() == digest
    assert "worktree_dirty_path_count" in payload


def _git_path_for(install_path):
    prefix = "LVW_Prompt_Service_MasterPack_v2.0.0"
    if install_path.startswith(BRIDGE_INSTALL_DIR + "/"):
        return f"{prefix}/LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/" + install_path[
            len(BRIDGE_INSTALL_DIR) + 1:
        ]
    return f"{prefix}/LVW_V0_RuntimePatch/workflows/" + install_path[
        len(WORKFLOWS_INSTALL_DIR) + 1:
    ]


def test_build_is_reproducible_for_same_candidate(tmp_path, fixed_candidate):
    """同一候选重复构建：包 hash 与 payload fingerprint 均可复算。"""
    first = tmp_path / "a.zip"
    second = tmp_path / "b.zip"
    for target in (first, second):
        code, payload, _stdout, stderr = run_cli(
            "build", "--repo", str(repo_root()), "--commit", fixed_candidate, "--out", str(target)
        )
        assert code == EXIT_CODES["OK"], stderr
    assert sha256_file(first) == sha256_file(second)
    code_a, payload_a, _out, _err = run_cli(
        "diagnose", "--package", str(first)
    )
    code_b, payload_b, _out, _err = run_cli(
        "diagnose", "--package", str(second)
    )
    assert code_a == code_b == EXIT_CODES["OK"]
    assert payload_a["manifest"]["sha256"] == payload_b["manifest"]["sha256"]
    assert payload_a["package"]["sha256"] == payload_b["package"]["sha256"]


def test_build_refuses_to_overwrite_existing_output(tmp_path, fixed_candidate):
    out = tmp_path / "pkg.zip"
    out.write_bytes(b"existing")
    before = sha256_file(out)
    code, payload, _stdout, stderr = run_cli(
        "build", "--repo", str(repo_root()), "--commit", fixed_candidate, "--out", str(out)
    )
    assert code == EXIT_CODES["CONFLICT"]
    assert payload["error_code"] == "CONFLICT"
    assert sha256_file(out) == before


def test_real_chain_install_diagnose_rollback_in_chinese_space_path(tmp_path, fixed_candidate):
    """真实链路：构建 → 校验 → 中文/空格隔离安装 → 诊断 → 回滚 → 哨兵不变。"""
    package = tmp_path / "真实 包.zip"
    code, build_payload, _stdout, stderr = run_cli(
        "build",
        "--repo",
        str(repo_root()),
        "--commit",
        fixed_candidate,
        "--out",
        str(package),
    )
    assert code == EXIT_CODES["OK"], stderr

    sandbox_parent, target, sentinel = make_sandbox(tmp_path)
    sentinel_before = sentinel.read_bytes()
    sentinel_sha = sha256_file(sentinel)

    # 诊断（不写任何文件）。
    code, diag_payload, _stdout, stderr = run_cli(
        "diagnose",
        "--package",
        str(package),
        "--target",
        str(target),
        "--sandbox-parent",
        str(sandbox_parent),
    )
    assert code == EXIT_CODES["OK"], stderr
    assert diag_payload["status"] == "OK"
    assert tree_snapshot(target) == {"哨兵 文件.txt": sentinel_sha}

    # 安装。
    receipt_path = tmp_path / "安装 收据.json"
    code, install_payload, _stdout, stderr = run_cli(
        "install",
        "--package",
        str(package),
        "--sandbox-parent",
        str(sandbox_parent),
        "--target",
        str(target),
        "--receipt-out",
        str(receipt_path),
    )
    assert code == EXIT_CODES["OK"], stderr
    assert install_payload["status"] == "OK"
    assert install_payload["session_id"]

    # 安装后的目录布局与 hash 集合。
    assert (target / BRIDGE_INSTALL_DIR / "core.py").is_file()
    assert (target / BRIDGE_INSTALL_DIR / "web" / "video_controls.js").is_file()
    assert (target / WORKFLOWS_INSTALL_DIR / "manual_prompt_v0.ui.json").is_file()
    expected = expected_payload_from_git(fixed_candidate)
    installed = {
        path.relative_to(target).as_posix(): sha256_file(path)
        for path in target.rglob("*")
        if path.is_file()
    }
    for install_path, digest in expected.items():
        assert installed.get(install_path) == digest
    # 原有哨兵字节不变。
    assert sentinel.read_bytes() == sentinel_before
    assert sha256_file(sentinel) == sentinel_sha

    # 回滚。
    code, rollback_payload, _stdout, stderr = run_cli(
        "rollback", "--receipt", str(receipt_path), "--target", str(target)
    )
    assert code == EXIT_CODES["OK"], stderr
    assert rollback_payload["status"] == "OK"
    assert rollback_payload["sentinel_unchanged"] is True
    assert rollback_payload["remaining_owned_files"] == []
    assert tree_snapshot(target) == {"哨兵 文件.txt": sentinel_sha}
    assert sentinel.read_bytes() == sentinel_before


def test_install_receipt_records_preimage_manifest_and_owned_writes(tmp_path, fixed_candidate):
    package = tmp_path / "pkg.zip"
    code, _payload, _stdout, stderr = run_cli(
        "build", "--repo", str(repo_root()), "--commit", fixed_candidate, "--out", str(package)
    )
    assert code == EXIT_CODES["OK"], stderr
    sandbox_parent, target, sentinel = make_sandbox(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    code, _payload, _stdout, stderr = run_cli(
        "install",
        "--package",
        str(package),
        "--sandbox-parent",
        str(sandbox_parent),
        "--target",
        str(target),
        "--receipt-out",
        str(receipt_path),
    )
    assert code == EXIT_CODES["OK"], stderr
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["session_id"]
    assert receipt["source_commit"] == fixed_candidate
    assert receipt["manifest"]["sha256"]
    assert receipt["manifest"]["content"]["source_commit"] == fixed_candidate
    preimage_paths = {entry["path"] for entry in receipt["preimage"]["files"]}
    assert "哨兵 文件.txt" in preimage_paths
    assert receipt["owned"]["files"]
    assert all(entry["sha256"] for entry in receipt["owned"]["files"])
    assert receipt["installed_top_level"] == [BRIDGE_INSTALL_DIR, WORKFLOWS_INSTALL_DIR]


# --------------------------------------------------------------------------- #
# 错误分支（合成包）
# --------------------------------------------------------------------------- #


def _diagnose_code(package, *extra):
    code, payload, _stdout, stderr = run_cli("diagnose", "--package", str(package), *extra)
    return code, payload, stderr


def test_tampered_payload_is_detected(tmp_path):
    package = tmp_path / "tampered.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    # 篡改包内 payload 字节（不改 manifest）。
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(package) as archive:
            members = [(info.filename, archive.read(info.filename)) for info in archive.infolist()]
    tampered = []
    for name, data in members:
        if name.startswith("payload/"):
            data = data + b"# tampered\n"
        tampered.append((name, data))
    _write_zip(package, tampered)
    code, payload, stderr = _diagnose_code(package)
    assert code == EXIT_CODES["INTEGRITY_MISMATCH"]
    assert payload["error_code"] == "INTEGRITY_MISMATCH"
    assert "INTEGRITY_MISMATCH" in stderr


def test_manifest_tampering_is_detected(tmp_path):
    package = tmp_path / "manifest-tampered.zip"

    def mutate(manifest):
        manifest["items"][0]["sha256"] = "0" * 64

    synthetic_package(package, SIMPLE_PAYLOAD, manifest_mutator=mutate)
    code, payload, _stderr = _diagnose_code(package)
    assert code == EXIT_CODES["INTEGRITY_MISMATCH"]
    assert payload["error_code"] == "INTEGRITY_MISMATCH"


@pytest.mark.parametrize(
    "bad_name",
    [
        "payload/../../escape.txt",
        "payload/../escape.txt",
        "/etc/passwd",
        "C:/Windows/system32/x.dll",
        "payload\\windows\\style.py",
        "payload//double//slash.py",
    ],
)
def test_unsafe_member_names_are_rejected(tmp_path, bad_name):
    package = tmp_path / "unsafe.zip"
    synthetic_package(
        package,
        SIMPLE_PAYLOAD,
        extra_members=[(bad_name, b"evil\n")],
    )
    code, payload, _stderr = _diagnose_code(package)
    assert code == EXIT_CODES["PATH_REJECTED"]
    assert payload["error_code"] == "PATH_REJECTED"


def test_duplicate_member_is_rejected(tmp_path):
    package = tmp_path / "duplicate.zip"
    synthetic_package(
        package,
        SIMPLE_PAYLOAD,
        extra_members=[("payload/custom_nodes/lvw_v0_bridge/core.py", b"# duplicate\n")],
    )
    code, payload, _stderr = _diagnose_code(package)
    assert code == EXIT_CODES["PATH_REJECTED"]
    assert payload["error_code"] == "PATH_REJECTED"


def test_case_insensitive_member_collision_is_rejected(tmp_path):
    package = tmp_path / "case.zip"
    synthetic_package(
        package,
        SIMPLE_PAYLOAD,
        extra_members=[("payload/custom_nodes/lvw_v0_bridge/Core.py", b"# case twin\n")],
    )
    code, payload, _stderr = _diagnose_code(package)
    assert code == EXIT_CODES["PATH_REJECTED"]
    assert payload["error_code"] == "PATH_REJECTED"


def test_symlink_member_is_rejected(tmp_path):
    package = tmp_path / "symlink.zip"
    symlink_attr = (stat.S_IFLNK | 0o777) << 16
    synthetic_package(
        package,
        SIMPLE_PAYLOAD,
        extra_members=[("payload/custom_nodes/lvw_v0_bridge/link.py", b"/etc/passwd", symlink_attr)],
    )
    code, payload, _stderr = _diagnose_code(package)
    assert code == EXIT_CODES["PATH_REJECTED"]
    assert payload["error_code"] == "PATH_REJECTED"


def _boundary_filler(total_bytes):
    """构造中等可压缩的填充字节：压缩后明显小于上限，压缩比也在 zip bomb 阈值内。"""
    rng = random.Random(20261112)
    out = bytearray(total_bytes)
    out[0::4] = rng.randbytes(len(out[0::4]))
    filler = bytes(out)
    assert len(filler) == total_bytes
    return filler


def test_size_limit_exact_boundary_passes_and_one_over_fails(tmp_path):
    """体积边界：展开 payload 恰好 20 MiB 通过，超 1 字节拒绝。"""
    exact = tmp_path / "exact.zip"
    synthetic_package(
        exact, [(f"{BRIDGE_INSTALL_DIR}/core.py", _boundary_filler(SIZE_LIMIT_BYTES))]
    )
    code, payload, _stderr = _diagnose_code(exact)
    assert code == EXIT_CODES["OK"], payload
    assert payload["payload_expanded_bytes"] == SIZE_LIMIT_BYTES

    over = tmp_path / "over.zip"
    synthetic_package(
        over, [(f"{BRIDGE_INSTALL_DIR}/core.py", _boundary_filler(SIZE_LIMIT_BYTES + 1))]
    )
    code, payload, _stderr = _diagnose_code(over)
    assert code == EXIT_CODES["SIZE_LIMIT"]
    assert payload["error_code"] == "SIZE_LIMIT"


def test_zip_bomb_ratio_is_rejected(tmp_path):
    """高压缩比成员按 zip bomb 拒绝。"""
    package = tmp_path / "bomb.zip"
    synthetic_package(package, [(f"{BRIDGE_INSTALL_DIR}/core.py", b"\0" * (4 * 1024 * 1024))])
    code, payload, _stderr = _diagnose_code(package)
    assert code == EXIT_CODES["SIZE_LIMIT"]
    assert payload["error_code"] == "SIZE_LIMIT"


def test_missing_meta_members_are_rejected(tmp_path):
    package = tmp_path / "no-usage.zip"
    synthetic_package(
        package,
        SIMPLE_PAYLOAD,
        member_names={"meta/使用说明.md": "meta/使用说明.txt"},
    )
    code, payload, _stderr = _diagnose_code(package)
    assert code == EXIT_CODES["INTEGRITY_MISMATCH"]
    assert payload["error_code"] == "INTEGRITY_MISMATCH"


# --------------------------------------------------------------------------- #
# 安装 / 回滚错误分支
# --------------------------------------------------------------------------- #


def test_existing_owned_content_conflicts_with_zero_writes(tmp_path):
    package = tmp_path / "pkg.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    sandbox_parent, target, sentinel = make_sandbox(tmp_path)
    conflicting = target / BRIDGE_INSTALL_DIR / "core.py"
    conflicting.parent.mkdir(parents=True, exist_ok=True)
    conflicting.write_bytes(b"# pre-existing non-owned content\n")
    before = tree_snapshot(target)

    code, payload, _stdout, stderr = run_cli(
        "install",
        "--package",
        str(package),
        "--sandbox-parent",
        str(sandbox_parent),
        "--target",
        str(target),
    )
    assert code == EXIT_CODES["CONFLICT"]
    assert payload["error_code"] == "CONFLICT"
    assert tree_snapshot(target) == before
    assert not (target / WORKFLOWS_INSTALL_DIR).exists()


def test_install_failure_midway_reverts_committed_owned_items(tmp_path):
    """安装中途故障：已 commit 的 owned 项必须回退，非 owned 字节保留。"""
    package = tmp_path / "pkg.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    sandbox_parent, target, sentinel = make_sandbox(tmp_path)
    # 让第二个 owned 顶层目录的 rename 失败：workflows 先是一个普通文件。
    blocker = target / "workflows"
    blocker.write_bytes(b"not a directory\n")
    before = tree_snapshot(target)

    code, payload, _stdout, stderr = run_cli(
        "install",
        "--package",
        str(package),
        "--sandbox-parent",
        str(sandbox_parent),
        "--target",
        str(target),
    )
    assert code == EXIT_CODES["INSTALL_FAILED"]
    assert payload["error_code"] == "INSTALL_FAILED"
    # 已 commit 的 owned 项被回退。
    assert not (target / BRIDGE_INSTALL_DIR).exists()
    assert not (target / "custom_nodes").exists()
    # 非 owned 字节保留。
    assert blocker.read_bytes() == b"not a directory\n"
    assert tree_snapshot(target) == before
    detail = payload["detail"]
    assert detail["original_failure"]["error_code"]
    assert detail["cleanup"]["staging_removed"] is True
    # 失败不得留下暂存目录。
    assert not [entry for entry in sandbox_parent.iterdir() if entry.name.startswith(".lvw-v0-stage-")]


def test_user_modified_install_blocks_rollback_and_preserves_bytes(tmp_path):
    package = tmp_path / "pkg.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    sandbox_parent, target, sentinel = make_sandbox(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    code, _payload, _stdout, stderr = run_cli(
        "install",
        "--package",
        str(package),
        "--sandbox-parent",
        str(sandbox_parent),
        "--target",
        str(target),
        "--receipt-out",
        str(receipt_path),
    )
    assert code == EXIT_CODES["OK"], stderr

    edited = target / BRIDGE_INSTALL_DIR / "core.py"
    edited.write_bytes(b"# user edited this file\n")
    edited_bytes = edited.read_bytes()

    code, payload, _stdout, stderr = run_cli(
        "rollback", "--receipt", str(receipt_path), "--target", str(target)
    )
    assert code == EXIT_CODES["ROLLBACK_CONFLICT"]
    assert payload["error_code"] == "ROLLBACK_CONFLICT"
    # 用户字节保留，不做删除。
    assert edited.read_bytes() == edited_bytes
    assert payload["detail"]["drifted_owned_files"]
    assert payload["detail"]["removed"] == []


def test_rollback_reports_missing_owned_file_as_conflict(tmp_path):
    package = tmp_path / "pkg.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    sandbox_parent, target, sentinel = make_sandbox(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    code, _payload, _stdout, stderr = run_cli(
        "install",
        "--package",
        str(package),
        "--sandbox-parent",
        str(sandbox_parent),
        "--target",
        str(target),
        "--receipt-out",
        str(receipt_path),
    )
    assert code == EXIT_CODES["OK"], stderr
    (target / BRIDGE_INSTALL_DIR / "core.py").unlink()
    code, payload, _stdout, stderr = run_cli(
        "rollback", "--receipt", str(receipt_path), "--target", str(target)
    )
    assert code == EXIT_CODES["ROLLBACK_CONFLICT"]
    assert payload["detail"]["missing_owned_files"]


def test_rollback_never_deletes_non_owned_files(tmp_path):
    """回滚只删本轮 owned 文件；非 owned 字节必须保留。"""
    package = tmp_path / "pkg.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    sandbox_parent, target, sentinel = make_sandbox(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    code, _payload, _stdout, stderr = run_cli(
        "install",
        "--package",
        str(package),
        "--sandbox-parent",
        str(sandbox_parent),
        "--target",
        str(target),
        "--receipt-out",
        str(receipt_path),
    )
    assert code == EXIT_CODES["OK"], stderr
    # 安装完成后，用户在 owned 目录里放了一个非 owned 文件。
    other = target / BRIDGE_INSTALL_DIR / "其它 节点.py"
    other.write_bytes(b"# another node, not owned\n")
    code, rollback_payload, _stdout, stderr = run_cli(
        "rollback", "--receipt", str(receipt_path), "--target", str(target)
    )
    assert code == EXIT_CODES["OK"], stderr
    # 非 owned 字节保留，目录因含非 owned 内容而保留并被报告。
    assert other.read_bytes() == b"# another node, not owned\n"
    assert rollback_payload["removed_files"]
    retained = {entry["path"] for entry in rollback_payload["retained_directories"]}
    assert BRIDGE_INSTALL_DIR in retained
    assert all(
        entry["non_empty"] for entry in rollback_payload["retained_directories"]
    )


# --------------------------------------------------------------------------- #
# 沙箱 / 宿主边界
# --------------------------------------------------------------------------- #


def test_production_host_path_is_rejected(tmp_path):
    package = tmp_path / "pkg.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    host = tmp_path / "ComfyUI-aki-v2"
    host.mkdir(parents=True, exist_ok=True)
    (host / SANDBOX_MARKER_NAME).write_text(
        json.dumps({"magic": SANDBOX_MARKER_MAGIC, "tool": TOOL_NAME}), encoding="utf-8"
    )
    target = host / "custom_nodes"
    code, payload, _stdout, stderr = run_cli(
        "install",
        "--package",
        str(package),
        "--sandbox-parent",
        str(host),
        "--target",
        str(target),
    )
    assert code == EXIT_CODES["PATH_REJECTED"]
    assert payload["error_code"] == "PATH_REJECTED"


def test_target_outside_sandbox_parent_is_rejected(tmp_path):
    package = tmp_path / "pkg.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    sandbox_parent, _target, _sentinel = make_sandbox(tmp_path)
    outside = tmp_path / "外部 目录"
    outside.mkdir(parents=True, exist_ok=True)
    code, payload, _stdout, stderr = run_cli(
        "install",
        "--package",
        str(package),
        "--sandbox-parent",
        str(sandbox_parent),
        "--target",
        str(outside),
    )
    assert code == EXIT_CODES["PATH_REJECTED"]
    assert payload["error_code"] == "PATH_REJECTED"
    assert not (outside / BRIDGE_INSTALL_DIR).exists()


def test_missing_sandbox_marker_is_rejected(tmp_path):
    package = tmp_path / "pkg.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    sandbox_parent, target, _sentinel = make_sandbox(tmp_path, marker=False)
    code, payload, _stdout, stderr = run_cli(
        "install",
        "--package",
        str(package),
        "--sandbox-parent",
        str(sandbox_parent),
        "--target",
        str(target),
    )
    assert code == EXIT_CODES["BAD_INPUT"]
    assert payload["error_code"] == "BAD_INPUT"
    assert not (target / BRIDGE_INSTALL_DIR).exists()


def test_validation_failure_leaves_no_empty_install_dir(tmp_path):
    """校验失败不得写 target，也不得留下空安装目录。"""
    package = tmp_path / "tampered.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(package) as archive:
            members = [(i.filename, archive.read(i.filename)) for i in archive.infolist()]
    _write_zip(
        package,
        [(name, data + b"# tamper\n" if name.startswith("payload/") else data)
         for name, data in members],
    )
    sandbox_parent, target, _sentinel = make_sandbox(tmp_path)
    before = tree_snapshot(target)
    code, _payload, _stdout, stderr = run_cli(
        "install",
        "--package",
        str(package),
        "--sandbox-parent",
        str(sandbox_parent),
        "--target",
        str(target),
    )
    assert code == EXIT_CODES["INTEGRITY_MISMATCH"]
    assert tree_snapshot(target) == before
    assert not (target / BRIDGE_INSTALL_DIR).exists()
    assert not (target / WORKFLOWS_INSTALL_DIR).exists()


def test_diagnose_does_not_write_to_target(tmp_path):
    package = tmp_path / "pkg.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    sandbox_parent, target, _sentinel = make_sandbox(tmp_path)
    before = tree_snapshot(target)
    code, _payload, _stdout, stderr = run_cli(
        "diagnose",
        "--package",
        str(package),
        "--target",
        str(target),
        "--sandbox-parent",
        str(sandbox_parent),
    )
    assert code == EXIT_CODES["OK"], stderr
    assert tree_snapshot(target) == before


# --------------------------------------------------------------------------- #
# CLI 契约
# --------------------------------------------------------------------------- #


def test_cli_help_and_version():
    for args in (["--help"], ["build", "--help"], ["diagnose", "--help"],
                 ["install", "--help"], ["rollback", "--help"]):
        code, _payload, stdout, _stderr = run_cli(*args)
        assert code == 0
        assert "usage:" in stdout
    code, _payload, stdout, _stderr = run_cli("--version")
    assert code == 0
    assert TOOL_NAME in stdout


def test_cli_emits_structured_json_on_stdout_and_diagnostics_on_stderr(tmp_path):
    package = tmp_path / "pkg.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    code, payload, stdout, stderr = run_cli("diagnose", "--package", str(package))
    assert code == EXIT_CODES["OK"]
    assert json.loads(stdout)["status"] == "OK"
    assert payload["checks"]
    assert stderr.strip(), "诊断信息必须写到 stderr"


def test_cli_failure_emits_json_and_nonzero_exit(tmp_path):
    missing = tmp_path / "missing.zip"
    code, payload, stdout, _stderr = run_cli("diagnose", "--package", str(missing))
    assert code == EXIT_CODES["BAD_INPUT"]
    assert code != 0
    assert json.loads(stdout)["status"] == "FAILED"
    assert payload["error_code"] == "BAD_INPUT"


def test_error_code_exit_code_table_is_stable():
    """冻结的错误码与退出码映射。"""
    assert EXIT_CODES["BAD_INPUT"] == 2
    assert EXIT_CODES["INTEGRITY_MISMATCH"] == 3
    assert EXIT_CODES["PATH_REJECTED"] == 4
    assert EXIT_CODES["SIZE_LIMIT"] == 5
    assert EXIT_CODES["CONFLICT"] == 6
    assert EXIT_CODES["INSTALL_FAILED"] == 7
    assert EXIT_CODES["ROLLBACK_CONFLICT"] == 8


def test_redact_root_removes_absolute_paths_from_output(tmp_path):
    """--redact-root 必须把绝对路径从 stdout、stderr 与收据里脱敏掉。"""
    package = tmp_path / "pkg.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    receipt_path = tmp_path / "收据.json"
    code, payload, stdout, stderr = run_cli(
        "diagnose",
        "--package",
        str(package),
        "--receipt-out",
        str(receipt_path),
        "--redact-root",
        str(tmp_path),
    )
    assert code == EXIT_CODES["OK"]
    assert str(tmp_path) not in stdout
    assert str(tmp_path) not in stderr
    assert str(tmp_path) not in receipt_path.read_text(encoding="utf-8")
    assert "<redacted-root>" in stdout
    assert payload["package"]["path"].startswith("<redacted-root>")


def test_redact_root_handles_paths_with_chinese_and_spaces(tmp_path):
    """含中文与空格的路径在脱敏后必须整体被替换。"""
    sandbox_parent, target, _sentinel = make_sandbox(tmp_path)
    package = tmp_path / "pkg.zip"
    synthetic_package(package, SIMPLE_PAYLOAD)
    code, _payload, stdout, stderr = run_cli(
        "diagnose",
        "--package",
        str(package),
        "--target",
        str(target),
        "--sandbox-parent",
        str(sandbox_parent),
        "--redact-root",
        str(sandbox_parent),
    )
    assert code == EXIT_CODES["OK"]
    assert str(sandbox_parent) not in stdout
    assert str(sandbox_parent) not in stderr


def test_tool_contains_no_shell_execution_interface():
    """工具不得包含任意 shell 执行接口。"""
    source = TOOL_PATH.read_text(encoding="utf-8")
    for forbidden in ("os.system", "os.popen", "shell=True", "commands.getoutput"):
        assert forbidden not in source, f"tool must not expose {forbidden}"


def test_tool_is_stdlib_only():
    """工具不得引入第三方依赖（只检查真实 import 语句）。"""
    source = TOOL_PATH.read_text(encoding="utf-8")
    imported = set()
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            imported.add(stripped[len("import "):].split()[0].split(".")[0])
        elif stripped.startswith("from ") and " import " in stripped:
            imported.add(stripped[len("from "):].split()[0].split(".")[0])
    third_party = imported & {"requests", "numpy", "yaml", "PIL", "pandas", "click", "toml"}
    assert not third_party, f"工具不得依赖第三方库: {third_party}"
