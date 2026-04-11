const { useState, useEffect, useRef } = React;

const App = () => {
    const [view, setActiveView] = useState("dashboard"); 
    const [tasks, setTasks] = useState([]);
    const [selectedTask, setSelectedTask] = useState(null);
    const [detailedItems, setDetailedItems] = useState([]); 
    const [selectedItem, setSelectedItem] = useState(null); 
    const [sysStatus, setSysStatus] = useState({});
    const [newKeyword, setNewKeyword] = useState("");

    useEffect(() => {
        const timer = setInterval(refreshData, 60000);
        refreshData();
        return () => clearInterval(timer);
    }, []);

    const refreshData = async () => {
        if (document.hidden) return;
        try {
            const tResp = await fetch("/api/tasks");
            setTasks(await tResp.json());
            const sResp = await fetch("/api/sys/status");
            setSysStatus(await sResp.json());
        } catch (e) {}
    };

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

    const completedTasks = tasks.filter(t => t.status === '已完成');

    return (
        <React.Fragment>
            {/* 1. PC 侧边栏 (由 CSS 控制在移动端隐藏) */}
            <aside className="sidebar">
                <div className="logo-area">选品中枢 PRO</div>
                <ul className="nav-menu">
                    <li className={`sidebar-item ${view === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveView("dashboard")}>
                        <i className="fas fa-chart-pie"></i><span>控制台概览</span>
                    </li>
                    <li className={`sidebar-item ${view === 'tasks' ? 'active' : ''}`} onClick={() => setActiveView("tasks")}>
                        <i className="fas fa-tasks"></i><span>任务调度池</span>
                    </li>
                    <li className={`sidebar-item ${['results', 'item_detail'].includes(view) ? 'active' : ''}`} onClick={() => setActiveView("results")}>
                        <i className="fas fa-database"></i><span>选品资产库</span>
                    </li>
                </ul>
            </aside>

            {/* 2. 移动端底部导航 (由 CSS 控制在 PC 端隐藏) */}
            <nav className="nav-bar">
                <div className={`nav-item ${view === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveView("dashboard")}>
                    <i className="fas fa-chart-line"></i><span>概览</span>
                </div>
                <div className={`nav-item ${view === 'tasks' ? 'active' : ''}`} onClick={() => setActiveView("tasks")}>
                    <i className="fas fa-list-check"></i><span>任务</span>
                </div>
                <div className={`nav-item ${['results', 'item_detail'].includes(view) ? 'active' : ''}`} onClick={() => setActiveView("results")}>
                    <i className="fas fa-gem"></i><span>决策</span>
                </div>
            </nav>

            {/* 3. 主内容区 */}
            <main className="main-container">
                {view === "dashboard" && (
                    <div className="view-content animate-in">
                        <header><h1>系统中枢</h1><p>全自动选品调度管理系统</p></header>
                        
                        <div className="stats-grid">
                            <div className="stat-card">
                                <span className="label">1688 节点</span>
                                <span className={`val ${sysStatus["1688_login"] === '有效' ? 'text-green' : 'text-red'}`}>{sysStatus["1688_login"] || 'OFF'}</span>
                            </div>
                            <div className="stat-card"><span className="label">资产库</span><span className="val">{completedTasks.length} 个品类</span></div>
                            <div className="stat-card"><span className="label">活跃 Worker</span><span className="val">{sysStatus["active_workers"]}</span></div>
                            <div className="stat-card"><span className="label">存储架构</span><span className="val">MySQL</span></div>
                        </div>
                        
                        <div className="task-card" style={{marginTop: '20px'}}>
                            <h3 style={{marginBottom: '15px'}}>新建深度挖掘任务</h3>
                            <div style={{display: 'flex', gap: '10px'}}>
                                <input value={newKeyword} onChange={e => setNewKeyword(e.target.value)} placeholder="输入品类词..." />
                                <button className="pro-btn" style={{background:'#000', color:'#fff'}} onClick={createTask}>立即启动</button>
                            </div>
                        </div>
                    </div>
                )}

                {view === "tasks" && (
                    <div className="view-content animate-in">
                        <header><h1>任务流水线</h1></header>
                        <div className="task-list">
                            {tasks.map(t => (
                                <div className={`task-card ${t.status}`} key={t.id} onClick={() => t.status === '已完成' && loadTaskResults(t)}>
                                    <div className="task-title">{t.keyword}</div>
                                    <div style={{fontSize: '0.8rem', color: '#666'}}>{t.msg}</div>
                                    <div className="nano-progress"><div className="nano-bar" style={{width: `${t.progress}%`}}></div></div>
                                    <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem'}}>
                                        <span>进度: {t.progress}%</span>
                                        {t.status === '已完成' && <span style={{color: 'var(--primary)', fontWeight: 'bold'}}>查看详情 →</span>}
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
                                <header>
                                    <h1 onClick={() => setSelectedTask(null)} style={{cursor: 'pointer'}}>← {selectedTask.keyword}</h1>
                                    <button className="pro-btn outline" onClick={() => window.open(`/api/download/${selectedTask.id}`)}>导出 XLSX</button>
                                </header>
                                <div className="item-list">
                                    {detailedItems.map((group, i) => (
                                        <div className="item-card-flat" key={i} onClick={() => {setSelectedItem(group); setActiveView("item_detail")}}>
                                            <img src={group.xianyu_item.image_url} className="item-img-flat" referrerPolicy="no-referrer" />
                                            <div className="tile-body">
                                                <div className="tile-title" style={{fontWeight:'bold', fontSize:'0.9rem', marginBottom:'10px'}}>#{group.rank} {group.xianyu_item.title}</div>
                                                <div className="tile-price">¥{group.xianyu_item.price}</div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </>
                        ) : (
                            <div className="task-list">
                                <header><h1>选品决策资产库</h1></header>
                                {completedTasks.map(t => (
                                    <div className="task-card 已完成" key={t.id} onClick={() => loadTaskResults(t)}>
                                        <div className="task-title">{t.keyword}</div>
                                        <div style={{fontSize: '0.75rem', color: '#666'}}>调研完成日期: {t.created_at}</div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {view === "item_detail" && selectedItem && (
                    <div className="view-content animate-in">
                        <div style={{fontSize: '0.9rem', color: 'var(--text-sec)', cursor: 'pointer', marginBottom: '20px'}} onClick={() => setActiveView("results")}>← 返回品类列表</div>
                        <div className="task-card" style={{display: 'flex', gap: '20px', padding: '20px', background: '#fff', border: 'none'}}>
                            <img src={selectedItem.xianyu_item.image_url} style={{width: '120px', height: '120px', borderRadius: '12px', objectFit: 'cover'}} referrerPolicy="no-referrer" />
                            <div>
                                <h2 style={{fontSize: '1rem', fontWeight: 'bold', marginBottom: '10px'}}>{selectedItem.xianyu_item.title}</h2>
                                <div style={{display: 'flex', gap: '30px'}}>
                                    <div><span style={{fontSize: '0.7rem', color: '#999'}}>售价</span><div style={{fontWeight: '800'}}>¥{selectedItem.xianyu_item.price}</div></div>
                                    <div><span style={{fontSize: '0.7rem', color: '#999'}}>想要</span><div style={{fontWeight: '800'}}>{selectedItem.xianyu_item.want_count}</div></div>
                                </div>
                            </div>
                        </div>
                        <div style={{marginTop: '30px'}}>
                            <h3 style={{fontSize: '0.95rem', marginBottom: '15px'}}>1688 深度货源对比</h3>
                            {selectedItem.sources.map((src, i) => {
                                const margin = (selectedItem.xianyu_item.price - src.min_price - 20).toFixed(2);
                                return (
                                    <div className="task-card" key={i} style={{padding: '15px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                                        <div style={{flex: 1, paddingRight: '15px'}}>
                                            <a href={src.url} target="_blank" style={{textDecoration: 'none', color: 'inherit', fontWeight: 'bold', fontSize: '0.85rem'}}>{src.title}</a>
                                            <div style={{fontSize: '0.7rem', color: '#999', marginTop: '5px'}}>{src.sku_count} 个 SKU 规格</div>
                                        </div>
                                        <div style={{textAlign: 'right'}}>
                                            <div style={{fontWeight: '800'}}>¥{src.min_price}</div>
                                            <div style={{fontSize: '0.75rem', color: margin > 50 ? 'var(--success)' : 'var(--text-sec)', fontWeight: 'bold'}}>利: ¥{margin}</div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </main>
        </React.Fragment>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
