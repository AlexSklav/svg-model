"""
This is a New BSD License.
http://www.opensource.org/licenses/bsd-license.php

Copyright (c) 2008-2009, Jonathan Hartley (tartley@tartley.com)
Copyright (c) 2012, Christian Fobel (christian@fobel.net)
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
    * Neither the name of Jonathan Hartley nor the names of contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
from itertools import chain

from .loop import Loop


class Path:
    """
    A Path is a list of loops.
    """

    def __init__(self, loops: list[Loop]):
        self.loops = [loop if isinstance(loop, Loop) else Loop(loop) for loop in loops]

    def get_area(self) -> float:
        return sum(loop.get_area() for loop in self.loops)

    def get_mass(self) -> float:
        return sum(loop.get_mass() for loop in self.loops)

    def get_center(self) -> tuple[float, float]:
        x, y, width, height = self.get_bounding_box()
        return x + width / 2.0, y + height / 2.0

    def get_centroid(self) -> tuple[float, float]:
        x, y = 0.0, 0.0

        for loop in self.loops:
            loop_x, loop_y = loop.get_centroid()
            x += loop_x * loop.get_mass()
            y += loop_y * loop.get_mass()

        area = self.get_area()
        if area > 0:
            x /= area
            y /= area
        return x, y

    def get_moment(self) -> float:
        return sum(loop.get_moment() for loop in self.loops)

    def offset(self, x: float, y: float):
        for loop in self.loops:
            loop.offset(x, y)

    def offset_to_origin(self) -> None:
        x, y = self.get_centroid()
        for loop in self.loops:
            loop.offset(-x, -y)

    def get_bounding_box(self) -> tuple[float, float, float, float]:
        x_vals = list(chain(*[list(zip(*loop.verts))[0] for loop in self.loops]))
        y_vals = list(chain(*[list(zip(*loop.verts))[1] for loop in self.loops]))
        min_x, min_y = min(x_vals), min(y_vals)
        max_x, max_y = max(x_vals), max(y_vals)
        return min_x, min_y, max_x - min_x, max_y - min_y


class ColoredPath(Path):

    def __init__(self, loops: list[Loop]):
        super().__init__(loops)
        self.color = (0, 0, 0)

    def _serialize_verts(self, triangles):
        for vert in triangles:
            yield vert[0]
            yield vert[1]
