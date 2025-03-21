import streamlit as st
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import zipfile
import os
import tempfile
import matplotlib
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static


# 设置中文字体支持
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'Microsoft YaHei', 'SimSun']  # 优先使用的中文字体
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
matplotlib.rcParams['font.family'] = 'sans-serif'  # 使用无衬线字体

# 页面标题
st.title("地震直接经济损失评估系统")

# 创建临时目录
temp_dir = tempfile.mkdtemp()

# 1. 文件上传
st.subheader("数据上传")
uploaded_buildings = st.file_uploader("上传建筑物数据（ZIP格式）", type=["zip"])
uploaded_units = st.file_uploader("上传行政区划数据（shilZIP格式）", type=["zip"])
uploaded_price = st.file_uploader("上传重置单价表（CSV格式）", type=["csv"])
uploaded_loss_ratio = st.file_uploader("上传损失比表（CSV格式）", type=["csv"])

# 添加系数输入
st.subheader("评估参数设置")
col1, col2 = st.columns(2)
with col1:
    rho_b = st.number_input("建筑物损失扩展系数", min_value=1.0, max_value=5.0, value=2.68, step=0.01, format="%.2f", 
                          help="评估单元建筑物损失扩展到建筑物总损失的系数")
with col2:
    rho_eb = st.number_input("直接损失系数", min_value=1.0, max_value=3.0, value=1.58, step=0.01, format="%.2f",
                           help="建筑物总损失扩展到直接经济损失的系数")

if uploaded_buildings and uploaded_units and uploaded_price and uploaded_loss_ratio:
    # 2. 解压建筑物数据
    buildings_zip_path = os.path.join(temp_dir, "buildings.zip")
    with open(buildings_zip_path, "wb") as f:
        f.write(uploaded_buildings.getbuffer())
    
    buildings_dir = os.path.join(temp_dir, "buildings")
    os.makedirs(buildings_dir, exist_ok=True)
    with zipfile.ZipFile(buildings_zip_path, 'r') as zip_ref:
        zip_ref.extractall(buildings_dir)
    
    # 3. 解压行政区划数据
    units_zip_path = os.path.join(temp_dir, "units.zip")
    with open(units_zip_path, "wb") as f:
        f.write(uploaded_units.getbuffer())
    
    units_dir = os.path.join(temp_dir, "units")
    os.makedirs(units_dir, exist_ok=True)
    with zipfile.ZipFile(units_zip_path, 'r') as zip_ref:
        zip_ref.extractall(units_dir)
    
    # 4. 保存CSV文件
    price_path = os.path.join(temp_dir, "reset_price.csv")
    with open(price_path, "wb") as f:
        f.write(uploaded_price.getbuffer())
    
    ratio_path = os.path.join(temp_dir, "loss_ratio.csv")
    with open(ratio_path, "wb") as f:
        f.write(uploaded_loss_ratio.getbuffer())
    
    # 5. 查找SHP文件
    buildings_shp = None
    for root, dirs, files in os.walk(buildings_dir):
        for file in files:
            if file.endswith(".shp"):
                buildings_shp = os.path.join(root, file)
                break
        if buildings_shp:
            break
    
    units_shp = None
    for root, dirs, files in os.walk(units_dir):
        for file in files:
            if file.endswith(".shp"):
                units_shp = os.path.join(root, file)
                break
        if units_shp:
            break
    
    if buildings_shp and units_shp:
        # 6. 读取数据
        st.info("正在读取数据...")
        buildings = gpd.read_file(buildings_shp)
        units = gpd.read_file(units_shp)
        reset_price = pd.read_csv(price_path)
        loss_ratio = pd.read_csv(ratio_path)
        
        
        # 7. 显示数据预览
        st.subheader("数据预览")
        st.write("建筑物数据：")
        st.write(buildings.head())
        
        st.write("行政区划数据：")
        st.write(units.head())
        
        st.write("重置单价表：")
        st.write(reset_price.head())
        
        st.write("损失比表：")
        st.write(loss_ratio.head())
        
        # 8. 合并数据
        st.info("正在计算损失...")
        try:
            buildings = buildings.merge(reset_price, on="建筑类")
            buildings = buildings.merge(loss_ratio, on="破坏类")
            st.subheader("合并后的建筑物预览：")
            st.write(buildings.head())

            # 9. 计算损失
            buildings["OneLoss"] = (
                buildings["Area"] * 
                buildings["单价"] * 
                buildings["损失比"] / 100
            )
            unit_loss = buildings.groupby("评估区")["OneLoss"].sum().reset_index()
            
            # 10. 计算总损失 (使用用户输入的系数)
            # 不再使用硬编码的值，而是使用用户输入的值
            total_loss = unit_loss["OneLoss"].sum() * rho_b
            direct_loss = total_loss * rho_eb
            
            # 11. 可视化
            st.subheader("各评估单元损失分布")
            fig, ax = plt.subplots(figsize=(10, 6))
            bars = ax.bar(unit_loss["评估区"], unit_loss["OneLoss"])
            ax.set_xlabel("评估单元", fontsize=12)
            ax.set_ylabel("损失（万元）", fontsize=12)
            ax.set_title("各评估单元建筑物损失", fontsize=14)
            plt.xticks(rotation=45, ha='right', fontsize=10)
            plt.yticks(fontsize=10)
            plt.tight_layout()
            
            # 添加数值标签
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}',
                        ha='center', va='bottom', rotation=0, fontsize=9)
            
            st.pyplot(fig)
            
            # 12. 显示详细结果
            st.subheader("损失详情")
            st.write(unit_loss)
            
            # 13. 总损失结果
            st.subheader("总损失结果")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("建筑物总损失（万元）", f"{total_loss:.2f}")
            with col2:
                st.metric("直接经济损失（万元）", f"{direct_loss:.2f}")
            
            # 14. 提供下载结果
            csv = unit_loss.to_csv(index=False)
            st.download_button(
                label="下载损失评估结果",
                data=csv,
                file_name="地震损失评估结果.csv",
                mime="text/csv",
            )
            
            # 15. 添加交互式地图可视化
            st.subheader("受灾区域交互式地图")
            
            # 确保行政区划数据有几何信息
            if units.geometry.is_empty.all():
                st.warning("行政区划数据缺少有效的几何信息，无法生成地图")
            else:
                # 将损失数据与行政区划数据合并
                try:
                    # 确保行政区划数据中有评估区字段
                    if "评估区" not in units.columns and "TOWNNAME" in units.columns:
                        units = units.rename(columns={"TOWNNAME": "评估区"})
                    
                    # 合并损失数据到行政区划
                    units_with_loss = units.merge(unit_loss, on="评估区", how="left")
                    units_with_loss["OneLoss"] = units_with_loss["OneLoss"].fillna(0)
                    
                    # 计算地图中心点 - 优先考虑损失最严重的区域
                    # 找出损失最大的区域
                    max_loss_unit = units_with_loss.loc[units_with_loss['OneLoss'].idxmax()]
                    
                    # 使用损失最大区域的中心点作为地图中心
                    center_lat = max_loss_unit.geometry.centroid.y
                    center_lon = max_loss_unit.geometry.centroid.x
                    
                    # 创建基础地图 - 提供多个底图选项
                    # 添加天地图密钥输入（使用默认密钥）
                    tianditu_key = st.text_input("天地图API密钥（可选，已提供默认密钥）", "8bb021e9f10ebcd69223d1c7e012a797", help="默认已提供密钥，也可使用自己在天地图开发者平台申请的密钥: https://console.tianditu.gov.cn/register")
                    
                    try:
                        # 根据是否有天地图密钥选择默认底图
                        if tianditu_key:
                            # 使用天地图矢量图作为默认底图
                            m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles=None)
                            # 添加天地图矢量图作为默认图层
                            folium.TileLayer(
                                tiles=f'http://t0.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={{z}}&TILEROW={{y}}&TILECOL={{x}}&tk={tianditu_key}',
                                attr='天地图 © 国家地理信息公共服务平台 GS(2019)1719号',
                                name='天地图矢量图',
                                overlay=False
                            ).add_to(m)
                        else:
                            # 使用OpenStreetMap作为默认底图
                            m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='OpenStreetMap')
                        
                        # 添加多个底图选项
                        folium.TileLayer('CartoDB positron', name='CartoDB Positron').add_to(m)
                        folium.TileLayer('CartoDB dark_matter', name='CartoDB Dark').add_to(m)
                        folium.TileLayer('Stamen Terrain', name='Stamen Terrain').add_to(m)
                        folium.TileLayer('Stamen Toner', name='Stamen Toner').add_to(m)
                        
                        # 如果有天地图密钥，添加天地图底图选项
                        if tianditu_key:
                            # 天地图矢量图注记
                            folium.TileLayer(
                                tiles=f'http://t0.tianditu.gov.cn/cva_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cva&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={{z}}&TILEROW={{y}}&TILECOL={{x}}&tk={tianditu_key}',
                                attr='天地图 © 国家地理信息公共服务平台 GS(2019)1719号',
                                name='天地图矢量注记',
                                overlay=True
                            ).add_to(m)
                            
                            # 天地图影像图
                            folium.TileLayer(
                                tiles=f'http://t0.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={{z}}&TILEROW={{y}}&TILECOL={{x}}&tk={tianditu_key}',
                                attr='天地图 © 国家地理信息公共服务平台 GS(2019)1719号',
                                name='天地图影像图'
                            ).add_to(m)
                            
                            # 天地图影像注记
                            folium.TileLayer(
                                tiles=f'http://t0.tianditu.gov.cn/cia_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cia&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={{z}}&TILEROW={{y}}&TILECOL={{x}}&tk={tianditu_key}',
                                attr='天地图 © 国家地理信息公共服务平台 GS(2019)1719号',
                                name='天地图影像注记',
                                overlay=True
                            ).add_to(m)
                            
                            # 天地图地形图
                            folium.TileLayer(
                                tiles=f'http://t0.tianditu.gov.cn/ter_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ter&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={{z}}&TILEROW={{y}}&TILECOL={{x}}&tk={tianditu_key}',
                                attr='天地图 © 国家地理信息公共服务平台 GS(2019)1719号',
                                name='天地图地形图'
                            ).add_to(m)
                            
                            # 天地图地形注记
                            folium.TileLayer(
                                tiles=f'http://t0.tianditu.gov.cn/cta_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cta&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={{z}}&TILEROW={{y}}&TILECOL={{x}}&tk={tianditu_key}',
                                attr='天地图 © 国家地理信息公共服务平台 GS(2019)1719号',
                                name='天地图地形注记',
                                overlay=True
                            ).add_to(m)
                        
                        # 添加图层控制
                        folium.LayerControl().add_to(m)
                    except Exception as e:
                        st.warning(f"加载地图底图时出错: {e}，尝试使用备选底图")
                        # 备选方案：使用CartoDB底图
                        m = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles='CartoDB positron')
                    
                    # 根据损失程度设置颜色
                    def get_color(loss_value):
                        if loss_value <= 0:
                            return '#FFFFFF'  # 白色，无损失
                        elif loss_value < unit_loss["OneLoss"].quantile(0.25):
                            return '#FFEDA0'  # 浅黄色，轻微损失
                        elif loss_value < unit_loss["OneLoss"].quantile(0.5):
                            return '#FEB24C'  # 橙黄色，中等损失
                        elif loss_value < unit_loss["OneLoss"].quantile(0.75):
                            return '#FC4E2A'  # 橙红色，严重损失
                        else:
                            return '#B10026'  # 深红色，极重损失
                    
                    # 添加行政区划多边形
                    geo_json = folium.GeoJson(
                        units_with_loss,
                        name="受灾区域",
                        style_function=lambda feature: {
                            'fillColor': get_color(feature['properties']['OneLoss']),
                            'color': 'black',
                            'weight': 1,
                            'fillOpacity': 0.7
                        },
                        tooltip=folium.GeoJsonTooltip(
                            fields=['评估区', 'OneLoss'],
                            aliases=['评估单元: ', '损失(万元): '],
                            localize=True,
                            sticky=False,
                            labels=True,
                            style="""background-color: #F0EFEF; border: 2px solid black; border-radius: 3px; box-shadow: 3px;""",
                            max_width=800,
                        )
                    ).add_to(m)
                    
                    # 添加自动聚焦功能，确保地图显示所有受灾区域
                    # 获取所有受灾区域的边界框
                    bounds = units_with_loss.geometry.total_bounds  # 返回 [minx, miny, maxx, maxy]
                    # 将边界框转换为folium格式的边界 [[miny, minx], [maxy, maxx]]
                    sw = [bounds[1], bounds[0]]
                    ne = [bounds[3], bounds[2]]
                    # 设置地图边界以包含所有受灾区域
                    m.fit_bounds([sw, ne])
                    
                    # 添加图例
                    legend_html = '''
                    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; background-color: white; padding: 10px; border: 1px solid grey; border-radius: 5px;">
                      <p><strong>损失程度</strong></p>
                      <p><i style="background: #FFEDA0; width: 15px; height: 15px; display: inline-block;"></i> 轻微损失</p>
                      <p><i style="background: #FEB24C; width: 15px; height: 15px; display: inline-block;"></i> 中等损失</p>
                      <p><i style="background: #FC4E2A; width: 15px; height: 15px; display: inline-block;"></i> 严重损失</p>
                      <p><i style="background: #B10026; width: 15px; height: 15px; display: inline-block;"></i> 极重损失</p>
                    </div>
                    '''
                    m.get_root().html.add_child(folium.Element(legend_html))
                    
                    # 添加建筑物点位
                    if not buildings.geometry.is_empty.all():
                        # 创建建筑物点位聚类
                        marker_cluster = MarkerCluster().add_to(m)
                        
                        # 对建筑物数据进行采样，避免点位过多
                        sample_size = min(1000, len(buildings))
                        buildings_sample = buildings.sample(sample_size) if len(buildings) > sample_size else buildings
                        
                        # 添加建筑物点位
                        for idx, row in buildings_sample.iterrows():
                            # 获取建筑物中心点
                            try:
                                point = row.geometry.centroid
                                popup_text = f"建筑类型: {row['建筑类']}<br>破坏类型: {row['破坏类']}<br>损失: {row['OneLoss']:.2f}万元"
                                
                                # 根据破坏程度设置颜色
                                if row['破坏类'] == "倒塌":
                                    color = 'red'
                                elif row['破坏类'] == "部分倒塌":
                                    color = 'orange'
                                else:
                                    color = 'green'
                                                                                                                                                                                                                                                                                                
                                folium.Marker(
                                    location=[point.y, point.x],
                                    popup=folium.Popup(popup_text, max_width=300),
                                    icon=folium.Icon(color=color, icon='home')
                                ).add_to(marker_cluster)
                            except Exception as e:
                                continue
                    
                    # 显示地图
                    folium_static(m)
                    
                except Exception as e:
                    st.error(f"生成地图时出错: {e}")
            
        except Exception as e:
            st.error(f"计算过程中出错: {e}")
    else:
        st.error("未找到有效的SHP文件，请检查上传的ZIP文件")

# 添加说明信息
st.sidebar.title("使用说明")
st.sidebar.info("""
1. 上传建筑物数据（ZIP格式，包含SHP文件）
2. 上传行政区划数据（ZIP格式，包含SHP文件）
3. 上传重置单价表（CSV格式）
4. 上传损失比表（CSV格式）
5. 系统将自动计算并显示损失评估结果
6. 交互式地图将显示受灾区域分布情况
""")

st.sidebar.title("数据要求")
st.sidebar.info("""
- 建筑物数据需包含字段：建筑类、破坏类、评估区、Area
- 重置单价表需包含字段：建筑类、单价
- 损失比表需包含字段：破坏类、损失比
- 行政区划数据需包含有效的几何信息和评估区字段
""")

st.sidebar.title("地图说明")
st.sidebar.info("""
- 地图颜色表示损失程度：从浅黄色（轻微）到深红色（极重）
- 点击区域可查看详细损失信息
- 建筑物标记颜色：红色（倒塌）、橙色（部分倒塌）、绿色（未倒塌）
""")