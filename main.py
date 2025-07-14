import streamlit as st
import pandas as pd
import json
import networkx as nx
from streamlit_echarts import st_echarts
import time
import uuid

# 页面设置为宽屏布局
st.set_page_config(layout="wide")

st.title("🚀 德融宝知识图谱 动画路径聚焦")

# --- 函数定义 ---

def nx_to_echarts(G, path_highlight=None, current_node=None):
    """
    转换NetworkX图为ECharts格式。
    支持路径高亮和当前动画节点的特殊高亮。
    """
    echarts_nodes = []
    echarts_links = []
    
    color_map = {
        'SensorProduct': '#FFA500',    # 橙色
        'ProductCategory': '#00BFFF', # 深天蓝
        'Company': '#32CD32',         # 酸橙绿
        'Application': '#9370DB',     # 中紫色
        'Property': '#D2691E',        # 巧克力色
        'Other': '#CCCCCC'            # 灰色
    }
    
    for i, (node, data) in enumerate(G.nodes(data=True)):
        style = {}
        node_type = data.get('type', 'Other')
        base_color = color_map.get(node_type, '#CCCCCC')
        
        if current_node and node == current_node:
            style = {
                'color': '#ff1744',
                'borderColor': '#fff',
                'borderWidth': 4,
                'shadowBlur': 20,
                'shadowColor': '#ff1744'
            }
            symbol_size = 120
        elif path_highlight and node in path_highlight:
            style = {
                'color': '#ff5722',
                'borderColor': '#fff',
                'borderWidth': 2
            }
            symbol_size = 85
        else:
            style = {
                'color': base_color,
                'opacity': 0.3 if path_highlight else 1.0
            }
            symbol_size = 30 if node_type == "Property" else 40
        
        echarts_nodes.append({
            "name": node,
            "symbolSize": symbol_size,
            "itemStyle": style,
            "value": node_type,
            "emphasis": {"focus": "adjacency", "scale": 1.2}
        })

    for u, v, d in G.edges(data=True):
        line_style = {"color": "#ddd", "width": 1, "opacity": 0.3 if path_highlight else 1.0}
        
        if path_highlight:
            try:
                u_idx = path_highlight.index(u)
                v_idx = path_highlight.index(v)
                if abs(u_idx - v_idx) == 1:
                    line_style = {
                        "color": "#ff5722", 
                        "width": 5,
                        "opacity": 1.0,
                        "shadowBlur": 8,
                        "shadowColor": "#ff5722"
                    }
            except ValueError:
                pass
        
        echarts_links.append({
            "source": u,
            "target": v,
            "label": {"show": True, "formatter": d.get('relation', ''), "fontSize": 10, "color": "#666"},
            "lineStyle": line_style
        })
    
    return echarts_nodes, echarts_links

def create_graph_option(echarts_nodes, echarts_links, animation_duration=2000, is_animating=False, step=0, max_steps=None, path_to_animate=None):
    """
    创建ECharts图表的基础配置，修复动画效果
    """
    force_config = {
        "repulsion": 800 if not is_animating else 600,
        "edgeLength": 300 if not is_animating else 250,
        "gravity": 0.15 if not is_animating else 0.3,
        "layoutAnimation": True,
        "friction": 0.8
    }

    # 修复：直接修改节点属性而不是重新赋值
    if is_animating and path_to_animate:
        for i, node in enumerate(echarts_nodes):
            node_name = node["name"]
            if node_name in path_to_animate:
                node_step = path_to_animate.index(node_name)
                if node_step <= step:
                    # 已经到达的节点保持高亮
                    node['itemStyle']['opacity'] = 1.0
                    if node_name == path_to_animate[step]:
                        # 当前节点特殊高亮
                        node['symbolSize'] = 120
                    else:
                        # 路径上其他节点
                        node['symbolSize'] = 85
                else:
                    # 未到达的路径节点
                    node['itemStyle']['opacity'] = 0.5
                    node['symbolSize'] = 60
            else:
                # 非路径节点
                node['itemStyle']['opacity'] = 0.2
                node['symbolSize'] = 30

    return {
        "animationDurationUpdate": animation_duration,
        "animationEasingUpdate": "cubicInOut",
        "tooltip": {"show": True, "formatter": "{b}<br/>类型: {c}"},
        "series": [{
            "type": "graph",
            "layout": "force",
            "data": echarts_nodes,
            "links": echarts_links,
            "roam": True,
            "label": {"show": True, "position": "right", "formatter": "{b}", "fontSize": 12},
            "edgeSymbol": ['circle', 'arrow'],
            "edgeSymbolSize": [4, 12],
            "force": force_config,
            "scaleLimit": {"min": 0.1, "max": 10},
            "emphasis": {"focus": "adjacency"}
        }]
    }

# --- 主应用流程 ---

uploaded_file = st.file_uploader("上传一个包含节点信息的 Excel 文件", type=["xlsx"])

if uploaded_file:
    # --- 1. 数据加载与图谱构建 ---
    df = pd.read_excel(uploaded_file, sheet_name=0)
    G = nx.DiGraph()
    
    for _, row in df.iterrows():
        p = row.get('产品名称')
        c = row.get('子分类')
        m = row.get('企业名称')
        a = row.get('应用')
        if pd.notna(p): G.add_node(p, type='SensorProduct')
        if pd.notna(c):
            G.add_node(c, type='ProductCategory')
            if pd.notna(p): G.add_edge(p, c, relation='属于')
        if pd.notna(m):
            G.add_node(m, type='Company')
            if pd.notna(p): G.add_edge(p, m, relation='由...生产')
        if pd.notna(a):
            G.add_node(a, type='Application')
            if pd.notna(p): G.add_edge(p, a, relation='适用于')
        try:
            if pd.notna(row.get('产品详细属性')):
                props = json.loads(row.get('产品详细属性', '{}'))
                props = props.get("属性", {})
                for k, v in props.items():
                    node = f"{k}={v}"
                    G.add_node(node, type='Property')
                    if pd.notna(p): G.add_edge(p, node, relation='具有属性')
        except Exception as e:
            st.warning(f"属性解析失败: {e}")

    # --- 2. UI 控件与状态初始化 ---
    st.subheader("📊 知识图谱统计")
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("节点数量", len(G.nodes()))
    with col2: st.metric("边数量", len(G.edges()))
    with col3: st.metric("连通分量", nx.number_weakly_connected_components(G))

    st.subheader("🔍 路径查找与动画控制")
    col1, col2 = st.columns(2)
    all_nodes = sorted(list(G.nodes()))
    with col1:
        source_node = st.selectbox("选择起点（源节点）", options=all_nodes, index=0 if all_nodes else -1)
    with col2:
        keyword = st.text_input("输入目标关键词（模糊搜索）", "")
        matched_targets = [n for n in all_nodes if keyword and keyword.lower() in n.lower()]
        target_node = None
        if matched_targets:
            target_node = st.selectbox(f"选择目标节点 (匹配到 {len(matched_targets)} 个)", matched_targets)
        elif keyword:
            st.warning("未找到匹配的目标节点")

    max_hops = st.slider("最大跳数（路径长度限制）", 2, 10, 6)

    # 初始化会话状态
    if 'matched_paths' not in st.session_state: st.session_state.matched_paths = []
    if 'is_animating' not in st.session_state: st.session_state.is_animating = False
    if 'animation_step' not in st.session_state: st.session_state.animation_step = 0
    if 'chart_key' not in st.session_state: st.session_state.chart_key = f"kg_{uuid.uuid4()}"

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔍 查找路径", disabled=st.session_state.is_animating):
            st.session_state.matched_paths = []
            if source_node and target_node:
                try:
                    paths = list(nx.all_simple_paths(G, source=source_node, target=target_node, cutoff=max_hops-1))
                    if paths:
                        st.session_state.matched_paths = sorted(paths, key=len)
                        st.success(f"找到 {len(paths)} 条路径！将默认播放最短路径。")
                        st.session_state.chart_key = f"kg_path_{uuid.uuid4()}"
                    else:
                        st.warning("未找到符合条件的路径")
                except nx.NodeNotFound as e:
                    st.error(f"节点未找到: {e}")
            else:
                st.warning("请选择有效的起点和目标节点")
    
    with col2:
        if st.button("🎬 播放路径动画", disabled=not st.session_state.matched_paths or st.session_state.is_animating):
            st.session_state.is_animating = True
            st.session_state.animation_step = 0
            st.session_state.chart_key = f"kg_anim_{uuid.uuid4()}" 
            st.rerun()

    with col3:
        speed_mapping = {"慢速": 1.5, "中速": 1.0, "快速": 0.5}
        speed_choice = st.selectbox("动画速度", speed_mapping.keys(), index=1, disabled=st.session_state.is_animating)
        animation_delay = speed_mapping[speed_choice]

    # --- 3. 路径详情显示 ---
    if st.session_state.matched_paths:
        st.subheader("📋 找到的路径")
        for i, path in enumerate(st.session_state.matched_paths):
            is_expanded = (i == 0)
            with st.expander(f"路径 {i+1} (长度: {len(path)}) {'- 动画将播放此路径' if i == 0 else ''}", expanded=is_expanded):
                st.write(" → ".join(f"`{node}`" for node in path))
    
    # --- 4. 修复后的图表渲染与动画逻辑 ---
    st.subheader("🌐 知识图谱可视化")
    progress_placeholder = st.empty()
    chart_container = st.container()

    path_to_animate = st.session_state.matched_paths[0] if st.session_state.matched_paths else None

    if st.session_state.is_animating and path_to_animate:
        step = st.session_state.animation_step
        
        if step < len(path_to_animate):
            current_node = path_to_animate[step]
            progress_placeholder.info(f"🎬 动画播放中... 步骤 {step+1}/{len(path_to_animate)}: **{current_node}**")
            
            # 更新chart_key以强制重新渲染
            st.session_state.chart_key = f"kg_anim_{step}_{uuid.uuid4()}"
            
            nodes, links = nx_to_echarts(G, path_highlight=path_to_animate, current_node=current_node)
            option = create_graph_option(nodes, links, 
                                       animation_duration=1000, 
                                       is_animating=True, 
                                       step=step, 
                                       max_steps=len(path_to_animate) - 1, 
                                       path_to_animate=path_to_animate)
            
            with chart_container:
                st_echarts(option, height="700px", key=st.session_state.chart_key)
            
            st.session_state.animation_step += 1
            time.sleep(animation_delay)
            st.rerun()

        else:
            progress_placeholder.success("🎉 动画播放完成！完整路径已高亮显示。")
            nodes, links = nx_to_echarts(G, path_highlight=path_to_animate, current_node=None)
            option = create_graph_option(nodes, links, is_animating=False, path_to_animate=path_to_animate)
            
            with chart_container:
                st_echarts(option, height="700px", key=st.session_state.chart_key)
            
            st.session_state.is_animating = False
            st.session_state.animation_step = 0
            
    else:
        # 静态图表显示
        if path_to_animate:
            progress_placeholder.info("路径已找到。点击"/播放路径动画/"开始播放。")
            nodes, links = nx_to_echarts(G, path_highlight=path_to_animate)
        else:
            progress_placeholder.info("上传文件、选择起终点并查找路径以开始。")
            nodes, links = nx_to_echarts(G)
        
        option = create_graph_option(nodes, links, is_animating=False)
        with chart_container:
            st_echarts(option, height="700px", key=st.session_state.chart_key)

    # --- 5. 使用说明 ---
    with st.expander("📖 使用说明与问题修复"):
        st.markdown("""
        **已修复的问题:**
        1. **节点属性修改问题**: 修复了直接修改节点属性的逻辑，确保动画时节点样式正确更新
        2. **动画刷新问题**: 每个动画步骤都生成新的chart_key，强制图表重新渲染
        3. **动画速度优化**: 调整了动画延迟时间，使效果更流畅
        4. **节点显示逻辑**: 改进了动画过程中节点的透明度和大小变化逻辑
        
        **动画效果说明:**
        - 当前节点会显示为红色大节点，带有阴影效果
        - 路径上已经过的节点保持橙色高亮
        - 未到达的路径节点显示为半透明
        - 非路径节点透明度降低，突出路径显示
        """)

else:
    st.info("💡 请上传 Excel 文件以开始知识图谱可视化。")
    with st.expander("📝查看 Excel 文件格式示例"):
        sample_data = {'产品名称': ['...'], '子分类': ['...'], '企业名称': ['...'], '应用': ['...'], '产品详细属性': ['...']}
        st.dataframe(pd.DataFrame(sample_data))
