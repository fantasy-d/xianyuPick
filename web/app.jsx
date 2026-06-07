const { useState, useEffect, useRef } = React;

// --- 日志视图组件 ---
const LogViewer = ({ tasks }) => {
    const [logType, setLogType] = useState('task');
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
            <header><h1>任务日志中心</h1><p>实时监控具体任务的后台输出。</p></header>
            <div style={{ marginBottom: '20px', display: 'flex', gap: '15px', alignItems: 'center' }}>
                <span style={{fontWeight: 600}}>选择任务:</span>
                <select onChange={(e) => setSelectedTaskId(e.target.value)} defaultValue="" style={{padding: '10px', borderRadius: '8px', border: '1px solid var(--border)', flex: 1, maxWidth: '400px'}}>
                    <option value="" disabled>-- 请选择一个任务 --</option>
                    {tasks.map(t => <option key={t.id} value={t.id}>{t.keyword} ({t.id})</option>)}
                </select>
            </div>
            <pre style={{ background: '#1E293B', color: '#E2E8F0', padding: '20px', borderRadius: '12px', whiteSpace: 'pre-wrap', height: '60vh', overflowY: 'auto' }}>
                {logContent}
            </pre>
        </div>
    );
};

// --- 发布至闲鱼按钮组件 ---
const PublishButton = ({ src, xianyuPrice, batchStatus, batchResult }) => {
    const [status, setStatus] = useState('idle'); // idle | publishing | done | failed
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
                }
            })
            .catch(() => {});
    }, [src.db_id]);

    // 联动外部批量发布状态
    useEffect(() => {
        if (batchStatus) {
            setStatus(batchStatus);
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
                // 初始化每个规格的默认闲鱼价格 (进价 + 30) 并将库存最大限制在 9999
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
            setStatus(res.status === 'success' ? 'done' : 'failed');
        } catch (e) {
            setPubResult({ msg: '网络错误，请稍后重试' });
            setStatus('failed');
        }
    };

    const btnStyle = { padding: '6px 14px', borderRadius: '8px', border: 'none', cursor: 'pointer', fontSize: '0.8rem', fontWeight: '600', marginTop: '8px' };

    return (
        <div>
            {status === 'done' && (
                <a href={pubResult?.published_url} target="_blank" rel="noreferrer"
                   style={{ ...btnStyle, display: 'inline-block', background: '#10B98120', color: '#10B981', textDecoration: 'none' }}>
                    ✅ 已发布
                </a>
            )}
            {status === 'publishing' && (
                <span style={{ ...btnStyle, display: 'inline-block', background: '#3B82F620', color: '#3B82F6' }}>🔄 发布中...</span>
            )}
            {status === 'failed' && (
                <div>
                    <span style={{ fontSize: '0.75rem', color: '#EF4444' }}>❌ {pubResult?.msg || '发布失败'}</span>
                    <button style={{ ...btnStyle, background: '#EF444420', color: '#EF4444', marginLeft: '8px' }} onClick={openModal}>重试</button>
                </div>
            )}
            {status === 'idle' && (
                <button style={{ ...btnStyle, background: 'var(--primary)', color: '#fff' }} onClick={openModal}>
                    发布至闲鱼 →
                </button>
            )}

            {showModal && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                     onClick={() => setShowModal(false)}>
                    <div style={{ background: 'var(--card-bg)', borderRadius: '16px', padding: '32px', width: '500px', maxWidth: '90vw', boxShadow: '0 20px 60px rgba(0,0,0,0.4)' }}
                         onClick={e => e.stopPropagation()}>
                        <h3 style={{ marginBottom: '20px', fontSize: '1.1rem' }}>📦 发布预览</h3>

                        {/* 图片预览 */}
                        {src.images && src.images.length > 0 && (
                            <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
                                {src.images.slice(0, 5).map((img, idx) => (
                                    <img key={idx} src={img} referrerPolicy="no-referrer"
                                         style={{ width: '72px', height: '72px', borderRadius: '8px', objectFit: 'cover', border: '1px solid var(--border)' }} />
                                ))}
                            </div>
                        )}

                        {/* 标题编辑 */}
                        <div style={{ marginBottom: '16px' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>标题（最多60字）</label>
                            <input value={editTitle} onChange={e => setEditTitle(e.target.value.slice(0, 60))}
                                   style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', boxSizing: 'border-box' }} />
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textAlign: 'right', marginTop: '4px' }}>{editTitle.length}/60</div>
                        </div>

                        {/* 售价与多规格编辑 */}
                        {loadingSkus ? (
                            <div style={{ marginBottom: '24px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                                🔄 正在加载规格规格配置信息...
                            </div>
                        ) : skus.length > 0 ? (
                            <div style={{ marginBottom: '24px' }}>
                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '10px' }}>
                                    规格售价与库存配置（进价加价后默认 +30 元）
                                </label>
                                <div style={{ maxHeight: '180px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: '8px', padding: '12px' }}>
                                    {skus.map((s, idx) => (
                                        <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px', borderBottom: idx < skus.length - 1 ? '1px solid var(--border)' : 'none', paddingBottom: '10px' }}>
                                            {s.image && (
                                                <img src={s.image} referrerPolicy="no-referrer"
                                                     style={{ width: '28px', height: '28px', borderRadius: '4px', objectFit: 'cover', border: '1px solid var(--border)' }} />
                                            )}
                                            <span style={{ fontSize: '0.8rem', flex: 1, wordBreak: 'break-all' }}>{s.sku_text}</span>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', width: '145px' }}>
                                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>进¥{s.price}→</span>
                                                <input type="number" min="0" step="0.5" value={s.xianyu_price}
                                                       onChange={e => {
                                                           const val = e.target.value;
                                                           setSkus(prev => prev.map((item, i) => i === idx ? { ...item, xianyu_price: val } : item));
                                                       }}
                                                       style={{ width: '70px', padding: '6px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', fontSize: '0.8rem' }} />
                                            </div>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', width: '85px' }}>
                                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>库存</span>
                                                <input type="number" min="1" max="9999" value={s.stock}
                                                       onChange={e => {
                                                           const val = Math.min(9999, parseInt(e.target.value) || 1);
                                                           setSkus(prev => prev.map((item, i) => i === idx ? { ...item, stock: val } : item));
                                                       }}
                                                       style={{ width: '45px', padding: '6px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', fontSize: '0.8rem' }} />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            /* 售价编辑（单规格） */
                            <div style={{ marginBottom: '24px' }}>
                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>售价（元）<span style={{ color: 'var(--text-secondary)', fontWeight: 'normal' }}>1688进价 ¥{src.min_price}，加价后默认 ¥{(parseFloat(src.min_price)+30).toFixed(2)}</span></label>
                                <input type="number" min="0" step="0.5" value={editPrice} onChange={e => setEditPrice(e.target.value)}
                                       style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', boxSizing: 'border-box' }} />
                            </div>
                        )}

                        <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                            <button style={{ ...btnStyle, background: 'var(--border)', color: 'var(--text)' }} onClick={() => setShowModal(false)}>取消</button>
                            <button style={{ ...btnStyle, background: 'var(--primary)', color: '#fff' }} onClick={doPublish} disabled={loadingSkus}>确认发布</button>
                        </div>
                    </div>
                </div>
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
    const [batchStatusMap, setBatchStatusMap] = useState({});
    const [batchResultMap, setBatchResultMap] = useState({});

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

    const createTask = async () => { if (!newKeyword) return; await fetch("/api/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ keyword: newKeyword }) }); setNewKeyword(""); setActiveView("tasks"); refreshData(); };
    const pauseTask = (id) => { fetch(`/api/tasks/${id}/pause`, { method: "POST" }).then(refreshData); };
    const retryTask = (id) => { fetch(`/api/tasks/${id}/retry`, { method: "POST" }).then(refreshData); };
    const deleteTask = (id) => { if (confirm("确定永久逻辑删除该任务吗?")) fetch(`/api/tasks/${id}`, { method: "DELETE" }).then(refreshData); };
    
    const doBatchPublish = async () => {
        if (selectedIds.length === 0) {
            alert("请先选择要批量发布的货源");
            return;
        }
        setBatchPublishing(true);
        
        for (const dbId of selectedIds) {
            if (batchStatusMap[dbId] === 'done') {
                continue;
            }
            
            setBatchStatusMap(prev => ({ ...prev, [dbId]: 'publishing' }));
            
            try {
                const resSkus = await fetch(`/api/source_skus/${dbId}`).then(r => r.json());
                const src = selectedItem.sources.find(s => s.db_id === dbId);
                if (!src) continue;
                
                const payload = { title: src.title.slice(0, 60) };
                
                if (resSkus.skus && resSkus.skus.length > 1) {
                    payload.sku_items = resSkus.skus.map(s => ({
                        sku_text: s.sku_text,
                        price: parseFloat((parseFloat(s.price) + 30).toFixed(2)),
                        stock: Math.min(9999, parseInt(s.stock) || 1)
                    }));
                    
                    const skuImages = [];
                    resSkus.skus.forEach(s => {
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
                } else if (resSkus.skus && resSkus.skus.length === 1) {
                    payload.price = parseFloat((parseFloat(resSkus.skus[0].price) + 30).toFixed(2));
                } else {
                    payload.price = parseFloat((parseFloat(src.min_price) + 30).toFixed(2));
                }
                
                const resPub = await fetch(`/api/publish/${dbId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                }).then(r => r.json());
                
                if (resPub.status === 'success') {
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'done' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: resPub }));
                } else {
                    setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                    setBatchResultMap(prev => ({ ...prev, [dbId]: resPub }));
                }
            } catch (e) {
                console.error(`批量发布货源 ${dbId} 失败:`, e);
                setBatchStatusMap(prev => ({ ...prev, [dbId]: 'failed' }));
                setBatchResultMap(prev => ({ ...prev, [dbId]: { msg: '网络或连接出错' } }));
            }
            
            await new Promise(r => setTimeout(r, 1000));
        }
        
        setBatchPublishing(false);
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

    return (
        <React.Fragment>
            <aside className="sidebar">
                <div className="logo-area">选品中枢 PRO</div>
                <ul className="nav-menu">
                    <li className={`nav-item ${view === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveView("dashboard")}><i className="fas fa-chart-pie"></i><span>控制台</span></li>
                    <li className={`nav-item ${view === 'tasks' ? 'active' : ''}`} onClick={() => setActiveView("tasks")}><i className="fas fa-tasks"></i><span>任务调度</span></li>
                    <li className={`nav-item ${['results', 'item_detail'].includes(view) ? 'active' : ''}`} onClick={() => setActiveView("results")}><i className="fas fa-database"></i><span>决策资产</span></li>
                    <li className={`nav-item ${view === 'logs' ? 'active' : ''}`} onClick={() => setActiveView("logs")}><i className="fas fa-file-alt"></i><span>系统日志</span></li>
                </ul>
                <div className="sidebar-footer"><div className="label">SYSTEM STATUS</div><div style={{color: sysStatus["1688_login"] === '有效' ? 'var(--success)' : 'var(--danger)', fontWeight:'bold'}}>{sysStatus["1688_login"] || 'OFFLINE'}</div></div>
            </aside>

            <main className="main-container">
                {view === 'logs' ? <LogViewer tasks={tasks} /> : 
                 view === "dashboard" ? (() => {
                    const activeTasks = tasks.filter(t => t.status !== '已完成');
                    const runningCount = tasks.filter(t => ['执行中', '正在暂停'].includes(t.status)).length;
                    const pendingCount = tasks.filter(t => t.status === '排队中').length;
                    return (
                        <div className="view-content">
                            <header><h1>仪表盘概览</h1><p>欢迎回来，系统当前运行平稳。</p></header>
                            <div className="stats-grid">
                                <div className="stat-card"><span className="label">活跃 Worker</span><span className="val">{sysStatus["active_workers"] || 0}</span></div>
                                <div className="stat-card"><span className="label">已存选品</span><span className="val">{completedTasks.length}</span></div>
                                <div className="stat-card"><span className="label">队列概览</span><div className="val" style={{fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '15px'}}><div><span style={{color: 'var(--primary)'}}>{runningCount}</span> <span style={{fontSize: '1rem'}}>执行</span></div><div><span style={{color: 'var(--text-secondary)'}}>{pendingCount}</span> <span style={{fontSize: '1rem'}}>排队</span></div></div></div>
                                <div className="stat-card"><span className="label">同步频率</span><span className="val">60s</span></div>
                            </div>
                            <div className="task-card" style={{marginTop:'40px'}}><h3 style={{marginBottom:'20px'}}>新建深度扫描任务</h3><div style={{display: 'flex', gap: '15px'}}><input style={{flex:1, padding:'15px', borderRadius:'8px', border:'1px solid var(--border)'}} value={newKeyword} onChange={e => setNewKeyword(e.target.value)} placeholder="请输入要调研的商品品类关键词..." /><button className="pro-btn primary" style={{padding: '0 30px'}} onClick={createTask}>立即启动任务</button></div></div>
                            {activeTasks.length > 0 && (<div className="task-card" style={{marginTop:'20px', cursor: 'pointer'}} onClick={() => setActiveView('tasks')}>
                                    <h3 style={{marginBottom: '15px'}}>进行中任务 ({activeTasks.length})</h3>
                                    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px'}}>
                                        {activeTasks.slice(0, 4).map(t => (
                                            <div key={t.id} style={{padding: '10px', border: '1px solid var(--border)', borderRadius: '8px'}}>
                                                <div style={{fontWeight: 600, fontSize: '0.9rem'}}>{t.keyword}</div>
                                                <div style={{color: 'var(--text-secondary)', fontSize: '0.8rem'}}>{t.status} ({t.progress}%)</div>
                                            </div>
                                        ))}
                                    </div>
                                    <div style={{textAlign: 'center', marginTop: '15px', color: 'var(--primary)', fontWeight: 'bold'}}>点击跳转到任务队列查看全部 →</div>
                                </div>)}
                        </div>
                    );
                 })() :
                 view === "tasks" ? (() => {
                    const activeTasks = tasks.filter(t => t.status !== '已完成').sort((a, b) => a.created_at.localeCompare(b.created_at));
                    const completedTasks = tasks.filter(t => t.status === '已完成');
                    return (
                        <div className="view-content"><header><h1>任务队列详情</h1><p>左侧为活动任务，右侧为已完成的历史归档。</p></header><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '40px', alignItems: 'flex-start' }}>
                            {/* 左栏：执行队列 (严格删除模式) */}
                            <div><h3 style={{ marginBottom: '20px' }}>执行队列</h3><div className="task-list">{activeTasks.map(t => (
                                <div className={`task-card ${t.status}`} key={t.id} style={{minHeight: '130px', display: 'flex', flexDirection: 'column', position: 'relative', justifyContent: 'space-between'}}>
                                    <div style={{ position: 'absolute', top: '20px', right: '20px', display: 'flex', gap: '8px' }}>
                                        {t.status === '执行中' ? <button className="pro-btn" onClick={(e) => { e.stopPropagation(); pauseTask(t.id); }}>暂停</button> : (t.status === '已暂停' || t.status === '失败') ? <button className="pro-btn primary" onClick={(e) => { e.stopPropagation(); retryTask(t.id); }}>恢复</button> : null}
                                    </div>
                                    <div style={{ paddingRight: '100px' }}><div className="task-kw">{t.keyword}</div><div className="task-msg">{t.msg}</div></div>
                                    <div className="nano-progress"><div className="nano-bar" style={{width: `${t.progress}%`}}></div></div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '5px' }}>
                                        <div style={{display: 'flex', gap: '15px', alignItems: 'center'}}>
                                            <span style={{fontSize: '0.7rem', color: '#94A3B8', fontWeight: 'bold'}}>V.{t.version}</span>
                                            <span style={{fontSize: '0.7rem', color: '#CBD5E1'}}>ID: {t.id}</span>
                                        </div>
                                        {/* 仅已暂停或失败的任务显示删除按钮 */}
                                        <button className="pro-btn danger" style={{minWidth: '80px', padding: '4px 15px', display: (t.status === '已暂停' || t.status === '失败') ? 'block' : 'none'}} onClick={(e) => { e.stopPropagation(); deleteTask(t.id); }}><i className="fas fa-trash" style={{fontSize: '0.7rem'}}></i> 删除</button>
                                    </div>
                                </div>
                            ))}{activeTasks.length === 0 && <div className="task-card" style={{textAlign: 'center', padding: '40px'}}>当前没有活动任务</div>}</div></div>
                            {/* 右栏：完成队列 (开放删除模式) */}
                            <div><h3 style={{ marginBottom: '20px' }}>完成队列</h3><div className="task-list">{completedTasks.map(t => (
                                <div className={`task-card ${t.status}`} key={t.id} onClick={() => loadTaskResults(t)} style={{ cursor: 'pointer', minHeight: '130px', display: 'flex', flexDirection: 'column', position: 'relative', justifyContent: 'space-between' }}>
                                    <div style={{ position: 'absolute', top: '20px', right: '20px' }}><button className="pro-btn" onClick={(e) => { e.stopPropagation(); retryTask(t.id); }}>重扫</button></div>
                                    <div style={{paddingRight: '80px'}}><div className="task-kw">{t.keyword}</div><div className="task-msg">调研于 {t.created_at}</div></div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '15px' }}>
                                        <div style={{display: 'flex', gap: '15px', alignItems: 'center'}}>
                                            <span style={{fontSize: '0.7rem', color: '#94A3B8', fontWeight: 'bold'}}>V.{t.version}</span>
                                            <span style={{fontSize: '0.7rem', color: '#CBD5E1'}}>ID: {t.id}</span>
                                        </div>
                                        {/* 完成队列始终显示删除按钮 */}
                                        <button className="pro-btn danger" style={{minWidth: '80px', padding: '4px 15px', display: 'block'}} onClick={(e) => { e.stopPropagation(); deleteTask(t.id); }}><i className="fas fa-trash" style={{fontSize: '0.7rem'}}></i> 删除</button>
                                    </div>
                                </div>
                            ))}</div></div></div></div>
                    )
                 })() :
                 view === "results" ? ( selectedTask ? ( <> <header style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}><div><h1 onClick={() => setSelectedTask(null)} style={{cursor: 'pointer'}}>← {selectedTask.keyword} 深度报告</h1></div><button className="pro-btn primary" onClick={() => window.open(`/api/download/${selectedTask.id}`)}>导出 XLSX</button></header><div className="item-grid">{detailedItems.length > 0 ? detailedItems.map((group) => (<div className="item-card" key={group.rank} onClick={() => enterItemDetail(group)}><img src={group.xianyu_item?.image_url} referrerPolicy="no-referrer" /><div className="tile-body"><div className="tile-title">#{group.rank} {group.xianyu_item?.title}</div><div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px'}}><span className="tile-price">¥{group.xianyu_item?.price}</span><span style={{fontSize: '0.8rem', color: 'var(--text-secondary)'}}>{group.sources?.length || 0} 个货源</span></div><div className="id-corner">ID: {group.xianyu_item?.db_id}</div></div></div>)) : (<div className="task-card" style={{gridColumn: '1/-1', textAlign: 'center', padding: '100px'}}><p>该任务尚未产生详情数据。</p></div>)}</div></> ) : (<div><header><h1>选品决策资产库</h1></header><div className="task-list">{completedTasks.map(t => (
                                        <div className="task-card 已完成" key={t.id} style={{position: 'relative', minHeight: '120px', display: 'flex', flexDirection: 'column', justifyContent: 'center', margin: 0, padding: '20px'}} onClick={() => loadTaskResults(t)}>
                                            <div className="task-kw" style={{textAlign: 'center', fontSize: '1.2rem', marginBottom: '10px', width: '100%'}}>{t.keyword}</div>
                                            <div className="task-msg" style={{textAlign: 'left', fontSize: '0.8rem', width: '100%'}}>调研于 {t.created_at}</div>
                                            <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', position:'absolute', bottom:'10px', left:'20px', right:'20px', pointerEvents:'none'}}>
                                                <span style={{fontSize:'0.7rem', color:'#94A3B8', fontWeight:'bold'}}>V.{t.version}</span>
                                                <span style={{fontSize:'0.7rem', color:'#CBD5E1'}}>ID: {t.id}</span>
                                            </div>
                                        </div>
                                    ))}</div></div>) ) :
                 view === "item_detail" && selectedItem ? ( <div className="view-content"><div onClick={() => setActiveView("results")} style={{cursor: 'pointer', marginBottom: '30px', color: 'var(--text-secondary)', fontSize: '0.9rem', fontWeight: '500'}}><i className="fas fa-arrow-left"></i> 返回 "{selectedTask.keyword}" 报告</div>
                        <div className="task-card" style={{padding: '30px', marginBottom: '40px', position: 'relative', display: 'block'}}>
                            <div style={{display: 'flex', gap: '30px', alignItems: 'center'}}>
                                <img src={selectedItem.xianyu_item?.image_url} style={{width:'200px', height: '200px', borderRadius:'12px', objectFit:'cover'}} referrerPolicy="no-referrer" />
                                <div style={{flex: 1}}>
                                    <h2 style={{fontSize:'1.5rem', fontWeight: '700', marginBottom: '20px'}}>
                                        <a href={selectedItem.xianyu_item?.item_url} target="_blank" className="hover-link" style={{textDecoration: 'none', color: 'inherit'}}>
                                            {selectedItem.xianyu_item?.title} <i className="fas fa-external-link-alt" style={{fontSize: '0.8rem', color: 'var(--text-secondary)'}}></i>
                                        </a>
                                    </h2>
                                    <div style={{display: 'flex', gap: '40px'}}>
                                        <div className="stat-card" style={{padding: '0', border: 'none', background: 'none'}}><span className="label">闲鱼售价</span><div className="val" style={{fontSize: '1.8rem'}}>¥{selectedItem.xianyu_item?.price}</div></div>
                                        <div className="stat-card" style={{padding: '0', border: 'none', background: 'none'}}><span className="label">“想要”人数</span><div className="val" style={{fontSize: '1.8rem'}}>{selectedItem.xianyu_item?.want_count}</div></div>
                                    </div>
                                </div>
                            </div>
                            <div className="id-corner">ID: {selectedItem.xianyu_item?.db_id}</div>
                        </div>
                        <div>
                            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '15px' }}>
                                <h3 style={{ margin: 0 }}>1688 货源深度对比表 ({selectedItem.sources?.length || 0} 条)</h3>
                                {selectedItem.sources?.filter(s => !s.drop_reason).length > 0 && (
                                    <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
                                        <label style={{ fontSize: '0.85rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-secondary)' }}>
                                            <input 
                                                type="checkbox" 
                                                checked={selectedItem.sources.filter(s => !s.drop_reason).length > 0 && selectedItem.sources.filter(s => !s.drop_reason).every(s => selectedIds.includes(s.db_id))}
                                                onChange={(e) => {
                                                    if (e.target.checked) {
                                                        setSelectedIds(selectedItem.sources.filter(s => !s.drop_reason).map(s => s.db_id));
                                                    } else {
                                                        setSelectedIds([]);
                                                    }
                                                }}
                                                style={{ cursor: 'pointer' }}
                                            />
                                            全选未丢弃
                                        </label>
                                        <button 
                                            className="pro-btn primary" 
                                            disabled={batchPublishing || selectedIds.length === 0} 
                                            onClick={doBatchPublish}
                                            style={{ padding: '6px 16px', fontSize: '0.8rem' }}
                                        >
                                            {batchPublishing ? "🔄 批量发布中..." : `🚀 批量发布所选 (${selectedIds.length})`}
                                        </button>
                                    </div>
                                )}
                            </header>
                            {paginatedSources.map((src, i) => { 
                                const margin = (selectedItem.xianyu_item?.price - src.min_price - 20).toFixed(2); 
                                const isDropped = !!src.drop_reason;
                                const isChecked = selectedIds.includes(src.db_id);
                                return (
                                    <div className={`task-card ${isDropped ? 'dropped' : ''}`} key={i} style={{display:'flex', justifyContent:'space-between', alignItems:'center', padding: '15px', marginBottom: '15px'}}>
                                        <div style={{display:'flex', gap:'15px', alignItems:'center', flex: 1}}>
                                            {!isDropped && (
                                                <input 
                                                    type="checkbox" 
                                                    checked={isChecked}
                                                    onChange={(e) => {
                                                        if (e.target.checked) {
                                                            setSelectedIds(prev => [...prev, src.db_id]);
                                                        } else {
                                                            setSelectedIds(prev => prev.filter(id => id !== src.db_id));
                                                        }
                                                    }}
                                                    style={{ width: '18px', height: '18px', cursor: 'pointer', marginRight: '5px' }}
                                                />
                                            )}
                                            {src.images && src.images.length > 0 && (
                                                <img src={src.images[0]} style={{width:'60px', height:'60px', borderRadius:'4px', objectFit:'cover'}} referrerPolicy="no-referrer" />
                                            )}
                                            <div style={{flex:1}}>
                                                <a href={src.url} target="_blank" className={isDropped ? 'text-muted' : 'hover-link'} style={{textDecoration: isDropped ? 'line-through' : 'none', color:'inherit', fontWeight:'600', display: 'block', marginBottom: '5px'}}>{src.title}</a>
                                                <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
                                                    <span style={{fontSize: '0.8rem', color: 'var(--text-secondary)'}}>{src.sku_count > 0 ? `${src.sku_count} 个 SKU 规格` : '无 SKU 规格'}</span>
                                                    <span style={{fontSize: '0.7rem', color: 'var(--text-secondary)', background: '#F1F5F9', padding: '1px 6px', borderRadius: '4px'}}>ID: {src.db_id}</span>
                                                </div>

                                            </div>
                                        </div>
                                        <div style={{textAlign:'right', paddingLeft:'20px', minWidth: '170px'}}>
                                            {isDropped ? (
                                                <span className="drop-badge">已丢弃: {src.drop_reason}</span>
                                            ) : (
                                                <>
                                                    <div style={{fontSize:'1.2rem', fontWeight:'700'}}>¥{src.min_price}</div>
                                                    <div style={{fontSize:'0.9rem', color: margin > 50 ? 'var(--success)' : 'var(--danger)', fontWeight:'bold'}}>利润: ¥{margin}</div>
                                                    <PublishButton 
                                                        src={src} 
                                                        xianyuPrice={selectedItem.xianyu_item?.price} 
                                                        batchStatus={batchStatusMap[src.db_id]}
                                                        batchResult={batchResultMap[src.db_id]}
                                                    />
                                                </>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                            {selectedItem.sources?.length === 0 && <div className="task-card"><p>该商品暂未找到匹配的 1688 货源。</p></div>}
                            {totalPages > 1 && (<div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '15px', marginTop: '30px'}}><button className="pro-btn" disabled={sourcePage <= 1} onClick={() => setSourcePage(p => p - 1)}>上一页</button><span style={{fontSize: '0.9rem', color: 'var(--text-secondary)'}}>第 {sourcePage} / {totalPages} 页</span><button className="pro-btn" disabled={sourcePage >= totalPages} onClick={() => setSourcePage(p => p + 1)}>下一页</button></div>)}
                        </div></div> ) : null
                }
            </main>
        </React.Fragment>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
