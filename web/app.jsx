const { useState, useEffect, useRef, useMemo } = React;
const sourceSkuCache = new Map();

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

    const fetchStats = async () => {
        try {
            setLoading(true);
            const resp = await fetch('/api/token/stats');
            const data = await resp.json();
            if (data.status === 'success') {
                setStats(data);
                setError(null);
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
                        <span>审计流水日志 (最近 20 次)</span>
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
                                recent_logs.map(log => (
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

// --- 商品详情模态弹窗组件（解决闪烁与退场动画） ---
const DetailModal = ({ item, onClose, onUpdateItem, handleStatusLoaded, batchStatusMap, batchResultMap }) => {
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
    const margin = (refPrice - costPrice - 20).toFixed(2);
    
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
                        闲鱼已发布商品档案
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
                                        <span className="text-[10px] text-secondary block">发布记录时间</span>
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
                                <>
                                    <div className="flex justify-between items-baseline border-t border-border-hairline/60 pt-2">
                                        <span className="text-xs text-secondary">爆款参考售价</span>
                                        <span className="font-mono text-sm font-bold text-on-surface">¥{item.ref_price}</span>
                                    </div>
                                    <div className="flex justify-between items-baseline border-t border-border-hairline/60 pt-2">
                                        <span className="text-xs text-secondary">预期净利润额</span>
                                        <span className={`font-mono text-base font-black ${parseFloat(margin) > 50 ? 'text-success' : 'text-error'}`}>
                                            ¥{margin}
                                        </span>
                                    </div>
                                </>
                            )}
                            <div className="text-[10px] text-secondary pt-1">
                                ROI {roiPercentage}% · 运费估算已计入
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

// --- 闲鱼已上架商品管理组件 ---
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
    const [selectedProduct, setSelectedProduct] = useState(null); // 记录当前查看详情的已发布商品
    const [sortBy, setSortBy] = useState('publish_time');
    const [sortOrder, setSortOrder] = useState('desc');
    const [selectedIds, setSelectedIds] = useState([]);
    const [batchPublishing, setBatchPublishing] = useState(false);
    const [batchDepublishing, setBatchDepublishing] = useState(false);
    const [batchDeleting, setBatchDeleting] = useState(false);
    const [confirmDialog, setConfirmDialog] = useState(null);

    // 用于收集每个商品的实时状态映射
    const [batchStatusMap, setBatchStatusMap] = useState({});
    const [batchResultMap, setBatchResultMap] = useState({});

    const normalizePublishedStatus = (rawStatus) => {
        if (rawStatus === 'success' || rawStatus === 'done') return 'done';
        if (rawStatus === 'depublished') return 'depublished';
        if (rawStatus === 'failed') return 'failed';
        if (rawStatus === 'pending' || rawStatus === 'publishing' || rawStatus === 'depublishing') return 'publishing';
        if (rawStatus === 'deleting') return 'deleting';
        if (rawStatus === 'deleted' || rawStatus === 'none' || rawStatus === 'idle' || !rawStatus) return 'idle';
        return 'idle';
    };

    const getPublishedItemStatus = (item) => normalizePublishedStatus(batchStatusMap[item.source_db_id] || item.publish_status);
    const selectedItems = items.filter(item => selectedIds.includes(item.source_db_id));
    const publishableIds = selectedItems
        .filter(item => ['idle', 'failed', 'depublished'].includes(getPublishedItemStatus(item)))
        .map(item => item.source_db_id);
    const depublishableIds = selectedItems
        .filter(item => getPublishedItemStatus(item) === 'done')
        .map(item => item.source_db_id);
    const deletableIds = selectedItems
        .filter(item => ['depublished', 'failed'].includes(getPublishedItemStatus(item)))
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
            console.error("加载已发布商品失败:", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchPublishedProducts();
    }, [page, keyword, filterStatus, minSourcePrice, maxSourcePrice, minRefPrice, maxRefPrice, sortBy, sortOrder, refreshTrigger]);

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
                '已下架商品会执行云端删除；同步失败商品只会清理本地记录。此操作不可恢复。'
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
                        闲鱼上架商品中枢
                    </h1>
                    <p className="font-sans text-sm text-secondary mt-1">管理并监控已经在闲鱼铺货成功的商品，支持与 1688 源头采购价、物流信息实时联动。点击行项目可展开详情数据与下架控制。</p>
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
                            placeholder="输入货源标题、闲鱼发布标题或者商品 ID 进行搜索..."
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
                        正在同步已上架商品资产列表...
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
                        </div>

                        {selectedIds.length > 0 && (
                            <div className="flex items-center gap-2 flex-wrap min-h-[32px]">
                                {publishableIds.length > 0 && (
                                    <button
                                        className="px-3.5 py-1.5 bg-primary hover:bg-primary-container text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-40"
                                        disabled={batchPublishing || batchDepublishing || batchDeleting}
                                        onClick={doBatchPublish}
                                    >
                                        {batchPublishing ? "云同步中..." : `🚀 批量发布 (${publishableIds.length})`}
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
                                    
                                    let statusText = '未知';
                                    let statusClass = 'bg-secondary/10 text-secondary border-secondary/20';
                                    let pulseColor = 'bg-secondary';

                                    if (currentStatus === 'done') {
                                        statusText = '已上架';
                                        statusClass = 'bg-success/10 text-success border-success/20';
                                        pulseColor = 'bg-success';
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
                                                </div>
                                            </td>
                                            <td className="p-cell-padding font-mono font-bold text-on-surface">{item.xianyu_item_id || '-'}</td>
                                            <td className="p-cell-padding">
                                                <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold border ${statusClass}`}>
                                                    <span className={`w-1.5 h-1.5 rounded-full ${pulseColor} animate-pulse`}></span>
                                                    {statusText}
                                                </span>
                                            </td>
                                            <td className="p-cell-padding font-mono text-secondary font-bold">¥{item.source_price}</td>
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
                                共 {total} 个商品，当前显示第 {page} / {totalPages} 页
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
                    <p className="text-secondary font-semibold mt-4 text-sm">📦 暂无已发布在闲鱼的商品记录。</p>
                    <p className="text-xs text-secondary/60 mt-1">您可以先前往“决策资产”库中发布选中的匹配商品。</p>
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
                '如果商品已下架，会同时执行闲鱼云端删除；如果是同步失败商品，则只清理本地记录。此操作不可恢复。'
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
            { key: 'encrypted_waybill', label: '密文面单', group: '服务能力' }
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
    const currentSourceDisplayName = currentSourceRealtimeName || currentSourceLabel || '';
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
                                            loginReadySourceAccounts.map(account => {
                                                const isChecked = visibleActiveSourceAccountIds.includes(account.account_id);
                                                return (
                                                    <label key={account.account_id} className="inline-flex items-center gap-2 text-xs text-on-surface font-sans cursor-pointer">
                                                        <input
                                                            type="checkbox"
                                                            checked={isChecked}
                                                            onChange={(e) => handleSourceActiveAccountToggle(account.account_id, e.target.checked)}
                                                            className="rounded border-border-hairline text-primary focus:ring-primary/30"
                                                        />
                                                        <span>{account.label || account.account_id}</span>
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
                                                    {account.label || `渠道账号 ${idx + 1}`}
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
                                                        真实账号名：{currentSourceRealtimeName || '未识别'}
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
                                    控制每个闲鱼爆款商品去 1688 抓取的最大候选商品深度（合理区间：5 - 50）。数值越大扫描更彻底，但也会消耗更多抓取时间与资源。
                                </p>
                                <div className="flex items-center gap-4">
                                    <input 
                                        type="range"
                                        min="5"
                                        max="50"
                                        step="1"
                                        value={crawlConfig.source_limit_1688}
                                        onChange={(e) => setCrawlConfig(prev => ({ ...prev, source_limit_1688: parseInt(e.target.value) || 10 }))}
                                        className="flex-1 h-1.5 bg-surface-container rounded-lg appearance-none cursor-pointer accent-primary"
                                    />
                                    <input 
                                        type="number"
                                        min="5"
                                        max="50"
                                        value={crawlConfig.source_limit_1688}
                                        onChange={(e) => {
                                            let val = parseInt(e.target.value) || 10;
                                            if (val < 5) val = 5;
                                            if (val > 50) val = 50;
                                            setCrawlConfig(prev => ({ ...prev, source_limit_1688: val }));
                                        }}
                                        className="w-16 bg-surface-container-low border border-border-hairline text-on-surface text-center font-mono text-xs rounded-lg px-2 py-1 focus:outline-none focus:border-primary"
                                    />
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
                                                        {currentCrawlChannel.crawl_accounts.map(account => {
                                                            const report = account.session_report || {};
                                                            const isChecked = currentCrawlSelectedAccountIds.includes(account.account_id);
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
                                                                                {account.session_report?.account_name || account.label || account.account_id}
                                                                            </span>
                                                                            <span className="inline-flex items-center gap-1 text-[10px] text-success">
                                                                                <span className="w-1.5 h-1.5 rounded-full bg-success"></span>
                                                                                <span>{report.status_text || '登录正常'}</span>
                                                                            </span>
                                                                        </div>
                                                                        <div className="mt-1 text-[11px] text-secondary">
                                                                            渠道账号备注：{account.label || account.account_id}
                                                                        </div>
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
    const [sysStatus, setSysStatus] = useState({});
    const [newKeyword, setNewKeyword] = useState("");

    const [selectedIds, setSelectedIds] = useState([]);
    const [batchPublishing, setBatchPublishing] = useState(false);
    const [batchDepublishing, setBatchDepublishing] = useState(false);
    const [batchDeleting, setBatchDeleting] = useState(false);
    const [batchStatusMap, setBatchStatusMap] = useState({});
    const [batchResultMap, setBatchResultMap] = useState({});
    const [confirmDialog, setConfirmDialog] = useState(null);
    const [sourceChannelFilter, setSourceChannelFilter] = useState("all");

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
        } else {
            setSelectedIds([]);
            setBatchStatusMap({});
            setBatchResultMap({});
        }
    }, [selectedItem]);

    const selectableSources = (selectedItem?.sources || []).filter(src => !src.drop_reason);
    const selectedSources = selectableSources.filter(src => selectedIds.includes(src.db_id));
    const normalizeSourceActionStatus = (rawStatus) => {
        if (rawStatus === 'success' || rawStatus === 'done') return 'done';
        if (rawStatus === 'depublished') return 'depublished';
        if (rawStatus === 'publishing' || rawStatus === 'depublishing' || rawStatus === 'deleting' || rawStatus === 'failed') return rawStatus;
        if (rawStatus === 'deleted' || rawStatus === 'none' || rawStatus === 'idle' || !rawStatus) return 'idle';
        return 'idle';
    };
    const getSourceActionStatus = (src) => normalizeSourceActionStatus(batchStatusMap[src.db_id] || src.publish_status || 'idle');
    const publishableIds = selectedSources
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

    const createTask = async () => { 
        if (!newKeyword) return; 
        await fetch("/api/tasks", { 
            method: "POST", 
            headers: { "Content-Type": "application/json" }, 
            body: JSON.stringify({ keyword: newKeyword }) 
        }); 
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
    
    const doBatchPublish = async () => {
        if (selectedIds.length === 0) {
            alert("请先选择要批量发布的货源");
            return;
        }
        setBatchPublishing(true);
        
        const toPublishIds = [...publishableIds];
        if (toPublishIds.length === 0) {
            setBatchPublishing(false);
            alert("当前勾选商品里，没有可执行批量发布的货源。");
            return;
        }
        
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
            alert("当前勾选商品里，没有可删除的已下架或同步失败货源。");
            return;
        }
        setConfirmDialog({
            title: '确认批量删除',
            description: [
                `即将批量删除 ${toDeleteIds.length} 个货源记录。`,
                '已下架商品会执行云端删除；同步失败商品只会清理本地记录。此操作不可恢复。'
            ],
            confirmLabel: `确认删除 ${toDeleteIds.length} 项`,
            tone: 'danger',
            onConfirm: () => executeSourceBatchDelete(toDeleteIds)
        });
    };

    const getItemUsedChannels = (group) => {
        if (Array.isArray(group?.used_channels) && group.used_channels.length > 0) {
            return group.used_channels;
        }
        const usedMap = {};
        (group?.sources || []).forEach(source => {
            const channelId = source?.source_channel_id || 'ali1688';
            if (!usedMap[channelId]) {
                usedMap[channelId] = {
                    channel_id: channelId,
                    channel_type: source?.source_channel_type || 'ali1688',
                    channel_label: source?.source_channel_label || '1688 货源渠道',
                };
            }
        });
        return Object.values(usedMap);
    };

    const getTaskUsedChannels = (task) => {
        if (Array.isArray(task?.used_channels) && task.used_channels.length > 0) {
            return task.used_channels;
        }
        return [];
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
    };

    const getChannelFilterLabel = (filterKey) => channelSearchFilterLabelMap[filterKey] || filterKey;

    const summarizeChannelFilterSnapshot = (snapshot) => {
        if (!snapshot || typeof snapshot !== 'object') {
            return {
                configured: [],
                queryInjected: [],
                applied: [],
                unapplied: [],
                filterStatusMap: {},
                queryVerificationDetails: {},
                mappingStage: '',
                mappingNotes: '',
            };
        }
        const filterStatusMap = snapshot.filter_status_map && typeof snapshot.filter_status_map === 'object'
            ? snapshot.filter_status_map
            : {};
        const configured = Array.isArray(snapshot.configured_enabled_filter_keys)
            ? snapshot.configured_enabled_filter_keys
            : Array.isArray(snapshot.configured_filter_keys)
                ? snapshot.configured_filter_keys
            : Array.isArray(snapshot.enabled_filter_keys)
                ? snapshot.enabled_filter_keys
                : Object.entries(snapshot.filters || {})
                    .filter(([, enabled]) => !!enabled)
                    .map(([key]) => key);
        const queryInjected = Object.entries(filterStatusMap)
            .filter(([, meta]) => meta?.status === 'query_injected_pending_verification')
            .map(([key]) => key);
        const applied = Object.entries(filterStatusMap)
            .filter(([, meta]) => meta?.status === 'applied')
            .map(([key]) => key);
        const unapplied = Object.entries(filterStatusMap)
            .filter(([, meta]) => meta?.status === 'unapplied')
            .map(([key]) => key);
        const fallbackQueryInjected = Array.isArray(snapshot.query_injected_filter_keys)
            ? snapshot.query_injected_filter_keys
            : [];
        const fallbackApplied = Array.isArray(snapshot.applied_filter_keys) ? snapshot.applied_filter_keys : [];
        const fallbackQueryInjectedPending = fallbackQueryInjected.filter((key) => !fallbackApplied.includes(key));
        const fallbackUnapplied = (Array.isArray(snapshot.unapplied_filter_keys) ? snapshot.unapplied_filter_keys : [])
            .filter((key) => !fallbackQueryInjected.includes(key));
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
        return {
            configured,
            queryInjected: queryInjected.length > 0 || applied.length > 0 || unapplied.length > 0 ? queryInjected : fallbackQueryInjectedPending,
            applied: applied.length > 0 || queryInjected.length > 0 || unapplied.length > 0 ? applied : fallbackApplied,
            unapplied: unapplied.length > 0 || queryInjected.length > 0 || applied.length > 0 ? unapplied : fallbackUnapplied,
            filterStatusMap,
            queryVerificationDetails,
            mappingStage: snapshot.mapping_stage || '',
            mappingNotes: snapshot.mapping_notes || '',
        };
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
        if (detail.probe_mode === 'html_text_scan') {
            const matchedTerms = Array.isArray(detail.matched_terms)
                ? detail.matched_terms.filter(Boolean)
                : [];
            const probeTerms = Array.isArray(detail.probe_terms)
                ? detail.probe_terms.filter(Boolean)
                : [];
            const detailParts = [];
            if (matchedTerms.length > 0) {
                detailParts.push(`页面文案命中：${matchedTerms.join(' / ')}`);
            } else if (probeTerms.length > 0) {
                detailParts.push(`探测文案：${probeTerms.join(' / ')}`);
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
            return detailParts.join(' · ');
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
        if (mappingHint) {
            hintParts.push(mappingHint);
        }
        return hintParts.join(' · ');
    };

    const getSourceEstimatedProfit = (source, xianyuPrice) => {
        const listingPrice = parseFloat(xianyuPrice || 0);
        const costPrice = parseFloat(source?.min_price || 0);
        return listingPrice - costPrice - 20;
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
        setSelectedTask(task);
        setActiveView("results");
    };
    
    const enterItemDetail = (group) => {
        setSelectedItem(group);
        setSourceChannelFilter("all");
        setActiveView("item_detail");
    };
    const completedTasks = tasks.filter(t => t.status === '已完成');
    const resolvedChannelGroups = useMemo(() => {
        if (!selectedItem) return [];
        const rawGroups = Array.isArray(selectedItem.channel_groups) && selectedItem.channel_groups.length > 0
            ? selectedItem.channel_groups
            : buildChannelGroupsFromSources(selectedItem.sources || []);
        const listingPrice = parseFloat(selectedItem.xianyu_item?.price || 0);
        const decorateGroup = (group) => {
            const sortedSources = [...(group.sources || [])].sort(
                (left, right) => getSourceEstimatedProfit(right, listingPrice) - getSourceEstimatedProfit(left, listingPrice)
            );
            const bestEstimatedProfit = sortedSources.length > 0
                ? Math.max(...sortedSources.map(source => getSourceEstimatedProfit(source, listingPrice)))
                : Number.NEGATIVE_INFINITY;
            return {
                ...group,
                sources: sortedSources,
                best_estimated_profit: bestEstimatedProfit,
            };
        };
        return rawGroups
            .map(decorateGroup)
            .filter(group => sourceChannelFilter === "all" || group.channel_id === sourceChannelFilter)
            .sort((left, right) => {
                return right.best_estimated_profit - left.best_estimated_profit;
            });
    }, [selectedItem, sourceChannelFilter]);
    const pageIntro = (() => {
        if (view === 'item_detail') return null;
        if (view === 'dashboard') return { icon: 'dashboard', title: '控制台中心', description: '全局扫描 Worker 统计面板及后台状态概览。' };
        if (view === 'tasks') return { icon: 'list_alt', title: '任务队列中心', description: '查看和管理各个品类的深度爬取状态。左侧显示活跃进行中队列，右侧显示归档历史。' };
        if (view === 'results' && selectedTask) return { icon: 'query_stats', title: `“${selectedTask.keyword}” 爆款深度对比报告`, description: '每个爆款商品均可以点入查看对应货源渠道的深度对比结果。' };
        if (view === 'results') return { icon: 'travel_explore', title: '选品决策资产库', description: '系统已完成的爆款数据中心。点击各个品类卡片，可直接穿透查看商品的多渠道货源采购价与深度分析。' };
        if (view === 'published') return { icon: 'shopping_bag', title: '闲鱼上架商品中枢', description: '管理并监控已经在闲鱼铺货成功的商品，支持与 1688 源头采购价、物流信息实时联动。点击行项目可展开详情数据与下架控制。' };
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
        const isActive = (itemKey === 'results' && ['results', 'item_detail'].includes(view)) || view === itemKey;
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
                        <span className={`sidebar-fade-content ${sidebarCollapsed ? 'is-collapsed' : ''}`}>已发布管理</span>
                        {sidebarCollapsed && <span className="sidebar-tooltip">已发布管理</span>}
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
                                        onClick={createTask}
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
                                        {completedTasks.map(t => (
                                            <div 
                                                className="bg-surface-container-lowest border border-border-hairline rounded-xl p-5 relative overflow-hidden ambient-shadow hover:border-primary transition-colors cursor-pointer group"
                                                key={t.id}
                                                onClick={() => loadTaskResults(t)}
                                            >
                                                <div className="flex justify-between items-start mb-2">
                                                    <div>
                                                        <div className="font-bold text-on-surface text-base group-hover:text-primary transition-colors">{t.keyword}</div>
                                                        <div className="flex items-center gap-2 mt-1.5">
                                                            <span className="text-[10px] text-secondary font-mono">TASK_ID: {t.id}</span>
                                                            {renderTaskTypeBadge(t.input_type)}
                                                        </div>
                                                    </div>
                                                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-success/10 text-success border border-success/20">
                                                        已完成
                                                    </span>
                                                </div>

                                                <p className="text-xs text-secondary mt-2">调研时间: {t.created_at}</p>

                                                {getTaskUsedChannels(t).length > 0 && (
                                                    <div className="flex flex-wrap gap-1.5 mt-3 min-h-[24px]">
                                                        {getTaskUsedChannels(t).map(channel => (
                                                            <span
                                                                key={`archive-${t.id}-${channel.channel_id}`}
                                                                className="px-2 py-0.5 rounded-full bg-primary/8 text-primary border border-primary/15 text-[10px] font-semibold"
                                                            >
                                                                {channel.channel_label || channel.channel_id}
                                                                {channel.source_count > 0 ? ` · ${channel.source_count}` : ''}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}

                                                <div className="flex justify-between items-center border-t border-border-hairline/60 pt-3 mt-4">
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
                                                        <button 
                                                            className="px-3 py-1 bg-surface-container border border-border-hairline hover:border-primary text-secondary hover:text-primary rounded text-xs font-semibold transition-colors" 
                                                            onClick={(e) => { e.stopPropagation(); retryTask(t.id); }}
                                                        >
                                                            重新扫描
                                                        </button>
                                                        <button 
                                                            className="px-3 py-1 bg-error/10 border border-error/20 hover:bg-error hover:text-white text-error rounded text-xs font-semibold transition-all opacity-0 group-hover:opacity-100" 
                                                            onClick={(e) => { e.stopPropagation(); deleteTask(t.id); }}
                                                        >
                                                            逻辑删除
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
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
                     selectedTask ? ( 
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

                             <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                                 {detailedItems.length > 0 ? detailedItems.map((group) => (
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
                                             <div className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded bg-success text-white font-sans text-[9px] font-bold shadow">
                                                 98% Match
                                             </div>
                                         </div>
                                         
                                         <div className="p-4">
                                             <h3 className="text-xs font-bold text-on-surface line-clamp-2 h-9 leading-relaxed">
                                                 {group.xianyu_item?.title}
                                             </h3>
                                             <div className="flex flex-wrap gap-1.5 mt-3 min-h-[24px]">
                                                 {getItemUsedChannels(group).map(channel => (
                                                     <span
                                                         key={`${group.rank}-${channel.channel_id}`}
                                                         className="px-2 py-0.5 rounded-full bg-surface-container text-secondary border border-border-hairline text-[10px] font-semibold"
                                                     >
                                                         {channel.channel_label || channel.channel_id}
                                                     </span>
                                                 ))}
                                             </div>
                                             
                                             <div className="flex justify-between items-center mt-4 border-t border-border-hairline/60 pt-3">
                                                 <span className="text-base font-black text-primary">¥{group.xianyu_item?.price}</span>
                                                 <span className="text-[10px] text-secondary font-semibold bg-surface-container px-2 py-0.5 rounded-full border border-border-hairline">
                                                     {group.sources?.length || 0} 个比价货源
                                                 </span>
                                             </div>
                                         </div>
                                         <div className="id-corner">DB_ID: {group.xianyu_item?.db_id}</div>
                                     </div>
                                 )) : (
                                     <div className="col-span-full bg-surface-container-lowest border border-border-hairline rounded-xl py-24 text-center">
                                         <p className="text-secondary text-sm">该分析任务尚未产生可匹配的比价数据。</p>
                                     </div>
                                 )}
                             </div>
                         </div> 
                     ) : (
                         <div>
                             <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
                                 {completedTasks.map(t => (
                                     <div 
                                         className="bg-surface-container-lowest border border-border-hairline rounded-xl p-6 relative overflow-hidden ambient-shadow hover:border-primary transition-all duration-150 cursor-pointer group" 
                                         key={t.id} 
                                         onClick={() => loadTaskResults(t)}
                                     >
                                         <div className="flex flex-col justify-between h-28">
                                             <div className="text-center">
                                                 <div className="font-black text-on-surface text-lg group-hover:text-primary transition-colors">{t.keyword}</div>
                                                 <div className="text-xs text-secondary mt-2">调研时间: {t.created_at}</div>
                                             </div>

                                             {getTaskUsedChannels(t).length > 0 && (
                                                 <div className="flex flex-wrap justify-center gap-1.5 mt-3 min-h-[24px]">
                                                     {getTaskUsedChannels(t).map(channel => (
                                                         <span
                                                             key={`results-${t.id}-${channel.channel_id}`}
                                                             className="px-2 py-0.5 rounded-full bg-primary/8 text-primary border border-primary/15 text-[10px] font-semibold"
                                                         >
                                                             {channel.channel_label || channel.channel_id}
                                                             {channel.source_count > 0 ? ` · ${channel.source_count}` : ''}
                                                         </span>
                                                     ))}
                                                 </div>
                                             )}
                                             
                                             <div className="flex justify-between items-end border-t border-border-hairline/60 pt-2 font-mono text-[9px] text-secondary/60 mt-3">
                                                 <span>V.{t.version}</span>
                                                 <span>ID: {t.id}</span>
                                             </div>
                                         </div>
                                     </div>
                                 ))}
                             </div>
                         </div>
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
                                     <h3 className="font-sans text-sm font-bold text-on-surface">货源深度对比表 ({selectedItem.sources?.length || 0} 条匹配)</h3>
                                     <div className="flex flex-wrap gap-1.5 mt-2">
                                         {getItemUsedChannels(selectedItem).map(channel => (
                                             <span
                                                 key={`detail-${channel.channel_id}`}
                                                 className="px-2 py-0.5 rounded-full bg-primary/8 text-primary border border-primary/15 text-[10px] font-semibold"
                                             >
                                                 {channel.channel_label || channel.channel_id}
                                             </span>
                                         ))}
                                     </div>
                                 </div>
                                 
                                 <div className="flex flex-wrap items-center justify-end gap-3">
                                     <div className="flex items-center gap-2 bg-surface-container border border-border-hairline px-3 py-2 rounded-xl ambient-shadow">
                                         <span className="material-symbols-outlined text-[15px] text-secondary">swap_vert</span>
                                         <span className="text-xs text-secondary font-semibold whitespace-nowrap">固定排序</span>
                                         <span className="px-2.5 py-1 rounded-lg bg-surface-container-low border border-border-hairline text-xs font-semibold text-on-surface whitespace-nowrap">
                                             预估纯利倒序
                                         </span>
                                     </div>

                                     <div className="flex items-center gap-2 bg-surface-container border border-border-hairline px-3 py-2 rounded-xl ambient-shadow">
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
                                         <div className="flex items-center gap-4 bg-surface-container border border-border-hairline px-4 py-2 rounded-xl ambient-shadow">
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
                                                         {publishableIds.length > 0 && (
                                                             <button 
                                                                 className="px-3.5 py-1.5 bg-primary hover:bg-primary-container text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-40" 
                                                                 disabled={batchPublishing || batchDepublishing || batchDeleting} 
                                                                 onClick={doBatchPublish}
                                                             >
                                                                 {batchPublishing ? "云同步中..." : `🚀 批量发布 (${publishableIds.length})`}
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
                                         当前结果固定按预估纯利从高到低排序，渠道筛选仅影响当前展示范围。
                                     </span>
                                 </div>
                             </header>

                             {/* 货源列表卡片 */}
                             <div className="space-y-4">
                                {resolvedChannelGroups.map(group => (
                                     <div key={`channel-group-${group.channel_id}`} className="space-y-3">
                                         <div className="flex flex-wrap items-center gap-2 px-1">
                                             <span className="font-sans text-xs font-bold text-on-surface">
                                                 {group.channel_label || group.channel_id}
                                             </span>
                                             <span className="px-2 py-0.5 rounded-full bg-surface-container text-secondary border border-border-hairline text-[10px] font-semibold">
                                                 {group.source_count} 条货源
                                             </span>
                                             {group.account_labels.map(accountLabel => (
                                                 <span
                                                     key={`${group.channel_id}-${accountLabel}`}
                                                     className="px-2 py-0.5 rounded-full bg-surface-container-low text-secondary border border-border-hairline text-[10px]"
                                                 >
                                                     {accountLabel}
                                                 </span>
                                             ))}
                                             {group.account_labels.length === 0 && (
                                                 <span className="px-2 py-0.5 rounded-full bg-warning/8 text-warning border border-warning/20 text-[10px]">
                                                     历史资产未记录账号快照
                                                 </span>
                                             )}
                                         </div>

                                         {(() => {
                                             const filterSummary = summarizeChannelFilterSnapshot(group.source_filter_snapshot);
                                             if (
                                                 filterSummary.configured.length === 0 &&
                                                 filterSummary.applied.length === 0 &&
                                                 filterSummary.unapplied.length === 0
                                             ) {
                                                 return null;
                                             }
                                             return (
                                                 <div className="px-1 flex flex-wrap items-center gap-2">
                                                     {filterSummary.configured.length > 0 && (
                                                         <div className="flex flex-wrap items-center gap-1.5">
                                                             <span className="text-[10px] font-semibold text-secondary">已配置</span>
                                                             {filterSummary.configured.map(filterKey => (
                                                                 <span
                                                                     key={`${group.channel_id}-configured-${filterKey}`}
                                                                     className="px-2 py-0.5 rounded-full bg-primary/8 text-primary border border-primary/15 text-[10px]"
                                                                 >
                                                                     {getChannelFilterLabel(filterKey)}
                                                                 </span>
                                                             ))}
                                                         </div>
                                                     )}
                                                     {filterSummary.queryInjected.length > 0 && (
                                                         <div className="flex flex-wrap items-center gap-1.5">
                                                             <span className="text-[10px] font-semibold text-secondary">已注入待验证</span>
                                                             {filterSummary.queryInjected.map(filterKey => (
                                                                 <span
                                                                     key={`${group.channel_id}-query-injected-${filterKey}`}
                                                                     className="px-2 py-0.5 rounded-full bg-secondary/10 text-secondary border border-border-hairline text-[10px]"
                                                                 >
                                                                     {getChannelFilterLabel(filterKey)}
                                                                 </span>
                                                             ))}
                                                         </div>
                                                     )}
                                                     {filterSummary.applied.length > 0 && (
                                                         <div className="flex flex-wrap items-center gap-1.5">
                                                             <span className="text-[10px] font-semibold text-secondary">已生效</span>
                                                             {filterSummary.applied.map(filterKey => (
                                                                 <span
                                                                     key={`${group.channel_id}-applied-${filterKey}`}
                                                                     className="px-2 py-0.5 rounded-full bg-success/8 text-success border border-success/20 text-[10px]"
                                                                 >
                                                                     {getChannelFilterLabel(filterKey)}
                                                                 </span>
                                                             ))}
                                                         </div>
                                                     )}
                                                     {filterSummary.unapplied.length > 0 && (
                                                         <div className="flex flex-wrap items-center gap-1.5">
                                                             <span className="text-[10px] font-semibold text-secondary">待映射</span>
                                                             {filterSummary.unapplied.map(filterKey => (
                                                                 <span
                                                                     key={`${group.channel_id}-unapplied-${filterKey}`}
                                                                     className="px-2 py-0.5 rounded-full bg-warning/8 text-warning border border-warning/20 text-[10px]"
                                                                 >
                                                                     {getChannelFilterLabel(filterKey)}
                                                                 </span>
                                                             ))}
                                                         </div>
                                                     )}
                                                     {filterSummary.mappingStage === 'snapshot_only' && !filterSummary.mappingNotes && (
                                                         <span className="text-[10px] text-secondary">
                                                             当前仅完成配置快照透传，真实搜索参数映射仍在继续接入。
                                                         </span>
                                                     )}
                                                     {filterSummary.mappingNotes && (
                                                         <span className="text-[10px] text-secondary">
                                                             {filterSummary.mappingNotes}
                                                         </span>
                                                     )}
                                                     {filterSummary.applied.length > 0 && (
                                                         <div className="w-full flex flex-wrap items-center gap-1.5">
                                                             <span className="text-[10px] font-semibold text-secondary">命中参数</span>
                                                             {filterSummary.applied.map((filterKey) => {
                                                                 const detailText = formatQueryVerificationDetail(
                                                                     filterSummary.queryVerificationDetails?.[filterKey]
                                                                 );
                                                                 if (!detailText) {
                                                                     return null;
                                                                 }
                                                                 return (
                                                                     <span
                                                                         key={`${group.channel_id}-applied-detail-${filterKey}`}
                                                                         className="px-2 py-0.5 rounded-full bg-success/6 text-success border border-success/15 text-[10px]"
                                                                     >
                                                                         {getChannelFilterLabel(filterKey)}: {detailText}
                                                                     </span>
                                                                 );
                                                             })}
                                                         </div>
                                                     )}
                                                     {filterSummary.queryInjected.length > 0 && (
                                                         <div className="w-full flex flex-wrap items-center gap-1.5">
                                                             <span className="text-[10px] font-semibold text-secondary">待验证线索</span>
                                                             {filterSummary.queryInjected.map((filterKey) => {
                                                                 const detailText = formatQueryVerificationDetail(
                                                                     filterSummary.queryVerificationDetails?.[filterKey]
                                                                 );
                                                                 const reasonText = getFilterStatusReasonText(
                                                                     filterSummary.filterStatusMap?.[filterKey]?.reason
                                                                 );
                                                                 if (!detailText) {
                                                                     return (
                                                                         <span
                                                                             key={`${group.channel_id}-pending-detail-${filterKey}`}
                                                                             className="px-2 py-0.5 rounded-full bg-secondary/8 text-secondary border border-border-hairline text-[10px]"
                                                                         >
                                                                             {getChannelFilterLabel(filterKey)}{reasonText ? `: ${reasonText}` : ''}
                                                                         </span>
                                                                     );
                                                                 }
                                                                 return (
                                                                     <span
                                                                         key={`${group.channel_id}-pending-detail-${filterKey}`}
                                                                         className="px-2 py-0.5 rounded-full bg-secondary/8 text-secondary border border-border-hairline text-[10px]"
                                                                     >
                                                                         {getChannelFilterLabel(filterKey)}: {detailText}{reasonText ? ` · ${reasonText}` : ''}
                                                                     </span>
                                                                 );
                                                             })}
                                                         </div>
                                                     )}
                                                     {filterSummary.unapplied.length > 0 && (
                                                         <div className="w-full flex flex-wrap items-center gap-1.5">
                                                             <span className="text-[10px] font-semibold text-secondary">未应用原因</span>
                                                             {filterSummary.unapplied.map((filterKey) => {
                                                                 const filterMeta = filterSummary.filterStatusMap?.[filterKey];
                                                                 const reasonText = getFilterStatusReasonText(
                                                                     filterMeta?.reason
                                                                 );
                                                                 const detailText = formatQueryVerificationDetail(
                                                                     filterSummary.queryVerificationDetails?.[filterKey]
                                                                 );
                                                                 const hintText = formatFilterMappingHint(filterMeta, filterKey);
                                                                 return (
                                                                     <span
                                                                         key={`${group.channel_id}-unapplied-reason-${filterKey}`}
                                                                         className="px-2 py-0.5 rounded-full bg-warning/6 text-warning border border-warning/15 text-[10px]"
                                                                     >
                                                                         {getChannelFilterLabel(filterKey)}
                                                                         {detailText ? `: ${detailText}` : ''}
                                                                         {reasonText ? `${detailText ? ' · ' : ': '}${reasonText}` : ''}
                                                                         {hintText ? ` · ${hintText}` : ''}
                                                                     </span>
                                                                 );
                                                             })}
                                                         </div>
                                                     )}
                                                 </div>
                                             );
                                         })()}

                                         {group.sources.map((src, i) => { 
                                             const marginVal = (selectedItem.xianyu_item?.price - src.min_price - 20).toFixed(2); 
                                             const isDropped = !!src.drop_reason;
                                             const isChecked = selectedIds.includes(src.db_id);
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
                                                                 <span>{src.sku_count > 0 ? `${src.sku_count} 个多属性 SKU 规格` : '一口价商品'}</span>
                                                                 <span className="w-1.5 h-1.5 rounded-full bg-border-hairline"></span>
                                                                 <span className="font-mono bg-surface-container px-2 py-0.5 rounded text-[10px]">ID: {src.db_id}</span>
                                                                 {src.source_account_label && (
                                                                     <>
                                                                         <span className="w-1.5 h-1.5 rounded-full bg-border-hairline"></span>
                                                                         <span>{src.source_account_label}</span>
                                                                     </>
                                                                 )}
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
                                                                     <span className="font-mono text-lg font-black text-on-surface">¥{src.min_price}</span>
                                                                     <span className={`text-xs font-bold ${parseFloat(marginVal) > 50 ? 'text-success' : 'text-error'}`}>
                                                                         预估纯利: ¥{marginVal}
                                                                     </span>
                                                                 </div>
                                                                 
                                                                 <PublishButton 
                                                                     src={src} 
                                                                     xianyuPrice={selectedItem.xianyu_item?.price} 
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

                                 {selectedItem.sources?.length === 0 && (
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
