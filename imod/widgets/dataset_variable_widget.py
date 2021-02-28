"""Modified from https://github.com/lutraconsulting/qgis-crayfish-plugin/blob/master/crayfish/gui/plot_dataset_groups_widget.py
"""

from PyQt5.QtWidgets import QMenu, QToolButton, QWidgetAction, QCheckBox
from PyQt5.QtCore import Qt, pyqtSignal

DEFAULT_NAME = "layer number"


class DatasetVariableMenu(QMenu):

    # emits empty list when "current" is selected
    dataset_variable_changed = pyqtSignal(str)

    def __init__(self, parent=None, datasetType=None):
        QMenu.__init__(self, parent)
        self.variable_options = None
        self.layer = None
        self.action_current = None
        self.datasetType = datasetType

    def populate_actions(self, variables):
        """
        Populate actions

        Parameters
        ----------
        variables : list
            List with variable names
        """
        self.clear()

        if self.layer is None or self.layer.dataProvider() is None:
            return

        self.action_current = self.addAction(DEFAULT_NAME)
        self.action_current.variable_name = DEFAULT_NAME
        self.action_current.setCheckable(True)
        self.action_current.setChecked(True)
        self.action_current.triggered.connect(self.triggered_action_current)
        self.addSeparator()

        for variable in variables:
            a = self.addAction(variable)
            a.variable_name = variable
            a.setCheckable(True)
            a.triggered.connect(self.triggered_action)

    def triggered_action(self):
        for a in self.actions():
            a.setChecked(a == self.sender())
        self.dataset_variable_changed.emit(self.sender().variable_name)

    def triggered_action_current(self):
        for a in self.actions():
            a.setChecked(a == self.action_current)
        self.dataset_variable_changed.emit(DEFAULT_NAME)

    def on_current_dataset_changed(self):
        if self.action_current.isChecked():
            self.dataset_variable_changed.emit(DEFAULT_NAME)  # re-emit changed signal

    def set_layer(self, layer, variables):
        if layer is self.layer:
            return

        if self.layer is not None:
            self.layer.activeScalarDatasetGroupChanged.disconnect(
                self.on_current_dataset_changed
            )
            self.layer.dataChanged.disconnect(self.populate_actions)

        self.layer = layer
        if self.layer is not None:
            self.layer.activeScalarDatasetGroupChanged.connect(
                self.on_current_dataset_changed
            )
            self.layer.dataChanged.connect(self.populate_actions)

        self.populate_actions(variables)


class VariablesWidget(QToolButton):

    dataset_variable_changed = pyqtSignal(str)

    def __init__(self, parent=None, datasetType=None):
        QToolButton.__init__(self, parent)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # self.setIcon(QIcon(QPixmap(":/plugins/crayfish/images/icon_contours.png")))
        self.menu_datasets = DatasetVariableMenu(datasetType=datasetType)
        self.setPopupMode(QToolButton.InstantPopup)
        self.setMenu(self.menu_datasets)
        self.menu_datasets.dataset_variable_changed.connect(
            self.on_dataset_variable_changed
        )
        self.set_dataset_variable(DEFAULT_NAME)

    def on_dataset_variable_changed(self, name):
        self.dataset_variable = name
        self.setText("Variable: " + name)
        self.dataset_variable_changed.emit(name)

    def set_dataset_variable(self, name):
        self.on_dataset_variable_changed(name)

    def set_layer(self, layer, variables):
        self.menu_datasets.set_layer(layer, variables)
        self.set_dataset_variable(DEFAULT_NAME)


class MultipleVariablesMenu(QMenu):
    def __init__(self, parent=None):
        QMenu.__init__(self, parent)
        self.setContentsMargins(10, 5, 5, 5)

    def populate_actions(self, variables):
        self.clear()
        for variable in variables:
            a = QWidgetAction(self)
            a.variable_name = variable
            a.setDefaultWidget(QCheckBox(variable))
            self.addAction(a)


class MultipleVariablesWidget(QToolButton):
    def __init__(self, parent=None):
        QToolButton.__init__(self, parent)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.menu_datasets = MultipleVariablesMenu()
        self.setPopupMode(QToolButton.InstantPopup)
        self.setMenu(self.menu_datasets)
        self.setText("Variables: ")
