# Independent Review Template

```text
Project / Stage / Workpack:
Candidate SHA:
Spec version / acceptance hash / gate version:
Reviewer identity and isolated session:
Implementation session (must differ):
Environment and source checkout:
```

## Reproduction

- Commands and exit codes:
- Fixed denominator recomputation:
- Public production entry traced:
- Negative/failure/cleanup paths:
- Candidate/evidence hash match:

## Findings

每项必须包含 severity、file/line、trigger、expected、actual、raw evidence、reproduction。审查者不直接修改候选。

## Conclusion

```text
Fatal:
Major:
Minor:
Recommended gate status:
Limitations:
```

## ADR-16 分层与完整纠偏

逐发现记录 affected_layer、canonical_result、candidate/evidence绑定、原始失败与清理事实、是否假绿/产品影响、classification_reason、原始证据引用、独立审查身份及技术债owner/退出条件。只有docs/36全部条件满足才可将纯辅助附加诊断列Minor；无法取证不降级。历史发现通过新裁决关联，不编辑旧报告。一次审完同根因/共享影响；原始历史用路径/hash引用，避免递归复制。
