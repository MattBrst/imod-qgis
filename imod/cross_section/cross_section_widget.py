from PyQt5.QtWidgets import (
    QWidget,
    QStackedLayout,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGridLayout,
    QLabel,
    QToolButton,
    QMenu,
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, pyqtSignal
from qgis.gui import (
    QgsMapLayerComboBox,
    QgsColorButton,
    QgsColorRampButton,
    QgsVertexMarker,
    QgsRubberBand,
    QgsMapTool,
)
from qgis.core import (
    QgsColorBrewerColorRamp,
    QgsGeometry,
    QgsWkbTypes,
    QgsPointXY,
    QgsMeshDatasetIndex,
    QgsMapLayerProxyModel
)

import numpy as np
import pyqtgraph as pg

from .pcolormesh import PColorMeshItem
from .plot_util import cross_section_x_data, cross_section_y_data, cross_section_hue_data
from .dataset_variable_widget import VariablesWidget
from ..utils.layers import groupby_variable, get_group_names

class PickGeometryTool(QgsMapTool):
    picked = pyqtSignal(
        list, bool
    )  # list of pointsXY, whether finished or still drawing

    def __init__(self, canvas):
        QgsMapTool.__init__(self, canvas)
        self.points = []
        self.capturing = False

    def canvasMoveEvent(self, e):
        if not self.capturing:
            return
        self.picked.emit(self.points + [e.mapPoint()], False)

    def canvasPressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.capturing = True
            self.points.append(e.mapPoint())
            self.picked.emit(self.points, False)
        if e.button() == Qt.RightButton:
            self.picked.emit(self.points, True)
            self.capturing = False
            self.points = []

    def canvasReleaseEvent(self, e):
        pass


class LineGeometryPickerWidget(QWidget):
    geometries_changed = pyqtSignal()
    PICK_NO, PICK_MAP, PICK_LAYER = range(3)

    def __init__(self, iface, parent=None):
        QWidget.__init__(self, parent)

        self.iface = iface
        self.pick_mode = self.PICK_NO
        self.pick_layer = None
        self.geometries = []

        self.button = QPushButton("From map")
        self.button.clicked.connect(self.picker_clicked)

        self.tool = PickGeometryTool(self.iface.mapCanvas())
        self.tool.picked.connect(self.on_picked)
        self.tool.setButton(self.button)

        layout = QHBoxLayout()
        layout.addWidget(self.button)
        self.setLayout(layout)

    def clear_geometries(self):
        self.geometries = []
        self.geometries_changed.emit()

    def picker_clicked(self):
        was_active = self.pick_mode == self.PICK_MAP
        self.stop_picking()
        if not was_active:
            self.start_picking_map()

    def start_picking_map(self):
        self.pick_mode = self.PICK_MAP
        self.iface.mapCanvas().setMapTool(self.tool)
        self.clear_geometries()

    def stop_picking(self):
        if self.pick_mode == self.PICK_MAP:
            self.iface.mapCanvas().unsetMapTool(self.tool)
        elif self.pick_mode == self.PICK_LAYER:
            self.pick_layer.selectionChanged.disconnect(self.on_pick_selection_changed)
            self.pick_layer = None
        self.pick_mode = self.PICK_NO

    def on_picked(self, points, finished):
        if len(points) >= 2:
            self.geometries = [QgsGeometry.fromPolylineXY(points)]
        else:
            self.geometries = []
        self.geometries_changed.emit()
        if finished:  # no more updates
            self.stop_picking()


class ImodCrossSectionWidget(QWidget):
    #TODO: Use QGIS colormaps instead of pyqt ones
    #TODO: Include resolution setting in box
    #TODO: Calculate proper default resolution
    #TODO: Include time selection box
    def __init__(self, parent, iface):
        QWidget.__init__(self, parent)
        self.iface = iface

        self.layer_selection = QgsMapLayerComboBox()
        self.layer_selection.setFilters(QgsMapLayerProxyModel.MeshLayer)
        self.layer_selection.layerChanged.connect(self.on_layer_changed)

        self.variable_selection = VariablesWidget()
        self.variable_selection.dataset_variable_changed.connect(self.on_variable_changed)

        #Initialize groupby variables and variable names
        self.set_groupby_variables()
        self.set_variable_names() 

        self.line_picker = LineGeometryPickerWidget(iface)
        self.line_picker.geometries_changed.connect(
            self.on_geometries_changed
            )

        self.plot_button = QPushButton("Plot")
        self.plot_button.clicked.connect(self.draw_plot)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_plot)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=True, y=True)

        self.rubber_band = None

        first_row = QHBoxLayout()
        first_row.addWidget(self.layer_selection)
        first_row.addWidget(self.variable_selection)
        first_row.addWidget(self.line_picker)

        first_row.addWidget(self.plot_button)
        first_row.addWidget(self.clear_button)

        second_row = QHBoxLayout()
        second_row.addWidget(self.plot_widget)

        layout = QVBoxLayout()
        layout.addLayout(first_row)
        layout.addLayout(second_row)
        self.setLayout(layout)

    def hideEvent(self, e):
        self.clear_plot()
        QWidget.hideEvent(self, e)

    def clear_plot(self):
        self.plot_widget.clear()
        self.line_picker.clear_geometries()
        self.clear_legend()

    def clear_legend(self):
        pass

    def _repeat_to_2d(self, arr, n, axis=0):
        """Repeat array n times along new axis
        
        Parameters
        ----------
        arr : np.array[m]
        
        n : int
        

        Returns
        -------
        np.array[n x m]

        """
        return np.repeat(np.expand_dims(arr, axis=axis), n, axis=axis)

    def extract_cross_section_data(self):
        current_layer = self.layer_selection.currentLayer()

        #Get arbitrary key
        first_key = next(iter(self.gb_var.keys()))

        #Get layer numbers: first element contains layer number
        layer_nrs = next(zip(*self.gb_var[first_key]))
        layer_nrs = list(layer_nrs)
        layer_nrs.sort()
        n_lay = len(layer_nrs)

        #TODO: Are there ever more geometries than one Linestring?
        geometry = self.line_picker.geometries[0] 

        #Get x values of points
        x_line = cross_section_x_data(current_layer, geometry, resolution=50.)
        n_x = x_line.size

        #Get y values of points
        ## Amount of layers * 2 because we have tops and bottoms we independently add
        y = np.zeros((n_lay * 2, n_x)) 

        ## FUTURE: When MDAL supports UGRID layer, looping over layers not necessary.
        for k in range(n_lay):
            layer_nr, dataset_bottom = self.gb_var["bottom"][k]
            layer_nr, dataset_top    = self.gb_var["top"][k]

            i = (layer_nr-1) * 2
            y[i, :] = cross_section_y_data(current_layer, geometry, dataset_top, x_line)
            y[i+1, :] = cross_section_y_data(current_layer, geometry, dataset_bottom, x_line)

        #Repeat x along new dimension to get np.meshgrid like array
        x = self._repeat_to_2d(x_line, n_lay * 2)

        if len(self.dataset_variable) == 0: 
            raise ValueError("No variable set")
        elif self.dataset_variable == "layer number": 
            z = self.color_by_layer(n_lay, n_x, layer_nrs)
        else:
            z = self.color_by_variable(n_lay, n_x, geometry, x_line)

        #Filter values line outside mesh
        ## Assume: NaNs in first layer are NaNs in every layer
        is_nan = np.isnan(y[0, :])
        y[:, is_nan] = 0.0 #Give dummy value, these will be deactivated by inactive z
        color_nan = is_nan[1:] | is_nan[:-1] #If a vertex on either side is NaN, deactivate

        z[:, color_nan] = np.nan

        return x, y, z

    def color_by_layer(self, n_lay, n_x, layer_nrs):
        z = np.empty((n_lay * 2 - 1, n_x - 1))
        z[:] = np.nan
        ## Color only parts between top and bot, not bot and top.
        z[::2, :] = np.expand_dims(layer_nrs, axis=1)
        return z

    def color_by_variable(self, n_lay, n_x, geometry, x):
        current_layer = self.layer_selection.currentLayer()
        
        x_mids = (x[1:] + x[:-1])/2

        z = np.empty((n_lay * 2 - 1, n_x - 1))
        z[:] = np.nan
        for k in range(n_lay):
            var_name = self.dataset_variable

            layer_nr, dataset = self.gb_var[var_name][k]
            i = (layer_nr-1) * 2
            z[i, :] = cross_section_hue_data(current_layer, geometry, dataset, x_mids)
        return z

    def draw_plot(self):
        self.plot_widget.clear() #Ensure plot is cleared before adding new stuff

        x, y, z = self.extract_cross_section_data()

        #debug
        self.x_values = x
        self.y_values = y

        pcmi = PColorMeshItem(x, y, z, cmap="inferno")
        self.plot_widget.addItem(pcmi)

        # Might be smart to draw ConvexPolygons instead of pColorMeshItem,
        # (see code in pColorMeshItem)
        # https://github.com/pyqtgraph/pyqtgraph/blob/5eb671217c295178de255b1fece56379cdef8235/pyqtgraph/graphicsItems/PColorMeshItem.py#L140
        # So we can draw rectangular polygons if necessary.

    def set_groupby_variables(self):
        current_layer = self.layer_selection.currentLayer()
        idx, group_names = get_group_names(current_layer)
        self.gb_var = groupby_variable(group_names, idx)

    def set_variable_names(self):
        current_layer = self.layer_selection.currentLayer()
        variable_names = list(self.gb_var.keys())
        variable_names = [x for x in variable_names if x not in ["bottom", "top"]]

        self.variable_selection.set_layer(current_layer, variable_names)

        self.dataset_variable = self.variable_selection.dataset_variable

    def on_geometries_changed(self):
        self.iface.mapCanvas().scene().removeItem(self.rubber_band)
        if len(self.line_picker.geometries) == 0:
            return
        self.rubber_band = QgsRubberBand(
            self.iface.mapCanvas(), QgsWkbTypes.PointGeometry
        )
        self.rubber_band.setColor(QColor(Qt.red))
        self.rubber_band.setWidth(2)
        self.rubber_band.setToGeometry(self.line_picker.geometries[0], None)

    def on_layer_changed(self):
        self.set_groupby_variables()
        self.set_variable_names()

    def on_variable_changed(self):
        self.dataset_variable = self.variable_selection.dataset_variable