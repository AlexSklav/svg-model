# coding: utf-8
import re


def hex_color_to_rgba(hex_color: str, normalize_to: int = 255) -> tuple:
    """
    Convert a hex-formatted number (i.e., `"#RGB[A]"` or `"#RRGGBB[AA]"`) to an
    RGBA tuple (i.e., `(<r>, <g>, <b>, <a>)`).

    Args:

        hex_color (str) : hex-formatted number (e.g., `"#2fc"`, `"#3c2f8611"`)
        normalize_to (int, float) : Factor to normalize each channel by

    Returns:

        (tuple) : RGBA tuple (i.e., `(<r>, <g>, <b>, <a>)`), where range of
            each channel in tuple is `[0, normalize_to]`.
    """
    color_pattern = re.compile(r'#(?P<R>[\da-fA-F]{1,2})(?P<G>[\da-fA-F]{1,2})'
                               r'(?P<B>[\da-fA-F]{1,2})(?P<A>[\da-fA-F]{1,2})?')

    match = color_pattern.match(hex_color)

    if not match:
        raise ValueError('Color string must be in format #RGB[A] or '
                         '#RRGGBB[AA] (alpha channel is optional)')

    channels = match.groupdict()
    scale = normalize_to / 255

    return tuple(int(ch, 16) * scale if ch else None for ch in channels.values())
