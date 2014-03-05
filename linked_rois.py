#!/usr/bin/python
# coding=utf-8

# Base Python File (linked_rois.py)
# Created: Wed Mar  5 15:52:16 2014
# Version: 1.0
#
# This Python script was developped by François-Xavier Thomas.
# You are free to copy, adapt or modify it.
# If you do so, however, leave my name somewhere in the credits, I'd appreciate it ;)
#
# (ɔ) François-Xavier Thomas <fx.thomas@gmail.com>

# Usage: linked_rois.py image.jpg

import pyqtgraph as pg
import numpy as np
import sys
import cv2
import math
from PyQt4 import QtGui, QtCore

##########################
# Create the main window #
##########################

# This should be pretty self-explanatory if you have worked with Qt/PyQt
# before. If not, consider reading a tutorial or a book.
app = QtGui.QApplication([])
win = QtGui.QWidget()
lay = QtGui.QGridLayout()
win.setLayout(lay)

# Create a the first GraphicsView, which will contain a ViewBox for easier
# image zoom/pan/rotate operations, which will in turn contain the ImageItem
# responsible for displaying the image.
pg1 = pg.GraphicsView()
vb1 = pg.ViewBox()
im1 = pg.ImageItem()
vb1.addItem(im1)
vb1.setAspectLocked(True)    # No aspect distortions
pg1.setBackground(None)      # Transparent background outside of the image
pg1.setCentralWidget(vb1)    # Autoscale the image when the window is rescaled

# Do the same for the second GraphicsView
pg2 = pg.GraphicsView()
vb2 = pg.ViewBox()
im2 = pg.ImageItem()
vb2.addItem(im2)
vb2.setAspectLocked(True)
pg2.setBackground(None)
pg2.setCentralWidget(vb2)

# Add both GraphicsView to the Qt window
lay.addWidget(pg1, 0, 0, 1, 1)
lay.addWidget(pg2, 0, 1, 1, 1)

########################
# Load the first image #
########################

# Read the image, and only take the first channel if it has multiple channels
image = cv2.imread(sys.argv[1] if len(sys.argv) >= 2 else "./images/test.jpg")
image = image if image.ndim == 2 else image[:, :, 0]

# Transpose and mirror the image because PyQtGraph doesn't seem to use and
# display image arrays the same way OpenCV usually does.
#
#                              J
#    O------------->J          ^.....
#    |              .          |    .
#    |    OpenCV    .          |    . PyQtGraph
#    V              .          |    .
#    I...............          O--->I
#
image = image.T[:, ::-1]

###########################
# Create the second image #
###########################

# Simulate another image with a perspective transformation relative to the
# first image, by rotating it by 45° around its center.

# Rotate it by 45°...
rotation = np.matrix([
    [np.cos(math.pi / 4), np.sin(math.pi / 4), 0.0],
    [-np.sin(math.pi / 4), np.cos(math.pi / 4), 0.0],
    [0., 0., 1.]])

# ...around its center
translation = np.matrix([
    [1.0, 0.0, image.shape[1] / 2],
    [0.0, 1.0, image.shape[0] / 2],
    [0.0, 0.0, 1.0]])

# Compose the two previous matrices and warp the image
warpmat = translation * rotation * translation.I
invwarp = warpmat.I
warpimage = cv2.warpPerspective(image, warpmat, (image.shape[1], image.shape[0]))

##################
# Display images #
##################

# Load the first image and autoscale it to be displayed entirely on the screen
im1.setImage(image)
vb1.autoRange()

# Do the same for the warped image
im2.setImage(warpimage)
vb2.autoRange()

################
# Add the ROIs #
################

size = min(image.shape) / 3
posx = (image.shape[0] - size) / 2
posy = (image.shape[1] - size) / 2

roi1 = pg.RectROI((posx, posy), size, pen=9)
roi2 = pg.RectROI((posx, posy), size, pen=9)

roi1.addScaleHandle([0, 0], [1, 1])
roi2.addScaleHandle([0, 0], [1, 1])
roi1.addScaleRotateHandle([1, 0], [1, 1])
roi2.addScaleRotateHandle([1, 0], [1, 1])

vb1.addItem(roi1)
vb2.addItem(roi2)


# This method will handle ROI region changes
def regionChanged(source):
    """This method will handle ROI region changes."""

    # In the following comments, the "source" will refer to the image whose ROI
    # was just changed by the user, and the "target" will refer to the other
    # image, whose ROI we now have to update so that both ROI show the same
    # image region.
    #
    # The (O), (OX) and (OY) notations will refer to the source or target ROI's
    # axes in their own coordinate systems.

    # Find the target ROI and retrieve the associated image items and
    # transformation matrix.
    target = roi2 if source == roi1 else roi1
    source_image = im1 if source == roi1 else im2
    target_image = im2 if source == roi1 else im1
    transform = warpmat if source == roi1 else invwarp

    # Make a list of points representing the source ROI
    sx, sy = source.size()
    source_points = [
        QtCore.QPointF(0.0, 0.0),   # (O)rigin of the source ROI's coordinates
        QtCore.QPointF(sx, 0.0),    # (OX) axis
        QtCore.QPointF(0.0, sy)]    # (OY) axis

    # These coordinates were in the source ROI's coordinate system (i.e.
    # rotated, scaled and translated wrt. the source image's origin). We now
    # need to convert them to the coordinate system of the source image.
    target_points = [source.mapToItem(source_image, h) for h in source_points]

    # Transform those points using the perspective transformation we defined
    # earlier to warp the first image into the second image.
    target_points = [np.array([p.y(), p.x(), 1.0]) for p in target_points]
    target_points = [p * transform.T for p in target_points]

    # Now that those points have been transformed, we need to transform them
    # back to the target image's coordinate system.
    target_points = [np.array(p).ravel() for p in target_points]
    target_points = [QtCore.QPointF(y / w, x / w) for x, y, w in target_points]

    # Using those transformed points, we are going to determine the position,
    # rotation and scale of the target ROI. Note that since both the target ROI
    # and the target image are children of the same ViewBox, the position of
    # the ROI is already defined in the target image's coordinate system.

    # The position (i.e. the origin) of the ROI is easy to determine : it's the
    # transformed position of the source origin.
    position = target_points[0]

    # We can also determine the target (OX) and (OY) vectors, thus defining the
    # X and Y axes for the target ROI.
    ux = target_points[1] - target_points[0]
    uy = target_points[2] - target_points[0]

    # Their norm gives us the size of the target ROI.
    ux = np.array([ux.x(), ux.y()])
    uy = np.array([uy.x(), uy.y()])
    sizex = np.linalg.norm(ux)
    sizey = np.linalg.norm(uy)

    # The rotation angle of the target ROI is the rotation angle of the (OX)
    # axis wrt. an horizontal line in the image's coordinate system.
    u0 = np.array([1.0, 0.0])
    rcos = np.dot(u0, ux / sizex)
    rsin = np.cross(u0, ux / sizex)
    rotation = math.acos(rcos)
    rotation = -rotation if rsin < 0 else rotation
    rotation = 180.0 * rotation / math.pi

    # Now that we have everything we need, we can Update the target ROI The
    # 'finish' and 'udpate' arguments are set to False to avoid emitting
    # other signals when modifying the target ROI.
    target.setRotation(rotation)
    target.setSize((sizex, sizey), finish=False, update=False)
    target.setPos(position, finish=False, update=False)

# Connect the ROI's regionChanged signals to the method above
roi1.sigRegionChanged.connect(regionChanged)
roi2.sigRegionChanged.connect(regionChanged)

# Run it once to load the ROI positions
regionChanged(roi1)

###################
# Show the window #
###################

win.showMaximized()
win.setWindowTitle("PyQtGraph Examples - Linked ROIs")
app.exec_()
