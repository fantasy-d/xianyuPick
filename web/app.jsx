const { useState, useEffect, useRef } = React;

const App = () => {
    const [view, setActiveView] = useState("dashboard"); 
    const [tasks, setTasks] = useState([]);
    const [selectedTask, setSelectedTask] = useState(null);
    const [detailedItems, setDetailedItems] = useState([]); 
    const [selectedItem, setSelectedItem] = useState(null); 
    const [sysStatus, setSysStatus] = useState({});
    const [newKeyword, setNewKeyword] = useState("");
    const timerRef = useRef(null);

    const refreshData = async () => {
        if (document.hidden) return;
        try {
            const tResp = await fetch("/api/tasks");
            setTasks(await tResp.json());
            const sResp = await fetch("/api/sys/status");
            setSysStatus(await sResp.json());
        } catch (e) {}
    };

    useEffect(() => {
        const POLL_INTERVAL = 60000; 
        const startPolling = () => {
            if (!timerRef.current) {
                refreshData();
                timerRef.current = setInterval(refreshData, POLL_INTERVAL);
            }
        };
        const stopPolling = () => {
            if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
        };
        startPolling();
        const handleVisibilityChange = () => document.hidden ? stopPolling() : startPolling();
        document.addEventListener("visibilitychange", handleVisibilityChange);
        return () => { stopPolling(); document.removeEventListener("visibilitychange", handleVisibilityChange); };
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

    const loadTaskResults = async (task) => {
        const resp = await fetch(`/api/task_details/${task.id}`);
        const data = await resp.json();
        if (data.details) {
            setDetailedItems(data.details);
            setSelectedTask(task);
            setActiveView("results");
        }
    };

    const enterItemDetail = (group) => {
        setSelectedItem(group);
        setActiveView("item_detail");
    };

    const completedTasks = tasks.filter(t => t.status === '已完成');

    return (
        <div className="container">
            <div className="bg-gradient"></div>
            
            <nav className="nav-bar">
                <div className={`nav-item ${view === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveView("dashboard")}>
                    <i className="fas fa-compass"></i><span>探索</span>
                </div>
                <div className={`nav-item ${view === 'tasks' ? 'active' : ''}`} onClick={() => setActiveView("tasks")}>
                    <i className="fas fa-bolt"></i><span>执行</span>
                </div>
                <div className={`nav-item ${['results', 'item_detail'].includes(view) ? 'active' : ''}`} onClick={() => setActiveView("results")}>
                    <i className="fas fa-gem"></i><span>宝库</span>
                </div>
            </nav>

            {/* 1. 探索中心 (Dashboard) */}
            {view === "dashboard" && (
                <div className="view-content animate-in">
                    <div className="hero-stats">
                        <div className="hero-title">选品中枢</div>
                        <div className="hero-subtitle">全网热度分析 · 1688 深度溯源</div>
                        <div className="stats-grid">
                            <div className="stat-card">
                                <span className="label">1688 状态</span>
                                <span className={`val ${sysStatus["1688_login"] === '有效' ? 'text-green' : 'text-red'}`}>
                                    {sysStatus["1688_login"] === '有效' ? 'ONLINE' : 'OFFLINE'}
                                </span>
                            </div>
                            <div className="stat-card">
                                <span className="label">已存选品</span>
                                <span className="val">{completedTasks.length} 个</span>
                            </div>
                        </div>
                    </div>
                    <div className="console-card">
                        <div className="search-glow">
                            <input value={newKeyword} onChange={e => setNewKeyword(e.target.value)} placeholder="输入品类词..." />
                            <button className="run-btn" onClick={createTask}><i className="fas fa-paper-plane"></i></button>
                        </div>
                    </div>
                </div>
            )}

            {/* 2. 执行队列 (Tasks) */}
            {view === "tasks" && (
                <div className="view-content animate-in">
                    <header><h1 className="hero-title">执行队列</h1></header>
                    <div className="task-list">
                        {tasks.map(t => (
                            <div className={`task-card ${t.status}`} key={t.id} onClick={() => t.status === '已完成' && loadTaskResults(t)}>
                                <div className="task-header">
                                    <div className="task-kw">{t.keyword}</div>
                                    {t.status === '执行中' && <div className="pulse-icon"></div>}
                                </div>
                                <div className="task-msg" style={{fontSize: '0.8rem', color: '#64748B'}}>{t.msg}</div>
                                <div className="nano-progress"><div className="nano-bar" style={{width: `${t.progress}%`}}></div></div>
                                <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#94A3B8'}}>
                                    <span>进度: {t.progress}%</span>
                                    {t.status === '已完成' ? <span style={{color: 'var(--primary)', fontWeight: 'bold'}}>查看详情 →</span> : <span>ID: {t.id}</span>}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* 3. 选品宝库 (Results) */}
            {view === "results" && (
                <div className="view-content animate-in">
                    {selectedTask ? (
                        <>
                            <header>
                                <div>
                                    <div style={{fontSize: '0.8rem', color: '#64748B', cursor: 'pointer'}} onClick={() => setSelectedTask(null)}>← 返回决策库</div>
                                    <h1 className="hero-title">{selectedTask.keyword}</h1>
                                </div>
                                <button className="mini-btn" style={{background: 'var(--dark)', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '15px', fontWeight: 'bold'}} onClick={() => window.open(`/api/download/${selectedTask.id}`)}>导出 XLSX</button>
                            </header>
                            <div className="item-masonry">
                                {detailedItems.map((group, i) => (
                                    <div className="item-tile" key={i} onClick={() => enterItemDetail(group)}>
                                        <img src={group.xianyu_item.image_url} referrerPolicy="no-referrer" />
                                        <div className="tile-body">
                                            <div className="tile-title">{group.xianyu_item.title}</div>
                                            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                                                <span className="tile-price">¥{group.xianyu_item.price}</span>
                                                <span style={{fontSize: '0.65rem', color: '#94A3B8'}}>{group.sources.length}货源</span>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </>
                    ) : (
                        <div>
                            <header><h1 className="hero-title">选品资产库</h1></header>
                            <div className="task-list">
                                {completedTasks.map(t => (
                                    <div className="task-card 已完成" key={t.id} onClick={() => loadTaskResults(t)}>
                                        <div className="task-header">
                                            <div className="task-kw">{t.keyword}</div>
                                            <i className="fas fa-chevron-right" style={{color: '#E2E8F0'}}></i>
                                        </div>
                                        <div className="task-msg">调研日期: {t.created_at} · 10个闲鱼热品</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* 4. 详情页 (Item Detail) */}
            {view === "item_detail" && selectedItem && (
                <div className="view-content animate-in">
                    <div className="back-btn" onClick={() => setActiveView("results")}>
                        <i className="fas fa-arrow-left"></i> 返回列表
                    </div>
                    <div className="detail-hero-card">
                        <img src={selectedItem.xianyu_item.image_url} className="hero-img-full" referrerPolicy="no-referrer" />
                        <div className="hero-content">
                            <h2 style={{fontSize: '1.1rem', fontWeight: 'bold', marginBottom: '15px'}}>{selectedItem.xianyu_item.title}</h2>
                            <div style={{display: 'flex', gap: '25px'}}>
                                <div><span style={{fontSize: '0.7rem', color: '#64748B'}}>想要</span><div style={{fontWeight: '800', fontSize: '1.1rem'}}>{selectedItem.xianyu_item.want_count}</div></div>
                                <div><span style={{fontSize: '0.7rem', color: '#64748B'}}>售价</span><div style={{fontWeight: '800', fontSize: '1.1rem'}}>¥{selectedItem.xianyu_item.price}</div></div>
                            </div>
                        </div>
                    </div>
                    <div className="source-section">
                        <h3 style={{marginBottom: '15px', fontSize: '1rem', fontWeight: 'bold'}}>1688 货源对比</h3>
                        {selectedItem.sources.map((src, i) => {
                            const margin = (selectedItem.xianyu_item.price - src.min_price - 20).toFixed(2);
                            return (
                                <div className="source-detail-row" key={i}>
                                    <div style={{flex: 1, paddingRight: '15px'}}>
                                        <a href={src.url} target="_blank" style={{textDecoration: 'none', color: 'inherit', fontWeight: 'bold', fontSize: '0.85rem', display: 'block', marginBottom: '5px'}}>{src.title}</a>
                                        <span style={{fontSize: '0.7rem', color: '#64748B'}}>{src.sku_count} 个 SKU</span>
                                    </div>
                                    <div style={{textAlign: 'right', minWidth: '80px'}}>
                                        <div style={{fontSize: '0.9rem', fontWeight: '800'}}>¥{src.min_price}</div>
                                        <div style={{fontSize: '0.75rem', color: margin > 50 ? '#16A34A' : '#DC2626', fontWeight: 'bold'}}>利: ¥{margin}</div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
