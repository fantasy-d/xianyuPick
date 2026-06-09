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

    const btnStyle = { padding: '6px 14px', borderRadius: '8px', border: 'none', cursor: 'pointer', fontSize: '0.8rem', fontWeight: '600', marginTop: '8px' };

    return ReactDOM.createPortal(
        <div 
            className={`preview-modal-overlay ${active ? 'active' : ''}`}
            onClick={handleClose}
        >
            <div 
                className={`preview-modal-wrapper ${active ? 'active' : ''}`}
                onClick={e => e.stopPropagation()}
            >
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
                    <button style={{ ...btnStyle, background: 'var(--border)', color: 'var(--text)' }} onClick={handleClose}>取消</button>
                    <button style={{ ...btnStyle, background: 'var(--primary)', color: '#fff' }} onClick={handleConfirm} disabled={loadingSkus}>确认发布</button>
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

    const margin = (item.ref_price - item.source_price - 20).toFixed(2);
    
    // 动态构造 mockSrc 数据结构传给 PublishButton
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
                className={`detail-modal-wrapper ${active ? 'active' : ''}`}
                onClick={e => e.stopPropagation()}
            >
                <div className="detail-modal-header">
                    <h2><i className="fas fa-box-open" style={{ color: 'var(--primary)' }}></i> 闲鱼发布商品详情</h2>
                    <button className="detail-modal-close" onClick={handleClose}>&times;</button>
                </div>
                
                <div className="detail-modal-body">
                    <div style={{ display: 'flex', gap: '25px', alignItems: 'flex-start' }}>
                        {/* 缩略图大图展示 */}
                        <div style={{ flexShrink: 0 }}>
                            {item.source_image ? (
                                <img src={item.source_image} style={{ width: '180px', height: '180px', borderRadius: '16px', objectFit: 'cover', border: '1px solid var(--border)', boxShadow: '0 8px 20px rgba(0,0,0,0.06)' }} referrerPolicy="no-referrer" />
                            ) : (
                                <div style={{ width: '180px', height: '180px', borderRadius: '16px', background: '#F1F5F9', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94A3B8', border: '1px solid var(--border)' }}>暂无图片</div>
                            )}
                        </div>
                        
                        {/* 关键信息显示 */}
                        <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                                <span style={{ fontSize: '0.7rem', color: 'var(--primary)', background: '#FFEFE6', padding: '3px 8px', borderRadius: '4px', fontWeight: 'bold' }}>1688 货源</span>
                                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>ID: {item.source_db_id}</span>
                            </div>
                            <h3 style={{ fontSize: '1.05rem', fontWeight: '700', lineHeight: '1.4', marginBottom: '16px', color: 'var(--text-main)' }}>
                                <a href={item.source_url} target="_blank" rel="noreferrer" className="hover-link" style={{ textDecoration: 'none', color: 'inherit' }}>
                                    {item.source_title} <i className="fas fa-external-link-alt" style={{ fontSize: '0.75rem', color: '#94A3B8' }}></i>
                                </a>
                            </h3>
                            
                            {/* 信息卡片网格 */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 20px', padding: '16px', background: 'rgba(0,0,0,0.02)', borderRadius: '12px', border: '1px solid var(--border)', marginBottom: '16px' }}>
                                <div>
                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>闲鱼端商品 ID</span>
                                    <div style={{ fontWeight: '700', fontSize: '0.88rem', marginTop: '3px', fontFamily: 'monospace' }}>{item.xianyu_item_id || '暂无'}</div>
                                </div>
                                <div>
                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>发布记录时间</span>
                                    <div style={{ fontWeight: '600', fontSize: '0.88rem', marginTop: '3px' }}>{item.publish_time}</div>
                                </div>
                                {item.ref_title && (
                                    <div style={{ gridColumn: '1 / -1' }}>
                                        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>关联参考爆款标题</span>
                                        <div style={{ fontWeight: '600', fontSize: '0.82rem', marginTop: '3px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={item.ref_title}>
                                            {item.ref_title}
                                        </div>
                                    </div>
                                )}
                            </div>
                            
                            {/* 核心对比利润指标 */}
                            <div style={{ display: 'flex', gap: '20px', alignItems: 'center', borderTop: '1px dashed var(--border)', paddingTop: '16px' }}>
                                <div>
                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>1688 成本进价</span>
                                    <div style={{ fontSize: '1.25rem', fontWeight: '800', marginTop: '3px' }}>¥{item.source_price}</div>
                                </div>
                                {item.ref_price > 0 && (
                                    <>
                                        <div style={{ borderLeft: '1px solid var(--border)', height: '24px' }}></div>
                                        <div>
                                            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>爆款参考价</span>
                                            <div style={{ fontSize: '1.25rem', fontWeight: '800', marginTop: '3px' }}>¥{item.ref_price}</div>
                                        </div>
                                        <div style={{ borderLeft: '1px solid var(--border)', height: '24px' }}></div>
                                        <div>
                                            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>预计利润额</span>
                                            <div style={{ fontSize: '1.25rem', fontWeight: '800', color: margin > 50 ? 'var(--success)' : 'var(--danger)', marginTop: '3px' }}>¥{margin}</div>
                                        </div>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* SKU 规格明细板块 */}
                    <div style={{ marginTop: '25px', borderTop: '1px solid var(--border)', paddingTop: '20px' }}>
                        <h4 style={{ fontSize: '0.9rem', fontWeight: '800', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-main)' }}>
                            <i className="fas fa-th-list" style={{ color: 'var(--primary)', fontSize: '0.85rem' }}></i>
                            商品关联 SKU 规格明细 ({skus.length} 个规格)
                        </h4>
                        
                        {loadingSkus ? (
                            <div style={{ padding: '20px 0', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                                🔄 正在加载 SKU 规格明细...
                            </div>
                        ) : skus.length > 0 ? (
                            <div style={{ 
                                maxHeight: '220px', 
                                overflowY: 'auto', 
                                border: '1px solid var(--border)', 
                                borderRadius: '12px', 
                                background: 'rgba(0, 0, 0, 0.01)',
                                padding: '4px'
                            }}>
                                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', textAlign: 'left' }}>
                                    <thead>
                                        <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                            <th style={{ padding: '10px 12px', color: 'var(--text-secondary)', fontWeight: '700', width: '50px' }}>规格图</th>
                                            <th style={{ padding: '10px 12px', color: 'var(--text-secondary)', fontWeight: '700' }}>规格文案</th>
                                            <th style={{ padding: '10px 12px', color: 'var(--text-secondary)', fontWeight: '700', width: '100px' }}>成本进价</th>
                                            <th style={{ padding: '10px 12px', color: 'var(--text-secondary)', fontWeight: '700', width: '110px' }}>默认闲鱼价</th>
                                            <th style={{ padding: '10px 12px', color: 'var(--text-secondary)', fontWeight: '700', width: '80px' }}>库存</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {skus.map((sku, idx) => (
                                            <tr key={idx} style={{ 
                                                borderBottom: idx < skus.length - 1 ? '1px solid rgba(0,0,0,0.04)' : 'none',
                                                transition: 'background-color 0.15s'
                                            }} className="sku-detail-row">
                                                <td style={{ padding: '8px 12px' }}>
                                                    {sku.image ? (
                                                        <img src={sku.image} referrerPolicy="no-referrer" style={{ width: '32px', height: '32px', borderRadius: '6px', objectFit: 'cover', border: '1px solid var(--border)' }} />
                                                    ) : (
                                                        <div style={{ width: '32px', height: '32px', borderRadius: '6px', background: '#F1F5F9', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94A3B8', fontSize: '0.55rem' }}>无图</div>
                                                    )}
                                                </td>
                                                <td style={{ padding: '8px 12px', fontWeight: '600', color: 'var(--text-main)', wordBreak: 'break-all' }}>
                                                    {sku.sku_text}
                                                </td>
                                                <td style={{ padding: '8px 12px', fontWeight: '700', color: 'var(--text-secondary)' }}>
                                                    ¥{sku.price}
                                                </td>
                                                <td style={{ padding: '8px 12px', fontWeight: '800', color: 'var(--primary)' }}>
                                                    ¥{(parseFloat(sku.price) + 30).toFixed(2)}
                                                </td>
                                                <td style={{ padding: '8px 12px', color: sku.stock > 10 ? 'var(--success)' : 'var(--danger)', fontWeight: '700' }}>
                                                    {sku.stock}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <div style={{ padding: '20px 0', textAlign: 'center', color: '#94A3B8', fontSize: '0.85rem' }}>
                                📦 该商品为单规格一口价商品（无多属性规格明细）。
                            </div>
                        )}
                    </div>
                </div>
                
                <div className="detail-modal-footer">
                    <div style={{ display: 'flex', width: '100%', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                            提示：可在右侧控制面板进行下架或删除操作。
                        </div>
                        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
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
                            <button className="pro-btn" style={{ padding: '6px 16px', fontSize: '0.8rem' }} onClick={handleClose}>关闭</button>
                        </div>
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
            const res = await fetch(`/api/xianyu_products?page=${page}&limit=${limit}&keyword=${encodeURIComponent(keyword)}&sort_by=${sortBy}&sort_order=${sortOrder}`)
                .then(r => r.json());
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
    }, [page, keyword, sortBy, sortOrder, refreshTrigger]);

    // 移除原有的 overflow 控制逻辑，由 DetailModal 组件自身效果管控

    const handleStatusLoaded = (dbId, status, result) => {
        setBatchStatusMap(prev => {
            // 如果已经被删除，我们需要更新列表
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

    const renderSortHeader = (label, field, style = {}) => {
        const isCurrent = sortBy === field;
        let icon = <i className="fas fa-sort" style={{ color: '#CBD5E1', marginLeft: '6px' }}></i>;
        if (isCurrent) {
            icon = sortOrder === 'asc' 
                ? <i className="fas fa-sort-up" style={{ color: 'var(--primary)', marginLeft: '6px' }}></i>
                : <i className="fas fa-sort-down" style={{ color: 'var(--primary)', marginLeft: '6px' }}></i>;
        }
        return (
            <th 
                onClick={() => handleSort(field)} 
                style={{ cursor: 'pointer', userSelect: 'none', ...style }}
                title="点击进行排序"
            >
                <div style={{ display: 'flex', alignItems: 'center' }}>
                    {label} {icon}
                </div>
            </th>
        );
    };

    const totalPages = Math.ceil(total / limit);

    return (
        <div className="view-content">
            <header>
                <h1>📦 闲鱼已上架商品管理</h1>
                <p>管理目前在闲鱼中已成功发布的商品资产，并与 1688 原始货源进行联动追踪。点击行项目可展开详情及控制面板。</p>
            </header>

            {/* 搜索栏 */}
            <div className="task-card" style={{ padding: '20px', marginBottom: '30px', display: 'flex', gap: '15px' }}>
                <input 
                    style={{ flex: 1, padding: '10px 15px', borderRadius: '8px', border: '1px solid var(--border)' }}
                    value={keyword}
                    onChange={e => { setKeyword(e.target.value); setPage(1); }}
                    placeholder="输入商品标题关键字搜索（支持搜索 1688 源标题或参考爆款标题）..."
                />
                <button className="pro-btn primary" onClick={() => { setPage(1); fetchPublishedProducts(); }}>搜索</button>
            </div>

            {loading ? (
                <div className="task-card" style={{ textAlign: 'center', padding: '100px' }}>
                    <p>🔄 正在加载闲鱼商品列表...</p>
                </div>
            ) : items.length > 0 ? (
                <div>
                    <div className="pub-list-container">
                        <table className="pub-table">
                            <thead>
                                <tr>
                                    <th style={{ width: '80px' }}>商品图片</th>
                                    {renderSortHeader("1688 原始货源信息", "title")}
                                    {renderSortHeader("闲鱼商品 ID", "xianyu_item_id")}
                                    {renderSortHeader("当前状态", "publish_status")}
                                    {renderSortHeader("货源进价", "source_price")}
                                    {renderSortHeader("参考售价", "ref_price")}
                                    {renderSortHeader("发布时间", "publish_time")}
                                </tr>
                            </thead>
                            <tbody>
                                {items.map((item) => {
                                    const currentStatus = batchStatusMap[item.source_db_id] || item.publish_status;
                                    
                                    let statusText = '未知';
                                    let statusClass = 'pending';
                                    if (currentStatus === 'success' || currentStatus === 'done') {
                                        statusText = '已上架';
                                        statusClass = 'success';
                                    } else if (currentStatus === 'depublished') {
                                        statusText = '已下架';
                                        statusClass = 'depublished';
                                    } else if (currentStatus === 'failed') {
                                        statusText = '发布失败';
                                        statusClass = 'failed';
                                    } else if (currentStatus === 'pending' || currentStatus === 'publishing') {
                                        statusText = '同步中';
                                        statusClass = 'pending';
                                    } else if (currentStatus === 'deleting') {
                                        statusText = '删除中';
                                        statusClass = 'failed';
                                    }

                                    return (
                                        <tr key={item.publish_id} className="pub-row" onClick={() => setSelectedProduct(item)}>
                                            <td>
                                                {item.source_image ? (
                                                    <img src={item.source_image} style={{ width: '48px', height: '48px', borderRadius: '8px', objectFit: 'cover' }} referrerPolicy="no-referrer" />
                                                ) : (
                                                    <div style={{ width: '48px', height: '48px', borderRadius: '8px', background: '#F1F5F9', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94A3B8', fontSize: '0.65rem' }}>暂无图片</div>
                                                )}
                                            </td>
                                            <td>
                                                <div style={{ fontWeight: '600', color: 'var(--text-main)', maxWidth: '380px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={item.source_title}>
                                                    {item.source_title}
                                                </div>
                                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                                                    <a href={item.source_url} target="_blank" rel="noreferrer" className="hover-link" onClick={e => e.stopPropagation()} style={{ textDecoration: 'none', color: 'inherit' }}>
                                                        查看 1688 货源链接 ↗
                                                    </a>
                                                </div>
                                            </td>
                                            <td style={{ fontFamily: 'monospace', fontWeight: '700' }}>{item.xianyu_item_id || '-'}</td>
                                            <td>
                                                <span className={`badge ${statusClass}`}>
                                                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'currentColor' }}></span>
                                                    {statusText}
                                                </span>
                                            </td>
                                            <td style={{ fontWeight: '700' }}>¥{item.source_price}</td>
                                            <td style={{ fontWeight: '600' }}>¥{item.ref_price || '-'}</td>
                                            <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{item.publish_time}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            ) : (
                <div className="task-card" style={{ textAlign: 'center', padding: '100px' }}>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>📦 暂无已发布在闲鱼的商品。</p>
                    <p style={{ color: '#94A3B8', fontSize: '0.85rem', marginTop: '10px' }}>您可以先去“决策资产”库中发布选中的商品。</p>
                </div>
            )}

            {/* 分页控制 */}
            {totalPages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '15px', marginTop: '40px' }}>
                    <button className="pro-btn" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button>
                    <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>第 {page} / {totalPages} 页 (共 {total} 个商品)</span>
                    <button className="pro-btn" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</button>
                </div>
            )}

            {/* 详情模态弹窗 (点击行记录展开) */}
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

    // 移除原有滚动穿透控制，由 PublishPreviewModal 组件自身效果管控

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

    const btnStyle = { padding: '6px 14px', borderRadius: '8px', border: 'none', cursor: 'pointer', fontSize: '0.8rem', fontWeight: '600', marginTop: '8px' };

    return (
        <div>
            {status === 'done' && (
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <a href={pubResult?.published_url} target="_blank" rel="noreferrer"
                       style={{ ...btnStyle, display: 'inline-block', background: '#10B98120', color: '#10B981', textDecoration: 'none', margin: '8px 0 0 0' }}>
                        ✅ 已发布
                    </a>
                    <button style={{ ...btnStyle, background: '#F59E0B20', color: '#F59E0B', margin: '8px 0 0 0' }} onClick={doDepublish}>
                        下架
                    </button>
                </div>
            )}
            {status === 'depublished' && (
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span style={{ ...btnStyle, display: 'inline-block', background: '#F59E0B20', color: '#F59E0B', margin: '8px 0 0 0' }}>
                        ⚠️ 已下架
                    </span>
                    <button style={{ ...btnStyle, background: 'var(--primary)', color: '#fff', margin: '8px 0 0 0' }} onClick={openModal}>
                        重新上架
                    </button>
                    <button style={{ ...btnStyle, background: '#EF444420', color: '#EF4444', margin: '8px 0 0 0' }} onClick={doDelete}>
                        删除
                    </button>
                </div>
            )}
            {status === 'publishing' && (
                <span style={{ ...btnStyle, display: 'inline-block', background: '#3B82F620', color: '#3B82F6' }}>🔄 操作中...</span>
            )}
            {status === 'deleting' && (
                <span style={{ ...btnStyle, display: 'inline-block', background: '#EF444420', color: '#EF4444' }}>🔄 删除中...</span>
            )}
            {status === 'failed' && (
                <div>
                    <span style={{ fontSize: '0.75rem', color: '#EF4444' }}>❌ {pubResult?.msg || '操作失败'}</span>
                    <button style={{ ...btnStyle, background: '#EF444420', color: '#EF4444', marginLeft: '8px' }} onClick={openModal}>重试</button>
                </div>
            )}
            {status === 'idle' && (
                <button style={{ ...btnStyle, background: 'var(--primary)', color: '#fff' }} onClick={openModal}>
                    发布至闲鱼 →
                </button>
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

    return (
        <React.Fragment>
            <aside className="sidebar">
                <div className="logo-area">选品中枢 PRO</div>
                <ul className="nav-menu">
                    <li className={`nav-item ${view === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveView("dashboard")}><i className="fas fa-chart-pie"></i><span>控制台</span></li>
                    <li className={`nav-item ${view === 'tasks' ? 'active' : ''}`} onClick={() => setActiveView("tasks")}><i className="fas fa-tasks"></i><span>任务调度</span></li>
                    <li className={`nav-item ${['results', 'item_detail'].includes(view) ? 'active' : ''}`} onClick={() => setActiveView("results")}><i className="fas fa-database"></i><span>决策资产</span></li>
                    <li className={`nav-item ${view === 'published' ? 'active' : ''}`} onClick={() => setActiveView("published")}><i className="fas fa-shopping-bag"></i><span>闲鱼商品</span></li>
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
                                            disabled={batchPublishing || batchDepublishing || batchDeleting || selectedIds.length === 0} 
                                            onClick={doBatchPublish}
                                            style={{ padding: '6px 16px', fontSize: '0.8rem', marginRight: '10px' }}
                                        >
                                            {batchPublishing ? "🔄 批量发布中..." : `🚀 批量发布所选 (${selectedIds.length})`}
                                        </button>
                                        <button 
                                            className="pro-btn warn" 
                                            disabled={batchPublishing || batchDepublishing || batchDeleting || selectedIds.length === 0} 
                                            onClick={doBatchDepublish}
                                            style={{ padding: '6px 16px', fontSize: '0.8rem', backgroundColor: '#e67e22', color: '#fff', marginRight: '10px' }}
                                        >
                                            {batchDepublishing ? "🔄 批量下架中..." : `⚠️ 批量下架所选 (${selectedIds.length})`}
                                        </button>
                                        <button 
                                            className="pro-btn danger" 
                                            disabled={batchPublishing || batchDepublishing || batchDeleting || selectedIds.length === 0} 
                                            onClick={doBatchDelete}
                                            style={{ padding: '6px 16px', fontSize: '0.8rem', backgroundColor: '#e74c3c', color: '#fff' }}
                                        >
                                            {batchDeleting ? "🔄 批量删除中..." : `🗑️ 批量删除所选 (${selectedIds.length})`}
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
                            {selectedItem.sources?.length === 0 && <div className="task-card"><p>该商品暂未找到匹配的 1688 货源。</p></div>}
                            {totalPages > 1 && (<div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '15px', marginTop: '30px'}}><button className="pro-btn" disabled={sourcePage <= 1} onClick={() => setSourcePage(p => p - 1)}>上一页</button><span style={{fontSize: '0.9rem', color: 'var(--text-secondary)'}}>第 {sourcePage} / {totalPages} 页</span><button className="pro-btn" disabled={sourcePage >= totalPages} onClick={() => setSourcePage(p => p + 1)}>下一页</button></div>)}
                        </div></div> ) : view === "published" ? <PublishedManager /> : null
                }
            </main>
        </React.Fragment>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
