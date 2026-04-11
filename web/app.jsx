const { useState, useEffect, useRef } = React;

const App = () => {
    const [view, setActiveView] = useState("dashboard"); 
    const [tasks, setTasks] = useState([]);
    const [selectedTask, setSelectedTask] = useState(null);
    const [detailedItems, setDetailedItems] = useState([]); 
    const [selectedItem, setSelectedItem] = useState(null); 
    const [sourcePage, setSourcePage] = useState(1); // 将分页状态提升到顶层
    const [sysStatus, setSysStatus] = useState({});
    const [newKeyword, setNewKeyword] = useState("");
    const timerRef = useRef(null);

    const refreshData = () => {
        fetch("/api/tasks").then(r => r.json()).then(setTasks);
        fetch("/api/sys/status").then(r => r.json()).then(setSysStatus);
    };

    useEffect(() => {
        const timer = setInterval(refreshData, 60000);
        refreshData();
        return () => clearInterval(timer);
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
        setSourcePage(1); // 每次进入新详情页时，重置为第一页
        setActiveView("item_detail");
    };
    
    const completedTasks = tasks.filter(t => t.status === '已完成');

    // --- 分页逻辑 ---
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
                {/* ... 其他视图保持不变 ... */}
                {view === "dashboard" && (
                    <div className="view-content">
                        <header><h1>仪表盘概览</h1><p>欢迎回来，系统当前运行平稳。</p></header>
                        <div className="stats-grid">
                            <div className="stat-card"><span className="label">活跃 Worker</span><span className="val">{sysStatus["active_workers"] || 0}</span></div>
                            <div className="stat-card"><span className="label">已存选品</span><span className="val">{completedTasks.length}</span></div>
                            <div className="stat-card"><span className="label">数据库驱动</span><span className="val">MySQL</span></div>
                            <div className="stat-card"><span className="label">同步频率</span><span className="val">60s</span></div>
                        </div>
                        <div className="task-card" style={{marginTop:'40px'}}>
                            <h3 style={{marginBottom:'20px'}}>新建深度扫描任务</h3>
                            <div style={{display: 'flex', gap: '15px'}}>
                                <input style={{flex:1, padding:'15px', borderRadius:'8px', border:'1px solid var(--border)'}} value={newKeyword} onChange={e => setNewKeyword(e.target.value)} placeholder="请输入要调研的商品品类关键词..." />
                                <button className="pro-btn primary" style={{padding: '0 30px'}} onClick={createTask}>立即启动任务</button>
                            </div>
                        </div>
                    </div>
                )}
                {view === "tasks" && (
                    <div className="view-content">
                        <header><h1>任务流水线</h1><p>监控所有正在执行、排队中、已完成或失败的任务。</p></header>
                        <div className="task-list">
                            {tasks.map(t => (
                                <div className={`task-card ${t.status}`} key={t.id}>
                                    <div style={{ position: 'absolute', top: '20px', right: '20px', display: 'flex', gap: '8px' }}>
                                        {t.status === '执行中' && <button className="pro-btn" onClick={() => pauseTask(t.id)}>暂停</button>}
                                        {t.status === '已完成' && <button className="pro-btn" onClick={() => retryTask(t.id)}>重扫</button>}
                                        {(t.status === '已暂停' || t.status === '失败') && <button className="pro-btn primary" onClick={() => retryTask(t.id)}>恢复</button>}
                                    </div>
                                    <div style={{ paddingRight: '120px' }}>
                                        <div className="task-kw" onClick={() => t.status === '已完成' && loadTaskResults(t)} style={{cursor: t.status === '已完成' ? 'pointer' : 'default'}}>{t.keyword}</div>
                                    </div>
                                    <div className="task-msg">{t.msg}</div>
                                    <div className="nano-progress"><div className="nano-bar" style={{width: `${t.progress}%`}}></div></div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <span style={{fontSize: '0.8rem', color: '#999'}}>ID: {t.id}</span>
                                        <button className="pro-btn danger" onClick={() => deleteTask(t.id)}><i className="fas fa-trash"></i></button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                {view === "results" && (
                    <div className="view-content">
                        {selectedTask ? (
                            <>
                                <header style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                                    <div><h1 onClick={() => setSelectedTask(null)} style={{cursor: 'pointer'}}>← {selectedTask.keyword} 深度报告</h1></div>
                                    <button className="pro-btn primary" onClick={() => window.open(`/api/download/${selectedTask.id}`)}>导出完整 XLSX 报表</button>
                                </header>
                                <div className="item-grid">
                                    {detailedItems.map((group) => (
                                        <div className="item-card" key={group.rank} onClick={() => enterItemDetail(group)}>
                                            <img src={group.xianyu_item.image_url} referrerPolicy="no-referrer" />
                                            <div className="tile-body">
                                                <div className="tile-title">#{group.rank} {group.xianyu_item.title}</div>
                                                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                                                    <span className="tile-price">¥{group.xianyu_item.price}</span>
                                                    <span style={{fontSize: '0.8rem', color: 'var(--text-secondary)'}}>{group.sources.length} 个货源</span>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </>
                        ) : (
                            <div>
                                <header><h1>选品决策资产库</h1></header>
                                <div className="task-list">
                                    {completedTasks.map(t => (
                                        <div className="task-card 已完成" key={t.id} onClick={() => loadTaskResults(t)} style={{cursor: 'pointer'}}>
                                            <div className="task-kw">{t.keyword}</div>
                                            <div className="task-msg">调研完成日期: {t.created_at}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* --- D. 最终详情页视图 (已修复) --- */}
                {view === "item_detail" && selectedItem && (
                    <div className="view-content">
                         <div onClick={() => setActiveView("results")} style={{cursor: 'pointer', marginBottom: '30px', color: 'var(--text-secondary)', fontSize: '0.9rem', fontWeight: '500'}}>
                            <i className="fas fa-arrow-left"></i> 返回 "{selectedTask.keyword}" 报告
                         </div>
                        <div className="task-card" style={{display: 'flex', gap: '30px', alignItems: 'center', padding: '30px', marginBottom: '40px'}}>
                            <img src={selectedItem.xianyu_item.image_url} style={{width:'200px', height: '200px', borderRadius:'12px', objectFit:'cover'}} referrerPolicy="no-referrer" />
                            <div style={{flex: 1}}>
                                <h2 style={{fontSize:'1.5rem', fontWeight: '700', marginBottom: '20px'}}>{selectedItem.xianyu_item.title}</h2>
                                <div style={{display: 'flex', gap: '40px'}}>
                                    <div className="stat-card" style={{padding: '0', border: 'none', background: 'none'}}><span className="label">闲鱼售价</span><div className="val" style={{fontSize: '1.8rem'}}>¥{selectedItem.xianyu_item.price}</div></div>
                                    <div className="stat-card" style={{padding: '0', border: 'none', background: 'none'}}><span className="label">“想要”人数</span><div className="val" style={{fontSize: '1.8rem'}}>{selectedItem.xianyu_item.want_count}</div></div>
                                </div>
                            </div>
                        </div>
                        <div>
                            <header><h3 style={{marginBottom: '20px'}}>1688 货源深度对比表 ({selectedItem.sources.length} 条)</h3></header>
                            {paginatedSources.map((src, i) => {
                                const margin = (selectedItem.xianyu_item.price - src.min_price - 20).toFixed(2);
                                return (
                                    <div className="task-card" key={i} style={{display:'flex', justifyContent:'space-between', alignItems:'center', padding: '15px', marginBottom: '15px'}}>
                                        <div style={{flex:1}}><a href={src.url} target="_blank" style={{textDecoration:'none', color:'inherit', fontWeight:'600', display: 'block', marginBottom: '5px'}}>{src.title}</a><span style={{fontSize: '0.8rem', color: 'var(--text-secondary)'}}>{src.sku_count} 个 SKU 规格</span></div>
                                        <div style={{textAlign:'right', paddingLeft:'20px', minWidth: '120px'}}><div style={{fontSize:'1.2rem', fontWeight:'700'}}>¥{src.min_price}</div><div style={{fontSize:'0.9rem', color: margin > 50 ? 'var(--success)' : 'var(--danger)', fontWeight:'bold'}}>利润: ¥{margin}</div></div>
                                    </div>
                                );
                            })}
                            {selectedItem.sources.length === 0 && <div className="task-card"><p>该商品暂未找到匹配的 1688 货源。</p></div>}
                            
                            {totalPages > 1 && (
                                <div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '15px', marginTop: '30px'}}>
                                    <button className="pro-btn" disabled={sourcePage <= 1} onClick={() => setSourcePage(p => p - 1)}>上一页</button>
                                    <span style={{fontSize: '0.9rem', color: 'var(--text-secondary)'}}>第 {sourcePage} / {totalPages} 页</span>
                                    <button className="pro-btn" disabled={sourcePage >= totalPages} onClick={() => setSourcePage(p => p + 1)}>下一页</button>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </main>
        </React.Fragment>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
