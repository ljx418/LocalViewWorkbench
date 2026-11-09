# 可视残差输入纠偏：离线完成，真实验证未运行

候选96e77ea3691cf68422ccd159c85985b4d9a118ec。用户本轮要求继续到人工验收；按既有母授权继续离线开发，不将普通继续解释为每Stage3轮上限的额外额度。

源帧仍按F1..F4/实际秒数完整缩略展示；下方D1→2等为逐RGB通道绝对差的派生可视化，并非额外采样帧、场景内容或运动方向真值。不裁切源帧，不替换样本，单一PNG最大768×768，一次Provider请求，原FrameRef/SHA/PTS/raw/显式采纳/预算守卫保留；video内部模板1.2.0与presentation temporal-sheet/2-residual可追溯。公共合同、固定UM10、质量与资源阈值不变，不增加依赖。

124项离线回归通过，权限增量支持落盘后最终34项Provider/预算定向通过。源输入独审158个独立合成断言/完整源缩略图/absRGB字节oracle/边界/单HTTP/raw/资源检查通过；预算独审28项SQLite/privateGit检查通过，双方Fatal0/Major0/Minor0，均绑定96e77ea。所有预览只用合成像素，无模型、服务或媒体探测。

新增预算保护代码只接受精确人批且hash匹配的AUTH-BUDGET-V1-R1-RESIDUAL-01：R1/live08、限一次完整运行、stage3→4、模型≤8/1800秒、母授权512动作/8轮/24h不变；候选祖先/冻结源零差异、请求/批准撤销或漂移、终态过期与重放均拒绝。当前没有approval、没有live08目录，真实账本仍3轮/9动作/178秒。

请求文件authorization-residual-recheck-01.request.json已绑定候选，源/权限独审证据在independent-residual-*。本次不签语义通过、不请求人工体验代跑，只有显式预算增量批准后才能进行下一新鲜真实复验。
