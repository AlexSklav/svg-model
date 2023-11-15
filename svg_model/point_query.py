# coding: utf-8
import pandas as pd
import pymunk as pm

from typing import Union, List, Tuple


def get_shapes_pymunk_space(df_convex_shapes: pd.DataFrame,
                            shape_i_columns: Union[str, List[str]]) -> Tuple[pm.Space, pd.Series]:
    """
    Return two-ple containing:

     - A `pymunk.Space` instance.
     - A `pandas.Series` mapping each `pymunk.Body` object in the `Space` to a
       shape index.

    The `Body` to shape index mapping makes it possible to, for example, look
    up the index of the convex shape associated with a `Body` returned by a
    `pymunk` point query in the `Space`.
    """
    if isinstance(shape_i_columns, str):
        shape_i_columns = [shape_i_columns]

    space = pm.Space()
    bodies = []

    convex_groups = df_convex_shapes.groupby(shape_i_columns)

    for shape_i, df_i in convex_groups:
        if not isinstance(shape_i, (list, tuple)):
            shape_i = [shape_i]

        if hasattr(pm.Body, 'STATIC'):
            # Assume `pymunk>=5.0`, where static bodies must be declared explicitly.
            body = pm.Body(body_type=pm.Body.STATIC)
        else:
            # Assume `pymunk<5.0`, where bodies are static unless otherwise specified.
            body = pm.Body()

        space.add(body)  # Add the body to the space before adding shapes

        # Using a list comprehension is more efficient than df_i[['x', 'y']].values.
        points = [[x, y] for x, y in zip(df_i.x, df_i.y)]
        poly = pm.Poly(body, points)
        space.add(poly)
        bodies.append([body, shape_i[0]])

    bodies = None if not bodies else bodies
    return space, pd.DataFrame(bodies, columns=['body', shape_i_columns[0]]).set_index('body')[shape_i_columns[0]]
