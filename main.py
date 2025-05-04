import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication, QMainWindow, QSpacerItem, QGridLayout, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel, QCheckBox, QSlider, QStyle, QSizePolicy
from PyQt6.QtGui import QIcon, QMovie, QPixmap, QFont
from PyQt6.QtCore import QSize, Qt, QRunnable, QThreadPool, QObject, pyqtSignal
from PyQt6.QtTest import QTest

import numpy as np
import os
import sys


class LoadingScreen(QWidget):
    """Ladescreen-Klasse zur Anzeige während des Ladens von Daten"""
    def __init__(self):
        super().__init__()

        self.cwd = os.path.abspath(os.path.dirname(__file__))

        self.setFixedSize(441, 291)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.CustomizeWindowHint)

        # Label mit Gifdarstellung
        self.label_animation = QLabel(parent=self)
        self.movie = QMovie(os.path.join(self.cwd, 'icons', 'loading.gif')) 
        self.label_animation.setMovie(self.movie)
        self.movie.start()

    def start_animation(self):
        self.show()
        self.movie.start()
    
    def stop_animation(self):
        self.movie.stop()
        self.close()


class SignalEmitter(QObject):
    """Klasse für eigene Signale"""
    working = pyqtSignal(int)
    failed = pyqtSignal(Exception)
    finished = pyqtSignal(object)


class GenericWorker(QRunnable):
    """Klasse für generischen Worker für das parallele Ausführen allgemeiner Funktionen"""
    def __init__(self, func, *args, **kwargs):
        super(GenericWorker, self).__init__()

        self.emitter = SignalEmitter()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            self.emitter.working.emit(True)
            result = self.func(*self.args, **self.kwargs)
        except Exception as e:
            self.emitter.failed.emit(e)
            self.emitter.working.emit(False)
        else:
            self.emitter.finished.emit(result)
            self.emitter.working.emit(False)


class MainWindow(QMainWindow):
    """Klasse für GUI-Anwendung"""
    def __init__(self):
        super(MainWindow, self).__init__()

        self.cwd = os.path.abspath(os.path.dirname(__file__))

        self.radar_data = []
        self.data = {'timestamp': '', 'min_ahead': '', 'data': None}

        ## Satellitenkarte laden
        self.map = self.get_map()

        ## Threadpool für parallele Berechnungen
        self.threadpool = QThreadPool()

        ## MainWindow Einstellungen
        self.setWindowTitle('Regenradar')
        self.setMinimumSize(QSize(1200, 800))
        self.setWindowIcon(QIcon(os.path.join(self.cwd, 'icons', 'icon.png')))

        ## Default Textfont
        def_font = QFont()
        def_font.setPointSize(10)

        ## Widgets
        # Label mit Zeitstempel
        self.lbl_time = QLabel()
        lbl_time_font = QFont()
        lbl_time_font.setPointSize(15)
        lbl_time_font.setBold(True)
        self.lbl_time.setFont(lbl_time_font)

        # Label für Links und Rechts vom Radarslider
        self.lbl_jetzt = QLabel('Jetzt')
        self.lbl_jetzt.setFont(def_font)
        self.lbl_120 = QLabel('in 2h')
        self.lbl_120.setFont(def_font)

        # Slider zur Auswahl des Zeitstempels
        self.sld_radar = QSlider()
        self.sld_radar.setOrientation(Qt.Orientation.Horizontal)
        self.sld_radar.setRange(1, 25)

        # Label mit Regenmenge beim Mauszeiger
        self.lbl_value = QLabel()
        lbl_value_font = QFont()
        lbl_value_font.setPointSize(15)
        lbl_value_font.setBold(True)
        self.lbl_value.setFont(lbl_value_font)

        # Label mit Programm-Icon
        self.lbl_icon = QLabel()
        self.lbl_icon.setPixmap(QPixmap(os.path.join(self.cwd, 'icons', 'icon.png')).scaled(QSize(100, 100)))

        # Button zum Abspielen der Radarslideshow
        self.btn_play = QPushButton()
        self.btn_play.setText('Regenradar abspielen')
        self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play.setIconSize(QSize(40, 40))
        bnt_play_font = QFont()
        bnt_play_font.setPointSize(10)
        bnt_play_font.setBold(True)
        self.btn_play.setFont(bnt_play_font)
        self.btn_play.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        # Slider zum Einstellen der Abspielgeschwindigkeit
        self.sld_speed = QSlider()
        self.sld_speed.setOrientation(Qt.Orientation.Horizontal)
        self.sld_speed.setRange(1, 6)
        self.sld_speed.setValue(2)
        self.sld_speed.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        # Label zur Anzeige der Abspielgeschwindigkeit
        self.lbl_speed = QLabel()
        self.lbl_speed.setText(f'Wiedergabegeschwindigkeit: {str(self.sld_speed.value() * 0.5)}x')
        self.lbl_speed.setFont(def_font)

        # Checkbox zum Ein- und Ausblenden der Radardaten
        self.cb_show_radar = QCheckBox('Radar anzeigen')
        self.cb_show_radar.setChecked(True)
        self.cb_show_radar.setFont(def_font)

        # Button zum Herunterladen und Darstellen aktueller Radardaten
        self.btn_load = QPushButton('Aktuelle Daten herunterladen')
        self.btn_load.setFont(def_font)
        self.btn_load.setToolTip('Deaktiviert')

        ## PyQtGraph Widgets
        # GraphicsLayoutWidget als Hauptwidget der Plotdarstellung
        self.pg_glw = pg.GraphicsLayoutWidget(border='k')
        self.pg_glw.setBackground('w')

        # ViewBoxes für Hauptansicht und Zoomansicht
        self.vb_radar = pg.ViewBox(border='k', lockAspect=True)
        self.vb_zoom = pg.ViewBox(border='k', lockAspect=True)

        # ImageItems für Karte, Radardaten und Zoomdarstellung
        self.img_map = pg.ImageItem(self.map)
        self.img_map.setOpts(axisOrder='col-major')
        self.img_data = pg.ImageItem()
        self.img_data.setOpts(axisOrder='row-major')
        self.img_data.setColorMap('viridis')
        self.img_zoom_map = pg.ImageItem()
        self.img_zoom_map.setOpts(axisOrder='col-major')
        self.img_zoom_data = pg.ImageItem()
        self.img_zoom_data.setOpts(axisOrder='row-major')
        self.img_zoom_data.setColorMap('viridis')

        # Layout für PyQtGraph-Ansicht
        self.pg_layout = pg.GraphicsLayout()
        self.vb_radar.addItem(self.img_map)
        self.vb_radar.addItem(self.img_data)
        self.vb_zoom.addItem(self.img_zoom_map)
        self.vb_zoom.addItem(self.img_zoom_data)
        self.pg_layout.addItem(self.vb_radar, row=0, col=0)
        self.pg_layout.addItem(self.vb_zoom, row=0, col=1)
        self.pg_glw.setCentralItem(self.pg_layout)

        ## Region of Interest (ROI)
        self.roi = pg.RectROI([1150, 3250], [250, 250])
        self.roi.setPen(pg.mkPen(width=3))
        self.vb_radar.addItem(self.roi)

        ## Signale
        # ROI Signal
        self.roi.sigRegionChanged.connect(self.update_roi)

        # Button, Slider, Checkbox Signale
        self.cb_show_radar.stateChanged.connect(self.show_radar)
        self.sld_speed.valueChanged.connect(self.update_speed)
        self.btn_play.clicked.connect(self.play_slideshow)
        self.sld_radar.valueChanged.connect(self.slider_changed)

        # MouseEvents
        self.img_zoom_data.scene().sigMouseMoved.connect(self.update_value)
        self.img_data.scene().sigMouseClicked.connect(self.set_roi)

        ## Layout
        # Oben links
        top_left_layout = QVBoxLayout()
        lyt_a = QHBoxLayout()
        lyt_b = QHBoxLayout()
        lyt_a.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        lyt_a.addWidget(self.lbl_time)
        lyt_a.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        lyt_b.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        lyt_b.addWidget(self.lbl_jetzt)
        lyt_b.addWidget(self.sld_radar)
        lyt_b.addWidget(self.lbl_120)
        lyt_b.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        top_left_layout.addLayout(lyt_a)
        top_left_layout.addLayout(lyt_b)

        # Oben rechts
        top_right_layout = QHBoxLayout()
        top_right_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        top_right_layout.addWidget(self.lbl_value)
        top_right_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        top_right_layout.addWidget(self.lbl_icon)

        # Mitte mit PyQtGraph-Ansicht
        middle_layout = QVBoxLayout()
        middle_layout.addWidget(self.pg_glw)

        # Unten links
        bottom_left_layout = QVBoxLayout()
        lyt_c = QHBoxLayout()
        lyt_d = QHBoxLayout()
        lyt_c.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        lyt_c.addWidget(self.btn_play)
        lyt_c.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        lyt_d.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        lyt_d.addWidget(self.lbl_speed)
        lyt_d.addWidget(self.sld_speed)
        lyt_d.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        bottom_left_layout.addLayout(lyt_c)
        bottom_left_layout.addLayout(lyt_d)

        # Unten rechts
        bottom_right_layout = QVBoxLayout()
        lyt_e = QHBoxLayout()
        lyt_f = QHBoxLayout()
        lyt_e.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        lyt_e.addWidget(self.cb_show_radar)
        lyt_e.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        lyt_f.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        lyt_f.addWidget(self.btn_load)
        lyt_f.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        bottom_right_layout.addLayout(lyt_e)
        bottom_right_layout.addLayout(lyt_f)

        # Hauptlayout
        self.layout = QGridLayout()
        self.layout.setColumnStretch(0, 1)
        self.layout.setColumnStretch(1, 1)
        self.layout.addLayout(top_left_layout, 0, 0)
        self.layout.addLayout(top_right_layout, 0, 1)
        self.layout.addLayout(middle_layout, 1, 0, 1, 2)
        self.layout.addLayout(bottom_left_layout, 2, 0)
        self.layout.addLayout(bottom_right_layout, 2, 1)

        self.container = QWidget()
        self.container.setLayout(self.layout)
        self.setCentralWidget(self.container)

        self.btn_load.setEnabled(False)

        ## Ausführung von Methoden bei Programmstart
        # ROI-Darstellung
        self.update_roi(self.roi)
        # Beispieldatensatz laden
        self.load_with_worker('2301091610_radar_data.npz')
    

    # Methode zum Versetzen der ROI per Klick auf Karte
    def set_roi(self, evt):
        # Position des Events
        evt_pos = evt.pos()
        # Integer-Check verhindert falsche Koordinaten
        if float(evt_pos.x()).is_integer() and float(evt_pos.y()).is_integer():
            # Umrechnung der Koordinaten zu View-Koordinaten
            pos = self.vb_radar.mapToView(evt_pos)
            # Klickposition soll Mitte der ROI sein
            size = self.roi.size()
            new_x = int(pos.x()) - int(size.x()) // 2
            new_y = int(pos.y()) - int(size.y()) // 2
            # Neue ROI-Position festlegen
            self.roi.setPos(new_x, new_y)


    # Methode zum Aktualisieren des Labels mit der Regenmenge
    def update_value(self, evt):
        # Position bestimmen
        pos = self.vb_zoom.mapSceneToView(evt)
        x = int(pos.x())
        y = int(pos.y())
        data = self.img_zoom_data.image
        # Pruefen ob schon Daten vorliegen
        if not isinstance(data, type(None)):
            # Werte außerhalb des Daten-Arrays ignorieren
            m, n = data.shape
            if 0 <= y < m and 0 <= x < n:
                # Text formatieren und Label aktualisieren
                value = round(data[y, x], 4)
                if value >= 0:
                    self.lbl_value.setText(f'Regenmenge: {format(value, ".4f")} mm')
                else:
                    self.lbl_value.setText(f'Regenmenge: {format(0., ".4f")} mm')


    # Methode zum Laden eines neuen Datensatzes mit Hilfe eines parallelen Worker-Threads
    def load_with_worker(self, filename):
        # Widgets temporär deaktivieren
        self.btn_play.setEnabled(False)
        self.sld_radar.setEnabled(False)
        self.sld_speed.setEnabled(False)
        self.btn_load.setEnabled(False)
        # Worker-Thread beauftragen
        loading_worker = GenericWorker(self.load_data, filename)
        loading_worker.emitter.working.connect(self.loading_worker_working)
        loading_worker.emitter.finished.connect(self.loading_worker_finished)
        loading_worker.emitter.failed.connect(self.loading_worker_failed)
        self.threadpool.start(loading_worker)
    

    # Methode zum Darstellen des Ladescreens, wenn Worker aktiv ist
    def loading_worker_working(self, working):
        # Ladescreen starten wenn Worker arbeitet
        if working:
            self.loading_animation = LoadingScreen()
            self.loading_animation.start_animation()
        # Ladescreen stoppen wenn Worker fertig
        else:
            self.loading_animation.stop_animation()


    # Methode für erfolgreiche Arbeit des Workers
    def loading_worker_finished(self, r):
        # Ergebnisse übertragen
        self.radar_data = r
        # Darstellung aktualisieren
        self.update_radar(self.radar_data[0])
        print(f'Loading worker finished.')
        # Widgets wieder aktivieren
        self.btn_play.setEnabled(True)
        self.sld_radar.setEnabled(True)
        self.sld_speed.setEnabled(True)
        #self.btn_load.setEnabled(True)


    # Methode für Exception beim Worker
    def loading_worker_failed(self, e):
        # Exception ausgeben
        print(f'Loading worker failed: {e}')
        # Widgets wieder aktivieren
        self.btn_play.setEnabled(True)
        self.sld_radar.setEnabled(True)
        self.sld_speed.setEnabled(True)
        #self.btn_load.setEnabled(True)


    # Methode zum Aktualisieren des Labels mit der Wiedergabegeschwindigkeit
    def update_speed(self, value):
        self.lbl_speed.setText(f'Wiedergabegeschwindigkeit: {str(value * 0.5)}x')


    # Methode zum Aktualisieren der Radardarstellung, der ROI und des Labels mit Zeitstempel
    def update_radar(self, data):
        # Aktueller Datensatz
        self.data = data
        # Image mit Datensatz aktualisieren
        self.img_data.setImage(self.data['data'], levels=[0., 5.])
        # ROI aktualisieren
        self.update_roi(self.roi)
        # Text formatieren und Label aktualisieren
        timestamp = self.data['timestamp']
        min_ahead = int(self.data['min_ahead'])
        text = f'UTC-Zeit: {timestamp[4:6]}.{timestamp[2:4]}.20{timestamp[0:2]} {timestamp[6:8]}:{timestamp[8:10]} +{min_ahead} Minuten'
        self.lbl_time.setText(text)


    # Methode zum Aktualisieren der Zoomansicht
    def update_roi(self, roi):
        # Zoom-Image mit Ausschnitt des Satellitenbilds aktualisieren
        self.img_zoom_map.setImage(roi.getArrayRegion(self.map, self.img_map), levels=(self.img_map.getLevels()))
        # Pruefen ob schon Daten vorliegen
        if not isinstance(self.data['data'], type(None)):
            # Zoom-Image mit Radardaten im Bereich der ROI aktualisieren
            self.img_zoom_data.setImage(roi.getArrayRegion(self.data['data'], self.img_data), levels=(self.img_data.getLevels()))
        self.vb_zoom.autoRange()


    # Methode für Aktualisierung nach Veränderung des Zeitstempelsliders
    def slider_changed(self, value):
        self.update_radar(self.radar_data[value-1])


    # Methode zum Abspielen der Radarslideshow
    def play_slideshow(self):
        # Widgets temporär deaktivieren
        self.btn_play.setEnabled(False)
        self.sld_radar.setEnabled(False)
        self.sld_speed.setEnabled(False)
        self.btn_load.setEnabled(False)
        # Zeitintervall festlegen
        wait = round(400 / float(self.sld_speed.value()))
        # Anzahl der Wiederholungen festlegen
        for _ in range(1, 2):
            # Durch alle Zeitstempel iterieren
            for data in self.radar_data:
                # Darstellung aktualisieren
                self.update_radar(data)
                # Der App ermöglichen Änderungen zu verarbeiten
                QApplication.processEvents()
                # Festgelegte Zeit warten
                QTest.qWait(wait)
        # Zum Zeitstempel 0 zurückkehren
        self.update_radar(self.radar_data[0])
        # Widgets wieder aktivieren
        self.btn_play.setEnabled(True)
        self.sld_radar.setEnabled(True)
        self.sld_speed.setEnabled(True)


    # Methode zum Ein- und Ausblenden der Radardarstellung
    def show_radar(self, checked):
        self.img_data.setVisible(checked)
        self.img_zoom_data.setVisible(checked)


    # Methode zum Laden der Satellitenkarte
    def get_map(self):
        with open(os.path.join(self.cwd, 'satellite.npy'), 'rb') as f:
            rgb = np.load(f)
        return rgb


    # Methode zum Berechnen und Laden eines neuen Datensatzes
    def load_data(self, filename):
        radar_data = []
        timestamp = filename.split('_')[0]

        # Numpy Arrays laden aus Datei
        radar_data_loaded = np.load(os.path.join(self.cwd, filename))
        # Durch geladene Arrays loopen und zu Liste der Radardaten hinzufügen
        for min_ahead, data in radar_data_loaded.items():
            radar_data.append({'timestamp': timestamp, 'min_ahead': min_ahead, 'data': data})

        # Liste mit Daten returnen
        return radar_data


if __name__ == '__main__':
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
