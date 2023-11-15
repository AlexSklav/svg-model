"""
This is a New BSD License.
https://www.opensource.org/licenses/bsd-license.php

Copyright (c) 2008-2009, Jonathan Hartley (tartley@tartley.com)
Copyright (c) 2012, Christian Fobel (christian@fobel.net)
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
following conditions are met:

    * Redistributions of source code must retain the above copyright notice, this list of conditions and the
    following disclaimer. * Redistributions in binary form must reproduce the above copyright notice, this list of
    conditions and the following disclaimer in the documentation and/or other materials provided with the
    distribution. * Neither the name of Jonathan Hartley nor the names of contributors may be used to endorse or
    promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."""
import warnings

from lxml import etree

from path_helpers import path

from .path_parser import PathParser, ParseError
from ..loop import Loop
from ..geo_path import Path


class SvgParseError(Exception):
    pass


def parse_warning(*args):
    filename, tag, message = args
    msg = f'Error parsing {filename}:{tag.sourceline}, {message}\n    {etree.tostring(tag)}'
    if filename:
        filename = filename.name
    warnings.warn(msg, RuntimeWarning)


class Svg:
    """
    Maintains an ordered list of paths, each one corresponding to a path tag
    from an SVG file. Creates a pylget Batch containing all these paths, for
    rendering as a single OpenGL GL_TRIANGLES indexed vert primitive.
    """

    def __init__(self):
        self.paths = {}
        self.color = (0, 0, 0)

    def add_path(self, id_: str, path_: Path) -> None:
        self.paths[id_] = path_

    def add_to_batch(self, batch):
        """
        Adds paths to the given batch object. They are all added as
        GL_TRIANGLES, so the batch will aggregate them all into a single OpenGL
        primitive.
        """
        for name in self.paths:
            svg_path = self.paths[name]
            svg_path.add_to_batch(batch)

    def get_bounding_box(self) -> Loop:
        points = list(self.all_verts())
        x_vals = [x for x, y in points]
        y_vals = [y for x, y in points]
        min_x, min_y = min(x_vals), min(y_vals)
        max_x, max_y = max(x_vals), max(y_vals)
        return Loop([(min_x, min_y), (min_x, max_y), (max_x, max_y),
                     (max_x, min_y)])

    def get_boundary(self) -> Path:
        if 'boundary' in self.paths:
            boundary = self.paths['boundary']
        else:
            boundary = Path([self.get_bounding_box()])
        return boundary

    def all_verts(self):
        for svg_path in self.paths.values():
            for loop in svg_path.loops:
                for vert in loop.verts:
                    yield vert


class SvgParser:
    """
    parse(filename) returns an Svg object, populated from the <path> tags in the file.
    """

    def __init__(self):
        self.filename = None

    def parse_file(self, filename: str, on_error=None) -> Svg:
        self.filename = path(filename)
        xml_root = etree.parse(self.filename)
        return self.parse(xml_root, on_error)

    def parse(self, xml_root, on_error=None) -> Svg:
        """
        Parse all <path> elements from xml_root.
        """
        svg = Svg()
        svg_namespace = {'svg': 'http://www.w3.org/2000/svg'}
        path_tags = xml_root.xpath('(/svg:svg|/svg:svg/svg:g)/svg:path',
                                   namespaces=svg_namespace)
        parser = PathParser()
        for path_tag in path_tags:
            try:
                id, svg_path = parser.parse(path_tag)
                if svg_path.loops:
                    svg.add_path(id, svg_path)
            except ParseError as why:
                filename = getattr(self, 'filename', None)
                args = (filename, path_tag, why.message)
                if on_error:
                    on_error(*args)
                else:
                    raise SvgParseError(*args)

        if svg.paths:
            x, y = svg.get_boundary().get_center()
            for svg_path in svg.paths.values():
                svg_path.offset(-x, -y)
        return svg
