const { useState, useEffect, useRef } = React;

const App = () => {
    const [view, setActiveView] = useState("dashboard"); 
    const [tasks, setTasks] = useState([]);
    const [selectedTask, setSelectedTask] = useState(null);
    const [detailedItems, setDetailedItems] = useState([]); 
    const [selectedItem, setSelectedItem] = useState(null); 
    const [sourcePage, setSourcePage] = useState(1);
    const [sysStatus, setSysStatus] = useState({});
    const [newKeyword, setNewKeyword] = useState("");
    const timerRef = useRef(null);

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
            else {
                refreshData();
                timerId = setInterval(refreshData, POLL_INTERVAL);
            }
        };
        handleVisibilityChange();
        document.addEventListener("visibilitychange", handleVisibilityChange);
        return () => {
            clearInterval(timerId);
            document.removeEventListener("visibilitychange", handleVisibilityChange);
        };
    }, []);

    const createTask = async () => {
        if (!newKeyword) return;
        await fetch("/api/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ keyword: newKeyword }) });
        setNewKeyword("");
        setActiveView("tasks");
        refreshData();
    };
    const pauseTask = (id) => { fetch(`/api/tasks/${id}/pause`, { method: "POST" }).then(refreshData); };
    const retryTask = (id) => { fetch(`/api/tasks/${id}/retry`, { method: "POST" }).then(refreshData); };
    const deleteTask = (id) => { if (confirm("确定永久删除任务及数据吗?")) fetch(`/api/tasks/${id}`, { method: "DELETE" }).then(refreshData); };
    
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
        setSourcePage(1);
        setActiveView("item_detail");
    };
    
    const completedTasks = tasks.filter(t => t.status === '已完成');
    const pageSize = 4;
    const totalPages = selectedItem ? Math.ceil(selectedItem.sources.length / pageSize) : 0;
    const paginatedSources = selectedItem ? selectedItem.sources.slice((sourcePage - 1) * pageSize, sourcePage * pageSize) : [];

    return (
        <React.Fragment>
            <aside className="sidebar">
                <div className="logo-area">选品中枢 PRO</div>
                <ul className="nav-menu">
                    <li className={`nav-item ${view === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveView("dashboard")}>
                        <i className="fas fa-chart-pie"></i><span>控制台</span>
                    </li>
                    <li className={`nav-item ${view === 'tasks' ? 'active' : ''}`} onClick={() => setActiveView("tasks")}>
                        <i className="fas fa-tasks"></i><span>任务调度</span>
                    </li>
                    <li className={`nav-item ${['results', 'item_detail'].includes(view) ? 'active' : ''}`} onClick={() => setActiveView("results")}>
                        <i className="fas fa-database"></i><span>决策资产</span>
                    </li>
                </ul>
                <div className="sidebar-footer">
                    <div className="label">SYSTEM STATUS</div>
                    <div style={{color: sysStatus["1688_login"] === '有效' ? 'var(--success)' : 'var(--danger)', fontWeight:'bold'}}>{sysStatus["1688_login"] || 'OFFLINE'}</div>
                </div>
            </aside>

            <main className="main-container">
                {view === "dashboard" && (() => {
                    const activeTasks = tasks.filter(t => t.status !== '已完成');
                    const runningCount = tasks.filter(t => ['执行中', '正在暂停'].includes(t.status)).length;
                    const pendingCount = tasks.filter(t => t.status === '排队中').length;
                    return (
                        <div className="view-content">
                            <header><h1>仪表盘概览</h1><p>欢迎回来，系统当前运行平稳。</p></header>
                            <div className="stats-grid">
                                <div className="stat-card"><span className="label">活跃 Worker</span><span className="val">{sysStatus["active_workers"] || 0}</span></div>
                                <div className="stat-card"><span className="label">已存选品</span><span className="val">{completedTasks.length}</span></div>
                                <div className="stat-card">
                                    <span className="label">队列概览</span>
                                    <div className="val" style={{fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '15px'}}>
                                        <div><span style={{color: 'var(--primary)'}}>{runningCount}</span> <span style={{fontSize: '1rem'}}>执行</span></div>
                                        <div><span style={{color: 'var(--text-secondary)'}}>{pendingCount}</span> <span style={{fontSize: '1rem'}}>排队</span></div>
                                    </div>
                                </div>
                                <div className="stat-card"><span className="label">同步频率</span><span className="val">60s</span></div>
                            </div>
                            <div className="task-card" style={{marginTop:'40px'}}>
                                <h3 style={{marginBottom:'20px'}}>新建深度扫描任务</h3>
                                <div style={{display: 'flex', gap: '15px'}}>
                                    <input style={{flex:1, padding:'15px', borderRadius:'8px', border:'1px solid var(--border)'}} value={newKeyword} onChange={e => setNewKeyword(e.target.value)} placeholder="请输入要调研的商品品类关键词..." />
                                    <button className="pro-btn primary" style={{padding: '0 30px'}} onClick={createTask}>立即启动任务</button>
                                </div>
                            </div>
                            {activeTasks.length > 0 && (
                                <div className="task-card" style={{marginTop:'20px', cursor: 'pointer'}} onClick={() => setActiveView('tasks')}>
                                    <h3 style={{marginBottom: '15px'}}>进行中任务 ({activeTasks.length})</h3>
                                    {activeTasks.slice(0, 3).map(t => (
                                        <div key={t.id} style={{display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderTop: '1px solid var(--border)'}}>
                                            <span style={{fontWeight: 500}}>{t.keyword}</span>
                                            <span style={{color: 'var(--text-secondary)'}}>{t.status} ({t.progress}%)</span>
                                        </div>
                                    ))}
                                    <div style={{textAlign: 'center', marginTop: '15px', color: 'var(--primary)', fontWeight: 'bold'}}>点击跳转到任务队列查看全部 →</div>
                                </div>
                            )}
                        </div>
                    );
                })()}

                {view === "tasks" && (() => {
                    const activeTasks = tasks.filter(t => t.status !== '已完成');
                    const completedTasks = tasks.filter(t => t.status === '已完成');
                    return (
                        <div className="view-content">
                            <header><h1>任务队列详情</h1><p>左侧为活动任务，右侧为已完成的历史归档。</p></header>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '40px', alignItems: 'flex-start' }}>
                                <div>
                                    <h3 style={{ marginBottom: '20px' }}>执行队列</h3>
                                    <div className="task-list">
                                        {activeTasks.map(t => (
                                            <div className={`task-card ${t.status}`} key={t.id}>
                                                <div style={{ position: 'absolute', top: '20px', right: '20px', display: 'flex', gap: '8px' }}><button className="pro-btn" onClick={(e) => { e.stopPropagation(); pauseTask(t.id); }}>暂停</button></div>
                                                <div style={{ paddingRight: '100px' }}><div className="task-kw">{t.keyword}</div></div>
                                                <div className="task-msg">{t.msg}</div>
                                                <div className="nano-progress"><div className="nano-bar" style={{width: `${t.progress}%`}}></div></div>
                                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                    <span style={{fontSize: '0.8rem', color: '#999'}}>ID: {t.id}</span>
                                                    <button className="pro-btn danger" onClick={(e) => { e.stopPropagation(); deleteTask(t.id); }}><i className="fas fa-trash"></i></button>
                                                </div>
                                            </div>
                                        ))}
                                        {activeTasks.length === 0 && <div className="task-card" style={{textAlign: 'center', padding: '40px'}}>当前没有活动任务</div>}
                                    </div>
                                </div>
                                <div>
                                    <h3 style={{ marginBottom: '20px' }}>完成队列</h3>
                                    <div className="task-list">
                                        {completedTasks.map(t => (
                                            <div className={`task-card ${t.status}`} key={t.id} onClick={() => loadTaskResults(t)} style={{ cursor: 'pointer' }}>
                                                <div style={{ position: 'absolute', top: '20px', right: '20px', display: 'flex', gap: '8px' }}><button className="pro-btn" onClick={(e) => { e.stopPropagation(); retryTask(t.id); }}>重扫</button></div>
                                                <div style={{ paddingRight: '80px' }}><div className="task-kw">{t.keyword}</div></div>
                                                <div className="task-msg">调研完成于 {t.created_at}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )
                })()}

                {/* ... 其他视图 ... */}
            </main>
        </React.Fragment>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
