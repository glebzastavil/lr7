import sys, json, os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import math
import random
from datetime import datetime

# Кастомный QGraphicsView — передаёт координаты клика
class CustomGraphicsView(QGraphicsView):
    scene_clicked = pyqtSignal(float, float)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.scene_clicked.emit(
                self.mapToScene(event.pos()).x(), 
                self.mapToScene(event.pos()).y()
            )
        super().mousePressEvent(event)

# Графический элемент пути (точка + номер)
class PathPointItem(QGraphicsEllipseItem):
    def __init__(self, x, y, index, parent=None):
        super().__init__(-8, -8, 16, 16, parent)
        self.setPos(x, y)
        self.setBrush(QColor(255, 165, 0))
        self.setPen(QPen(Qt.black, 2))
        self.setZValue(10)
        self.index = index
        
        self.label = QGraphicsSimpleTextItem(str(index), parent)
        self.label.setPos(x + 10, y - 10)
        self.label.setBrush(Qt.black)
        self.label.setZValue(11)

# Диалог для отображения журнала событий
class EventLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Журнал событий")
        self.resize(800, 500)
        
        layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Время начала обучения", 
            "Номер эпохи", 
            "Сохранение модели",
            "Загруженность перекрестка"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        
        self.setLayout(layout)
        
    def update_data(self, events):
        self.table.setRowCount(len(events))
        for row, event in enumerate(events):
            self.table.setItem(row, 0, QTableWidgetItem(event['time']))
            self.table.setItem(row, 1, QTableWidgetItem(str(event['epoch'])))
            self.table.setItem(row, 2, QTableWidgetItem(event['model_saved']))
            self.table.setItem(row, 3, QTableWidgetItem(f"{event['load_level']:.2f}"))

# Диалог для отображения процесса обучения
class TrainingProcessDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Процесс обучения")
        self.resize(700, 500)
        
        layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([
            "Эпоха", 
            "Потери (Loss)", 
            "Точность (Accuracy)"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        
        self.setLayout(layout)
        
    def update_data(self, training_history):
        self.table.setRowCount(len(training_history))
        for row, data in enumerate(training_history):
            self.table.setItem(row, 0, QTableWidgetItem(str(data['epoch'])))
            self.table.setItem(row, 1, QTableWidgetItem(f"{data['loss']:.4f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{data['accuracy']:.2f}%"))

# Главный класс приложения
class TrafficEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Интеллектуальная система преображения перекрестков")
        self.resize(1200, 700)
        
        icon_path = os.path.join(os.path.dirname(__file__), "GCicon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.objects = []
        self.selected_obj = None
        self.current_tool = None
        self.current_sign_type = 'start'
        
        self.path_points = []
        self.path_line_items = []
        self.path_point_items = []
        
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self._anim_step)
        self.anim_index = 0
        self.anim_progress = 0.0
        self.anim_speed = 2.0
        self.anim_car = None
        self.anim_running = False
        
        # Данные для обучения
        self.current_epoch = 0
        self.training_history = []
        self.event_log = []
        
        self.media_dir = self.find_media_dir()
        self.pixmaps = self.load_pixmaps()
        self.init_ui()

    def find_media_dir(self):
        for p in ["media", "resources/media", "../media"]:
            if os.path.exists(p):
                return p
        return "media"

    def load_pixmaps(self):
        pixmaps = {}
        files = {
            'blue_up': 'BCvertical.png', 'blue_down': 'BCbottom.png',
            'blue_left': 'BCleft.png', 'blue_right': 'BCright.png',
            'red_up': 'Cvertical.png', 'red_down': 'Cbottom.png',
            'red_left': 'Cleft.png', 'red_right': 'Cright.png',
            'traffic_green': 'TLgreen.png', 'traffic_red': 'TLred.png',
            'traffic_yellow': 'TLyellow.png', 'pedestrian': 'Pedestrain.png',
            'crossroads': 'Rcrossroads.png', 'road': 'Rvertical.png',
            'start': 'Start.png', 'stop': 'Stop.png', 'block': 'Block.png',
            'zebra_h': 'Zhorizontal.png', 'zebra_v': 'Zvertical.png',
        }
        for key, filename in files.items():
            path = os.path.join(self.media_dir, filename)
            pixmaps[key] = QPixmap(path) if os.path.exists(path) else self._fallback_pixmap()
        return pixmaps

    def _fallback_pixmap(self):
        p = QPixmap(40, 40)
        p.fill(Qt.gray)
        return p

    def init_ui(self):
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 2000, 1500)
        self.scene.setBackgroundBrush(QColor(200, 200, 200))
        self.draw_grid()
        
        self.view = CustomGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.scene_clicked.connect(self.on_scene_click)
        self.setCentralWidget(self.view)
        
        self.create_toolbar()
        self.create_properties_panel()
        self.statusBar().showMessage(
            "Готов. Выберите инструмент и кликните на сцене. "
            "Инструмент «Путь» — задаёт маршрут для машинки."
        )

    def draw_grid(self):
        pen = QPen(QColor(180, 180, 180), 1, Qt.DotLine)
        for x in range(0, 2000, 50):
            self.scene.addLine(x, 0, x, 1500, pen)
        for y in range(0, 1500, 50):
            self.scene.addLine(0, y, 2000, y, pen)

    def create_toolbar(self):
        toolbar = QToolBar("Инструменты")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(48, 48))
        toolbar.setStyleSheet("QToolBar{ spacing: 10px; padding: 5px;}")
        self.addToolBar(toolbar)
        
        for name, tool in [
            ("Автомобиль", "car"), ("Пешеход", "pedestrian"), 
            ("Светофор", "traffic"), ("Перекресток", "crossroads"),
            ("Дорога", "road"), ("Пешеходный переход", "zebra")
        ]:
            action = QAction(name, self)
            action.triggered.connect(lambda checked, t=tool: self.set_tool(t))
            toolbar.addAction(action)
            
        action_path = QAction("Путь", self)
        action_path.setCheckable(True)
        action_path.triggered.connect(lambda checked: self.set_tool('path' if checked else None))
        toolbar.addAction(action_path)
        
        signs_menu = QMenu()
        for name, stype in [("Старт", "start"), ("Стоп", "stop"), ("Блок", "block")]:
            action = QAction(name, self)
            action.triggered.connect(lambda checked, s=stype: self.set_sign_tool(s))
            signs_menu.addAction(action)
        signs_action = QAction("Знаки", self)
        signs_action.setMenu(signs_menu)
        toolbar.addAction(signs_action)
        toolbar.addSeparator()
        
        # Кнопки обучения
        action_train_start = QAction("🎓 Начать обучение", self)
        action_train_start.triggered.connect(self.start_training)
        toolbar.addAction(action_train_start)
        
        action_train_process = QAction("📊 Процесс обучения", self)
        action_train_process.triggered.connect(self.show_training_process)
        toolbar.addAction(action_train_process)
        
        action_event_log = QAction("📋 Журнал событий", self)
        action_event_log.triggered.connect(self.show_event_log)
        toolbar.addAction(action_event_log)
        toolbar.addSeparator()
        
        self.btn_anim_start = QAction("▶ Запустить анимацию", self)
        self.btn_anim_start.triggered.connect(self.start_animation)
        toolbar.addAction(self.btn_anim_start)
        
        self.btn_anim_stop = QAction("■ Остановить анимацию", self)
        self.btn_anim_stop.triggered.connect(self.stop_animation)
        toolbar.addAction(self.btn_anim_stop)
        toolbar.addSeparator()
        
        action_clear_path = QAction("Очистить путь", self)
        action_clear_path.triggered.connect(self.clear_path)
        toolbar.addAction(action_clear_path)
        toolbar.addSeparator()
        
        for name, func in [("Сохранить", self.save_project), ("Загрузить", self.load_project)]:
            action = QAction(name, self)
            action.triggered.connect(func)
            toolbar.addAction(action)

    def set_sign_tool(self, sign_type):
        self.current_tool = 'sign'
        self.current_sign_type = sign_type
        self.statusBar().showMessage(f"Инструмент: Знак {sign_type}")

    def set_tool(self, tool):
        self.current_tool = tool
        self.statusBar().showMessage(f"Инструмент: {tool or 'нет'}")

    def create_properties_panel(self):
        dock = QDockWidget("Свойства объекта", self)
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.lbl_info = QLabel("Объект не выбран")
        self.lbl_info.setStyleSheet("background:#f0f0f0; padding: 5px;")
        layout.addWidget(self.lbl_info)
        
        group_anim = QGroupBox("Анимация движения")
        form_anim = QFormLayout()
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.5, 20.0)
        self.spin_speed.setSingleStep(0.5)
        self.spin_speed.setValue(2.0)
        self.spin_speed.setSuffix(" px/тик")
        form_anim.addRow("Скорость:", self.spin_speed)
        
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(5, 100)
        self.spin_interval.setValue(16)
        self.spin_interval.setSuffix(" мс")
        form_anim.addRow("Интервал таймера:", self.spin_interval)
        group_anim.setLayout(form_anim)
        layout.addWidget(group_anim)
        
        group_scale = QGroupBox("Масштаб объекта")
        form_scale = QFormLayout()
        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(0.25, 3.0)
        self.spin_scale.setSingleStep(0.1)
        self.spin_scale.setValue(1.0)
        self.spin_scale.valueChanged.connect(self.on_property_changed)
        form_scale.addRow("Размер:", self.spin_scale)
        group_scale.setLayout(form_scale)
        layout.addWidget(group_scale)
        
        group_rotate = QGroupBox("Поворот объекта")
        form_rotate = QFormLayout()
        self.spin_rotation = QSpinBox()
        self.spin_rotation.setRange(0, 360)
        self.spin_rotation.setSingleStep(90)
        self.spin_rotation.setValue(0)
        self.spin_rotation.setSuffix("°")
        self.spin_rotation.valueChanged.connect(self.on_property_changed)
        form_rotate.addRow("Угол поворота:", self.spin_rotation)
        
        btn_left = QPushButton("Повернуть влево (-90°)")
        btn_left.clicked.connect(self.rotate_left)
        form_rotate.addRow(btn_left)
        
        btn_right = QPushButton("Повернуть вправо (+90°)")
        btn_right.clicked.connect(self.rotate_right)
        form_rotate.addRow(btn_right)
        group_rotate.setLayout(form_rotate)
        layout.addWidget(group_rotate)
        
        self.group_car = QGroupBox("Параметры машины")
        form_car = QFormLayout()
        self.combo_car_color = QComboBox()
        self.combo_car_color.addItems(['blue', 'red'])
        self.combo_car_color.currentTextChanged.connect(self.on_property_changed)
        form_car.addRow("Цвет:", self.combo_car_color)
        
        self.combo_car_direction = QComboBox()
        self.combo_car_direction.addItems(['up', 'down', 'left', 'right'])
        self.combo_car_direction.currentTextChanged.connect(self.on_property_changed)
        form_car.addRow("Направление:", self.combo_car_direction)
        self.group_car.setLayout(form_car)
        layout.addWidget(self.group_car)
        
        self.group_traffic = QGroupBox("Параметры светофора")
        form_traffic = QFormLayout()
        self.combo_signal = QComboBox()
        self.combo_signal.addItems(['red', 'yellow', 'green'])
        self.combo_signal.currentTextChanged.connect(self.on_property_changed)
        form_traffic.addRow("Сигнал:", self.combo_signal)
        self.group_traffic.setLayout(form_traffic)
        layout.addWidget(self.group_traffic)
        
        self.group_zebra = QGroupBox("Параметры перехода")
        form_zebra = QFormLayout()
        self.combo_zebra_orientation = QComboBox()
        self.combo_zebra_orientation.addItems(['horizontal', 'vertical'])
        self.combo_zebra_orientation.currentTextChanged.connect(self.on_property_changed)
        form_zebra.addRow("Ориентация:", self.combo_zebra_orientation)
        self.group_zebra.setLayout(form_zebra)
        layout.addWidget(self.group_zebra)
        
        btn_delete = QPushButton("Удалить объект")
        btn_delete.clicked.connect(self.delete_object)
        layout.addWidget(btn_delete)
        
        widget.setLayout(layout)
        dock.setWidget(widget)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def rotate_left(self):
        if self.selected_obj:
            self.spin_rotation.setValue((self.spin_rotation.value() - 90) % 360)

    def rotate_right(self):
        if self.selected_obj:
            self.spin_rotation.setValue((self.spin_rotation.value() + 90) % 360)

    def on_property_changed(self):
        if not self.selected_obj:
            return
        obj = self.selected_obj
        obj['scale'] = self.spin_scale.value()
        obj['rotation'] = self.spin_rotation.value()
        obj['item'].setScale(obj['scale'])
        obj['item'].setRotation(obj['rotation'])
        
        if obj['type'] == 'car':
            obj['color'] = self.combo_car_color.currentText()
            obj['direction'] = self.combo_car_direction.currentText()
            obj['item'].setPixmap(
                self._get_pixmap(obj['color'] + '_' + obj['direction'], 'blue_up')
            )
        elif obj['type'] == 'traffic':
            obj['signal'] = self.combo_signal.currentText()
            obj['item'].setPixmap(
                self._get_pixmap('traffic_' + obj['signal'], 'traffic_green')
            )
        elif obj['type'] == 'zebra':
            obj['orientation'] = self.combo_zebra_orientation.currentText()
            key = 'zebra_v' if obj['orientation'] == 'vertical' else 'zebra_h'
            obj['item'].setPixmap(self.pixmaps.get(key))

    def on_scene_click(self, x, y):
        if self.current_tool == 'path':
            self._add_path_point(x, y)
            return
            
        item = self.scene.itemAt(QPointF(x, y), QTransform())
        if item:
            for o in self.objects:
                if o['item'] == item:
                    self.select_object(o)
                    return
            return
            
        scale = self.spin_scale.value()
        rotation = self.spin_rotation.value()
        
        if self.current_tool == 'car':
            self._add_item('car', x, y, scale, rotation, 
                           color=self.combo_car_color.currentText(), 
                           direction=self.combo_car_direction.currentText())
        elif self.current_tool == 'traffic':
            self._add_item('traffic', x, y, scale, rotation, 
                           signal=self.combo_signal.currentText())
        elif self.current_tool == 'zebra':
            self._add_item('zebra', x, y, scale, rotation, 
                           orientation=self.combo_zebra_orientation.currentText())
        elif self.current_tool == 'sign':
            self._add_item('sign', x, y, scale, rotation, 
                           sign_type=self.current_sign_type)
        else:
            self._add_item(self.current_tool, x, y, scale, rotation)

    # РАБОТА С ПУТЁМ
    def _add_path_point(self, x, y):
        idx = len(self.path_points)
        pt = QPointF(x, y)
        self.path_points.append(pt)
        
        point_item = PathPointItem(x, y, idx + 1)
        self.scene.addItem(point_item)
        self.path_point_items.append(point_item)
        
        if idx > 0:
            prev = self.path_points[idx - 1]
            line = self.scene.addLine(prev.x(), prev.y(), x, y, QPen(QColor(0, 120, 215), 3, Qt.DashLine))
            line.setZValue(9)
            self.path_line_items.append(line)
            
        self.statusBar().showMessage(
            f"Точка пути #{idx + 1} добавлена. Всего точек: {len(self.path_points)}"
        )

    def clear_path(self):
        for it in self.path_line_items:
            self.scene.removeItem(it)
        for it in self.path_point_items:
            self.scene.removeItem(it)
            if hasattr(it, 'label'):
                self.scene.removeItem(it.label)
        self.path_line_items.clear()
        self.path_point_items.clear()
        self.path_points.clear()
        self.statusBar().showMessage("Путь очищен.")

    def _redraw_path(self):
        self.clear_path()
        for i, pt in enumerate(self.path_points):
            point_item = PathPointItem(pt.x(), pt.y(), i + 1)
            self.scene.addItem(point_item)
            self.path_point_items.append(point_item)
            if i > 0:
                prev = self.path_points[i - 1]
                line = self.scene.addLine(prev.x(), prev.y(), pt.x(), pt.y(), QPen(QColor(0, 120, 215), 3, Qt.DashLine))
                line.setZValue(9)
                self.path_line_items.append(line)

    # АНИМАЦИЯ ДВИЖЕНИЯ МАШИНКИ ПО ПУТИ
    def start_animation(self):
        if len(self.path_points) < 2:
            QMessageBox.warning(self, "Внимание", "Путь должен содержать минимум 2 точки!")
            return
            
        car_obj = None
        for o in self.objects:
            if o['type'] == 'car':
                car_obj = o
                break
                
        if car_obj is None:
            QMessageBox.warning(self, "Внимание", "На сцене нет объекта типа «car»!")
            return
            
        self.anim_car = car_obj
        self.anim_index = 0
        self.anim_progress = 0.0
        self.anim_speed = self.spin_speed.value()
        
        start = self.path_points[0]
        car_obj['item'].setPos(start.x(), start.y())
        car_obj['x'] = start.x()
        car_obj['y'] = start.y()
        
        base_pixmap = self._get_pixmap(car_obj['color'] + '_up', 'blue_up')
        car_obj['item'].setPixmap(base_pixmap)
        car_obj['item'].setTransformationMode(Qt.SmoothTransformation)
        
        self._orient_car_to_segment(0)
        
        interval = self.spin_interval.value()
        self.anim_timer.start(interval)
        self.anim_running = True
        self.statusBar().showMessage("Анимация запущена.")

    def stop_animation(self):
        self.anim_timer.stop()
        self.anim_running = False
        self.statusBar().showMessage("Анимация остановлена.")

    def _orient_car_to_segment(self, seg_index):
        if self.anim_car is None:
            return
        if seg_index >= len(self.path_points) - 1:
            return
            
        p1 = self.path_points[seg_index]
        p2 = self.path_points[seg_index + 1]
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        
        angle_rad = math.atan2(dy, dx)
        target_angle = math.degrees(angle_rad) + 90.0
        target_angle = target_angle % 360
        
        self.anim_car['target_rotation'] = target_angle
        
        if abs(dx) > abs(dy):
            direction = 'right' if dx > 0 else 'left'
        else:
            direction = 'down' if dy > 0 else 'up'
        self.anim_car['direction'] = direction

    def _anim_step(self):
        if self.anim_car is None:
            self.stop_animation()
            return
            
        if self.anim_index >= len(self.path_points) - 1:
            self.stop_animation()
            self.statusBar().showMessage("Машинка достигла конечной точки. Анимация завершена.")
            QMessageBox.information(self, "Готово", "Машинка достигла конечной точки и остановилась.")
            return
            
        p1 = self.path_points[self.anim_index]
        p2 = self.path_points[self.anim_index + 1]
        
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        seg_len = (dx * dx + dy * dy) ** 0.5
        
        if seg_len == 0:
            self.anim_index += 1
            self.anim_progress = 0.0
            return
            
        step = self.anim_speed / seg_len
        self.anim_progress += step
        
        if self.anim_progress >= 1.0:
            self.anim_index += 1
            self.anim_progress = 0.0
            self._orient_car_to_segment(self.anim_index)
        else:
            t = self.anim_progress
            new_x = p1.x() + dx * t
            new_y = p1.y() + dy * t
            self.anim_car['item'].setPos(new_x, new_y)
            self.anim_car['x'] = new_x
            self.anim_car['y'] = new_y
            
            if 'target_rotation' in self.anim_car:
                item = self.anim_car['item']
                current = item.rotation() % 360
                target = self.anim_car['target_rotation']
                
                diff = target - current
                if diff > 180:
                    diff -= 360
                elif diff < -180:
                    diff += 360
                    
                rotate_step = 8.0
                if abs(diff) <= rotate_step:
                    item.setRotation(target)
                else:
                    new_rot = current + (rotate_step if diff > 0 else -rotate_step)
                    item.setRotation(new_rot)

    # ДОБАВЛЕНИЕ ОБЪЕКТОВ
    def _add_item(self, obj_type, x, y, scale, rotation, **kwargs):
        pixmap_key = self._get_pixmap_key(obj_type, **kwargs)
        pixmap = self.pixmaps.get(pixmap_key, self.pixmaps.get('road'))
        
        item = QGraphicsPixmapItem(pixmap)
        item.setPos(x, y)
        item.setScale(scale)
        item.setRotation(rotation)
        item.setFlags(QGraphicsPixmapItem.ItemIsSelectable | QGraphicsPixmapItem.ItemIsMovable)
        self.scene.addItem(item)
        
        obj = {
            'item': item, 'type': obj_type, 'x': x, 'y': y,
            'scale': scale, 'rotation': rotation
        }
        obj.update(kwargs)
        self.objects.append(obj)

    def _get_pixmap_key(self, obj_type, **kwargs):
        if obj_type == 'car':
            return kwargs.get('color', 'blue') + '_' + kwargs.get('direction', 'up')
        elif obj_type == 'traffic':
            return 'traffic_' + kwargs.get('signal', 'green')
        elif obj_type == 'zebra':
            return 'zebra_v' if kwargs.get('orientation') == 'vertical' else 'zebra_h'
        elif obj_type == 'sign':
            return kwargs.get('sign_type', 'start')
        return obj_type

    def _get_pixmap(self, key, fallback):
        return self.pixmaps.get(key, self.pixmaps.get(fallback))

    def select_object(self, obj):
        self.selected_obj = obj
        self.spin_scale.setValue(obj.get('scale', 1.0))
        self.spin_rotation.setValue(obj.get('rotation', 0))
        self.lbl_info.setText(f"Выбран: {obj['type']}")
        
        if obj['type'] == 'car':
            self.combo_car_color.setCurrentText(obj.get('color', 'blue'))
            self.combo_car_direction.setCurrentText(obj.get('direction', 'up'))
        elif obj['type'] == 'traffic':
            self.combo_signal.setCurrentText(obj.get('signal', 'green'))
        elif obj['type'] == 'zebra':
            self.combo_zebra_orientation.setCurrentText(obj.get('orientation', 'horizontal'))

    def delete_object(self):
        if not self.selected_obj:
            QMessageBox.warning(self, "Внимание", "Сначала выберите объект!")
            return
        self.scene.removeItem(self.selected_obj['item'])
        self.objects.remove(self.selected_obj)
        self.selected_obj = None
        self.lbl_info.setText("Объект не выбран")

    # сохранение
    def save_project(self):
        file, _ = QFileDialog.getSaveFileName(self, "Сохранить", "", "JSON (*.json)")
        if not file:
            return
            
        data = {
            'objects': [],
            'path': [{'x': p.x(), 'y': p.y()} for p in self.path_points]
        }
        
        for obj in self.objects:
            item_data = {
                'type': obj['type'], 'x': obj['x'], 'y': obj['y'],
                'scale': obj.get('scale', 1.0), 'rotation': obj.get('rotation', 0)
            }
            for key in ['color', 'direction', 'signal', 'orientation', 'sign_type']:
                if key in obj:
                    item_data[key] = obj[key]
            data['objects'].append(item_data)
            
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        QMessageBox.information(self, "OK", "Проект сохранён!")

    def load_project(self):
        file, _ = QFileDialog.getOpenFileName(self, "Загрузить", "", "JSON (*.json)")
        if not file:
            return
            
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.scene.clear()
        self.objects.clear()
        self.draw_grid()
        
        for item_data in data.get('objects', []):
            obj_type = item_data['type']
            kwargs = {k: v for k, v in item_data.items() if k in ['color', 'direction', 'signal', 'orientation', 'sign_type']}
            self._add_item(obj_type, item_data['x'], item_data['y'], 
                           item_data.get('scale', 1.0), item_data.get('rotation', 0), **kwargs)
                           
        self.path_points = [QPointF(p['x'], p['y']) for p in data.get('path', [])]
        self._redraw_path()
        QMessageBox.information(self, "OK", "Проект загружен!")

    # ОБУЧЕНИЕ МОДЕЛИ
    def calculate_intersection_load(self):
        """
        Формула расчёта загруженности перекрестка:
        Загруженность = (количество машин * 2 + количество пешеходов * 1) / площадь сцены * 1000
        """
        car_count = sum(1 for obj in self.objects if obj['type'] == 'car')
        pedestrian_count = sum(1 for obj in self.objects if obj['type'] == 'pedestrian')
        scene_area = 2000 * 1500  # площадь сцены
        
        load = (car_count * 2 + pedestrian_count * 1) / scene_area * 1000
        return min(load, 100.0)  # ограничиваем до 100%

    def start_training(self):
        """Обучение на 1 эпоху"""
        self.current_epoch += 1
        
        # Расчёт загруженности перекрестка
        load_level = self.calculate_intersection_load()
        
        # Имитация обучения (в реальности здесь будет код обучения нейросети)
        # Потери уменьшаются с каждой эпохой, точность растёт
        base_loss = 1.0 / (1 + self.current_epoch * 0.1)
        loss = base_loss + random.uniform(-0.05, 0.05)
        loss = max(0.01, loss)
        
        base_accuracy = min(95.0, 50.0 + self.current_epoch * 3.5)
        accuracy = base_accuracy + random.uniform(-2.0, 2.0)
        accuracy = max(0.0, min(100.0, accuracy))
        
        # Запись в историю обучения
        self.training_history.append({
            'epoch': self.current_epoch,
            'loss': loss,
            'accuracy': accuracy
        })
        
        # Сохранение модели (имитация)
        model_saved = "Да" if self.current_epoch % 5 == 0 else "Нет"
        
        # Запись в журнал событий
        event = {
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'epoch': self.current_epoch,
            'model_saved': model_saved,
            'load_level': load_level
        }
        self.event_log.append(event)
        
        self.statusBar().showMessage(
            f"Эпоха {self.current_epoch} завершена. Loss: {loss:.4f}, Accuracy: {accuracy:.2f}%, "
            f"Загруженность: {load_level:.2f}%"
        )
        
        QMessageBox.information(
            self, 
            "Обучение", 
            f"Эпоха {self.current_epoch} завершена!\n\n"
            f"Потери (Loss): {loss:.4f}\n"
            f"Точность (Accuracy): {accuracy:.2f}%\n"
            f"Загруженность перекрестка: {load_level:.2f}%\n"
            f"Модель сохранена: {model_saved}"
        )

    def show_training_process(self):
        """Отображение процесса обучения"""
        if not self.training_history:
            QMessageBox.warning(self, "Внимание", "История обучения пуста. Начните обучение!")
            return
            
        dialog = TrainingProcessDialog(self)
        dialog.update_data(self.training_history)
        dialog.exec_()

    def show_event_log(self):
        """Отображение журнала событий"""
        if not self.event_log:
            QMessageBox.warning(self, "Внимание", "Журнал событий пуст. Начните обучение!")
            return
            
        dialog = EventLogDialog(self)
        dialog.update_data(self.event_log)
        dialog.exec_()

# ТОЧКА ВХОДА
if __name__ == '__main__':
    app = QApplication(sys.argv)
    try:
        window = TrafficEditor()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Ошибка: {e}")