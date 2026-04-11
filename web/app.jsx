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
        const POLL_INTERVAL = 10000; // 调试时设为10秒，方便观察暂停状态
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
        return () => stopPolling();
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

    const pauseTask = async (id) => {
        await fetch(`/api/tasks/${id}/pause`, { method: "POST" });
        refreshData();
    };

    const retryTask = async (id) => {
        await fetch(`/api/tasks/${id}/retry`, { method: "POST" });
        refreshData();
    };

    const deleteTask = async (id) => {
        if (confirm("确定删除任务?")) {
            await fetch(`/api/tasks/${id}`, { method: "DELETE" });
            refreshData();
        }
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

    const getStatusIcon = (status) => {
        if (status === '执行中') return <i className="fas fa-sync fa-spin" style={{color: 'var(--system-orange)'}}></i>;
        if (status === '正在暂停') return <i className="fas fa-hand-paper" style={{color: 'var(--system-orange)'}}></i>;
        if (status === '已完成') return <i className="fas fa-check-circle" style={{color: 'var(--system-green)'}}></i>;
        if (status === '已暂停') return <i className="fas fa-pause-circle" style={{color: '#8E8E93'}}></i>;
        return <i className="far fa-clock" style={{color: '#8E8E93'}}></i>;
    };

    return (
        <div className="container">
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

            {view === "dashboard" && (
                <div className="view-content animate-in">
                    <header>
                        <h1 className="hero-title">Mission HUB</h1>
                        <p className="hero-subtitle">支持 Checkpoint 级平滑暂停</p>
                    </header>
                    <div className="stats-grid">
                        <div className="stat-card"><span className="label">1688 节点</span><span className="val text-green">ONLINE</span></div>
                        <div className="stat-card"><span className="label">已存资产</span><span className="val">{tasks.filter(t=>t.status==='已完成').length}</span></div>
                    </div>
                    <div className="console-card">
                        <div className="search-glow">
                            <input value={newKeyword} onChange={e => setNewKeyword(e.target.value)} placeholder="输入待爆破品类..." />
                            <button className="run-btn" onClick={createTask}><i className="fas fa-paper-plane"></i></button>
                        </div>
                    </div>
                </div>
            )}

            {view === "tasks" && (
                <div className="view-content animate-in">
                    <header><h1 className="hero-title">执行队列</h1></header>
                    <div className="task-list">
                        {tasks.map(t => (
                            <div className={`task-card ${t.status}`} key={t.id}>
                                <div className="task-header" onClick={() => t.status === '已完成' && loadTaskResults(t)}>
                                    <div className="task-kw-group">
                                        <div className="task-icon">{getStatusIcon(t.status)}</div>
                                        <div className="task-kw">{t.keyword}</div>
                                    </div>
                                    <div style={{fontSize: '0.6rem', color: 'var(--text-secondary)'}}>{t.created_at}</div>
                                </div>
                                <div style={{fontSize: '0.75rem', color: 'var(--text-secondary)', marginLeft: '28px', marginBottom: '10px'}}>{t.msg}</div>
                                <div className="nano-progress" style={{marginLeft: '28px'}}><div className="nano-bar" style={{width: `${t.progress}%`}}></div></div>
                                
                                <div className="task-actions" style={{marginLeft: '28px', marginTop: '10px', display: 'flex', gap: '10px'}}>
                                    {t.status === '执行中' && (
                                        <button className="pro-btn outline" onClick={() => pauseTask(t.id)}>
                                            <i className="fas fa-pause"></i> 暂停
                                        </button>
                                    )}
                                    {(t.status === '已完成' || t.status === '已暂停' || t.status === '失败') && (
                                        <button className="pro-btn outline" onClick={() => retryTask(t.id)}>
                                            <i className="fas fa-play"></i> {t.status === '已完成' ? '重扫' : '恢复执行'}
                                        </button>
                                    )}
                                    {t.status === '已完成' && <button className="pro-btn outline" onClick={() => loadTaskResults(t)}>查看结果</button>}
                                    <button className="pro-btn danger" onClick={() => deleteTask(t.id)}><i className="fas fa-trash"></i></button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {view === "results" && (
                <div className="view-content animate-in">
                    {selectedTask ? (
                        <>
                            <header style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end'}}>
                                <div><div onClick={() => setSelectedTask(null)} style={{fontSize: '0.7rem', color: 'var(--text-secondary)', cursor: 'pointer'}}>← BACK</div><h1 className="hero-title">{selectedTask.keyword}</h1></div>
                                <button className="mini-btn" onClick={() => window.open(`/api/download/${selectedTask.id}`)}>XLSX</button>
                            </header>
                            <div className="results-list">
                                {detailedItems.map((group, i) => (
                                    <div className="item-card-flat" key={i} onClick={() => enterItemDetail(group)}>
                                        <img src={group.xianyu_item.image_url} className="item-img-flat" referrerPolicy="no-referrer" />
                                        <div className="tile-body">
                                            <div className="tile-title">#{group.rank} {group.xianyu_item.title}</div>
                                            <div className="tile-price">¥{group.xianyu_item.price}</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </>
                    ) : (
                        <div className="task-list">
                            <header><h1 className="hero-title">选品资产库</h1></header>
                            {completedTasks.map(t => (
                                <div className="task-card 已完成" key={t.id} onClick={() => loadTaskResults(t)}>
                                    <div className="task-header"><div className="task-kw-group"><div className="task-icon"><i className="fas fa-folder" style={{color: '#FFCC00'}}></i></div><div className="task-kw">{t.keyword}</div></div><i className="fas fa-chevron-right"></i></div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {view === "item_detail" && selectedItem && (
                <div className="view-content animate-in">
                    <div className="back-btn" onClick={() => setActiveView("results")}>← 返回列表</div>
                    <div className="detail-hero-card">
                        <img src={selectedItem.xianyu_item.image_url} className="hero-img-full" referrerPolicy="no-referrer" />
                        <div className="hero-content"><h2 style={{fontSize: '1rem'}}>{selectedItem.xianyu_item.title}</h2><div className="hero-metrics" style={{display: 'flex', gap: '20px', marginTop: '10px'}}><div><span>售价</span><strong>¥{selectedItem.xianyu_item.price}</strong></div><div><span>想要</span><strong>{selectedItem.xianyu_item.want_count}</strong></div></div></div>
                    </div>
                    {selectedItem.sources.map((src, i) => (
                        <div className="source-detail-row" key={i}><div style={{flex: 1}}><a href={src.url} target="_blank" style={{color: 'inherit', textDecoration: 'none', fontWeight: 'bold'}}>{src.title}</a></div><div style={{textAlign: 'right'}}><strong>¥{src.min_price}</strong></div></div>
                    ))}
                </div>
            )}
        </div>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
