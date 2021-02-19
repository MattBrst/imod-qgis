#%%
from __future__ import division

from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
from pyqtgraph import functions as fn
from pyqtgraph.graphicsItems.GraphicsObject import GraphicsObject
from pyqtgraph.Point import Point
from pyqtgraph import getConfigOption
from pyqtgraph.graphicsItems.GradientEditorItem import Gradients # List of colormaps
from pyqtgraph.colormap import ColorMap
#%%
try:
    from collections.abc import Callable
except ImportError:
    # fallback for python < 3.3
    from collections import Callable

__all__ = ['PColorMeshItem']


class PColorMeshItem(GraphicsObject):
    """
    **Bases:** :class:`GraphicsObject <pyqtgraph.GraphicsObject>`
    """


    def __init__(self, *args, **kwargs):
        """
        Create a pseudocolor plot with convex polygons.
        Modified from: https://github.com/pyqtgraph/pyqtgraph/blob/5eb671217c295178de255b1fece56379cdef8235/pyqtgraph/graphicsItems/PColorMeshItem.py

        Call signature:

        ``PColorMeshItem([x, y,] z, **kwargs)``

        x and y can be used to specify the corners of the quadrilaterals.
        z must be used to specified to color of the quadrilaterals.

        Parameters
        ----------
        x, y : np.ndarray, optional, default None
            2D array containing the coordinates of the polygons
        z : np.ndarray
            2D array containing the value which will be maped into the polygons
            colors.
            If x and y is None, the polygons will be displaced on a grid
            otherwise x and y will be used as polygons vertices coordinates as::

                (x[i+1, j], y[i+1, j])           (x[i+1, j+1], y[i+1, j+1])
                                    +---------+
                                    | z[i, j] |
                                    +---------+
                    (x[i, j], y[i, j])           (x[i, j+1], y[i, j+1])

            "ASCII from: <https://matplotlib.org/3.2.1/api/_as_gen/
                         matplotlib.pyplot.pcolormesh.html>".
        colorramp : QgsColorRamp
            Colorramp used to map the z value to colors.
        edgecolors : dict, default None
            The color of the edges of the polygons.
            Default None means no edges.
            The dict may contains any arguments accepted by :func:`mkColor() <pyqtgraph.mkColor>`.
            Example:

                ``mkPen(color='w', width=2)``

        antialiasing : bool, default False
            Whether to draw edgelines with antialiasing.
            Note that if edgecolors is None, antialiasing is always False.
        """

        GraphicsObject.__init__(self)

        self.qpicture = None  ## rendered picture for display
        
        self.axisOrder = getConfigOption('imageAxisOrder')

        if 'edgecolors' in kwargs.keys():
            self.edgecolors = kwargs['edgecolors']
        else:
            self.edgecolors = None

        if 'antialiasing' in kwargs.keys():
            self.antialiasing = kwargs['antialiasing']
        else:
            self.antialiasing = False

        if 'colorramp' not in kwargs.keys():
            raise ValueError("ColorRamp not provided")
        else:
            self.colorramp = kwargs['colorramp']
        
        # If some data have been sent we directly display it
        if len(args)>0:
            self.setData(*args)


    def _prepareData(self, args):
        """
        Check the shape of the data.
        Return a set of 2d array x, y, z ready to be used to draw the picture.
        """

        # User didn't specified data
        if len(args)==0:

            self.x = None
            self.y = None
            self.z = None
            
        # User only specified z
        elif len(args)==1:
            # If x and y is None, the polygons will be displaced on a grid
            x = np.arange(0, args[0].shape[0]+1, 1)
            y = np.arange(0, args[0].shape[1]+1, 1)
            self.x, self.y = np.meshgrid(x, y, indexing='ij')
            self.z = args[0]

        # User specified x, y, z
        elif len(args)==3:

            # Shape checking
            if args[0].shape[0] != args[2].shape[0]+1 or args[0].shape[1] != args[2].shape[1]+1:
                raise ValueError('The dimension of x should be one greater than the one of z')
            
            if args[1].shape[0] != args[2].shape[0]+1 or args[1].shape[1] != args[2].shape[1]+1:
                raise ValueError('The dimension of y should be one greater than the one of z')
        
            self.x = args[0]
            self.y = args[1]
            self.z = args[2]

        else:
            ValueError('Data must been sent as (z) or (x, y, z)')


    def setData(self, *args):
        """
        Set the data to be drawn.

        Parameters
        ----------
        x, y : np.ndarray, optional, default None
            2D array containing the coordinates of the polygons
        z : np.ndarray
            2D array containing the value which will be maped into the polygons
            colors.
            If x and y is None, the polygons will be displaced on a grid
            otherwise x and y will be used as polygons vertices coordinates as::
                
                (x[i+1, j], y[i+1, j])           (x[i+1, j+1], y[i+1, j+1])
                                    +---------+
                                    | z[i, j] |
                                    +---------+
                    (x[i, j], y[i, j])           (x[i, j+1], y[i, j+1])

            "ASCII from: <https://matplotlib.org/3.2.1/api/_as_gen/
                         matplotlib.pyplot.pcolormesh.html>".
        """

        # Prepare data
        cd = self._prepareData(args)

        # Has the view bounds changed
        shapeChanged = False
        if self.qpicture is None:
            shapeChanged = True
        elif len(args)==1:
            if args[0].shape[0] != self.x[:,1][-1] or args[0].shape[1] != self.y[0][-1]:
                shapeChanged = True
        elif len(args)==3:
            if np.any(self.x != args[0]) or np.any(self.y != args[1]):
                shapeChanged = True

        self.qpicture = QtGui.QPicture()
        p = QtGui.QPainter(self.qpicture)
        # We set the pen of all polygons once
        if self.edgecolors is None:
            p.setPen(fn.mkPen(QtGui.QColor(0, 0, 0, 0)))
        else:
            p.setPen(fn.mkPen(self.edgecolors))
            if self.antialiasing:
                p.setRenderHint(QtGui.QPainter.Antialiasing)
                

        ## Normalize data for colorramp
        norm  = self.z - np.nanmin(self.z)
        norm = norm/np.nanmax(norm)
        
        # Go through all the data and draw the polygons accordingly
        for xi in range(self.z.shape[0]):
            for yi in range(self.z.shape[1]):
                
                # Set the color of the polygon first
                norm_value = norm[xi][yi]
                if np.isnan(norm_value):
                    continue #Value is NoData
                color = self.colorramp.color(value=norm_value)

                p.setBrush(fn.mkBrush(color))

                polygon = QtGui.QPolygonF(
                    [QtCore.QPointF(self.x[xi][yi],     self.y[xi][yi]),
                     QtCore.QPointF(self.x[xi+1][yi],   self.y[xi+1][yi]),
                     QtCore.QPointF(self.x[xi+1][yi+1], self.y[xi+1][yi+1]),
                     QtCore.QPointF(self.x[xi][yi+1],   self.y[xi][yi+1])]
                )

                # DrawConvexPlygon is faster
                p.drawConvexPolygon(polygon)


        p.end()
        self.update()

        self.prepareGeometryChange()
        if shapeChanged:
            self.informViewBoundsChanged()



    def paint(self, p, *args):
        if self.z is None:
            return

        p.drawPicture(0, 0, self.qpicture)



    def setBorder(self, b):
        self.border = fn.mkPen(b)
        self.update()



    def width(self):
        if self.x is None:
            return None
        return np.max(self.x)



    def height(self):
        if self.y is None:
            return None
        return np.max(self.y)




    def boundingRect(self):
        if self.qpicture is None:
            return QtCore.QRectF(0., 0., 0., 0.)
        return QtCore.QRectF(self.qpicture.boundingRect())
