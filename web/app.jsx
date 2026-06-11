const { useState, useEffect, useRef } = React;

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
const LogViewer = ({ tasks }) => {
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
            <header className="mb-6">
                <h1 className="font-sans text-2xl font-bold text-on-surface">任务日志中心</h1>
                <p className="font-sans text-sm text-secondary mt-1">实时监控扫描Worker的后台标准输出日志。</p>
            </header>
            
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
const TokenStatsView = () => {
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
            <header className="mb-6 flex justify-between items-center">
                <div>
                    <h1 className="font-sans text-2xl font-bold text-on-surface">AI Token 计量舱</h1>
                    <p className="font-sans text-sm text-secondary mt-1">系统大模型调用统计、模型消耗占比及审计流水线。</p>
                </div>
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
                        <div className="space-y-4">
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
                        <div className="space-y-4">
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

// --- 商品详情模态弹窗组件（解决闪烁与退场动画） ---
const DetailModal = ({ item, onClose, onUpdateItem, handleStatusLoaded, batchStatusMap, batchResultMap }) => {
    const [active, setActive] = useState(false);
    const [skus, setSkus] = useState([]);
    const [loadingSkus, setLoadingSkus] = useState(false);

    useEffect(() => {
        setLoadingSkus(true);
        fetch(`/api/source_skus/${item.source_db_id}`)
            .then(r => r.json())
            .then(res => {
                setSkus(res.skus || []);
            })
            .catch(err => console.error("加载详情SKU失败:", err))
            .finally(() => setLoadingSkus(false));
    }, [item.source_db_id]);

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
                style={{ width: '840px' }}
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
                
                <div className="p-6 overflow-y-auto max-h-[72vh] flex gap-6">
                    {/* 左侧主要信息: Span 8 布局 */}
                    <div className="flex-1 flex flex-col gap-5">
                        <div className="flex gap-4 items-start">
                            {item.source_image ? (
                                <img 
                                    src={item.source_image} 
                                    className="w-36 h-36 rounded-xl object-cover border border-border-hairline ambient-shadow shrink-0" 
                                    referrerPolicy="no-referrer" 
                                />
                            ) : (
                                <div className="w-36 h-36 rounded-xl bg-surface-container-low border border-border-hairline flex items-center justify-center text-secondary shrink-0 text-xs">
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
                                
                                <div className="grid grid-cols-2 gap-2 mt-4 p-3 bg-surface-container rounded-lg border border-border-hairline">
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
                            <div className="p-3 bg-surface-container-low border border-border-hairline rounded-lg text-xs">
                                <span className="text-[10px] text-secondary font-semibold block mb-0.5">关联参考爆款标题</span>
                                <span className="text-on-surface font-medium block truncate" title={item.ref_title}>{item.ref_title}</span>
                            </div>
                        )}

                        {/* SKU 规格明细板块 */}
                        <div className="border-t border-border-hairline pt-4">
                            <h4 className="text-xs font-bold text-on-surface flex items-center gap-1.5 mb-3">
                                <span className="material-symbols-outlined text-primary text-[18px]">format_list_bulleted</span>
                                商品规格明细 ({skus.length} 个规格)
                            </h4>
                            
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
                    </div>

                    {/* 右侧决策面板: Span 4 布局 (AI ROI 引擎) */}
                    <div className="w-64 shrink-0 flex flex-col gap-4">
                        {/* 基础测算卡片 */}
                        <div className="bg-surface-container rounded-xl p-4 border border-border-hairline flex flex-col gap-3">
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
                        </div>

                        {/* AI 决策建议 */}
                        <div className="bg-surface-container-low border border-border-hairline rounded-xl p-4 flex-1 flex flex-col justify-between">
                            <div>
                                <span className="font-sans text-[10px] font-bold text-secondary tracking-wider uppercase block mb-3">AI 推荐诊断</span>
                                
                                <div className="flex items-center gap-1.5 mb-2">
                                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border flex items-center gap-1 ${badgeColorClass}`}>
                                        <span className={`w-1.5 h-1.5 rounded-full ${pulseColorClass} animate-pulse`}></span>
                                        {recommendationBadge}
                                    </span>
                                </div>
                                
                                <div className="text-3xl font-sans font-black text-on-surface tracking-tight mt-2 flex items-baseline">
                                    {roiPercentage}%
                                    <span className="text-xs text-secondary font-normal ml-1">预期 ROI</span>
                                </div>
                                
                                <p className="text-xs leading-relaxed text-secondary mt-3 bg-surface-container-lowest p-3 rounded-lg border border-border-hairline/50">
                                    {aiAdvice}
                                </p>
                            </div>
                            
                            <div className="text-[10px] text-secondary font-mono mt-4 text-center">
                                * ROI 测算扣除了估计加价运费成本
                            </div>
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
                                    onUpdateItem({ ...item, publish_status: status });
                                }
                            }}
                            batchStatus={batchStatusMap[item.source_db_id]}
                            batchResult={batchResultMap[item.source_db_id]}
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
const PublishedManager = () => {
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

    // 用于收集每个商品的实时状态映射
    const [batchStatusMap, setBatchStatusMap] = useState({});
    const [batchResultMap, setBatchResultMap] = useState({});

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
            <header className="mb-6">
                <h1 className="font-sans text-2xl font-bold text-on-surface flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary text-[28px]">shopping_bag</span>
                    闲鱼上架商品中枢
                </h1>
                <p className="font-sans text-sm text-secondary mt-1">管理并监控已经在闲鱼铺货成功的商品，支持与 1688 源头采购价、物流信息实时联动。点击行项目可展开详情数据与下架控制。</p>
            </header>

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
                                className="w-full bg-surface-container-low border border-border-hairline text-on-surface text-sm rounded-lg pl-4 pr-10 py-2 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all cursor-pointer appearance-none animate-none"
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
                    <div className="overflow-x-auto w-full">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="bg-table-header-bg border-b border-border-hairline">
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
                                    const currentStatus = batchStatusMap[item.source_db_id] || item.publish_status;
                                    
                                    let statusText = '未知';
                                    let statusClass = 'bg-secondary/10 text-secondary border-secondary/20';
                                    let pulseColor = 'bg-secondary';

                                    if (currentStatus === 'success' || currentStatus === 'done') {
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
                                            <td className="p-cell-padding">
                                                {item.source_image ? (
                                                    <img 
                                                        src={item.source_image} 
                                                        className="w-12 h-12 rounded-lg object-cover border border-border-hairline mx-auto" 
                                                        referrerPolicy="no-referrer" 
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
        </div>
    );
};

// --- 发布至闲鱼按钮组件 ---
const PublishButton = ({ src, xianyuPrice, batchStatus, batchResult, onStatusLoaded }) => {
    const [status, setStatus] = useState('idle'); // idle | publishing | done | failed | depublished | deleting
    const [pubResult, setPubResult] = useState(null);
    const [showModal, setShowModal] = useState(false);
    const [editTitle, setEditTitle] = useState('');
    const [editPrice, setEditPrice] = useState('');
    const [skus, setSkus] = useState([]);
    const [loadingSkus, setLoadingSkus] = useState(false);

    // 挂载时查询历史发布状态
    useEffect(() => {
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
    }, [src.db_id]);

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

    const doDepublish = async () => {
        if (!confirm("确定要下架此商品吗？")) return;
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

    const doDelete = async () => {
        if (!confirm("确定要彻底删除该商品的发布记录及闲管家云端商品吗？\n此操作不可逆！")) return;
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
        </div>
    );
};

const App = () => {
    const [view, setActiveView] = useState("dashboard"); 
    const [tasks, setTasks] = useState([]);
    const [selectedTask, setSelectedTask] = useState(null);
    const [detailedItems, setDetailedItems] = useState([]); 
    const [selectedItem, setSelectedItem] = useState(null); 
    const [sourcePage, setSourcePage] = useState(1);
    const [sysStatus, setSysStatus] = useState({});
    const [newKeyword, setNewKeyword] = useState("");

    const [selectedIds, setSelectedIds] = useState([]);
    const [batchPublishing, setBatchPublishing] = useState(false);
    const [batchDepublishing, setBatchDepublishing] = useState(false);
    const [batchDeleting, setBatchDeleting] = useState(false);
    const [batchStatusMap, setBatchStatusMap] = useState({});
    const [batchResultMap, setBatchResultMap] = useState({});

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

    // 当切换商品详情时，自动重置批量状态，并默认勾选全部未丢弃的货源
    useEffect(() => {
        if (selectedItem) {
            const activeIds = (selectedItem.sources || [])
                .filter(src => !src.drop_reason)
                .map(src => src.db_id);
            setSelectedIds(activeIds);
            setBatchStatusMap({});
            setBatchResultMap({});
        } else {
            setSelectedIds([]);
            setBatchStatusMap({});
            setBatchResultMap({});
        }
    }, [selectedItem]);

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
    const deleteTask = (id) => { if (confirm("确定永久逻辑删除该任务吗?")) fetch(`/api/tasks/${id}`, { method: "DELETE" }).then(refreshData); };
    
    const doBatchPublish = async () => {
        if (selectedIds.length === 0) {
            alert("请先选择要批量发布的货源");
            return;
        }
        setBatchPublishing(true);
        
        const toPublishIds = selectedIds.filter(dbId => batchStatusMap[dbId] !== 'done');
        if (toPublishIds.length === 0) {
            setBatchPublishing(false);
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

    const doBatchDepublish = async () => {
        if (selectedIds.length === 0) {
            alert("请先选择要批量下架的货源");
            return;
        }
        if (!confirm(`确定要批量下架所选的 ${selectedIds.length} 个商品吗？`)) {
            return;
        }
        setBatchDepublishing(true);
        
        const toDepublishIds = [...selectedIds];
        
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

    const doBatchDelete = async () => {
        if (selectedIds.length === 0) {
            alert("请先选择要批量删除的货源");
            return;
        }

        const invalidIds = selectedIds.filter(dbId => {
            const status = batchStatusMap[dbId] || 'idle';
            return status !== 'depublished';
        });

        if (invalidIds.length > 0) {
            alert("只有已下架的商品可以删除。请取消勾选未下架的商品。");
            return;
        }

        if (!confirm(`确定要批量删除所选的 ${selectedIds.length} 个商品吗？\n此操作将彻底删除闲管家中的对应云端商品，且不可恢复！`)) {
            return;
        }

        setBatchDeleting(true);
        const toDeleteIds = [...selectedIds];

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

    const loadTaskResults = async (task) => {
        const resp = await fetch(`/api/task_details/${task.id}`);
        const data = await resp.json();
        setDetailedItems(data.details || []);
        setSelectedTask(task);
        setActiveView("results");
    };
    
    const enterItemDetail = (group) => { setSelectedItem(group); setSourcePage(1); setActiveView("item_detail"); };
    const completedTasks = tasks.filter(t => t.status === '已完成');
    const pageSize = 4;
    const totalPages = selectedItem ? Math.ceil((selectedItem.sources?.length || 0) / pageSize) : 0;
    const paginatedSources = selectedItem ? (selectedItem.sources || []).slice((sourcePage - 1) * pageSize, sourcePage * pageSize) : [];

    const navItemClass = (itemKey) => {
        const isActive = (itemKey === 'results' && ['results', 'item_detail'].includes(view)) || view === itemKey;
        return `flex items-center gap-3 px-4 py-3 rounded-xl font-sans text-xs transition-all duration-150 scale-100 active:scale-95 cursor-pointer ${
            isActive 
            ? 'text-primary font-bold bg-surface-container border-r-4 border-primary' 
            : 'text-secondary hover:bg-surface-container-high transition-colors'
        }`;
    };

    return (
        <React.Fragment>
            {/* SideNavBar */}
            <aside className="w-[260px] h-screen bg-surface-container-lowest border-r border-border-hairline fixed left-0 top-0 flex flex-col py-6 z-20 transition-all duration-200">
                <div className="px-6 mb-8 flex items-center gap-3">
                    <div className="w-9 h-9 rounded bg-primary flex items-center justify-center text-on-primary">
                        <span className="material-symbols-outlined text-[20px]" style={{fontVariationSettings: "'FILL' 1"}}>precision_manufacturing</span>
                    </div>
                    <div>
                        <h1 className="font-sans text-base font-bold text-primary tracking-tight">选品中枢 PRO</h1>
                        <p className="font-mono text-[9px] text-secondary uppercase tracking-wider">Automated Precision</p>
                    </div>
                </div>

                <ul className="flex-1 px-4 space-y-1 w-full">
                    <li className={navItemClass("dashboard")} onClick={() => setActiveView("dashboard")}>
                        <span className="material-symbols-outlined text-[18px]">dashboard</span>
                        <span>控制台中心</span>
                    </li>
                    <li className={navItemClass("tasks")} onClick={() => setActiveView("tasks")}>
                        <span className="material-symbols-outlined text-[18px]">list_alt</span>
                        <span>任务队列</span>
                    </li>
                    <li className={navItemClass("results")} onClick={() => setActiveView("results")}>
                        <span className="material-symbols-outlined text-[18px]">travel_explore</span>
                        <span>决策资产库</span>
                    </li>
                    <li className={navItemClass("published")} onClick={() => setActiveView("published")}>
                        <span className="material-symbols-outlined text-[18px]">shopping_bag</span>
                        <span>已发布管理</span>
                    </li>
                    <li className={navItemClass("logs")} onClick={() => setActiveView("logs")}>
                        <span className="material-symbols-outlined text-[18px]">analytics</span>
                        <span>日志日志</span>
                    </li>
                    <li className={navItemClass("token_stats")} onClick={() => setActiveView("token_stats")}>
                        <span className="material-symbols-outlined text-[18px]">generating_tokens</span>
                        <span>AI Token 计量舱</span>
                    </li>
                </ul>

                {/* 侧栏底部状态 */}
                <div className="px-4 mt-auto space-y-3">
                    <div className="p-3.5 rounded-xl bg-surface-container-low border border-border-hairline">
                        <div className="flex items-center gap-2 mb-1.5">
                            <span className={`material-symbols-outlined text-[16px] ${sysStatus["1688_login"] === '有效' ? 'text-success' : 'text-error'}`} style={{fontVariationSettings: "'FILL' 1"}}>check_circle</span>
                            <span className="font-sans text-[11px] text-secondary font-medium">1688 接入状态</span>
                        </div>
                        <div className="font-mono text-xs font-bold text-on-surface">
                            {sysStatus["1688_login"] || 'OFFLINE'}
                        </div>
                    </div>

                    <button 
                        onClick={() => setTheme(t => t === 'light' ? 'dark' : 'light')}
                        className="w-full flex items-center justify-center gap-2 py-2 bg-surface-container-high border border-border-hairline text-on-surface hover:text-primary rounded-lg transition-colors font-sans text-xs scale-100 active:scale-95 duration-100"
                    >
                        <span className="material-symbols-outlined text-[16px]">{theme === 'light' ? 'dark_mode' : 'light_mode'}</span>
                        <span>{theme === 'light' ? '深色 midnight' : '浅色 efficient'}</span>
                    </button>
                </div>
            </aside>

            {/* TopNavBar */}
            <header className="fixed top-0 right-0 left-[260px] h-16 bg-surface-container-lowest/80 backdrop-blur-md border-b border-border-hairline flex items-center justify-between px-6 z-10 w-[calc(100%-260px)] transition-all duration-200">
                <div className="flex items-center gap-2 text-secondary">
                    <span className="material-symbols-outlined text-[20px]">explore</span>
                    <span className="font-sans text-xs font-bold capitalize">
                        {view === 'item_detail' ? '决策资产 / 货源明细' : 
                         view === 'token_stats' ? 'AI Token 计量舱 / 成本审计' : 
                         view}
                    </span>
                </div>
                <div className="flex items-center gap-4">
                    <div className="hidden sm:flex items-center px-3 py-1 bg-surface-container-low border border-border-hairline rounded-full">
                        <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse mr-2"></span>
                        <span className="font-sans text-[10px] text-secondary">系统健康运行</span>
                    </div>
                    <div className="w-px h-6 bg-border-hairline"></div>
                    <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary font-mono text-[10px] font-bold">
                            M
                        </div>
                        <span className="font-sans text-xs text-secondary font-medium">管理员用户</span>
                    </div>
                </div>
            </header>

            {/* Main Container */}
            <main className="ml-[260px] mt-16 p-6 overflow-y-auto flex-1 h-[calc(100vh-64px)] transition-all duration-200">
                {view === 'logs' ? <LogViewer tasks={tasks} /> : 
                 view === 'token_stats' ? <TokenStatsView /> :
                 view === "dashboard" ? (() => {
                    const activeTasks = tasks.filter(t => t.status !== '已完成');
                    const runningCount = tasks.filter(t => ['执行中', '正在暂停'].includes(t.status)).length;
                    const pendingCount = tasks.filter(t => t.status === '排队中').length;
                    return (
                        <div className="view-content">
                            <header className="mb-6">
                                <h1 className="font-sans text-2xl font-bold text-on-surface">控制台中心</h1>
                                <p className="font-sans text-sm text-secondary mt-1">全局扫描 Worker 统计面板及后台状态概览。</p>
                            </header>

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
                            <header className="mb-6">
                                <h1 className="font-sans text-2xl font-bold text-on-surface">任务队列中心</h1>
                                <p className="font-sans text-sm text-secondary mt-1">查看和管理各个品类的深度爬取状态。左侧显示活跃进行中队列，右侧显示归档历史。</p>
                            </header>

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
                                 <div>
                                     <button onClick={() => setSelectedTask(null)} className="text-secondary hover:text-primary text-xs font-bold flex items-center gap-1 mb-2">
                                         <span className="material-symbols-outlined text-[16px]">arrow_back</span>
                                         返回决策资产列表
                                     </button>
                                     <h1 className="font-sans text-2xl font-bold text-on-surface">“{selectedTask.keyword}” 爆款深度对比报告</h1>
                                 </div>
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
                             <header className="mb-6">
                                 <h1 className="font-sans text-2xl font-bold text-on-surface">选品决策资产库</h1>
                                 <p className="font-sans text-sm text-secondary mt-1">系统已完成的爆款数据中心。点击各个品类卡片，可直接穿透查看商品的 1688 源头采购价与深度分析。</p>
                             </header>
                             
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
                                 <h3 className="font-sans text-sm font-bold text-on-surface">1688 货源深度对比表 ({selectedItem.sources?.length || 0} 条匹配)</h3>
                                 
                                 {/* 批量处理 */}
                                 {selectedItem.sources?.filter(s => !s.drop_reason).length > 0 && (
                                     <div className="flex items-center gap-4 bg-surface-container border border-border-hairline px-4 py-2 rounded-xl ambient-shadow">
                                         <label className="text-xs text-secondary font-semibold cursor-pointer flex items-center gap-1">
                                             <input 
                                                 type="checkbox" 
                                                 className="rounded border-secondary text-primary focus:ring-primary/20 w-4 h-4 cursor-pointer"
                                                 checked={selectedItem.sources.filter(s => !s.drop_reason).length > 0 && selectedItem.sources.filter(s => !s.drop_reason).every(s => selectedIds.includes(s.db_id))}
                                                 onChange={(e) => {
                                                     if (e.target.checked) {
                                                         setSelectedIds(selectedItem.sources.filter(s => !s.drop_reason).map(s => s.db_id));
                                                     } else {
                                                         setSelectedIds([]);
                                                     }
                                                 }}
                                             />
                                             全选未丢弃
                                         </label>
                                         <div className="w-px h-5 bg-border-hairline/60"></div>
                                         
                                         <div className="flex gap-2">
                                             <button 
                                                 className="px-3.5 py-1.5 bg-primary hover:bg-primary-container text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-40" 
                                                 disabled={batchPublishing || batchDepublishing || batchDeleting || selectedIds.length === 0} 
                                                 onClick={doBatchPublish}
                                             >
                                                 {batchPublishing ? "云同步中..." : `🚀 批量发布 (${selectedIds.length})`}
                                             </button>
                                             <button 
                                                 className="px-3.5 py-1.5 bg-warning hover:bg-warning/80 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-40" 
                                                 disabled={batchPublishing || batchDepublishing || batchDeleting || selectedIds.length === 0} 
                                                 onClick={doBatchDepublish}
                                             >
                                                 {batchDepublishing ? "云同步中..." : `⚠️ 批量下架 (${selectedIds.length})`}
                                             </button>
                                             <button 
                                                 className="px-3.5 py-1.5 bg-error hover:bg-error/85 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-40" 
                                                 disabled={batchPublishing || batchDepublishing || batchDeleting || selectedIds.length === 0} 
                                                 onClick={doBatchDelete}
                                             >
                                                 {batchDeleting ? "云注销中..." : `🗑️ 批量删除 (${selectedIds.length})`}
                                             </button>
                                         </div>
                                     </div>
                                 )}
                             </header>

                             {/* 货源列表卡片 */}
                             <div className="space-y-4">
                                 {paginatedSources.map((src, i) => { 
                                     const marginVal = (selectedItem.xianyu_item?.price - src.min_price - 20).toFixed(2); 
                                     const isDropped = !!src.drop_reason;
                                     const isChecked = selectedIds.includes(src.db_id);
                                     return (
                                         <div 
                                             className={`bg-surface-container-lowest border rounded-xl p-4 ambient-shadow flex justify-between items-center relative overflow-hidden group ${
                                                 isDropped ? 'border-dashed border-outline-variant/60 opacity-60 bg-surface-container-low' : 'border-border-hairline hover:border-primary transition-colors'
                                             }`} 
                                             key={i}
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
                                                     <div className="flex gap-3 items-center mt-2.5 text-xs text-secondary">
                                                         <span>{src.sku_count > 0 ? `${src.sku_count} 个多属性 SKU 规格` : '一口价商品'}</span>
                                                         <span className="w-1.5 h-1.5 rounded-full bg-border-hairline"></span>
                                                         <span className="font-mono bg-surface-container px-2 py-0.5 rounded text-[10px]">ID: {src.db_id}</span>
                                                     </div>
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

                                 {selectedItem.sources?.length === 0 && (
                                     <div className="bg-surface-container-lowest border border-border-hairline rounded-xl py-12 text-center text-xs text-secondary">
                                         该爆款商品暂未匹配到对应的 1688 采购货源。
                                     </div>
                                 )}

                                 {/* 分页 */}
                                 {totalPages > 1 && (
                                     <div className="flex justify-center items-center gap-1.5 mt-8">
                                         <button 
                                             className="w-8 h-8 flex items-center justify-center rounded border border-border-hairline text-secondary hover:bg-surface-container-low transition-colors disabled:opacity-40" 
                                             disabled={sourcePage <= 1} 
                                             onClick={() => setSourcePage(p => p - 1)}
                                         >
                                             <span className="material-symbols-outlined text-[18px]">chevron_left</span>
                                         </button>
                                         <span className="font-mono text-xs font-bold px-3 py-1 bg-primary/10 border border-primary/20 text-primary rounded">
                                             第 {sourcePage} / {totalPages} 页
                                         </span>
                                         <button 
                                             className="w-8 h-8 flex items-center justify-center rounded border border-border-hairline text-secondary hover:bg-surface-container-low transition-colors disabled:opacity-40" 
                                             disabled={sourcePage >= totalPages} 
                                             onClick={() => setSourcePage(p => p + 1)}
                                         >
                                             <span className="material-symbols-outlined text-[18px]">chevron_right</span>
                                         </button>
                                     </div>
                                 )}
                             </div>
                         </div>
                     </div> 
                 ) : view === "published" ? <PublishedManager /> : null
                }
            </main>
        </React.Fragment>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
