# coding: utf-8
# Copyright 2015
# Jerry Zhou <jerryzhou@hotmail.ca> and Christian Fobel <christian@fobel.net>
import re
import warnings
from typing import Dict, Tuple, Optional

import pandas as pd
import numpy as np

from io import StringIO
from lxml import etree

from . import INKSCAPE_NSMAP
from .draw import draw_lines_svg_layer as _draw_lines_svg_layer
from .shapes_canvas import ShapesCanvas


def extend_shapes(df_shapes: pd.DataFrame, axis: str, distance: float) -> pd.DataFrame:
    """
    Extend shape/polygon outline away from polygon center point by absolute
    distance.
    """
    df_shapes_i = df_shapes.copy()
    offsets = df_shapes_i[f'{axis}_center_offset'].copy()
    offsets[offsets < 0] -= distance
    offsets[offsets >= 0] += distance
    df_shapes_i[axis] = df_shapes_i[f'{axis}_center'] + offsets
    return df_shapes_i


def extract_adjacent_shapes(df_shapes: pd.DataFrame, shape_i_column: str, extend: float = 0.5) -> pd.DataFrame:
    """
    Generate list of connections between "adjacent" polygon shapes based on
    geometrical "closeness".

    Parameters
    ----------
    df_shapes : pandas.DataFrame
        Table of polygon shape vertices (one row per vertex).

        Table rows with the same value in the :data:`shape_i_column` column
        are grouped together as a polygon.
    shape_i_column : str or list[str]
        Column name(s) that identify the polygon each row belongs to.
    extend : float, optional
        Extend ``x``/``y`` coords by the specified number of absolute units
        from the center point of each polygon.
        Each polygon is stretched independently in the ``x`` and ``y`` direction.
        In each direction, a polygon considered adjacent to all polygons that
        are overlapped by the extended shape.

    Returns
    -------
    pandas.DataFrame
        Adjacency list as a frame containing the columns ``source`` and
        ``target``.

        The ``source`` and ``target`` of each adjacency connection is ordered
        such that the ``source`` is less than the ``target``.
    """
    # Find corners of each solid shape outline.
    # Extend x coords by abs units
    df_scaled_x = extend_shapes(df_shapes, 'x', extend)
    # Extend y coords by abs units
    df_scaled_y = extend_shapes(df_shapes, 'y', extend)

    df_corners = df_shapes.groupby(shape_i_column).agg({'x': ['min', 'max'],
                                                        'y': ['min', 'max']})

    # Find adjacent electrodes
    row_list = []

    for shapeNumber in df_shapes[shape_i_column].drop_duplicates():
        df_stretched = df_scaled_x[df_scaled_x[shape_i_column].isin([shapeNumber])]
        xmin_x, xmax_x, ymin_x, ymax_x = (df_stretched.x.min(), df_stretched.x.max(),
                                          df_stretched.y.min(), df_stretched.y.max())
        df_stretched = df_scaled_y[df_scaled_y[shape_i_column].isin([shapeNumber])]
        xmin_y, xmax_y, ymin_y, ymax_y = (df_stretched.x.min(), df_stretched.x.max(),
                                          df_stretched.y.min(), df_stretched.y.max())

        adjacent = df_corners[((df_corners.x['min'] < xmax_x) & (df_corners.x['max'] >= xmax_x)
                               | (df_corners.x['min'] < xmin_x) & (df_corners.x['max'] >= xmin_x))
                              & (df_corners.y['min'] < ymax_x) & (df_corners.y['max'] > ymin_x) |

                              ((df_corners.y['min'] < ymax_y) & (df_corners.y['max'] >= ymax_y)
                               | (df_corners.y['min'] < ymin_y) & (df_corners.y['max'] >= ymin_y))
                              & ((df_corners.x['min'] < xmax_y) & (df_corners.x['max'] > xmin_y))
                              ].index.values

        for shape in adjacent:
            temp_dict = {'source': shapeNumber, 'target': shape}
            reverse_dict = {'source': shape, 'target': shapeNumber}

            if reverse_dict not in row_list:
                row_list.append(temp_dict)

    df_connected = (pd.DataFrame(row_list)[['source', 'target']]
                    .sort_index(axis=1, ascending=True)
                    .sort_values(['source', 'target']))
    return df_connected


def get_adjacency_matrix(df_connected: pd.DataFrame) -> Tuple[np.ndarray, pd.Series, pd.Series]:
    """
    Return matrix where $a_{i,j} = 1$ indicates polygon $i$ is connected to
    polygon $j$.

    Also, return mapping (and reverse mapping) from original keys in
    `df_connected` to zero-based integer index used for matrix rows and
    columns.
    """
    sorted_path_keys = np.sort(np.unique(df_connected[['source', 'target']].values.ravel()))
    indexed_paths = pd.Series(sorted_path_keys)
    path_indexes = pd.Series(indexed_paths.index, index=sorted_path_keys)

    adjacency_matrix = np.zeros((path_indexes.shape[0],) * 2, dtype=int)
    for i_key, j_key in df_connected[['source', 'target']].values:
        i, j = path_indexes.loc[[i_key, j_key]]
        adjacency_matrix[i, j] = 1
        adjacency_matrix[j, i] = 1
    return adjacency_matrix, indexed_paths, path_indexes


def extract_connections(svg_source: str, shapes_canvas: ShapesCanvas, line_layer: str = 'Connections',
                        line_xpath: Optional[str] = None, path_xpath: Optional[str] = None,
                        namespaces: Optional[Dict] = None) -> pd.DataFrame:
    """
    Load all ``<svg:line>`` elements and ``<svg:path>`` elements from a layer
    of an SVG source.  For each element, if endpoints overlap distinct shapes
    in :data:`shapes_canvas`, add connection between overlapped shapes.

    Parameters
    ----------
    svg_source : filepath
        Input SVG file containing connection lines.
    shapes_canvas : shapes_canvas.ShapesCanvas
        Shapes canvas containing shapes to compare against connection
        endpoints.
    line_layer : str
        Name of layer in SVG containing connection lines.
    line_xpath : str
        XPath string to iterate through connection lines.
    path_xpath : str
        XPath string to iterate through connection paths.
    namespaces : dict
        SVG namespaces (compatible with :func:`etree.parse`).

    Returns
    -------
    pandas.DataFrame
        Each row corresponds to connection between two shapes in
        :data:`shapes_canvas`, denoted ``source`` and ``target``.

    Version log
    -----------
    .. versionchanged:: 0.6.post1
        Allow both ``<svg:line>`` *and* ``<svg:path>`` instances to denote
        connected/adjacent shapes.

    .. versionadded:: 0.6.post1
        :data:`path_xpath`
    """
    if namespaces is None:
        # Inkscape namespace is required to match SVG elements as well as
        # Inkscape-specific SVG tags and attributes (e.g., `inkscape:label`).
        namespaces = INKSCAPE_NSMAP

    # Parse SVG source.
    e_root = etree.parse(svg_source)
    # List to hold records of form: `[<id>, <x1>, <y1>, <x2>, <y2>]`.
    frames = []
    coords_columns = ['x1', 'y1', 'x2', 'y2']

    if line_xpath is None:
        # Define a query to look for `svg:line` elements in the top level of layer of
        # SVG specified to contain connections.
        line_xpath = ("//svg:g[@inkscape:label='%s']/svg:line" % line_layer)

    for line_i in e_root.xpath(line_xpath, namespaces=namespaces):
        line_i_dict = dict(line_i.items())
        values = [line_i_dict.get('id', None)] + [float(line_i_dict[k]) for k in coords_columns]
        frames.append(values)

    cre_path_ends = re.compile(r'^\s*M\s*(?P<start_x>\d+(\.\d+)?),\s*(?P<start_y>\d+(\.\d+)?)'
                               r'.*((L\s*(?P<end_x>\d+(\.\d+)?),\s*(?P<end_y>\d+(\.\d+)?))|'
                               r'(V\s*(?P<end_vy>\d+(\.\d+)?))|'
                               r'(H\s*(?P<end_hx>\d+(\.\d+)?)))\D*$')

    if path_xpath is None:
        path_xpath = f"//svg:g[@inkscape:label='{line_layer}']/svg:path"

    for path_i in e_root.xpath(path_xpath, namespaces=namespaces):
        path_i_dict = dict(path_i.items())
        match_i = cre_path_ends.match(path_i_dict['d'])
        if match_i:
            # Connection `svg:path` matched required format.  Extract start and
            # end coordinates.
            match_dict_i = match_i.groupdict()
            if match_dict_i['end_vy']:
                # Path ended with vertical line
                match_dict_i['end_x'] = match_dict_i['start_x']
                match_dict_i['end_y'] = match_dict_i['end_vy']
            if match_dict_i['end_hx']:
                # Path ended with horizontal line
                match_dict_i['end_x'] = match_dict_i['end_hx']
                match_dict_i['end_y'] = match_dict_i['start_y']
            # Append record for end points of the current path.
            frames.append([path_i_dict['id']] + list(map(float, (match_dict_i['start_x'],
                                                                 match_dict_i['start_y'],
                                                                 match_dict_i['end_x'],
                                                                 match_dict_i['end_y']))))

    if not frames:
        return pd.DataFrame(None, columns=['source', 'target'])

    df_connection_lines = pd.DataFrame(frames, columns=['id'] + coords_columns)

    # Use `shapes_canvas.find_shape` to determine shapes overlapped by end
    # points of each `svg:path` or `svg:line`.
    df_shape_connections_i = pd.DataFrame([[shapes_canvas.find_shape(x1, y1),
                                            shapes_canvas.find_shape(x2, y2)]
                                           for i, (x1, y1, x2, y2) in
                                           df_connection_lines[coords_columns].iterrows()],
                                          columns=['source', 'target'])
    # Order the source and target of each row so the source shape identifier is
    # always the lowest.
    df_shape_connections_i.sort_index(axis=1, inplace=True)
    # Tag each shape connection with the corresponding `svg:line`/`svg:path`
    # identifier.  May be useful, e.g., in debugging.
    df_shape_connections_i['line_id'] = df_connection_lines['id']
    # Remove connections where source or target shape was not matched (e.g., if
    # one or more end points does not overlap with a shape).
    return df_shape_connections_i.dropna()


def draw_lines_svg_layer(df_endpoints: pd.DataFrame, layer_name: str = 'Connections') -> StringIO:
    warnings.warn('`draw_lines_svg_layer` has been moved to `svg_model.draw`')
    return _draw_lines_svg_layer(df_endpoints, layer_name=layer_name)
