const { useState, useEffect, useRef, useMemo } = React;
const sourceSkuCache = new Map();
const DEFAULT_GROSS_PROFIT_RATE = 0.3;
const SOURCE_LIST_PAGE_SIZE = 10;
const TOKEN_LOG_PAGE_SIZE = 10;
const ORDER_PAGE_SIZE = 20;
const OPENAPI_ORDER_STATUS_OPTIONS = [
    { value: "11", label: "待付款" },
    { value: "12", label: "待发货" },
    { value: "21", label: "已发货" },
    { value: "22", label: "已完成" },
    { value: "23", label: "已退款" },
    { value: "24", label: "已关闭" },
];

const formatCentValueForInput = (value) => {
    const amount = Number(value);
    return Number.isFinite(amount) ? (amount / 100).toFixed(2) : '';
};

const isSourceDetailIncomplete = (source) => !!(
    source?.is_detail_incomplete
    || source?.source_is_detail_incomplete
    || source?.detail_status === 'failed'
    || source?.source_detail_status === 'failed'
);

const getSourceDetailIncompleteReason = (source) => (
    source?.detail_incomplete_reason
    || source?.source_detail_incomplete_reason
    || '1688 风控/验证码导致详情页未完整抓取'
);

const normalizeGrossProfitRate = (value) => {
    let rate = parseFloat(value);
    if (!Number.isFinite(rate) || rate <= 0) return DEFAULT_GROSS_PROFIT_RATE;
    if (rate > 1) rate = rate / 100;
    return Math.min(rate, 1);
};

// --- 任务类型标签组件 ---
const renderTaskTypeBadge = (inputType) => {
    const type = inputType || 'keyword';
    if (type === 'image') {
        return (
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-purple-100/80 text-purple-700 border border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800/40">
                <span className="material-symbols-outlined text-[11px] leading-none">image</span>
                以图搜图
            </span>
        );
    }
    if (type === 'url') {
        return (
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-blue-100/80 text-blue-700 border border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800/40">
                <span className="material-symbols-outlined text-[11px] leading-none">link</span>
                单品链接
            </span>
        );
    }
    return (
        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-amber-100/80 text-amber-700 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/40">
            <span className="material-symbols-outlined text-[11px] leading-none">search</span>
            品类扫描
        </span>
    );
};


// --- 日志视图组件 ---
const LogViewer = ({ tasks, hideHeader = false }) => {
    const [selectedTaskId, setSelectedTaskId] = useState(null);
    const [logContent, setLogContent] = useState('请选择一个任务来查看日志...');
    const logPollTimer = useRef(null);

    const fetchLogs = async () => {
        if (!selectedTaskId) return;
        try {
            const resp = await fetch(`/api/tasks/${selectedTaskId}/logs`);
            const text = await resp.text();
            setLogContent(text);
        } catch { setLogContent('无法加载日志。'); }
    };

    useEffect(() => {
        if (logPollTimer.current) clearInterval(logPollTimer.current);
        if (selectedTaskId) {
            fetchLogs();
            logPollTimer.current = setInterval(fetchLogs, 5000);
        }
        return () => clearInterval(logPollTimer.current);
    }, [selectedTaskId]);

    return (
        <div className="view-content">
            {!hideHeader && (
                <header className="mb-6">
                    <h1 className="font-sans text-2xl font-bold text-on-surface">任务日志中心</h1>
                    <p className="font-sans text-sm text-secondary mt-1">实时监控扫描Worker的后台标准输出日志。</p>
                </header>
            )}
            
            <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-5 mb-6 ambient-shadow flex items-center gap-4">
                <span className="font-sans text-sm font-semibold text-secondary whitespace-nowrap">选择活跃任务:</span>
                <div className="relative flex-1 max-w-md">
                    <select 
                        onChange={(e) => setSelectedTaskId(e.target.value)} 
                        defaultValue="" 
                        className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-sm rounded-lg px-4 py-2.5 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all cursor-pointer appearance-none"
                    >
                        <option value="" disabled>-- 请选择一个已启动的任务 --</option>
                        {tasks.map(t => <option key={t.id} value={t.id}>{t.keyword} (ID: {t.id})</option>)}
                    </select>
                    <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-secondary pointer-events-none">expand_more</span>
                </div>
            </div>

            <pre className="bg-surface-container-high border border-border-hairline text-on-surface font-mono text-xs p-5 rounded-xl whiteSpace-pre-wrap h-[60vh] overflow-y-auto shadow-inner">
                {logContent}
            </pre>
        </div>
    );
};

// --- AI Token 计量舱视图组件 ---
const TokenStatsView = ({ hideHeader = false }) => {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [tokenLogPage, setTokenLogPage] = useState(1);

    const fetchStats = async () => {
        try {
            setLoading(true);
            const resp = await fetch('/api/token/stats');
            const data = await resp.json();
            if (data.status === 'success') {
                setStats(data);
                setError(null);
                setTokenLogPage(1);
            } else {
                setError(data.message || '加载统计数据失败');
            }
        } catch (err) {
            setError('网络请求失败，请稍后重试');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchStats();
    }, []);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-[50vh] gap-4">
                <span className="material-symbols-outlined text-[48px] text-primary animate-spin">autorenew</span>
                <p className="font-sans text-sm text-secondary">正在计算 Token 账单明细...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-[50vh] gap-4 text-center">
                <span className="material-symbols-outlined text-[48px] text-error">error</span>
                <p className="font-sans text-sm text-error font-semibold">{error}</p>
                <button onClick={fetchStats} className="px-4 py-2 bg-primary text-on-primary rounded-lg text-xs font-semibold hover:bg-primary-hover transition-colors">重新加载</button>
            </div>
        );
    }

    const { summary, by_model, by_feature, recent_logs } = stats;
    const tokenLogTotalPages = Math.max(1, Math.ceil(recent_logs.length / TOKEN_LOG_PAGE_SIZE));
    const currentTokenLogPage = Math.max(1, Math.min(tokenLogPage, tokenLogTotalPages));
    const paginatedTokenLogs = recent_logs.slice(
        (currentTokenLogPage - 1) * TOKEN_LOG_PAGE_SIZE,
        currentTokenLogPage * TOKEN_LOG_PAGE_SIZE
    );

    return (
        <div className="view-content">
            <header className={`flex justify-between items-center ${hideHeader ? 'mb-4' : 'mb-6'}`}>
                {!hideHeader && (
                    <div>
                        <h1 className="font-sans text-2xl font-bold text-on-surface">AI Token 计量舱</h1>
                        <p className="font-sans text-sm text-secondary mt-1">系统大模型调用统计、模型消耗占比及审计流水线。</p>
                    </div>
                )}
                <button 
                    onClick={fetchStats}
                    className="flex items-center gap-1.5 px-4 py-2 bg-surface-container-high border border-border-hairline hover:bg-surface-container-highest text-on-surface hover:text-primary rounded-lg transition-colors font-sans text-xs font-semibold"
                >
                    <span className="material-symbols-outlined text-[16px]">autorenew</span>
                    <span>刷新面板</span>
                </button>
            </header>

            {/* Bento Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                {/* Card 1: Total Tokens */}
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-5 ambient-shadow glow-bg hover:border-primary transition-all duration-150 group relative overflow-hidden">
                    <div className="flex justify-between items-start mb-3">
                        <span className="font-sans text-xs font-semibold text-secondary uppercase tracking-wider">总 Token 消耗</span>
                        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                            <span className="material-symbols-outlined text-[18px]">generating_tokens</span>
                        </div>
                    </div>
                    <div className="font-mono text-3xl font-bold text-on-surface mb-2">
                        {summary.total_tokens.toLocaleString()}
                    </div>
                    <div className="text-[11px] text-secondary font-sans flex items-center gap-1">
                        <span>Prompt: {(summary.total_prompt_tokens).toLocaleString()}</span>
                        <span className="text-border-hairline">|</span>
                        <span>Completion: {(summary.total_completion_tokens).toLocaleString()}</span>
                    </div>
                </div>

                {/* Card 2: Calls */}
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-5 ambient-shadow glow-bg hover:border-primary transition-all duration-150 group relative overflow-hidden">
                    <div className="flex justify-between items-start mb-3">
                        <span className="font-sans text-xs font-semibold text-secondary uppercase tracking-wider">大模型调用次数</span>
                        <div className="w-8 h-8 rounded-lg bg-processing/10 flex items-center justify-center text-processing">
                            <span className="material-symbols-outlined text-[18px]">api</span>
                        </div>
                    </div>
                    <div className="font-mono text-3xl font-bold text-on-surface mb-2">
                        {summary.total_calls.toLocaleString()}
                    </div>
                    <div className="text-[11px] text-secondary font-sans">
                        单次均耗 {summary.total_calls > 0 ? Math.round(summary.total_tokens / summary.total_calls).toLocaleString() : 0} Token
                    </div>
                </div>

                {/* Card 3: Model Count */}
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-5 ambient-shadow glow-bg hover:border-primary transition-all duration-150 group relative overflow-hidden">
                    <div className="flex justify-between items-start mb-3">
                        <span className="font-sans text-xs font-semibold text-secondary uppercase tracking-wider">活跃模型数</span>
                        <div className="w-8 h-8 rounded-lg bg-success/10 flex items-center justify-center text-success">
                            <span className="material-symbols-outlined text-[18px]">robot_2</span>
                        </div>
                    </div>
                    <div className="font-mono text-3xl font-bold text-on-surface mb-2">
                        {summary.model_count} <span className="text-sm font-sans text-secondary font-normal">个</span>
                    </div>
                    <div className="text-[11px] text-secondary font-sans truncate">
                        主流模型: {by_model[0]?.model || '无'}
                    </div>
                </div>

                {/* Card 4: Feature Count */}
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-5 ambient-shadow glow-bg hover:border-primary transition-all duration-150 group relative overflow-hidden">
                    <div className="flex justify-between items-start mb-3">
                        <span className="font-sans text-xs font-semibold text-secondary uppercase tracking-wider">涉及功能类别</span>
                        <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center text-amber-500">
                            <span className="material-symbols-outlined text-[18px]">category</span>
                        </div>
                    </div>
                    <div className="font-mono text-3xl font-bold text-on-surface mb-2">
                        {summary.feature_count} <span className="text-sm font-sans text-secondary font-normal">种</span>
                    </div>
                    <div className="text-[11px] text-secondary font-sans truncate">
                        核心场景: {by_feature[0]?.feature || '无'}
                    </div>
                </div>
            </div>

            {/* Split Grid for Charts/Percentages */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                {/* Model Share */}
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 ambient-shadow">
                    <h3 className="font-sans text-sm font-bold text-on-surface mb-4 flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-[18px] text-primary">analytics</span>
                        <span>模型消耗占比</span>
                    </h3>
                    {by_model.length === 0 ? (
                        <p className="font-sans text-xs text-secondary py-8 text-center">暂无大模型调用数据</p>
                    ) : (
                        <div className="space-y-2">
                            {by_model.map(m => {
                                const percentage = summary.total_tokens > 0 ? (m.total_tokens / summary.total_tokens * 100).toFixed(1) : 0;
                                return (
                                    <div key={m.model} className="space-y-1.5">
                                        <div className="flex justify-between items-center text-xs">
                                            <span className="font-mono font-medium text-on-surface">{m.model}</span>
                                            <span className="font-sans text-secondary font-semibold">{m.total_tokens.toLocaleString()} ({percentage}%)</span>
                                        </div>
                                        <div className="w-full h-2 bg-surface-container-high rounded-full overflow-hidden">
                                            <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: `${percentage}%` }}></div>
                                        </div>
                                        <div className="text-[10px] text-secondary font-sans">
                                            调用次数: {m.calls.toLocaleString()} | Prompt: {m.prompt_tokens.toLocaleString()} | Completion: {m.completion_tokens.toLocaleString()}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Feature Share */}
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 ambient-shadow">
                    <h3 className="font-sans text-sm font-bold text-on-surface mb-4 flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-[18px] text-primary">dashboard_customize</span>
                        <span>功能消耗占比</span>
                    </h3>
                    {by_feature.length === 0 ? (
                        <p className="font-sans text-xs text-secondary py-8 text-center">暂无大模型调用数据</p>
                    ) : (
                        <div className="space-y-2">
                            {by_feature.map(f => {
                                const percentage = summary.total_tokens > 0 ? (f.total_tokens / summary.total_tokens * 100).toFixed(1) : 0;
                                return (
                                    <div key={f.feature} className="space-y-1.5">
                                        <div className="flex justify-between items-center text-xs">
                                            <span className="font-mono font-medium text-on-surface">{f.feature === 'source_relevance' ? '商品品类相关性判定 (source_relevance)' : f.feature}</span>
                                            <span className="font-sans text-secondary font-semibold">{f.total_tokens.toLocaleString()} ({percentage}%)</span>
                                        </div>
                                        <div className="w-full h-2 bg-surface-container-high rounded-full overflow-hidden">
                                            <div className="h-full bg-secondary rounded-full transition-all duration-500" style={{ width: `${percentage}%` }}></div>
                                        </div>
                                        <div className="text-[10px] text-secondary font-sans">
                                            调用次数: {f.calls.toLocaleString()} | Prompt: {f.prompt_tokens.toLocaleString()} | Completion: {f.completion_tokens.toLocaleString()}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>

            {/* Recent Logs Table */}
            <div className="bg-surface-container-lowest border border-border-hairline rounded-xl overflow-hidden ambient-shadow">
                <div className="px-6 py-4 border-b border-border-hairline flex justify-between items-center bg-surface-container-lowest">
                    <h3 className="font-sans text-sm font-bold text-on-surface flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-[18px] text-primary">receipt_long</span>
                        <span>审计流水日志</span>
                    </h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-surface-container-low border-b border-border-hairline">
                                <th className="p-4 font-sans text-[11px] font-bold text-secondary uppercase tracking-wider">时间</th>
                                <th className="p-4 font-sans text-[11px] font-bold text-secondary uppercase tracking-wider">场景功能</th>
                                <th className="p-4 font-sans text-[11px] font-bold text-secondary uppercase tracking-wider">大模型</th>
                                <th className="p-4 font-sans text-[11px] font-bold text-secondary uppercase tracking-wider">对应调研任务</th>
                                <th className="p-4 font-sans text-[11px] font-bold text-secondary uppercase tracking-wider text-right">Prompt</th>
                                <th className="p-4 font-sans text-[11px] font-bold text-secondary uppercase tracking-wider text-right">Completion</th>
                                <th className="p-4 font-sans text-[11px] font-bold text-secondary uppercase tracking-wider text-right">Total</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border-hairline">
                            {recent_logs.length === 0 ? (
                                <tr>
                                    <td colSpan="7" className="p-8 text-center font-sans text-xs text-secondary">
                                        暂无明细审计日志
                                    </td>
                                </tr>
                            ) : (
                                paginatedTokenLogs.map(log => (
                                    <tr key={log.id} className="hover:bg-surface-container-low/50 transition-colors">
                                        <td className="p-4 font-mono text-xs text-on-surface whitespace-nowrap">{log.created_at}</td>
                                        <td className="p-4 font-sans text-xs text-on-surface">
                                            {log.feature === 'source_relevance' ? (
                                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                                                    品类相关性判定
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300">
                                                    {log.feature}
                                                </span>
                                            )}
                                        </td>
                                        <td className="p-4 font-mono text-xs text-on-surface">{log.model}</td>
                                        <td className="p-4 font-sans text-xs text-secondary max-w-xs truncate">
                                            {log.task_keyword ? (
                                                <span title={log.task_keyword}>{log.task_keyword}</span>
                                            ) : log.task_id ? (
                                                <span className="font-mono text-[10px]" title={log.task_id}>Task: {log.task_id.slice(0, 8)}...</span>
                                            ) : (
                                                <span className="text-gray-400 italic">手动脚本或公共调用</span>
                                            )}
                                        </td>
                                        <td className="p-4 font-mono text-xs text-on-surface text-right">{log.prompt_tokens.toLocaleString()}</td>
                                        <td className="p-4 font-mono text-xs text-on-surface text-right">{log.completion_tokens.toLocaleString()}</td>
                                        <td className="p-4 font-mono text-xs font-bold text-primary text-right">{log.total_tokens.toLocaleString()}</td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
                {tokenLogTotalPages > 1 && (
                    <div className="flex justify-center items-center gap-4 px-6 py-4 border-t border-border-hairline bg-surface-container-lowest">
                        <button
                            type="button"
                            className="w-8 h-8 flex items-center justify-center rounded-lg border border-border-hairline bg-surface-container-lowest text-secondary hover:text-primary hover:border-primary transition-all disabled:opacity-40"
                            disabled={currentTokenLogPage <= 1}
                            onClick={() => setTokenLogPage(currentTokenLogPage - 1)}
                        >
                            <span className="material-symbols-outlined text-[18px]">chevron_left</span>
                        </button>
                        <span className="font-sans text-xs text-secondary font-semibold">
                            第 {currentTokenLogPage} / {tokenLogTotalPages} 页（共 {recent_logs.length} 条，每页 {TOKEN_LOG_PAGE_SIZE} 条）
                        </span>
                        <button
                            type="button"
                            className="w-8 h-8 flex items-center justify-center rounded-lg border border-border-hairline bg-surface-container-lowest text-secondary hover:text-primary hover:border-primary transition-all disabled:opacity-40"
                            disabled={currentTokenLogPage >= tokenLogTotalPages}
                            onClick={() => setTokenLogPage(currentTokenLogPage + 1)}
                        >
                            <span className="material-symbols-outlined text-[18px]">chevron_right</span>
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

// --- 发布预览模态弹窗组件（解决闪烁与退场动画） ---
const PublishPreviewModal = ({ src, editTitle, setEditTitle, editPrice, setEditPrice, skus, setSkus, loadingSkus, doPublish, onClose }) => {
    const [active, setActive] = useState(false);

    useEffect(() => {
        let frameId = requestAnimationFrame(() => {
            frameId = requestAnimationFrame(() => {
                setActive(true);
            });
        });

        document.body.style.overflow = 'hidden';

        return () => {
            cancelAnimationFrame(frameId);
            const hasOtherModal = document.querySelector('.detail-modal-overlay');
            if (!hasOtherModal) {
                document.body.style.overflow = '';
            }
        };
    }, []);

    const handleClose = () => {
        setActive(false);
        setTimeout(() => {
            onClose();
        }, 220);
    };

    const handleConfirm = () => {
        setActive(false);
        setTimeout(() => {
            doPublish();
        }, 220);
    };

    return ReactDOM.createPortal(
        <div 
            className={`preview-modal-overlay ${active ? 'active' : ''}`}
            onClick={handleClose}
        >
            <div 
                className={`preview-modal-wrapper ${active ? 'active' : ''}`}
                onClick={e => e.stopPropagation()}
            >
                <div className="px-6 py-4 border-b border-border-hairline flex justify-between items-center bg-surface-container-low">
                    <h3 className="font-sans text-base font-bold text-on-surface flex items-center gap-2">
                        <span className="material-symbols-outlined text-primary">publish</span>
                        闲鱼发布预览与定价
                    </h3>
                    <button onClick={handleClose} className="w-8 h-8 rounded-full hover:bg-surface-container-high flex items-center justify-center text-secondary hover:text-on-surface transition-all">
                        <span className="material-symbols-outlined text-[20px]">close</span>
                    </button>
                </div>

                <div className="p-6 overflow-y-auto max-h-[70vh]">
                    {/* 图片预览 */}
                    {src.images && src.images.length > 0 && (
                        <div className="flex gap-2.5 mb-5 flex-wrap">
                            {src.images.slice(0, 5).map((img, idx) => (
                                <img 
                                    key={idx} 
                                    src={img} 
                                    referrerPolicy="no-referrer"
                                    className="w-16 h-16 rounded-lg object-cover border border-border-hairline shadow-sm" 
                                />
                            ))}
                        </div>
                    )}

                    {/* 标题编辑 */}
                    <div className="mb-4">
                        <label className="font-sans text-xs font-semibold text-secondary block mb-1.5">商品标题（最多60字，自动过滤敏感词）</label>
                        <input 
                            value={editTitle} 
                            onChange={e => setEditTitle(e.target.value.slice(0, 60))}
                            className="w-full bg-surface-container-low border border-border-hairline text-on-surface rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all" 
                        />
                        <div className="text-right text-[11px] text-secondary mt-1 font-mono">{editTitle.length}/60</div>
                    </div>

                    {/* 售价与多规格编辑 */}
                    {loadingSkus ? (
                        <div className="py-6 text-center text-sm text-secondary flex items-center justify-center gap-2">
                            <span className="material-symbols-outlined animate-spin text-primary">sync</span>
                            正在加载规格库存信息...
                        </div>
                    ) : skus.length > 0 ? (
                        <div className="mb-5">
                            <label className="font-sans text-xs font-semibold text-secondary block mb-2">
                                规格售价与库存配置（进价默认加价 30 元）
                            </label>
                            <div className="max-h-56 overflow-y-auto border border-border-hairline rounded-lg bg-surface-container-low p-3 space-y-3">
                                {skus.map((s, idx) => (
                                    <div key={idx} className="flex items-center gap-3 pb-3 border-b border-border-hairline last:border-0 last:pb-0">
                                        {s.image && (
                                            <img 
                                                src={s.image} 
                                                referrerPolicy="no-referrer"
                                                className="w-8 h-8 rounded object-cover border border-border-hairline shrink-0" 
                                            />
                                        )}
                                        <span className="text-xs text-on-surface font-semibold flex-1 truncate" title={s.sku_text}>{s.sku_text}</span>
                                        
                                        <div className="flex items-center gap-1 shrink-0 w-36">
                                            <span className="text-[10px] text-secondary font-mono">进¥{s.price}→</span>
                                            <input 
                                                type="number" 
                                                min="0" 
                                                step="0.5" 
                                                value={s.xianyu_price}
                                                onChange={e => {
                                                    const val = e.target.value;
                                                    setSkus(prev => prev.map((item, i) => i === idx ? { ...item, xianyu_price: val } : item));
                                                }}
                                                className="w-16 bg-surface-container-lowest border border-border-hairline text-on-surface text-xs rounded px-1.5 py-1 text-center focus:outline-none focus:border-primary font-mono" 
                                            />
                                        </div>

                                        <div className="flex items-center gap-1 shrink-0 w-20">
                                            <span className="text-[10px] text-secondary">库存</span>
                                            <input 
                                                type="number" 
                                                min="1" 
                                                max="9999" 
                                                value={s.stock}
                                                onChange={e => {
                                                    const val = Math.min(9999, parseInt(e.target.value) || 1);
                                                    setSkus(prev => prev.map((item, i) => i === idx ? { ...item, stock: val } : item));
                                                }}
                                                className="w-12 bg-surface-container-lowest border border-border-hairline text-on-surface text-xs rounded px-1.5 py-1 text-center focus:outline-none focus:border-primary font-mono" 
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        /* 售价编辑（单规格） */
                        <div className="mb-5">
                            <label className="font-sans text-xs font-semibold text-secondary block mb-1.5">
                                售价（元）<span className="text-secondary font-normal ml-2">1688成本进价 ¥{src.min_price}，默认加价30元后 ¥{(parseFloat(src.min_price)+30).toFixed(2)}</span>
                            </label>
                            <div className="relative">
                                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-primary font-mono font-bold">¥</span>
                                <input 
                                    type="number" 
                                    min="0" 
                                    step="0.5" 
                                    value={editPrice} 
                                    onChange={e => setEditPrice(e.target.value)}
                                    className="w-full bg-surface-container-low border border-border-hairline text-on-surface rounded-lg pl-8 pr-3 py-2.5 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all font-mono font-bold" 
                                />
                            </div>
                        </div>
                    )}
                </div>

                <div className="px-6 py-4 border-t border-border-hairline flex gap-3 justify-end bg-surface-container-low">
                    <button 
                        onClick={handleClose} 
                        className="px-4 py-2 border border-border-hairline rounded-lg text-secondary font-sans text-xs font-semibold hover:bg-surface-container-high hover:text-on-surface transition-colors"
                    >
                        取消
                    </button>
                    <button 
                        onClick={handleConfirm} 
                        disabled={loadingSkus}
                        className="px-4 py-2 bg-primary hover:bg-primary-container text-white font-sans text-xs font-semibold rounded-lg shadow-sm disabled:opacity-50 transition-colors"
                    >
                        确认发布上架
                    </button>
                </div>
            </div>
        </div>,
        document.body
    );
};

const ActionConfirmModal = ({ title, description, confirmLabel, tone = 'warning', onConfirm, onClose }) => {
    const [active, setActive] = useState(false);

    useEffect(() => {
        let frameId = requestAnimationFrame(() => {
            frameId = requestAnimationFrame(() => {
                setActive(true);
            });
        });

        document.body.style.overflow = 'hidden';

        return () => {
            cancelAnimationFrame(frameId);
            const hasOtherModal = document.querySelector('.detail-modal-overlay');
            const hasPreviewModal = document.querySelector('.preview-modal-overlay');
            if (!hasOtherModal && !hasPreviewModal) {
                document.body.style.overflow = '';
            }
        };
    }, []);

    const handleClose = () => {
        setActive(false);
        setTimeout(() => {
            onClose();
        }, 220);
    };

    const handleConfirm = () => {
        setActive(false);
        setTimeout(() => {
            onConfirm();
        }, 220);
    };

    const toneClasses = tone === 'danger'
        ? 'bg-error hover:bg-error/90 text-white'
        : 'bg-warning hover:bg-warning/85 text-white';

    const descriptionLines = Array.isArray(description) ? description : [description];

    return ReactDOM.createPortal(
        <div
            className={`preview-modal-overlay ${active ? 'active' : ''}`}
            onClick={handleClose}
        >
            <div
                className={`preview-modal-wrapper ${active ? 'active' : ''}`}
                style={{ width: '480px' }}
                onClick={e => e.stopPropagation()}
            >
                <div className="px-6 py-4 border-b border-border-hairline flex justify-between items-center bg-surface-container-low">
                    <h3 className="font-sans text-base font-bold text-on-surface flex items-center gap-2">
                        <span className={`material-symbols-outlined ${tone === 'danger' ? 'text-error' : 'text-warning'}`}>warning</span>
                        {title}
                    </h3>
                    <button onClick={handleClose} className="w-8 h-8 rounded-full hover:bg-surface-container-high flex items-center justify-center text-secondary hover:text-on-surface transition-all">
                        <span className="material-symbols-outlined text-[20px]">close</span>
                    </button>
                </div>

                <div className="p-6">
                    <div className="rounded-xl border border-border-hairline bg-surface-container-low px-4 py-4">
                        <div className="flex items-start gap-3">
                            <div className={`mt-0.5 w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${tone === 'danger' ? 'bg-error/10 text-error' : 'bg-warning/10 text-warning'}`}>
                                <span className="material-symbols-outlined text-[20px]">priority_high</span>
                            </div>
                            <div className="space-y-2">
                                {descriptionLines.map((line, idx) => (
                                    <p key={idx} className="text-sm leading-relaxed text-secondary">
                                        {line}
                                    </p>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="px-6 py-4 border-t border-border-hairline flex gap-3 justify-end bg-surface-container-low">
                    <button
                        onClick={handleClose}
                        className="px-4 py-2 border border-border-hairline rounded-lg text-secondary font-sans text-xs font-semibold hover:bg-surface-container-high hover:text-on-surface transition-colors"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleConfirm}
                        className={`px-4 py-2 font-sans text-xs font-semibold rounded-lg shadow-sm transition-colors ${toneClasses}`}
                    >
                        {confirmLabel}
                    </button>
                </div>
            </div>
        </div>,
        document.body
    );
};

const TaskStartConfigModal = ({ keyword, crawlConfig, sourceChannelsConfig, llmConfig, onStart, onClose }) => {
    const [active, setActive] = useState(false);
    const [mode, setMode] = useState('confirm');
    const [draft, setDraft] = useState(() => ({
        source_limit_1688: Number(crawlConfig?.source_limit_1688 || 10),
        gross_profit_rate: normalizeGrossProfitRate(crawlConfig?.gross_profit_rate),
        source_filter_models: Array.isArray(crawlConfig?.source_filter_models) ? crawlConfig.source_filter_models : [],
        source_channel_selection_mode: crawlConfig?.source_channel_selection_mode || 'active_pool',
        enabled_source_channels: Array.isArray(crawlConfig?.enabled_source_channels) ? crawlConfig.enabled_source_channels : [],
        channel_search_filters: Array.isArray(crawlConfig?.channel_search_filters) ? crawlConfig.channel_search_filters : [],
    }));

    useEffect(() => {
        let frameId = requestAnimationFrame(() => {
            frameId = requestAnimationFrame(() => setActive(true));
        });
        document.body.style.overflow = 'hidden';
        return () => {
            cancelAnimationFrame(frameId);
            document.body.style.overflow = '';
        };
    }, []);

    const close = () => {
        setActive(false);
        setTimeout(onClose, 220);
    };

    const channels = Array.isArray(sourceChannelsConfig?.channels) ? sourceChannelsConfig.channels : [];
    const llmModels = Array.from(new Set(
        (Array.isArray(llmConfig) ? llmConfig : [])
            .flatMap(item => Array.isArray(item.models) ? item.models : [])
            .map(name => String(name || '').trim())
            .filter(Boolean)
    ));
    const filterMeta = [
        { key: 'rapid_invoice', label: '极速开票' },
        { key: 'selected_distributors', label: '分销严选' },
        { key: 'single_piece_drop_shipping', label: '一件代发' },
        { key: 'seven_day_return', label: '7天无理由' },
        { key: 'single_piece_free_shipping', label: '1件代发包邮' },
        { key: 'free_shipping', label: '包邮' },
        { key: 'freight_insurance_return', label: '退货包运费' },
        { key: 'real_factory_verified', label: '真实工厂认证' },
        { key: 'strength_verified', label: '实力认证' },
        { key: 'official_logistics', label: '官方物流' },
        { key: 'douyin_encrypted_waybill', label: '抖音面单' },
    ];

    const setSourceLimit = (value) => {
        let next = parseInt(value, 10) || 10;
        if (next < 1) next = 1;
        if (next > 100) next = 100;
        setDraft(prev => ({ ...prev, source_limit_1688: next }));
    };

    const setGrossRatePercent = (value) => {
        let next = parseInt(value, 10) || 30;
        if (next < 1) next = 1;
        if (next > 100) next = 100;
        setDraft(prev => ({ ...prev, gross_profit_rate: next / 100 }));
    };

    const toggleModel = (modelName) => {
        setDraft(prev => {
            const current = Array.isArray(prev.source_filter_models) ? prev.source_filter_models : [];
            const next = current.includes(modelName)
                ? current.filter(item => item !== modelName)
                : [...current, modelName];
            return { ...prev, source_filter_models: next };
        });
    };

    const toggleAccount = (channelId, accountId, checked) => {
        setDraft(prev => {
            const entries = Array.isArray(prev.enabled_source_channels) ? [...prev.enabled_source_channels] : [];
            const idx = entries.findIndex(item => item.channel_id === channelId);
            const entry = idx >= 0 ? { ...entries[idx] } : { channel_id: channelId, enabled: true, account_ids: [] };
            const accountIds = Array.isArray(entry.account_ids) ? [...entry.account_ids] : [];
            entry.account_ids = checked
                ? Array.from(new Set([...accountIds, accountId]))
                : accountIds.filter(item => item !== accountId);
            entry.enabled = entry.account_ids.length > 0;
            if (idx >= 0) entries[idx] = entry;
            else entries.push(entry);
            return { ...prev, source_channel_selection_mode: 'custom_selected', enabled_source_channels: entries };
        });
    };

    const toggleFilter = (channelId, filterKey, checked) => {
        setDraft(prev => {
            const entries = Array.isArray(prev.channel_search_filters) ? [...prev.channel_search_filters] : [];
            const idx = entries.findIndex(item => item.channel_id === channelId);
            const entry = idx >= 0 ? { ...entries[idx], filters: { ...(entries[idx].filters || {}) } } : { channel_id: channelId, filters: {} };
            entry.filters[filterKey] = checked;
            if (idx >= 0) entries[idx] = entry;
            else entries.push(entry);
            return { ...prev, channel_search_filters: entries };
        });
    };

    const getSelectedAccountIds = (channelId) => {
        const entry = (draft.enabled_source_channels || []).find(item => item.channel_id === channelId);
        return Array.isArray(entry?.account_ids) ? entry.account_ids : [];
    };

    const getFilterValues = (channelId) => {
        return ((draft.channel_search_filters || []).find(item => item.channel_id === channelId)?.filters) || {};
    };

    const summarizeEnabledChannel = (channel) => {
        const selectedAccountIds = getSelectedAccountIds(channel.channel_id);
        const accounts = (channel.accounts || []).filter(account => selectedAccountIds.includes(account.account_id));
        const accountLabels = accounts.map(account => {
            const realName = account.session_report?.account_name;
            return realName || account.label || account.account_id;
        });
        return {
            channelLabel: channel.label || channel.channel_id,
            accountLabels,
        };
    };

    const enabledChannelSummaries = channels
        .map(summarizeEnabledChannel)
        .filter(item => item.accountLabels.length > 0);

    const configuredFilterLabels = channels.flatMap(channel => {
        const values = getFilterValues(channel.channel_id);
        return filterMeta
            .filter(filter => values[filter.key])
            .map(filter => `${channel.label || channel.channel_id}：${filter.label}`);
    });

    const selectedModelLabels = (draft.source_filter_models || []).length > 0
        ? draft.source_filter_models
        : llmModels;

    const startWithConfig = (useDefault) => {
        onStart(useDefault ? crawlConfig : draft);
    };

    return ReactDOM.createPortal(
        <div className={`preview-modal-overlay ${active ? 'active' : ''}`} onClick={close}>
            <div
                className={`preview-modal-wrapper ${active ? 'active' : ''}`}
                style={{ width: mode === 'confirm' ? '640px' : '880px' }}
                onClick={e => e.stopPropagation()}
            >
                <div className="px-6 py-4 border-b border-border-hairline flex justify-between items-center bg-surface-container-low">
                    <h3 className="font-sans text-base font-bold text-on-surface flex items-center gap-2">
                        <span className="material-symbols-outlined text-primary">tune</span>
                        启动扫描配置
                    </h3>
                    <button onClick={close} className="w-8 h-8 rounded-full hover:bg-surface-container-high flex items-center justify-center text-secondary hover:text-on-surface transition-all">
                        <span className="material-symbols-outlined text-[20px]">close</span>
                    </button>
                </div>

                {mode === 'confirm' ? (
                    <div className="p-6 space-y-4">
                        <div className="rounded-xl border border-border-hairline bg-surface-container-low px-4 py-4">
                            <div className="text-sm font-semibold text-on-surface">是否使用系统默认商品爬取与筛选配置？</div>
                            <div className="mt-2 text-xs text-secondary leading-relaxed">
                                任务：<span className="font-semibold text-on-surface">{keyword}</span>。选择“自定义本次配置”只会影响本次任务，不会改动系统默认配置。
                            </div>
                        </div>
                        <div className="rounded-xl border border-primary/15 bg-primary/[0.03] px-4 py-4 space-y-3">
                            <div className="font-sans text-xs font-bold text-on-surface">当前系统默认配置概览</div>
                            <div className="flex flex-wrap gap-2 text-[11px]">
                                <span className="px-2.5 py-1 rounded-full bg-surface-container-lowest border border-border-hairline">
                                    1688 抓取 {draft.source_limit_1688} 条
                                </span>
                                <span className="px-2.5 py-1 rounded-full bg-surface-container-lowest border border-border-hairline">
                                    毛利率 {Math.round(normalizeGrossProfitRate(draft.gross_profit_rate) * 100)}%
                                </span>
                                <span className="px-2.5 py-1 rounded-full bg-surface-container-lowest border border-border-hairline">
                                    模型：{(draft.source_filter_models || []).length > 0 ? draft.source_filter_models.join('、') : '全部已保存模型'}
                                </span>
                            </div>
                            <div className="space-y-2 text-[11px]">
                                <div className="font-semibold text-secondary">货源渠道账号</div>
                                <div className="flex flex-wrap gap-2">
                                    {enabledChannelSummaries.length === 0 ? (
                                        <span className="px-2.5 py-1 rounded-full bg-warning/8 text-warning border border-warning/15">未选择可抓取账号</span>
                                    ) : enabledChannelSummaries.map(item => (
                                        <span key={`default-channel-${item.channelLabel}`} className="px-2.5 py-1 rounded-full bg-surface-container-lowest border border-border-hairline">
                                            {item.channelLabel}：{item.accountLabels.join('、')}
                                        </span>
                                    ))}
                                </div>
                            </div>
                            <div className="space-y-2 text-[11px]">
                                <div className="font-semibold text-secondary">货源筛选项</div>
                                <div className="flex flex-wrap gap-2">
                                    {configuredFilterLabels.length === 0 ? (
                                        <span className="px-2.5 py-1 rounded-full bg-surface-container-lowest border border-border-hairline">未启用</span>
                                    ) : configuredFilterLabels.map(label => (
                                        <span key={`default-filter-${label}`} className="px-2.5 py-1 rounded-full bg-success/8 text-success border border-success/15">
                                            {label}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="p-6 space-y-4 max-h-[82vh] overflow-y-auto">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <span className="font-sans text-xs text-secondary font-semibold">1688 商品爬取数量</span>
                                <div className="flex items-center gap-4">
                                    <input
                                        type="range"
                                        min="1"
                                        max="100"
                                        step="1"
                                        value={draft.source_limit_1688}
                                        onChange={(e) => setSourceLimit(e.target.value)}
                                        className="flex-1 h-1.5 bg-surface-container rounded-lg appearance-none cursor-pointer accent-primary"
                                    />
                                    <div className="flex items-center gap-1">
                                        <input
                                            type="number"
                                            min="1"
                                            max="100"
                                            step="1"
                                            value={draft.source_limit_1688}
                                            onChange={(e) => setSourceLimit(e.target.value)}
                                            className="w-16 bg-surface-container-low border border-border-hairline text-on-surface text-center font-mono text-xs rounded-lg px-2 py-1 focus:outline-none focus:border-primary"
                                        />
                                        <span className="font-sans text-xs text-secondary">条</span>
                                    </div>
                                </div>
                            </div>
                            <div className="space-y-2">
                                <span className="font-sans text-xs text-secondary font-semibold">预期净利润毛利率（%）</span>
                                <div className="flex items-center gap-4">
                                    <input
                                        type="range"
                                        min="1"
                                        max="100"
                                        step="1"
                                        value={Math.round(normalizeGrossProfitRate(draft.gross_profit_rate) * 100)}
                                        onChange={(e) => setGrossRatePercent(e.target.value)}
                                        className="flex-1 h-1.5 bg-surface-container rounded-lg appearance-none cursor-pointer accent-primary"
                                    />
                                    <div className="flex items-center gap-1">
                                        <input
                                            type="number"
                                            min="1"
                                            max="100"
                                            value={Math.round(normalizeGrossProfitRate(draft.gross_profit_rate) * 100)}
                                            onChange={(e) => setGrossRatePercent(e.target.value)}
                                            className="w-16 bg-surface-container-low border border-border-hairline text-on-surface text-center font-mono text-xs rounded-lg px-2 py-1 focus:outline-none focus:border-primary"
                                        />
                                        <span className="font-sans text-xs text-secondary">%</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-3">
                            <div className="flex items-center justify-between gap-3">
                                <div className="font-sans text-xs text-secondary font-semibold">货源渠道与账号</div>
                                <span className="text-[11px] text-secondary">勾选后仅影响本次任务</span>
                            </div>
                            {channels.length === 0 ? (
                                <div className="rounded-xl border border-warning/20 bg-warning/5 px-4 py-3 text-xs text-warning">
                                    当前系统配置中没有可用货源渠道。
                                </div>
                            ) : channels.map(channel => (
                                <div key={channel.channel_id} className="rounded-xl border border-border-hairline bg-surface-container-low p-3 space-y-3">
                                    <div className="font-sans text-xs font-bold text-on-surface">{channel.label || channel.channel_id}</div>
                                    {(channel.accounts || []).length === 0 ? (
                                        <div className="rounded-lg border border-dashed border-border-hairline bg-surface-container-lowest px-3 py-2 text-xs text-secondary">
                                            当前渠道暂无账号。
                                        </div>
                                    ) : (
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                            {(channel.accounts || []).map(account => {
                                                const accountName = account.session_report?.account_name;
                                                const statusText = account.session_report?.status_text || (account.session_report?.is_usable ? '登录正常' : '未检测');
                                                return (
                                            <label key={account.account_id} className="flex items-center gap-2 rounded-lg border border-border-hairline bg-surface-container-lowest px-3 py-2 text-xs cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={getSelectedAccountIds(channel.channel_id).includes(account.account_id)}
                                                    onChange={(e) => toggleAccount(channel.channel_id, account.account_id, e.target.checked)}
                                                    className="rounded border-secondary text-primary focus:ring-primary/20"
                                                />
                                                <span className="min-w-0">
                                                    <span className="font-semibold text-on-surface">{accountName || account.label || account.account_id}</span>
                                                    <span className="ml-2 text-secondary">{statusText}</span>
                                                </span>
                                            </label>
                                                );
                                            })}
                                        </div>
                                    )}
                                    <div className="flex flex-wrap gap-2 pt-2 border-t border-border-hairline/70">
                                        {filterMeta.map(filter => (
                                            <label key={filter.key} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full border border-border-hairline bg-surface-container-lowest text-[11px] cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={!!getFilterValues(channel.channel_id)[filter.key]}
                                                    onChange={(e) => toggleFilter(channel.channel_id, filter.key, e.target.checked)}
                                                    className="rounded border-secondary text-primary focus:ring-primary/20"
                                                />
                                                <span>{filter.label}</span>
                                            </label>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="space-y-3">
                            <div className="font-sans text-xs text-secondary font-semibold">商品相关性筛选模型（空则使用全部已保存模型）</div>
                            <div className="flex flex-wrap gap-2">
                                {llmModels.length === 0 ? (
                                    <span className="text-xs text-secondary">当前未读取到已保存模型。</span>
                                ) : llmModels.map(modelName => (
                                    <label key={modelName} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full border border-border-hairline bg-surface-container-low text-[11px] cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={(draft.source_filter_models || []).includes(modelName)}
                                            onChange={() => toggleModel(modelName)}
                                            className="rounded border-secondary text-primary focus:ring-primary/20"
                                        />
                                        <span>{modelName}</span>
                                    </label>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                <div className="px-6 py-4 border-t border-border-hairline flex gap-3 justify-end bg-surface-container-low">
                    <button
                        onClick={close}
                        className="px-4 py-2 border border-border-hairline rounded-lg text-secondary font-sans text-xs font-semibold hover:bg-surface-container-high hover:text-on-surface transition-colors"
                    >
                        取消
                    </button>
                    {mode === 'confirm' ? (
                        <>
                            <button
                                onClick={() => setMode('custom')}
                                className="px-4 py-2 border border-primary/25 text-primary rounded-lg font-sans text-xs font-semibold hover:bg-primary/5 transition-colors"
                            >
                                自定义本次配置
                            </button>
                            <button
                                onClick={() => startWithConfig(true)}
                                className="px-4 py-2 bg-primary hover:bg-primary-container text-white font-sans text-xs font-semibold rounded-lg shadow-sm transition-colors"
                            >
                                使用系统默认配置
                            </button>
                        </>
                    ) : (
                        <button
                            onClick={() => startWithConfig(false)}
                            className="px-4 py-2 bg-primary hover:bg-primary-container text-white font-sans text-xs font-semibold rounded-lg shadow-sm transition-colors"
                        >
                            启动
                        </button>
                    )}
                </div>
            </div>
        </div>,
        document.body
    );
};

// --- 商品详情模态弹窗组件（解决闪烁与退场动画） ---
const DetailModal = ({ item, onClose, onUpdateItem, handleStatusLoaded, batchStatusMap, batchResultMap, grossProfitRate = DEFAULT_GROSS_PROFIT_RATE }) => {
    const [active, setActive] = useState(false);
    const [skus, setSkus] = useState([]);
    const [loadingSkus, setLoadingSkus] = useState(false);
    const [showSkuSection, setShowSkuSection] = useState(false);
    const [showReferenceSection, setShowReferenceSection] = useState(false);
    const [showAiSection, setShowAiSection] = useState(false);

    useEffect(() => {
        if (!showSkuSection) {
            return;
        }

        const cachedSkus = sourceSkuCache.get(item.source_db_id);
        if (cachedSkus) {
            setSkus(cachedSkus);
            setLoadingSkus(false);
            return;
        }

        setLoadingSkus(true);
        fetch(`/api/source_skus/${item.source_db_id}`)
            .then(r => r.json())
            .then(res => {
                const nextSkus = res.skus || [];
                sourceSkuCache.set(item.source_db_id, nextSkus);
                setSkus(nextSkus);
            })
            .catch(err => console.error("加载详情SKU失败:", err))
            .finally(() => setLoadingSkus(false));
    }, [item.source_db_id, showSkuSection]);

    useEffect(() => {
        let frameId = requestAnimationFrame(() => {
            frameId = requestAnimationFrame(() => {
                setActive(true);
            });
        });

        document.body.style.overflow = 'hidden';

        return () => {
            cancelAnimationFrame(frameId);
            document.body.style.overflow = '';
        };
    }, []);

    const handleClose = () => {
        setActive(false);
        setTimeout(() => {
            onClose();
        }, 220);
    };

    const costPrice = parseFloat(item.source_price) || 0;
    const refPrice = parseFloat(item.ref_price) || 0;
    const normalizedGrossProfitRate = normalizeGrossProfitRate(grossProfitRate);
    const margin = (costPrice * normalizedGrossProfitRate).toFixed(2);
    
    // AI ROI 测算
    const roiPercentage = costPrice > 0 ? Math.round(((refPrice - costPrice) / costPrice) * 100) : 0;
    let recommendationBadge = "Strong Buy";
    let badgeColorClass = "bg-success/10 text-success border-success/20";
    let pulseColorClass = "bg-success";
    let aiAdvice = "利润空间巨大，超过 40% 的理想红线。且货源在同类厂家中最为稳定，建议立即上架抢占市场。";

    if (roiPercentage < 30) {
        recommendationBadge = "Low Margin";
        badgeColorClass = "bg-error/10 text-error border-error/20";
        pulseColorClass = "bg-error";
        aiAdvice = "该商品的利润低于 30%，存在一定程度的价格战风险，建议提高闲鱼端售价或者寻找更低价货源。";
    } else if (roiPercentage < 60) {
        recommendationBadge = "Good to Buy";
        badgeColorClass = "bg-warning/10 text-warning border-warning/20";
        pulseColorClass = "bg-warning";
        aiAdvice = "利润处于中等健康区间，可稳健切入。建议配合赠品等差异化策略来提升客单价及流量。";
    }

    const mockSrc = {
        db_id: item.source_db_id,
        title: item.source_title,
        min_price: item.source_price,
        url: item.source_url,
        images: item.source_image ? [item.source_image] : []
    };

    return ReactDOM.createPortal(
        <div 
            className={`detail-modal-overlay ${active ? 'active' : ''}`}
            onClick={handleClose}
        >
            <div 
                className={`detail-modal-wrapper ${active ? 'active' : ''} max-w-4xl`}
                style={{ width: '760px' }}
                onClick={e => e.stopPropagation()}
            >
                <div className="px-6 py-4 border-b border-border-hairline flex justify-between items-center bg-surface-container-low">
                    <h2 className="font-sans text-base font-bold text-on-surface flex items-center gap-2">
                        <span className="material-symbols-outlined text-primary">inventory</span>
                        选品商品档案
                    </h2>
                    <button className="w-8 h-8 rounded-full hover:bg-surface-container-high flex items-center justify-center text-secondary hover:text-on-surface transition-all" onClick={handleClose}>
                        <span className="material-symbols-outlined text-[20px]">close</span>
                    </button>
                </div>
                
                <div className="p-5 overflow-y-auto max-h-[72vh] flex gap-4">
                    {/* 左侧主要信息: Span 8 布局 */}
                    <div className="flex-1 flex flex-col gap-4">
                        <div className="flex gap-3 items-start">
                            {item.source_image ? (
                                <img 
                                    src={item.source_image} 
                                    className="w-28 h-28 rounded-xl object-cover border border-border-hairline ambient-shadow shrink-0" 
                                    referrerPolicy="no-referrer"
                                    loading="eager"
                                    decoding="async"
                                />
                            ) : (
                                <div className="w-28 h-28 rounded-xl bg-surface-container-low border border-border-hairline flex items-center justify-center text-secondary shrink-0 text-xs">
                                    暂无商品图片
                                </div>
                            )}
                            
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1.5">
                                    <span className="text-[10px] text-primary bg-primary/10 border border-primary/20 px-2 py-0.5 rounded font-bold">1688货源</span>
                                    <span className="text-[10px] text-secondary font-mono">DB_ID: {item.source_db_id}</span>
                                </div>
                                <h3 className="text-sm font-bold text-on-surface leading-snug line-clamp-2 hover:text-primary transition-colors">
                                    <a href={item.source_url} target="_blank" rel="noreferrer" className="flex items-center gap-1">
                                        {item.source_title}
                                        <span className="material-symbols-outlined text-xs text-secondary">open_in_new</span>
                                    </a>
                                </h3>
                                
                                <div className="grid grid-cols-2 gap-2 mt-3 p-3 bg-surface-container rounded-lg border border-border-hairline">
                                    <div>
                                        <span className="text-[10px] text-secondary block">闲鱼商品 ID</span>
                                        <span className="font-mono text-xs font-bold text-on-surface mt-0.5 block">{item.xianyu_item_id || '暂无云端ID'}</span>
                                    </div>
                                    <div>
                                        <span className="text-[10px] text-secondary block">加入/发布记录时间</span>
                                        <span className="text-xs font-semibold text-on-surface mt-0.5 block">{item.publish_time}</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* 爆款参考 */}
                        {item.ref_title && (
                            <div className="border border-border-hairline rounded-lg bg-surface-container-low">
                                <button
                                    type="button"
                                    onClick={() => setShowReferenceSection(prev => !prev)}
                                    className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-surface-container transition-colors rounded-lg"
                                >
                                    <span className="text-xs font-bold text-on-surface">关联参考爆款标题</span>
                                    <span className="material-symbols-outlined text-secondary text-[18px]" style={{ transform: showReferenceSection ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }}>
                                        expand_more
                                    </span>
                                </button>
                                {showReferenceSection && (
                                    <div className="px-3 pb-3 text-xs text-on-surface leading-relaxed break-words">
                                        {item.ref_title}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* SKU 规格明细板块 */}
                        <div className="border-t border-border-hairline pt-4">
                            <button
                                type="button"
                                onClick={() => setShowSkuSection(prev => !prev)}
                                className="w-full flex items-center justify-between rounded-lg border border-border-hairline bg-surface-container-low px-3 py-2 text-left hover:bg-surface-container transition-colors"
                            >
                                <span className="text-xs font-bold text-on-surface flex items-center gap-1.5">
                                    <span className="material-symbols-outlined text-primary text-[18px]">format_list_bulleted</span>
                                    商品规格明细
                                    {showSkuSection && <span className="text-secondary font-normal">({skus.length} 个规格)</span>}
                                </span>
                                <span className="material-symbols-outlined text-secondary text-[18px]" style={{ transform: showSkuSection ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }}>
                                    expand_more
                                </span>
                            </button>

                            {showSkuSection && (
                                <div className="mt-3">
                                    {loadingSkus ? (
                                        <div className="py-6 text-center text-xs text-secondary flex items-center justify-center gap-2">
                                            <span className="material-symbols-outlined animate-spin text-primary">sync</span>
                                            正在同步SKU明细中...
                                        </div>
                                    ) : skus.length > 0 ? (
                                        <div className="max-h-48 overflow-y-auto border border-border-hairline rounded-lg bg-surface-container-low p-1.5">
                                            <table className="w-full text-left border-collapse text-xs">
                                                <thead>
                                                    <tr className="border-b border-border-hairline">
                                                        <th className="p-2 font-bold text-secondary w-12 text-center">规格图</th>
                                                        <th className="p-2 font-bold text-secondary">规格描述</th>
                                                        <th className="p-2 font-bold text-secondary w-20">成本进价</th>
                                                        <th className="p-2 font-bold text-secondary w-20">建议闲鱼价</th>
                                                        <th className="p-2 font-bold text-secondary w-16 text-center">云仓库存</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {skus.map((sku, idx) => (
                                                        <tr key={idx} className="border-b border-border-hairline/40 last:border-0 hover:bg-primary/5 transition-colors">
                                                            <td className="p-2 text-center">
                                                                {sku.image ? (
                                                                    <img 
                                                                        src={sku.image}
                                                                        referrerPolicy="no-referrer"
                                                                        loading="lazy"
                                                                        decoding="async"
                                                                        className="w-8 h-8 rounded object-cover border border-border-hairline mx-auto" 
                                                                    />
                                                                ) : (
                                                                    <div className="w-8 h-8 rounded bg-surface-container border border-border-hairline flex items-center justify-center text-[9px] text-secondary mx-auto">无图</div>
                                                                )}
                                                            </td>
                                                            <td className="p-2 font-semibold text-on-surface break-words max-w-[150px]">
                                                                {sku.sku_text}
                                                            </td>
                                                            <td className="p-2 font-mono text-secondary">
                                                                ¥{sku.price}
                                                            </td>
                                                            <td className="p-2 font-mono text-primary font-bold">
                                                                ¥{(parseFloat(sku.price) + 30).toFixed(2)}
                                                            </td>
                                                            <td className={`p-2 text-center font-mono font-bold ${sku.stock > 10 ? 'text-success' : 'text-error'}`}>
                                                                {sku.stock}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    ) : (
                                        <div className="py-6 text-center text-xs text-secondary bg-surface-container rounded-lg border border-border-hairline border-dashed">
                                            📦 该商品属于单规格一口价商品（无多规格明细）。
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* 右侧决策面板: Span 4 布局 (AI ROI 引擎) */}
                    <div className="w-56 shrink-0 flex flex-col gap-3">
                        {/* 基础测算卡片 */}
                        <div className="bg-surface-container rounded-xl p-3 border border-border-hairline flex flex-col gap-2.5">
                            <span className="font-sans text-[10px] font-bold text-secondary tracking-wider uppercase">价格与纯利测算</span>
                            
                            <div className="flex justify-between items-baseline">
                                <span className="text-xs text-secondary">1688成本价</span>
                                <span className="font-mono text-sm font-bold text-on-surface">¥{item.source_price}</span>
                            </div>
                            
                            {item.ref_price > 0 && (
                                <div className="flex justify-between items-baseline border-t border-border-hairline/60 pt-2">
                                    <span className="text-xs text-secondary">爆款参考售价</span>
                                    <span className="font-mono text-sm font-bold text-on-surface">¥{item.ref_price}</span>
                                </div>
                            )}
                            {costPrice > 0 && (
                                <div className="flex justify-between items-baseline border-t border-border-hairline/60 pt-2">
                                    <span className="text-xs text-secondary">预期净利润额</span>
                                    <span className={`font-mono text-base font-black ${parseFloat(margin) > 50 ? 'text-success' : 'text-error'}`}>
                                        ¥{margin}
                                    </span>
                                </div>
                            )}
                            <div className="text-[10px] text-secondary pt-1">
                                ROI {roiPercentage}% · 毛利率配置 {Math.round(normalizedGrossProfitRate * 100)}%
                            </div>
                        </div>

                        {/* AI 决策建议 */}
                        <div className="bg-surface-container-low border border-border-hairline rounded-xl">
                            <button
                                type="button"
                                onClick={() => setShowAiSection(prev => !prev)}
                                className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-surface-container transition-colors rounded-xl"
                            >
                                <div>
                                    <span className="font-sans text-[10px] font-bold text-secondary tracking-wider uppercase block">AI 推荐诊断</span>
                                    <span className="text-xs text-on-surface font-semibold mt-1 block">{recommendationBadge} · ROI {roiPercentage}%</span>
                                </div>
                                <span className="material-symbols-outlined text-secondary text-[18px]" style={{ transform: showAiSection ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }}>
                                    expand_more
                                </span>
                            </button>
                            {showAiSection && (
                                <div className="px-3 pb-3">
                                    <div className="flex items-center gap-1.5 mb-2">
                                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border flex items-center gap-1 ${badgeColorClass}`}>
                                            <span className={`w-1.5 h-1.5 rounded-full ${pulseColorClass}`}></span>
                                            {recommendationBadge}
                                        </span>
                                    </div>
                                    <p className="text-xs leading-relaxed text-secondary bg-surface-container-lowest p-3 rounded-lg border border-border-hairline/50">
                                        {aiAdvice}
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
                
                <div className="px-6 py-4 border-t border-border-hairline bg-surface-container-low flex justify-between items-center">
                    <div className="text-[11px] text-secondary">
                        提示：可在右侧面板控制直接执行云端数据同步。
                    </div>
                    <div className="flex gap-3 items-center">
                        <PublishButton 
                            src={mockSrc} 
                            xianyuPrice={item.ref_price} 
                            onStatusLoaded={(dbId, status, result) => {
                                handleStatusLoaded(dbId, status, result);
                                if (status === 'idle') {
                                    handleClose();
                                } else {
                                    onUpdateItem({ ...item, publish_status: status, published_url: result?.published_url || item.published_url });
                                }
                            }}
                            batchStatus={batchStatusMap[item.source_db_id]}
                            batchResult={batchResultMap[item.source_db_id]}
                            initialStatus={item.publish_status}
                            initialResult={item.published_url ? { published_url: item.published_url } : null}
                            skipStatusFetch={true}
                        />
                        <button 
                            className="px-4 py-2 border border-border-hairline rounded-lg text-secondary hover:text-on-surface hover:bg-surface-container-high font-sans text-xs font-semibold transition-all" 
                            onClick={handleClose}
                        >
                            关闭档案
                        </button>
                    </div>
                </div>
            </div>
        </div>,
        document.body
    );
};

const OrderImageThumb = ({ order, sizeClass = "w-14 h-14" }) => {
    const image = order?.goods?.image;
    if (!image) {
        return (
            <div className={`${sizeClass} rounded-lg bg-surface-container border border-border-hairline flex items-center justify-center text-secondary shrink-0`}>
                <span className="material-symbols-outlined text-[18px]">image_not_supported</span>
            </div>
        );
    }
    return (
        <img
            src={image}
            referrerPolicy="no-referrer"
            loading="lazy"
            decoding="async"
            className={`${sizeClass} rounded-lg object-cover border border-border-hairline bg-surface-container shrink-0`}
        />
    );
};

// --- 订单详情页组件 ---
const OrderDetailPage = ({ orderNo, onBack }) => {
    const [orderDetail, setOrderDetail] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const fetchOrderDetail = async () => {
        if (!orderNo) {
            setError('缺少订单号，请返回订单列表重新选择。');
            return;
        }
        setLoading(true);
        setError('');
        try {
            const res = await fetch(`/api/orders/${encodeURIComponent(orderNo)}`).then(r => r.json());
            if (res.status === 'success') {
                setOrderDetail(res.order || null);
            } else {
                setError(res.msg || '订单详情查询失败');
            }
        } catch (err) {
            setError('订单详情连接失败，请检查后端服务。');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchOrderDetail();
    }, [orderNo]);

    return (
        <div className="view-content">
            <button
                onClick={onBack}
                className="mb-5 inline-flex items-center gap-1 text-secondary hover:text-primary text-xs font-bold transition-colors"
            >
                <span className="material-symbols-outlined text-[18px]">arrow_back</span>
                返回订单列表
            </button>

            {loading ? (
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-12 text-center text-secondary ambient-shadow">
                    <span className="material-symbols-outlined animate-spin text-primary align-middle mr-2">sync</span>
                    正在读取订单详情...
                </div>
            ) : error ? (
                <div className="bg-error/10 border border-error/30 text-error rounded-xl p-5 text-sm font-semibold">
                    {error}
                </div>
            ) : orderDetail ? (
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-5 ambient-shadow">
                    <div className="flex flex-wrap items-start justify-between gap-4 pb-5 border-b border-border-hairline">
                        <div className="space-y-3">
                            <div className="grid grid-cols-[56px_minmax(0,1fr)] items-center gap-3">
                                <div className="text-xs text-secondary">订单号</div>
                                <div className="font-mono text-lg font-black text-on-surface break-all">{orderDetail.order_no}</div>
                            </div>
                            <div className="grid grid-cols-[56px_minmax(0,1fr)] items-center gap-3">
                                <div className="text-xs text-secondary">状态</div>
                                <div className="text-xs font-bold text-primary">
                                    {orderDetail.order_status_label}
                                </div>
                            </div>
                        </div>
                        <button
                            onClick={fetchOrderDetail}
                            className="px-3 py-2 bg-surface-container-high hover:bg-primary/10 text-primary rounded-lg text-xs font-bold flex items-center gap-1 transition-colors"
                        >
                            <span className="material-symbols-outlined text-[16px]">sync</span>
                            刷新详情
                        </button>
                    </div>

                    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] gap-6 pt-5">
                        <section>
                            <div className="font-sans text-sm font-bold text-on-surface mb-4 flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary text-[18px]">inventory_2</span>
                                商品信息
                            </div>
                            <div className="flex gap-4">
                                <OrderImageThumb order={orderDetail} sizeClass="w-20 h-20" />
                                <div className="min-w-0">
                                    <div className="text-base font-bold text-on-surface leading-snug">{orderDetail.goods?.title || '未命名商品'}</div>
                                    <div className="text-xs text-secondary mt-2">{orderDetail.goods?.sku_text || '默认规格'}</div>
                                    <div className="text-xs text-secondary mt-1">数量 {orderDetail.goods?.quantity || 0} · 单价 {orderDetail.goods?.price_text}</div>
                                    <div className="text-xs text-secondary mt-1">商品 ID {orderDetail.goods?.item_id || '-'}</div>
                                </div>
                            </div>
                        </section>

                        <section>
                            <div className="font-sans text-sm font-bold text-on-surface mb-4 flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary text-[18px]">payments</span>
                                金额与时间
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                                <div className="flex justify-between items-baseline gap-3"><span className="text-secondary">实付金额</span><span className="font-mono text-lg font-black text-primary">{orderDetail.pay_amount_text}</span></div>
                                <div className="flex justify-between items-baseline gap-3"><span className="text-secondary">订单总额</span><span className="font-mono font-bold text-on-surface">{orderDetail.total_amount_text}</span></div>
                                <div className="flex justify-between items-baseline gap-3"><span className="text-secondary">运费</span><span className="font-mono font-bold text-on-surface">{orderDetail.express_fee_text}</span></div>
                                <div className="flex justify-between gap-3"><span className="text-secondary">下单时间</span><span className="text-on-surface font-semibold text-right">{orderDetail.order_time_text || '-'}</span></div>
                                <div className="flex justify-between gap-3"><span className="text-secondary">支付时间</span><span className="text-on-surface font-semibold text-right">{orderDetail.pay_time_text || '-'}</span></div>
                                <div className="flex justify-between gap-3"><span className="text-secondary">发货时间</span><span className="text-on-surface font-semibold text-right">{orderDetail.consign_time_text || '-'}</span></div>
                                <div className="flex justify-between gap-3"><span className="text-secondary">取消时间</span><span className="text-on-surface font-semibold text-right">{orderDetail.cancel_time_text || '-'}</span></div>
                            </div>
                        </section>
                    </div>

                    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 pt-5 mt-5 border-t border-border-hairline">
                        <section>
                            <div className="font-sans text-sm font-bold text-on-surface mb-4 flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary text-[18px]">location_on</span>
                                收货信息
                            </div>
                            <div className="space-y-3 text-sm">
                                <div>
                                    <div className="text-xs text-secondary mb-1">收货人</div>
                                    <div className="font-semibold text-on-surface">{orderDetail.receiver_name || '-'}</div>
                                </div>
                                <div>
                                    <div className="text-xs text-secondary mb-1">联系电话</div>
                                    <div className="font-semibold text-on-surface">{orderDetail.receiver_mobile || '-'}</div>
                                </div>
                                <div>
                                    <div className="text-xs text-secondary mb-1">收货地址</div>
                                    <div className="font-semibold text-on-surface leading-relaxed">{orderDetail.receiver_address || '-'}</div>
                                </div>
                            </div>
                        </section>

                        <section>
                            <div className="font-sans text-sm font-bold text-on-surface mb-4 flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary text-[18px]">local_shipping</span>
                                物流信息
                            </div>
                            <div className="space-y-3 text-sm">
                                <div>
                                    <div className="text-xs text-secondary mb-1">物流公司</div>
                                    <div className="font-semibold text-on-surface">{orderDetail.express_name || orderDetail.express_code || '暂无物流公司'}</div>
                                </div>
                                <div>
                                    <div className="text-xs text-secondary mb-1">运单号</div>
                                    <div className="font-mono font-semibold text-on-surface">{orderDetail.waybill_no || '暂无运单号'}</div>
                                </div>
                            </div>
                        </section>

                        <section>
                            <div className="font-sans text-sm font-bold text-on-surface mb-4 flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary text-[18px]">person</span>
                                交易对象
                            </div>
                            <div className="space-y-3 text-sm">
                                <div>
                                    <div className="text-xs text-secondary mb-1">买家昵称</div>
                                    <div className="font-semibold text-on-surface">{orderDetail.buyer_nick || '-'}</div>
                                </div>
                                <div>
                                    <div className="text-xs text-secondary mb-1">卖家账号</div>
                                    <div className="font-semibold text-on-surface">{orderDetail.seller_name || '-'}</div>
                                </div>
                                {orderDetail.seller_remark && (
                                    <div>
                                        <div className="text-xs text-secondary mb-1">卖家备注</div>
                                        <div className="text-secondary leading-relaxed">{orderDetail.seller_remark}</div>
                                    </div>
                                )}
                            </div>
                        </section>
                    </div>
                </div>
            ) : (
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-12 text-center text-secondary ambient-shadow">
                    暂无订单详情
                </div>
            )}
        </div>
    );
};

const OrderOperationModal = ({ type, order, onClose, onSuccess }) => {
    const [active, setActive] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');
    const [shipForm, setShipForm] = useState({
        waybill_no: '',
        express_code: '',
        express_name: '',
        ship_name: '',
        ship_mobile: '',
        ship_district_id: '',
        ship_prov_name: '',
        ship_city_name: '',
        ship_area_name: '',
        ship_address: '',
    });
    const [priceForm, setPriceForm] = useState({
        order_price_yuan: formatCentValueForInput(order?.total_amount),
        express_fee_yuan: formatCentValueForInput(order?.express_fee),
    });

    useEffect(() => {
        let frameId = requestAnimationFrame(() => {
            frameId = requestAnimationFrame(() => setActive(true));
        });
        document.body.style.overflow = 'hidden';
        return () => {
            cancelAnimationFrame(frameId);
            document.body.style.overflow = '';
        };
    }, []);

    const close = () => {
        if (submitting) return;
        setActive(false);
        setTimeout(onClose, 220);
    };

    const updateShipForm = (key, value) => {
        setShipForm(prev => ({ ...prev, [key]: value }));
    };

    const updatePriceForm = (key, value) => {
        setPriceForm(prev => ({ ...prev, [key]: value }));
    };

    const submit = async () => {
        setError('');
        if (!order?.order_no) {
            setError('缺少订单号，请返回列表重新选择订单。');
            return;
        }

        let endpoint = '';
        let body = {};
        if (type === 'ship') {
            if (!shipForm.waybill_no.trim() || !shipForm.express_code.trim() || !shipForm.express_name.trim()) {
                setError('请填写快递单号、快递公司代码和快递公司名称。');
                return;
            }
            endpoint = `/api/orders/${encodeURIComponent(order.order_no)}/ship`;
            body = shipForm;
        } else {
            const orderPrice = Number(priceForm.order_price_yuan);
            const expressFee = Number(priceForm.express_fee_yuan || 0);
            if (!Number.isFinite(orderPrice) || orderPrice <= 0) {
                setError('订单价格必须大于 0。');
                return;
            }
            if (!Number.isFinite(expressFee) || expressFee < 0) {
                setError('运费不能小于 0。');
                return;
            }
            endpoint = `/api/orders/${encodeURIComponent(order.order_no)}/modify_price`;
            body = priceForm;
        }

        setSubmitting(true);
        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            }).then(r => r.json());
            if (res.status !== 'success') {
                setError(res.msg || '操作失败');
                return;
            }
            setActive(false);
            setTimeout(() => onSuccess(res.msg || '操作成功'), 220);
        } catch (err) {
            setError('连接失败，请检查后端服务。');
        } finally {
            setSubmitting(false);
        }
    };

    const isShip = type === 'ship';
    const title = isShip ? '订单物流发货' : '订单修改价格';
    const icon = isShip ? 'local_shipping' : 'payments';

    return ReactDOM.createPortal(
        <div className={`preview-modal-overlay ${active ? 'active' : ''}`} onClick={close}>
            <div
                className={`preview-modal-wrapper ${active ? 'active' : ''}`}
                style={{ width: '640px' }}
                onClick={e => e.stopPropagation()}
            >
                <div className="px-6 py-4 border-b border-border-hairline flex justify-between items-center bg-surface-container-low">
                    <h3 className="font-sans text-base font-bold text-on-surface flex items-center gap-2">
                        <span className="material-symbols-outlined text-primary">{icon}</span>
                        {title}
                    </h3>
                    <button onClick={close} className="w-8 h-8 rounded-full hover:bg-surface-container-high flex items-center justify-center text-secondary hover:text-on-surface transition-all">
                        <span className="material-symbols-outlined text-[20px]">close</span>
                    </button>
                </div>

                <div className="p-6 space-y-4">
                    <div className="rounded-xl border border-border-hairline bg-surface-container-low px-4 py-3 text-xs text-secondary">
                        <div className="font-mono font-bold text-on-surface break-all">订单号：{order?.order_no || '-'}</div>
                        <div className="mt-1">{isShip ? '寄件方信息不填时，将使用闲管家后台默认发货地址。' : '金额单位为元，提交时会按 OpenAPI 要求转换为分。'}</div>
                    </div>

                    {error && (
                        <div className="rounded-lg border border-error/30 bg-error/10 text-error px-4 py-3 text-xs font-semibold">
                            {error}
                        </div>
                    )}

                    {isShip ? (
                        <div className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                <label className="block">
                                    <span className="block text-xs text-secondary mb-1">快递单号</span>
                                    <input value={shipForm.waybill_no} onChange={e => updateShipForm('waybill_no', e.target.value)} className="w-full px-3 py-2 rounded-lg border border-border-hairline bg-surface-container-lowest text-sm focus:outline-none focus:border-primary" />
                                </label>
                                <label className="block">
                                    <span className="block text-xs text-secondary mb-1">快递公司代码</span>
                                    <input value={shipForm.express_code} onChange={e => updateShipForm('express_code', e.target.value)} placeholder="如 shunfeng / qita" className="w-full px-3 py-2 rounded-lg border border-border-hairline bg-surface-container-lowest text-sm focus:outline-none focus:border-primary" />
                                </label>
                                <label className="block">
                                    <span className="block text-xs text-secondary mb-1">快递公司名称</span>
                                    <input value={shipForm.express_name} onChange={e => updateShipForm('express_name', e.target.value)} placeholder="如 顺丰速运" className="w-full px-3 py-2 rounded-lg border border-border-hairline bg-surface-container-lowest text-sm focus:outline-none focus:border-primary" />
                                </label>
                            </div>
                            <div className="border-t border-border-hairline pt-4">
                                <div className="text-xs font-bold text-on-surface mb-3">寄件方信息（可选）</div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <input value={shipForm.ship_name} onChange={e => updateShipForm('ship_name', e.target.value)} placeholder="寄件人姓名" className="px-3 py-2 rounded-lg border border-border-hairline bg-surface-container-lowest text-sm focus:outline-none focus:border-primary" />
                                    <input value={shipForm.ship_mobile} onChange={e => updateShipForm('ship_mobile', e.target.value)} placeholder="寄件人手机号" className="px-3 py-2 rounded-lg border border-border-hairline bg-surface-container-lowest text-sm focus:outline-none focus:border-primary" />
                                    <input value={shipForm.ship_district_id} onChange={e => updateShipForm('ship_district_id', e.target.value)} placeholder="地区 ID（有则优先）" className="px-3 py-2 rounded-lg border border-border-hairline bg-surface-container-lowest text-sm focus:outline-none focus:border-primary" />
                                    <input value={shipForm.ship_prov_name} onChange={e => updateShipForm('ship_prov_name', e.target.value)} placeholder="省份" className="px-3 py-2 rounded-lg border border-border-hairline bg-surface-container-lowest text-sm focus:outline-none focus:border-primary" />
                                    <input value={shipForm.ship_city_name} onChange={e => updateShipForm('ship_city_name', e.target.value)} placeholder="城市" className="px-3 py-2 rounded-lg border border-border-hairline bg-surface-container-lowest text-sm focus:outline-none focus:border-primary" />
                                    <input value={shipForm.ship_area_name} onChange={e => updateShipForm('ship_area_name', e.target.value)} placeholder="区县" className="px-3 py-2 rounded-lg border border-border-hairline bg-surface-container-lowest text-sm focus:outline-none focus:border-primary" />
                                    <input value={shipForm.ship_address} onChange={e => updateShipForm('ship_address', e.target.value)} placeholder="详细地址" className="md:col-span-2 px-3 py-2 rounded-lg border border-border-hairline bg-surface-container-lowest text-sm focus:outline-none focus:border-primary" />
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <label className="block">
                                <span className="block text-xs text-secondary mb-1">订单价格（元）</span>
                                <input type="number" min="0.01" step="0.01" value={priceForm.order_price_yuan} onChange={e => updatePriceForm('order_price_yuan', e.target.value)} className="w-full px-3 py-2 rounded-lg border border-border-hairline bg-surface-container-lowest text-sm focus:outline-none focus:border-primary" />
                            </label>
                            <label className="block">
                                <span className="block text-xs text-secondary mb-1">运费（元）</span>
                                <input type="number" min="0" step="0.01" value={priceForm.express_fee_yuan} onChange={e => updatePriceForm('express_fee_yuan', e.target.value)} className="w-full px-3 py-2 rounded-lg border border-border-hairline bg-surface-container-lowest text-sm focus:outline-none focus:border-primary" />
                            </label>
                        </div>
                    )}
                </div>

                <div className="px-6 py-4 border-t border-border-hairline flex gap-3 justify-end bg-surface-container-low">
                    <button onClick={close} disabled={submitting} className="px-4 py-2 border border-border-hairline rounded-lg text-secondary font-sans text-xs font-semibold hover:bg-surface-container-high hover:text-on-surface transition-colors disabled:opacity-50">
                        取消
                    </button>
                    <button onClick={submit} disabled={submitting} className="px-4 py-2 bg-primary hover:bg-primary-container text-white font-sans text-xs font-semibold rounded-lg shadow-sm disabled:opacity-50 transition-colors">
                        {submitting ? '提交中...' : (isShip ? '确认发货' : '确认改价')}
                    </button>
                </div>
            </div>
        </div>,
        document.body
    );
};

// --- 订单管理组件 ---
const OrderManager = ({ hideHeader = false, onOpenDetail }) => {
    const [orders, setOrders] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [orderStatus, setOrderStatus] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [selectedOrderNo, setSelectedOrderNo] = useState('');
    const [operationType, setOperationType] = useState('');
    const [operationNotice, setOperationNotice] = useState('');

    const totalPages = Math.max(1, Math.ceil(total / ORDER_PAGE_SIZE));
    const selectedOrder = orders.find(order => order.order_no === selectedOrderNo);
    const canShipSelectedOrder = Number(selectedOrder?.order_status) === 12;
    const canModifyPriceSelectedOrder = Number(selectedOrder?.order_status) === 11;

    const fetchOrders = async () => {
        setLoading(true);
        setError('');
        setSelectedOrderNo('');
        try {
            const url = `/api/orders?page=${page}&limit=${ORDER_PAGE_SIZE}&order_status=${encodeURIComponent(orderStatus)}`;
            const res = await fetch(url).then(r => r.json());
            if (res.status !== 'success') {
                setOrders([]);
                setTotal(0);
                setError(res.msg || '订单列表查询失败');
                return;
            }
            setOrders(res.items || []);
            setTotal(res.total || 0);
        } catch (err) {
            setOrders([]);
            setTotal(0);
            setError('订单列表连接失败，请检查后端服务。');
        } finally {
            setLoading(false);
        }
    };

    const selectOrder = (orderNo) => {
        setSelectedOrderNo(orderNo);
    };

    const toggleOrder = (orderNo, checked) => {
        if (checked) {
            setSelectedOrderNo(orderNo);
        } else if (selectedOrderNo === orderNo) {
            setSelectedOrderNo('');
        }
    };

    const openOrderOperation = (type) => {
        setOperationNotice('');
        if (!selectedOrder) {
            setError('请先选择订单。');
            return;
        }
        if (type === 'ship' && !canShipSelectedOrder) {
            setError('只有待发货订单才能物流发货。');
            return;
        }
        if (type === 'price' && !canModifyPriceSelectedOrder) {
            setError('只有待付款订单才能修改价格。');
            return;
        }
        setOperationType(type);
    };

    const handleOrderOperationSuccess = (message) => {
        setOperationType('');
        setOperationNotice(message || '操作成功');
        fetchOrders();
    };

    useEffect(() => {
        fetchOrders();
    }, [page, orderStatus]);

    const changeOrderStatus = (value) => {
        setPage(1);
        setOrderStatus(value);
    };

    return (
        <div className="view-content">
            {!hideHeader && (
                <header className="mb-6">
                    <h1 className="font-sans text-2xl font-bold text-on-surface">订单管理</h1>
                    <p className="font-sans text-sm text-secondary mt-1">通过闲管家 OpenAPI 查询订单列表与订单详情。</p>
                </header>
            )}

            <div className="bg-surface-container-lowest border border-border-hairline rounded-xl ambient-shadow overflow-hidden">
                <div className="px-5 py-4 border-b border-border-hairline flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <div className="font-sans text-sm font-bold text-on-surface flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary text-[18px]">receipt_long</span>
                            闲管家订单列表
                            <span className="text-secondary font-semibold">({total} 条)</span>
                        </div>
                        <div className="text-xs text-secondary mt-1">列表按闲管家 OpenAPI 返回结果展示，订单详情按订单号实时查询。</div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <select
                            value={orderStatus}
                            onChange={(e) => changeOrderStatus(e.target.value)}
                            className="bg-surface-container-low border border-border-hairline rounded-lg px-3 py-2 text-xs text-on-surface focus:outline-none focus:border-primary"
                        >
                            <option value="">全部状态</option>
                            {OPENAPI_ORDER_STATUS_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                        </select>
                        <button
                            onClick={fetchOrders}
                            className="px-3 py-2 bg-primary hover:bg-primary-container text-white rounded-lg text-xs font-bold flex items-center gap-1 transition-colors"
                        >
                            <span className={`material-symbols-outlined text-[16px] ${loading ? 'animate-spin' : ''}`}>sync</span>
                            刷新订单
                        </button>
                        <button
                            disabled={!selectedOrderNo}
                            onClick={() => onOpenDetail && onOpenDetail(selectedOrderNo)}
                            className="px-3 py-2 bg-surface-container-high hover:bg-primary/10 text-primary rounded-lg text-xs font-bold flex items-center gap-1 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                            <span className="material-symbols-outlined text-[16px]">open_in_new</span>
                            查看订单详情
                        </button>
                        <button
                            disabled={!canShipSelectedOrder}
                            title={selectedOrderNo && !canShipSelectedOrder ? '只有待发货订单才能物流发货' : ''}
                            onClick={() => openOrderOperation('ship')}
                            className="px-3 py-2 bg-surface-container-high hover:bg-primary/10 text-primary rounded-lg text-xs font-bold flex items-center gap-1 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                            <span className="material-symbols-outlined text-[16px]">local_shipping</span>
                            物流发货
                        </button>
                        <button
                            disabled={!canModifyPriceSelectedOrder}
                            title={selectedOrderNo && !canModifyPriceSelectedOrder ? '只有待付款订单才能修改价格' : ''}
                            onClick={() => openOrderOperation('price')}
                            className="px-3 py-2 bg-surface-container-high hover:bg-primary/10 text-primary rounded-lg text-xs font-bold flex items-center gap-1 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                            <span className="material-symbols-outlined text-[16px]">payments</span>
                            修改价格
                        </button>
                    </div>
                </div>

                {error && (
                    <div className="mx-5 mt-4 rounded-lg border border-error/30 bg-error/10 text-error px-4 py-3 text-xs font-semibold">
                        {error}
                    </div>
                )}
                {operationNotice && (
                    <div className="mx-5 mt-4 rounded-lg border border-primary/30 bg-primary/10 text-primary px-4 py-3 text-xs font-semibold">
                        {operationNotice}
                    </div>
                )}

                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="bg-table-header-bg border-b border-border-hairline">
                                <th className="p-cell-padding font-sans text-xs font-bold text-secondary w-12"></th>
                                <th className="p-cell-padding font-sans text-xs font-bold text-secondary">商品</th>
                                <th className="p-cell-padding font-sans text-xs font-bold text-secondary">订单</th>
                                <th className="p-cell-padding font-sans text-xs font-bold text-secondary">订单状态</th>
                                <th className="p-cell-padding font-sans text-xs font-bold text-secondary">订单时间</th>
                                <th className="p-cell-padding font-sans text-xs font-bold text-secondary">数量</th>
                                <th className="p-cell-padding font-sans text-xs font-bold text-secondary">金额</th>
                                <th className="p-cell-padding font-sans text-xs font-bold text-secondary">总金额</th>
                                <th className="p-cell-padding font-sans text-xs font-bold text-secondary">买家/收货</th>
                                <th className="p-cell-padding font-sans text-xs font-bold text-secondary">物流</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border-hairline">
                            {loading ? (
                                <tr>
                                    <td colSpan="10" className="py-12 text-center text-secondary text-sm">
                                        <span className="material-symbols-outlined animate-spin text-primary align-middle mr-2">sync</span>
                                        正在读取订单...
                                    </td>
                                </tr>
                            ) : orders.length === 0 ? (
                                <tr>
                                    <td colSpan="10" className="py-12 text-center text-secondary text-sm">暂无订单数据</td>
                                </tr>
                            ) : orders.map(order => {
                                const isSelected = selectedOrderNo === order.order_no;
                                return (
                                    <tr
                                        key={order.order_no}
                                        className={`transition-colors cursor-pointer ${isSelected ? 'bg-primary/5' : 'hover:bg-surface-container-low'}`}
                                        onClick={() => selectOrder(order.order_no)}
                                    >
                                        <td className="p-cell-padding">
                                            <input
                                                type="checkbox"
                                                checked={isSelected}
                                                onClick={(e) => e.stopPropagation()}
                                                onChange={(e) => toggleOrder(order.order_no, e.target.checked)}
                                                className="w-4 h-4 accent-primary cursor-pointer"
                                                aria-label={`选择订单 ${order.order_no}`}
                                            />
                                        </td>
                                        <td className="p-cell-padding min-w-[300px]">
                                            <div className="flex items-start gap-3">
                                                <OrderImageThumb order={order} />
                                                <div className="min-w-0">
                                                    <div className="font-sans text-sm font-bold text-on-surface line-clamp-2">{order.goods?.title || '未命名商品'}</div>
                                                    <div className="text-xs text-secondary mt-1 line-clamp-1">{order.goods?.sku_text || '默认规格'}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="p-cell-padding">
                                            <div className="font-mono text-xs font-bold text-on-surface">{order.order_no}</div>
                                        </td>
                                        <td className="p-cell-padding">
                                            <div className="inline-flex items-center px-2 py-0.5 rounded-full bg-surface-container border border-border-hairline text-[10px] text-secondary font-bold">
                                                {order.order_status_label}
                                            </div>
                                        </td>
                                        <td className="p-cell-padding min-w-[150px]">
                                            <div className="text-[11px] text-secondary">{order.order_time_text || '无下单时间'}</div>
                                        </td>
                                        <td className="p-cell-padding">
                                            <div className="font-mono text-xs font-bold text-on-surface">{order.goods?.quantity || 0}</div>
                                        </td>
                                        <td className="p-cell-padding">
                                            <div className="font-mono text-sm font-bold text-primary">{order.pay_amount_text}</div>
                                        </td>
                                        <td className="p-cell-padding">
                                            <div className="font-mono text-sm font-bold text-on-surface">{order.total_amount_text}</div>
                                        </td>
                                        <td className="p-cell-padding min-w-[220px]">
                                            <div className="text-xs font-bold text-on-surface">{order.buyer_nick || '未知买家'}</div>
                                            <div className="text-[11px] text-secondary mt-1 line-clamp-2">{order.receiver_name} {order.receiver_mobile} {order.receiver_address}</div>
                                        </td>
                                        <td className="p-cell-padding">
                                            <div className="text-xs font-bold text-on-surface">{order.express_name || order.express_code || '未发货/无物流'}</div>
                                            <div className="text-[11px] text-secondary mt-1">{order.waybill_no || '暂无运单号'}</div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>

                <div className="px-5 py-4 border-t border-border-hairline flex items-center justify-between">
                    <div className="text-xs text-secondary">
                        第 {page} / {totalPages} 页
                    </div>
                    <div className="flex gap-2">
                        <button
                            disabled={page <= 1 || loading}
                            onClick={() => setPage(prev => Math.max(1, prev - 1))}
                            className="px-3 py-1.5 rounded-lg border border-border-hairline text-xs text-secondary disabled:opacity-40 hover:bg-surface-container-high"
                        >
                            上一页
                        </button>
                        <button
                            disabled={page >= totalPages || loading}
                            onClick={() => setPage(prev => Math.min(totalPages, prev + 1))}
                            className="px-3 py-1.5 rounded-lg border border-border-hairline text-xs text-secondary disabled:opacity-40 hover:bg-surface-container-high"
                        >
                            下一页
                        </button>
                    </div>
                </div>
            </div>
            {operationType && (
                <OrderOperationModal
                    type={operationType}
                    order={selectedOrder}
                    onClose={() => setOperationType('')}
                    onSuccess={handleOrderOperationSuccess}
                />
            )}
        </div>
    );
};

// --- 选品管理组件 ---
const PublishedManager = ({ hideHeader = false }) => {
    const [items, setItems] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [limit] = useState(10);
    const [keyword, setKeyword] = useState('');
    const [filterStatus, setFilterStatus] = useState('');
    const [minSourcePrice, setMinSourcePrice] = useState('');
    const [maxSourcePrice, setMaxSourcePrice] = useState('');
    const [minRefPrice, setMinRefPrice] = useState('');
    const [maxRefPrice, setMaxRefPrice] = useState('');
    const [isExpanded, setIsExpanded] = useState(false); // 控制高级筛选展开折叠
    const [loading, setLoading] = useState(false);
    const [refreshTrigger, setRefreshTrigger] = useState(0);
    const [selectedProduct, setSelectedProduct] = useState(null); // 记录当前查看详情的选品商品
    const [sortBy, setSortBy] = useState('publish_time');
    const [sortOrder, setSortOrder] = useState('desc');
    const [selectedIds, setSelectedIds] = useState([]);
    const [batchPublishing, setBatchPublishing] = useState(false);
    const [batchDepublishing, setBatchDepublishing] = useState(false);
    const [batchDeleting, setBatchDeleting] = useState(false);
    const [batchSyncingStatus, setBatchSyncingStatus] = useState(false);
    const [syncStatusNotice, setSyncStatusNotice] = useState("");
    const [confirmDialog, setConfirmDialog] = useState(null);
    const [grossProfitRate, setGrossProfitRate] = useState(DEFAULT_GROSS_PROFIT_RATE);

    // 用于收集每个商品的实时状态映射
    const [batchStatusMap, setBatchStatusMap] = useState({});
    const [batchResultMap, setBatchResultMap] = useState({});

    const normalizePublishedStatus = (rawStatus) => {
        if (rawStatus === 'selected') return 'selected';
        if (rawStatus === 'success' || rawStatus === 'done') return 'done';
        if (rawStatus === 'depublished') return 'depublished';
        if (rawStatus === 'failed') return 'failed';
        if (rawStatus === 'pending' || rawStatus === 'publishing' || rawStatus === 'depublishing' || rawStatus === 'syncing') return 'publishing';
        if (rawStatus === 'deleting') return 'deleting';
        if (rawStatus === 'deleted' || rawStatus === 'none' || rawStatus === 'idle' || !rawStatus) return 'idle';
        return 'idle';
    };

    const formatPublishedSourcePrice = (item) => {
        const suffix = Number(item?.source_sku_count || 0) > 1 ? '起' : '';
        return `¥${item?.source_price}${suffix}`;
    };

    const getPublishedItemStatus = (item) => normalizePublishedStatus(batchStatusMap[item.source_db_id] || item.publish_status);
    const selectedItems = items.filter(item => selectedIds.includes(item.source_db_id));
    const publishableIds = selectedItems
        .filter(item => ['selected', 'idle', 'failed', 'depublished'].includes(getPublishedItemStatus(item)))
        .map(item => item.source_db_id);
    const depublishableIds = selectedItems
        .filter(item => getPublishedItemStatus(item) === 'done')
        .map(item => item.source_db_id);
    const deletableIds = selectedItems
        .filter(item => ['selected', 'depublished', 'failed'].includes(getPublishedItemStatus(item)))
        .map(item => item.source_db_id);
    const syncableIds = selectedItems
        .filter(item => item.xianyu_item_id && !['selected', 'idle'].includes(getPublishedItemStatus(item)))
        .map(item => item.source_db_id);

    const fetchPublishedProducts = async () => {
        setLoading(true);
        try {
            let url = `/api/xianyu_products?page=${page}&limit=${limit}&keyword=${encodeURIComponent(keyword)}&sort_by=${sortBy}&sort_order=${sortOrder}`;
            if (filterStatus) url += `&publish_status=${filterStatus}`;
            if (minSourcePrice) url += `&min_source_price=${minSourcePrice}`;
            if (maxSourcePrice) url += `&max_source_price=${maxSourcePrice}`;
            if (minRefPrice) url += `&min_ref_price=${minRefPrice}`;
            if (maxRefPrice) url += `&max_ref_price=${maxRefPrice}`;

            const res = await fetch(url).then(r => r.json());
            setItems(res.items || []);
            setTotal(res.total || 0);
        } catch (e) {
            console.error("加载选品商品失败:", e);
        } finally {
            setLoading(false);
        }
    };

    const fetchProfitConfig = async () => {
        try {
            const res = await fetch('/api/system/configs').then(r => r.json());
            if (res.status === 'success') {
                setGrossProfitRate(normalizeGrossProfitRate(res.data?.crawl?.gross_profit_rate));
            }
        } catch (e) {
            console.error("加载毛利率配置失败:", e);
        }
    };

    useEffect(() => {
        fetchPublishedProducts();
    }, [page, keyword, filterStatus, minSourcePrice, maxSourcePrice, minRefPrice, maxRefPrice, sortBy, sortOrder, refreshTrigger]);

    useEffect(() => {
        fetchProfitConfig();
    }, []);

    useEffect(() => {
        const visibleIds = new Set(items.map(item => item.source_db_id));
        setSelectedIds(prev => prev.filter(id => visibleIds.has(id)));
    }, [items]);

    const handleStatusLoaded = (dbId, status, result) => {
        setBatchStatusMap(prev => {
            // 如果已被删除，我们需要更新列表
            if (status === 'idle' && prev[dbId] === 'deleting') {
                setTimeout(() => {
                    setRefreshTrigger(t => t + 1);
                }, 1000);
            }
            if (prev[dbId] === status) return prev;
            return { ...prev, [dbId]: status };
        });
        if (result) {
            setBatchResultMap(prev => {
                if (prev[dbId]) return prev;
                return { ...prev, [dbId]: result };
            });
        }
        if (status === 'idle') {
            setSelectedIds(prev => prev.filter(id => id !== dbId));
        }
    };

    const doBatchPublish = async () => {
        if (selectedIds.length === 0) {
            alert("请先选择要批量发布的商品");
            return;
        }
        const toPublishIds = [...publishableIds];
        if (toPublishIds.length === 0) {
            alert("当前勾选商品里，没有可执行批量发布的商品。");
            return;
        }

        setBatchPublishing(true);
        toPublishIds.forEach(dbId => {
            setBatchStatusMap(prev => ({ ...prev, [dbId]: 'publishing' }));
        });

        try {
            const resBatch = await fetch('/api/publish/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_ids: toPublishIds })
            }).then(r => r.json());

            if (resBatch.success) {
                resBatch.success.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'done' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'success', xianyu_item_id: item.product_id, published_url: item.published_url } }));
                });
            }
            if (resBatch.failed) {
                resBatch.failed.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: item.msg } }));
                });
            }
            if (resBatch.error) {
                toPublishIds.forEach(dbId => {
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: resBatch.error } }));
                });
            }
        } catch (e) {
            console.error("批量发布失败:", e);
            toPublishIds.forEach(dbId => {
                setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: '网络或连接出错' } }));
            });
        } finally {
            setBatchPublishing(false);
        }
    };

    const doBatchSyncStatus = async () => {
        if (selectedIds.length === 0) {
            alert("请先选择要同步状态的选品");
            return;
        }
        const toSyncIds = [...syncableIds];
        if (toSyncIds.length === 0) {
            alert("当前勾选选品里，没有可同步的已发布商品。");
            return;
        }
        const previousStatusById = {};
        selectedItems.forEach(item => {
            previousStatusById[item.source_db_id] = batchStatusMap[item.source_db_id] || item.publish_status || 'idle';
        });

        setBatchSyncingStatus(true);
        setSyncStatusNotice("");
        toSyncIds.forEach(dbId => {
            setBatchStatusMap(prev => ({ ...prev, [dbId]: 'syncing' }));
        });

        try {
            const resBatch = await fetch('/api/selection/sync_status/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_ids: toSyncIds })
            }).then(r => r.json());

            if (resBatch.success) {
                resBatch.success.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: item.publish_status || item.status }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: item.publish_status || item.status, msg: item.msg, published_url: item.published_url } }));
                });
            }
            if (resBatch.failed) {
                resBatch.failed.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: previousStatusById[dbId] || 'idle' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: item.msg } }));
                });
            }
            const successCount = (resBatch.success || []).length;
            const failedItems = resBatch.failed || [];
            if (failedItems.length > 0) {
                const firstMsg = failedItems[0]?.msg || '未知错误';
                setSyncStatusNotice(`同步选品状态：成功 ${successCount} 项，失败 ${failedItems.length} 项。失败原因：${firstMsg}`);
            } else {
                setSyncStatusNotice(`同步选品状态：成功 ${successCount} 项`);
            }
        } catch (e) {
            console.error("同步选品状态失败:", e);
            toSyncIds.forEach(dbId => {
                setBatchStatusMap(prev => ({ ...prev, [dbId]: previousStatusById[dbId] || 'idle' }));
                setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: '网络或连接出错' } }));
            });
            setSyncStatusNotice("同步选品状态失败：网络或连接出错");
        } finally {
            setBatchSyncingStatus(false);
            setRefreshTrigger(t => t + 1);
        }
    };

    const executeBatchDepublish = async (toDepublishIds) => {
        setBatchDepublishing(true);
        toDepublishIds.forEach(dbId => {
            setBatchStatusMap(prev => ({ ...prev, [dbId]: 'depublishing' }));
        });

        try {
            const resBatch = await fetch('/api/depublish/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_ids: toDepublishIds })
            }).then(r => r.json());

            if (resBatch.success) {
                resBatch.success.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'depublished' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'depublished', msg: '已下架' } }));
                });
            }
            if (resBatch.failed) {
                resBatch.failed.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: item.msg } }));
                });
            }
        } catch (e) {
            console.error("批量下架失败:", e);
            toDepublishIds.forEach(dbId => {
                setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: '网络或连接出错' } }));
            });
        } finally {
            setBatchDepublishing(false);
        }
    };

    const doBatchDepublish = async () => {
        if (selectedIds.length === 0) {
            alert("请先选择要批量下架的商品");
            return;
        }
        const toDepublishIds = [...depublishableIds];
        if (toDepublishIds.length === 0) {
            alert("当前勾选商品里，没有处于已上架状态的商品。");
            return;
        }
        setConfirmDialog({
            title: '确认批量下架',
            description: [
                `即将批量下架 ${toDepublishIds.length} 个已上架商品。`,
                '下架后商品会从闲鱼云端撤下，但本地发布记录会保留，方便后续重新上架。'
            ],
            confirmLabel: `确认下架 ${toDepublishIds.length} 项`,
            tone: 'warning',
            onConfirm: () => executeBatchDepublish(toDepublishIds)
        });
    };

    const executeBatchDelete = async (toDeleteIds) => {
        setBatchDeleting(true);
        toDeleteIds.forEach(dbId => {
            setBatchStatusMap(prev => ({ ...prev, [dbId]: 'deleting' }));
        });

        try {
            const resBatch = await fetch('/api/delete/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_ids: toDeleteIds })
            }).then(r => r.json());

            if (resBatch.success) {
                resBatch.success.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'idle' }));
                    setBatchResultMap(prev => {
                        const copy = { ...prev };
                        delete copy[dbId];
                        return copy;
                    });
                });
                setSelectedIds(prev => prev.filter(id => !toDeleteIds.includes(id)));
                setRefreshTrigger(t => t + 1);
            }
            if (resBatch.failed) {
                resBatch.failed.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: item.msg } }));
                });
            }
        } catch (e) {
            console.error("批量删除失败:", e);
            toDeleteIds.forEach(dbId => {
                setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: '网络或连接出错' } }));
            });
        } finally {
            setBatchDeleting(false);
        }
    };

    const doBatchDelete = async () => {
        if (selectedIds.length === 0) {
            alert("请先选择要批量删除的商品");
            return;
        }
        const toDeleteIds = [...deletableIds];
        if (toDeleteIds.length === 0) {
            alert("当前勾选商品里，没有可删除的已下架或同步失败商品。");
            return;
        }
        setConfirmDialog({
            title: '确认批量删除',
            description: [
                `即将批量删除 ${toDeleteIds.length} 个商品记录。`,
                '已选品和同步失败商品只会清理本地记录；已下架商品会执行云端删除。此操作不可恢复。'
            ],
            confirmLabel: `确认删除 ${toDeleteIds.length} 项`,
            tone: 'danger',
            onConfirm: () => executeBatchDelete(toDeleteIds)
        });
    };

    const handleSort = (field) => {
        if (sortBy === field) {
            setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
        } else {
            setSortBy(field);
            setSortOrder('asc'); // 默认正序
        }
        setPage(1); // 排序后回到第一页
    };

    const renderSortHeader = (label, field, extraClasses = "") => {
        const isCurrent = sortBy === field;
        let icon = <span className="material-symbols-outlined text-[16px] text-secondary/40 ml-1">swap_vert</span>;
        if (isCurrent) {
            icon = sortOrder === 'asc' 
                ? <span className="material-symbols-outlined text-[16px] text-primary ml-1">arrow_upward</span>
                : <span className="material-symbols-outlined text-[16px] text-primary ml-1">arrow_downward</span>;
        }
        return (
            <th 
                onClick={() => handleSort(field)} 
                className={`p-cell-padding font-sans text-xs font-semibold text-secondary uppercase tracking-wider cursor-pointer user-select-none hover:bg-surface-container-high transition-colors ${extraClasses}`}
                title="点击切换升序/降序"
            >
                <div className="flex items-center justify-start">
                    {label} {icon}
                </div>
            </th>
        );
    };

    const totalPages = Math.ceil(total / limit);

    return (
        <div className="view-content">
            {!hideHeader && (
                <header className="mb-6">
                    <h1 className="font-sans text-2xl font-bold text-on-surface flex items-center gap-2">
                        <span className="material-symbols-outlined text-primary text-[28px]">shopping_bag</span>
                        选品管理
                    </h1>
                    <p className="font-sans text-sm text-secondary mt-1">管理从决策资产库加入的候选货源，支持后续上架、下架与删除处理。</p>
                </header>
            )}

            {/* 多维筛选功能区 */}
            <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-4 mb-6 ambient-shadow space-y-4">
                {/* 第一排：主搜索框与高级筛选控制按钮 */}
                <div className="flex gap-3">
                    <div className="relative flex-1">
                        <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-secondary text-[20px]">search</span>
                        <input 
                            className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-sm rounded-lg pl-10 pr-4 py-2 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all placeholder-secondary/50"
                            value={keyword}
                            onChange={e => { setKeyword(e.target.value); setPage(1); }}
                            placeholder="输入货源标题、参考爆款标题或者商品 ID 进行搜索..."
                        />
                    </div>
                    {/* 高级筛选控制 */}
                    <button 
                        onClick={() => setIsExpanded(!isExpanded)}
                        className={`px-4 py-2 rounded-lg font-sans text-sm font-semibold transition-all flex items-center gap-1.5 border border-border-hairline hover:bg-surface-container-high ${isExpanded ? 'bg-primary/10 text-primary border-primary/20' : 'bg-surface-container-low text-on-surface'}`}
                    >
                        <span className="material-symbols-outlined text-[18px]">tune</span>
                        <span>高级筛选</span>
                        <span className="material-symbols-outlined text-[16px] transition-transform duration-200" style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0)' }}>expand_more</span>
                    </button>
                </div>

                {/* 展开的更多筛选项区域 */}
                {isExpanded && (
                    <div className="pt-4 border-t border-border-hairline/60 grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
                        {/* 状态下拉框 */}
                        <div className="relative">
                            <select 
                                value={filterStatus}
                                onChange={e => { setFilterStatus(e.target.value); setPage(1); }}
                                className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-sm rounded-lg pl-4 pr-10 py-2 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all cursor-pointer appearance-none animate-none bg-none"
                            >
                                <option value="">-- 系统同步状态 (全部) --</option>
                                <option value="selected">已选品</option>
                                <option value="success">已上架</option>
                                <option value="depublished">已下架</option>
                                <option value="pending">同步中</option>
                                <option value="failed">同步失败</option>
                            </select>
                            <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-secondary pointer-events-none">expand_more</span>
                        </div>
                        
                        {/* 拿货进价价格区间 */}
                        <div className="flex items-center gap-2">
                            <span className="font-sans text-xs font-semibold text-secondary whitespace-nowrap w-16">拿货进价:</span>
                            <input 
                                type="number" 
                                placeholder="Min"
                                value={minSourcePrice}
                                onChange={e => { setMinSourcePrice(e.target.value); setPage(1); }}
                                className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-primary transition-all font-mono"
                            />
                            <span className="text-secondary text-xs">~</span>
                            <input 
                                type="number" 
                                placeholder="Max"
                                value={maxSourcePrice}
                                onChange={e => { setMaxSourcePrice(e.target.value); setPage(1); }}
                                className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-primary transition-all font-mono"
                            />
                        </div>

                        {/* 爆款参考价价格区间 */}
                        <div className="flex items-center gap-2">
                            <span className="font-sans text-xs font-semibold text-secondary whitespace-nowrap w-16">参考价:</span>
                            <input 
                                type="number" 
                                placeholder="Min"
                                value={minRefPrice}
                                onChange={e => { setMinRefPrice(e.target.value); setPage(1); }}
                                className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-primary transition-all font-mono"
                            />
                            <span className="text-secondary text-xs">~</span>
                            <input 
                                type="number" 
                                placeholder="Max"
                                value={maxRefPrice}
                                onChange={e => { setMaxRefPrice(e.target.value); setPage(1); }}
                                className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-primary transition-all font-mono"
                            />
                        </div>

                        {/* 操作按钮组 (强行放到第三列) */}
                        <div className="md:col-start-3 flex justify-end gap-2.5">
                            <button 
                                className="px-4 py-2 bg-surface-container-high border border-border-hairline hover:bg-surface-container-highest text-on-surface rounded-lg font-sans text-sm font-semibold transition-colors flex items-center gap-1.5"
                                onClick={() => {
                                    setKeyword('');
                                    setFilterStatus('');
                                    setMinSourcePrice('');
                                    setMaxSourcePrice('');
                                    setMinRefPrice('');
                                    setMaxRefPrice('');
                                    setPage(1);
                                }}
                            >
                                <span className="material-symbols-outlined text-[18px]">clear_all</span>
                                <span>重置</span>
                            </button>
                            <button 
                                className="bg-primary hover:bg-primary-container text-white px-5 py-2 rounded-lg font-sans text-sm font-semibold transition-colors flex items-center gap-1.5 shadow-[0_2px_8px_rgba(168,50,0,0.15)]"
                                onClick={() => { setPage(1); fetchPublishedProducts(); }}
                            >
                                <span className="material-symbols-outlined text-[18px]">filter_alt</span>
                                <span>立即筛选</span>
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {loading ? (
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl py-24 text-center ambient-shadow">
                    <div className="inline-flex items-center gap-2 text-secondary text-sm">
                        <span className="material-symbols-outlined animate-spin text-primary text-[24px]">sync</span>
                        正在加载选品商品资产列表...
                    </div>
                </div>
            ) : items.length > 0 ? (
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl overflow-hidden ambient-shadow">
                    <div className="px-4 py-3 min-h-[56px] border-b border-border-hairline bg-surface-container-lowest flex items-center justify-between gap-4 flex-wrap">
                        <div className="flex items-center gap-3 min-h-[32px]">
                            {selectedIds.length > 0 && (
                                <span className="text-xs font-semibold text-primary bg-primary/10 border border-primary/20 px-2 py-0.5 rounded-full">
                                    已选 {selectedIds.length} 项
                                </span>
                            )}
                            {syncStatusNotice && (
                                <span className="text-xs font-semibold text-warning bg-warning/10 border border-warning/20 px-2 py-0.5 rounded-full">
                                    {syncStatusNotice}
                                </span>
                            )}
                        </div>

                        {selectedIds.length > 0 && (
                            <div className="flex items-center gap-2 flex-wrap min-h-[32px]">
                                {publishableIds.length > 0 && (
                                    <button
                                        className="px-3.5 py-1.5 bg-primary hover:bg-primary-container text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-40"
                                        disabled={batchPublishing || batchDepublishing || batchDeleting || batchSyncingStatus}
                                        onClick={doBatchPublish}
                                    >
                                        {batchPublishing ? "云同步中..." : `🚀 批量发布 (${publishableIds.length})`}
                                    </button>
                                )}
                                {syncableIds.length > 0 && (
                                    <button
                                        className="px-3.5 py-1.5 bg-surface-container-high hover:bg-surface-container-highest border border-border-hairline text-on-surface rounded-lg text-xs font-semibold transition-colors disabled:opacity-40 flex items-center gap-1"
                                        disabled={batchPublishing || batchDepublishing || batchDeleting || batchSyncingStatus}
                                        onClick={doBatchSyncStatus}
                                    >
                                        <span className={`material-symbols-outlined text-[16px] ${batchSyncingStatus ? 'animate-spin' : ''}`}>sync</span>
                                        {batchSyncingStatus ? "同步中..." : `同步选品状态 (${syncableIds.length})`}
                                    </button>
                                )}
                                {depublishableIds.length > 0 && (
                                    <button
                                        className="px-3.5 py-1.5 bg-warning hover:bg-warning/80 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-40"
                                        disabled={batchPublishing || batchDepublishing || batchDeleting || batchSyncingStatus}
                                        onClick={doBatchDepublish}
                                    >
                                        {batchDepublishing ? "云同步中..." : `⚠️ 批量下架 (${depublishableIds.length})`}
                                    </button>
                                )}
                                {deletableIds.length > 0 && (
                                    <button
                                        className="px-3.5 py-1.5 bg-error hover:bg-error/85 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-40"
                                        disabled={batchPublishing || batchDepublishing || batchDeleting || batchSyncingStatus}
                                        onClick={doBatchDelete}
                                    >
                                        {batchDeleting ? "云注销中..." : `🗑️ 批量删除 (${deletableIds.length})`}
                                    </button>
                                )}
                            </div>
                        )}
                    </div>

                    <div className="overflow-x-auto w-full">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="bg-table-header-bg border-b border-border-hairline">
                                    <th className="p-cell-padding font-sans text-xs font-semibold text-secondary uppercase tracking-wider w-14 text-center">
                                        <input
                                            type="checkbox"
                                            className="rounded border-secondary text-primary focus:ring-primary/20 w-4 h-4 cursor-pointer"
                                            checked={items.length > 0 && items.every(item => selectedIds.includes(item.source_db_id))}
                                            onChange={(e) => {
                                                if (e.target.checked) {
                                                    setSelectedIds(items.map(item => item.source_db_id));
                                                } else {
                                                    setSelectedIds([]);
                                                }
                                            }}
                                            title="本页全选"
                                        />
                                    </th>
                                    <th className="p-cell-padding font-sans text-xs font-semibold text-secondary uppercase tracking-wider w-20">主图</th>
                                    {renderSortHeader("1688 原始货源信息", "title")}
                                    {renderSortHeader("闲鱼端商品 ID", "xianyu_item_id", "font-mono")}
                                    {renderSortHeader("系统同步状态", "publish_status")}
                                    {renderSortHeader("拿货进价", "source_price")}
                                    {renderSortHeader("爆款参考价", "ref_price")}
                                    {renderSortHeader("发布时间", "publish_time")}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border-hairline text-sm">
                                {items.map((item) => {
                                    const currentStatus = getPublishedItemStatus(item);
                                    const isChecked = selectedIds.includes(item.source_db_id);
                                    const detailIncomplete = isSourceDetailIncomplete(item);
                                    const detailIncompleteReason = getSourceDetailIncompleteReason(item);
                                    
                                    let statusText = '未知';
                                    let statusClass = 'bg-secondary/10 text-secondary border-secondary/20';
                                    let pulseColor = 'bg-secondary';

                                    if (currentStatus === 'done') {
                                        statusText = '已上架';
                                        statusClass = 'bg-success/10 text-success border-success/20';
                                        pulseColor = 'bg-success';
                                    } else if (currentStatus === 'selected') {
                                        statusText = '已选品';
                                        statusClass = 'bg-primary/10 text-primary border-primary/20';
                                        pulseColor = 'bg-primary';
                                    } else if (currentStatus === 'depublished') {
                                        statusText = '已下架';
                                        statusClass = 'bg-warning/10 text-warning border-warning/20';
                                        pulseColor = 'bg-warning';
                                    } else if (currentStatus === 'failed') {
                                        statusText = '同步失败';
                                        statusClass = 'bg-error/10 text-error border-error/20';
                                        pulseColor = 'bg-error';
                                    } else if (currentStatus === 'pending' || currentStatus === 'publishing') {
                                        statusText = '同步中';
                                        statusClass = 'bg-processing/10 text-processing border-processing/20';
                                        pulseColor = 'bg-processing';
                                    } else if (currentStatus === 'deleting') {
                                        statusText = '删除中';
                                        statusClass = 'bg-error/10 text-error border-error/20';
                                        pulseColor = 'bg-error';
                                    }

                                    return (
                                        <tr 
                                            key={item.publish_id} 
                                            className="hover:bg-surface-container-low transition-colors cursor-pointer group"
                                            onClick={() => setSelectedProduct(item)}
                                        >
                                            <td className="p-cell-padding text-center">
                                                <input
                                                    type="checkbox"
                                                    className="rounded border-secondary text-primary focus:ring-primary/20 w-4 h-4 cursor-pointer"
                                                    checked={isChecked}
                                                    onClick={e => e.stopPropagation()}
                                                    onChange={(e) => {
                                                        if (e.target.checked) {
                                                            setSelectedIds(prev => [...prev, item.source_db_id]);
                                                        } else {
                                                            setSelectedIds(prev => prev.filter(id => id !== item.source_db_id));
                                                        }
                                                    }}
                                                />
                                            </td>
                                            <td className="p-cell-padding">
                                                {item.source_image ? (
                                                    <img 
                                                        src={item.source_image} 
                                                        className="w-12 h-12 rounded-lg object-cover border border-border-hairline mx-auto" 
                                                        referrerPolicy="no-referrer"
                                                        loading="lazy"
                                                        decoding="async"
                                                    />
                                                ) : (
                                                    <div className="w-12 h-12 rounded-lg bg-surface-container border border-border-hairline flex items-center justify-center text-secondary text-[10px] mx-auto">暂无图片</div>
                                                )}
                                            </td>
                                            <td className="p-cell-padding">
                                                <div className="font-semibold text-on-surface max-w-[280px] truncate" title={item.source_title}>
                                                    {item.source_title}
                                                </div>
                                                <div className="text-xs text-secondary mt-1 flex items-center gap-1">
                                                    <a 
                                                        href={item.source_url} 
                                                        target="_blank" 
                                                        rel="noreferrer" 
                                                        className="hover:text-primary transition-colors flex items-center gap-0.5" 
                                                        onClick={e => e.stopPropagation()}
                                                    >
                                                        查看1688货源 ↗
                                                    </a>
                                                    {detailIncomplete && (
                                                        <span
                                                            className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-warning/10 text-warning border border-warning/20 text-[10px] font-bold"
                                                            title={detailIncompleteReason}
                                                        >
                                                            <span className="material-symbols-outlined text-[12px] leading-none">warning</span>
                                                            风控未完整抓取
                                                        </span>
                                                    )}
                                                </div>
                                            </td>
                                            <td className="p-cell-padding font-mono font-bold text-on-surface">{item.xianyu_item_id || '-'}</td>
                                            <td className="p-cell-padding">
                                                <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold border ${statusClass}`}>
                                                    <span className={`w-1.5 h-1.5 rounded-full ${pulseColor} animate-pulse`}></span>
                                                    {statusText}
                                                </span>
                                            </td>
                                            <td className="p-cell-padding font-mono text-secondary font-bold">{formatPublishedSourcePrice(item)}</td>
                                            <td className="p-cell-padding font-mono text-on-surface font-semibold">¥{item.ref_price || '-'}</td>
                                            <td className="p-cell-padding text-secondary text-xs">{item.publish_time}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>

                    {/* 分页控制 */}
                    {totalPages > 1 && (
                        <div className="p-4 border-t border-border-hairline bg-surface-container-lowest flex items-center justify-between">
                            <span className="font-mono text-xs text-secondary">
                                第 {page} / {totalPages} 页（共 {total} 条，每页 {limit} 条）
                            </span>
                            <div className="flex items-center gap-1.5">
                                <button 
                                    className="w-8 h-8 flex items-center justify-center rounded border border-border-hairline text-secondary hover:bg-surface-container-low transition-colors disabled:opacity-40" 
                                    disabled={page <= 1} 
                                    onClick={() => setPage(p => p - 1)}
                                >
                                    <span className="material-symbols-outlined text-[18px]">chevron_left</span>
                                </button>
                                <span className="font-mono text-xs font-bold px-3 py-1 bg-primary/10 border border-primary/20 text-primary rounded">
                                    {page}
                                </span>
                                <button 
                                    className="w-8 h-8 flex items-center justify-center rounded border border-border-hairline text-secondary hover:bg-surface-container-low transition-colors disabled:opacity-40" 
                                    disabled={page >= totalPages} 
                                    onClick={() => setPage(p => p + 1)}
                                >
                                    <span className="material-symbols-outlined text-[18px]">chevron_right</span>
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            ) : (
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl py-24 text-center ambient-shadow">
                    <span className="material-symbols-outlined text-secondary text-[48px] opacity-40">package_2</span>
                    <p className="text-secondary font-semibold mt-4 text-sm">暂无选品记录。</p>
                    <p className="text-xs text-secondary/60 mt-1">您可以先前往“决策资产库”中将匹配货源加入选品。</p>
                </div>
            )}

            {/* 详情模态弹窗 */}
            {selectedProduct && (
                <DetailModal
                    item={selectedProduct}
                    onClose={() => setSelectedProduct(null)}
                    onUpdateItem={setSelectedProduct}
                    handleStatusLoaded={handleStatusLoaded}
                    batchStatusMap={batchStatusMap}
                    batchResultMap={batchResultMap}
                    grossProfitRate={grossProfitRate}
                />
            )}
            {confirmDialog && (
                <ActionConfirmModal
                    title={confirmDialog.title}
                    description={confirmDialog.description}
                    confirmLabel={confirmDialog.confirmLabel}
                    tone={confirmDialog.tone}
                    onConfirm={() => {
                        const action = confirmDialog.onConfirm;
                        setConfirmDialog(null);
                        action();
                    }}
                    onClose={() => setConfirmDialog(null)}
                />
            )}
        </div>
    );
};

// --- 加入选品按钮组件 ---
const SelectionButton = ({ src, batchStatus, batchResult, onStatusLoaded }) => {
    const normalizeSelectionStatus = (rawStatus) => {
        if (rawStatus === 'selected' || rawStatus === 'success' || rawStatus === 'done') return 'selected';
        if (rawStatus === 'selecting') return 'selecting';
        if (rawStatus === 'failed') return 'failed';
        return 'idle';
    };
    const [status, setStatus] = useState(() => normalizeSelectionStatus(src.publish_status));
    const [result, setResult] = useState(null);

    useEffect(() => {
        if (batchStatus) {
            setStatus(normalizeSelectionStatus(batchStatus));
        }
        if (batchResult) {
            setResult(batchResult);
        }
    }, [batchStatus, batchResult]);

    const addToSelection = async () => {
        setStatus('selecting');
        try {
            const res = await fetch('/api/selection/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_ids: [src.db_id] })
            }).then(r => r.json());
            const failed = (res.failed || []).find(item => item.source_id === src.db_id);
            if (failed || res.error) {
                const errResult = { msg: failed?.msg || res.error || '加入选品失败' };
                setResult(errResult);
                setStatus('failed');
                if (onStatusLoaded) onStatusLoaded(src.db_id, 'failed', errResult);
                return;
            }
            const success = (res.success || []).find(item => item.source_id === src.db_id);
            const finalStatus = success?.status === 'success' ? 'done' : 'selected';
            const okResult = { status: finalStatus, msg: '已加入选品' };
            setResult(okResult);
            setStatus('selected');
            if (onStatusLoaded) onStatusLoaded(src.db_id, finalStatus, okResult);
        } catch (e) {
            const errResult = { msg: '网络错误，请稍后重试' };
            setResult(errResult);
            setStatus('failed');
            if (onStatusLoaded) onStatusLoaded(src.db_id, 'failed', errResult);
        }
    };

    if (status === 'selected') {
        return (
            <div className="flex justify-end mt-1">
                <span className="px-3 py-1 bg-primary/10 text-primary rounded-lg font-sans text-xs font-semibold flex items-center gap-1">
                    <span className="material-symbols-outlined text-[16px] icon-fill">done</span>
                    已加入选品
                </span>
            </div>
        );
    }

    if (status === 'selecting') {
        return (
            <div className="flex justify-end mt-1">
                <span className="px-3 py-1 bg-processing/15 text-processing rounded-lg font-sans text-xs font-semibold flex items-center gap-1">
                    <span className="material-symbols-outlined text-[16px] animate-spin">sync</span>
                    加入中...
                </span>
            </div>
        );
    }

    if (status === 'failed') {
        return (
            <div className="flex flex-col items-end gap-1 mt-1">
                <span className="text-[10px] text-error font-medium truncate max-w-[150px]">{result?.msg || '加入失败'}</span>
                <button
                    className="px-3 py-1 bg-error/15 hover:bg-error/20 text-error rounded-lg font-sans text-xs font-semibold transition-colors"
                    onClick={addToSelection}
                >
                    重新加入
                </button>
            </div>
        );
    }

    return (
        <div className="flex justify-end mt-1">
            <button
                className="px-4 py-1.5 bg-primary hover:bg-primary-container text-white rounded-lg font-sans text-xs font-bold shadow-sm transition-all scale-100 active:scale-95 flex items-center gap-1"
                onClick={addToSelection}
            >
                <span className="material-symbols-outlined text-[16px]">playlist_add</span>
                加入选品
            </button>
        </div>
    );
};

// --- 发布至闲鱼按钮组件 ---
const PublishButton = ({ src, xianyuPrice, batchStatus, batchResult, onStatusLoaded, initialStatus = null, initialResult = null, skipStatusFetch = false }) => {
    const [status, setStatus] = useState('idle'); // idle | publishing | done | failed | depublished | deleting
    const [pubResult, setPubResult] = useState(null);
    const [showModal, setShowModal] = useState(false);
    const [confirmDialog, setConfirmDialog] = useState(null);
    const [editTitle, setEditTitle] = useState('');
    const [editPrice, setEditPrice] = useState('');
    const [skus, setSkus] = useState([]);
    const [loadingSkus, setLoadingSkus] = useState(false);

    // 挂载时查询历史发布状态
    useEffect(() => {
        if (skipStatusFetch) {
            if (initialStatus === 'success' || initialStatus === 'done') {
                setStatus('done');
                if (initialResult) setPubResult(initialResult);
                if (onStatusLoaded) onStatusLoaded(src.db_id, 'done', initialResult);
            } else if (initialStatus === 'depublished') {
                setStatus('depublished');
                if (initialResult) setPubResult(initialResult);
                if (onStatusLoaded) onStatusLoaded(src.db_id, 'depublished', initialResult);
            } else if (initialStatus === 'failed') {
                setStatus('failed');
                if (initialResult) setPubResult(initialResult);
                if (onStatusLoaded) onStatusLoaded(src.db_id, 'failed', initialResult);
            } else if (initialStatus === 'selected') {
                setStatus('idle');
                if (initialResult) setPubResult(initialResult);
            } else {
                setStatus('idle');
                if (initialResult) setPubResult(initialResult);
                if (onStatusLoaded) onStatusLoaded(src.db_id, 'idle', initialResult);
            }
            return;
        }

        fetch(`/api/published_status/${src.db_id}`)
            .then(r => r.json())
            .then(res => {
                if (res.publish_status === 'success') {
                    setStatus('done');
                    setPubResult(res);
                    if (onStatusLoaded) onStatusLoaded(src.db_id, 'done', res);
                } else if (res.publish_status === 'depublished') {
                    setStatus('depublished');
                    setPubResult(res);
                    if (onStatusLoaded) onStatusLoaded(src.db_id, 'depublished', res);
                } else if (res.publish_status === 'deleted') {
                    setStatus('idle');
                    setPubResult(null);
                    if (onStatusLoaded) onStatusLoaded(src.db_id, 'idle', null);
                } else if (res.publish_status === 'selected') {
                    setStatus('idle');
                    setPubResult(res);
                } else {
                    if (onStatusLoaded) onStatusLoaded(src.db_id, 'idle', null);
                }
            })
            .catch(() => {});
    }, [src.db_id, skipStatusFetch, initialStatus]);

    // 联动外部批量发布状态
    useEffect(() => {
        if (batchStatus) {
            setStatus(batchStatus);
            if (batchStatus === 'idle') {
                setPubResult(null);
            }
        }
        if (batchResult) {
            setPubResult(batchResult);
        }
    }, [batchStatus, batchResult]);

    const openModal = async () => {
        setEditTitle(src.title.slice(0, 60));
        setEditPrice((parseFloat(src.min_price) + 30).toFixed(2));
        setSkus([]);
        setLoadingSkus(true);
        setShowModal(true);
        try {
            const res = await fetch(`/api/source_skus/${src.db_id}`).then(r => r.json());
            if (res.skus && res.skus.length > 0) {
                const initializedSkus = res.skus.map(s => ({
                    ...s,
                    xianyu_price: (parseFloat(s.price) + 30).toFixed(2),
                    stock: Math.min(9999, parseInt(s.stock) || 1)
                }));
                setSkus(initializedSkus);
            }
        } catch (e) {
            console.error("加载SKU失败:", e);
        } finally {
            setLoadingSkus(false);
        }
    };

    const doPublish = async () => {
        setShowModal(false);
        setStatus('publishing');
        try {
            const payload = { title: editTitle };
            if (skus.length > 1) {
                payload.sku_items = skus.map(s => ({
                    sku_text: s.sku_text,
                    price: parseFloat(s.xianyu_price),
                    stock: parseInt(s.stock) || 1
                }));

                // 自动组装单轴绑定规格图 sku_images
                const skuImages = [];
                skus.forEach(s => {
                    if (s.image) {
                        const firstAttr = s.sku_text.split(';')[0];
                        skuImages.push({
                            src: s.image,
                            width: 800,
                            height: 800,
                            sku_text: firstAttr
                        });
                    }
                });
                if (skuImages.length > 0) {
                    payload.sku_images = skuImages;
                }
            } else if (skus.length === 1) {
                payload.price = parseFloat(skus[0].xianyu_price);
            } else {
                payload.price = parseFloat(editPrice);
            }

            const res = await fetch(`/api/publish/${src.db_id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).then(r => r.json());
            setPubResult(res);
            const finalStatus = res.status === 'success' ? 'done' : 'failed';
            setStatus(finalStatus);
            if (onStatusLoaded) onStatusLoaded(src.db_id, finalStatus, res);
        } catch (e) {
            const errResult = { msg: '网络错误，请稍后重试' };
            setPubResult(errResult);
            setStatus('failed');
            if (onStatusLoaded) onStatusLoaded(src.db_id, 'failed', errResult);
        }
    };

    const executeDepublish = async () => {
        setStatus('publishing');
        try {
            const res = await fetch(`/api/depublish/${src.db_id}`, {
                method: 'POST'
            }).then(r => r.json());
            if (res.status === 'success') {
                setStatus('depublished');
                if (onStatusLoaded) onStatusLoaded(src.db_id, 'depublished', res);
                alert("下架成功！");
            } else {
                alert("下架失败: " + (res.msg || "未知错误"));
                setStatus('done');
                if (onStatusLoaded) onStatusLoaded(src.db_id, 'done', res);
            }
        } catch (e) {
            alert("网络错误，下架失败");
            setStatus('done');
            if (onStatusLoaded) onStatusLoaded(src.db_id, 'done', null);
        }
    };

    const doDepublish = () => {
        setConfirmDialog({
            title: '确认下架商品',
            description: [
                '该商品当前已发布到闲鱼云端。',
                '确认后会立即执行下架，但本地发布记录会保留，方便后续重新上架。'
            ],
            confirmLabel: '确认下架',
            tone: 'warning',
            onConfirm: () => executeDepublish()
        });
    };

    const executeDelete = async () => {
        setStatus('deleting');
        if (onStatusLoaded) onStatusLoaded(src.db_id, 'deleting', null);
        try {
            const res = await fetch(`/api/delete/${src.db_id}`, {
                method: 'POST'
            }).then(r => r.json());
            if (res.status === 'success') {
                setStatus('idle');
                setPubResult(null);
                if (onStatusLoaded) onStatusLoaded(src.db_id, 'idle', null);
                alert("删除成功！");
            } else {
                alert("删除失败: " + (res.msg || "未知错误"));
                setStatus('depublished');
                if (onStatusLoaded) onStatusLoaded(src.db_id, 'depublished', res);
            }
        } catch (e) {
            alert("网络错误，删除失败");
            setStatus('depublished');
            if (onStatusLoaded) onStatusLoaded(src.db_id, 'depublished', null);
        }
    };

    const doDelete = () => {
        setConfirmDialog({
            title: '确认删除商品',
            description: [
                '这会删除当前商品的发布记录。',
                '如果商品已下架，会同时执行闲鱼云端删除；如果是已选品或同步失败商品，则只清理本地记录。此操作不可恢复。'
            ],
            confirmLabel: '确认删除',
            tone: 'danger',
            onConfirm: () => executeDelete()
        });
    };

    return (
        <div>
            {status === 'done' && (
                <div className="flex gap-2 items-center justify-end mt-1">
                    <a 
                        href={pubResult?.published_url} 
                        target="_blank" 
                        rel="noreferrer"
                        className="px-3 py-1 bg-success/15 hover:bg-success/20 text-success rounded-lg font-sans text-xs font-semibold transition-colors flex items-center gap-1"
                    >
                        <span className="material-symbols-outlined text-[16px] icon-fill">done</span>
                        已发布
                    </a>
                    <button 
                        className="px-3 py-1 bg-warning/15 hover:bg-warning/20 text-warning rounded-lg font-sans text-xs font-semibold transition-colors flex items-center gap-1" 
                        onClick={doDepublish}
                    >
                        <span className="material-symbols-outlined text-[16px]">pause_circle</span>
                        下架
                    </button>
                </div>
            )}
            {status === 'depublished' && (
                <div className="flex gap-2 items-center justify-end mt-1">
                    <span className="px-3 py-1 bg-warning/15 text-warning rounded-lg font-sans text-xs font-semibold flex items-center gap-1">
                        <span className="material-symbols-outlined text-[16px]">warning</span>
                        已下架
                    </span>
                    <button 
                        className="px-3 py-1 bg-primary hover:bg-primary-container text-white rounded-lg font-sans text-xs font-semibold transition-colors flex items-center gap-1" 
                        onClick={openModal}
                    >
                        <span className="material-symbols-outlined text-[16px]">publish</span>
                        上架
                    </button>
                    <button 
                        className="px-3 py-1 bg-error/15 hover:bg-error/20 text-error rounded-lg font-sans text-xs font-semibold transition-colors flex items-center gap-1" 
                        onClick={doDelete}
                    >
                        <span className="material-symbols-outlined text-[16px]">delete</span>
                        删除
                    </button>
                </div>
            )}
            {status === 'publishing' && (
                <div className="flex justify-end mt-1">
                    <span className="px-3 py-1 bg-processing/15 text-processing rounded-lg font-sans text-xs font-semibold flex items-center gap-1">
                        <span className="material-symbols-outlined text-[16px] animate-spin">sync</span>
                        云同步中...
                    </span>
                </div>
            )}
            {status === 'deleting' && (
                <div className="flex justify-end mt-1">
                    <span className="px-3 py-1 bg-error/15 text-error rounded-lg font-sans text-xs font-semibold flex items-center gap-1">
                        <span className="material-symbols-outlined text-[16px] animate-spin">sync</span>
                        注销中...
                    </span>
                </div>
            )}
            {status === 'failed' && (
                <div className="flex flex-col items-end gap-1 mt-1">
                    <span className="text-[10px] text-error font-medium truncate max-w-[150px]">❌ {pubResult?.msg || '操作失败'}</span>
                    <button 
                        className="px-3 py-1 bg-error/15 hover:bg-error/20 text-error rounded-lg font-sans text-xs font-semibold transition-colors" 
                        onClick={openModal}
                    >
                        重新尝试
                    </button>
                </div>
            )}
            {status === 'idle' && (
                <div className="flex justify-end mt-1">
                    <button 
                        className="px-4 py-1.5 bg-primary hover:bg-primary-container text-white rounded-lg font-sans text-xs font-bold shadow-sm transition-all scale-100 active:scale-95 flex items-center gap-1" 
                        onClick={openModal}
                    >
                        <span className="material-symbols-outlined text-[16px]">publish</span>
                        上架闲鱼
                    </button>
                </div>
            )}

            {showModal && (
                <PublishPreviewModal
                    src={src}
                    editTitle={editTitle}
                    setEditTitle={setEditTitle}
                    editPrice={editPrice}
                    setEditPrice={setEditPrice}
                    skus={skus}
                    setSkus={setSkus}
                    loadingSkus={loadingSkus}
                    doPublish={doPublish}
                    onClose={() => setShowModal(false)}
                />
            )}
            {confirmDialog && (
                <ActionConfirmModal
                    title={confirmDialog.title}
                    description={confirmDialog.description}
                    confirmLabel={confirmDialog.confirmLabel}
                    tone={confirmDialog.tone}
                    onConfirm={() => {
                        const action = confirmDialog.onConfirm;
                        setConfirmDialog(null);
                        action();
                    }}
                    onClose={() => setConfirmDialog(null)}
                />
            )}
        </div>
    );
};

// --- 系统配置管理视图组件 ---
const SystemSettingsView = ({ hideHeader = false }) => {
    const SOURCE_CHANNEL_TYPE_META = {
        ali1688: {
            label: '1688 货源渠道',
            supportsSessionState: true,
            supportsLoginTrigger: true,
            authTypeLabel: '系统托管 Chrome 会话'
        },
        taobao: {
            label: '淘宝货源渠道',
            supportsSessionState: false,
            supportsLoginTrigger: false,
            authTypeLabel: '待接入'
        },
        pdd: {
            label: '拼多多货源渠道',
            supportsSessionState: false,
            supportsLoginTrigger: false,
            authTypeLabel: '待接入'
        },
        custom: {
            label: '自定义货源渠道',
            supportsSessionState: false,
            supportsLoginTrigger: false,
            authTypeLabel: '自定义适配'
        }
    };

    const getSourceChannelCapabilities = (channelType) => SOURCE_CHANNEL_TYPE_META[channelType] || SOURCE_CHANNEL_TYPE_META.custom;
    const CHANNEL_SEARCH_FILTER_META = {
        ali1688: [
            { key: 'rapid_invoice', label: '极速开票', group: '服务能力' },
            { key: 'selected_distributors', label: '分销严选', group: '分销能力' },
            { key: 'single_piece_drop_shipping', label: '一件代发', group: '分销能力' },
            { key: 'seven_day_return', label: '7天无理由', group: '售后保障' },
            { key: 'single_piece_free_shipping', label: '1件代发包邮', group: '分销能力' },
            { key: 'free_shipping', label: '包邮', group: '服务能力' },
            { key: 'freight_insurance_return', label: '退货包运费', group: '售后保障' },
            { key: 'real_factory_verified', label: '真实工厂认证', group: '资质认证' },
            { key: 'strength_verified', label: '实力认证', group: '资质认证' },
            { key: 'official_logistics', label: '官方物流', group: '服务能力' },
            { key: 'douyin_encrypted_waybill', label: '抖音面单', group: '密文面单' }
        ]
    };
    const getSupportedChannelSearchFilters = (channelType) => CHANNEL_SEARCH_FILTER_META[channelType] || [];

    const createOpenapiAccount = (index = 1) => ({
        id: `account-${Date.now()}-${index}`,
        name: `闲鱼账号 ${index}`,
        base_url: 'https://open.goofish.pro',
        appid: '',
        app_secret: '',
        show_secret: false,
        state_file: '',
        default_config: {
            user_name: '',
            province: 110000,
            city: 110100,
            district: 110101,
            item_biz_type: 2,
            sp_biz_type: 2,
            channel_cat_id: '',
            stuff_status: 100,
            express_fee: 0
        }
    });

    const createSourceChannelAccount = (channelId = 'ali1688', index = 1) => ({
        account_id: `${channelId}-account-${Date.now()}-${index}`,
        label: channelId === 'ali1688' ? `1688 账号 ${index}` : `渠道账号 ${index}`,
        enabled: true,
        notes: '',
        session_report: {
            is_usable: false,
            is_logged_in: false,
            requires_verification: false,
            account_name: '',
            status_text: '未检测',
            last_checked_at: '',
            error_message: '',
            meta: {}
        }
    });

    const createSourceChannel = (index = 1, channelType = 'ali1688') => {
        const channelId = channelType === 'ali1688' ? 'ali1688' : `source-channel-${Date.now()}-${index}`;
        const firstAccount = createSourceChannelAccount(channelId, 1);
        const channelMeta = getSourceChannelCapabilities(channelType);
        return {
            channel_id: channelId,
            channel_type: channelType,
            label: channelMeta.label || `货源渠道 ${index}`,
            enabled: true,
            active_account_ids: [firstAccount.account_id],
            active_account_id: firstAccount.account_id,
            accounts: [firstAccount]
        };
    };

    const [configs, setConfigs] = useState({
        openapi: {
            active_account_id: 'account-1',
            accounts: [createOpenapiAccount(1)]
        },
        source_channels: {
            active_channel_id: 'ali1688',
            channels: [createSourceChannel(1)]
        }
    });
    
    // 多大模型配置列表状态
    const [llmList, setLlmList] = useState([]);
    
    // 卡片折叠状态，默认收起
    const [llmCollapsed, setLlmCollapsed] = useState(true);
    const [openapiCollapsed, setOpenapiCollapsed] = useState(true);
    const [sessionCollapsed, setSessionCollapsed] = useState(true);
    const [sourceChannelsCollapsed, setSourceChannelsCollapsed] = useState(true);
    const [crawlCollapsed, setCrawlCollapsed] = useState(true);
    const [crawlConfig, setCrawlConfig] = useState({
        source_limit_1688: 10,
        gross_profit_rate: DEFAULT_GROSS_PROFIT_RATE,
        source_filter_models: [],
        source_channel_selection_mode: 'active_pool',
        enabled_source_channels: [],
        channel_search_filters: []
    });
    const [selectedCrawlChannelId, setSelectedCrawlChannelId] = useState('');
    const [crawlSelectionAdjustmentNotice, setCrawlSelectionAdjustmentNotice] = useState('');

    // 从 llmList 中聚合出所有保存的模型名称
    const availableModels = useMemo(() => {
        const modelsSet = new Set();
        llmList.forEach(item => {
            if (item.models_str) {
                item.models_str.split(',')
                    .map(m => m.trim())
                    .filter(m => m)
                    .forEach(m => modelsSet.add(m));
            }
        });
        return Array.from(modelsSet);
    }, [llmList]);

    // 级联选择下拉框数据 (从后端获取)
    const [regions, setRegions] = useState([]);
    
    // 下拉级联选择当前选中的 adcode 状态
    const [selectedProv, setSelectedProv] = useState("110000");
    const [selectedCity, setSelectedCity] = useState("110100");
    const [selectedDist, setSelectedDist] = useState("110101");
    const [isCustomRegion, setIsCustomRegion] = useState(false);

    // 类目数据 (从后端获取)
    const [catGroups, setCatGroups] = useState([]); 
    const [catList, setCatList] = useState([]); 
    const [selectedGroup, setSelectedGroup] = useState(""); 
    const [catQuery, setCatQuery] = useState(""); 
    const [selectedCat, setSelectedCat] = useState(""); 
    const [isCustomCat, setIsCustomCat] = useState(false);

    // 系统基础请求及消息状态
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState(null);
    const [error, setError] = useState(null);

    const [xianyuLoginStatus, setXianyuLoginStatus] = useState(null);
    const [isXianyuLoggingIn, setIsXianyuLoggingIn] = useState(false);
    const [xianyuLoginSuccessMessage, setXianyuLoginSuccessMessage] = useState(null);
    const [isCheckingSourceChannelStatus, setIsCheckingSourceChannelStatus] = useState(false);
    const [isSourceChannelLoggingIn, setIsSourceChannelLoggingIn] = useState(false);
    const [sourceChannelLoginResult, setSourceChannelLoginResult] = useState('');
    const [sourceChannelLoginResultFinishedAt, setSourceChannelLoginResultFinishedAt] = useState('');
    const [sourceChannelLoginErrorMessage, setSourceChannelLoginErrorMessage] = useState('');
    const [persistedOpenapiAccountIds, setPersistedOpenapiAccountIds] = useState([]);
    const xianyuLoginFlowRef = useRef(false);
    const prevXianyuLoggingInRef = useRef(false);
    const sourceChannelLoginFlowRef = useRef(false);
    const prevSourceChannelLoggingInRef = useRef(false);
    const sourceChannelLoginStartedAtRef = useRef('');
    const sourceChannelLoginHandledAtRef = useRef('');
    const noticeTimerRef = useRef(null);
    const xianyuLoginSuccessTimerRef = useRef(null);
    const lastCrawlSelectionAdjustmentRef = useRef('');
    const currentOpenapiAccounts = configs.openapi?.accounts || [];
    const activeOpenapiAccountId = configs.openapi?.active_account_id || currentOpenapiAccounts[0]?.id || '';
    const currentOpenapiAccount = currentOpenapiAccounts.find(item => item.id === activeOpenapiAccountId) || currentOpenapiAccounts[0] || createOpenapiAccount(1);
    const currentSourceChannels = configs.source_channels?.channels || [];
    const normalizeLocalCrawlConfig = (rawCrawlCfg, channels) => {
        const safeCfg = rawCrawlCfg && typeof rawCrawlCfg === 'object' ? rawCrawlCfg : {};
        const safeChannels = Array.isArray(channels) ? channels : [];
        const selectionMode = safeCfg.source_channel_selection_mode === 'custom_selected' ? 'custom_selected' : 'active_pool';
        const availableChannelMap = {};
        const availableChannelTypeMap = {};
        const orderedChannelIds = [];
        safeChannels
            .filter(channel => channel?.enabled !== false && channel?.channel_id)
            .forEach(channel => {
                orderedChannelIds.push(channel.channel_id);
                const rawActiveIds = Array.isArray(channel?.active_account_ids)
                    ? channel.active_account_ids
                    : (channel?.active_account_id ? [channel.active_account_id] : []);
                const usableAccountIds = (channel?.accounts || [])
                    .filter(account => rawActiveIds.includes(account.account_id) && isSourceAccountLoginReady(account))
                    .map(account => account.account_id);
                availableChannelMap[channel.channel_id] = Array.from(new Set(usableAccountIds));
                availableChannelTypeMap[channel.channel_id] = channel.channel_type || 'custom';
            });

        const rawEntries = Array.isArray(safeCfg.enabled_source_channels) ? safeCfg.enabled_source_channels : [];
        const normalizedEntries = [];
        const removedChannels = [];
        const removedAccounts = [];

        rawEntries.forEach(item => {
            if (!item || !item.channel_id) return;
            const channelId = item.channel_id;
            const availableAccountIds = availableChannelMap[channelId];
            if (!availableAccountIds) {
                removedChannels.push(channelId);
                return;
            }
            const requestedAccountIds = Array.isArray(item.account_ids) ? item.account_ids.filter(Boolean) : [];
            const nextAccountIds = requestedAccountIds.filter(accountId => availableAccountIds.includes(accountId));
            const droppedAccountIds = requestedAccountIds.filter(accountId => !nextAccountIds.includes(accountId));
            if (droppedAccountIds.length > 0) {
                removedAccounts.push(`${channelId}: ${droppedAccountIds.join(', ')}`);
            }
            if (nextAccountIds.length > 0) {
                normalizedEntries.push({
                    channel_id: channelId,
                    enabled: item.enabled !== false,
                    account_ids: Array.from(new Set(nextAccountIds)),
                });
            }
        });

        const noticeParts = [];
        if (removedChannels.length > 0) {
            noticeParts.push(`已自动移除失效渠道：${removedChannels.join('、')}`);
        }
        if (removedAccounts.length > 0) {
            noticeParts.push(`已自动移除不可用账号：${removedAccounts.join('；')}`);
        }

        const rawFilterEntries = Array.isArray(safeCfg.channel_search_filters) ? safeCfg.channel_search_filters : [];
        const rawFilterMap = {};
        rawFilterEntries.forEach(item => {
            if (!item || !item.channel_id || !availableChannelTypeMap[item.channel_id]) return;
            rawFilterMap[item.channel_id] = item.filters && typeof item.filters === 'object' ? item.filters : {};
        });
        const normalizedFilterEntries = orderedChannelIds.map(channelId => {
            const supportedFilters = getSupportedChannelSearchFilters(availableChannelTypeMap[channelId]);
            const rawFilters = rawFilterMap[channelId] || {};
            return {
                channel_id: channelId,
                filters: supportedFilters.reduce((acc, filter) => {
                    acc[filter.key] = !!rawFilters[filter.key];
                    return acc;
                }, {})
            };
        });

        return {
            normalized: {
                ...safeCfg,
                source_channel_selection_mode: selectionMode,
                enabled_source_channels: normalizedEntries,
                channel_search_filters: normalizedFilterEntries,
            },
            adjustmentNotice: noticeParts.join('；'),
        };
    };
    const activeSourceChannelId = configs.source_channels?.active_channel_id || currentSourceChannels[0]?.channel_id || 'ali1688';
    const currentSourceChannel = currentSourceChannels.find(item => item.channel_id === activeSourceChannelId) || currentSourceChannels[0] || createSourceChannel(1);
    const currentSourceChannelCapabilities = getSourceChannelCapabilities(currentSourceChannel?.channel_type);
    const currentSourceAccounts = currentSourceChannel?.accounts || [];
    const isSourceAccountLoginReady = (account) => {
        const report = account?.session_report || {};
        if (report?.is_logged_in || report?.is_usable) {
            return true;
        }
        const statusText = report?.status_text || '';
        const runtimeState = report?.meta?.state || '';
        const hasKnownIdentity = !!(report?.account_name || report?.last_checked_at || report?.meta?.cached_account_name_at);
        return hasKnownIdentity && (
            runtimeState === 'profile_locked'
            || statusText.includes('浏览器配置被占用')
        );
    };
    const loginReadySourceAccounts = currentSourceAccounts.filter(isSourceAccountLoginReady);
    const activeSourceAccountIds = (() => {
        const availableIds = currentSourceAccounts.map(item => item.account_id);
        const rawIds = Array.isArray(currentSourceChannel?.active_account_ids)
            ? currentSourceChannel.active_account_ids
            : (currentSourceChannel?.active_account_id ? [currentSourceChannel.active_account_id] : []);
        return rawIds.filter(id => availableIds.includes(id));
    })();
    const [selectedSourceAccountId, setSelectedSourceAccountId] = useState('');
    const currentSourceAccountId = selectedSourceAccountId && currentSourceAccounts.some(item => item.account_id === selectedSourceAccountId)
        ? selectedSourceAccountId
        : activeSourceAccountIds[0] || currentSourceAccounts[0]?.account_id || '';
    const currentSourceAccount = currentSourceAccounts.find(item => item.account_id === currentSourceAccountId) || currentSourceAccounts[0] || createSourceChannelAccount(currentSourceChannel?.channel_id || 'ali1688', 1);
    const currentSourceRealtimeName = currentSourceAccount?.session_report?.account_name || '';
    const currentSourceLabel = currentSourceAccount?.label || '';
    const getSourceAccountDisplayName = (account, fallbackIndex) => {
        const reportName = account?.session_report?.account_name || '';
        const fallbackName = fallbackIndex ? `渠道账号 ${fallbackIndex}` : '';
        return reportName || account?.label || account?.account_id || fallbackName;
    };
    const currentSourceDisplayName = getSourceAccountDisplayName(currentSourceAccount);
    const currentSourceNameSource = currentSourceAccount?.session_report?.account_name_source || currentSourceAccount?.session_report?.source || '';
    const isSourceNameFallback = !currentSourceRealtimeName && !!currentSourceLabel;
    const visibleActiveSourceAccountIds = activeSourceAccountIds.filter(id => loginReadySourceAccounts.some(account => account.account_id === id));
    const normalizedCrawlChannelSelections = Array.isArray(crawlConfig.enabled_source_channels)
        ? crawlConfig.enabled_source_channels.filter(item => item && item.channel_id)
        : [];
    const crawlChannelSelectionMap = normalizedCrawlChannelSelections.reduce((acc, item) => {
        acc[item.channel_id] = {
            channel_id: item.channel_id,
            enabled: item.enabled !== false,
            account_ids: Array.isArray(item.account_ids) ? item.account_ids : [],
        };
        return acc;
    }, {});
    const crawlAvailableChannels = currentSourceChannels
        .filter(channel => channel?.enabled !== false)
        .map(channel => {
            const rawActiveIds = Array.isArray(channel?.active_account_ids)
                ? channel.active_account_ids
                : (channel?.active_account_id ? [channel.active_account_id] : []);
            const loginReadyActiveAccounts = (channel?.accounts || []).filter(account => (
                rawActiveIds.includes(account.account_id) && isSourceAccountLoginReady(account)
            ));
            return {
                ...channel,
                crawl_accounts: loginReadyActiveAccounts,
            };
        });
    const effectiveSelectedCrawlChannelId = (
        selectedCrawlChannelId && crawlAvailableChannels.some(item => item.channel_id === selectedCrawlChannelId)
            ? selectedCrawlChannelId
            : crawlAvailableChannels.some(item => item.channel_id === activeSourceChannelId)
                ? activeSourceChannelId
                : normalizedCrawlChannelSelections.find(item => crawlAvailableChannels.some(channel => channel.channel_id === item.channel_id))?.channel_id
                || crawlAvailableChannels[0]?.channel_id
                || ''
    );
    const currentCrawlChannel = crawlAvailableChannels.find(item => item.channel_id === effectiveSelectedCrawlChannelId) || crawlAvailableChannels[0] || null;
    const activeSourceChannelInCrawlPool = crawlAvailableChannels.find(item => item.channel_id === activeSourceChannelId) || null;
    const isCrawlEditorFollowingActiveSourceChannel = !!(
        currentCrawlChannel
        && activeSourceChannelInCrawlPool
        && currentCrawlChannel.channel_id === activeSourceChannelInCrawlPool.channel_id
    );
    const currentCrawlSelection = currentCrawlChannel ? (crawlChannelSelectionMap[currentCrawlChannel.channel_id] || null) : null;
    const currentCrawlSelectedAccountIds = currentCrawlSelection?.enabled
        ? (currentCrawlSelection.account_ids || [])
        : [];
    const crawlChannelSearchFilterMap = Array.isArray(crawlConfig.channel_search_filters)
        ? crawlConfig.channel_search_filters.reduce((acc, item) => {
            if (item?.channel_id) {
                acc[item.channel_id] = item.filters && typeof item.filters === 'object' ? item.filters : {};
            }
            return acc;
        }, {})
        : {};
    const currentCrawlFilterMeta = getSupportedChannelSearchFilters(currentCrawlChannel?.channel_type);
    const currentCrawlFilterGroups = currentCrawlFilterMeta.reduce((acc, item) => {
        const groupName = item.group || '其他';
        if (!acc[groupName]) acc[groupName] = [];
        acc[groupName].push(item);
        return acc;
    }, {});
    const currentCrawlFilterValues = currentCrawlChannel
        ? (crawlChannelSearchFilterMap[currentCrawlChannel.channel_id] || {})
        : {};
    const hasAnyCrawlAccountSelection = normalizedCrawlChannelSelections.some(item => (
        item?.enabled !== false && Array.isArray(item.account_ids) && item.account_ids.length > 0
    ));
    const isCustomCrawlSelectionMode = crawlConfig.source_channel_selection_mode === 'custom_selected';
    const isCrawlSelectionMissing = isCustomCrawlSelectionMode && crawlAvailableChannels.length > 0 && !hasAnyCrawlAccountSelection;
    const getSourceSessionVisualState = (report) => {
        const statusText = report?.status_text || '';
        const isLoggedIn = !!(report?.is_logged_in || report?.is_usable);
        const requiresVerification = !!report?.requires_verification
            || statusText.includes('风控')
            || statusText.includes('滑块')
            || statusText.includes('验证');

        if (requiresVerification) {
            return {
                dotClass: 'bg-warning',
                textClass: 'text-warning',
                title: statusText || '需完成验证'
            };
        }
        if (isLoggedIn) {
            return {
                dotClass: 'bg-success',
                textClass: 'text-success',
                title: statusText || '登录正常'
            };
        }
        if (report?.last_checked_at) {
            return {
                dotClass: 'bg-error',
                textClass: 'text-error',
                title: statusText || '登录异常'
            };
        }
        return {
            dotClass: 'bg-secondary/60',
            textClass: 'text-secondary',
            title: statusText || '未检测'
        };
    };
    const currentSourceSessionState = getSourceSessionVisualState(currentSourceAccount?.session_report);
    const currentSourceSessionLoggedIn = !!(currentSourceAccount?.session_report?.is_logged_in || currentSourceAccount?.session_report?.is_usable);
    const currentSourceStatusTextForDisplay = isSourceChannelLoggingIn
        ? '等待扫码登录'
        : (currentSourceAccount?.session_report?.status_text || '未检测');
    const currentSourceStatusDotClassForDisplay = isSourceChannelLoggingIn
        ? 'bg-primary'
        : currentSourceSessionState.dotClass;
    const currentSourceStatusTextClassForDisplay = isSourceChannelLoggingIn
        ? 'text-primary'
        : currentSourceSessionState.textClass;
    const selectableChipClass = (isActive) => (
        `flex items-center gap-1 rounded-full border px-3 py-1.5 text-[11px] font-sans transition-all duration-200 ${
            isActive
                ? 'border-primary bg-primary text-on-primary shadow-[0_0_0_1px_rgba(197,86,16,0.32),0_12px_24px_rgba(197,86,16,0.28)]'
                : 'border-border-hairline bg-surface-container-low text-secondary hover:border-primary/25 hover:bg-primary/[0.05] hover:text-on-surface'
        }`
    );
    const selectableChipActionClass = (isActive) => (
        `font-semibold cursor-pointer transition-colors ${isActive ? 'text-on-primary' : 'text-secondary hover:text-on-surface'}`
    );

    const setCurrentOpenapiAccount = (updater) => {
        setConfigs(prev => {
            const openapi = prev.openapi || {};
            const accounts = openapi.accounts || [];
            const activeId = openapi.active_account_id || accounts[0]?.id;
            return {
                ...prev,
                openapi: {
                    ...openapi,
                    accounts: accounts.map(account => {
                        if (account.id !== activeId) return account;
                        return typeof updater === 'function' ? updater(account) : { ...account, ...updater };
                    })
                }
            };
        });
    };

    const setCurrentSourceChannel = (updater) => {
        setConfigs(prev => {
            const sourceChannels = prev.source_channels || {};
            const channels = sourceChannels.channels || [];
            const activeChannelId = sourceChannels.active_channel_id || channels[0]?.channel_id;
            return {
                ...prev,
                source_channels: {
                    ...sourceChannels,
                    channels: channels.map(channel => {
                        if (channel.channel_id !== activeChannelId) return channel;
                        return typeof updater === 'function' ? updater(channel) : { ...channel, ...updater };
                    })
                }
            };
        });
    };

    const setCurrentSourceAccount = (updater) => {
        setConfigs(prev => {
            const sourceChannels = prev.source_channels || {};
            const channels = sourceChannels.channels || [];
            const activeChannelId = sourceChannels.active_channel_id || channels[0]?.channel_id;
            return {
                ...prev,
                source_channels: {
                    ...sourceChannels,
                    channels: channels.map(channel => {
                        if (channel.channel_id !== activeChannelId) return channel;
                        return {
                            ...channel,
                            accounts: (channel.accounts || []).map(account => {
                                if (account.account_id !== currentSourceAccountId) return account;
                                return typeof updater === 'function' ? updater(account) : { ...account, ...updater };
                            })
                        };
                    })
                }
            };
        });
    };

    const updateSourceAccountByIds = (channelId, accountId, updater) => {
        setConfigs(prev => {
            const sourceChannels = prev.source_channels || {};
            const channels = sourceChannels.channels || [];
            return {
                ...prev,
                source_channels: {
                    ...sourceChannels,
                    channels: channels.map(channel => {
                        if (channel.channel_id !== channelId) return channel;
                        return {
                            ...channel,
                            accounts: (channel.accounts || []).map(account => {
                                if (account.account_id !== accountId) return account;
                                return typeof updater === 'function' ? updater(account) : { ...account, ...updater };
                            })
                        };
                    })
                }
            };
        });
    };

    const fetchXianyuLoginStatus = async () => {
        try {
            const accountId = activeOpenapiAccountId || '';
            if (!persistedOpenapiAccountIds.includes(accountId)) {
                setXianyuLoginStatus({ account_name: '', is_usable: false });
                setIsXianyuLoggingIn(false);
                return;
            }
            const resp = await fetch(`/api/system/xianyu_login_status?account_id=${encodeURIComponent(accountId)}`);
            const res = await resp.json();
            if (res.status === 'success') {
                setXianyuLoginStatus(res.data.report || {});
                setIsXianyuLoggingIn(res.data.is_logging_in || false);
            }
        } catch (err) {
            console.error("Failed to fetch Xianyu login status:", err);
        }
    };

    const handleXianyuLoginTrigger = async () => {
        try {
            if (!persistedOpenapiAccountIds.includes(activeOpenapiAccountId)) {
                alert("请先保存当前账号配置，再执行登录授权。");
                return;
            }
            xianyuLoginFlowRef.current = true;
            setIsXianyuLoggingIn(true);
            const resp = await fetch('/api/system/xianyu_login_trigger', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_id: activeOpenapiAccountId })
            });
            const res = await resp.json();
            if (res.status === 'success') {
                setMessage(res.msg || "已启动闲鱼登录，请完成手机扫码");
                setError(null);
                fetchXianyuLoginStatus();
            } else {
                alert(res.msg || "启动登录失败");
                xianyuLoginFlowRef.current = false;
                setIsXianyuLoggingIn(false);
            }
        } catch (err) {
            console.error("Trigger login failed:", err);
            xianyuLoginFlowRef.current = false;
            setIsXianyuLoggingIn(false);
        }
    };

    const handleOpenapiAccountSwitch = (accountId) => {
        setConfigs(prev => ({
            ...prev,
            openapi: {
                ...prev.openapi,
                active_account_id: accountId
            }
        }));
        setMessage(null);
        setError(null);
    };

    const handleSourceChannelSwitch = (channelId) => {
        setConfigs(prev => ({
            ...prev,
            source_channels: {
                ...prev.source_channels,
                active_channel_id: channelId
            }
        }));
        setSelectedCrawlChannelId(channelId);
        setMessage(null);
        setError(null);
    };

    const handleAddSourceChannel = () => {
        setConfigs(prev => {
            const channels = prev.source_channels?.channels || [];
            const nextChannel = createSourceChannel(channels.length + 1, 'custom');
            return {
                ...prev,
                source_channels: {
                    active_channel_id: nextChannel.channel_id,
                    channels: [...channels, nextChannel]
                }
            };
        });
        setSelectedCrawlChannelId('');
    };

    const handleRemoveSourceChannel = (channelId) => {
        const nextChannels = currentSourceChannels.filter(item => item.channel_id !== channelId);
        const fallbackChannel = nextChannels[0]?.channel_id || '';
        const nextActiveId = nextChannels.some(item => item.channel_id === activeSourceChannelId)
            ? activeSourceChannelId
            : fallbackChannel;
        setConfigs(prev => {
            const channels = (prev.source_channels?.channels || []).filter(item => item.channel_id !== channelId);
            const nextChannels = channels.length ? channels : [createSourceChannel(1)];
            const nextActiveId = nextChannels.some(item => item.channel_id === prev.source_channels?.active_channel_id)
                ? prev.source_channels.active_channel_id
                : nextChannels[0].channel_id;
            return {
                ...prev,
                source_channels: {
                    active_channel_id: nextActiveId,
                    channels: nextChannels
                }
            };
        });
        if (selectedCrawlChannelId === channelId) {
            setSelectedCrawlChannelId(nextActiveId);
        }
    };

    const handleAddSourceAccount = () => {
        const baseChannelId = currentSourceChannel?.channel_id || 'ali1688';
        const nextIndex = (currentSourceAccounts || []).length + 1;
        const nextAccount = createSourceChannelAccount(baseChannelId, nextIndex);
        setCurrentSourceChannel(prev => {
            const accounts = prev.accounts || [];
            return {
                ...prev,
                accounts: [...accounts, nextAccount]
            };
        });
        setSelectedSourceAccountId(nextAccount.account_id);
    };

    const handleRemoveSourceAccount = (accountId) => {
        setCurrentSourceChannel(prev => {
            const accounts = (prev.accounts || []).filter(item => item.account_id !== accountId);
            const nextAccounts = accounts.length ? accounts : [createSourceChannelAccount(prev.channel_id, 1)];
            const nextLoginReadyAccounts = nextAccounts.filter(isSourceAccountLoginReady);
            const nextActiveAccountIds = (Array.isArray(prev.active_account_ids) ? prev.active_account_ids : (prev.active_account_id ? [prev.active_account_id] : []))
                .filter(id => id !== accountId && nextLoginReadyAccounts.some(item => item.account_id === id));
            if (nextActiveAccountIds.length === 0 && nextLoginReadyAccounts[0]?.account_id) {
                nextActiveAccountIds.push(nextLoginReadyAccounts[0].account_id);
            }
            return {
                ...prev,
                active_account_ids: nextActiveAccountIds,
                active_account_id: nextActiveAccountIds[0] || '',
                accounts: nextAccounts
            };
        });
        setSelectedSourceAccountId(prev => (prev === accountId ? '' : prev));
    };

    const handleSourceAccountSwitch = (accountId) => {
        setSelectedSourceAccountId(accountId);
    };

    const handleSourceActiveAccountToggle = (accountId, checked) => {
        setCurrentSourceChannel(prev => {
            const accounts = prev.accounts || [];
            const loginReadyAccounts = accounts.filter(isSourceAccountLoginReady);
            if (!loginReadyAccounts.some(account => account.account_id === accountId)) {
                return prev;
            }
            let nextActiveAccountIds = Array.isArray(prev.active_account_ids) ? [...prev.active_account_ids] : (prev.active_account_id ? [prev.active_account_id] : []);
            nextActiveAccountIds = nextActiveAccountIds.filter(id => loginReadyAccounts.some(item => item.account_id === id));
            if (checked) {
                if (!nextActiveAccountIds.includes(accountId)) {
                    nextActiveAccountIds.push(accountId);
                }
            } else {
                nextActiveAccountIds = nextActiveAccountIds.filter(id => id !== accountId);
            }
            if (nextActiveAccountIds.length === 0 && loginReadyAccounts[0]?.account_id) {
                nextActiveAccountIds = [loginReadyAccounts[0].account_id];
            }
            return {
                ...prev,
                active_account_ids: nextActiveAccountIds,
                active_account_id: nextActiveAccountIds[0] || ''
            };
        });
    };

    const upsertCrawlChannelSelection = (channelId, nextAccountIds) => {
        setCrawlConfig(prev => {
            const cleanedAccountIds = Array.from(new Set((nextAccountIds || []).filter(Boolean)));
            const currentEntries = Array.isArray(prev.enabled_source_channels) ? [...prev.enabled_source_channels] : [];
            const nextEntries = currentEntries.filter(item => item?.channel_id !== channelId);
            if (cleanedAccountIds.length > 0) {
                nextEntries.push({
                    channel_id: channelId,
                    enabled: true,
                    account_ids: cleanedAccountIds,
                });
            }
            return {
                ...prev,
                source_channel_selection_mode: 'custom_selected',
                enabled_source_channels: nextEntries,
            };
        });
    };

    const handleCrawlChannelSwitch = (channelId) => {
        setSelectedCrawlChannelId(channelId);
    };

    const handleCrawlChannelUseActiveAccounts = (channelId) => {
        const channel = crawlAvailableChannels.find(item => item.channel_id === channelId);
        if (!channel) return;
        const nextAccountIds = (channel.crawl_accounts || []).map(item => item.account_id);
        setCrawlSelectionAdjustmentNotice('');
        lastCrawlSelectionAdjustmentRef.current = '';
        upsertCrawlChannelSelection(channelId, nextAccountIds);
        setSelectedCrawlChannelId(channelId);
    };

    const handleCrawlAccountToggle = (channelId, accountId, checked) => {
        const channel = crawlAvailableChannels.find(item => item.channel_id === channelId);
        if (!channel) return;
        const selectableIds = (channel.crawl_accounts || []).map(item => item.account_id);
        if (!selectableIds.includes(accountId)) return;
        const currentSelectedIds = (crawlChannelSelectionMap[channelId]?.account_ids || []).filter(id => selectableIds.includes(id));
        let nextSelectedIds = [...currentSelectedIds];
        if (checked) {
            if (!nextSelectedIds.includes(accountId)) {
                nextSelectedIds.push(accountId);
            }
        } else {
            nextSelectedIds = nextSelectedIds.filter(id => id !== accountId);
        }
        setCrawlSelectionAdjustmentNotice('');
        lastCrawlSelectionAdjustmentRef.current = '';
        upsertCrawlChannelSelection(channelId, nextSelectedIds);
        setSelectedCrawlChannelId(channelId);
    };

    const upsertCrawlChannelSearchFilters = (channelId, updater) => {
        const channel = currentSourceChannels.find(item => item.channel_id === channelId);
        if (!channel) return;
        const supportedFilters = getSupportedChannelSearchFilters(channel.channel_type);
        if (supportedFilters.length === 0) return;

        setCrawlConfig(prev => {
            const currentEntries = Array.isArray(prev.channel_search_filters) ? [...prev.channel_search_filters] : [];
            const existing = currentEntries.find(item => item?.channel_id === channelId);
            const baseFilters = supportedFilters.reduce((acc, filter) => {
                acc[filter.key] = !!existing?.filters?.[filter.key];
                return acc;
            }, {});
            const rawNextFilters = typeof updater === 'function' ? updater(baseFilters) : (updater || baseFilters);
            const normalizedFilters = supportedFilters.reduce((acc, filter) => {
                acc[filter.key] = !!rawNextFilters[filter.key];
                return acc;
            }, {});
            const nextEntries = currentEntries.filter(item => item?.channel_id !== channelId);
            nextEntries.push({
                channel_id: channelId,
                filters: normalizedFilters,
            });
            return {
                ...prev,
                channel_search_filters: nextEntries,
            };
        });
    };

    const handleCrawlSearchFilterToggle = (channelId, filterKey, checked) => {
        upsertCrawlChannelSearchFilters(channelId, currentFilters => ({
            ...currentFilters,
            [filterKey]: checked,
        }));
        setSelectedCrawlChannelId(channelId);
    };

    const handleCheckSourceChannelStatus = async () => {
        if (!currentSourceChannel?.channel_id || !currentSourceAccount?.account_id) {
            setError('当前渠道账号配置不完整，无法检测状态');
            return;
        }
        if (isSourceChannelLoggingIn) {
            setError('当前账号正在进行 1688 登录，请先完成或关闭登录窗口后再检测状态');
            return;
        }
        setIsCheckingSourceChannelStatus(true);
        try {
            const resp = await fetch('/api/system/source_channel_status/check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    channel_id: currentSourceChannel.channel_id,
                    account_id: currentSourceAccount.account_id,
                    channel: {
                        channel_id: currentSourceChannel.channel_id,
                        channel_type: currentSourceChannel.channel_type,
                        label: currentSourceChannel.label
                    },
                    account: {
                        account_id: currentSourceAccount.account_id,
                        label: currentSourceAccount.label,
                        enabled: currentSourceAccount.enabled !== false,
                        notes: currentSourceAccount.notes
                    }
                })
            });
            const res = await resp.json();
            if (res.status === 'success') {
                updateSourceAccountByIds(
                    res.data.channel_id || currentSourceChannel.channel_id,
                    res.data.account_id || currentSourceAccount.account_id,
                    prev => ({
                        ...prev,
                        session_report: res.data.report || prev.session_report
                    })
                );
                setMessage('货源渠道账号状态检测完成');
                setError(null);
            } else {
                setError(res.msg || '检测渠道账号状态失败');
            }
        } catch (err) {
            setError('网络连接异常，检测状态失败');
        } finally {
            setIsCheckingSourceChannelStatus(false);
        }
    };

    const fetchSourceChannelLoginStatus = async () => {
        try {
            if (!currentSourceChannel?.channel_id || !currentSourceAccount?.account_id) {
                setIsSourceChannelLoggingIn(false);
                setSourceChannelLoginResult('');
                setSourceChannelLoginResultFinishedAt('');
                setSourceChannelLoginErrorMessage('');
                return;
            }
            if (!currentSourceChannelCapabilities.supportsSessionState) {
                setIsSourceChannelLoggingIn(false);
                setSourceChannelLoginResult('');
                setSourceChannelLoginResultFinishedAt('');
                setSourceChannelLoginErrorMessage('');
                return;
            }
            const url = `/api/system/source_channel_login_status?channel_id=${encodeURIComponent(currentSourceChannel.channel_id)}&account_id=${encodeURIComponent(currentSourceAccount.account_id)}`;
            const resp = await fetch(url);
            const res = await resp.json();
            if (res.status === 'success') {
                updateSourceAccountByIds(
                    res.data.channel_id || currentSourceChannel.channel_id,
                    res.data.account_id || currentSourceAccount.account_id,
                    prev => ({
                        ...prev,
                        session_report: res.data.report || prev.session_report
                    })
                );
                setIsSourceChannelLoggingIn(res.data.is_logging_in || false);
                setSourceChannelLoginResult(res.data.login_result || '');
                setSourceChannelLoginResultFinishedAt(res.data.login_result_finished_at || '');
                setSourceChannelLoginErrorMessage(res.data.err_msg || '');
            }
        } catch (err) {
            console.error("Failed to fetch source channel login status:", err);
        }
    };

    const handleSourceChannelLoginTrigger = async () => {
        try {
            if (!currentSourceChannel?.channel_id || !currentSourceAccount?.account_id) {
                setError('当前渠道账号配置不完整，无法执行登录');
                return;
            }
            setMessage(null);
            setError(null);
            sourceChannelLoginFlowRef.current = true;
            sourceChannelLoginStartedAtRef.current = new Date().toISOString();
            sourceChannelLoginHandledAtRef.current = '';
            setIsSourceChannelLoggingIn(true);
            setSourceChannelLoginResult('');
            setSourceChannelLoginResultFinishedAt('');
            setSourceChannelLoginErrorMessage('');
            const resp = await fetch('/api/system/source_channel_login_trigger', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    channel_id: currentSourceChannel.channel_id,
                    account_id: currentSourceAccount.account_id,
                    channel: {
                        channel_id: currentSourceChannel.channel_id,
                        channel_type: currentSourceChannel.channel_type,
                        label: currentSourceChannel.label
                    },
                    account: {
                        account_id: currentSourceAccount.account_id,
                        label: currentSourceAccount.label,
                        enabled: currentSourceAccount.enabled !== false,
                        notes: currentSourceAccount.notes
                    }
                })
            });
            const res = await resp.json();
            if (res.status === 'success') {
                setMessage(res.msg || '已启动渠道账号登录浏览器，请完成扫码登录');
                setError(null);
                fetchSourceChannelLoginStatus();
            } else {
                setError(res.msg || '启动渠道账号登录失败');
                sourceChannelLoginFlowRef.current = false;
                sourceChannelLoginStartedAtRef.current = '';
                sourceChannelLoginHandledAtRef.current = '';
                setIsSourceChannelLoggingIn(false);
                setSourceChannelLoginResult('failed');
            }
        } catch (err) {
            console.error("Trigger source channel login failed:", err);
            setError('网络连接异常，启动渠道账号登录失败');
            sourceChannelLoginFlowRef.current = false;
            sourceChannelLoginStartedAtRef.current = '';
            sourceChannelLoginHandledAtRef.current = '';
            setIsSourceChannelLoggingIn(false);
            setSourceChannelLoginResult('failed');
        }
    };

    const handleAddOpenapiAccount = () => {
        setConfigs(prev => {
            const accounts = prev.openapi?.accounts || [];
            const nextAccount = createOpenapiAccount(accounts.length + 1);
            return {
                ...prev,
                openapi: {
                    ...prev.openapi,
                    active_account_id: nextAccount.id,
                    accounts: [...accounts, nextAccount]
                }
            };
        });
        setXianyuLoginStatus(null);
    };

    const handleRemoveOpenapiAccount = (accountId) => {
        setConfigs(prev => {
            const accounts = (prev.openapi?.accounts || []).filter(item => item.id !== accountId);
            const nextAccounts = accounts.length ? accounts : [createOpenapiAccount(1)];
            const nextActiveId = nextAccounts.some(item => item.id === prev.openapi?.active_account_id)
                ? prev.openapi.active_account_id
                : nextAccounts[0].id;
            return {
                ...prev,
                openapi: {
                    ...prev.openapi,
                    active_account_id: nextActiveId,
                    accounts: nextAccounts
                }
            };
        });
        setMessage(null);
        setError(null);
        setXianyuLoginStatus(null);
    };

    // 异步加载基础省市区和类目数据
    const initMetadata = async (currentCatId) => {
        try {
            // 1. 获取全量省市区
            const regResp = await fetch('/api/system/regions');
            const regRes = await regResp.json();
            let loadedRegions = [];
            if (regRes.status === 'success') {
                loadedRegions = regRes.data || [];
                setRegions(loadedRegions);
            }

            // 2. 获取大类列表和默认类目列表
            const catResp = await fetch('/api/system/openapi_categories');
            const catRes = await catResp.json();
            if (catRes.status === 'success') {
                setCatGroups(catRes.data.groups || []);
                setCatList(catRes.data.categories || []);
            }

            // 3. 如果当前存在 channel_cat_id，反查该 ID 的大类和类目名以便下拉框回显
            if (currentCatId) {
                const queryResp = await fetch(`/api/system/openapi_categories?cat_id=${encodeURIComponent(currentCatId)}`);
                const queryRes = await queryResp.json();
                if (queryRes.status === 'success' && queryRes.data.categories && queryRes.data.categories.length > 0) {
                    const matchedCat = queryRes.data.categories[0];
                    setSelectedCat(currentCatId);
                    setSelectedGroup(matchedCat.group || "");
                    setIsCustomCat(false);
                    
                    // 补充该大类下的子类目列表到下拉列表中
                    if (matchedCat.group) {
                        const subResp = await fetch(`/api/system/openapi_categories?group=${encodeURIComponent(matchedCat.group)}`);
                        const subRes = await subResp.json();
                        if (subRes.status === 'success') {
                            setCatList(subRes.data.categories || []);
                        }
                    }
                } else {
                    setSelectedCat("custom");
                    setIsCustomCat(true);
                }
            } else {
                if (catRes.status === 'success' && catRes.data.categories && catRes.data.categories.length > 0) {
                    setSelectedCat(catRes.data.categories[0].id);
                    setSelectedGroup(catRes.data.categories[0].group || "");
                }
            }

            return loadedRegions;
        } catch (err) {
            console.error("Failed to initialize metadata:", err);
            return [];
        }
    };

    const searchCategories = async (groupName, queryStr) => {
        try {
            let url = '/api/system/openapi_categories';
            const params = [];
            if (groupName) params.push(`group=${encodeURIComponent(groupName)}`);
            if (queryStr) params.push(`query=${encodeURIComponent(queryStr)}`);
            if (params.length > 0) {
                url += '?' + params.join('&');
            }
            
            const resp = await fetch(url);
            const res = await resp.json();
            if (res.status === 'success') {
                setCatList(res.data.categories || []);
            }
        } catch (err) {
            console.error("Failed to query categories:", err);
        }
    };

    const handleGroupChange = (groupName) => {
        setSelectedGroup(groupName);
        searchCategories(groupName, catQuery);
    };

    const handleQueryChange = (val) => {
        setCatQuery(val);
        searchCategories(selectedGroup, val);
    };

    const handleProvChange = (pCode) => {
        setSelectedProv(pCode);
        const prov = regions.find(p => p.code.toString() === pCode);
        if (prov && prov.cities.length > 0) {
            const firstCity = prov.cities[0];
            setSelectedCity(firstCity.code.toString());
            if (firstCity.districts.length > 0) {
                const firstDist = firstCity.districts[0];
                setSelectedDist(firstDist.code.toString());
                
                setCurrentOpenapiAccount(prev => ({
                    ...prev,
                    default_config: {
                        ...prev.default_config,
                        province: prov.code,
                        city: firstCity.code,
                        district: firstDist.code
                    }
                }));
            }
        }
    };

    const handleCityChange = (cCode) => {
        setSelectedCity(cCode);
        const prov = regions.find(p => p.code.toString() === selectedProv);
        const city = prov ? prov.cities.find(c => c.code.toString() === cCode) : null;
        if (city && city.districts.length > 0) {
            const firstDist = city.districts[0];
            setSelectedDist(firstDist.code.toString());
            
            setCurrentOpenapiAccount(prev => ({
                ...prev,
                default_config: {
                    ...prev.default_config,
                    city: city.code,
                    district: firstDist.code
                }
            }));
        }
    };

    const handleDistChange = (dCode) => {
        setSelectedDist(dCode);
        setCurrentOpenapiAccount(prev => ({
            ...prev,
            default_config: {
                ...prev.default_config,
                district: parseInt(dCode) || 0
            }
        }));
    };

    const handleCatChange = (catId) => {
        if (catId === "custom") {
            setIsCustomCat(true);
            setSelectedCat("custom");
        } else {
            setIsCustomCat(false);
            setSelectedCat(catId);
            setCurrentOpenapiAccount(prev => ({
                ...prev,
                default_config: {
                    ...prev.default_config,
                    channel_cat_id: catId
                }
            }));
        }
    };

    const handleCustomCatChange = (val) => {
        setCurrentOpenapiAccount(prev => ({
            ...prev,
            default_config: {
                ...prev.default_config,
                channel_cat_id: val
            }
        }));
    };

    const fetchConfigs = async ({ silent = false } = {}) => {
        try {
            if (!silent) {
                setLoading(true);
            }
            const resp = await fetch('/api/system/configs');
            const res = await resp.json();
            if (res.status === 'success') {
                const data = res.data;
                const rawOpenapi = data.openapi || {};
                const accounts = (rawOpenapi.accounts || []).map((account, idx) => ({
                    id: account.id || `account-${idx + 1}`,
                    name: account.name || `闲鱼账号 ${idx + 1}`,
                    base_url: account.base_url || 'https://open.goofish.pro',
                    appid: account.appid || '',
                    app_secret: account.app_secret || '',
                    show_secret: false,
                    state_file: account.state_file || '',
                    session_report: account.session_report || {},
                    default_config: {
                        user_name: account.default_config?.user_name || account.session_report?.account_name || '',
                        province: parseInt(account.default_config?.province) || 110000,
                        city: parseInt(account.default_config?.city) || 110100,
                        district: parseInt(account.default_config?.district) || 110101,
                        item_biz_type: parseInt(account.default_config?.item_biz_type) || 2,
                        sp_biz_type: parseInt(account.default_config?.sp_biz_type) || 2,
                        channel_cat_id: account.default_config?.channel_cat_id || '',
                        stuff_status: parseInt(account.default_config?.stuff_status) || 100,
                        express_fee: parseInt(account.default_config?.express_fee) || 0
                    }
                }));
                const openapiData = {
                    active_account_id: rawOpenapi.active_account_id || accounts[0]?.id || 'account-1',
                    accounts: accounts.length ? accounts : [createOpenapiAccount(1)]
                };
                const rawSourceChannels = data.source_channels || {};
                const sourceChannels = (rawSourceChannels.channels || []).map((channel, idx) => {
                    const accounts = (channel.accounts || []).map((account, accountIdx) => ({
                        account_id: account.account_id || `${channel.channel_id || 'channel'}-account-${accountIdx + 1}`,
                        label: account.label || `渠道账号 ${accountIdx + 1}`,
                        enabled: account.enabled !== false,
                        notes: account.notes || '',
                        session_report: account.session_report || {
                            is_usable: false,
                            is_logged_in: false,
                            requires_verification: false,
                            account_name: '',
                            status_text: '未检测',
                            last_checked_at: '',
                            error_message: '',
                            meta: {}
                        }
                    }));
                    const normalizedActiveAccountIds = (() => {
                        const availableIds = accounts.map(item => item.account_id);
                        const rawIds = Array.isArray(channel.active_account_ids)
                            ? channel.active_account_ids
                            : (channel.active_account_id ? [channel.active_account_id] : []);
                        const validIds = rawIds.filter(id => availableIds.includes(id));
                        if (validIds.length > 0) return validIds;
                        return accounts[0]?.account_id ? [accounts[0].account_id] : [];
                    })();
                    return {
                        channel_id: channel.channel_id || `source-channel-${idx + 1}`,
                        channel_type: channel.channel_type || 'custom',
                        label: channel.label || `货源渠道 ${idx + 1}`,
                        enabled: channel.enabled !== false,
                        active_account_ids: normalizedActiveAccountIds,
                        active_account_id: normalizedActiveAccountIds[0] || '',
                        accounts: accounts.length ? accounts : [createSourceChannelAccount(channel.channel_id || `source-channel-${idx + 1}`, 1)]
                    };
                });
                const sourceChannelsData = {
                    active_channel_id: rawSourceChannels.active_channel_id || sourceChannels[0]?.channel_id || 'ali1688',
                    channels: sourceChannels.length ? sourceChannels : [createSourceChannel(1)]
                };
                setConfigs({
                    openapi: openapiData,
                    source_channels: sourceChannelsData
                });
                setPersistedOpenapiAccountIds(openapiData.accounts.map(item => item.id));
                
                // 初始化加载动态元数据并在完成后回显示发货地址省市区
                const activeAccount = openapiData.accounts.find(item => item.id === openapiData.active_account_id) || openapiData.accounts[0];
                setXianyuLoginStatus(activeAccount?.session_report || {
                    account_name: activeAccount?.default_config?.user_name || '',
                    is_usable: false
                });
                await initMetadata(activeAccount?.default_config?.channel_cat_id);
                
                if (data.llm && data.llm.length > 0) {
                    const mapped = data.llm.map(item => ({
                        api_key: item.api_key || '',
                        base_url: item.base_url || '',
                        models_str: (item.models || []).join(', '),
                        is_collapsed: false
                    }));
                    setLlmList(mapped);
                } else {
                    setLlmList([{ api_key: '', base_url: '', models_str: '', is_collapsed: false }]);
                }

                if (data.crawl) {
                    setCrawlConfig({
                        source_limit_1688: parseInt(data.crawl.source_limit_1688) || 10,
                        gross_profit_rate: normalizeGrossProfitRate(data.crawl.gross_profit_rate),
                        source_filter_models: data.crawl.source_filter_models || [],
                        source_channel_selection_mode: data.crawl.source_channel_selection_mode || 'active_pool',
                        enabled_source_channels: Array.isArray(data.crawl.enabled_source_channels) ? data.crawl.enabled_source_channels : [],
                        channel_search_filters: Array.isArray(data.crawl.channel_search_filters) ? data.crawl.channel_search_filters : []
                    });
                }
                setCrawlSelectionAdjustmentNotice('');
                lastCrawlSelectionAdjustmentRef.current = '';
                setError(null);
            } else {
                setError(res.msg || '加载配置失败');
            }
        } catch (err) {
            setError('获取配置网络请求失败');
        } finally {
            if (!silent) {
                setLoading(false);
            }
        }
    };

    useEffect(() => {
        fetchConfigs();
    }, []);

    useEffect(() => {
        if (effectiveSelectedCrawlChannelId && effectiveSelectedCrawlChannelId !== selectedCrawlChannelId) {
            setSelectedCrawlChannelId(effectiveSelectedCrawlChannelId);
        }
    }, [effectiveSelectedCrawlChannelId, selectedCrawlChannelId]);

    useEffect(() => {
        const { normalized, adjustmentNotice } = normalizeLocalCrawlConfig(crawlConfig, currentSourceChannels);
        const currentSnapshot = JSON.stringify({
            source_channel_selection_mode: crawlConfig.source_channel_selection_mode,
            enabled_source_channels: crawlConfig.enabled_source_channels || [],
            channel_search_filters: crawlConfig.channel_search_filters || [],
        });
        const normalizedSnapshot = JSON.stringify({
            source_channel_selection_mode: normalized.source_channel_selection_mode,
            enabled_source_channels: normalized.enabled_source_channels || [],
            channel_search_filters: normalized.channel_search_filters || [],
        });

        if (currentSnapshot !== normalizedSnapshot) {
            setCrawlConfig(prev => ({
                ...prev,
                source_channel_selection_mode: normalized.source_channel_selection_mode,
                enabled_source_channels: normalized.enabled_source_channels,
                channel_search_filters: normalized.channel_search_filters,
            }));
        }

        if (adjustmentNotice && adjustmentNotice !== lastCrawlSelectionAdjustmentRef.current) {
            setCrawlSelectionAdjustmentNotice(adjustmentNotice);
            lastCrawlSelectionAdjustmentRef.current = adjustmentNotice;
        } else if (!adjustmentNotice && lastCrawlSelectionAdjustmentRef.current) {
            setCrawlSelectionAdjustmentNotice('');
            lastCrawlSelectionAdjustmentRef.current = '';
        }
    }, [crawlConfig, currentSourceChannels]);

    useEffect(() => {
        fetchXianyuLoginStatus();
        const pollInterval = isXianyuLoggingIn ? 1000 : 300000;
        const timer = setInterval(() => {
            fetchXianyuLoginStatus();
        }, pollInterval);

        return () => clearInterval(timer);
    }, [isXianyuLoggingIn, activeOpenapiAccountId, persistedOpenapiAccountIds.join('|')]);

    useEffect(() => {
        if (!currentSourceChannelCapabilities.supportsSessionState) {
            setIsSourceChannelLoggingIn(false);
            return undefined;
        }
        fetchSourceChannelLoginStatus();
        const pollInterval = isSourceChannelLoggingIn ? 1000 : 300000;
        const timer = setInterval(() => {
            fetchSourceChannelLoginStatus();
        }, pollInterval);

        return () => clearInterval(timer);
    }, [isSourceChannelLoggingIn, activeSourceChannelId, currentSourceAccountId, currentSourceChannelCapabilities.supportsSessionState]);

    useEffect(() => {
        if (!currentSourceAccountId) {
            setSelectedSourceAccountId('');
            return;
        }
        if (!selectedSourceAccountId || !currentSourceAccounts.some(item => item.account_id === selectedSourceAccountId)) {
            setSelectedSourceAccountId(currentSourceAccountId);
        }
    }, [currentSourceAccountId, selectedSourceAccountId, currentSourceAccounts]);

    useEffect(() => {
        const cfg = currentOpenapiAccount?.default_config;
        if (!cfg) return;

        initMetadata(cfg.channel_cat_id || '');
        if (regions.length === 0) return;

        const provCode = parseInt(cfg.province) || 0;
        const cityCode = parseInt(cfg.city) || 0;
        const distCode = parseInt(cfg.district) || 0;
        const foundProv = regions.find(p => p.code === provCode);
        const foundCity = foundProv ? foundProv.cities.find(c => c.code === cityCode) : null;
        const foundDist = foundCity ? foundCity.districts.find(d => d.code === distCode) : null;

        if (foundProv && foundCity && foundDist) {
            setSelectedProv(provCode.toString());
            setSelectedCity(cityCode.toString());
            setSelectedDist(distCode.toString());
            setIsCustomRegion(false);
        } else {
            setIsCustomRegion(true);
        }
        setSelectedCat(cfg.channel_cat_id || '');
    }, [currentOpenapiAccount?.id, regions.length]);

    useEffect(() => {
        const wasLoggingIn = prevXianyuLoggingInRef.current;
        const isNowUsable = !!xianyuLoginStatus?.is_usable;

        if (xianyuLoginFlowRef.current && wasLoggingIn && !isXianyuLoggingIn) {
            if (isNowUsable) {
                setMessage(null);
                setXianyuLoginSuccessMessage(`闲鱼账号登录成功，当前会话已同步${xianyuLoginStatus?.account_name ? `：${xianyuLoginStatus.account_name}` : ''}`);
                setError(null);
            } else {
                setMessage(null);
            }
            xianyuLoginFlowRef.current = false;
        }

        prevXianyuLoggingInRef.current = isXianyuLoggingIn;
    }, [isXianyuLoggingIn, xianyuLoginStatus]);

    useEffect(() => {
        const wasLoggingIn = prevSourceChannelLoggingInRef.current;
        const isNowLoggedIn = !!(currentSourceAccount?.session_report?.is_logged_in || currentSourceAccount?.session_report?.is_usable);
        const finishedAt = sourceChannelLoginResultFinishedAt || '';
        const startedAt = sourceChannelLoginStartedAtRef.current || '';
        const isFreshAttemptResult = !!finishedAt && (!startedAt || finishedAt >= startedAt);
        const isUnhandledResult = finishedAt && sourceChannelLoginHandledAtRef.current !== finishedAt;

        if (sourceChannelLoginFlowRef.current && wasLoggingIn && !isSourceChannelLoggingIn && isFreshAttemptResult && isUnhandledResult) {
            if (sourceChannelLoginResult === 'success' && isNowLoggedIn) {
                setMessage(`货源渠道账号登录成功，当前会话已同步${currentSourceDisplayName ? `：${currentSourceDisplayName}` : ''}`);
                setError(null);
            } else if (sourceChannelLoginResult === 'cancelled') {
                setMessage('你已关闭 1688 登录浏览器，本次登录已取消');
                setError(null);
            } else if (sourceChannelLoginResult === 'failed') {
                setMessage(null);
                setError(sourceChannelLoginErrorMessage || '货源渠道账号登录未完成或已取消');
            }
            sourceChannelLoginHandledAtRef.current = finishedAt;
            sourceChannelLoginFlowRef.current = false;
            sourceChannelLoginStartedAtRef.current = '';
        }

        prevSourceChannelLoggingInRef.current = isSourceChannelLoggingIn;
    }, [
        isSourceChannelLoggingIn,
        currentSourceAccount,
        currentSourceDisplayName,
        sourceChannelLoginResult,
        sourceChannelLoginResultFinishedAt,
        sourceChannelLoginErrorMessage
    ]);

    useEffect(() => {
        if (!message && !error) return undefined;

        if (noticeTimerRef.current) {
            clearTimeout(noticeTimerRef.current);
        }

        noticeTimerRef.current = setTimeout(() => {
            setMessage(null);
            setError(null);
            noticeTimerRef.current = null;
        }, error ? 3200 : 2200);

        return () => {
            if (noticeTimerRef.current) {
                clearTimeout(noticeTimerRef.current);
                noticeTimerRef.current = null;
            }
        };
    }, [message, error]);

    useEffect(() => {
        if (!xianyuLoginSuccessMessage) return undefined;

        if (xianyuLoginSuccessTimerRef.current) {
            clearTimeout(xianyuLoginSuccessTimerRef.current);
        }

        xianyuLoginSuccessTimerRef.current = setTimeout(() => {
            setXianyuLoginSuccessMessage(null);
            xianyuLoginSuccessTimerRef.current = null;
        }, 2200);

        return () => {
            if (xianyuLoginSuccessTimerRef.current) {
                clearTimeout(xianyuLoginSuccessTimerRef.current);
                xianyuLoginSuccessTimerRef.current = null;
            }
        };
    }, [xianyuLoginSuccessMessage]);

    const handleAddLlm = () => {
        setLlmList([...llmList, { api_key: '', base_url: '', models_str: '', is_collapsed: false }]);
    };

    const handleRemoveLlm = (index) => {
        const copy = [...llmList];
        copy.splice(index, 1);
        setLlmList(copy);
    };

    const handleLlmChange = (index, field, value) => {
        const copy = [...llmList];
        copy[index][field] = value;
        setLlmList(copy);
    };

    const handleToggleLlmCard = (index) => {
        const copy = [...llmList];
        copy[index] = {
            ...copy[index],
            is_collapsed: !copy[index]?.is_collapsed
        };
        setLlmList(copy);
    };

    const handleSave = async (e) => {
        e?.preventDefault?.();
        setSaving(true);
        setMessage(null);
        setError(null);

        const updatedLlm = llmList.map(item => ({
            api_key: item.api_key.trim ? item.api_key.trim() : item.api_key,
            base_url: item.base_url.trim ? item.base_url.trim() : item.base_url,
            models: item.models_str.split(',').map(m => m.trim()).filter(m => m)
        })).filter(item => item.api_key || item.base_url);

        if (updatedLlm.length === 0) {
            setError('请至少配置一个有效的大模型接口密钥');
            setSaving(false);
            return;
        }

        if (isCrawlSelectionMissing) {
            setError('当前已切换为“手动选择货源账号”，请至少为一个渠道勾选登录成功的激活账号后再保存。');
            setSaving(false);
            return;
        }

        const payload = {
            llm: updatedLlm,
            openapi: configs.openapi,
            crawl: crawlConfig,
            source_channels: configs.source_channels
        };

        try {
            const resp = await fetch('/api/system/configs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const res = await resp.json();
            if (res.status === 'success') {
                setMessage(res.msg || '配置已成功保存并同步！');
                fetchConfigs({ silent: true });
            } else {
                setError(res.msg || '保存配置失败');
            }
        } catch (err) {
            setError('网络连接异常，保存失败');
        } finally {
            setSaving(false);
        }
    };

    const renderCardActions = () => (
        <div className="border-t border-border-hairline/80 pt-4 flex justify-end gap-3">
            <button
                type="button"
                onClick={() => fetchConfigs()}
                className="px-5 py-2.5 bg-surface-container-high border border-border-hairline hover:bg-surface-container-highest text-on-surface rounded-xl font-sans text-xs font-semibold transition-colors active:scale-95 duration-100"
            >
                放弃更改
            </button>
            <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="px-6 py-2.5 bg-primary hover:bg-primary-hover disabled:bg-primary/50 text-on-primary rounded-xl font-sans text-xs font-bold transition-colors shadow-lg shadow-primary/20 flex items-center gap-1.5 active:scale-95 duration-100"
            >
                {saving ? (
                    <>
                        <span className="material-symbols-outlined text-[16px] animate-spin">autorenew</span>
                        <span>正在同步保存...</span>
                    </>
                ) : (
                    <>
                        <span className="material-symbols-outlined text-[16px]">save</span>
                        <span>保存并同步配置</span>
                    </>
                )}
            </button>
        </div>
    );

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-[50vh] gap-4">
                <span className="material-symbols-outlined text-[48px] text-primary animate-spin">autorenew</span>
                <p className="font-sans text-sm text-secondary">正在读取系统配置参数...</p>
            </div>
        );
    }

    const systemNotice = error
        ? {
            title: '操作失败',
            text: error,
            icon: 'error',
            iconWrapClass: 'bg-error/12 text-error',
            titleClass: 'text-red-700',
            textClass: 'text-red-600',
            panelClass: 'border border-error/20 bg-[radial-gradient(circle_at_top,_rgba(239,68,68,0.14),_transparent_62%),linear-gradient(135deg,#fff1f2,#ffffff_58%)]'
        }
        : message
            ? (() => {
                const isLoginLaunching = message.includes('已启动') && message.includes('登录');
                return {
                    title: isLoginLaunching ? '正在打开登录页' : '操作成功',
                    text: message,
                    icon: isLoginLaunching ? 'open_in_new' : 'check_circle',
                    iconWrapClass: isLoginLaunching ? 'bg-primary/12 text-primary' : 'bg-success/12 text-success',
                    titleClass: 'text-slate-900',
                    textClass: 'text-slate-600',
                    panelClass: isLoginLaunching
                        ? 'border border-primary/20 bg-[radial-gradient(circle_at_top,_rgba(197,86,16,0.14),_transparent_62%),linear-gradient(135deg,#fff7ed,#ffffff_58%)]'
                        : 'border border-success/20 bg-[radial-gradient(circle_at_top,_rgba(34,197,94,0.16),_transparent_62%),linear-gradient(135deg,#f0fdf4,#ffffff_58%)]'
                };
            })()
            : null;

    return (
        <div className="view-content max-w-4xl">
            {xianyuLoginSuccessMessage && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/72 backdrop-blur-sm px-6">
                    <div className="w-full max-w-lg rounded-[28px] border border-success/25 bg-white shadow-[0_32px_120px_rgba(15,23,42,0.35)] overflow-hidden animate-[fadeIn_180ms_ease-out]">
                        <div className="bg-[radial-gradient(circle_at_top,_rgba(34,197,94,0.18),_transparent_60%),linear-gradient(135deg,#f0fdf4,#ffffff_58%)] px-8 py-12 text-center">
                            <div className="mx-auto mb-5 flex h-20 w-20 items-center justify-center rounded-full bg-success/12 text-success">
                                <span className="material-symbols-outlined text-[42px]">verified</span>
                            </div>
                            <h2 className="font-sans text-[28px] font-bold text-slate-900">登录成功</h2>
                            <p className="mt-3 font-sans text-sm leading-6 text-slate-600">{xianyuLoginSuccessMessage}</p>
                            <div className="mt-6 flex items-center justify-center gap-2 text-[11px] font-sans text-slate-400">
                                <span className="inline-block h-1.5 w-1.5 rounded-full bg-success animate-pulse"></span>
                                <span>会自动返回当前页面</span>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {systemNotice && (
                <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/44 backdrop-blur-[3px] px-6 pointer-events-none">
                    <div className={`w-full max-w-md rounded-[26px] bg-white shadow-[0_28px_100px_rgba(15,23,42,0.28)] overflow-hidden animate-[fadeIn_180ms_ease-out] ${systemNotice.panelClass}`}>
                        <div className="px-8 py-10 text-center">
                            <div className={`mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full ${systemNotice.iconWrapClass}`}>
                                <span className="material-symbols-outlined text-[34px]">{systemNotice.icon}</span>
                            </div>
                            <h3 className={`font-sans text-[24px] font-bold ${systemNotice.titleClass}`}>{systemNotice.title}</h3>
                            <p className={`mt-3 font-sans text-sm leading-6 ${systemNotice.textClass}`}>{systemNotice.text}</p>
                            <div className="mt-5 flex items-center justify-center gap-2 text-[11px] font-sans text-slate-400">
                                <span className={`inline-block h-1.5 w-1.5 rounded-full ${error ? 'bg-error' : 'bg-success'} animate-pulse`}></span>
                                <span>提示会自动关闭</span>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <header className={`mb-6 flex flex-col gap-4 md:flex-row md:items-start ${hideHeader ? 'md:justify-end' : 'md:justify-between'}`}>
                {!hideHeader && (
                    <div>
                        <h1 className="font-sans text-2xl font-bold text-on-surface">系统参数配置</h1>
                        <p className="font-sans text-sm text-secondary mt-1">全局管理大模型服务密钥及闲鱼 OpenAPI 的各类配置。</p>
                    </div>
                )}
            </header>

            <form id="system-settings-form" onSubmit={handleSave} className="space-y-6">
                {/* 1. 大模型配置 Bento 卡片 */}
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 ambient-shadow space-y-6">
                    <div className="flex justify-between items-center border-b border-border-hairline pb-2.5">
                        <div 
                            className="flex items-center gap-2 cursor-pointer select-none group/title"
                            onClick={() => setLlmCollapsed(!llmCollapsed)}
                        >
                            <span className="material-symbols-outlined text-primary">generating_tokens</span>
                            <span className="font-sans text-sm font-bold text-on-surface group-hover/title:text-primary transition-colors">大模型接口设置 (LLM API)</span>
                            <span className="material-symbols-outlined text-secondary text-[20px] transition-transform duration-200" style={{ transform: llmCollapsed ? 'rotate(0deg)' : 'rotate(180deg)' }}>
                                expand_more
                            </span>
                        </div>
                        
                    </div>

                    {!llmCollapsed && (
                        <div className="space-y-3">
                            <div className="flex justify-start -mt-1">
                                <button 
                                    type="button"
                                    onClick={handleAddLlm}
                                    className="flex items-center gap-1 px-2.5 py-1 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg font-sans text-xs font-semibold active:scale-95 transition-all"
                                >
                                    <span className="material-symbols-outlined text-[14px]">add</span>
                                    <span>添加模型接口</span>
                                </button>
                            </div>
                            {llmList.map((item, idx) => (
                                <div key={idx} className="p-4 rounded-xl bg-surface-container-low border border-border-hairline relative group ambient-shadow hover:border-primary/40 transition-colors">
                                    {llmList.length > 1 && (
                                        <button
                                            type="button"
                                            onClick={() => handleRemoveLlm(idx)}
                                            className="absolute top-3 right-3 inline-flex h-7 w-7 items-center justify-center rounded-md text-secondary hover:text-error hover:bg-error/8 transition-colors cursor-pointer"
                                            title="删除此接口"
                                        >
                                            <span className="material-symbols-outlined text-[16px]">delete</span>
                                        </button>
                                    )}

                                    <div className={`flex items-center ${item.is_collapsed ? 'mb-0' : 'mb-3'}`}>
                                        <div className="font-sans text-xs font-bold text-primary flex items-center gap-1.5">
                                            <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
                                            <span>接口 #{idx + 1}</span>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => handleToggleLlmCard(idx)}
                                            className="ml-3 flex items-center gap-1 text-[11px] font-sans font-semibold text-secondary hover:text-primary transition-colors"
                                        >
                                            <span>{item.is_collapsed ? '展开' : '收起'}</span>
                                            <span
                                                className="material-symbols-outlined text-[18px] transition-transform duration-200"
                                                style={{ transform: item.is_collapsed ? 'rotate(0deg)' : 'rotate(180deg)' }}
                                            >
                                                expand_more
                                            </span>
                                        </button>
                                    </div>

                                    {!item.is_collapsed && (
                                    <div className="space-y-4">
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            <div className="space-y-1">
                                                <label className="block font-sans text-[10px] text-secondary font-semibold">API 代理端点 (Base URL)</label>
                                                <input 
                                                    type="text"
                                                    value={item.base_url}
                                                    onChange={(e) => handleLlmChange(idx, 'base_url', e.target.value)}
                                                    placeholder="https://api.deepseek.com/v1"
                                                    className="w-full bg-surface-container-lowest border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-mono"
                                                    required
                                                />
                                            </div>
                                            <div className="space-y-1">
                                                <label className="block font-sans text-[10px] text-secondary font-semibold">API 调用密钥 (API Key)</label>
                                                <div className="relative">
                                                    <input 
                                                        type={item.show_key ? 'text' : 'password'}
                                                        value={item.api_key}
                                                        onChange={(e) => handleLlmChange(idx, 'api_key', e.target.value)}
                                                        placeholder="请填写 API 密钥"
                                                        className="w-full bg-surface-container-lowest border border-border-hairline text-on-surface text-xs rounded-lg pl-3 pr-10 py-2 focus:outline-none focus:border-primary transition-all font-mono"
                                                        required
                                                    />
                                                    <button
                                                        type="button"
                                                        onClick={() => handleLlmChange(idx, 'show_key', !item.show_key)}
                                                        className="absolute inset-y-0 right-0 flex items-center pr-3 text-secondary hover:text-primary transition-colors cursor-pointer"
                                                        title={item.show_key ? '隐藏密钥' : '显示密钥'}
                                                    >
                                                        <span className="material-symbols-outlined text-[18px]">
                                                            {item.show_key ? 'visibility' : 'visibility_off'}
                                                        </span>
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="space-y-1">
                                            <label className="block font-sans text-[10px] text-secondary font-semibold">支持的模型列表 (逗号隔开)</label>
                                            <input 
                                                type="text"
                                                value={item.models_str}
                                                onChange={(e) => handleLlmChange(idx, 'models_str', e.target.value)}
                                                placeholder="deepseek-chat, deepseek-reasoner"
                                                className="w-full bg-surface-container-lowest border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-mono"
                                                required
                                            />
                                        </div>
                                    </div>
                                    )}
                                </div>
                            ))}
                            {renderCardActions()}
                        </div>
                    )}
                </div>

                {/* 3. 闲鱼 OpenAPI 配置 Bento 卡片 */}
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 ambient-shadow space-y-6">
                    <div className="flex justify-between items-center border-b border-border-hairline pb-2.5 mb-4">
                        <div 
                            className="flex items-center gap-2 cursor-pointer select-none group/title"
                            onClick={() => setOpenapiCollapsed(!openapiCollapsed)}
                        >
                            <span className="material-symbols-outlined text-primary">travel_explore</span>
                            <span className="font-sans text-sm font-bold text-on-surface group-hover/title:text-primary transition-colors">闲鱼 OpenAPI 与默认发布项配置</span>
                            <span className="material-symbols-outlined text-secondary text-[20px] transition-transform duration-200" style={{ transform: openapiCollapsed ? 'rotate(0deg)' : 'rotate(180deg)' }}>
                                expand_more
                            </span>
                        </div>
                    </div>

                    {!openapiCollapsed && (
                        <div className="space-y-4">
                            <div className="space-y-3">
                                <div className="flex flex-wrap items-center gap-2 pb-1">
                                {(configs.openapi.accounts || []).map((account, idx) => {
                                    const isActive = account.id === activeOpenapiAccountId;
                                    return (
                                        <div
                                            key={account.id}
                                            className={selectableChipClass(isActive)}
                                        >
                                            <button
                                                type="button"
                                                onClick={() => handleOpenapiAccountSwitch(account.id)}
                                                className={selectableChipActionClass(isActive)}
                                            >
                                                {account.name || `闲鱼账号 ${idx + 1}`}
                                            </button>
                                            {(configs.openapi.accounts || []).length > 1 && (
                                                <button
                                                    type="button"
                                                    onClick={() => handleRemoveOpenapiAccount(account.id)}
                                                    className="material-symbols-outlined text-[14px] cursor-pointer opacity-70 hover:opacity-100"
                                                    title="删除账号"
                                                >
                                                    close
                                                </button>
                                            )}
                                        </div>
                                    );
                                })}
                                <button
                                    type="button"
                                    onClick={handleAddOpenapiAccount}
                                    className="px-3 py-1.5 rounded-full border border-dashed border-primary/35 text-primary text-[11px] font-sans font-semibold hover:bg-primary/5 transition-colors"
                                >
                                    + 新增账号
                                </button>
                                </div>
                                <h4 className="font-sans text-sm font-bold text-on-surface">闲管家OpenAPI配置</h4>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div className="space-y-1">
                                    <label className="block font-sans text-xs text-secondary font-semibold">账号备注</label>
                                    <input 
                                        type="text"
                                        value={currentOpenapiAccount.name || ''}
                                        onChange={(e) => setCurrentOpenapiAccount(prev => ({ ...prev, name: e.target.value }))}
                                        className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-sans"
                                        placeholder="例如：主账号 / 店铺 A"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="block font-sans text-xs text-secondary font-semibold">开放平台地址 (Base URL)</label>
                                    <input 
                                        type="text"
                                        value={currentOpenapiAccount.base_url || ''}
                                        onChange={(e) => setCurrentOpenapiAccount(prev => ({ ...prev, base_url: e.target.value }))}
                                        className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-mono"
                                        required
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="block font-sans text-xs text-secondary font-semibold">应用公钥 (AppID / App Key)</label>
                                    <input 
                                        type="text"
                                        value={currentOpenapiAccount.appid || ''}
                                        onChange={(e) => setCurrentOpenapiAccount(prev => ({ ...prev, appid: e.target.value }))}
                                        className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-mono"
                                        required
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="block font-sans text-xs text-secondary font-semibold">应用私钥 (App Secret)</label>
                                    <div className="relative">
                                        <input
                                            type={currentOpenapiAccount.show_secret ? 'text' : 'password'}
                                            value={currentOpenapiAccount.app_secret || ''}
                                            onChange={(e) => setCurrentOpenapiAccount(prev => ({ ...prev, app_secret: e.target.value }))}
                                            className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg pl-3 pr-10 py-2 focus:outline-none focus:border-primary transition-all font-mono"
                                            required
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setCurrentOpenapiAccount(prev => ({ ...prev, show_secret: !prev.show_secret }))}
                                            className="absolute inset-y-0 right-0 flex items-center pr-3 text-secondary hover:text-primary transition-colors cursor-pointer"
                                            title={currentOpenapiAccount.show_secret ? '隐藏密钥' : '显示密钥'}
                                        >
                                            <span className="material-symbols-outlined text-[18px]">
                                                {currentOpenapiAccount.show_secret ? 'visibility' : 'visibility_off'}
                                            </span>
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <div className="border-t border-border-hairline/80 pt-4 mb-4">
                                <h4 className="font-sans text-sm font-bold text-on-surface mb-3">闲鱼账号信息</h4>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    <div className="space-y-1">
                                        <label className="block font-sans text-xs text-secondary font-semibold">闲鱼会员名</label>
                                        <div className="w-[271px] h-[34px] bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 flex items-center">
                                            <div className="min-w-0 flex items-center gap-2 text-xs">
                                                <div className="font-mono text-on-surface truncate">
                                                    {xianyuLoginStatus?.account_name || "未从当前 Session 识别到账号"}
                                                </div>
                                                <div className="text-[10px] text-secondary flex items-center gap-1.5 font-sans shrink-0">
                                                    {xianyuLoginStatus?.is_usable ? (
                                                        <>
                                                            <span className="w-1.5 h-1.5 rounded-full bg-success"></span>
                                                            <span className="text-success font-semibold">登录正常 (已同步)</span>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <span className="w-1.5 h-1.5 rounded-full bg-error animate-ping"></span>
                                                            <span className="text-error font-semibold">未检测到登录 (或凭证已过期)</span>
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="space-y-1">
                                        <label className="block font-sans text-xs text-secondary font-semibold opacity-0 select-none">登录操作</label>
                                        <div className="min-h-[38px] flex items-center">
                                            {isXianyuLoggingIn ? (
                                                <button
                                                    type="button"
                                                    disabled
                                                    className="px-3 py-1.5 bg-secondary/10 text-secondary text-[11px] font-bold rounded-lg flex items-center gap-1 opacity-70 cursor-not-allowed select-none"
                                                >
                                                    <span className="material-symbols-outlined text-[14px] animate-spin">sync</span>
                                                    <span>等待登录...</span>
                                                </button>
                                            ) : (
                                                <button
                                                    type="button"
                                                    onClick={handleXianyuLoginTrigger}
                                                    className="px-3 py-1.5 bg-primary hover:bg-primary-hover text-on-primary text-[11px] font-bold rounded-lg flex items-center gap-1 active:scale-95 transition-all cursor-pointer"
                                                >
                                                    <span className="material-symbols-outlined text-[14px]">open_in_new</span>
                                                    <span>{xianyuLoginStatus?.is_usable ? "重新登录" : "立即登录"}</span>
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                    <div className="hidden md:block"></div>
                                </div>
                            </div>

                            <div className="border-t border-border-hairline/80 pt-4">
                                <h4 className="font-sans text-sm font-bold text-on-surface mb-3">闲鱼宝贝发布默认参数</h4>
                                
                                {isCustomRegion ? (
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                                        <div className="space-y-1">
                                            <label className="block font-sans text-xs text-secondary font-semibold">发货省份代码</label>
                                            <input 
                                                type="number"
                                                value={currentOpenapiAccount.default_config?.province}
                                                onChange={(e) => setCurrentOpenapiAccount(prev => ({
                                                    ...prev,
                                                    default_config: { ...prev.default_config, province: parseInt(e.target.value) || 0 }
                                                }))}
                                                className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-mono"
                                                required
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="block font-sans text-xs text-secondary font-semibold">发货城市代码</label>
                                            <input 
                                                type="number"
                                                value={currentOpenapiAccount.default_config?.city}
                                                onChange={(e) => setCurrentOpenapiAccount(prev => ({
                                                    ...prev,
                                                    default_config: { ...prev.default_config, city: parseInt(e.target.value) || 0 }
                                                }))}
                                                className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-mono"
                                                required
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <div className="flex justify-between items-center">
                                                <label className="block font-sans text-xs text-secondary font-semibold">发货区县代码</label>
                                                <button 
                                                    type="button" 
                                                    onClick={() => {
                                                        setIsCustomRegion(false);
                                                        setSelectedProv("110000");
                                                        setSelectedCity("110100");
                                                        setSelectedDist("110101");
                                                        setCurrentOpenapiAccount(prev => ({
                                                            ...prev,
                                                            default_config: {
                                                                ...prev.default_config,
                                                                province: 110000,
                                                                city: 110100,
                                                                district: 110101
                                                            }
                                                        }));
                                                    }}
                                                    className="text-[10px] text-primary hover:underline cursor-pointer"
                                                >
                                                    返回选择
                                                </button>
                                            </div>
                                            <input 
                                                type="number"
                                                value={currentOpenapiAccount.default_config?.district}
                                                onChange={(e) => setCurrentOpenapiAccount(prev => ({
                                                    ...prev,
                                                    default_config: { ...prev.default_config, district: parseInt(e.target.value) || 0 }
                                                }))}
                                                className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-mono"
                                                required
                                            />
                                        </div>
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                                        <div className="space-y-1">
                                            <label className="block font-sans text-xs text-secondary font-semibold">发货省份</label>
                                            <select
                                                value={selectedProv}
                                                onChange={(e) => {
                                                    if (e.target.value === "custom") {
                                                        setIsCustomRegion(true);
                                                    } else {
                                                        handleProvChange(e.target.value);
                                                    }
                                                }}
                                                className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-sans cursor-pointer"
                                            >
                                                {regions.map(p => (
                                                    <option key={p.code} value={p.code}>{p.name}</option>
                                                ))}
                                                <option value="custom">[手动输入 Adcode 代码]</option>
                                            </select>
                                        </div>
                                        <div className="space-y-1">
                                            <label className="block font-sans text-xs text-secondary font-semibold">发货城市</label>
                                            <select
                                                value={selectedCity}
                                                onChange={(e) => handleCityChange(e.target.value)}
                                                className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-sans cursor-pointer"
                                            >
                                                {(regions.find(p => p.code.toString() === selectedProv)?.cities || []).map(c => (
                                                    <option key={c.code} value={c.code}>{c.name}</option>
                                                ))}
                                            </select>
                                        </div>
                                        <div className="space-y-1">
                                            <label className="block font-sans text-xs text-secondary font-semibold">发货区县</label>
                                            <select
                                                value={selectedDist}
                                                onChange={(e) => handleDistChange(e.target.value)}
                                                className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-sans cursor-pointer"
                                            >
                                                {((regions.find(p => p.code.toString() === selectedProv)?.cities || []).find(c => c.code.toString() === selectedCity)?.districts || []).map(d => (
                                                    <option key={d.code} value={d.code}>{d.name}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>
                                )}

                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    <div className="space-y-1">
                                        <label className="block font-sans text-xs text-secondary font-semibold">默认运费 (分)</label>
                                        <input
                                            type="number"
                                            value={currentOpenapiAccount.default_config?.express_fee}
                                            onChange={(e) => setCurrentOpenapiAccount(prev => ({
                                                ...prev,
                                                default_config: { ...prev.default_config, express_fee: parseInt(e.target.value) || 0 }
                                            }))}
                                            className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-mono"
                                        />
                                    </div>
                                    <div className="hidden md:block"></div>
                                    <div className="hidden md:block"></div>
                                </div>
                            </div>

                            {renderCardActions()}
                        </div>
                    )}
                </div>

                {/* 4. 货源渠道号池配置 */}
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 ambient-shadow space-y-6 mt-6">
                    <div className="flex justify-between items-center border-b border-border-hairline pb-2.5 mb-4">
                        <div
                            className="flex items-center gap-2 cursor-pointer select-none group/title"
                            onClick={() => setSourceChannelsCollapsed(!sourceChannelsCollapsed)}
                        >
                            <span className="material-symbols-outlined text-primary">hub</span>
                            <span className="font-sans text-sm font-bold text-on-surface group-hover/title:text-primary transition-colors">货源渠道号池</span>
                            <span className="material-symbols-outlined text-secondary text-[20px] transition-transform duration-200" style={{ transform: sourceChannelsCollapsed ? 'rotate(0deg)' : 'rotate(180deg)' }}>
                                expand_more
                            </span>
                        </div>
                    </div>

                    {!sourceChannelsCollapsed && (
                        <div className="space-y-6">
                            <div className="grid grid-cols-1 md:grid-cols-1 gap-4">
                                <div className="space-y-1">
                                    <div className="flex flex-wrap items-center gap-2">
                                        {currentSourceChannels.length > 1 ? (
                                            currentSourceChannels.map((channel, idx) => {
                                                const isActive = channel.channel_id === activeSourceChannelId;
                                                return (
                                                    <div
                                                        key={channel.channel_id}
                                                        className={selectableChipClass(isActive)}
                                                    >
                                                        <button
                                                            type="button"
                                                            onClick={() => handleSourceChannelSwitch(channel.channel_id)}
                                                            className={selectableChipActionClass(isActive)}
                                                        >
                                                            {channel.label || `货源渠道 ${idx + 1}`}
                                                        </button>
                                                    </div>
                                                );
                                            })
                                        ) : (
                                            <div className={selectableChipClass(true)}>
                                                <span className={selectableChipActionClass(true)}>
                                                    {currentSourceChannel.label || '1688 货源渠道'}
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-3">
                                <h4 className="font-sans text-sm font-bold text-on-surface">当前激活账号</h4>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-1 gap-4">
                                <div className="space-y-1">
                                    <div className="w-full min-h-[38px] bg-surface-container-low border border-border-hairline rounded-lg px-3 py-2 flex flex-wrap items-center gap-3">
                                        {loginReadySourceAccounts.length > 0 ? (
                                            loginReadySourceAccounts.map((account, idx) => {
                                                const isChecked = visibleActiveSourceAccountIds.includes(account.account_id);
                                                return (
                                                    <label key={account.account_id} className="inline-flex items-center gap-2 text-xs text-on-surface font-sans cursor-pointer">
                                                        <input
                                                            type="checkbox"
                                                            checked={isChecked}
                                                            onChange={(e) => handleSourceActiveAccountToggle(account.account_id, e.target.checked)}
                                                            className="rounded border-border-hairline text-primary focus:ring-primary/30"
                                                        />
                                                        <span>{getSourceAccountDisplayName(account, idx + 1)}</span>
                                                    </label>
                                                );
                                            })
                                        ) : (
                                            <span className="text-xs text-secondary font-sans">暂无登录成功的账号，完成登录后才会展示在这里</span>
                                        )}
                                    </div>
                                </div>
                            </div>

                            <div className="border-t border-border-hairline/80 pt-4 space-y-4">
                                <div className="flex flex-wrap items-center gap-2">
                                    {currentSourceAccounts.map((account, idx) => {
                                        const isSelected = account.account_id === currentSourceAccountId;
                                        const isActive = visibleActiveSourceAccountIds.includes(account.account_id);
                                        const loginVisualState = getSourceSessionVisualState(account.session_report);
                                        return (
                                            <div
                                                key={account.account_id}
                                                className={selectableChipClass(isSelected)}
                                            >
                                                <button
                                                    type="button"
                                                    onClick={() => handleSourceAccountSwitch(account.account_id)}
                                                    className={selectableChipActionClass(isSelected)}
                                                >
                                                    {getSourceAccountDisplayName(account, idx + 1)}
                                                </button>
                                                {isActive && (
                                                    <span className={`inline-block w-1.5 h-1.5 rounded-full ${loginVisualState.dotClass}`} title={loginVisualState.title}></span>
                                                )}
                                                {currentSourceAccounts.length > 1 && (
                                                    <button
                                                        type="button"
                                                        onClick={() => handleRemoveSourceAccount(account.account_id)}
                                                        className="material-symbols-outlined text-[14px] cursor-pointer opacity-70 hover:opacity-100"
                                                        title="删除账号"
                                                    >
                                                        close
                                                    </button>
                                                )}
                                            </div>
                                        );
                                    })}
                                    <button
                                        type="button"
                                        onClick={handleAddSourceAccount}
                                        className="px-3 py-1.5 rounded-full border border-dashed border-primary/35 text-primary text-[11px] font-sans font-semibold hover:bg-primary/5 transition-colors"
                                    >
                                        + 新增账号
                                    </button>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="space-y-1">
                                        <label className="block font-sans text-xs text-secondary font-semibold">账号备注</label>
                                        <input
                                            type="text"
                                            value={currentSourceAccount.label || ''}
                                            onChange={(e) => setCurrentSourceAccount(prev => ({ ...prev, label: e.target.value }))}
                                            className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-sans"
                                            placeholder="例如：1688 主账号"
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="block font-sans text-xs text-secondary font-semibold">账号状态</label>
                                        <div className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 font-sans">
                                            {currentSourceAccount.enabled !== false ? '已启用' : '已停用'}
                                        </div>
                                    </div>
                                    <div className="space-y-1 md:col-span-2">
                                        <label className="block font-sans text-xs text-secondary font-semibold">备注</label>
                                        <input
                                            type="text"
                                            value={currentSourceAccount.notes || ''}
                                            onChange={(e) => setCurrentSourceAccount(prev => ({ ...prev, notes: e.target.value }))}
                                            className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-primary transition-all font-sans"
                                            placeholder="可记录该账号的用途、归属渠道或其他说明"
                                        />
                                    </div>
                                </div>

                                <div className="rounded-xl border border-border-hairline bg-surface-container-low px-4 py-4 flex flex-col gap-4">
                                    {currentSourceChannelCapabilities.supportsSessionState ? (
                                        <>
                                            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                                                <div className="space-y-1">
                                                    <div className="flex items-center gap-2">
                                                        <span className={`inline-block w-2 h-2 rounded-full ${currentSourceStatusDotClassForDisplay}`}></span>
                                                        <span className={`font-sans text-sm font-bold ${currentSourceStatusTextClassForDisplay}`}>
                                                            {currentSourceStatusTextForDisplay}
                                                        </span>
                                                    </div>
                                                    <div className="font-sans text-xs text-secondary">
                                                        页面识别名：{currentSourceRealtimeName || '未识别'}
                                                    </div>
                                                    {currentSourceLabel && (
                                                        <div className="font-sans text-[11px] text-secondary">
                                                            账号备注：{currentSourceLabel}
                                                            {isSourceNameFallback && (
                                                                <span className="ml-1 text-[10px] text-primary">当前展示为备注兜底</span>
                                                            )}
                                                        </div>
                                                    )}
                                                    {currentSourceNameSource && (
                                                        <div className="font-sans text-[10px] text-secondary/80">
                                                            识别来源：{currentSourceNameSource}
                                                        </div>
                                                    )}
                                                    <div className="font-sans text-[11px] text-secondary">
                                                        最近检测：{currentSourceAccount.session_report?.last_checked_at || '暂无'}
                                                    </div>
                                                </div>
                                                <div className="flex flex-wrap items-center gap-2">
                                                    {currentSourceChannelCapabilities.supportsLoginTrigger && (
                                                        isSourceChannelLoggingIn ? (
                                                            <button
                                                                type="button"
                                                                disabled
                                                                className="px-4 py-2 bg-secondary/10 text-secondary rounded-lg font-sans text-xs font-bold transition-colors flex items-center gap-1.5 cursor-not-allowed"
                                                            >
                                                                <span className="material-symbols-outlined text-[16px] animate-spin">autorenew</span>
                                                                <span>等待登录...</span>
                                                            </button>
                                                        ) : (
                                                            <button
                                                                type="button"
                                                                onClick={handleSourceChannelLoginTrigger}
                                                                className="px-4 py-2 bg-primary hover:bg-primary-hover text-on-primary rounded-lg font-sans text-xs font-bold transition-colors shadow-sm flex items-center gap-1.5 active:scale-95 duration-100"
                                                            >
                                                                <span className="material-symbols-outlined text-[16px]">open_in_new</span>
                                                                <span>{currentSourceSessionLoggedIn ? '重新登录' : '立即登录'}</span>
                                                            </button>
                                                        )
                                                    )}
            <button
                                                        type="button"
                                                        onClick={handleCheckSourceChannelStatus}
                                                        disabled={isCheckingSourceChannelStatus || isSourceChannelLoggingIn}
                                                        className="px-4 py-2 bg-surface-container-high hover:bg-surface-container text-on-surface disabled:opacity-60 rounded-lg font-sans text-xs font-bold transition-colors shadow-sm flex items-center gap-1.5 active:scale-95 duration-100 disabled:cursor-not-allowed"
                                                    >
                                                        <span className={`material-symbols-outlined text-[16px] ${isCheckingSourceChannelStatus ? 'animate-spin' : ''}`}>
                                                            {isCheckingSourceChannelStatus ? 'autorenew' : 'sync'}
                                                        </span>
                                                        <span>{isCheckingSourceChannelStatus ? '正在检测...' : (isSourceChannelLoggingIn ? '登录中不可检测' : '检测状态')}</span>
                                                    </button>
                                                </div>
                                            </div>

                                            {!!currentSourceAccount.session_report?.error_message && (
                                                <div className="rounded-lg bg-error/6 border border-error/15 px-3 py-2 text-[11px] text-error leading-relaxed">
                                                    {currentSourceAccount.session_report.error_message}
                                                </div>
                                            )}
                                        </>
                                    ) : (
                                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                                            <div className="space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="inline-block w-2 h-2 rounded-full bg-secondary/60"></span>
                                                    <span className="font-sans text-sm font-bold text-on-surface">待接入</span>
                                                </div>
                                                <div className="font-sans text-xs text-secondary">
                                                    当前渠道暂未接入会话状态检测，账号池仅保留结构与备注信息。
                                                </div>
                                            </div>
                                            <button
                                                type="button"
                                                disabled
                                                className="px-4 py-2 bg-surface-container-high text-secondary rounded-lg font-sans text-xs font-bold transition-colors flex items-center gap-1.5 cursor-not-allowed opacity-70"
                                            >
                                                <span className="material-symbols-outlined text-[16px]">schedule</span>
                                                <span>待接入</span>
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                            {renderCardActions()}
                        </div>
                    )}
                </div>

                {/* 4. 商品爬取与筛选配置 Bento 卡片 */}
                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 ambient-shadow space-y-6 mt-6">
                    <div className="flex justify-between items-center border-b border-border-hairline pb-2.5">
                        <div 
                            className="flex items-center gap-2 cursor-pointer select-none group/title"
                            onClick={() => setCrawlCollapsed(!crawlCollapsed)}
                        >
                            <span className="material-symbols-outlined text-primary">travel_explore</span>
                            <span className="font-sans text-sm font-bold text-on-surface group-hover/title:text-primary transition-colors">商品爬取与筛选配置</span>
                            <span className="material-symbols-outlined text-secondary text-[20px] transition-transform duration-200" style={{ transform: crawlCollapsed ? 'rotate(0deg)' : 'rotate(180deg)' }}>
                                expand_more
                            </span>
                        </div>
                    </div>

                    {!crawlCollapsed && (
                        <div className="space-y-6">
                            {/* 1688 商品爬取数量 */}
                            <div className="space-y-2">
                                <div className="flex justify-between items-center">
                                    <label className="font-sans text-xs text-secondary font-semibold">1688 商品爬取数量</label>
                                    <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">
                                        {crawlConfig.source_limit_1688} 条
                                    </span>
                                </div>
                                <p className="font-sans text-[11px] text-secondary leading-relaxed">
                                    控制每个闲鱼爆款商品去 1688 抓取的最大候选商品深度（最多 100 条）。数值越大扫描更彻底，但也会消耗更多抓取时间与资源。
                                </p>
                                <div className="flex items-center gap-4">
                                    <input 
                                        type="range"
                                        min="1"
                                        max="100"
                                        step="1"
                                        value={crawlConfig.source_limit_1688}
                                        onChange={(e) => setCrawlConfig(prev => ({ ...prev, source_limit_1688: parseInt(e.target.value) || 10 }))}
                                        className="flex-1 h-1.5 bg-surface-container rounded-lg appearance-none cursor-pointer accent-primary"
                                    />
                                    <div className="flex items-center gap-1">
                                        <input
                                            type="number"
                                            min="1"
                                            max="100"
                                            step="1"
                                            value={crawlConfig.source_limit_1688}
                                            onChange={(e) => {
                                                let val = parseInt(e.target.value) || 10;
                                                if (val < 1) val = 1;
                                                if (val > 100) val = 100;
                                                setCrawlConfig(prev => ({ ...prev, source_limit_1688: val }));
                                            }}
                                            className="w-16 bg-surface-container-low border border-border-hairline text-on-surface text-center font-mono text-xs rounded-lg px-2 py-1 focus:outline-none focus:border-primary"
                                        />
                                        <span className="font-sans text-xs text-secondary">条</span>
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-2 pt-2 border-t border-border-hairline/70">
                                <div className="flex justify-between items-center">
                                    <label className="font-sans text-xs text-secondary font-semibold">预期净利润毛利率</label>
                                    <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">
                                        {Math.round(normalizeGrossProfitRate(crawlConfig.gross_profit_rate) * 100)}%
                                    </span>
                                </div>
                                <p className="font-sans text-[11px] text-secondary leading-relaxed">
                                    商品档案与货源对比中的预期净利润按 “1688 成本价 × 毛利率” 计算。
                                </p>
                                <div className="flex items-center gap-4">
                                    <input
                                        type="range"
                                        min="1"
                                        max="100"
                                        step="1"
                                        value={Math.round(normalizeGrossProfitRate(crawlConfig.gross_profit_rate) * 100)}
                                        onChange={(e) => setCrawlConfig(prev => ({ ...prev, gross_profit_rate: (parseInt(e.target.value) || 30) / 100 }))}
                                        className="flex-1 h-1.5 bg-surface-container rounded-lg appearance-none cursor-pointer accent-primary"
                                    />
                                    <div className="flex items-center gap-1">
                                        <input
                                            type="number"
                                            min="1"
                                            max="100"
                                            value={Math.round(normalizeGrossProfitRate(crawlConfig.gross_profit_rate) * 100)}
                                            onChange={(e) => {
                                                let val = parseInt(e.target.value) || 30;
                                                if (val < 1) val = 1;
                                                if (val > 100) val = 100;
                                                setCrawlConfig(prev => ({ ...prev, gross_profit_rate: val / 100 }));
                                            }}
                                            className="w-16 bg-surface-container-low border border-border-hairline text-on-surface text-center font-mono text-xs rounded-lg px-2 py-1 focus:outline-none focus:border-primary"
                                        />
                                        <span className="font-sans text-xs text-secondary">%</span>
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-3 pt-2 border-t border-border-hairline/70">
                                <div className="flex items-center justify-between gap-3 flex-wrap">
                                    <label className="block font-sans text-xs text-secondary font-semibold">货源渠道配置</label>
                                    <span className="font-sans text-[11px] text-secondary">
                                        仅展示“已登录成功 + 已加入当前激活账号”的渠道账号
                                    </span>
                                </div>
                                {crawlAvailableChannels.length === 0 ? (
                                    <div className="p-4 bg-warning/5 border border-warning/15 rounded-xl flex items-center gap-3 text-warning">
                                        <span className="material-symbols-outlined text-[20px]">warning</span>
                                        <div className="font-sans text-xs leading-relaxed">
                                            当前货源渠道号池中还没有可用于抓取的登录成功账号。请先去上方 <strong>“货源渠道号池”</strong> 完成账号登录，并将其加入当前激活账号。
                                        </div>
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        {crawlSelectionAdjustmentNotice && (
                                            <div className="rounded-xl border border-warning/20 bg-warning/5 px-4 py-3 flex items-start gap-3 text-warning">
                                                <span className="material-symbols-outlined text-[18px] mt-0.5">info</span>
                                                <div className="font-sans text-[11px] leading-relaxed">
                                                    {crawlSelectionAdjustmentNotice}
                                                </div>
                                            </div>
                                        )}
                                        {!isCrawlEditorFollowingActiveSourceChannel && currentCrawlChannel && (
                                            <div className="rounded-xl border border-primary/15 bg-primary/[0.04] px-4 py-3 flex items-start gap-3 text-primary">
                                                <span className="material-symbols-outlined text-[18px] mt-0.5">sync_alt</span>
                                                <div className="font-sans text-[11px] leading-relaxed">
                                                    当前正在编辑的抓取渠道为 <strong>{currentCrawlChannel.label || currentCrawlChannel.channel_id}</strong>。
                                                    {activeSourceChannelInCrawlPool
                                                        ? (
                                                            <> 上方切换货源渠道后，这里会自动跟随到对应渠道。</>
                                                        )
                                                        : (
                                                            <> 当前上方选中的渠道还没有“已登录成功且加入当前激活账号”的可抓取账号，因此这里暂时回落到最近一个可编辑渠道。</>
                                                        )}
                                                </div>
                                            </div>
                                        )}
                                        {isCrawlSelectionMissing && (
                                            <div className="rounded-xl border border-warning/20 bg-warning/5 px-4 py-3 flex items-start gap-3 text-warning">
                                                <span className="material-symbols-outlined text-[18px] mt-0.5">warning</span>
                                                <div className="font-sans text-[11px] leading-relaxed">
                                                    当前已进入“手动选择货源账号”模式，但还没有选中任何可参与抓取的账号。
                                                    请为至少一个渠道勾选账号，或点击 <strong>“使用当前激活账号”</strong> 后再保存。
                                                </div>
                                            </div>
                                        )}
                                        <div className="flex flex-wrap items-center gap-2">
                                            {crawlAvailableChannels.map(channel => {
                                                const isFocused = channel.channel_id === effectiveSelectedCrawlChannelId;
                                                const selectedCount = crawlChannelSelectionMap[channel.channel_id]?.account_ids?.length || 0;
                                                const isEnabledForCrawl = selectedCount > 0;
                                                return (
                                                    <button
                                                        key={channel.channel_id}
                                                        type="button"
                                                        onClick={() => handleCrawlChannelSwitch(channel.channel_id)}
                                                        className={`px-3 py-1.5 rounded-full border text-[11px] font-sans font-semibold transition-all ${
                                                            isFocused
                                                                ? 'border-primary bg-primary text-on-primary shadow-[0_0_0_1px_rgba(197,86,16,0.32),0_10px_18px_rgba(197,86,16,0.22)]'
                                                                : isEnabledForCrawl
                                                                    ? 'border-primary/35 bg-primary/[0.06] text-primary hover:bg-primary/[0.1]'
                                                                    : 'border-border-hairline bg-surface-container-low text-secondary hover:border-primary/25 hover:text-on-surface'
                                                        }`}
                                                    >
                                                        <span>{channel.label || channel.channel_id}</span>
                                                        <span className={`ml-1 ${isFocused ? 'text-on-primary/90' : isEnabledForCrawl ? 'text-primary/80' : 'text-secondary/80'}`}>
                                                            {selectedCount > 0 ? `(${selectedCount})` : ''}
                                                        </span>
                                                    </button>
                                                );
                                            })}
                                        </div>

                                        {currentCrawlChannel && (
                                            <div className="rounded-xl border border-border-hairline bg-surface-container-low p-4 space-y-3">
                                                <div className="flex items-center justify-between gap-3 flex-wrap">
                                                    <div>
                                                        <div className="font-sans text-xs font-bold text-on-surface">
                                                            {currentCrawlChannel.label || currentCrawlChannel.channel_id}
                                                        </div>
                                                        <div className="mt-1 font-sans text-[11px] text-secondary">
                                                            已登录且可参与抓取的账号：{(currentCrawlChannel.crawl_accounts || []).length} 个
                                                        </div>
                                                    </div>
                                                    <button
                                                        type="button"
                                                        onClick={() => handleCrawlChannelUseActiveAccounts(currentCrawlChannel.channel_id)}
                                                        className="px-3 py-1.5 rounded-lg bg-primary/10 hover:bg-primary/15 text-primary text-[11px] font-sans font-semibold transition-colors"
                                                    >
                                                        使用当前激活账号
                                                    </button>
                                                </div>

                                                {(currentCrawlChannel.crawl_accounts || []).length === 0 ? (
                                                    <div className="rounded-lg border border-dashed border-border-hairline bg-surface-container-lowest px-3 py-3 text-[11px] text-secondary">
                                                        当前渠道暂无“已登录成功且加入当前激活账号”的可选账号。
                                                    </div>
                                                ) : (
                                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                        {currentCrawlChannel.crawl_accounts.map((account, idx) => {
                                                            const report = account.session_report || {};
                                                            const isChecked = currentCrawlSelectedAccountIds.includes(account.account_id);
                                                            const accountDisplayName = getSourceAccountDisplayName(account, idx + 1);
                                                            const accountRemark = account.label || '';
                                                            return (
                                                                <label
                                                                    key={account.account_id}
                                                                    className={`flex items-start gap-3 rounded-xl border px-3 py-3 cursor-pointer transition-all ${
                                                                        isChecked
                                                                            ? 'border-primary/45 bg-primary/[0.05] shadow-sm shadow-primary/5'
                                                                            : 'border-border-hairline bg-surface-container-lowest hover:border-primary/20'
                                                                    }`}
                                                                >
                                                                    <input
                                                                        type="checkbox"
                                                                        className="mt-0.5 rounded border-secondary text-primary focus:ring-primary/20"
                                                                        checked={isChecked}
                                                                        onChange={(e) => handleCrawlAccountToggle(currentCrawlChannel.channel_id, account.account_id, e.target.checked)}
                                                                    />
                                                                    <div className="min-w-0 flex-1">
                                                                        <div className="flex items-center gap-2 flex-wrap">
                                                                            <span className="font-sans text-xs font-semibold text-on-surface">
                                                                                {accountDisplayName}
                                                                            </span>
                                                                            <span className="inline-flex items-center gap-1 text-[10px] text-success">
                                                                                <span className="w-1.5 h-1.5 rounded-full bg-success"></span>
                                                                                <span>{report.status_text || '登录正常'}</span>
                                                                            </span>
                                                                        </div>
                                                                        {accountRemark && accountRemark !== accountDisplayName && (
                                                                            <div className="mt-1 text-[11px] text-secondary">
                                                                                账号备注：{accountRemark}
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                </label>
                                                            );
                                                        })}
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {currentCrawlChannel && (
                                            <div className="rounded-xl border border-border-hairline bg-surface-container-low p-4 space-y-4">
                                                <div className="flex items-center justify-between gap-3 flex-wrap">
                                                    <div>
                                                        <div className="font-sans text-xs font-bold text-on-surface">
                                                            当前渠道货源筛选项
                                                        </div>
                                                        <div className="mt-1 font-sans text-[11px] text-secondary">
                                                            按渠道独立保存。切换渠道后，会自动切换到该渠道自己的筛选配置。
                                                        </div>
                                                    </div>
                                                    <span className="px-2.5 py-1 rounded-full bg-surface-container-lowest border border-border-hairline text-[11px] font-sans text-secondary">
                                                        {currentCrawlChannel.label || currentCrawlChannel.channel_id}
                                                    </span>
                                                </div>

                                                {currentCrawlFilterMeta.length === 0 ? (
                                                    <div className="rounded-lg border border-dashed border-border-hairline bg-surface-container-lowest px-3 py-3 text-[11px] text-secondary">
                                                        当前渠道暂不支持列表筛选项配置。
                                                    </div>
                                                ) : (
                                                    <div className="space-y-4">
                                                        {Object.entries(currentCrawlFilterGroups).map(([groupName, filters]) => (
                                                            <div key={groupName} className="space-y-2">
                                                                <div className="font-sans text-[11px] font-semibold text-secondary">
                                                                    {groupName}
                                                                </div>
                                                                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                                                    {filters.map(filter => {
                                                                        const isChecked = !!currentCrawlFilterValues[filter.key];
                                                                        return (
                                                                            <label
                                                                                key={filter.key}
                                                                                className={`flex items-center gap-2 rounded-xl border px-3 py-3 cursor-pointer transition-all ${
                                                                                    isChecked
                                                                                        ? 'border-primary/45 bg-primary/[0.05] text-primary shadow-sm shadow-primary/5'
                                                                                        : 'border-border-hairline bg-surface-container-lowest text-on-surface hover:border-primary/20'
                                                                                }`}
                                                                            >
                                                                                <input
                                                                                    type="checkbox"
                                                                                    className="rounded border-secondary text-primary focus:ring-primary/20"
                                                                                    checked={isChecked}
                                                                                    onChange={(e) => handleCrawlSearchFilterToggle(currentCrawlChannel.channel_id, filter.key, e.target.checked)}
                                                                                />
                                                                                <span className="font-sans text-xs font-semibold">
                                                                                    {filter.label}
                                                                                </span>
                                                                            </label>
                                                                        );
                                                                    })}
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* 商品筛选使用的模型 */}
                            <div className="space-y-3 pt-2">
                                <label className="block font-sans text-xs text-secondary font-semibold">商品相关性筛选模型（支持多选轮询）</label>
                                <p className="font-sans text-[11px] text-secondary leading-relaxed">
                                    多选大模型后，系统将对选中的模型做全局负载轮询（Round-Robin），以摊平单个模型接口 of Token 额度消耗。若为空，则默认轮询大模型接口设置下的全部有效模型。
                                </p>
                                
                                {availableModels.length === 0 ? (
                                    <div className="p-4 bg-error/5 border border-error/15 rounded-xl flex items-center gap-3 text-error">
                                        <span className="material-symbols-outlined text-[20px]">warning</span>
                                        <div className="font-sans text-xs leading-relaxed">
                                            未在上方大模型接口中检测到已保存的候选模型。请在 <strong>“大模型接口设置”</strong> 中先添加并保存至少一个模型，然后在此多选。
                                        </div>
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                                        {availableModels.map(modelName => {
                                            const isChecked = crawlConfig.source_filter_models.includes(modelName);
                                            return (
                                                <div 
                                                    key={modelName}
                                                    onClick={() => {
                                                        const currentList = [...crawlConfig.source_filter_models];
                                                        if (isChecked) {
                                                            const idx = currentList.indexOf(modelName);
                                                            if (idx !== -1) currentList.splice(idx, 1);
                                                        } else {
                                                            currentList.push(modelName);
                                                        }
                                                        setCrawlConfig(prev => ({ ...prev, source_filter_models: currentList }));
                                                    }}
                                                    className={`p-3 border rounded-xl flex items-center gap-2.5 transition-all select-none cursor-pointer scale-100 active:scale-95 ${
                                                        isChecked 
                                                        ? 'bg-primary/5 border-primary/45 text-primary shadow-sm shadow-primary/5' 
                                                        : 'bg-surface-container-low border-border-hairline hover:bg-surface-container hover:border-secondary-container text-on-surface'
                                                    }`}
                                                >
                                                    <span className={`material-symbols-outlined text-[18px] ${isChecked ? 'text-primary' : 'text-secondary'}`}>
                                                        {isChecked ? 'check_box' : 'check_box_outline_blank'}
                                                    </span>
                                                    <span className="font-sans text-xs font-semibold truncate leading-none" title={modelName}>{modelName}</span>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                            {renderCardActions()}
                        </div>
                    )}
                </div>
            </form>
        </div>
    );
};

const App = () => {
    const [view, setActiveView] = useState("dashboard"); 
    const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("xianyu-sidebar-collapsed") === "true");
    const [tasks, setTasks] = useState([]);
    const [selectedTask, setSelectedTask] = useState(null);
    const [detailedItems, setDetailedItems] = useState([]); 
    const [selectedItem, setSelectedItem] = useState(null); 
    const [selectedOrderNo, setSelectedOrderNo] = useState('');
    const [sysStatus, setSysStatus] = useState({});
    const [newKeyword, setNewKeyword] = useState("");

    const [selectedIds, setSelectedIds] = useState([]);
    const [batchPublishing, setBatchPublishing] = useState(false);
    const [batchDepublishing, setBatchDepublishing] = useState(false);
    const [batchDeleting, setBatchDeleting] = useState(false);
    const [batchStatusMap, setBatchStatusMap] = useState({});
    const [batchResultMap, setBatchResultMap] = useState({});
    const [confirmDialog, setConfirmDialog] = useState(null);
    const [taskStartConfig, setTaskStartConfig] = useState(null);
    const [sourceChannelFilter, setSourceChannelFilter] = useState("all");
    const [sourceSortRule, setSourceSortRule] = useState("price_asc");
    const [sourceListPage, setSourceListPage] = useState(1);
    const [archivePage, setArchivePage] = useState(1);
    const [resultPage, setResultPage] = useState(1);
    const [resultTaskPage, setResultTaskPage] = useState(1);

    // 全局双主题状态机
    const [theme, setTheme] = useState(() => localStorage.getItem("xianyu-theme") || "light");

    useEffect(() => {
        if (theme === "dark") {
            document.documentElement.classList.add("dark");
            document.documentElement.classList.remove("light");
        } else {
            document.documentElement.classList.add("light");
            document.documentElement.classList.remove("dark");
        }
        localStorage.setItem("xianyu-theme", theme);
    }, [theme]);

    useEffect(() => {
        localStorage.setItem("xianyu-sidebar-collapsed", sidebarCollapsed ? "true" : "false");
    }, [sidebarCollapsed]);

    // 当切换商品详情时，自动重置批量状态，并清空当前勾选
    useEffect(() => {
        if (selectedItem) {
            setSelectedIds([]);
            setBatchStatusMap({});
            setBatchResultMap({});
            setSourceListPage(1);
        } else {
            setSelectedIds([]);
            setBatchStatusMap({});
            setBatchResultMap({});
            setSourceListPage(1);
        }
    }, [selectedItem]);

    useEffect(() => {
        setSourceListPage(1);
    }, [sourceChannelFilter, sourceSortRule]);

    const selectableSources = (selectedItem?.sources || []).filter(src => !src.drop_reason);
    const selectedSources = selectableSources.filter(src => selectedIds.includes(src.db_id));
    const normalizeSourceActionStatus = (rawStatus) => {
        if (rawStatus === 'selected') return 'selected';
        if (rawStatus === 'success' || rawStatus === 'done') return 'done';
        if (rawStatus === 'depublished') return 'depublished';
        if (rawStatus === 'selecting' || rawStatus === 'publishing' || rawStatus === 'depublishing' || rawStatus === 'deleting' || rawStatus === 'failed') return rawStatus;
        if (rawStatus === 'deleted' || rawStatus === 'none' || rawStatus === 'idle' || !rawStatus) return 'idle';
        return 'idle';
    };
    const getSourceActionStatus = (src) => normalizeSourceActionStatus(batchStatusMap[src.db_id] || src.publish_status || 'idle');
    const addableIds = selectedSources
        .filter(src => ['idle', 'failed', 'depublished'].includes(getSourceActionStatus(src)))
        .map(src => src.db_id);
    const depublishableIds = selectedSources
        .filter(src => getSourceActionStatus(src) === 'done')
        .map(src => src.db_id);
    const deletableIds = selectedSources
        .filter(src => ['depublished', 'failed'].includes(getSourceActionStatus(src)))
        .map(src => src.db_id);
    const hasSelectedBatchActions = selectedSources.length > 0;

    const refreshData = () => {
        if (document.hidden) return;
        fetch("/api/tasks").then(r => r.json()).then(setTasks);
        fetch("/api/sys/status").then(r => r.json()).then(setSysStatus);
    };

    useEffect(() => {
        const POLL_INTERVAL = 60000;
        let timerId;
        const handleVisibilityChange = () => {
            if (document.hidden) { clearInterval(timerId); } 
            else { refreshData(); timerId = setInterval(refreshData, POLL_INTERVAL); }
        };
        handleVisibilityChange();
        document.addEventListener("visibilitychange", handleVisibilityChange);
        return () => { clearInterval(timerId); document.removeEventListener("visibilitychange", handleVisibilityChange); };
    }, []);

    const openTaskStartConfig = async () => {
        const keyword = newKeyword.trim();
        if (!keyword) return;
        try {
            const payload = await fetch("/api/system/configs").then(r => r.json());
            const data = payload?.data || payload || {};
            setTaskStartConfig({
                keyword,
                crawl: data?.crawl || {},
                sourceChannels: data?.source_channels || {},
                llm: data?.llm || [],
            });
        } catch (err) {
            console.error("加载启动配置失败:", err);
            setConfirmDialog({
                title: '启动配置读取失败',
                description: '无法读取系统默认配置，请稍后重试。',
                confirmLabel: '我知道了',
                tone: 'warning',
                onConfirm: () => {}
            });
        }
    };

    const createTask = async (crawlConfigSnapshot) => {
        const keyword = (taskStartConfig?.keyword || newKeyword).trim();
        if (!keyword) return;
        await fetch("/api/tasks", { 
            method: "POST", 
            headers: { "Content-Type": "application/json" }, 
            body: JSON.stringify({ keyword, crawl_config: crawlConfigSnapshot })
        }); 
        setTaskStartConfig(null);
        setNewKeyword(""); 
        setActiveView("tasks"); 
        refreshData(); 
    };
    const pauseTask = (id) => { fetch(`/api/tasks/${id}/pause`, { method: "POST" }).then(refreshData); };
    const retryTask = (id) => { fetch(`/api/tasks/${id}/retry`, { method: "POST" }).then(refreshData); };
    const deleteTask = (id) => {
        setConfirmDialog({
            title: '确认删除任务',
            description: [
                '这会永久逻辑删除当前任务。',
                '删除后任务不会再出现在任务列表和分析资产视图中，请确认这是你要的操作。'
            ],
            confirmLabel: '确认删除任务',
            tone: 'danger',
            onConfirm: () => fetch(`/api/tasks/${id}`, { method: "DELETE" }).then(refreshData)
        });
    };
    
    const doBatchAddToSelection = async () => {
        if (selectedIds.length === 0) {
            alert("请先选择要加入选品的货源");
            return;
        }
        setBatchPublishing(true);
        
        const toAddIds = [...addableIds];
        if (toAddIds.length === 0) {
            setBatchPublishing(false);
            alert("当前勾选商品里，没有可加入选品的货源。");
            return;
        }
        
        toAddIds.forEach(dbId => {
            setBatchStatusMap(prev => ({ ...prev, [dbId]: 'selecting' }));
        });

        try {
            const resBatch = await fetch('/api/selection/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_ids: toAddIds })
            }).then(r => r.json());

            if (resBatch.success) {
                resBatch.success.forEach(item => {
                    const dbId = item.source_id;
                    const finalStatus = item.status === 'success' ? 'done' : 'selected';
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: finalStatus }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: finalStatus, msg: '已加入选品' } }));
                });
            }
            if (resBatch.failed) {
                resBatch.failed.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: item.msg } }));
                });
            }
            if (resBatch.error) {
                toAddIds.forEach(dbId => {
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: resBatch.error } }));
                });
            }
        } catch (e) {
            console.error("批量加入选品失败:", e);
            toAddIds.forEach(dbId => {
                setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: '网络或连接出错' } }));
            });
        }
        
        setBatchPublishing(false);
    };

    const executeSourceBatchDepublish = async (toDepublishIds) => {
        setBatchDepublishing(true);

        toDepublishIds.forEach(dbId => {
            setBatchStatusMap(prev => ({ ...prev, [dbId]: 'depublishing' }));
        });

        try {
            const resBatch = await fetch('/api/depublish/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_ids: toDepublishIds })
            }).then(r => r.json());

            if (resBatch.success) {
                resBatch.success.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'depublished' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'depublished', msg: '已下架' } }));
                });
            }
            if (resBatch.failed) {
                resBatch.failed.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: item.msg } }));
                });
            }
        } catch (e) {
            console.error("批量下架失败:", e);
            toDepublishIds.forEach(dbId => {
                setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: '网络或连接出错' } }));
            });
        }
        
        setBatchDepublishing(false);
    };

    const doBatchDepublish = async () => {
        if (selectedIds.length === 0) {
            alert("请先选择要批量下架的货源");
            return;
        }
        const toDepublishIds = [...depublishableIds];
        if (toDepublishIds.length === 0) {
            alert("当前勾选商品里，没有处于已上架状态的货源。");
            return;
        }
        setConfirmDialog({
            title: '确认批量下架',
            description: [
                `即将批量下架 ${toDepublishIds.length} 个已上架货源。`,
                '下架后商品会从闲鱼云端撤下，但本地发布记录会保留，方便后续继续处理。'
            ],
            confirmLabel: `确认下架 ${toDepublishIds.length} 项`,
            tone: 'warning',
            onConfirm: () => executeSourceBatchDepublish(toDepublishIds)
        });
    };

    const handleStatusLoaded = (dbId, status, result) => {
        setBatchStatusMap(prev => {
            if (prev[dbId] === 'publishing' || prev[dbId] === 'depublishing' || prev[dbId] === 'deleting') {
                return prev;
            }
            if (prev[dbId] === status) {
                return prev;
            }
            return { ...prev, [dbId]: status };
        });
        if (result) {
            setBatchResultMap(prev => {
                if (prev[dbId]) return prev;
                return { ...prev, [dbId]: result };
            });
        }
    };

    const executeSourceBatchDelete = async (toDeleteIds) => {
        setBatchDeleting(true);
        toDeleteIds.forEach(dbId => {
            setBatchStatusMap(prev => ({ ...prev, [dbId]: 'deleting' }));
        });

        try {
            const resBatch = await fetch('/api/delete/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_ids: toDeleteIds })
            }).then(r => r.json());

            if (resBatch.success) {
                resBatch.success.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'idle' }));
                    setBatchResultMap(prev => {
                        const copy = { ...prev };
                        delete copy[dbId];
                        return copy;
                    });
                });
            }
            if (resBatch.failed) {
                resBatch.failed.forEach(item => {
                    const dbId = item.source_id;
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: item.msg } }));
                });
            }
        } catch (e) {
            console.error("批量删除失败:", e);
            toDeleteIds.forEach(dbId => {
                setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                setBatchResultMap(prev => ({ ...prev, [dbId]: { status: 'failed', msg: '网络或连接出错' } }));
            });
        }

        setBatchDeleting(false);
    };

    const doBatchDelete = async () => {
        if (selectedIds.length === 0) {
            alert("请先选择要批量删除的货源");
            return;
        }
        const toDeleteIds = [...deletableIds];
        if (toDeleteIds.length === 0) {
            alert("当前勾选商品里，没有可删除的已选品、已下架或同步失败货源。");
            return;
        }
        setConfirmDialog({
            title: '确认批量删除',
            description: [
                `即将批量删除 ${toDeleteIds.length} 个货源记录。`,
                '已选品和同步失败商品只会清理本地记录；已下架商品会执行云端删除。此操作不可恢复。'
            ],
            confirmLabel: `确认删除 ${toDeleteIds.length} 项`,
            tone: 'danger',
            onConfirm: () => executeSourceBatchDelete(toDeleteIds)
        });
    };

    const getItemUsedChannels = (group) => {
        const usedMap = {};
        const hasSources = Array.isArray(group?.sources) && group.sources.length > 0;
        if (Array.isArray(group?.used_channels)) {
            group.used_channels.forEach(channel => {
                const channelId = channel?.channel_id || 'ali1688';
                if (!usedMap[channelId]) {
                    usedMap[channelId] = {
                        ...channel,
                        channel_id: channelId,
                        channel_type: channel?.channel_type || 'ali1688',
                        channel_label: channel?.channel_label || '1688 货源渠道',
                        source_count: hasSources ? 0 : Number(channel?.source_count || 0),
                    };
                }
            });
        }
        (group?.sources || []).forEach(source => {
            const channelId = source?.source_channel_id || 'ali1688';
            if (!usedMap[channelId]) {
                usedMap[channelId] = {
                    channel_id: channelId,
                    channel_type: source?.source_channel_type || 'ali1688',
                    channel_label: source?.source_channel_label || '1688 货源渠道',
                    source_count: 0,
                };
            }
            usedMap[channelId].source_count = Number(usedMap[channelId].source_count || 0) + 1;
        });
        return Object.values(usedMap);
    };

    const formatChannelCountLabel = (channel) => {
        const count = Number(channel?.source_count || 0);
        return `${channel?.channel_label || channel?.channel_id || '货源渠道'}（${count}）`;
    };

    const getItemCardChannels = (group, task) => {
        const itemChannels = getItemUsedChannels(group);
        if (itemChannels.length > 0) {
            return itemChannels;
        }
        return getTaskChannelSummaries(task).map(channel => ({
            ...channel,
            source_count: 0,
        }));
    };

    const getTaskUsedChannels = (task) => {
        if (Array.isArray(task?.used_channels) && task.used_channels.length > 0) {
            return task.used_channels;
        }
        return [];
    };

    const getTaskChannelSummaries = (task) => {
        if (Array.isArray(task?.channel_summaries) && task.channel_summaries.length > 0) {
            return task.channel_summaries.map((channel) => ({
                ...channel,
                filter_summary: normalizeChannelFilterSummary(channel?.filter_summary),
            }));
        }
        return getTaskUsedChannels(task).map((channel) => ({
            ...channel,
            filter_summary: normalizeChannelFilterSummary(channel?.filter_summary),
        }));
    };

    const getDetailFallbackFilterChannels = (item, task) => {
        const itemChannels = getItemUsedChannels(item);
        const isItemChannelSource = itemChannels.length > 0;
        const sourceChannels = isItemChannelSource ? itemChannels : getTaskChannelSummaries(task);
        return sourceChannels.map((channel) => ({
            ...channel,
            source_count: isItemChannelSource ? Number(channel?.source_count || 0) : 0,
            filter_summary: normalizeChannelFilterSummary(channel?.filter_summary),
        }));
    };

    const channelSearchFilterLabelMap = {
        rapid_invoice: '极速开票',
        selected_distributors: '分销严选',
        single_piece_drop_shipping: '一件代发',
        seven_day_return: '7天无理由',
        single_piece_free_shipping: '1件代发包邮',
        free_shipping: '包邮',
        freight_insurance_return: '退货包运费',
        real_factory_verified: '真实工厂认证',
        strength_verified: '实力认证',
        official_logistics: '官方物流',
        encrypted_waybill: '密文面单',
        douyin_encrypted_waybill: '抖音面单',
    };

    const nonConfigurableChannelSearchFilterKeys = new Set(['encrypted_waybill']);
    const isRenderableChannelSearchFilterKey = (filterKey) => !nonConfigurableChannelSearchFilterKeys.has(filterKey);
    const getChannelFilterLabel = (filterKey) => channelSearchFilterLabelMap[filterKey] || filterKey;

    const renderTaskStartConfigSummary = (task) => {
        const cfg = task?.crawl_config_snapshot || {};
        if (!cfg || Object.keys(cfg).length === 0) {
            return (
                <details className="mt-3 rounded-lg border border-border-hairline bg-surface-container-low px-3 py-2 text-xs text-secondary" onClick={e => e.stopPropagation()}>
                    <summary className="cursor-pointer font-semibold text-on-surface">查看启动配置</summary>
                    <div className="mt-2">该任务创建时尚未记录配置快照。</div>
                </details>
            );
        }
        const sourceLimit = Number(cfg.source_limit_1688 || 10);
        const grossRate = Math.round(normalizeGrossProfitRate(cfg.gross_profit_rate) * 100);
        const models = Array.isArray(cfg.source_filter_models) ? cfg.source_filter_models : [];
        const channels = Array.isArray(cfg.enabled_source_channels) ? cfg.enabled_source_channels : [];
        const filters = Array.isArray(cfg.channel_search_filters) ? cfg.channel_search_filters : [];

        return (
            <details className="mt-3 rounded-lg border border-border-hairline bg-surface-container-low px-3 py-2 text-xs text-secondary" onClick={e => e.stopPropagation()}>
                <summary className="cursor-pointer font-semibold text-on-surface">查看启动配置</summary>
                <div className="mt-2 space-y-2">
                    <div className="flex flex-wrap gap-2">
                        <span className="px-2 py-0.5 rounded bg-surface-container-lowest border border-border-hairline">1688 抓取 {sourceLimit} 条</span>
                        <span className="px-2 py-0.5 rounded bg-surface-container-lowest border border-border-hairline">毛利率 {grossRate}%</span>
                        <span className="px-2 py-0.5 rounded bg-surface-container-lowest border border-border-hairline">
                            模型：{models.length > 0 ? models.join('、') : '全部已保存模型'}
                        </span>
                    </div>
                    {channels.length > 0 && (
                        <div className="space-y-1">
                            <div className="font-semibold text-on-surface">货源账号</div>
                            <div className="flex flex-wrap gap-1.5">
                                {channels.map(channel => (
                                    <span key={`task-cfg-channel-${task.id}-${channel.channel_id}`} className="px-2 py-0.5 rounded-full bg-primary/8 text-primary border border-primary/15">
                                        {channel.channel_id}：{Array.isArray(channel.account_ids) && channel.account_ids.length > 0 ? channel.account_ids.join('、') : '未选择账号'}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                    {filters.length > 0 && (
                        <div className="space-y-1">
                            <div className="font-semibold text-on-surface">货源筛选项</div>
                            <div className="flex flex-wrap gap-1.5">
                                {filters.map(entry => {
                                    const enabledKeys = Object.entries(entry.filters || {})
                                        .filter(([key, enabled]) => !!enabled && isRenderableChannelSearchFilterKey(key))
                                        .map(([key]) => key);
                                    return (
                                        <span key={`task-cfg-filter-${task.id}-${entry.channel_id}`} className="px-2 py-0.5 rounded-full bg-surface-container-lowest border border-border-hairline">
                                            {entry.channel_id}：{enabledKeys.length > 0 ? enabledKeys.map(getChannelFilterLabel).join('、') : '未启用筛选项'}
                                        </span>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            </details>
        );
    };

    const buildEmptyChannelFilterSummary = () => ({
        configured: [],
        configuredPending: [],
        queryInjected: [],
        applied: [],
        unapplied: [],
        unsupported: false,
        configuredFilterCount: 0,
        filterStatusMap: {},
        queryVerificationDetails: {},
        mappingStage: '',
        mappingNotes: '',
        runtimeAuditStage: '',
        runtimeAuditSource: '',
        legacyMissingSnapshot: false,
        hasRuntimeSignal: false,
    });

    const summarizeChannelFilterSnapshot = (snapshot, channelType = '') => {
        if (!snapshot || typeof snapshot !== 'object') {
            return buildEmptyChannelFilterSummary();
        }
        const filterStatusMap = snapshot.filter_status_map && typeof snapshot.filter_status_map === 'object'
            ? snapshot.filter_status_map
            : {};
        const configuredRaw = Array.isArray(snapshot.configured_enabled_filter_keys)
            ? snapshot.configured_enabled_filter_keys
            : Array.isArray(snapshot.configured_filter_keys)
                ? snapshot.configured_filter_keys
            : Array.isArray(snapshot.enabled_filter_keys)
                ? snapshot.enabled_filter_keys
                : Object.entries(snapshot.filters || {})
                    .filter(([, enabled]) => !!enabled)
                    .map(([key]) => key);
        const configured = configuredRaw.filter(isRenderableChannelSearchFilterKey);
        const queryInjected = Object.entries(filterStatusMap)
            .filter(([key, meta]) => isRenderableChannelSearchFilterKey(key) && meta?.status === 'query_injected_pending_verification')
            .map(([key]) => key);
        const applied = Object.entries(filterStatusMap)
            .filter(([key, meta]) => isRenderableChannelSearchFilterKey(key) && meta?.status === 'applied')
            .map(([key]) => key);
        const unapplied = Object.entries(filterStatusMap)
            .filter(([key, meta]) => isRenderableChannelSearchFilterKey(key) && meta?.status === 'unapplied')
            .map(([key]) => key);
        const fallbackQueryInjected = Array.isArray(snapshot.query_injected_filter_keys)
            ? snapshot.query_injected_filter_keys.filter(isRenderableChannelSearchFilterKey)
            : [];
        const fallbackApplied = Array.isArray(snapshot.applied_filter_keys)
            ? snapshot.applied_filter_keys.filter(isRenderableChannelSearchFilterKey)
            : [];
        const fallbackQueryInjectedPending = fallbackQueryInjected.filter((key) => !fallbackApplied.includes(key));
        const fallbackUnapplied = (Array.isArray(snapshot.unapplied_filter_keys) ? snapshot.unapplied_filter_keys : [])
            .filter((key) => isRenderableChannelSearchFilterKey(key) && !fallbackQueryInjected.includes(key));
        const topLevelQueryVerificationDetails = snapshot.query_verification_details && typeof snapshot.query_verification_details === 'object'
            ? snapshot.query_verification_details
            : snapshot.verification_details && typeof snapshot.verification_details === 'object'
                ? snapshot.verification_details
                : {};
        const statusMapVerificationDetails = Object.entries(filterStatusMap).reduce((acc, [key, meta]) => {
            if (meta?.verification_detail && typeof meta.verification_detail === 'object') {
                acc[key] = meta.verification_detail;
            }
            return acc;
        }, {});
        const queryVerificationDetails = {
            ...statusMapVerificationDetails,
            ...topLevelQueryVerificationDetails,
        };
        const resolvedChannelType = String(snapshot.channel_type || channelType || '').trim().toLowerCase();
        const unsupported = !!resolvedChannelType && resolvedChannelType !== 'ali1688';
        const configuredPendingReasonSet = new Set([
            'runtime_mapping_not_implemented_yet',
            'query_candidate_not_validated',
            'semantic_combo_not_confirmed',
            'snapshot_only_until_semantics_confirmed',
            'special_panel_unmapped',
            'special_panel_entry_detected_unmapped',
        ]);
        const configuredPending = configured.filter((filterKey) => {
            const filterMeta = filterStatusMap?.[filterKey];
            if (!filterMeta || typeof filterMeta !== 'object') {
                return true;
            }
            if (filterMeta.status !== 'unapplied') {
                return false;
            }
            const perFilterMappingStage = String(filterMeta.mapping_stage || '').trim();
            const reason = String(filterMeta.reason || '').trim();
            return perFilterMappingStage === 'snapshot_only' || configuredPendingReasonSet.has(reason);
        });
        const appliedSet = new Set(applied);
        const queryInjectedSet = new Set(queryInjected);
        const configuredPendingSet = new Set(configuredPending);
        const unappliedStrict = unapplied.filter((filterKey) => (
            !appliedSet.has(filterKey)
            && !queryInjectedSet.has(filterKey)
            && !configuredPendingSet.has(filterKey)
        ));
        return {
            configured,
            configuredPending,
            queryInjected: queryInjected.length > 0 || applied.length > 0 || unapplied.length > 0 ? queryInjected : fallbackQueryInjectedPending,
            applied: applied.length > 0 || queryInjected.length > 0 || unapplied.length > 0 ? applied : fallbackApplied,
            unapplied: unapplied.length > 0 || queryInjected.length > 0 || applied.length > 0 ? unappliedStrict : fallbackUnapplied,
            unsupported,
            configuredFilterCount: configured.length,
            filterStatusMap,
            queryVerificationDetails,
            mappingStage: snapshot.mapping_stage || '',
            mappingNotes: snapshot.mapping_notes || '',
            runtimeAuditStage: String(snapshot.runtime_audit_stage || '').trim(),
            runtimeAuditSource: String(snapshot.runtime_audit_source || '').trim(),
            legacyMissingSnapshot: false,
            hasRuntimeSignal: applied.length > 0 || queryInjected.length > 0 || unapplied.length > 0,
        };
    };

    const normalizeChannelFilterSummary = (summary, fallbackSnapshot = null, channelType = '') => {
        if (summary && typeof summary === 'object') {
            const configured = Array.isArray(summary.configured)
                ? summary.configured.filter(isRenderableChannelSearchFilterKey)
                : [];
            return {
                ...buildEmptyChannelFilterSummary(),
                configured,
                configuredPending: Array.isArray(summary.configuredPending)
                    ? summary.configuredPending.filter(isRenderableChannelSearchFilterKey)
                    : Array.isArray(summary.configured_pending)
                        ? summary.configured_pending.filter(isRenderableChannelSearchFilterKey)
                        : [],
                queryInjected: Array.isArray(summary.queryInjected)
                    ? summary.queryInjected.filter(isRenderableChannelSearchFilterKey)
                    : Array.isArray(summary.query_injected)
                        ? summary.query_injected.filter(isRenderableChannelSearchFilterKey)
                        : [],
                applied: Array.isArray(summary.applied) ? summary.applied.filter(isRenderableChannelSearchFilterKey) : [],
                unapplied: Array.isArray(summary.unapplied) ? summary.unapplied.filter(isRenderableChannelSearchFilterKey) : [],
                unsupported: !!summary.unsupported,
                configuredFilterCount: Number.isFinite(Number(summary.configuredFilterCount))
                    ? Number(summary.configuredFilterCount)
                    : Number.isFinite(Number(summary.configured_filter_count))
                        ? Number(summary.configured_filter_count)
                        : configured.length,
                filterStatusMap: summary.filterStatusMap && typeof summary.filterStatusMap === 'object'
                    ? summary.filterStatusMap
                    : summary.filter_status_map && typeof summary.filter_status_map === 'object'
                        ? summary.filter_status_map
                        : {},
                queryVerificationDetails: summary.queryVerificationDetails && typeof summary.queryVerificationDetails === 'object'
                    ? summary.queryVerificationDetails
                    : summary.query_verification_details && typeof summary.query_verification_details === 'object'
                        ? summary.query_verification_details
                        : summary.verification_details && typeof summary.verification_details === 'object'
                            ? summary.verification_details
                            : {},
                mappingStage: String(summary.mappingStage || summary.mapping_stage || '').trim(),
                mappingNotes: String(summary.mappingNotes || summary.mapping_notes || '').trim(),
                runtimeAuditStage: String(summary.runtimeAuditStage || summary.runtime_audit_stage || '').trim(),
                runtimeAuditSource: String(summary.runtimeAuditSource || summary.runtime_audit_source || '').trim(),
                legacyMissingSnapshot: !!(summary.legacyMissingSnapshot ?? summary.legacy_missing_snapshot),
                hasRuntimeSignal: !!(summary.hasRuntimeSignal ?? summary.has_runtime_signal),
            };
        }
        if (fallbackSnapshot && typeof fallbackSnapshot === 'object') {
            return summarizeChannelFilterSnapshot(fallbackSnapshot, channelType);
        }
        return buildEmptyChannelFilterSummary();
    };

    const hasRenderableChannelFilterSummary = (summary) => (
        !!summary
        && (
            summary.configured.length > 0
            || summary.configuredPending.length > 0
            || summary.queryInjected.length > 0
            || summary.applied.length > 0
            || summary.unapplied.length > 0
            || summary.legacyMissingSnapshot
            || summary.unsupported
            || !!summary.runtimeAuditStage
        )
    );

    const formatRuntimeAuditStage = (stage) => {
        const stageText = String(stage || '').trim();
        const stageLabelMap = {
            initialized: '运行审计：已初始化',
            image_download_failed: '运行审计：图片下载失败',
            prewarm_failed: '运行审计：首页预热失败',
            image_search_home_failed: '运行审计：图搜首页失败',
            direct_url_fallback_failed: '运行审计：直连兜底失败',
            query_filter_post_navigation_verified: '运行审计：query 跳转后已验证',
            query_filter_navigation_failed: '运行审计：query 跳转失败',
            query_filter_in_place_verified: '运行审计：query 原位已验证',
            visible_filter_toggle_checked: '运行审计：已检查可见筛选项',
            special_panel_candidate_checked: '运行审计：已检查特殊面板入口',
            parse_failed_final: '运行审计：最终解析失败',
            summary_written: '运行审计：已写入货源结果',
        };
        if (!stageText) {
            return '';
        }
        if (stageText.startsWith('html_text_probe_attempt_')) {
            const attempt = stageText.replace('html_text_probe_attempt_', '');
            return `运行审计：第 ${attempt} 次文本探测`;
        }
        return stageLabelMap[stageText] || `运行审计：${stageText}`;
    };

    const getFilterStatusReasonText = (reason) => {
        const reasonMap = {
            query_filter_injected_pending_verification: '已注入结果页，但结果级验证仍未完成',
            query_filter_not_applied_in_runtime: '当前 runtime 还未实际注入该 query 筛选项',
            query_filter_navigation_failed: '已尝试跳转到带筛选参数的结果页，但页面导航失败',
            query_param_not_retained: '已尝试注入筛选参数，但最终结果页未保留目标参数',
            runtime_mapping_not_implemented_yet: '当前仅完成配置透传，真实映射尚未接入',
            query_candidate_not_validated: '已识别到候选参数，但还未验证为真实生效',
            ui_selector_not_stable: '页面控件定位暂未稳定，尚未进入真实生效',
            ui_apply_not_observed: '页面控件已尝试执行，但当前未观察到稳定的结果变化',
            special_panel_unmapped: '特殊入口尚未映射到可稳定执行的操作流',
            special_panel_entry_detected_unmapped: '结果页已观察到特殊入口线索，但二级面板动作链路尚未映射完成',
            special_panel_open_failed: '特殊入口已识别，但打开二级面板失败',
            snapshot_only_until_semantics_confirmed: '语义仍待确认，暂不宣称已生效',
            semantic_combo_not_confirmed: '组合语义尚未确认，暂不宣称该项可独立生效',
        };
        return reasonMap[reason] || reason || '';
    };

    const formatQueryVerificationDetail = (detail) => {
        if (!detail || typeof detail !== 'object') {
            return '';
        }
        const layoutLabelMap = {
            image_result_filter_bar: '图搜结果页筛选栏',
            standard_search_filter_bar: '标准搜索页筛选栏',
            unknown: '未识别页面布局',
        };
        const selectorStrategyLabelMap = {
            image_config_filter: '图搜配置筛选容器',
            image_config_label: '图搜配置标签',
            image_bottom_filter_option: '图搜底部筛选项',
            image_bottom_option_label: '图搜底部筛选标签',
            standard_search_filter_item: '标准搜索筛选项',
            standard_select_item: '标准搜索下拉项',
            standard_col_item: '标准搜索列项',
            text_fallback: '文本兜底节点',
        };
        const selectorResolutionModeLabelMap = {
            selector_candidate: '稳定 selector',
            text_fallback: '文本兜底',
        };
        const semanticConclusionLabelMap = {
            dependency_pair_incomplete: '语义结论：依赖组合未齐，暂不能判断独立语义',
            dependency_pair_ready_pending_runtime: '语义结论：依赖组合已齐备，待真实动作验证',
            dependency_pair_strong_verified: '语义结论：依赖组合已通过真实强证据确认',
            independent_entry_observed_pending_result_validation: '语义结论：已观察到独立入口，待结果侧验证',
            independent_entry_no_result_shift: '语义结论：独立入口可点击，但结果侧暂未观察到变化',
            independent_entry_result_shift_observed: '语义结论：独立入口动作后已观察到结果变化',
        };
        const specialPanelConclusionLabelMap = {
            entry_signal_detected_pending_panel_mapping: '入口结论：已观察到特殊入口线索，待面板动作映射',
            panel_open_or_toggle_failed: '入口结论：已尝试打开面板或切换筛选，但动作未完成',
            panel_action_applied_no_result_shift: '入口结论：面板动作已命中，但结果侧暂未观察到变化',
            panel_action_result_shift_observed: '入口结论：面板动作后已观察到结果变化',
            panel_active_condition_observed: '入口结论：结果页已存在该筛选的已选条件',
        };
        const verificationModeLabelMap = {
            in_place_url: '原位 URL 校验',
            post_navigation_url: '跳转后 URL 校验',
            navigation_failed: '跳转失败校验',
            dom_toggle_action: '筛选项勾选动作校验',
            dom_panel_action: '面板动作校验',
        };
        if (detail.probe_mode === 'html_text_scan') {
            const matchedTerms = Array.isArray(detail.matched_terms)
                ? detail.matched_terms.filter(Boolean)
                : [];
            const probeTerms = Array.isArray(detail.probe_terms)
                ? detail.probe_terms.filter(Boolean)
                : [];
            const detailParts = [];
            const semanticConclusionLabel = semanticConclusionLabelMap[String(detail.semantic_conclusion || '').trim()];
            if (semanticConclusionLabel) {
                detailParts.push(semanticConclusionLabel);
            }
            const specialPanelConclusionLabel = specialPanelConclusionLabelMap[String(detail.special_panel_conclusion || '').trim()];
            if (specialPanelConclusionLabel) {
                detailParts.push(specialPanelConclusionLabel);
            }
            if (matchedTerms.length > 0) {
                detailParts.push(`页面文案命中：${matchedTerms.join(' / ')}`);
            } else if (probeTerms.length > 0) {
                detailParts.push(`探测文案：${probeTerms.join(' / ')}`);
            }
            if (detail.observation_scope === 'result_page_text') {
                detailParts.push('证据来源：结果页文本');
            }
            if (detail.text_visible === true) {
                detailParts.push('页面可见：是');
            } else if (detail.text_visible === false) {
                detailParts.push('页面可见：否');
            }
            if (detail.entry_signal_detected === true) {
                detailParts.push('已观察到入口线索');
            }
            const entrySignalType = String(detail.entry_signal_type || '').trim();
            if (entrySignalType === 'text_term') {
                detailParts.push('入口线索：页面文案命中');
            } else if (entrySignalType) {
                detailParts.push(`入口线索：${entrySignalType}`);
            }
            if (Array.isArray(detail.semantic_dependencies) && detail.semantic_dependencies.length > 0) {
                const dependencyLabels = detail.semantic_dependencies
                    .map((dependencyKey) => getChannelFilterLabel(dependencyKey))
                    .filter(Boolean);
                if (dependencyLabels.length > 0) {
                        detailParts.push(
                            detail.dependencies_enabled
                                ? `依赖已开启：${dependencyLabels.join(' + ')}`
                                : `依赖未齐：${dependencyLabels.join(' + ')}`
                    );
                }
            }
            if (detail.semantic_verification_stage === 'dependency_pair_enabled') {
                detailParts.push('阶段：依赖组合已齐备，待真实动作验证');
            } else if (detail.semantic_verification_stage === 'dependency_pair_incomplete') {
                detailParts.push('阶段：依赖组合未齐备');
            }
            if (detail.next_required_action === 'panel_open_and_toggle') {
                detailParts.push('下一步：补齐面板打开与勾选动作');
            }
            const verificationMode = String(detail.verification_mode || '').trim();
            if (verificationMode) {
                detailParts.push(`校验方式：${verificationModeLabelMap[verificationMode] || verificationMode}`);
            }
            const resultUrl = String(detail.result_url || '').trim();
            if (resultUrl) {
                detailParts.push(`结果页：${resultUrl}`);
            }
            return detailParts.join(' · ');
        }
        if (detail.probe_mode === 'dom_toggle_action' || detail.probe_mode === 'dom_panel_action') {
            const detailParts = [];
            const semanticConclusionLabel = semanticConclusionLabelMap[String(detail.semantic_conclusion || '').trim()];
            if (semanticConclusionLabel) {
                detailParts.push(semanticConclusionLabel);
            }
            const specialPanelConclusionLabel = specialPanelConclusionLabelMap[String(detail.special_panel_conclusion || '').trim()];
            if (specialPanelConclusionLabel) {
                detailParts.push(specialPanelConclusionLabel);
            }
            const layoutLabel = layoutLabelMap[String(detail.page_filter_layout || '').trim()] || String(detail.page_filter_layout || '').trim();
            if (layoutLabel) {
                detailParts.push(`页面布局：${layoutLabel}`);
            }
            const selectorStrategy = String(detail.entry_selector_strategy || '').trim();
            if (selectorStrategy) {
                const selectorLabel = selectorStrategyLabelMap[selectorStrategy] || selectorStrategy;
                detailParts.push(`点击入口：${selectorLabel}`);
            }
            const selectorResolutionMode = String(detail.selector_resolution_mode || '').trim();
            if (selectorResolutionMode) {
                const selectorResolutionLabel = selectorResolutionModeLabelMap[selectorResolutionMode] || selectorResolutionMode;
                detailParts.push(`定位方式：${selectorResolutionLabel}`);
            }
            if (Array.isArray(detail.selector_candidates_tried) && detail.selector_candidates_tried.length > 0) {
                const selectorStrategies = detail.selector_candidates_tried
                    .map((candidate) => {
                        const strategy = String(candidate?.strategy || '').trim();
                        return selectorStrategyLabelMap[strategy] || strategy;
                    })
                    .filter(Boolean);
                if (selectorStrategies.length > 0) {
                    detailParts.push(`候选定位链路：${selectorStrategies.join(' -> ')}`);
                }
            }
            if (detail.text_fallback_considered === true) {
                detailParts.push('已评估文本兜底');
            } else if (detail.text_fallback_considered === false) {
                detailParts.push('未退化到文本兜底');
            }
            if (detail.probe_mode === 'dom_panel_action') {
                const triggerText = String(detail.panel_trigger_text || '').trim();
                if (triggerText) {
                    detailParts.push(`面板触发器：${triggerText}`);
                }
                if (detail.panel_trigger_clicked === true) {
                    detailParts.push('已尝试打开二级面板');
                }
                if (Array.isArray(detail.panel_trigger_candidates) && detail.panel_trigger_candidates.length > 0) {
                    detailParts.push(`触发词顺序：${detail.panel_trigger_candidates.join(' / ')}`);
                }
                const panelVisibleVia = String(detail.panel_visible_via || '').trim();
                if (panelVisibleVia === 'term_visible') {
                    detailParts.push('面板可见来源：入口直接可见');
                } else if (panelVisibleVia) {
                    detailParts.push(`面板可见来源：${panelVisibleVia}`);
                }
            }
            if (detail.entry_click_attempted === true) {
                detailParts.push(
                    detail.entry_click_succeeded === true
                        ? '已执行点击动作'
                        : '已尝试点击但未成功'
                );
            }
            if (detail.panel_term_visible_before_action === true || detail.panel_term_visible_after_action === true) {
                detailParts.push(
                    `入口可见：动作前${detail.panel_term_visible_before_action ? '是' : '否'} / 动作后${detail.panel_term_visible_after_action ? '是' : '否'}`
                );
            }
            if (
                typeof detail.panel_term_selected_before_action === 'boolean'
                || typeof detail.panel_term_selected_after_action === 'boolean'
            ) {
                detailParts.push(
                    `选中态：动作前${detail.panel_term_selected_before_action ? '是' : '否'} / 动作后${detail.panel_term_selected_after_action ? '是' : '否'}`
                );
            }
            const selectedVia = String(detail.panel_term_selected_via_after_action || '').trim();
            if (selectedVia === 'active_condition_text') {
                detailParts.push('选中来源：结果页已选条件条');
            } else if (selectedVia) {
                detailParts.push(`选中来源：${selectedVia}`);
            }
            if (detail.independent_ui_entry_observed === true) {
                detailParts.push('已观察到独立 UI 入口');
            }
            if (detail.result_url_changed === true) {
                detailParts.push('已观察到结果页 URL 变化');
            }
            if (detail.result_signature_changed === true) {
                detailParts.push('已观察到结果签名变化');
            } else if (
                detail.result_signature_before_action
                || detail.result_signature_after_action
            ) {
                const beforeCount = Number(detail.result_signature_before_action?.item_count || 0);
                const afterCount = Number(detail.result_signature_after_action?.item_count || 0);
                detailParts.push(`结果签名：动作前${beforeCount}条 / 动作后${afterCount}条`);
            }
            if (detail.semantic_verification_stage === 'direct_entry_result_shift_observed') {
                detailParts.push('阶段：独立入口动作后已观察到结果变化');
            } else if (detail.semantic_verification_stage === 'direct_entry_result_shift_not_observed') {
                detailParts.push('阶段：独立入口动作后暂未观察到结果变化');
            } else if (detail.semantic_verification_stage === 'dependency_pair_strong_verified') {
                detailParts.push('阶段：依赖组合已通过真实强证据确认');
            }
            if (detail.observation_scope === 'result_page_text') {
                detailParts.push('证据来源：结果页可见筛选区');
            }
            if (detail.next_required_action === 'panel_open_and_toggle') {
                detailParts.push('下一步：继续收紧面板打开与勾选闭环');
            }
            const verificationMode = String(detail.verification_mode || '').trim();
            if (verificationMode) {
                detailParts.push(`校验方式：${verificationModeLabelMap[verificationMode] || verificationMode}`);
            }
            const resultUrl = String(detail.result_url || '').trim();
            if (resultUrl) {
                detailParts.push(`结果页：${resultUrl}`);
            }
            return detailParts.join(' · ');
        }
        const verificationMode = String(detail.verification_mode || '').trim();
        if (verificationMode) {
            const verificationModeLabel = verificationModeLabelMap[verificationMode] || verificationMode;
            if (verificationMode === 'navigation_failed' && detail.attempted_result_url) {
                return `校验方式：${verificationModeLabel} · 目标结果页：${detail.attempted_result_url}`;
            }
            return `校验方式：${verificationModeLabel}`;
        }
        const matchedParams = detail.matched_params && typeof detail.matched_params === 'object'
            ? Object.entries(detail.matched_params)
                .filter(([, value]) => !!value)
                .map(([key, value]) => `${key}=${value}`)
            : [];
        if (matchedParams.length > 0) {
            return matchedParams.join(' · ');
        }
        const observedValues = Array.isArray(detail.observed_values) ? detail.observed_values : [];
        if (observedValues.length > 0) {
            return `观察值：${observedValues.join(', ')}`;
        }
        const expectedValues = Array.isArray(detail.expected_values) ? detail.expected_values : [];
        if (expectedValues.length > 0) {
            return `目标值：${expectedValues.join(', ')}`;
        }
        if (detail.attempted_result_url) {
            return `目标结果页：${detail.attempted_result_url}`;
        }
        return '';
    };

    const formatFilterMappingHint = (filterMeta, filterKey) => {
        if (!filterMeta || typeof filterMeta !== 'object') {
            return '';
        }
        const semanticDependencies = Array.isArray(filterMeta.semantic_dependencies)
            ? filterMeta.semantic_dependencies
                .map((dependencyKey) => getChannelFilterLabel(dependencyKey))
                .filter(Boolean)
            : [];
        const verificationEntry = String(filterMeta.verification_entry || '').trim();
        const mappingHint = String(filterMeta.mapping_hint || '').trim();
        const hintParts = [];
        if (semanticDependencies.length > 0) {
            hintParts.push(`依赖项：${semanticDependencies.join(' + ')}`);
        }
        if (verificationEntry === 'config_filter_panel') {
            hintParts.push('验证入口：配置筛选面板');
        } else if (verificationEntry === 'search_result_semantic_combo') {
            hintParts.push('验证入口：结果页组合语义比对');
        } else if (verificationEntry === 'search_result_checkbox') {
            hintParts.push('验证入口：结果页筛选区 checkbox');
        } else if (verificationEntry) {
            hintParts.push(`验证入口：${verificationEntry}`);
        }
        if (filterMeta.observation_scope === 'result_page_text') {
            hintParts.push('观察范围：结果页文本');
        }
        if (filterMeta.next_required_action === 'panel_open_and_toggle') {
            hintParts.push('后续动作：面板打开与勾选');
        }
        if (mappingHint) {
            hintParts.push(mappingHint);
        }
        return hintParts.join(' · ');
    };

    const formatSourceFilterSummaryChipTitle = (filterSummary, filterKey) => {
        if (!filterSummary || typeof filterSummary !== 'object' || !filterKey) {
            return '';
        }
        const filterMeta = filterSummary.filterStatusMap?.[filterKey];
        const detailText = formatQueryVerificationDetail(
            filterSummary.queryVerificationDetails?.[filterKey]
        );
        const reasonText = getFilterStatusReasonText(filterMeta?.reason);
        const hintText = formatFilterMappingHint(filterMeta, filterKey);
        return [detailText, reasonText, hintText].filter(Boolean).join(' · ');
    };

    const getSourcePageOrder = (source) => {
        const pageIndex = Number(source?.page_original_index || 0);
        const normalizedIndex = pageIndex > 0 ? pageIndex : Number.MAX_SAFE_INTEGER;
        const dbId = Number(source?.db_id || 0);
        return [normalizedIndex, dbId];
    };

    const getSourceMinPrice = (source) => {
        const price = Number(source?.min_price);
        return Number.isFinite(price) ? price : Number.MAX_SAFE_INTEGER;
    };

    const formatSourceDisplayPrice = (source) => {
        const price = source?.min_price ?? '';
        const suffix = Number(source?.sku_count || 0) > 1 ? '起' : '';
        return `¥${price}${suffix}`;
    };

    const sortSourcesByRule = (sources = [], sortRule = "price_asc") => [...sources].sort((left, right) => {
        const [leftIndex, leftId] = getSourcePageOrder(left);
        const [rightIndex, rightId] = getSourcePageOrder(right);
        if (sortRule === "page_original") {
            return leftIndex - rightIndex || leftId - rightId;
        }
        const priceDiff = getSourceMinPrice(left) - getSourceMinPrice(right);
        return priceDiff || leftIndex - rightIndex || leftId - rightId;
    });

    const formatTaskChannelSummaryText = (channel) => {
        const summary = normalizeChannelFilterSummary(channel?.filter_summary);
        if (summary.unsupported) {
            return '当前渠道不支持';
        }
        if (summary.legacyMissingSnapshot) {
            return '历史快照缺失';
        }
        const parts = [];
        if (summary.configured.length > 0) {
            const labels = summary.configured.map(key => getChannelFilterLabel(key));
            parts.push(`筛选项：${labels.join('、')}`);
        }
        return parts.join(' · ');
    };

    const buildChannelGroupsFromSources = (sources = []) => {
        const hasMeaningfulChannelFilterSnapshot = (snapshot) => {
            if (!snapshot || typeof snapshot !== 'object') {
                return false;
            }
            if (snapshot.mapping_stage && snapshot.mapping_stage !== 'snapshot_only') {
                return true;
            }
            const listKeys = [
                'configured_filter_keys',
                'configured_enabled_filter_keys',
                'enabled_filter_keys',
                'applied_filter_keys',
                'query_injected_filter_keys',
                'unapplied_filter_keys',
            ];
            if (listKeys.some((key) => Array.isArray(snapshot[key]) && snapshot[key].length > 0)) {
                return true;
            }
            const filterMap = snapshot.configured_filters && typeof snapshot.configured_filters === 'object'
                ? snapshot.configured_filters
                : snapshot.filters && typeof snapshot.filters === 'object'
                    ? snapshot.filters
                    : null;
            return !!filterMap && Object.values(filterMap).some((value) => !!value);
        };
        const groups = [];
        const groupMap = {};
        sources.forEach(source => {
            const channelId = source?.source_channel_id || 'ali1688';
            if (!groupMap[channelId]) {
                groupMap[channelId] = {
                    channel_id: channelId,
                    channel_type: source?.source_channel_type || 'ali1688',
                    channel_label: source?.source_channel_label || '1688 货源渠道',
                    source_count: 0,
                    account_ids: [],
                    account_labels: [],
                    source_filter_snapshot: source?.source_filter_snapshot || {},
                    sources: [],
                };
                groups.push(groupMap[channelId]);
            }
            const currentGroup = groupMap[channelId];
            currentGroup.sources.push(source);
            currentGroup.source_count += 1;
            if (
                hasMeaningfulChannelFilterSnapshot(source?.source_filter_snapshot)
                && !hasMeaningfulChannelFilterSnapshot(currentGroup.source_filter_snapshot)
            ) {
                currentGroup.source_filter_snapshot = source.source_filter_snapshot;
            }
            if (source?.source_account_id && !currentGroup.account_ids.includes(source.source_account_id)) {
                currentGroup.account_ids.push(source.source_account_id);
            }
            if (source?.source_account_label && !currentGroup.account_labels.includes(source.source_account_label)) {
                currentGroup.account_labels.push(source.source_account_label);
            }
        });
        return groups;
    };

    const loadTaskResults = async (task) => {
        const resp = await fetch(`/api/task_details/${task.id}`);
        const data = await resp.json();
        setDetailedItems(data.details || []);
        setResultPage(1);
        setSelectedTask(task);
        setActiveView("results");
    };
    
    const enterItemDetail = (group) => {
        setSelectedItem(group);
        setSourceChannelFilter("all");
        setSourceSortRule("price_asc");
        setSourceListPage(1);
        setActiveView("item_detail");
    };

    const enterOrderDetail = (orderNo) => {
        setSelectedOrderNo(orderNo);
        setActiveView("order_detail");
    };
    const completedTasks = tasks.filter(t => t.status === '已完成');
    const resolvedChannelGroups = useMemo(() => {
        if (!selectedItem) return [];
        const hasApiProvidedChannelGroups = Array.isArray(selectedItem.channel_groups) && selectedItem.channel_groups.length > 0;
        const rawGroups = hasApiProvidedChannelGroups
            ? selectedItem.channel_groups
            : buildChannelGroupsFromSources(selectedItem.sources || []);
        const decorateGroup = (group) => {
            const normalizedSources = sortSourcesByRule(group.sources || [], sourceSortRule);
            const [firstPageOriginalIndex] = normalizedSources.length > 0
                ? getSourcePageOrder(normalizedSources[0])
                : [Number.MAX_SAFE_INTEGER, 0];
            const normalizedFilterSummary = group.filter_summary && typeof group.filter_summary === 'object'
                ? normalizeChannelFilterSummary(
                    group.filter_summary,
                    group.source_filter_snapshot,
                    group.channel_type
                )
                : summarizeChannelFilterSnapshot(group.source_filter_snapshot, group.channel_type);
            return {
                ...group,
                sources: normalizedSources,
                first_page_original_index: Number.isFinite(Number(group?.first_page_original_index))
                    ? Number(group.first_page_original_index)
                    : firstPageOriginalIndex,
                filter_summary: normalizedFilterSummary,
            };
        };
        const decoratedGroups = rawGroups
            .map(decorateGroup)
            .filter(group => sourceChannelFilter === "all" || group.channel_id === sourceChannelFilter);
        if (sourceSortRule === "page_original") {
            return decoratedGroups.sort((left, right) => {
                if (left.first_page_original_index !== right.first_page_original_index) {
                    return left.first_page_original_index - right.first_page_original_index;
                }
                return String(left.channel_label || left.channel_id || '').localeCompare(
                    String(right.channel_label || right.channel_id || ''),
                    'zh-CN'
                );
            });
        }
        return decoratedGroups.sort((left, right) => {
            const leftMinPrice = Math.min(...(left.sources || []).map(getSourceMinPrice));
            const rightMinPrice = Math.min(...(right.sources || []).map(getSourceMinPrice));
            const priceDiff = leftMinPrice - rightMinPrice;
            if (priceDiff !== 0) return priceDiff;
            if (left.first_page_original_index !== right.first_page_original_index) {
                return left.first_page_original_index - right.first_page_original_index;
            }
            return String(left.channel_label || left.channel_id || '').localeCompare(
                String(right.channel_label || right.channel_id || ''),
                'zh-CN'
            );
        });
    }, [selectedItem, sourceChannelFilter, sourceSortRule]);
    const sourceSortRuleDescription = sourceSortRule === "page_original"
        ? "当前结果按 1688 搜索结果页原始顺序展示，缺失原始序号的货源排在后面。"
        : "当前结果按货源价格从低到高排序，多 SKU 商品使用最低拿货价。";
    const sourceListEntries = useMemo(() => resolvedChannelGroups.flatMap(group => (
        (group.sources || []).map((source, sourceIndex) => ({ group, source, sourceIndex }))
    )), [resolvedChannelGroups]);
    const sourceListTotal = sourceListEntries.length;
    const sourceListTotalPages = Math.max(1, Math.ceil(sourceListTotal / SOURCE_LIST_PAGE_SIZE));
    const currentSourceListPage = Math.max(1, Math.min(sourceListPage, sourceListTotalPages));
    const paginatedChannelGroups = useMemo(() => {
        const start = (currentSourceListPage - 1) * SOURCE_LIST_PAGE_SIZE;
        const pageEntries = sourceListEntries.slice(start, start + SOURCE_LIST_PAGE_SIZE);
        const groupIndexMap = new Map();
        const groups = [];
        pageEntries.forEach(({ group, source }) => {
            const groupKey = group.channel_id || group.channel_label || 'unknown';
            if (!groupIndexMap.has(groupKey)) {
                groupIndexMap.set(groupKey, groups.length);
                groups.push({ ...group, sources: [] });
            }
            groups[groupIndexMap.get(groupKey)].sources.push(source);
        });
        return groups;
    }, [sourceListEntries, currentSourceListPage]);

    useEffect(() => {
        if (sourceListPage !== currentSourceListPage) {
            setSourceListPage(currentSourceListPage);
        }
    }, [sourceListPage, currentSourceListPage]);
    const detailFallbackFilterChannels = useMemo(() => {
        if (!selectedItem || resolvedChannelGroups.length > 0) {
            return [];
        }
        return getDetailFallbackFilterChannels(selectedItem, selectedTask)
            .filter(channel => sourceChannelFilter === "all" || channel.channel_id === sourceChannelFilter)
            .filter(channel => {
                const summary = normalizeChannelFilterSummary(channel.filter_summary, channel.source_filter_snapshot, channel.channel_type);
                return summary.configured.length > 0 || summary.legacyMissingSnapshot || summary.unsupported;
            });
    }, [selectedItem, selectedTask, resolvedChannelGroups, sourceChannelFilter]);
    const pageIntro = (() => {
        if (view === 'item_detail') return null;
        if (view === 'order_detail') return null;
        if (view === 'dashboard') return { icon: 'dashboard', title: '控制台中心', description: '全局扫描 Worker 统计面板及后台状态概览。' };
        if (view === 'tasks') return { icon: 'list_alt', title: '任务队列中心', description: '查看和管理各个品类的深度爬取状态。左侧显示活跃进行中队列，右侧显示归档历史。' };
        if (view === 'results' && selectedTask) return { icon: 'query_stats', title: `“${selectedTask.keyword}” 爆款深度对比报告`, description: '每个爆款商品均可以点入查看对应货源渠道的深度对比结果。' };
        if (view === 'results') return { icon: 'travel_explore', title: '选品决策资产库', description: '系统已完成的爆款数据中心。点击各个品类卡片，可直接穿透查看商品的多渠道货源采购价与深度分析。' };
        if (view === 'published') return { icon: 'shopping_bag', title: '选品管理', description: '管理从决策资产库加入的候选货源，支持后续上架、下架与删除处理。' };
        if (view === 'orders') return { icon: 'receipt_long', title: '订单管理', description: '通过闲管家 OpenAPI 查询订单列表和订单详情。' };
        if (view === 'logs') return { icon: 'analytics', title: '任务日志中心', description: '实时监控扫描 Worker 的后台标准输出日志。' };
        if (view === 'token_stats') return { icon: 'generating_tokens', title: 'AI Token 计量舱', description: '系统大模型调用统计、模型消耗占比及审计流水线。' };
        if (view === 'settings') return { icon: 'settings', title: '系统参数配置', description: '全局管理大模型服务密钥及闲鱼 OpenAPI 的各类配置。' };
        return null;
    })();
    const topBarMeta = (() => {
        if (view === 'item_detail') {
            return {
                icon: 'inventory_2',
                title: '决策资产 / 货源明细',
                description: '查看单个爆款商品对应的多渠道货源深度对比结果。'
            };
        }
        if (view === 'order_detail') {
            return {
                icon: 'receipt_long',
                title: '订单管理 / 订单详情',
                description: selectedOrderNo ? `查看订单 ${selectedOrderNo} 的实时详情。` : '查看订单实时详情。'
            };
        }
        if (view === 'token_stats') {
            return {
                icon: 'generating_tokens',
                title: 'AI Token 计量舱 / 成本审计',
                description: '查看模型消耗、功能占比和最近调用流水。'
            };
        }
        if (view === 'settings') {
            return {
                icon: 'settings',
                title: '系统参数配置 / 密钥管理',
                description: '统一管理模型配置、闲鱼 OpenAPI 与系统参数。'
            };
        }
        return pageIntro || {
            icon: 'explore',
            title: view,
            description: '当前功能页面'
        };
    })();

    const navItemClass = (itemKey) => {
        const isActive = (itemKey === 'results' && ['results', 'item_detail'].includes(view))
            || (itemKey === 'orders' && ['orders', 'order_detail'].includes(view))
            || view === itemKey;
        if (sidebarCollapsed) {
            return `group relative flex items-center justify-center px-3 py-3 rounded-xl font-sans text-xs transition-all duration-150 scale-100 active:scale-95 cursor-pointer ${
                isActive
                ? 'text-primary font-bold bg-primary/10 border border-primary/20 shadow-sm shadow-primary/5'
                : 'text-secondary hover:bg-surface-container-high transition-colors'
            }`;
        }
        return `flex items-center gap-3 px-4 py-3 rounded-xl font-sans text-xs transition-all duration-150 scale-100 active:scale-95 cursor-pointer ${
            isActive 
            ? 'text-primary font-bold bg-surface-container border-r-4 border-primary' 
            : 'text-secondary hover:bg-surface-container-high transition-colors'
        }`;
    };

    const collapsedSidebarIconButtonClass = 'group relative flex items-center justify-center px-3 py-3 rounded-xl font-sans text-xs text-secondary transition-all duration-150 scale-100 active:scale-95 cursor-pointer hover:bg-surface-container-high';
    const sidebarUtilityWrapperClass = sidebarCollapsed ? 'group relative flex justify-center' : 'group relative';
    const sidebarUtilityButtonClass = sidebarCollapsed
        ? 'w-12 h-12 rounded-xl'
        : 'w-full h-11 rounded-xl px-3';
    const sidebarUtilitySurfaceClass = sidebarCollapsed
        ? `${collapsedSidebarIconButtonClass} w-12 h-12 border border-transparent bg-transparent gap-0`
        : `${sidebarUtilityButtonClass} flex items-center justify-center gap-2 border border-border-hairline bg-surface-container-low hover:bg-surface-container-high text-secondary transition-colors font-sans text-xs scale-100 active:scale-95 duration-100`;
    const sidebarStatusCardClass = sidebarCollapsed
        ? 'w-12 h-12 rounded-xl flex items-center justify-center bg-transparent border border-transparent'
        : 'w-full h-14 rounded-xl px-3 py-2';

    return (
        <React.Fragment>
            {/* SideNavBar */}
            <aside className={`${sidebarCollapsed ? 'w-[88px]' : 'w-[260px]'} h-screen bg-surface-container-lowest border-r border-border-hairline fixed left-0 top-0 flex flex-col py-6 z-20 transition-all duration-200`}>
                <div className={`${sidebarCollapsed ? 'px-3' : 'px-6'} mb-8 flex items-center ${sidebarCollapsed ? 'justify-center' : 'gap-3'}`}>
                    <div className={`flex items-center ${sidebarCollapsed ? 'justify-center' : 'gap-3 min-w-0'}`}>
                        <div className="w-9 h-9 rounded bg-primary flex items-center justify-center text-on-primary shrink-0">
                            <span className="material-symbols-outlined text-[20px]" style={{fontVariationSettings: "'FILL' 1"}}>precision_manufacturing</span>
                        </div>
                        <div className={`sidebar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>
                            <h1 className="font-sans text-base font-bold text-primary tracking-tight whitespace-nowrap">选品中枢 PRO</h1>
                            <p className="font-mono text-[9px] text-secondary uppercase tracking-wider whitespace-nowrap">Automated Precision</p>
                        </div>
                    </div>
                </div>

                <ul className={`flex-1 ${sidebarCollapsed ? 'px-3' : 'px-4'} space-y-1 w-full`}>
                    <li className={navItemClass("dashboard")} onClick={() => setActiveView("dashboard")}>
                        <span className="material-symbols-outlined text-[18px]">dashboard</span>
                        <span className={`sidebar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>控制台中心</span>
                        {sidebarCollapsed && <span className="sidebar-tooltip">控制台中心</span>}
                    </li>
                    <li className={navItemClass("tasks")} onClick={() => setActiveView("tasks")}>
                        <span className="material-symbols-outlined text-[18px]">list_alt</span>
                        <span className={`sidebar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>任务队列</span>
                        {sidebarCollapsed && <span className="sidebar-tooltip">任务队列</span>}
                    </li>
                    <li className={navItemClass("results")} onClick={() => setActiveView("results")}>
                        <span className="material-symbols-outlined text-[18px]">travel_explore</span>
                        <span className={`sidebar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>决策资产库</span>
                        {sidebarCollapsed && <span className="sidebar-tooltip">决策资产库</span>}
                    </li>
                    <li className={navItemClass("published")} onClick={() => setActiveView("published")}>
                        <span className="material-symbols-outlined text-[18px]">shopping_bag</span>
                        <span className={`sidebar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>选品管理</span>
                        {sidebarCollapsed && <span className="sidebar-tooltip">选品管理</span>}
                    </li>
                    <li className={navItemClass("orders")} onClick={() => setActiveView("orders")}>
                        <span className="material-symbols-outlined text-[18px]">receipt_long</span>
                        <span className={`sidebar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>订单管理</span>
                        {sidebarCollapsed && <span className="sidebar-tooltip">订单管理</span>}
                    </li>
                    <li className={navItemClass("logs")} onClick={() => setActiveView("logs")}>
                        <span className="material-symbols-outlined text-[18px]">analytics</span>
                        <span className={`sidebar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>日志日志</span>
                        {sidebarCollapsed && <span className="sidebar-tooltip">日志日志</span>}
                    </li>
                    <li className={navItemClass("token_stats")} onClick={() => setActiveView("token_stats")}>
                        <span className="material-symbols-outlined text-[18px]">generating_tokens</span>
                        <span className={`sidebar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>AI Token 计量舱</span>
                        {sidebarCollapsed && <span className="sidebar-tooltip">AI Token 计量舱</span>}
                    </li>
                    <li className={navItemClass("settings")} onClick={() => setActiveView("settings")}>
                        <span className="material-symbols-outlined text-[18px]">settings</span>
                        <span className={`sidebar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>系统设置</span>
                        {sidebarCollapsed && <span className="sidebar-tooltip">系统设置</span>}
                    </li>
                </ul>

                {/* 侧栏底部工具 */}
                <div className={`${sidebarCollapsed ? 'px-3' : 'px-4'} mt-auto space-y-3`}>
                    <div className={sidebarUtilityWrapperClass}>
                        <button
                            type="button"
                            onClick={() => setSidebarCollapsed(prev => !prev)}
                            className={sidebarUtilitySurfaceClass}
                        >
                            <span className="material-symbols-outlined text-[16px]">{sidebarCollapsed ? 'left_panel_open' : 'left_panel_close'}</span>
                            <span className={`sidebar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>{sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}</span>
                        </button>
                        {sidebarCollapsed && (
                            <span className="sidebar-tooltip">展开侧边栏</span>
                        )}
                    </div>

                    <div className={sidebarUtilityWrapperClass}>
                        <button 
                            onClick={() => setTheme(t => t === 'light' ? 'dark' : 'light')}
                            className={sidebarUtilitySurfaceClass}
                        >
                            <span className="material-symbols-outlined text-[16px]">{theme === 'light' ? 'dark_mode' : 'light_mode'}</span>
                            <span className={`sidebar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>{theme === 'light' ? '深色 midnight' : '浅色 efficient'}</span>
                        </button>
                        {sidebarCollapsed && (
                            <span className="sidebar-tooltip">{theme === 'light' ? '切换到深色 midnight' : '切换到浅色 efficient'}</span>
                        )}
                    </div>
                </div>
            </aside>

            {/* TopNavBar */}
            <header className={`fixed top-0 right-0 ${sidebarCollapsed ? 'left-[88px] w-[calc(100%-88px)]' : 'left-[260px] w-[calc(100%-260px)]'} h-[72px] bg-surface-container-lowest/88 backdrop-blur-md border-b border-border-hairline flex items-center justify-between px-6 z-10 transition-all duration-200`}>
                <div className="flex items-center gap-3 min-w-0 flex-1">
                    <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/15 flex items-center justify-center text-primary shrink-0">
                        <span className="material-symbols-outlined text-[20px]">{topBarMeta.icon}</span>
                    </div>
                    <div className="min-w-0 flex-1">
                        <div className="font-sans text-sm font-bold text-on-surface truncate">
                            {topBarMeta.title}
                        </div>
                        <div className={`hidden lg:block font-sans text-[11px] text-secondary truncate transition-all duration-200 ${sidebarCollapsed ? 'max-w-[420px]' : 'max-w-[680px]'}`}>
                            {topBarMeta.description}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                    <div className={`hidden sm:flex items-center px-3 py-1 bg-surface-container-low border border-border-hairline rounded-full overflow-hidden transition-all duration-200 ${sidebarCollapsed ? 'max-w-0 opacity-0 px-0 py-1 border-transparent' : 'max-w-[180px] opacity-100'}`}>
                        <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse mr-2"></span>
                        <span className={`topbar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>
                            <span className="font-sans text-[10px] text-secondary">系统健康运行</span>
                        </span>
                    </div>
                    <div className={`w-px h-6 bg-border-hairline transition-opacity duration-200 ${sidebarCollapsed ? 'opacity-0' : 'opacity-100'}`}></div>
                    <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary font-mono text-[10px] font-bold">
                            M
                        </div>
                        <span className={`topbar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>
                            <span className="font-sans text-xs text-secondary font-medium">管理员用户</span>
                        </span>
                    </div>
                </div>
            </header>

            {/* Main Container */}
            <main className={`${sidebarCollapsed ? 'ml-[88px]' : 'ml-[260px]'} mt-[72px] p-6 overflow-y-auto flex-1 h-[calc(100vh-72px)] transition-all duration-200`}>
                {view === 'logs' ? <LogViewer tasks={tasks} hideHeader={true} /> : 
                 view === 'token_stats' ? <TokenStatsView hideHeader={true} /> :
                 view === 'settings' ? <SystemSettingsView hideHeader={true} /> :
                 view === 'orders' ? <OrderManager hideHeader={true} onOpenDetail={enterOrderDetail} /> :
                 view === 'order_detail' ? <OrderDetailPage orderNo={selectedOrderNo} onBack={() => setActiveView("orders")} /> :
                 view === "dashboard" ? (() => {
                    const activeTasks = tasks.filter(t => t.status !== '已完成');
                    const runningCount = tasks.filter(t => ['执行中', '正在暂停'].includes(t.status)).length;
                    const pendingCount = tasks.filter(t => t.status === '排队中').length;
                    return (
                        <div className="view-content">
                            {/* Bento Grid */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 ambient-shadow glow-bg hover:border-primary transition-all duration-150 group relative overflow-hidden">
                                    <div className="flex justify-between items-start mb-4">
                                        <h3 className="font-sans text-xs font-semibold text-secondary uppercase tracking-wider">活跃调研任务</h3>
                                        <button 
                                            onClick={(e) => { e.stopPropagation(); refreshData(); }}
                                            className="w-8 h-8 rounded-lg bg-processing/10 hover:bg-processing/20 flex items-center justify-center text-processing active:scale-90 transition-all cursor-pointer"
                                            title="手动刷新状态"
                                        >
                                            <span className="material-symbols-outlined text-[18px] hover:rotate-180 transition-transform duration-500">autorenew</span>
                                        </button>
                                    </div>
                                    <div className="flex items-baseline gap-2">
                                        <span className="font-sans text-3xl font-black text-on-surface">{activeTasks.length}</span>
                                        <span className="text-xs text-success font-semibold flex items-center gap-0.5"><span className="material-symbols-outlined text-[14px]">trending_up</span> 运行中</span>
                                    </div>
                                </div>

                                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 ambient-shadow glow-bg hover:border-primary transition-all duration-150 group relative overflow-hidden">
                                    <div className="flex justify-between items-start mb-4">
                                        <h3 className="font-sans text-xs font-semibold text-secondary uppercase tracking-wider">已存储爆款资产</h3>
                                        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                                            <span className="material-symbols-outlined text-[18px]">dataset</span>
                                        </div>
                                    </div>
                                    <div className="flex items-baseline gap-2">
                                        <span className="font-sans text-3xl font-black text-on-surface">{completedTasks.length}</span>
                                        <span className="text-xs text-secondary">分类库</span>
                                    </div>
                                </div>

                                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 ambient-shadow glow-bg hover:border-primary transition-all duration-150 group relative overflow-hidden">
                                    <div className="flex justify-between items-start mb-4">
                                        <h3 className="font-sans text-xs font-semibold text-secondary uppercase tracking-wider">队列统计概览</h3>
                                        <div className="w-8 h-8 rounded-lg bg-warning/10 flex items-center justify-center text-warning">
                                            <span className="material-symbols-outlined text-[18px]">queue</span>
                                        </div>
                                    </div>
                                    <div className="flex gap-4 items-baseline mt-1">
                                        <div className="text-xs font-semibold"><span className="text-primary text-lg font-black">{runningCount}</span> 个执行</div>
                                        <div className="text-xs font-semibold text-secondary"><span className="text-secondary text-lg font-black">{pendingCount}</span> 个排队</div>
                                    </div>
                                </div>
                            </div>

                            {/* 新建调研表单 */}
                            <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 ambient-shadow">
                                <div className="flex items-center gap-2 mb-4">
                                    <span className="material-symbols-outlined text-primary">add_task</span>
                                    <h3 className="font-sans text-sm font-bold text-on-surface">启动全新深度调研任务</h3>
                                </div>
                                <div className="flex gap-3">
                                    <input 
                                        className="flex-1 bg-surface-container-low border border-border-hairline text-on-surface placeholder-secondary/50 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
                                        value={newKeyword} 
                                        onChange={e => setNewKeyword(e.target.value)} 
                                        placeholder="支持输入品类关键词、闲鱼商品链接、淘口令或直接输入图片 URL 以图搜图比价..." 
                                    />
                                    <button 
                                        className="bg-primary hover:bg-primary-container text-white font-sans text-sm font-semibold px-6 py-3 rounded-lg transition-colors scale-100 active:scale-95 shadow-[0_2px_8px_rgba(168,50,0,0.15)] flex items-center gap-2 shrink-0"
                                        onClick={openTaskStartConfig}
                                    >
                                        <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                                        启动扫描 Worker
                                    </button>
                                </div>
                            </div>

                            {/* 进行中任务进度 */}
                            {activeTasks.length > 0 && (
                                <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 ambient-shadow mt-6 cursor-pointer" onClick={() => setActiveView('tasks')}>
                                    <div className="flex justify-between items-center mb-4">
                                        <h3 className="font-sans text-sm font-bold text-on-surface">运行中扫描任务 ({activeTasks.length})</h3>
                                        <span className="text-xs text-primary font-semibold flex items-center gap-0.5">查看详情 <span className="material-symbols-outlined text-[14px]">arrow_forward</span></span>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {activeTasks.slice(0, 4).map(t => (
                                            <div key={t.id} className="p-4 bg-surface-container-low border border-border-hairline rounded-lg">
                                                <div className="font-semibold text-on-surface text-sm">{t.keyword}</div>
                                                <div className="text-xs text-secondary mt-1 flex justify-between">
                                                    <span>{t.status}</span>
                                                    <span className="font-mono">{t.progress}%</span>
                                                </div>
                                                <div className="w-full h-1 bg-surface-container rounded-full overflow-hidden mt-2">
                                                    <div className="h-full bg-primary transition-all duration-300" style={{ width: `${t.progress}%` }}></div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                 })() :
                 view === "tasks" ? (() => {
                    const activeTasks = tasks.filter(t => t.status !== '已完成').sort((a, b) => a.created_at.localeCompare(b.created_at));
                    const completedTasks = tasks.filter(t => t.status === '已完成');
                     const itemsPerPage = 3;
                     const totalPages = Math.ceil(completedTasks.length / itemsPerPage);
                     const currentArchivePage = Math.max(1, Math.min(archivePage, totalPages || 1));
                     const paginatedCompletedTasks = completedTasks.slice(
                         (currentArchivePage - 1) * itemsPerPage,
                         currentArchivePage * itemsPerPage
                     )
                    return (
                        <div className="view-content">
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
                                {/* 左栏：执行队列 */}
                                <div>
                                    <h3 className="font-sans text-sm font-bold text-on-surface mb-4 flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                                        活跃执行队列
                                    </h3>
                                    <div className="space-y-4">
                                        {activeTasks.map(t => {
                                            let badgeColor = "bg-processing/10 text-processing border-processing/20";
                                            if (t.status === '已暂停') badgeColor = "bg-secondary/15 text-secondary border-secondary/20";
                                            if (t.status === '失败') badgeColor = "bg-error/10 text-error border-error/20";
                                            return (
                                                <div 
                                                    className="bg-surface-container-lowest border border-border-hairline rounded-xl p-5 relative overflow-hidden ambient-shadow hover:border-primary transition-colors group"
                                                    key={t.id}
                                                >
                                                    <div className="flex justify-between items-start mb-2">
                                                        <div>
                                                            <div className="font-bold text-on-surface text-base">{t.keyword}</div>
                                                            <div className="flex items-center gap-2 mt-1.5">
                                                                <span className="text-[10px] text-secondary font-mono">TASK_ID: {t.id}</span>
                                                                {renderTaskTypeBadge(t.input_type)}
                                                            </div>
                                                        </div>
                                                        
                                                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${badgeColor}`}>
                                                            {t.status}
                                                        </span>
                                                    </div>

                                                    <p className="text-xs text-secondary line-clamp-2 min-h-[32px] mt-2 mb-3 bg-surface-container-low p-2 rounded border border-border-hairline/40">{t.msg || 'Worker 正在分配进程空间...'}</p>
                                                    {renderTaskStartConfigSummary(t)}
                                                    
                                                    <div className="w-full h-1 bg-surface-container rounded-full overflow-hidden mb-4">
                                                        <div className="h-full bg-primary transition-all duration-300" style={{ width: `${t.progress}%` }}></div>
                                                    </div>

                                                    <div className="flex justify-between items-center border-t border-border-hairline/60 pt-3">
                                                        <div className="flex items-center gap-3">
                                                            <span className="text-[10px] text-secondary font-mono">V.{t.version}</span>
                                                            {t.total_tokens > 0 && (
                                                                <span className="inline-flex items-center gap-0.5 text-[10px] text-success/80 dark:text-success/90 font-mono">
                                                                    <span className="material-symbols-outlined text-[11px] leading-none">generating_tokens</span>
                                                                    AI Tokens: {(t.total_tokens || 0).toLocaleString()}
                                                                </span>
                                                            )}
                                                        </div>
                                                        <div className="flex gap-2">
                                                            {t.status === '执行中' ? (
                                                                <button className="px-3 py-1 bg-surface-container border border-border-hairline hover:border-primary text-secondary hover:text-primary rounded text-xs font-semibold transition-colors" onClick={() => pauseTask(t.id)}>暂停</button>
                                                            ) : (t.status === '已暂停' || t.status === '失败') ? (
                                                                <button className="px-3 py-1 bg-primary hover:bg-primary-container text-white rounded text-xs font-semibold transition-colors" onClick={() => retryTask(t.id)}>恢复运行</button>
                                                            ) : null}

                                                            {/* 删除按钮 */}
                                                            {(t.status === '已暂停' || t.status === '失败') && (
                                                                <button 
                                                                    className="px-3 py-1 bg-error/10 border border-error/20 hover:bg-error text-error hover:text-white rounded text-xs font-semibold transition-colors" 
                                                                    onClick={() => deleteTask(t.id)}
                                                                >
                                                                    彻底删除
                                                                </button>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                        {activeTasks.length === 0 && (
                                            <div className="bg-surface-container-lowest border border-border-hairline rounded-xl py-12 text-center text-xs text-secondary">
                                                当前暂无活跃的选品 Worker 任务
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* 右栏：完成归档 */}
                                <div>
                                    <h3 className="font-sans text-sm font-bold text-on-surface mb-4 flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-success"></span>
                                        已归档历史任务
                                    </h3>
                                    <div className="space-y-4">
                                        {paginatedCompletedTasks.map(t => (
                                            <div 
                                                className="bg-surface-container-lowest border border-border-hairline rounded-xl pt-4 pb-4 px-5 relative overflow-hidden ambient-shadow hover:border-primary transition-colors cursor-pointer group"
                                                key={t.id}
                                                onClick={() => loadTaskResults(t)}
                                            >
                                                <div className="flex justify-between items-start">
                                                    <div>
                                                        <div className="font-bold text-on-surface text-base group-hover:text-primary transition-colors">{t.keyword}</div>
                                                        <div className="flex items-center gap-2 mt-3">
                                                            <span className="text-xs text-secondary font-mono">TASK_ID: {t.id}</span>
                                                            {renderTaskTypeBadge(t.input_type)}
                                                        </div>
                                                    </div>
                                                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-success/10 text-success border border-success/20">
                                                        已完成
                                                    </span>
                                                </div>

                                                <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-secondary mt-2">
                                                    <span>调研时间: {t.created_at}</span>
                                                    {getTaskChannelSummaries(t).map(channel => {
                                                        const summaryText = formatTaskChannelSummaryText(channel);
                                                        return (
                                                            <React.Fragment key={`archive-summary-${t.id}-${channel.channel_id}`}>
                                                                <span className="text-border-hairline/60">|</span>
                                                                <React.Fragment>
                                                                    <span className="px-1.5 py-0.5 rounded bg-primary/8 text-primary font-semibold text-xs">
                                                                        {channel.channel_label || channel.channel_id}
                                                                    </span>
                                                                    {summaryText && (
                                                                        <React.Fragment>
                                                                            <span className="text-border-hairline/60">|</span>
                                                                            <span>{summaryText}</span>
                                                                        </React.Fragment>
                                                                    )}
                                                                </React.Fragment>
                                                            </React.Fragment>
                                                        );
                                                    })}
                                                </div>
                                                {renderTaskStartConfigSummary(t)}

                                                <div className="flex justify-between items-center mt-2.5 pt-2.5 border-t border-border-hairline/60">
                                                    <div className="flex items-center gap-2.5 text-xs text-secondary">
                                                        <span className="font-mono">V.{t.version}</span>
                                                        {t.total_tokens > 0 && (
                                                            <>
                                                                <span className="text-border-hairline/60">|</span>
                                                                <span className="inline-flex items-center gap-0.5">
                                                                    <span className="material-symbols-outlined text-[13px] leading-none text-success">generating_tokens</span>
                                                                    Tokens: {(t.total_tokens || 0).toLocaleString()}
                                                                </span>
                                                            </>
                                                        )}
                                                    </div>
                                                    <div className="flex gap-2">
                                                        <button 
                                                            className="px-3 py-1 bg-surface-container border border-border-hairline hover:border-primary text-secondary hover:text-primary rounded text-xs font-semibold transition-colors" 
                                                            onClick={(e) => { e.stopPropagation(); retryTask(t.id); }}
                                                        >
                                                            重新扫描
                                                        </button>
                                                        <button 
                                                            className="px-3 py-1 bg-error/10 border border-error/20 hover:bg-error hover:text-white text-error rounded text-xs font-semibold transition-all" 
                                                            onClick={(e) => { e.stopPropagation(); deleteTask(t.id); }}
                                                        >
                                                            逻辑删除
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                        
                                        {totalPages > 1 && (
                                            <div className="flex justify-center items-center gap-2 mt-4 pt-3 border-t border-border-hairline/60">
                                                <button
                                                    className="w-7 h-7 flex items-center justify-center rounded border border-border-hairline text-secondary hover:bg-surface-container-low transition-colors disabled:opacity-40"
                                                    disabled={currentArchivePage <= 1}
                                                    onClick={() => setArchivePage(currentArchivePage - 1)}
                                                >
                                                    <span className="material-symbols-outlined text-[16px]">chevron_left</span>
                                                </button>
                                                <span className="font-sans text-[11px] text-secondary font-semibold">
                                                    第 {currentArchivePage} / {totalPages} 页（共 {completedTasks.length} 条，每页 {itemsPerPage} 条）
                                                </span>
                                                <button
                                                    className="w-7 h-7 flex items-center justify-center rounded border border-border-hairline text-secondary hover:bg-surface-container-low transition-colors disabled:opacity-40"
                                                    disabled={currentArchivePage >= totalPages}
                                                    onClick={() => setArchivePage(currentArchivePage + 1)}
                                                >
                                                    <span className="material-symbols-outlined text-[16px]">chevron_right</span>
                                                </button>
                                            </div>
                                        )}
                                        {completedTasks.length === 0 && (
                                            <div className="bg-surface-container-lowest border border-border-hairline rounded-xl py-12 text-center text-xs text-secondary">
                                                当前暂无已归档的历史调研记录
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                 })() :
                 view === "results" ? ( 
                     selectedTask ? (() => {
                         const itemsPerPage = 6;
                         const totalResultPages = Math.ceil(detailedItems.length / itemsPerPage);
                         const currentResultPage = Math.max(1, Math.min(resultPage, totalResultPages || 1));
                         const paginatedDetailedItems = detailedItems.slice(
                             (currentResultPage - 1) * itemsPerPage,
                             currentResultPage * itemsPerPage
                         );
                         return (
                             <div> 
                                 <header className="mb-6 flex justify-between items-end">
                                     <button onClick={() => setSelectedTask(null)} className="text-secondary hover:text-primary text-xs font-bold flex items-center gap-1">
                                         <span className="material-symbols-outlined text-[16px]">arrow_back</span>
                                         返回决策资产列表
                                     </button>
                                     <button 
                                         className="px-4 py-2 bg-primary hover:bg-primary-container text-white font-sans text-xs font-semibold rounded-lg shadow-sm transition-colors flex items-center gap-1"
                                         onClick={() => window.open(`/api/download/${selectedTask.id}`)}
                                     >
                                         <span className="material-symbols-outlined text-[16px]">download</span>
                                         导出分析 Excel
                                     </button>
                                 </header>

                                 <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3 gap-6">
                                     {paginatedDetailedItems.length > 0 ? paginatedDetailedItems.map((group) => (
                                         <div 
                                             className="bg-surface-container-lowest border border-border-hairline rounded-xl overflow-hidden cursor-pointer hover:-translate-y-1 hover:shadow-lg transition-all relative group" 
                                             key={group.rank} 
                                             onClick={() => enterItemDetail(group)}
                                         >
                                             <div className="relative h-56 bg-surface-container-low border-b border-border-hairline overflow-hidden">
                                                 <img 
                                                     src={group.xianyu_item?.image_url} 
                                                     referrerPolicy="no-referrer" 
                                                     className="w-full h-full object-cover transition-transform group-hover:scale-105 duration-300"
                                                 />
                                                 <div className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded bg-primary/90 text-white font-mono text-[10px] font-black">
                                                     RANK #{group.rank}
                                                 </div>
                                             </div>
                                             
                                             <div className="pt-4 pb-3.5 px-4">
                                                 <h3 className="text-xs font-bold text-on-surface line-clamp-2 h-9 leading-relaxed">
                                                     {group.xianyu_item?.title}
                                                 </h3>
                                                 <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-secondary mt-2.5">
                                                     {getItemCardChannels(group, selectedTask).map((channel, cIdx) => {
                                                         const summaryText = formatTaskChannelSummaryText(channel);
                                                         return (
                                                             <React.Fragment key={`${group.rank}-${channel.channel_id}`}>
                                                                 {cIdx > 0 && <span className="text-border-hairline/60">|</span>}
                                                                 <span className="px-1.5 py-0.5 rounded bg-primary/8 text-primary font-semibold text-xs whitespace-nowrap">
                                                                     {formatChannelCountLabel(channel)}
                                                                 </span>
                                                                 {summaryText && (
                                                                     <React.Fragment>
                                                                         <span className="text-border-hairline/60">|</span>
                                                                         <span>{summaryText}</span>
                                                                     </React.Fragment>
                                                                 )}
                                                             </React.Fragment>
                                                         );
                                                     })}
                                                 </div>
                                                 
                                                 <div className="flex justify-between items-end gap-4 mt-2.5 border-t border-border-hairline/60 pt-2.5">
                                                     <span className="text-base font-black text-primary">¥{group.xianyu_item?.price}</span>
                                                     <div className="flex flex-col items-end gap-1 shrink-0">
                                                         <span className="text-xs text-secondary font-semibold leading-none">
                                                             {group.sources?.length || 0}个货源
                                                         </span>
                                                         <span className="font-mono text-[10px] leading-none text-outline/60">
                                                             DB_ID: {group.xianyu_item?.db_id}
                                                         </span>
                                                     </div>
                                                 </div>
                                             </div>
                                         </div>
                                     )) : (
                                         <div className="col-span-full bg-surface-container-lowest border border-border-hairline rounded-xl py-24 text-center">
                                             <p className="text-secondary text-sm">该分析任务尚未产生可匹配的比价数据。</p>
                                         </div>
                                     )}
                                 </div>

                                 {totalResultPages > 1 && (
                                     <div className="flex justify-center items-center gap-4 mt-8 pt-4 border-t border-border-hairline/60">
                                         <button
                                             className="w-8 h-8 flex items-center justify-center rounded-lg border border-border-hairline bg-surface-container-lowest text-secondary hover:text-primary hover:border-primary transition-all disabled:opacity-40"
                                             disabled={currentResultPage <= 1}
                                             onClick={() => setResultPage(currentResultPage - 1)}
                                         >
                                             <span className="material-symbols-outlined text-[18px]">chevron_left</span>
                                         </button>
                                         <span className="font-sans text-xs text-secondary font-semibold">
                                             第 {currentResultPage} / {totalResultPages} 页（共 {detailedItems.length} 条，每页 {itemsPerPage} 条）
                                         </span>
                                         <button
                                             className="w-8 h-8 flex items-center justify-center rounded-lg border border-border-hairline bg-surface-container-lowest text-secondary hover:text-primary hover:border-primary transition-all disabled:opacity-40"
                                             disabled={currentResultPage >= totalResultPages}
                                             onClick={() => setResultPage(currentResultPage + 1)}
                                         >
                                             <span className="material-symbols-outlined text-[18px]">chevron_right</span>
                                         </button>
                                     </div>
                                 )}
                             </div>
                         );
                     })() : (
                         (() => {
                             const tasksPerPage = 9;
                             const totalResultTaskPages = Math.ceil(completedTasks.length / tasksPerPage);
                             const currentResultTaskPage = Math.max(1, Math.min(resultTaskPage, totalResultTaskPages || 1));
                             const paginatedCompletedTasks = completedTasks.slice(
                                 (currentResultTaskPage - 1) * tasksPerPage,
                                 currentResultTaskPage * tasksPerPage
                             );
                             return (
                                 <div>
                                     <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
                                         {paginatedCompletedTasks.map(t => (
                                             <div 
                                                 className="bg-surface-container-lowest border border-border-hairline rounded-xl pt-4 pb-4 px-5 relative overflow-hidden ambient-shadow hover:border-primary transition-colors cursor-pointer group" 
                                                 key={t.id} 
                                                 onClick={() => loadTaskResults(t)}
                                             >
                                                 <div className="flex justify-between items-start">
                                                     <div>
                                                         <div className="font-bold text-on-surface text-base group-hover:text-primary transition-colors">{t.keyword}</div>
                                                         <div className="flex items-center gap-2 mt-2.5">
                                                             <span className="text-xs text-secondary font-mono">TASK_ID: {t.id}</span>
                                                             {renderTaskTypeBadge(t.input_type)}
                                                         </div>
                                                     </div>
                                                     <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-success/10 text-success border border-success/20">
                                                         已完成
                                                     </span>
                                                 </div>

                                                 <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-secondary mt-2.5">
                                                     <span>调研时间: {t.created_at}</span>
                                                     {getTaskChannelSummaries(t).map(channel => {
                                                         const summaryText = formatTaskChannelSummaryText(channel);
                                                         return (
                                                             <React.Fragment key={`results-summary-${t.id}-${channel.channel_id}`}>
                                                                 <span className="text-border-hairline/60">|</span>
                                                                 <React.Fragment>
                                                                     <span className="px-1.5 py-0.5 rounded bg-primary/8 text-primary font-semibold text-xs">
                                                                         {channel.channel_label || channel.channel_id}
                                                                     </span>
                                                                     {summaryText && (
                                                                         <React.Fragment>
                                                                             <span className="text-border-hairline/60">|</span>
                                                                             <span>{summaryText}</span>
                                                                         </React.Fragment>
                                                                     )}
                                                                 </React.Fragment>
                                                             </React.Fragment>
                                                         );
                                                     })}
                                                 </div>

                                                 <div className="flex justify-between items-center mt-2.5 pt-2.5 border-t border-border-hairline/60">
                                                     <div className="flex items-center gap-2.5 text-xs text-secondary">
                                                         <span className="font-mono">V.{t.version}</span>
                                                         {t.total_tokens > 0 && (
                                                             <React.Fragment>
                                                                 <span className="text-border-hairline/60">|</span>
                                                                 <span className="inline-flex items-center gap-0.5">
                                                                     <span className="material-symbols-outlined text-[13px] leading-none text-success">generating_tokens</span>
                                                                     Tokens: {(t.total_tokens || 0).toLocaleString()}
                                                                 </span>
                                                             </React.Fragment>
                                                         )}
                                                     </div>
                                                 </div>
                                             </div>
                                         ))}
                                     </div>

                                     {totalResultTaskPages > 1 && (
                                         <div className="flex justify-center items-center gap-4 mt-8 pt-4 border-t border-border-hairline/60">
                                             <button
                                                 className="w-8 h-8 flex items-center justify-center rounded-lg border border-border-hairline bg-surface-container-lowest text-secondary hover:text-primary hover:border-primary transition-all disabled:opacity-40"
                                                 disabled={currentResultTaskPage <= 1}
                                                 onClick={() => setResultTaskPage(currentResultTaskPage - 1)}
                                             >
                                                 <span className="material-symbols-outlined text-[18px]">chevron_left</span>
                                             </button>
                                             <span className="font-sans text-xs text-secondary font-semibold">
                                                 第 {currentResultTaskPage} / {totalResultTaskPages} 页（共 {completedTasks.length} 条，每页 {tasksPerPage} 条）
                                             </span>
                                             <button
                                                 className="w-8 h-8 flex items-center justify-center rounded-lg border border-border-hairline bg-surface-container-lowest text-secondary hover:text-primary hover:border-primary transition-all disabled:opacity-40"
                                                 disabled={currentResultTaskPage >= totalResultTaskPages}
                                                 onClick={() => setResultTaskPage(currentResultTaskPage + 1)}
                                             >
                                                 <span className="material-symbols-outlined text-[18px]">chevron_right</span>
                                             </button>
                                         </div>
                                     )}
                                 </div>
                             );
                         })()
                     ) 
                 ) :
                 view === "item_detail" && selectedItem ? ( 
                     <div className="view-content">
                         <div onClick={() => setActiveView("results")} className="text-secondary hover:text-primary text-xs font-bold flex items-center gap-1 mb-6 cursor-pointer">
                             <span className="material-symbols-outlined text-[16px]">arrow_back</span>
                             返回 "{selectedTask.keyword}" 分析报告
                         </div>
                         
                         {/* 爆款卡片头部 */}
                         <div className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 mb-8 relative ambient-shadow">
                             <div className="flex flex-col md:flex-row gap-6 items-start md:items-center">
                                 {selectedItem.xianyu_item?.image_url ? (
                                     <img 
                                         src={selectedItem.xianyu_item?.image_url} 
                                         className="w-32 h-32 rounded-xl object-cover border border-border-hairline shadow shrink-0"
                                         referrerPolicy="no-referrer" 
                                     />
                                 ) : (
                                     <div className="w-32 h-32 rounded-xl bg-surface-container border border-border-hairline shrink-0 flex items-center justify-center text-secondary text-xs">暂无图片</div>
                                 )}
                                 
                                 <div className="flex-grow min-w-0">
                                     <h2 className="text-lg font-bold text-on-surface leading-snug">
                                         <a href={selectedItem.xianyu_item?.item_url} target="_blank" className="hover:text-primary transition-all flex items-center gap-1.5">
                                             {selectedItem.xianyu_item?.title}
                                             <span className="material-symbols-outlined text-sm text-secondary">open_in_new</span>
                                         </a>
                                     </h2>
                                     
                                     <div className="flex gap-8 mt-5">
                                         <div>
                                             <span className="text-[10px] text-secondary block font-semibold uppercase">闲鱼售价</span>
                                             <span className="text-2xl font-black text-primary mt-1 block">¥{selectedItem.xianyu_item?.price}</span>
                                         </div>
                                         <div className="w-px h-8 bg-border-hairline self-end"></div>
                                         <div>
                                             <span className="text-[10px] text-secondary block font-semibold uppercase">买家想要数</span>
                                             <span className="text-2xl font-bold text-on-surface mt-1 block">{selectedItem.xianyu_item?.want_count} 人</span>
                                         </div>
                                     </div>
                                 </div>
                             </div>
                             <div className="id-corner">DB_ID: {selectedItem.xianyu_item?.db_id}</div>
                         </div>

                         {/* 货源比价区域 */}
                         <div>
                             <header className="flex justify-between items-center mb-4 flex-wrap gap-4 border-b border-border-hairline pb-4">
                                 <div>
                                     <h3 className="font-sans text-sm font-bold text-on-surface">货源深度对比表 ({sourceListTotal} 条匹配)</h3>
                                 </div>
                                 
                                 <div className="flex flex-wrap items-center justify-end gap-3">
                                     <div className="flex items-center gap-2">
                                         <span className="material-symbols-outlined text-[15px] text-secondary">swap_vert</span>
                                         <span className="text-xs text-secondary font-semibold whitespace-nowrap">排序规则</span>
                                         <div className="relative">
                                             <select
                                                 value={sourceSortRule}
                                                 onChange={(e) => setSourceSortRule(e.target.value)}
                                                 className="appearance-none bg-surface-container-low border border-border-hairline rounded-lg pl-3 pr-8 py-1.5 text-xs font-semibold text-on-surface focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
                                             >
                                                 <option value="price_asc">货源价格正序</option>
                                                 <option value="page_original">页面原始排序</option>
                                             </select>
                                             <span className="material-symbols-outlined absolute right-2 top-1/2 -translate-y-1/2 text-secondary text-[16px] pointer-events-none">expand_more</span>
                                         </div>
                                     </div>

                                     <div className="flex items-center gap-2">
                                         <span className="material-symbols-outlined text-[15px] text-secondary">filter_alt</span>
                                         <span className="text-xs text-secondary font-semibold whitespace-nowrap">货源渠道</span>
                                         <div className="relative">
                                             <select
                                                 value={sourceChannelFilter}
                                                 onChange={(e) => setSourceChannelFilter(e.target.value)}
                                                 className="appearance-none bg-surface-container-low border border-border-hairline rounded-lg pl-3 pr-8 py-1.5 text-xs font-semibold text-on-surface focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
                                             >
                                                 <option value="all">全部渠道</option>
                                                 {getItemUsedChannels(selectedItem).map(channel => (
                                                     <option key={`filter-${channel.channel_id}`} value={channel.channel_id}>
                                                         {channel.channel_label || channel.channel_id}
                                                     </option>
                                                 ))}
                                             </select>
                                             <span className="material-symbols-outlined absolute right-2 top-1/2 -translate-y-1/2 text-secondary text-[16px] pointer-events-none">expand_more</span>
                                         </div>
                                     </div>

                                     {selectableSources.length > 0 && (
                                         <div className="flex items-center gap-4">
                                             <label className="text-xs text-secondary font-semibold cursor-pointer flex items-center gap-1">
                                                 <input 
                                                     type="checkbox" 
                                                     className="rounded border-secondary text-primary focus:ring-primary/20 w-4 h-4 cursor-pointer"
                                                     checked={selectableSources.length > 0 && selectableSources.every(s => selectedIds.includes(s.db_id))}
                                                     onChange={(e) => {
                                                         if (e.target.checked) {
                                                             setSelectedIds(selectableSources.map(s => s.db_id));
                                                         } else {
                                                             setSelectedIds([]);
                                                         }
                                                     }}
                                                 />
                                                 全选未丢弃
                                             </label>
                                             {hasSelectedBatchActions && (
                                                 <>
                                                     <div className="w-px h-5 bg-border-hairline/60"></div>
                                                     
                                                     <div className="flex gap-2">
                                                         {addableIds.length > 0 && (
                                                             <button 
                                                                 className="px-3.5 py-1.5 bg-primary hover:bg-primary-container text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-40" 
                                                                 disabled={batchPublishing || batchDepublishing || batchDeleting} 
                                                                 onClick={doBatchAddToSelection}
                                                             >
                                                                 {batchPublishing ? "加入中..." : `加入选品 (${addableIds.length})`}
                                                             </button>
                                                         )}
                                                         {depublishableIds.length > 0 && (
                                                             <button 
                                                                 className="px-3.5 py-1.5 bg-warning hover:bg-warning/80 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-40" 
                                                                 disabled={batchPublishing || batchDepublishing || batchDeleting} 
                                                                 onClick={doBatchDepublish}
                                                             >
                                                                 {batchDepublishing ? "云同步中..." : `⚠️ 批量下架 (${depublishableIds.length})`}
                                                             </button>
                                                         )}
                                                         {deletableIds.length > 0 && (
                                                             <button 
                                                                 className="px-3.5 py-1.5 bg-error hover:bg-error/85 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-40" 
                                                                 disabled={batchPublishing || batchDepublishing || batchDeleting} 
                                                                 onClick={doBatchDelete}
                                                             >
                                                                 {batchDeleting ? "云注销中..." : `🗑️ 批量删除 (${deletableIds.length})`}
                                                             </button>
                                                         )}
                                                     </div>
                                                 </>
                                             )}
                                         </div>
                                     )}
                                 </div>
                                 <div className="w-full flex justify-end">
                                     <span className="text-[11px] text-secondary">
                                         {sourceSortRuleDescription}
                                     </span>
                                 </div>
                             </header>

                             {/* 货源列表卡片 */}
                             <div className="space-y-4">
                                {detailFallbackFilterChannels.map(channel => {
                                    const filterSummary = normalizeChannelFilterSummary(
                                        channel.filter_summary,
                                        channel.source_filter_snapshot,
                                        channel.channel_type
                                    );
                                    return (
                                        <div key={`fallback-channel-group-${channel.channel_id}`} className="space-y-3">
                                            <div className="flex flex-wrap items-center gap-2 px-1">
                                                <span className="font-sans text-xs font-bold text-on-surface">
                                                    {channel.channel_label || channel.channel_id}
                                                </span>
                                                <span className="px-2 py-0.5 rounded-full bg-surface-container text-secondary border border-border-hairline text-[10px] font-semibold">
                                                    {Number(channel.source_count || 0)} 条货源
                                                </span>
                                            </div>

                                            <div className="px-1 flex flex-wrap items-center gap-2">
                                                {filterSummary.configured.length > 0 && (
                                                    <div className="flex flex-wrap items-center gap-1.5">
                                                        <span className="text-[10px] font-semibold text-secondary">当前渠道货源筛选项</span>
                                                        {filterSummary.configured.map(filterKey => (
                                                            <span
                                                                key={`${channel.channel_id}-fallback-configured-${filterKey}`}
                                                                className="px-2 py-0.5 rounded-full bg-surface-container-low text-on-surface border border-border-hairline text-[10px]"
                                                            >
                                                                {getChannelFilterLabel(filterKey)}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}
                                                {filterSummary.unsupported && (
                                                    <div className="flex flex-wrap items-center gap-1.5">
                                                        <span className="text-[10px] font-semibold text-secondary">当前渠道不支持</span>
                                                        <span className="px-2 py-0.5 rounded-full bg-surface-container-low text-secondary border border-border-hairline text-[10px]">
                                                            当前渠道暂不支持 1688 搜索筛选项
                                                        </span>
                                                    </div>
                                                )}
                                                {filterSummary.legacyMissingSnapshot && (
                                                    <div className="flex flex-wrap items-center gap-1.5">
                                                        <span className="text-[10px] font-semibold text-secondary">历史快照缺失</span>
                                                        <span className="px-2 py-0.5 rounded-full bg-surface-container-low text-secondary border border-border-hairline text-[10px]">
                                                            该渠道资产生成时尚未记录筛选快照，当前无法回溯当时使用的搜索筛选策略
                                                        </span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                                {paginatedChannelGroups.map(group => (
                                     <div key={`channel-group-${group.channel_id}`} className="space-y-3">
                                         <div className="flex flex-wrap items-center gap-2 px-1">
                                             <span className="font-sans text-xs font-bold text-on-surface">
                                                 {group.channel_label || group.channel_id}
                                             </span>
                                             <span className="px-2 py-0.5 rounded-full bg-surface-container text-secondary border border-border-hairline text-[10px] font-semibold">
                                                 {group.source_count} 条货源
                                             </span>
                                         </div>

                                         {(() => {
                                            const filterSummary = normalizeChannelFilterSummary(
                                                group.filter_summary,
                                                group.source_filter_snapshot,
                                                group.channel_type
                                            );
                                            if (
                                                filterSummary.configured.length === 0 &&
                                                !filterSummary.legacyMissingSnapshot &&
                                                !filterSummary.unsupported
                                            ) {
                                                return null;
                                            }
                                            return (
                                                 <div className="px-1 flex flex-wrap items-center gap-2">
                                                     {filterSummary.configured.length > 0 && (
                                                         <div className="flex flex-wrap items-center gap-1.5">
                                                             <span className="text-[10px] font-semibold text-secondary">当前渠道货源筛选项</span>
                                                             {filterSummary.configured.map(filterKey => (
                                                                 <span
                                                                     key={`${group.channel_id}-configured-${filterKey}`}
                                                                     className="px-2 py-0.5 rounded-full bg-surface-container-low text-on-surface border border-border-hairline text-[10px]"
                                                                 >
                                                                     {getChannelFilterLabel(filterKey)}
                                                                 </span>
                                                             ))}
                                                         </div>
                                                     )}
                                                     {filterSummary.unsupported && (
                                                         <div className="flex flex-wrap items-center gap-1.5">
                                                             <span className="text-[10px] font-semibold text-secondary">当前渠道不支持</span>
                                                             <span className="px-2 py-0.5 rounded-full bg-surface-container-low text-secondary border border-border-hairline text-[10px]">
                                                                 当前渠道暂不支持 1688 搜索筛选项
                                                             </span>
                                                         </div>
                                                     )}
                                                     {filterSummary.legacyMissingSnapshot && (
                                                         <div className="flex flex-wrap items-center gap-1.5">
                                                             <span className="text-[10px] font-semibold text-secondary">历史快照缺失</span>
                                                             <span className="px-2 py-0.5 rounded-full bg-surface-container-low text-secondary border border-border-hairline text-[10px]">
                                                                 该渠道资产生成时尚未记录筛选快照，当前无法回溯当时使用的搜索筛选策略
                                                             </span>
                                                         </div>
                                                     )}
                                                 </div>
                                             );
                                         })()}

                                         {group.sources.map((src, i) => { 
                                             const pageOriginalIndex = Number(src.page_original_index || 0);
                                             const isDropped = !!src.drop_reason;
                                             const isChecked = selectedIds.includes(src.db_id);
                                            const detailIncomplete = isSourceDetailIncomplete(src);
                                            const detailIncompleteReason = getSourceDetailIncompleteReason(src);
                                            const sourceMetrics = [
                                                src.pickup_48h_text,
                                                src.pickup_24h_text,
                                                src.month_dispatch_text,
                                                src.seven_day_dispatch_text,
                                                src.listing_count_text,
                                                src.distributor_count_text,
                                                src.waybill_support_text,
                                                src.settled_years_text,
                                            ].filter(Boolean);
                                            return (
                                                 <div 
                                                     className={`bg-surface-container-lowest border rounded-xl p-4 ambient-shadow flex justify-between items-center relative overflow-hidden group ${
                                                         isDropped ? 'border-dashed border-outline-variant/60 opacity-60 bg-surface-container-low' : 'border-border-hairline hover:border-primary transition-colors'
                                                     }`} 
                                                     key={`${group.channel_id}-${src.db_id}-${i}`}
                                                 >
                                                     <div className="flex gap-4 items-center flex-1 min-w-0">
                                                         {!isDropped && (
                                                             <input 
                                                                 type="checkbox" 
                                                                 className="rounded border-secondary text-primary focus:ring-primary/20 w-4 h-4 cursor-pointer shrink-0"
                                                                 checked={isChecked}
                                                                 onChange={(e) => {
                                                                     if (e.target.checked) {
                                                                         setSelectedIds(prev => [...prev, src.db_id]);
                                                                     } else {
                                                                         setSelectedIds(prev => prev.filter(id => id !== src.db_id));
                                                                     }
                                                                 }}
                                                             />
                                                         )}
                                                         {src.images && src.images.length > 0 ? (
                                                             <img 
                                                                 src={src.images[0]} 
                                                                 className="w-16 h-16 rounded-lg object-cover border border-border-hairline shrink-0" 
                                                                 referrerPolicy="no-referrer" 
                                                             />
                                                         ) : (
                                                             <div className="w-16 h-16 rounded-lg bg-surface-container border border-border-hairline shrink-0 flex items-center justify-center text-secondary text-xs">无图</div>
                                                         )}
                                                         
                                                         <div className="flex-1 min-w-0">
                                                             <a 
                                                                 href={src.url} 
                                                                 target="_blank" 
                                                                 className={`font-semibold text-on-surface block text-sm leading-snug ${isDropped ? 'line-through text-secondary' : 'hover:text-primary transition-colors'}`}
                                                             >
                                                                 {src.title}
                                                             </a>
                                                             <div className="flex flex-wrap gap-3 items-center mt-2.5 text-xs text-secondary">
                                                                 {detailIncomplete ? (
                                                                     <span
                                                                         className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-warning/10 text-warning border border-warning/20 text-[10px] font-bold"
                                                                         title={detailIncompleteReason}
                                                                     >
                                                                         <span className="material-symbols-outlined text-[13px] leading-none">warning</span>
                                                                         风控未完整抓取
                                                                     </span>
                                                                 ) : (
                                                                     <span>{src.sku_count > 0 ? `${src.sku_count} 个多属性 SKU 规格` : '一口价商品'}</span>
                                                                 )}
                                                                 <span className="w-1.5 h-1.5 rounded-full bg-border-hairline"></span>
                                                                 <span className={`font-mono border px-2 py-0.5 rounded text-[10px] ${
                                                                     pageOriginalIndex > 0
                                                                         ? 'bg-primary/6 text-primary border-primary/15'
                                                                         : 'bg-surface-container text-secondary border-border-hairline'
                                                                 }`}>
                                                                     页面原始 {pageOriginalIndex > 0 ? `#${pageOriginalIndex}` : '未记录'}
                                                                 </span>
                                                                 <span className="w-1.5 h-1.5 rounded-full bg-border-hairline"></span>
                                                                 <span className="font-mono bg-surface-container px-2 py-0.5 rounded text-[10px]">ID: {src.db_id}</span>
                                                                 {src.company_name && (
                                                                     <>
                                                                         <span className="w-1.5 h-1.5 rounded-full bg-border-hairline"></span>
                                                                         <span className="truncate max-w-[240px]" title={src.company_name}>商家: {src.company_name}</span>
                                                                     </>
                                                                 )}
                                                             </div>
                                                             {sourceMetrics.length > 0 && (
                                                                 <div className="flex flex-wrap gap-2 mt-2">
                                                                     {sourceMetrics.map(metric => {
                                                                         const isPositiveMetric = metric.includes('支持') || metric.includes('揽收') || metric.includes('代发') || metric.includes('铺货数') || metric.includes('分销商数') || metric.includes('入驻');
                                                                         const metricClass = metric.includes('不支持')
                                                                             ? 'bg-error/8 text-error border-error/20'
                                                                             : isPositiveMetric
                                                                                 ? 'bg-success/8 text-success border-success/20'
                                                                                 : 'bg-surface-container text-secondary border-border-hairline';
                                                                         return (
                                                                             <span
                                                                                 key={`${src.db_id}-${metric}`}
                                                                                 className={`px-2 py-0.5 rounded-full border text-[11px] leading-5 ${metricClass}`}
                                                                             >
                                                                                 {metric}
                                                                             </span>
                                                                         );
                                                                     })}
                                                                 </div>
                                                             )}
                                                         </div>
                                                     </div>

                                                     <div className="text-right pl-6 shrink-0 min-w-[200px] flex flex-col justify-between h-16">
                                                         {isDropped ? (
                                                             <div className="flex justify-end items-center h-full">
                                                                 <span className="px-2.5 py-1 rounded bg-error/10 text-error border border-error/20 font-sans text-xs font-bold">
                                                                     已过滤丢弃: {src.drop_reason}
                                                                 </span>
                                                             </div>
                                                         ) : (
                                                                 <>
                                                                     <div className="flex justify-end gap-3 items-baseline">
                                                                     <span className="font-mono text-lg font-black text-on-surface">{formatSourceDisplayPrice(src)}</span>
                                                                 </div>
                                                                 
                                                                 <SelectionButton
                                                                     src={src} 
                                                                     onStatusLoaded={handleStatusLoaded} 
                                                                     batchStatus={batchStatusMap[src.db_id]}
                                                                     batchResult={batchResultMap[src.db_id]}
                                                                 />
                                                             </>
                                                         )}
                                                     </div>
                                                 </div>
                                             );
                                         })}
                                     </div>
                                 ))}

                                {sourceListTotalPages > 1 && (
                                    <div className="flex justify-center items-center gap-4 pt-2">
                                        <button
                                            type="button"
                                            className="w-8 h-8 flex items-center justify-center rounded-lg border border-border-hairline bg-surface-container-lowest text-secondary hover:text-primary hover:border-primary transition-all disabled:opacity-40"
                                            disabled={currentSourceListPage <= 1}
                                            onClick={() => setSourceListPage(currentSourceListPage - 1)}
                                        >
                                            <span className="material-symbols-outlined text-[18px]">chevron_left</span>
                                        </button>
                                        <span className="font-sans text-xs text-secondary font-semibold">
                                            第 {currentSourceListPage} / {sourceListTotalPages} 页（共 {sourceListTotal} 条，每页 {SOURCE_LIST_PAGE_SIZE} 条）
                                        </span>
                                        <button
                                            type="button"
                                            className="w-8 h-8 flex items-center justify-center rounded-lg border border-border-hairline bg-surface-container-lowest text-secondary hover:text-primary hover:border-primary transition-all disabled:opacity-40"
                                            disabled={currentSourceListPage >= sourceListTotalPages}
                                            onClick={() => setSourceListPage(currentSourceListPage + 1)}
                                        >
                                            <span className="material-symbols-outlined text-[18px]">chevron_right</span>
                                        </button>
                                    </div>
                                )}

                                {sourceListTotal === 0 && detailFallbackFilterChannels.length === 0 && (
                                     <div className="bg-surface-container-lowest border border-border-hairline rounded-xl py-12 text-center text-xs text-secondary">
                                         该爆款商品暂未匹配到对应的货源。
                                     </div>
                                 )}

                            </div>
                         </div>
                     </div> 
                ) : view === "published" ? <PublishedManager hideHeader={true} /> : null
                }
            </main>
            {taskStartConfig && (
                <TaskStartConfigModal
                    keyword={taskStartConfig.keyword}
                    crawlConfig={taskStartConfig.crawl}
                    sourceChannelsConfig={taskStartConfig.sourceChannels}
                    llmConfig={taskStartConfig.llm}
                    onStart={createTask}
                    onClose={() => setTaskStartConfig(null)}
                />
            )}
            {confirmDialog && (
                <ActionConfirmModal
                    title={confirmDialog.title}
                    description={confirmDialog.description}
                    confirmLabel={confirmDialog.confirmLabel}
                    tone={confirmDialog.tone}
                    onConfirm={() => {
                        const action = confirmDialog.onConfirm;
                        setConfirmDialog(null);
                        action();
                    }}
                    onClose={() => setConfirmDialog(null)}
                />
            )}
        </React.Fragment>
    );
};


const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
