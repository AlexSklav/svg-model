# coding: utf-8
import re
import warnings
from typing import List, Dict, Optional, Tuple, Union

from .data_frame import get_bounding_boxes

from io import StringIO
from lxml import etree
import pandas as pd
import pint  # Unit conversion from inches to mm

from ._version import get_versions

__version__ = get_versions()['version']
del get_versions

XHTML_NAMESPACE = "http://www.w3.org/2000/svg"
NSMAP = {'svg': XHTML_NAMESPACE}
INKSCAPE_NSMAP = NSMAP.copy()
INKSCAPE_NSMAP['inkscape'] = 'https://www.inkscape.org/namespaces/inkscape'

# Convert Inkscape pixels-per-inch (PPI) to pixels-per-mm (PPmm).
ureg = pint.UnitRegistry()

INKSCAPE_PPI = 90
INKSCAPE_PPmm = INKSCAPE_PPI / (1 * ureg.inch).to('mm')

float_pattern = r'[+-]?\d+(\.\d+)?([eE][+-]?\d+)?'  # 2, 1.23, 23e39, 1.23e-6, etc.
cre_path_command = re.compile(rf'((?P<xy_command>[ML])\s+(?P<x>{float_pattern}),\s*(?P<y>{float_pattern})\s*|'
                              rf'(?P<x_command>[H])\s+(?P<hx>{float_pattern})\s*|'
                              rf'(?P<y_command>[V])\s+(?P<vy>{float_pattern})\s*|'
                              rf'(?P<command>[Z]\s*|'
                              rf'(?P<curve_command>[CQ])\s+'
                              rf'((?P<curve_x1>{float_pattern}),\s*(?P<curve_y1>{float_pattern}),\s*'
                              rf'(?P<curve_x2>{float_pattern}),\s*(?P<curve_y2>{float_pattern}),\s*)?'
                              rf'(?P<curve_x>{float_pattern}),\s*(?P<curve_y>{float_pattern})\s*))'
                              rf'|'
                              rf'(?P<relative_command>[lhv])\s+(?P<relative_values>(?:{float_pattern}\s*,?\s*)+)'
                              )


def shape_path_points(svg_path_d: str) -> List[Dict[str, float]]:
    """
    Extracts and returns a list of coordinates of points found in the SVG path.

    Parameters
    ----------
    svg_path_d : str
        The "d" attribute of an SVG "path" element.

    Returns
    -------
    List[Dict[str, float]]
        A list of dictionaries, where each dictionary contains the "x" and "y"
        coordinates of a point.

    Notes
    -----
    This function currently supports the following SVG path commands:
    - M: Move to (absolute)
    - L: Line to (absolute)
    - H: Horizontal line to (absolute)
    - V: Vertical line to (absolute)
    - Z: Close path (absolute)
    - l: Line to (relative)
    - h: Horizontal line to (relative)
    - v: Vertical line to (relative)

    Each point is represented by a dictionary with keys "x" and "y".
    """

    # TODO Add support for relative commands, e.g., `l, h, v`.

    def _update_path_state(path_state: Dict[str, float], match: re.Match) -> Dict[str, float]:
        if match.group('xy_command'):
            for dim_j in 'xy':
                path_state[dim_j] = float(match.group(dim_j))
            if path_state.get('x0') is None:
                for dim_j in 'xy':
                    path_state[f'{dim_j}0'] = path_state[dim_j]
        elif match.group('x_command'):
            path_state['x'] = float(match.group('hx'))
        elif match.group('y_command'):
            path_state['y'] = float(match.group('vy'))
        elif match.group('command') == 'Z':
            for dim_j in 'xy':
                path_state[dim_j] = path_state[f'{dim_j}0']
        elif match.group('relative_command'):
            relative_command = match.group('relative_command')
            relative_values = [float(v) for v in re.findall(float_pattern, match.group('relative_values'))]

            if relative_command == 'l':
                path_state['x'] += relative_values[0]
                path_state['y'] += relative_values[1]
            elif relative_command == 'h':
                path_state['x'] += relative_values[0]
            elif relative_command == 'v':
                path_state['y'] += relative_values[0]
        elif match.group('curve_command'):
            curve_command = match.group('curve_command')
            curve_values = [float(v) for v in re.findall(float_pattern, match.group('curve_values'))]

            if curve_command == 'C':
                # Handle cubic Bezier curve command
                pass

            elif curve_command == 'Q':
                # Handle quadratic Bezier curve command
                pass

            raise NotImplementedError('Bezier curve commands are not supported')
        return path_state

    # Some commands in a SVG path element `"d"` attribute require previous state.
    #
    # For example, the `"H"` command is a horizontal move, so the previous
    # ``y`` position is required to resolve the new `(x, y)` position.
    #
    # Iterate through the commands in the `"d"` attribute in order and maintain
    # the current path position in the `path_state` dictionary.
    path_state = {'x': None, 'y': None}
    return [{k: v for k, v in _update_path_state(path_state, match_i).items()
             if k in 'xy'} for match_i in cre_path_command.finditer(svg_path_d)]


def svg_shapes_to_df(svg_source: str, xpath: str = '//svg:path | //svg:polygon',
                     namespaces: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """
    Construct a data frame with one row per vertex for all shapes in
    :data:`svg_source``.

    Arguments
    ---------
    svg_source : str or file-like
        A file path, URI, or file-like object.
    xpath : str, optional
        XPath path expression to select shape nodes.

        By default, all ``svg:path`` and ``svg:polygon`` elements are selected.
    namespaces : dict, optional
        Key/value mapping of XML namespaces.

    Returns
    -------
    pandas.DataFrame
        Frame with one row per vertex for all shapes in :data:`svg_source`,
        with the following columns:
         - ``vertex_i``: The index of the vertex within the corresponding
           shape.
         - ``x``: The x-coordinate of the vertex.
         - ``y``: The y-coordinate of the vertex.
         - other: attributes of the SVG shape element (e.g., ``id``, ``fill``,
            etc.)
    """
    if namespaces is None:
        namespaces = INKSCAPE_NSMAP

    e_root = etree.parse(svg_source)
    frames = []
    attribs_set = set()

    # Get list of attributes that are set in any of the shapes (not including
    # the `svg:path` `"d"` attribute or the `svg:polygon` `"points"`
    # attribute).
    #
    # This, for example, collects attributes such as:
    #
    #  - `fill`, `stroke` (as part of `"style"` attribute)
    #  - `"transform"`: matrix, scale, etc.
    for shape_i in e_root.xpath(xpath, namespaces=namespaces):
        attribs_set.update(list(shape_i.attrib.keys()))

    attribs_set.discard('d')
    attribs_set.discard('points')
    attribs = sorted(attribs_set)
    # Always add 'id' attribute as first attribute.
    attribs.insert(0, 'id')

    for shape_i in e_root.xpath(xpath, namespaces=namespaces):
        # Gather shape attributes from SVG element.
        base_fields = [shape_i.attrib.get(k, None) for k in attribs]

        if shape_i.tag == f'{{{XHTML_NAMESPACE}}}path':
            # Decode `svg:path` vertices from [`"d"`][1] attribute.
            #
            # [1]: https://developer.mozilla.org/en-US/docs/Web/SVG/Attribute/d
            points_i = [base_fields + [i] + [point_i.get(k) for k in 'xy']
                        for i, point_i in enumerate(shape_path_points(shape_i.attrib['d']))]
        elif shape_i.tag == f'{{{XHTML_NAMESPACE}}}polygon':
            # Decode `svg:polygon` vertices from [`"points"`][2] attribute.
            #
            # [2]: https://developer.mozilla.org/en-US/docs/Web/SVG/Attribute/points
            points_i = [base_fields + [i] + list(map(float, v.split(',')))
                        for i, v in enumerate(shape_i.attrib['points'].strip().split(' '))]
        else:
            warnings.warn(f'Unsupported shape tag type: {shape_i.tag}')
            continue
        frames.extend(points_i)
    if not frames:
        # There were no shapes found, so set `frames` list to `None` to allow
        # an empty data frame to be created.
        frames = None
    return pd.DataFrame(frames, columns=attribs + ['vertex_i', 'x', 'y'])


def compute_shape_centers(df_shapes: pd.DataFrame, shape_i_column: str, inplace: bool = False) -> pd.DataFrame:
    """
    Compute the center point of each polygon shape, and the offset of each
    vertex to the corresponding polygon center point.

    Parameters
    ----------
    df_shapes : pandas.DataFrame
        Table of polygon shape vertices (one row per vertex).

        Must have at least the following columns:
         - ``vertex_i``: The index of the vertex within the corresponding
           shape.
         - ``x``: The x-coordinate of the vertex.
         - ``y``: The y-coordinate of the vertex.
    shape_i_column : str or list, optional
        Table rows with the same value in the :data:`shape_i_column` column are
        grouped together as a shape.
    inplace : bool, optional
        If ``True``, center coordinate columns are added directly to the input
        frame.

        Otherwise, center coordinate columns are added to copy of the input
        frame.

    Returns
    -------
    pandas.DataFrame
        Input frame with the following additional columns:
         - ``x_center``/``y_center``: Absolute coordinates of shape center.
         - ``x_center_offset``/``y_center_offset``:
             * Coordinates of each vertex coordinate relative to shape center.
    """
    if not isinstance(shape_i_column, bytes):
        raise KeyError('Shape index must be a single column.')

    if not inplace:
        df_shapes = df_shapes.copy()

    # Get coordinates of the center of each path.
    df_bounding_boxes = get_bounding_boxes(df_shapes, shape_i_column)
    path_centers = (df_bounding_boxes[['x', 'y']] + .5 *
                    df_bounding_boxes[['width', 'height']].values)
    df_shapes['x_center'] = path_centers.x[df_shapes[shape_i_column]].values
    df_shapes['y_center'] = path_centers.y[df_shapes[shape_i_column]].values

    # Calculate the coordinates of each path vertex relative to center point of
    # path.
    center_offset = df_shapes[['x', 'y']] - df_shapes[['x_center', 'y_center']].values
    return df_shapes.join(center_offset, rsuffix='_center_offset')


def scale_points(df_points: pd.DataFrame, scale: float = INKSCAPE_PPmm.magnitude,
                 inplace: bool = False) -> pd.DataFrame:
    """
    Translate points such that bounding box is anchored at (0, 0) and scale
    ``x`` and ``y`` columns of input frame by specified :data:`scale`.

    Parameters
    ----------
    df_points : pandas.DataFrame
        Table of ``x``/``y`` point positions.

        Must have at least the following columns:
         - ``x``: x-coordinate
         - ``y``: y-coordinate
    scale : float, optional
        Factor to scale points by.

        By default, scale to millimeters based on Inkscape default of 90
        pixels-per-inch.
    scale : float, optional
        Factor to scale points by.
    inplace : bool, optional
        If ``True``, input frame will be modified.

        Otherwise, the scaled points are written to a new frame, leaving the
        input frame unmodified.

    Returns
    -------
    pandas.DataFrame
        Input frame with the points translated such that bounding box is
        anchored at (0, 0) and ``x`` and ``y`` values scaled by specified
        :data:`scale`.
    """
    if not inplace:
        df_points = df_points.copy()

    # Offset device, such that all coordinates are >= 0.
    df_points.x -= df_points.x.min()
    df_points.y -= df_points.y.min()

    # Scale path coordinates.
    df_points.x /= scale
    df_points.y /= scale

    return df_points


def scale_to_fit_a_in_b(a_shape: pd.Series, b_shape: pd.Series) -> float:
    """
    Return scale factor (scalar float) to fit `a_shape` into `b_shape` while
    maintaining aspect ratio.

    Arguments
    ---------
    a_shape, b_shape : pandas.Series
        Input shapes containing numeric `width` and `height` values.

    Returns
    -------
    float
        Scale factor to fit :data:`a_shape` into :data:`b_shape` while
        maintaining aspect ratio.
    """
    # Normalize the shapes to allow comparison.
    a_shape_normal = a_shape / a_shape.max()
    b_shape_normal = b_shape / b_shape.max()

    if a_shape_normal.width > b_shape_normal.width:
        a_shape_normal *= b_shape_normal.width / a_shape_normal.width

    if a_shape_normal.height > b_shape_normal.height:
        a_shape_normal *= b_shape_normal.height / a_shape_normal.height

    return a_shape_normal.max() * b_shape.max() / a_shape.max()


def fit_points_in_bounding_box(df_points: pd.DataFrame, bounding_box: pd.Series,
                               padding_fraction: float = 0) -> pd.DataFrame:
    """
    Return data frame with ``x``, ``y`` columns scaled to fit points from
    :data:`df_points` to fill :data:`bounding_box` while maintaining aspect
    ratio.

    Arguments
    ---------
    df_points : pandas.DataFrame
        A frame with at least the columns ``x`` and ``y``, containing one row
        per point.
    bounding_box: pandas.Series
        A `pandas.Series` containing numeric `width` and `height` values.
    padding_fraction : float
        Fraction of padding to add around points.

    Returns
    -------
    pandas.DataFrame
        Input frame with the points with ``x`` and ``y`` values scaled to fill
        :data:`bounding_box` while maintaining aspect ratio.
    """
    df_scaled_points = df_points.copy()
    offset, padded_scale = fit_points_in_bounding_box_params(df_points, bounding_box, padding_fraction)
    df_scaled_points[['x', 'y']] *= padded_scale
    df_scaled_points[['x', 'y']] += offset
    return df_scaled_points


def fit_points_in_bounding_box_params(df_points: pd.DataFrame, bounding_box: pd.Series,
                                      padding_fraction: float = 0, ) -> Tuple[pd.Series, float]:
    """
    Return offset and scale factor to scale ``x``, ``y`` columns of
    :data:`df_points` to fill :data:`bounding_box` while maintaining aspect
    ratio.

    Arguments
    ---------
    df_points : pandas.DataFrame
        A frame with at least the columns ``x`` and ``y``, containing one row
        per point.
    bounding_box: pandas.Series
        A `pandas.Series` containing numeric `width` and `height` values.
    padding_fraction : float
        Fraction of padding to add around points.

    Returns
    -------
    (offset, scale) : (pandas.Series, float)
        Offset translation and scale required to fit all points in
        :data:`df_points` to fill :data:`bounding_box` while maintaining aspect
        ratio.

        :data:`offset` contains ``x`` and ``y`` values for the offset.
    """
    width = df_points.x.max()
    height = df_points.y.max()

    points_bbox = pd.Series([width, height], index=['width', 'height'])
    fill_scale = 1 - 2 * padding_fraction
    assert fill_scale > 0

    scale = scale_to_fit_a_in_b(points_bbox, bounding_box)

    padded_scale = scale * fill_scale
    offset = .5 * (bounding_box - points_bbox * padded_scale)
    offset.index = ['x', 'y']
    return offset, padded_scale


def remove_layer(svg_source: str, layer_name: Union[str, List[str]]) -> StringIO:
    """
    Remove layer(s) from SVG document.

    Arguments
    ---------
    svg_source : str or file-like
        A file path, URI, or file-like object.
    layer_name : str or list
        Layer name or list of layer names to remove from SVG document.

    Returns
    -------
    StringIO.StringIO
        File-like object containing XML document with layer(s) removed.
    """
    # Parse input file.
    xml_root = etree.parse(svg_source)
    svg_root = xml_root.xpath('/svg:svg', namespaces=INKSCAPE_NSMAP)[0]

    if isinstance(layer_name, str):
        layer_name = [layer_name]

    for layer_name_i in layer_name:
        # Remove existing layer from source, in-memory XML (source file remains unmodified).
        layer_xpath = f'//svg:g[@inkscape:label="{layer_name_i}"]'
        layer_groups = svg_root.xpath(layer_xpath, namespaces=INKSCAPE_NSMAP)

        if layer_groups:
            for g in layer_groups:
                g.getparent().remove(g)

    # Write result to `StringIO`.
    output = StringIO()
    xml_root.write(output)
    output.seek(0)
    return output
