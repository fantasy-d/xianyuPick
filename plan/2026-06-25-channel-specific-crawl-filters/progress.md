# 进度日志：按渠道配置 1688 商品列表筛选项

## 会话：2026-06-27

### 阶段 0：计划与调研再次细化
- **状态：** completed
- 执行的操作：
  - 重新审阅 `plan/2026-06-25-channel-specific-crawl-filters/` 下现有计划，确认当前问题不是“没有计划”，而是计划没有对这批新增筛选项形成足够细的实施顺序。
  - 再次对齐现有代码事实，确认以下能力已经存在：
    - `src/xianyu_tools/channel_search_filters.py` 中已定义 11 个共享筛选项
    - `web/app.jsx` 中已存在对应前端筛选项元数据
    - `src/xianyu_tools/config.py` 中已具备 `channel_search_filters` 归一化和读取能力
  - 重新整理本轮新增诉求的真正重点：
    - 新增的 11 个筛选项要按渠道区分
    - 需要同时考虑决策资产库和详情页如何展示渠道与筛选策略
    - 需要把“筛选项配置”和“固定排序策略”继续强制分开
  - 重写 `task_plan.md`，将计划从“功能描述”改成可执行批次：
    - 阶段 1：渠道级配置行为收口
    - 阶段 2：运行时快照与结果追溯
    - 阶段 3：第一批 query 候选项真实接入
    - 阶段 4：UI 勾选候选项 / 特殊面板项调研
    - 阶段 5：决策资产库与详情页展示收口
    - 阶段 6：联调与回归验证
  - 重写 `findings.md`，将调研结论明确拆成：
    - 已确认事实
    - 11 个筛选项的当前判断
    - 需要继续补的页面证据 / 结果证据
    - 实施消费方式
- 阶段性输出：
  - 计划现已明确区分：
    - 渠道级配置
    - runtime 快照
    - query 候选项真实生效
    - 资产库 / 详情页展示
  - 已明确 `encrypted_waybill` 不应和常规 query 候选项混推，需要单独按 special panel candidate 路线处理。
  - 已明确顶层资产卡片与详情页承担不同的信息密度：
    - 顶层只展示渠道摘要
    - 详情页展示渠道筛选摘要
- 创建/修改的文件：
  - `plan/2026-06-25-channel-specific-crawl-filters/task_plan.md`
  - `plan/2026-06-25-channel-specific-crawl-filters/findings.md`

### 阶段 1：渠道级筛选配置初始化与清理规则落地
- **状态：** in_progress
- 执行的操作：
  - 调整 `src/xianyu_tools/config.py::_normalize_channel_search_filters(...)`：
    - 不再只保留请求中显式出现的渠道筛选项
    - 现在会按当前渠道列表自动补齐每个渠道的筛选配置容器
    - 对支持筛选能力的渠道补齐完整布尔字段
    - 对不支持筛选能力的渠道保留空 `filters`
  - 调整 `web/app.jsx::normalizeLocalCrawlConfig(...)`：
    - 前端本地归一化逻辑与后端对齐
    - 渠道新增、删除、切换后，`channel_search_filters` 会自动跟渠道列表对齐
    - 避免必须先点一次筛选复选框才生成该渠道的配置结构
  - 为后端验证脚本新增 `validate_channel_search_filters_default_initialization()`：
    - 校验空配置时会自动补齐已知渠道容器
    - 校验 `ali1688` 默认筛选字段完整且值全为 `false`
    - 校验不支持筛选能力的渠道仍保留空容器
  - 运行验证：
    - `/opt/anaconda3/envs/mytools/bin/python -m py_compile src/xianyu_tools/config.py scripts/validate_source_channel_config.py`
    - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
    - 结果：全部通过
- 阶段性输出：
  - 渠道级筛选配置现在具备“新增渠道即有默认容器、删除渠道自动清理脏项”的稳定行为。
  - 前后端对“渠道筛选配置默认值”的理解已统一，后续可继续推进阶段 1 里剩余的 UI 行为收口。
- 创建/修改的文件：
  - `src/xianyu_tools/config.py`
  - `web/app.jsx`
  - `scripts/validate_source_channel_config.py`

### 阶段 1.1：渠道切换与筛选编辑焦点同步
- **状态：** in_progress
- 执行的操作：
  - 调整 `web/app.jsx` 中抓取配置编辑器的渠道焦点选择规则：
    - 如果用户已经手动切到某个抓取渠道，优先保留该选择
    - 否则优先跟随“货源渠道号池”当前激活渠道
    - 若当前激活渠道暂无可抓取账号，则回退到最近可编辑渠道
  - 调整以下交互处理函数：
    - `handleSourceChannelSwitch(...)`
      - 上方货源渠道切换时，下面抓取配置编辑区同步切换到同一渠道
    - `handleAddSourceChannel(...)`
      - 新增渠道后清空旧的抓取编辑焦点，让下游按新的有效渠道自动重选
    - `handleRemoveSourceChannel(...)`
      - 删除当前渠道时，抓取配置编辑焦点同步回落到下一个可用渠道
  - 在“货源渠道配置”区域新增说明提示：
    - 当抓取配置编辑区没有跟随当前激活渠道时，明确告诉用户：
      - 当前真正正在编辑的是哪个渠道
      - 未跟随的原因是“当前上方选中的渠道暂无可抓取账号”
- 阶段性输出：
  - “货源渠道号池”和“商品爬取与筛选配置”两块区域的渠道焦点现在更一致了。
  - 当两者不一致时，页面会给出明确说明，不再让用户误以为自己在编辑上方那个渠道。
  - 后端验证脚本再次回归通过：
    - `PYTHONPATH=src /opt/anaconda3/envs/mytools/bin/python scripts/validate_source_channel_config.py`
- 创建/修改的文件：
  - `web/app.jsx`

## 会话：2026-06-25

### 阶段 1：现状调研与边界确认
- **状态：** in_progress
- **开始时间：** 2026-06-25T22:00:00+08:00
- 执行的操作：
  - 读取 `planning-with-files-zh` 技能说明，确认本次计划文件应统一放在项目内 `plan/` 目录
  - 查看现有 `plan/` 目录，确认已有计划包与命名风格
  - 读取已完成计划 `plan/2026-06-22-crawl-source-channel-config/`，用于确认职责边界与避免冲突
  - 调研 `src/xianyu_tools/config.py` 中 `crawl_config` 的默认值与归一化逻辑
  - 调研 `src/web_api/main.py` 中 `/api/system/configs` 保存链路
  - 调研 `web/app.jsx` 中“商品爬取与筛选配置”现有数据结构
  - 调研 `src/xianyu_tools/source_adapter/ali1688.py` 中 1688 搜索 URL 固定参数
  - 调研 `scripts/run_ali1688_slow_flow.py` 中 1688 慢抓取主链路
  - 结合用户截图，整理 1688 列表页待配置的筛选项集合
  - 把原始计划改写为更细粒度的执行版，补充：
    - 字段映射表
    - 配置层 / 接口层 / 前端层 / runtime 层 / 追溯层切面
    - 分阶段实施顺序
    - 风险与回退策略
    - 验证矩阵
- 阶段性输出：
  - 明确筛选项配置属于 `crawl_config`，不属于 `source_channels`
  - 明确结构需要是“按渠道区分”的容器，而不是全局 1688 单例对象
  - 明确本次计划必须顺带考虑决策资产库和详情页的渠道追溯能力
  - 明确运行时首选“query 参数映射”，页面点击仅作二期兜底方案
- 创建/修改的文件：
  - `plan/2026-06-25-channel-specific-crawl-filters/task_plan.md`
  - `plan/2026-06-25-channel-specific-crawl-filters/findings.md`
  - `plan/2026-06-25-channel-specific-crawl-filters/progress.md`

### 阶段 2：配置模型设计
- **状态：** completed
- 执行的操作：
  - 确定 `channel_search_filters[]` 为最终配置容器
  - 固化 11 个 1688 筛选项 key
  - 固化“仅 `ali1688` 首期支持、其他渠道空 schema”的规则
  - 固化默认值、旧配置兼容策略和字段清洗规则
  - 固化追溯快照最小结构建议
- 创建/修改的文件：
  - `plan/2026-06-25-channel-specific-crawl-filters/task_plan.md`
  - `plan/2026-06-25-channel-specific-crawl-filters/findings.md`
  - `plan/2026-06-25-channel-specific-crawl-filters/progress.md`

### 阶段 3：后端归一化与配置读写改造规划
- **状态：** in_progress
- 执行的操作：
  - 在 `src/xianyu_tools/config.py` 中新增渠道筛选项默认值与归一化逻辑
  - 在 `src/xianyu_tools/config.py` 中加入 `ali1688` 支持字段白名单
  - 在 `web/app.jsx` 中补齐 `crawlConfig.channel_search_filters`，确保前端读写链路不丢新字段
  - 通过脚本验证：
    - 不存在的渠道会被清洗
    - 非白名单字段会被清洗
    - 白名单字段会补全为完整布尔快照
- 当前遗留：
  - 还未补后端单测
  - 还未把这些筛选项接入 1688 搜索 URL 或页面交互
- 创建/修改的文件：
  - `src/xianyu_tools/config.py`
  - `web/app.jsx`

### 阶段 4：1688 抓取运行时接入规划
- **状态：** in_progress
- 执行的操作：
  - 检索仓库内是否已经存在 1688 列表筛选文案对应的参数映射
  - 检索当前 `ali1688.py` 与相关脚本中的搜索 URL / 固定过滤参数使用点
  - 在 `src/xianyu_tools/config.py` 中新增 runtime helper：
    - `get_channel_search_filters(...)`
    - `get_channel_search_filter_snapshot(...)`
- 当前结论：
  - 仓库内暂未发现用户截图这 11 个筛选项的现成参数映射表
  - 但已发现旧实验产物命名中存在弱证据：
    - `dropship`
    - `dropship_free_shipping`
    - `return_shipping`
  - 因此筛选项应拆成两批：
    - 第一批：有仓库弱证据，可继续推进 runtime 验证
    - 第二批：只有截图需求，先停留在配置层
  - 后续需要单独验证 query 参数映射，不能直接硬编码猜测
  - 已进一步确认 runtime 的真实断点：
    - `scripts/run_full_pipeline.py` 当前不会把 `channel_search_filters` 传给 `run_ali1688_slow_flow.py`
    - `scripts/run_ali1688_slow_flow.py` 当前也没有接收渠道筛选快照的 CLI 参数
  - 已进一步确认结果追溯断点：
    - `summary.json` 当前没有筛选策略快照
    - `ali1688_sources` 当前没有筛选快照列
    - `GET /api/task_details/{task_id}` 当前虽已返回 `used_channels / channel_groups`，但没有渠道筛选摘要
  - 已开始首批实现：
    - `src/xianyu_tools/config.py`
      - `get_channel_search_filter_snapshot(...)` 现已补充：
        - `supported_filter_keys`
        - `enabled_filter_keys`
    - `scripts/run_full_pipeline.py`
      - 已把当前渠道的筛选快照写入每个商品目录下的 `_channel_filter_snapshot.json`
      - 已把快照文件路径通过 `--channel-filter-snapshot-file` 传给 `run_ali1688_slow_flow.py`
    - `scripts/run_ali1688_slow_flow.py`
      - 已新增加载渠道筛选快照逻辑
      - 已为每条结果写出 `source_filter_snapshot`
      - 当前采用诚实快照策略：
        - `configured_filters`
        - `applied_filters`
        - `unapplied_filters`
        - `unapplied_reason_map`
      - 当前 `mapping_stage = snapshot_only`，明确表示“配置已进入 runtime，但尚未全部转成真实搜索参数”
    - `scripts/run_full_pipeline.py` / `src/web_api/main.py`
      - 已为 `ali1688_sources` 增加 `source_filter_snapshot_json` 列的自愈 DDL
      - 已在入库时写入筛选快照 JSON
    - `src/web_api/main.py`
      - `GET /api/task_details/{task_id}` 已把 `source_filter_snapshot` 带回前端
      - `channel_groups` 也会带首个可用的渠道筛选快照
    - `web/app.jsx`
      - 货源明细页已开始按渠道组展示筛选摘要：
        - 已配置
        - 已生效
        - 待映射
      - 当前会明确提示：真实搜索参数映射仍在继续接入
- 创建/修改的文件：
  - `src/xianyu_tools/config.py`
  - `scripts/run_full_pipeline.py`
  - `scripts/run_ali1688_slow_flow.py`
  - `src/web_api/main.py`
  - `web/app.jsx`
  - `plan/2026-06-25-channel-specific-crawl-filters/findings.md`
  - `plan/2026-06-25-channel-specific-crawl-filters/task_plan.md`
  - `plan/2026-06-25-channel-specific-crawl-filters/progress.md`

### 阶段 4.1：计划与调研再细化
- **状态：** in_progress
- 执行的操作：
  - 重新通读计划文件，识别“还停留在抽象层”的部分
  - 再次检索 runtime / 详情回流 / 前端消费关键字，确认现有代码断点
  - 复读以下精确文件以补强证据：
    - `src/xianyu_tools/source_adapter/ali1688.py`
    - `scripts/generate_ali1688_result_url_map_via_browser.py`
    - `scripts/run_source_resolution_from_browser_runs.py`
  - 把计划继续下钻到：
    - 实施拓扑
    - 配置/快照/结果三类数据契约
    - 逐文件实施清单
    - 分批次交付边界
    - 验收矩阵
    - 失败回退策略
- 当前新增结论：
  - 现有旧脚本只能提供“弱证据”，不能当正式参数映射来源
  - `ali1688.py` 当前抽象仍是“固定参数搜索”，还不是“动态筛选策略搜索”
  - 详情页链路已具备按渠道解释数据来源的 70% 基础，关键缺口是筛选快照
  - 本次实施必须强制区分：
    - 渠道筛选配置
    - 固定排序策略（预估纯利倒序）
- 创建/修改的文件：
  - `plan/2026-06-25-channel-specific-crawl-filters/task_plan.md`
  - `plan/2026-06-25-channel-specific-crawl-filters/findings.md`
  - `plan/2026-06-25-channel-specific-crawl-filters/progress.md`

### 阶段 5：前端系统设置页规划
- **状态：** in_progress
- 执行的操作：
  - 在 `web/app.jsx` 中新增 `CHANNEL_SEARCH_FILTER_META` 与 `getSupportedChannelSearchFilters(...)`
  - 将 `channel_search_filters` 纳入 `normalizeLocalCrawlConfig(...)`，确保前端本地归一化时同步清洗无效渠道和不支持字段
  - 在“商品爬取与筛选配置”中，为当前渠道增加“当前渠道货源筛选项”编辑区
  - 按分组渲染 11 个 1688 列表筛选项复选框：
    - 分销能力
    - 服务能力
    - 售后保障
    - 资质认证
  - 实现“切换渠道 -> 自动切换该渠道自己的筛选配置”的前端联动
  - 实现对不支持该能力的渠道展示空态文案
- 当前遗留：
  - 还未做浏览器侧联调验证
  - 还未把“已配置但未进入 runtime”的状态显式展示给用户
- 创建/修改的文件：
  - `web/app.jsx`

### 阶段 6：结果追溯与资产库影响评估
- **状态：** in_progress
- 计划执行的操作：
  - 确定结果侧追溯字段最小集
  - 评估资产列表与详情页未来消费这些数据的方式
- 创建/修改的文件：
  - `scripts/run_full_pipeline.py`
  - `scripts/run_ali1688_slow_flow.py`
  - `src/web_api/main.py`

### 阶段 6.1：任务级渠道摘要落地
- **状态：** in_progress
- 执行的操作：
  - 扩展 `GET /api/tasks`，按任务聚合 `ali1688_sources -> xianyu_items.task_id`，直接回传 `used_channels`
  - 每个渠道摘要包含：
    - `channel_id`
    - `channel_label`
    - `source_count`
  - 在前端新增 `getTaskUsedChannels(...)`
  - 在两处“决策资产库”任务卡片中展示渠道标签：
    - 任务队列页右栏“已归档历史任务”
    - 决策资产库顶层任务卡片
  - 这样用户在不进入详情页的情况下，也能一眼看出任务用了哪些渠道
- 当前结论：
  - 渠道追溯现在不再只存在于 `task_details`
  - 顶层资产卡片已经具备最小渠道可见性
- 创建/修改的文件：
  - `src/web_api/main.py`
  - `web/app.jsx`

### 阶段 3.1：渠道筛选配置清洗补充校验
- **状态：** in_progress
- 执行的操作：
  - 在 `scripts/validate_source_channel_config.py` 中新增 `validate_channel_search_filters_normalization()`
  - 覆盖以下校验路径：
    - 非法渠道被移除
    - `ali1688` 合法字段保留
    - 非法筛选字段被清洗
    - 缺省字段补全为 `false`
    - 不支持筛选能力的合法渠道保留空 `filters`
- 创建/修改的文件：
  - `scripts/validate_source_channel_config.py`

### 阶段 7：实施与验证清单预案
- **状态：** pending
- 计划执行的操作：
  - 固化实施顺序
  - 固化测试矩阵
  - 固化失败回退策略
- 创建/修改的文件：
  - 待开始

## 测试结果
| 测试 | 输入 | 预期结果 | 实际结果 | 状态 |
|------|------|---------|---------|------|
| 规划文件目录检查 | `ls -la plan` | 已有计划目录可复用，且本次可新增新计划包 | 已确认 `plan/` 目录存在且包含既有计划 | 通过 |
| 现有抓取配置调研 | 读取 `src/xianyu_tools/config.py` | 确认 `crawl_config` 当前结构与扩展点 | 已确认当前只有抓取数量、模型、渠道账号范围 | 通过 |
| 既有计划边界检查 | 读取 `plan/2026-06-22-crawl-source-channel-config/*` | 确认本计划不会与已完成计划冲突 | 已确认本次聚焦“渠道级筛选项”，与既有计划互补 | 通过 |
| 新版计划细化检查 | 复读 `task_plan.md` / `findings.md` / `progress.md` | 计划从概念级提升到可执行级 | 已补齐字段映射、实施切面、验证矩阵与追溯设计 | 通过 |
| 二次调研细化检查 | 复读 `ali1688.py` / 浏览器产物脚本 / 计划文件 | 计划进一步下钻到逐文件、逐契约、逐验收点 | 已补齐实施拓扑、快照契约、分批交付与失败回退 | 通过 |
| 仓库筛选证据检索 | 检索 `dropship/free_shipping/return_shipping` 相关命名 | 判断是否存在可复用弱证据 | 已确认旧实验产物命名存在对应线索，但不足以直接当正式参数映射 | 通过 |
| runtime 触点定位 | 读取 `scripts/run_full_pipeline.py` / `scripts/run_ali1688_slow_flow.py` | 确认配置是否已经进入 1688 子流程 | 已确认目前尚未透传 `channel_search_filters` | 通过 |
| 资产回流触点定位 | 读取 `src/web_api/main.py` 的 `task_details` 链路 | 确认详情页是否已有按渠道结构 | 已确认已有 `used_channels / channel_groups`，但无筛选摘要 | 通过 |
| 渠道筛选快照 helper 校验 | 构造 sample `crawl_config + source_channels` | 返回完整渠道筛选快照 | 已返回完整 `filters/supported_filter_keys/enabled_filter_keys` | 通过 |
| 脚本语法编译检查 | `PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache python3 -m py_compile ...` | 新增脚本和接口代码无语法错误 | 通过 | 通过 |
| 任务级渠道摘要聚合检查 | 复核 `/api/tasks` 聚合逻辑 | 任务列表接口可直接返回 `used_channels` | 已完成 SQL 聚合与字段回传 | 通过 |
| 渠道筛选清洗脚本校验 | `python3 scripts/validate_source_channel_config.py` | 新增渠道筛选配置校验全部通过 | 通过，新增 `channel_search_filters_normalization` 校验 | 通过 |

## 错误日志
| 时间戳 | 错误 | 尝试次数 | 解决方案 |
|--------|------|---------|---------|
| 2026-06-25 | `python -m py_compile` 默认 pycache 目录无权限 | 1 | 改用 `PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache` 后通过 |
| 2026-06-26 | 把 `web/app.jsx` 误用 `py_compile` 校验 | 1 | 改为只编译 Python 文件，并单独人工复核 JSX 改动片段 |

## 五问重启检查
| 问题 | 答案 |
|------|------|
| 我在哪里？ | 阶段 4：1688 抓取运行时接入规划 |
| 我要去哪里？ | 先打通“配置 -> runtime 快照 -> 资产详情回流”，再让第一批有弱证据的筛选项真正进入 runtime 生效 |
| 目标是什么？ | 为 1688 列表页筛选项建立“按渠道配置 + 可追溯 + 可分批生效”的抓取策略体系，并让决策资产库后续能解释每个渠道用了什么筛选策略 |
| 我学到了什么？ | 当前系统已具备渠道级抓取配置基础，且资产详情接口已有按渠道分组能力；真正缺失的是 runtime 透传层和筛选快照落地层 |
| 我做了什么？ | 已完成 schema 级设计、前端编辑区落位、runtime/helper 入口摸排，并把计划继续细化为“文件级 + 函数级 + 字段级”的实施清单 |

---
*当前处于“调研深化 + 实施前拆批”阶段：配置模型与前端编辑区已落位，下一步应先补 runtime 快照透传与结果回流，而不是直接硬猜全部筛选参数。*
