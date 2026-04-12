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

const App = () => {
    const [view, setActiveView] = useState("dashboard"); 
    const [tasks, setTasks] = useState([]);
    const [selectedTask, setSelectedTask] = useState(null);
    const [detailedItems, setDetailedItems] = useState([]); 
    const [selectedItem, setSelectedItem] = useState(null); 
    const [sourcePage, setSourcePage] = useState(1);
    const [sysStatus, setSysStatus] = useState({});
    const [newKeyword, setNewKeyword] = useState("");

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
    const deleteTask = (id) => { if (confirm("确定永久删除任务吗?")) fetch(`/api/tasks/${id}`, { method: "DELETE" }).then(refreshData); };
    
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
                            {activeTasks.length > 0 && (<div className="task-card" style={{marginTop:'20px', cursor: 'pointer'}} onClick={() => setActiveView('tasks')}><h3 style={{marginBottom: '15px'}}>进行中任务 ({activeTasks.length})</h3>{activeTasks.slice(0, 3).map(t => (<div key={t.id} style={{display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderTop: '1px solid var(--border)'}}><span style={{fontWeight: 500}}>{t.keyword}</span><span style={{color: 'var(--text-secondary)'}}>{t.status} ({t.progress}%)</span></div>))}<div style={{textAlign: 'center', marginTop: '15px', color: 'var(--primary)', fontWeight: 'bold'}}>点击跳转到任务队列查看全部 →</div></div>)}
                        </div>
                    );
                 })() :
                 view === "tasks" ? (() => {
                    const activeTasks = tasks.filter(t => t.status !== '已完成');
                    const completedTasks = tasks.filter(t => t.status === '已完成');
                    return (
                        <div className="view-content"><header><h1>任务队列详情</h1><p>左侧为活动任务，右侧为已完成的历史归档。</p></header><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '40px', alignItems: 'flex-start' }}><div><h3 style={{ marginBottom: '20px' }}>执行队列</h3><div className="task-list">{activeTasks.map(t => (<div className={`task-card ${t.status}`} key={t.id}><div style={{ position: 'absolute', top: '20px', right: '20px', display: 'flex', gap: '8px' }}>{t.status === '执行中' ? <button className="pro-btn" onClick={(e) => { e.stopPropagation(); pauseTask(t.id); }}>暂停</button> : (t.status === '已暂停' || t.status === '失败') ? <button className="pro-btn primary" onClick={(e) => { e.stopPropagation(); retryTask(t.id); }}>恢复</button> : null}</div><div style={{ paddingRight: '100px' }}><div className="task-kw">{t.keyword}</div></div><div className="task-msg">{t.msg}</div><div className="nano-progress"><div className="nano-bar" style={{width: `${t.progress}%`}}></div></div><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><span style={{fontSize: '0.8rem', color: '#999'}}>ID: {t.id}</span><button className="pro-btn danger" onClick={(e) => { e.stopPropagation(); deleteTask(t.id); }}><i className="fas fa-trash"></i></button></div></div>))}{activeTasks.length === 0 && <div className="task-card" style={{textAlign: 'center', padding: '40px'}}>当前没有活动任务</div>}</div></div><div><h3 style={{ marginBottom: '20px' }}>完成队列</h3><div className="task-list">{completedTasks.map(t => (<div className={`task-card ${t.status}`} key={t.id} onClick={() => loadTaskResults(t)} style={{ cursor: 'pointer' }}><div style={{ position: 'absolute', top: '20px', right: '20px', display: 'flex', gap: '8px' }}><button className="pro-btn" onClick={(e) => { e.stopPropagation(); retryTask(t.id); }}>重扫</button></div><div style={{ paddingRight: '80px' }}><div className="task-kw">{t.keyword}</div></div><div className="task-msg">调研完成于 {t.created_at}</div></div>))}</div></div></div></div>
                    )
                 })() :
                 view === "results" ? ( selectedTask ? ( <> <header style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}><div><h1 onClick={() => setSelectedTask(null)} style={{cursor: 'pointer'}}>← {selectedTask.keyword} 深度报告</h1></div><button className="pro-btn primary" onClick={() => window.open(`/api/download/${selectedTask.id}`)}>导出 XLSX</button></header><div className="item-grid">{detailedItems.length > 0 ? detailedItems.map((group) => (<div className="item-card" key={group.rank} onClick={() => enterItemDetail(group)}><img src={group.xianyu_item?.image_url} referrerPolicy="no-referrer" /><div className="tile-body"><div className="tile-title">#{group.rank} {group.xianyu_item?.title}</div><div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px'}}><span className="tile-price">¥{group.xianyu_item?.price}</span><span style={{fontSize: '0.8rem', color: 'var(--text-secondary)'}}>{group.sources?.length || 0} 个货源</span></div><div className="id-corner">ID: {group.xianyu_item?.db_id}</div></div></div>)) : (<div className="task-card" style={{gridColumn: '1/-1', textAlign: 'center', padding: '100px'}}><p>该任务尚未产生详情数据。</p></div>)}</div></> ) : (<div><header><h1>选品决策资产库</h1></header><div className="task-list">{completedTasks.map(t => (<div className="task-card 已完成" key={t.id} onClick={() => loadTaskResults(t)} style={{cursor: 'pointer'}}><div className="task-kw">{t.keyword}</div><div className="task-msg">调研完成日期: {t.created_at}</div></div>))}</div></div>) ) :
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
                            <header><h3 style={{marginBottom: '20px'}}>1688 货源深度对比表 ({selectedItem.sources?.length || 0} 条)</h3></header>
                            {paginatedSources.map((src, i) => { 
                                const margin = (selectedItem.xianyu_item?.price - src.min_price - 20).toFixed(2); 
                                const isDropped = !!src.drop_reason;
                                return (
                                    <div className={`task-card ${isDropped ? 'dropped' : ''}`} key={i} style={{display:'flex', justifyContent:'space-between', alignItems:'center', padding: '15px', marginBottom: '15px', position: 'relative'}}>
                                        <div style={{flex:1}}>
                                            <a href={src.url} target="_blank" className={isDropped ? 'text-muted' : 'hover-link'} style={{textDecoration: isDropped ? 'line-through' : 'none', color:'inherit', fontWeight:'600', display: 'block', marginBottom: '5px'}}>{src.title}</a>
                                            <div style={{display: 'flex', gap: '15px', alignItems: 'center'}}>
                                                <span style={{fontSize: '0.8rem', color: 'var(--text-secondary)'}}>{src.sku_count > 0 ? `${src.sku_count} 个 SKU 规格` : '仅列表页快照'}</span>
                                                <span style={{fontSize: '0.7rem', color: 'var(--text-secondary)', background: '#F1F5F9', padding: '1px 6px', borderRadius: '4px'}}>ID: {src.db_id}</span>
                                            </div>
                                        </div>
                                        <div style={{textAlign:'right', paddingLeft:'20px', minWidth: '150px'}}>
                                            {isDropped ? ( <span className="drop-badge">已丢弃: {src.drop_reason}</span> ) : ( <> <div style={{fontSize:'1.2rem', fontWeight:'700'}}>¥{src.min_price}</div> <div style={{fontSize:'0.9rem', color: margin > 50 ? 'var(--success)' : 'var(--danger)', fontWeight:'bold'}}>利润: ¥{margin}</div> </> )}
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
