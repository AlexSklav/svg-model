# coding: utf-8
import itertools

import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon
from mpl_toolkits.axes_grid1 import make_axes_locatable


def plot_shapes(df_shapes: pd.DataFrame, shape_i_columns: list, axis=None, autoxlim: bool = True,
                autoylim: bool = True, **kwargs) -> mpl.axes._axes.Axes:
    """
    Plot shapes from table/data-frame where each row corresponds to a vertex of
    a shape.  Shape vertices are grouped by `shape_i_columns`.

    Args:
        df_shapes (pd.DataFrame): DataFrame containing shape vertices.
        shape_i_columns (list): Columns used for shape grouping.
        axis (mpl.axes._axes.Axes, optional): Matplotlib axis. Defaults to None.
        autoxlim (bool, optional): Adjust x-axis limits. Defaults to True.
        autoylim (bool, optional): Adjust y-axis limits. Defaults to True.
        **kwargs: Additional keyword arguments.

    Returns:
        mpl.axes._axes.Axes: Matplotlib axis.
    """
    if axis is None:
        fig, axis = plt.subplots()
    props = itertools.cycle(mpl.rcParams['axes.prop_cycle'])
    color = kwargs.pop('fc', None)

    patches = [Polygon(df_shape_i[['x', 'y']].values, fc=next(props)['color'] if color is None else color, **kwargs)
               for shape_i, df_shape_i in df_shapes.groupby(shape_i_columns)]

    collection = PatchCollection(patches)

    axis.add_collection(collection)

    xy_stats = df_shapes[['x', 'y']].describe()
    if autoxlim:
        axis.set_xlim(*xy_stats.x.loc[['min', 'max']])
    if autoylim:
        axis.set_ylim(*xy_stats.y.loc[['min', 'max']])
    return axis


def plot_shapes_heat_map(df_shapes: pd.DataFrame, shape_i_columns: list, values: pd.Series, axis=None, vmin=None,
                         vmax=None, value_formatter=None, color_map=None) -> tuple:
    """
    Plot polygon shapes, colored based on values mapped onto a colormap.

    Args:
        df_shapes (pd.DataFrame): Polygon table containing shape coordinates.
        shape_i_columns (list): Columns used for shape grouping.
        values (pd.Series): Numeric values indexed by shape identifiers.
        axis (mpl.axes._axes.Axes, optional): Matplotlib axis. Defaults to None.
        vmin (float, optional): Minimum value for color mapping. Defaults to None.
        vmax (float, optional): Maximum value for color mapping. Defaults to None.
        value_formatter (str, optional): Format string for colorbar labels. Defaults to None.
        color_map (mpl.colors.Colormap, optional): Matplotlib colormap. Defaults to None.

    Returns:
        tuple: Heat map axis and colorbar axis.
    """
    df_shapes = df_shapes.copy()
    df_shapes['y'] = df_shapes.y.max() - df_shapes.y.values

    aspect_ratio = (df_shapes.x.max() - df_shapes.x.min()) / (df_shapes.y.max() - df_shapes.y.min())

    if vmin is not None or vmax is not None:
        norm = mpl.colors.Normalize(vmin=vmin or values.min(), vmax=vmax or values.max())
    else:
        norm = None

    if axis is None:
        fig, axis = plt.subplots(figsize=(10, 10 * aspect_ratio))
    else:
        fig = axis.get_figure()

    patches = {id_: Polygon(df_shape_i[['x', 'y']].values) for id_, df_shape_i in df_shapes.groupby(shape_i_columns)}
    patches = pd.Series(patches)

    collection = PatchCollection(patches.values, cmap=color_map, norm=norm)
    collection.set_array(values.loc[patches.index].values)

    axis.add_collection(collection)

    axis_divider = make_axes_locatable(axis)

    # Append color axis to the right of `axis`, with 10% width of `axis`.
    color_axis = axis_divider.append_axes("right", size="10%", pad=0.05)
    colorbar = fig.colorbar(collection, format=value_formatter, cax=color_axis)

    tick_labels = colorbar.ax.get_yticklabels()
    if vmin is not None:
        tick_labels[0] = f'$\leq$ {tick_labels[0].get_text()}'
    if vmax is not None:
        tick_labels[-1] = f'$\geq$ {tick_labels[-1].get_text()}'
    colorbar.ax.set_yticklabels(tick_labels)

    axis.set_xlim(df_shapes.x.min(), df_shapes.x.max())
    axis.set_ylim(df_shapes.y.min(), df_shapes.y.max())
    return axis, colorbar


def plot_color_map_bars(values: pd.Series, vmin=None, vmax=None, color_map=None, axis=None,
                        **kwargs) -> mpl.axes._axes.Axes:
    """
    Plot bar for each value in `values`, colored based on values mapped onto the specified color map.

    Args:
        values (pd.Series): Numeric values to plot bars.
        vmin (float, optional): Minimum value for color mapping. Defaults to None.
        vmax (float, optional): Maximum value for color mapping. Defaults to None.
        color_map (mpl.colors.Colormap, optional): Matplotlib colormap. Defaults to None.
        axis (mpl.axes._axes.Axes, optional): Matplotlib axis. Defaults to None.
        **kwargs: Additional keyword arguments for plotting.

    Returns:
        mpl.axes._axes.Axes: Matplotlib axis for the bar plot.
    """
    if axis is None:
        fig, axis = plt.subplots()

    norm = mpl.colors.Normalize(vmin=vmin or values.min(), vmax=vmax or values.max(), clip=True)
    if color_map is None:
        color_map = mpl.rcParams['image.cmap']
    colors = color_map(norm(values.values).filled())

    values.plot(kind='bar', ax=axis, color=colors, **kwargs)
    return axis
