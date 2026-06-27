# 计划目录说明

后续新的文件化计划统一存放在 `plan/` 目录下，不再继续在项目根目录新增 `task_plan.md`、`findings.md`、`progress.md`。

## 约定
- 每个plan完成后都需要打上标记，避免重复执行
- 每个独立任务使用一个单独子目录。
- 每个子目录固定包含：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
- 子目录命名建议：
  - `YYYY-MM-DD-任务短名`
  - 例如：`2026-06-13-source-channel-pool`

## 兼容说明

- 项目根目录下已有的 `task_plan.md`、`findings.md`、`progress.md` 视为历史计划，保留不动。
- 新计划不得覆盖或混写到旧计划文件中。
- 如后续需要继续旧任务，应优先在原有计划目录内续写，而不是新建重复计划。
