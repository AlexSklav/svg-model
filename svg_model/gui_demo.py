"""
This is a New BSD License.
http://www.opensource.org/licenses/bsd-license.php

Copyright (c) 2012, Christian Fobel (christian@fobel.net)
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
    * Neither the name of Jonathan Hartley nor the names of contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import sys
import pymunk

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QPainterPath

from svg_model.path_group import PathGroup
from svg_model.body_group import BodyGroup



class CustomWidget(QWidget):
    def __init__(self, path_group_, body_group_):
        super().__init__()
        self.path_group = path_group_
        self.body_group = body_group_
        self.setMinimumSize(640, 480)
        self.clicked_coords = None

    def mousePressEvent(self, event):
        x, y, width, height = self.path_group.get_bounding_box()
        coords = self.translate([(event.x(), event.y())], -width / 2., -height / 2.0)[0]
        shape = self.body_group.space.point_query_nearest(coords, max_distance=0, shape_filter=pymunk.ShapeFilter())

        if shape:
            print(self.body_group.get_name(shape.shape.body))

    def paintEvent(self, event):
        painter = QPainter(self)
        self.draw_paths(painter)

    def translate(self, coords, x, y):
        return [(c[0] + x, c[1] + y) for c in coords]

    def draw_path(self, painter, p):
        color = QColor(*p.color) if p.color else QColor(Qt.black)
        painter.setBrush(color)
        for loop in p.loops:
            path = QPainterPath()
            path.moveTo(*loop.verts[0])
            for v in loop.verts[1:]:
                path.lineTo(*v)
            path.closeSubpath()
            painter.drawPath(path)

    def draw_paths(self, painter):
        x, y, width, height = self.path_group.get_bounding_box()
        painter.translate(width / 2., height / 2.)
        for p in self.body_group.paths.values():
            self.draw_path(painter, p)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    path_group = PathGroup.load_svg('circles.svg')
    body_group = BodyGroup(path_group.paths)

    window = QMainWindow()
    central_widget = CustomWidget(path_group, body_group)
    window.setCentralWidget(central_widget)
    window.show()

    sys.exit(app.exec_())
