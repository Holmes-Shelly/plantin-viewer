# 用来展示数据
import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QTreeWidget,
                            QDateTimeEdit, QCheckBox, QTreeWidgetItem,
                            QTreeWidgetItemIterator, QLineEdit, QFrame)
from PyQt6.QtCore import Qt, QDateTime, QTimer
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
import numpy as np
from datetime import datetime
import logging
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号
plt.style.use('dark_background')
plt.rcParams.update({
    'figure.facecolor': '#2b2b2b',
    'axes.facecolor': '#2b2b2b',
    'savefig.facecolor': '#2b2b2b',
})

class DataViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数据查看器")
        self.setGeometry(100, 100, 1200, 800)
        
        # 设置暗色主题样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QTreeWidget {
                background-color: #363636;
                color: #ffffff;
                border: 1px solid #555555;
            }
            QTreeWidget::item:selected {
                background-color: #4a4a4a;
            }
            QTreeWidget::item {
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 4px;
            }
            QLineEdit {
                background-color: #363636;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 2px;
            }
            QPushButton {
                background-color: #363636;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #404040;
            }
            QPushButton:pressed {
                background-color: #505050;
            }
            QLabel {
                color: #ffffff;
            }
            QDateTimeEdit {
                background-color: #363636;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 2px;
            }
        """)
        
        # 加载数据
        self.df = None
        self.loaded_months = set()  # 用于跟踪已加载的月份
        self.load_initial_data()  # 替换原来的 load_data()
        
        # 创建主布局
        main_layout = QHBoxLayout()
        
        # 左侧控制面板
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        
        # 时间选择部分
        time_group = QWidget()
        time_layout = QVBoxLayout(time_group)
        
        # 开始时间选择
        start_time_label = QLabel("开始时间:")
        start_time_label.setStyleSheet("font-size: 12pt;")  # 增大标签字体
        self.start_time_edit = QDateTimeEdit()
        self.start_time_edit.setDateTime(
            QDateTime.fromString(
                self.df.index.min().strftime("%Y-%m-%d %H:%M:%S"),
                "yyyy-MM-dd HH:mm:ss"
            )
        )
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time_edit.setCalendarPopup(True)
        self.start_time_edit.setStyleSheet("font-size: 12pt;")  # 增大时间编辑器字体
        
        # 添加开始时间的前后按钮
        start_time_buttons = QHBoxLayout()
        start_time_prev = QPushButton("←")
        start_time_next = QPushButton("→")
        start_time_prev.setFixedWidth(30)
        start_time_next.setFixedWidth(30)
        start_time_prev.clicked.connect(lambda: self.adjust_time(self.start_time_edit, -1))
        start_time_next.clicked.connect(lambda: self.adjust_time(self.start_time_edit, 1))
        start_time_buttons.addWidget(start_time_prev)
        start_time_buttons.addWidget(start_time_next)
        
        # 结束时间选择
        end_time_label = QLabel("结束时间:")
        end_time_label.setStyleSheet("font-size: 12pt;")  # 增大标签字体
        self.end_time_edit = QDateTimeEdit()
        self.end_time_edit.setDateTime(
            QDateTime.fromString(
                self.df.index.max().strftime("%Y-%m-%d %H:%M:%S"),
                "yyyy-MM-dd HH:mm:ss"
            )
        )
        self.end_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_time_edit.setCalendarPopup(True)
        self.end_time_edit.setStyleSheet("font-size: 12pt;")  # 增大时间编辑器字体
        
        # 添加结束时间的前后按钮
        end_time_buttons = QHBoxLayout()
        end_time_prev = QPushButton("←")
        end_time_next = QPushButton("→")
        end_time_prev.setFixedWidth(30)
        end_time_next.setFixedWidth(30)
        end_time_prev.clicked.connect(lambda: self.adjust_time(self.end_time_edit, -1))
        end_time_next.clicked.connect(lambda: self.adjust_time(self.end_time_edit, 1))
        end_time_buttons.addWidget(end_time_prev)
        end_time_buttons.addWidget(end_time_next)
        
        # 修改布局添加方式
        time_layout.addWidget(start_time_label)
        time_layout.addWidget(self.start_time_edit)
        time_layout.addLayout(start_time_buttons)
        time_layout.addWidget(end_time_label)
        time_layout.addWidget(self.end_time_edit)
        time_layout.addLayout(end_time_buttons)
        
        # 在数据点选择之前添加搜索框
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索标签...")
        self.search_box.textChanged.connect(self.filter_tags)
        search_layout.addWidget(self.search_box)
        
        # 数据点选择（不设置标题）
        self.tag_tree = QTreeWidget()
        self.tag_tree.setHeaderHidden(True)  # 隐藏标题
        self.tag_tree.setSelectionMode(QTreeWidget.SelectionMode.MultiSelection)
        self.populate_tag_tree()
        
        # 添加控制选项
        options_group = QWidget()
        options_layout = QHBoxLayout(options_group)
        
        # 只保留截图按钮
        self.screenshot_button = QPushButton("截图")
        self.screenshot_button.clicked.connect(self.save_screenshot)
        options_layout.addWidget(self.screenshot_button)
        
        # 修改按钮布局为网格布局
        button_layout = QVBoxLayout()  # 改为垂直布局来容纳两行按钮
        
        # 第一行按钮
        first_row = QHBoxLayout()
        update_button = QPushButton("更新图表")
        update_button.setFixedSize(100, 50)  # 高度从100改为50
        update_button.clicked.connect(self.update_plot)
        
        reset_button = QPushButton("重置选择")
        reset_button.setFixedSize(100, 50)  # 高度从100改为50
        reset_button.clicked.connect(self.reset_selection)
        
        first_row.addWidget(update_button)
        first_row.addWidget(reset_button)
        
        # 第二行按钮
        second_row = QHBoxLayout()
        save_config_button = QPushButton("保存配置")
        save_config_button.setFixedSize(100, 50)  # 高度从100改为50
        save_config_button.clicked.connect(self.save_config)
        
        load_config_button = QPushButton("加载配置")
        load_config_button.setFixedSize(100, 50)  # 高度从100改为50
        load_config_button.clicked.connect(self.load_config)
        
        second_row.addWidget(save_config_button)
        second_row.addWidget(load_config_button)
        
        # 将两行按钮添加到主按钮布局中
        button_layout.addLayout(first_row)
        button_layout.addLayout(second_row)
        
        # 在control_layout中添加按钮布局
        control_layout.addLayout(button_layout)
        
        # 添加控件到控制面板
        control_layout.addWidget(time_group)
        control_layout.addLayout(search_layout)  # 添加搜索框
        control_layout.addWidget(self.tag_tree)
        control_layout.addWidget(options_group)
        
        # 创建中间的图表区域
        plot_panel = QWidget()
        plot_layout = QVBoxLayout(plot_panel)
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        plot_layout.addWidget(self.canvas)
        
        # 创建右侧范围控制面板
        range_panel = QWidget()
        self.range_layout = QVBoxLayout(range_panel)
        range_panel.setMaximumWidth(200)  # 限制范围控制面板的宽度
        
        # ��加范围控制面板标题
        range_title = QLabel("数据范围控制")
        self.range_layout.addWidget(range_title)
        
        # 设置整体布局
        main_layout.addWidget(control_panel, 1)
        main_layout.addWidget(plot_panel, 4)
        main_layout.addWidget(range_panel, 1)
        
        # 设置中心
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # 存储范围控制器
        self.range_controls = {}
        
        # 初始绘图
        self.update_plot()
        
        # 添加树形控件选择变更信号连接
        self.tag_tree.itemSelectionChanged.connect(self.on_selection_changed)
        
        # 添加用于跟踪垂直线和数据点标注的属性
        self.vline = None
        self.data_annotations = []
        
        # 连接鼠标事件
        self.canvas.mpl_connect('button_press_event', self.on_mouse_click)
    
    def load_initial_data(self):
        """只加载最近一个月的数据"""
        print("开始加载初始数据...")
        data_files = sorted([f for f in os.listdir('.') if f.startswith('data_matrix_') and f.endswith('.parquet')])
        if not data_files:
            raise FileNotFoundError("未找到任何数据文件")
        
        # 加载最新的数据文件
        latest_file = data_files[-1]
        print(f"正在加载最新数据: {latest_file}")
        self.df = pd.read_parquet(latest_file)
        
        # 从文件名中提取月份 (data_matrix_YYYYMM.parquet)
        month = latest_file.replace('data_matrix_', '').replace('.parquet', '')
        self.loaded_months.add(month)  # 直接使用YYYYMM格式
        print(f"初始数据加载完成，数据量: {len(self.df)} 行")
    
    def load_data_for_timerange(self, start_time, end_time):
        """根据时间范围按需加载数据,最多保留两个月"""
        start_month = start_time.strftime('%Y%m')
        end_month = end_time.strftime('%Y%m')
        
        # 检查是否需要加载新数据
        months_needed = set()
        current = pd.Timestamp(start_time)
        while current <= end_time:
            month_key = current.strftime('%Y%m')
            if month_key not in self.loaded_months:
                months_needed.add(month_key)
            current += pd.offsets.MonthEnd(1)
        
        if not months_needed:
            return
        
        # 如果需要加载的月份会导致超过两个月,先删除最旧的月份
        while len(self.loaded_months) + len(months_needed) > 2:
            oldest_month = min(self.loaded_months)
            print(f"移除旧数据: {oldest_month}")
            # 找到并删除这个月的数据
            month_start = pd.Timestamp(f"{oldest_month}01")
            month_end = month_start + pd.offsets.MonthEnd(1)
            self.df = self.df[~((self.df.index >= month_start) & (self.df.index <= month_end))]
            self.loaded_months.remove(oldest_month)
        
        # 加载新的数据文件
        for month in months_needed:
            filename = f'data_matrix_{month}.parquet'
            if os.path.exists(filename):
                print(f"加载新数据: {filename}")
                new_df = pd.read_parquet(filename)
                if self.df is None:
                    self.df = new_df
                else:
                    self.df = pd.concat([self.df, new_df])
                self.loaded_months.add(month)
        
        # 只排序,不裁剪时间范围
        if self.df is not None:
            self.df.sort_index(inplace=True)
    
    def populate_tag_tree(self):
        """填充数据点树形结构"""
        # 创建前缀字典
        prefix_dict = {}
        for tag in sorted(self.df.columns.get_level_values('tag').unique()):
            # 使用'-'分割标签名，取第一部分作为前缀
            prefix = tag.split('-')[0]
            if prefix not in prefix_dict:
                prefix_dict[prefix] = []
            prefix_dict[prefix].append(tag)
        
        # 创建树形结构
        for prefix, tags in sorted(prefix_dict.items()):
            prefix_item = QTreeWidgetItem(self.tag_tree)
            prefix_item.setText(0, prefix)
            for tag in sorted(tags):
                tag_item = QTreeWidgetItem(prefix_item)
                tag_item.setText(0, tag)
    
    def get_selected_tags(self):
        """获取选中的数据点"""
        selected_tags = []
        iterator = QTreeWidgetItemIterator(self.tag_tree, QTreeWidgetItemIterator.IteratorFlag.Selected)
        while iterator.value():
            item = iterator.value()
            if item.childCount() == 0:
                selected_tags.append(item.text(0))
            iterator += 1
        return selected_tags
    
    def update_plot(self):
        # 获取选择的间范围和数据点
        start_time = self.start_time_edit.dateTime().toPyDateTime()
        end_time = self.end_time_edit.dateTime().toPyDateTime()
        
        # 检查加载需要的数据
        self.load_data_for_timerange(start_time, end_time)
        
        selected_tags = self.get_selected_tags()
        
        if not selected_tags:
            return
        
        # 清除旧图
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # 用于存储每个曲线的颜色
        colors = plt.cm.tab20(np.linspace(0, 1, len(selected_tags)))
        
        # 绘制每个选中的数据点
        for i, (tag_name, color) in enumerate(zip(selected_tags, colors)):
            # 滤数
            mask = (self.df.index >= start_time) & (self.df.index <= end_time)
            data = self.df.loc[mask, (tag_name, 'value')]
            quality = self.df.loc[mask, (tag_name, 'quality')]
            
            # 区分正常数据和异常数据
            good_quality_mask = quality == 0
            bad_quality_mask = quality != 0
            
            # 创建新的y轴
            if i == 0:
                curr_ax = ax
            else:
                curr_ax = ax.twinx()
                # 对第3个及后的轴进行偏移
                if i >= 2:
                    offset = (i-1) * 60  # 每个轴偏移60像素
                    curr_ax.spines['right'].set_position(('outward', offset))
            
            # 隐藏y轴刻度标签
            curr_ax.yaxis.set_ticks([])
            curr_ax.yaxis.set_ticklabels([])
            
            # 隐藏y轴线
            curr_ax.spines['right'].set_visible(False)
            if i == 0:
                curr_ax.spines['left'].set_visible(False)
            
            # 绘制正常数据点
            if good_quality_mask.any():
                line = curr_ax.plot(data.index[good_quality_mask], 
                                  data[good_quality_mask], 
                                  '-', linewidth=1.5, color=color)[0]
                line.set_gid(tag_name)  # 使用gid存储标签信息
            
            # 绘制异常数据点
            if bad_quality_mask.any():
                line = curr_ax.plot(data.index[bad_quality_mask], 
                                  data[bad_quality_mask], 
                                  'x', color=color, alpha=0.5)[0]
                line.set_gid(tag_name)  # 使用gid存储标签信息
            
            # 设置Y轴范围
            if tag_name in self.range_controls:
                min_edit, max_edit = self.range_controls[tag_name]
                try:
                    y_min = float(min_edit.text())
                    y_max = float(max_edit.text())
                    curr_ax.set_ylim(y_min, y_max)
                except ValueError:
                    pass
        
        # 设置网格
        ax.grid(True, color='#404040', linestyle='-', linewidth=0.5)
        
        # 设置x轴样式
        ax.tick_params(axis='x', colors='#ffffff')
        
        # 调整布局
        self.figure.tight_layout()
        self.canvas.draw()
    
    def save_screenshot(self):
        """保存当前图表截图"""
        selected_tags = self.get_selected_tags()
        if not selected_tags:
            return
            
        timestamp = datetime.now().strftime("%m%d_%H%M")
        tag_name = selected_tags[0]
        filename = f"{tag_name}_{timestamp}.png"
        
        self.figure.savefig(filename, bbox_inches='tight', dpi=300)
    
    def reset_selection(self):
        """清除所有选中的数据"""
        iterator = QTreeWidgetItemIterator(self.tag_tree)
        while iterator.value():
            item = iterator.value()
            item.setSelected(False)
            iterator += 1
        self.update_plot()
    
    def create_range_controls(self, selected_tags):
        """创建或新范围控制器"""
        # 获取颜色映射
        colors = plt.cm.tab20(np.linspace(0, 1, len(selected_tags)))
        
        # 保存前的范围值
        current_ranges = {}
        for tag, (min_edit, max_edit) in self.range_controls.items():
            current_ranges[tag] = (min_edit.text(), max_edit.text())
        
        # 清除现有的范围控制器
        for i in reversed(range(self.range_layout.count())):
            widget = self.range_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        self.range_controls.clear()
        
        # 为每个选中的数据点创建范围控制器
        for i, tag in enumerate(selected_tags):
            # 创建框
            group = QWidget()
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(5)
            group_layout.setContentsMargins(5, 5, 5, 5)
            
            # 添加标签并设置颜色
            label = QLabel(tag)
            color = colors[i]
            # 将RGB颜色值（0-1）转换为十六进制颜色代码
            hex_color = "#{:02x}{:02x}{:02x}".format(
                int(color[0] * 255),
                int(color[1] * 255),
                int(color[2] * 255)
            )
            label.setStyleSheet(f"color: {hex_color}")
            group_layout.addWidget(label)
            
            # 创建范围输入布局
            range_widget = QWidget()
            range_layout = QHBoxLayout(range_widget)
            range_layout.setSpacing(2)
            range_layout.setContentsMargins(0, 0, 0, 0)
            
            # 创建最小值和最大值输入框
            min_label = QLabel("最小:")
            max_label = QLabel("最大:")
            min_edit = QLineEdit()
            max_edit = QLineEdit()
            
            # 设置输入框固定宽度
            min_edit.setFixedWidth(60)
            max_edit.setFixedWidth(60)
            
            # 如果有保存的范围值就使用它，否则使用默认值
            if tag in current_ranges:
                min_val, max_val = current_ranges[tag]
                min_edit.setText(min_val)
                max_edit.setText(max_val)
            else:
                # 设置默认值
                data = self.df[tag]['value']
                min_val = data.min()
                max_val = data.max()
                min_edit.setText(f"{min_val:.2f}")
                max_edit.setText(f"{max_val:.2f}")
            
            # 添加到布局
            range_layout.addWidget(min_label)
            range_layout.addWidget(min_edit)
            range_layout.addWidget(max_label)
            range_layout.addWidget(max_edit)
            
            group_layout.addWidget(range_widget)
            
            # 存储控制器
            self.range_controls[tag] = (min_edit, max_edit)
            
            # 添加更细的分隔线
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFixedHeight(1)
            group_layout.addWidget(line)
            
            # 添加到布局
            self.range_layout.addWidget(group)
            
            # 不再直接连接信号到update_plot
            # 范围的更新将通过"更新图表"按钮触发

    def on_selection_changed(self):
        """当树控件的选择发生变化时调用"""
        selected_tags = self.get_selected_tags()
        self.create_range_controls(selected_tags)
    
    def on_mouse_click(self, event):
        """处理鼠标点击事件"""
        if event.button == 3 and event.inaxes:  # 鼠标右键
            # 清除之前的垂直线和标注
            if self.vline:
                self.vline.remove()
            for ann in self.data_annotations:
                ann.remove()
            self.data_annotations = []
            
            # 绘制新的垂直线
            ymin, ymax = event.inaxes.get_ylim()
            self.vline = event.inaxes.plot([event.xdata, event.xdata], 
                                          [ymin, ymax], 
                                          '--', 
                                          color='white', 
                                          alpha=0.5)[0]
            
            # 获取点击时间
            click_time = pd.Timestamp(event.xdata, unit='D')
            
            # 获取当前显示的所有曲线
            for ax in self.figure.axes:
                for line in ax.lines:
                    if line.get_gid() is not None:  # 检查是否有标签信息
                        # 找到最接近点击位置的数点
                        xdata = line.get_xdata()
                        ydata = line.get_ydata()
                        
                        # 将时间换为数值类型
                        xdata_num = np.array([pd.Timestamp(x).timestamp() for x in xdata])
                        
                        # 找到最接近的时间点
                        idx = np.abs(xdata_num - click_time.timestamp()).argmin()
                        x = xdata[idx]
                        y = ydata[idx]
                        
                        # 检查时间差是否在20秒内
                        time_diff = abs(pd.Timestamp(x) - click_time).total_seconds()
                        if time_diff <= 20:  # 只有在20秒内的点才显示标注
                            # 创建数据点标注
                            timestamp = pd.Timestamp(x).strftime('%Y-%m-%d %H:%M:%S')
                            annotation = ax.annotate(
                                f'{line.get_gid()}\n{y:.2f}\n{timestamp}',
                                xy=(x, y),
                                xytext=(10, 10),
                                textcoords='offset points',
                                bbox=dict(boxstyle='round,pad=0.5', fc='#363636', ec='#555555', alpha=0.8),
                                color=line.get_color(),
                                fontsize=8
                            )
                            self.data_annotations.append(annotation)
            
            # 更新图表
            self.canvas.draw()
    
    def adjust_time(self, time_edit, direction):
        """调整时间
        Args:
            time_edit: QDateTimeEdit对象
            direction: 1表示向后，-1表示向前
        """
        current_time = time_edit.dateTime()
        # 调整1小时
        adjusted_time = current_time.addSecs(direction * 3600)
        time_edit.setDateTime(adjusted_time)
    
    def filter_tags(self, text):
        """根据搜索文本过滤标签，支持*作为通配符"""
        # 将搜索文本转换为正则表达式模式
        if text:
            # 将*替换为正则表���式的.*，并对其他特殊字符进行转义
            import re
            pattern = text.lower()
            # 转义正则表达式特殊字符，但保留*号
            pattern = ''.join(['.' if c == '*' else re.escape(c) for c in pattern])
            try:
                regex = re.compile(pattern)
            except re.error:
                # 如果正则表达式无效，则进行普通文本匹配
                regex = None
        
        # 遍历所有项目
        root = self.tag_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            group_visible = False
            
            # 检每个子项
            for j in range(group_item.childCount()):
                child_item = group_item.child(j)
                child_text = child_item.text(0).lower()
                
                # 如果搜索文本为空或者文本匹配，则显示项目
                if not text:
                    should_show = True
                elif regex:
                    should_show = bool(regex.search(child_text))
                else:
                    # 降级为简单的文本包含匹配
                    should_show = text.lower() in child_text
                    
                child_item.setHidden(not should_show)
                group_visible = group_visible or should_show
            
            # 如果组内有可见项目，则显示组并展开
            group_item.setHidden(not group_visible)
            if group_visible and text:  # 只在有搜索文本且组可见时展开
                group_item.setExpanded(True)
            elif not text:  # 当搜索框为空时折叠所有组
                group_item.setExpanded(False)

    def save_config(self):
        """保存当前配置到文件"""
        import configparser
        from PyQt6.QtWidgets import QFileDialog
        import time
        
        # 获取当前选中的标签
        selected_tags = self.get_selected_tags()
        if not selected_tags:
            return
        
        # 创建配置对象
        config = configparser.ConfigParser()
        
        # 保存标签列表
        config['Tags'] = {
            'tag_list': ','.join(selected_tags)
        }
        
        # 保存范围设置
        ranges = {}
        for tag, (min_edit, max_edit) in self.range_controls.items():
            if tag in selected_tags:  # 只保存选中标签的范围
                ranges[f"{tag}_range"] = f"{min_edit.text()},{max_edit.text()}"
        config['Ranges'] = ranges
        
        # 生成默认文件名（使用时间戳）
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        default_filename = f"tag_config_{timestamp}.ini"
        
        # 打开保存文件对话框
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "保存配置文件",
            default_filename,  # 默认文件名
            "配置文件 (*.ini);;所有文件 (*.*)"
        )
        
        if filename:  # 如果用户选择了文件名
            # 确保文件名.ini结尾
            if not filename.endswith('.ini'):
                filename += '.ini'
            
            # 保存到文件
            with open(filename, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
            
            print(f"配置已保存到: {filename}")

    def load_config(self):
        """从文件加载配置"""
        import configparser
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtCore import QTimer
        
        # 打开文件选择对话框
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "选择配置文件",
            "",
            "配置文件 (*.ini);;所有文件 (*.*)"
        )
        
        if not filename:
            return
        
        # 读取配置文件
        config = configparser.ConfigParser()
        config.read(filename, encoding='utf-8')
        
        # 首先清除当前选择
        self.reset_selection()
        
        # 获取并设置标签
        if 'Tags' in config and 'tag_list' in config['Tags']:
            tags = config['Tags']['tag_list'].split(',')
            
            # 选中这些标签
            iterator = QTreeWidgetItemIterator(self.tag_tree)
            while iterator.value():
                item = iterator.value()
                if item.childCount() == 0 and item.text(0) in tags:
                    item.setSelected(True)
                iterator += 1
        
        def set_ranges():
            # 设置范围值
            if 'Ranges' in config:
                for key, value in config['Ranges'].items():
                    tag = key.replace('_range', '').lower()
                    
                    # 在range_controls中查找匹配的标签（不区分大小写）
                    matching_tag = None
                    for control_tag in self.range_controls:
                        if control_tag.lower() == tag:
                            matching_tag = control_tag
                            break
                    
                    if matching_tag:
                        min_val, max_val = value.split(',')
                        min_edit, max_edit = self.range_controls[matching_tag]
                        min_edit.setText(min_val.strip())
                        max_edit.setText(max_val.strip())
            
            # 更新图表
            self.update_plot()
        
        # 使用定时器延迟设置范围值
        QTimer.singleShot(100, set_ranges)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = DataViewer()
    viewer.show()
    sys.exit(app.exec()) 