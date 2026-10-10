"""Draw data segments as a ribbon following an Archimedean spiral.

The common centerline is r(angle) = r0 + maximum_width / 2 + pitch * angle,
where pitch = (maximum_width + space) / (2 * pi) is radial growth per radian.
Angles increase counterclockwise and outward; fi0_deg rotates the whole strip.

Each segment has its own constant width, measured perpendicular to the
centerline. Its boundaries are offsets along the outward unit normal. The
maximum segment width determines the centerline for every segment.

Lengths, widths, radii, and padding use plot coordinates. Font sizes and
outline widths use typographic points. Internal angles use radians.

The default method approximates arc length with first-order angular steps.
accurate_lengths=True inverts the analytic arc-length equation numerically.
By default, both methods approximate the boundaries with straight polygon
edges. Neither checks turn overlaps, offset folds, or label collisions.
curved_boundaries=True instead approximates the offset boundaries with
adaptive cubic Bezier curves, controlled by curve_tolerance in plot units.

draw_spiral_strip creates, optionally saves/displays, and closes one figure.
plot_spiral_strip draws into caller-owned axes and returns SpiralStripPlot.
"""

import os as _os
import unicodedata as _unicode
from numbers import Real as _Real
from typing import NamedTuple as _NamedTuple

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.patches import Rectangle as _Rectangle
from matplotlib.patches import PathPatch as _PathPatch
from matplotlib.path import Path as _Path
from matplotlib.transforms import Bbox as _Bbox
from matplotlib.backend_bases import FigureCanvasBase as _FigureCanvasBase
from matplotlib.backends.backend_agg import RendererAgg as _RendererAgg
from matplotlib.font_manager import FontProperties as _FontProperties
from matplotlib.textpath import TextPath as _TextPath, TextToPath as _TextToPath
from matplotlib.axes import Axes as _Axes
from matplotlib.cm import ScalarMappable as _ScalarMappable
from matplotlib.colors import Normalize as _Normalize
from matplotlib.figure import Figure as _Figure
from matplotlib.artist import Artist as _Artist


_MAX_PATH_POINTS = 1_000_000
_MAX_CURVE_VERTICES = 1_000_000
_MAX_CURVE_ANGLE = np.pi / 4
_MAX_CURVE_DEPTH = 50
_MAX_RASTER_DIMENSION = 32_768
_MAX_RASTER_PIXELS = 100_000_000
_MAX_LABEL_CHARACTERS = 10_000
_MAX_TOTAL_LABEL_CHARACTERS = 200_000
_DISPLAY_PADDING_POINTS = 2
_VECTOR_FORMATS = frozenset({"eps", "pdf", "pgf", "ps", "svg", "svgz"})
_ARC_LENGTH_RELATIVE_TOLERANCE = 1e-10
_ARC_LENGTH_MAX_ITERATIONS = 64


class _SegmentInputs(_NamedTuple):
    """Validated arrays and label strings, with one entry per segment."""

    widths: np.ndarray
    lengths: np.ndarray
    font_sizes: np.ndarray
    gaps: np.ndarray
    labels: list
    values: object


class _SegmentColors(_NamedTuple):
    """Resolved fill, label, and outline colors in segment order."""

    fills: list
    labels: list
    edges: list


class _SegmentPath(_NamedTuple):
    """Centerline positions/normals and optional start/midpoint/end angles."""

    positions: np.ndarray
    normals: np.ndarray
    angles: object = None


class _Label(_NamedTuple):
    """Text placement in plot coordinates, with rotation in degrees."""

    position: np.ndarray
    rotation: float
    text: str
    color: object
    font_size: float
    curve: object = None


class _LabelCurve(_NamedTuple):
    """Exact spiral parameters for an experimental curved label guide."""

    angle: float
    offset: float
    backbone: float
    r0: float
    space: float
    rotation: float


class _SegmentPolygon(_NamedTuple):
    """Closed boundary and label; codes select curved rather than line edges."""

    vertices: np.ndarray
    label: _Label
    codes: object = None


class _BoundarySample(_NamedTuple):
    """Outside/inside positions and their derivatives with respect to angle."""

    positions: np.ndarray
    derivatives: np.ndarray


class _OutputTarget(_NamedTuple):
    """Validated filename and format, with default extensions resolved."""

    filename: str
    format: str
    is_raster: bool


def _reject_masked_data(value, name, active_containers=None):
    """Reject masks before any array conversion can discard them."""
    if np.ma.isMaskedArray(value):
        raise ValueError(f"{name} must not contain masked data")
    if isinstance(value, (list, tuple)):
        items = value
    elif isinstance(value, np.ndarray) and value.dtype.kind == "O":
        items = value.flat
    else:
        return
    if active_containers is None:
        active_containers = set()
    identity = id(value)
    if identity in active_containers:
        raise ValueError(f"{name} must not contain recursive containers")
    active_containers.add(identity)
    try:
        for item in items:
            _reject_masked_data(item, name, active_containers)
    finally:
        active_containers.remove(identity)


def _real_array(value, name):
    """Convert real numbers without silently coercing strings or losing data."""
    _reject_masked_data(value, name)
    try:
        # Object conversion preserves mixed Booleans, strings, and complex
        # entries that NumPy would otherwise coerce to a shared numeric dtype.
        raw_array = np.asarray(value, dtype=object)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a regular array of real numbers") from error
    for item in raw_array.flat:
        if isinstance(item, (bool, np.bool_)) or not isinstance(
            item, (_Real, np.integer, np.floating)
        ):
            raise TypeError(
                f"{name} must contain real numbers, not Booleans, strings, "
                "complex values, or other objects"
            )
    try:
        with np.errstate(over="ignore", invalid="ignore"):
            array = np.asarray(raw_array, dtype=float)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            f"{name} cannot be represented as floating-point values"
        ) from error
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def _numeric_segments(value, name, count, positive=False, nonnegative=False):
    """Repeat a numeric scalar or validate a finite vector of length count."""
    array = _real_array(value, name)
    if array.ndim == 0:
        array = np.full(count, array.item())
    if array.ndim != 1 or len(array) != count:
        raise ValueError(
            f"{name} must be a scalar or have exactly {count} entries"
        )
    if positive and np.any(array <= 0):
        raise ValueError(f"{name} must be greater than zero")
    if nonnegative and np.any(array < 0):
        raise ValueError(f"{name} must be nonnegative")
    return array


def _numeric_scalar(value, name, positive=False, nonnegative=False):
    """Validate one finite numeric value with an optional sign constraint."""
    array = _real_array(value, name)
    if array.ndim != 0:
        raise ValueError(f"{name} must be a scalar")
    return _numeric_segments(
        array, name, 1, positive=positive, nonnegative=nonnegative
    )[0]


def _boolean(value, name):
    """Accept Python and NumPy Booleans without truthiness coercion."""
    if not isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a boolean")
    return bool(value)


def _validate_raster_dimensions(size_inches, dpi, description):
    """Bound both the individual pixel dimensions and their total product."""
    size = _numeric_segments(size_inches, description, 2, positive=True)
    with np.errstate(over="ignore", invalid="ignore"):
        pixels = size * dpi
    if not np.all(np.isfinite(pixels)) or np.any(pixels < 1):
        raise ValueError(
            f"{description} must have finite dimensions of at least one pixel"
        )
    pixels = np.ceil(pixels)
    if (
        np.any(pixels > _MAX_RASTER_DIMENSION)
        or pixels[0] * pixels[1] > _MAX_RASTER_PIXELS
    ):
        raise ValueError(
            f"{description} exceeds the raster limit of "
            f"{_MAX_RASTER_DIMENSION:,} pixels per dimension or "
            f"{_MAX_RASTER_PIXELS:,} pixels total; reduce dpi or figure size"
        )


def _validate_figure_canvas():
    """Check the display canvas even when no output file is requested."""
    figure_dpi = _numeric_scalar(
        matplotlib.rcParams["figure.dpi"], "figure.dpi", positive=True
    )
    _validate_raster_dimensions(
        matplotlib.rcParams["figure.figsize"], figure_dpi, "Figure canvas"
    )
    return figure_dpi


def _validate_output_target(image_filename, dpi):
    """Check the path, registered output format, and saved raster size."""
    try:
        filename = _os.fspath(image_filename)
    except TypeError as error:
        raise TypeError(
            "image_filename must be a string or text path-like object"
        ) from error
    if not isinstance(filename, str):
        raise TypeError("image_filename must be a string or text path-like object")
    if not filename.strip() or "\0" in filename:
        raise ValueError(
            "image_filename must be nonempty and must not contain NUL characters"
        )
    if _os.path.isdir(filename):
        raise IsADirectoryError(f"image_filename identifies a directory: {filename}")

    output_format = _os.path.splitext(filename)[1][1:].lower()
    if not output_format:
        output_format = _FigureCanvasBase.get_default_filetype().lower()
        filename = filename.rstrip(".") + "." + output_format
    supported_formats = _FigureCanvasBase.get_supported_filetypes()
    if output_format not in supported_formats:
        raise ValueError(
            f"Unsupported image_filename format '{output_format}'; supported "
            f"formats: {', '.join(sorted(supported_formats))}"
        )
    parent = _os.path.dirname(_os.path.abspath(filename))
    if not _os.path.isdir(parent):
        raise FileNotFoundError(f"Output directory does not exist: {parent}")
    if _os.path.isdir(filename):
        raise IsADirectoryError(f"Output filename identifies a directory: {filename}")

    figure_size = matplotlib.rcParams["figure.figsize"]
    is_raster = output_format not in _VECTOR_FORMATS
    if is_raster:
        # Saving can render the full figure before computing its tight crop.
        _validate_raster_dimensions(figure_size, dpi, "Raster output canvas")
    return _OutputTarget(filename, output_format, is_raster)


def _require_geometry(value, description, positive=False):
    """Reject invalid calculated quantities before they reach Matplotlib."""
    if not np.all(np.isfinite(value)) or (positive and np.any(np.asarray(value) <= 0)):
        raise ValueError(
            f"Calculated {description} is outside the representable geometry range"
        )
    return value


def _spiral_pitch(width, space):
    """Radial growth per radian, avoiding overflow of width + space."""
    return width / (2 * np.pi) + space / (2 * np.pi)


def _validate_backbone(widths, r0, space):
    """Check that the radius, pitch, and all half-widths remain representable."""
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        _require_geometry(widths / 2, "segment half-widths", positive=True)
        maximum_width = np.amax(widths)
        _require_geometry(r0 + maximum_width / 2, "starting radius", positive=True)
        _require_geometry(
            _spiral_pitch(maximum_width, space), "spiral pitch", positive=True
        )
    return maximum_width


def _advance_angle(angle, distance, backbone_width, r0, space):
    """Apply the legacy first-order step, requiring representable progress."""
    if distance == 0:
        return angle
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        speed = _require_geometry(
            dldfi_fi(angle, backbone_width, r0, space),
            "centerline speed", positive=True,
        )
        next_angle = angle + distance / speed
    _require_geometry(next_angle, "angle")
    if next_angle <= angle:
        raise ValueError(
            "Requested length or gap is too small for representable "
            "angular progress"
        )
    return next_angle


def _prepare_segment_inputs(
    count, width, segment_length, font_size, gap, labels, values
):
    """Normalize per-segment inputs before geometry or colors are constructed."""
    widths = _numeric_segments(width, "width", count, positive=True)
    lengths = _numeric_segments(
        segment_length, "segment_length", count, positive=True
    )
    font_sizes = _numeric_segments(
        font_size, "labels1_fontsize", count, positive=True
    )
    gaps = _numeric_segments(
        gap, "gap_between_consecutive_segments", count, nonnegative=True
    )

    if labels is None:
        label_texts = [""] * count
    else:
        _reject_masked_data(labels, "labels1_text")
        try:
            # Object conversion preserves raw strings, including trailing NULs
            # that NumPy's fixed-width Unicode scalars would silently discard.
            label_array = np.asarray(labels, dtype=object)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "labels1_text must be a regular one-dimensional sequence"
            ) from error
        if label_array.ndim != 1 or len(label_array) != count:
            raise ValueError(f"labels1_text must have exactly {count} entries")
        label_texts = [str(text) for text in label_array]
        for text in label_texts:
            if len(text) > _MAX_LABEL_CHARACTERS:
                raise ValueError("Each labels1_text entry must have at most 10,000 characters")
            if any(
                (ord(char) < 32 and char not in "\t\n\r")
                or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF
                or ord(char) in (0xFFFE, 0xFFFF)
                for char in text
            ):
                raise ValueError("labels1_text contains an invalid control or Unicode character")
        if sum(map(len, label_texts)) > _MAX_TOTAL_LABEL_CHARACTERS:
            raise ValueError("labels1_text must have at most 200,000 characters in total")
        label_texts = [text.replace("\r\n", "\n").replace("\r", "\n") for text in label_texts]

    if values is not None:
        values = _real_array(values, "values")
        if values.ndim != 1:
            raise ValueError(f"values must have exactly {count} entries")
        values = _numeric_segments(values, "values", count)

    return _SegmentInputs(widths, lengths, font_sizes, gaps, label_texts, values)


def _substep_counts(lengths, maximum_step_length):
    """Choose even step counts and enforce the total path-point limit."""
    counts = []
    total_path_points = 0
    for length in lengths:
        with np.errstate(over="ignore", under="ignore"):
            ratio = length / maximum_step_length
        if not np.isfinite(ratio) or ratio > _MAX_PATH_POINTS:
            raise ValueError(
                "Requested geometry exceeds the 1,000,000 path-point limit; "
                "increase maximum_length_of_subsegment"
            )

        steps = max(2, int(np.ceil(ratio)))
        # An even count includes a centerline sample at the nominal half length.
        steps += steps % 2
        total_path_points += steps + 1
        if total_path_points > _MAX_PATH_POINTS:
            raise ValueError(
                "Requested geometry exceeds the 1,000,000 path-point limit; "
                "increase maximum_length_of_subsegment or reduce the "
                "number of segments"
            )
        counts.append(steps)
    return counts


def _segment_colors(value, name, count, matching_colors=None):
    """Resolve one color or a list, optionally matching each segment's fill.

    Matching is enabled only for labels and outlines. Keep numeric RGB/RGBA
    tuples intact before interpreting a sequence as one entry per segment.
    """
    _reject_masked_data(value, name)
    if isinstance(value, np.ndarray) and value.ndim == 0:
        value = value.item()
    if matching_colors is not None and isinstance(value, str) and value == "same_as_segment":
        return matching_colors.copy()
    # Treat an RGB/RGBA color as a whole, rather than as separate components.
    if matplotlib.colors.is_color_like(value):
        return [_checked_rgba(value, name)] * count
    if not isinstance(value, (list, tuple, np.ndarray)) or len(value) != count:
        raise ValueError(f"{name} must be a color or have exactly {count} colors")
    try:
        return [
            matching_colors[index]
            if matching_colors is not None and isinstance(color, str) and color == "same_as_segment"
            else _checked_rgba(color, f"{name}[{index}]")
            for index, color in enumerate(value)
        ]
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} contains an invalid color") from error


def _checked_rgba(color, name):
    """Require finite RGBA components in addition to Matplotlib color parsing."""
    _reject_masked_data(color, name)
    rgba = matplotlib.colors.to_rgba(color)
    components = np.asarray(rgba)
    if (
        not np.all(np.isfinite(components))
        or np.any(components < 0)
        or np.any(components > 1)
    ):
        raise ValueError(
            f"{name} must contain finite color components between zero and one"
        )
    return rgba


def _random_colors(count):
    """Generate independent RGB colors softened with 25 percent white."""
    return [0.25 + 0.75 * np.random.rand(3) for _ in range(count)]


def _colors_from_values(values, colormap_name):
    """Map the dataset range to a colormap, using its midpoint for constants."""
    if not isinstance(colormap_name, str):
        raise TypeError("colormap_name must be a string for value-based colors")
    # Scaling before subtraction avoids overflow for opposite float extremes.
    scale = np.max(np.abs(values))
    scaled_values = values / scale if scale > 0 else values
    span = np.ptp(scaled_values)
    if span > 0:
        normalized_values = (scaled_values - np.min(scaled_values)) / span
    else:
        normalized_values = np.full(len(values), 0.5)
    try:
        colormap = plt.get_cmap(colormap_name)
    except ValueError as error:
        raise ValueError(f"Unknown colormap_name: {colormap_name}") from error
    return [
        _checked_rgba(colormap(value), "colormap colors")
        for value in normalized_values
    ]


def _prepare_colors(
    count, fill_color, label_color, edge_color, values, colormap_name
):
    """Resolve special color options once, before drawing any segments."""
    if isinstance(fill_color, str) and fill_color == "random":
        fills = _random_colors(count)
    elif isinstance(fill_color, str) and fill_color == "by_values_and_colormap":
        if values is None:
            raise ValueError(
                "values is required when segment_color='by_values_and_colormap'"
            )
        fills = _colors_from_values(values, colormap_name)
    else:
        fills = _segment_colors(fill_color, "segment_color", count)

    if isinstance(label_color, str) and label_color == "random":
        labels = _random_colors(count)
    else:
        labels = _segment_colors(label_color, "labels1_color", count, fills)

    edges = _segment_colors(edge_color, "segment_edge_linecolor", count, fills)
    return _SegmentColors(fills, labels, edges)


def r_fi(fi, width, r0, space):
    """Return centerline radius at angle fi, in radians from the start.

    width is the backbone width; draw_spiral_strip supplies the maximum
    segment width. fi0_deg changes orientation, not this radius.
    """
    pitch = _spiral_pitch(width, space)
    start_radius = r0 + width / 2
    return start_radius + pitch * fi


def dldfi_fi(fi, width, r0, space):
    """Return ds/d(fi), the centerline arc length per radian.

    For r(fi) = start_radius + pitch * fi, ds/d(fi) = hypot(r(fi), pitch).
    The legacy public function and argument names are retained for callers.
    """
    radius = r_fi(fi, width, r0, space)
    pitch = _spiral_pitch(width, space)
    return np.hypot(radius, pitch)


def e_p_fi(fi, width, r0, space, fi0):
    """Return the outward unit normal [normal_x, normal_y].

    fi and the orientation offset fi0 are in radians. Rotating the tangent
    clockwise by 90 degrees selects the outside of this expanding spiral.
    """
    angle = fi + fi0
    radius = r_fi(fi, width, r0, space)
    pitch = _spiral_pitch(width, space)
    tangent_x = pitch * np.cos(angle) - radius * np.sin(angle)
    tangent_y = pitch * np.sin(angle) + radius * np.cos(angle)
    tangent_length = np.hypot(tangent_x, tangent_y)
    return [tangent_y / tangent_length, -tangent_x / tangent_length]


def polar_to_cartesian(fi, r, x0, y0, fi0):
    """Return [x, y] for radius r and angle fi + fi0, translated by (x0, y0).

    Both angles are in radians. Argument names remain compatible with the
    original public helper.
    """
    angle = fi + fi0
    return [x0 + r * np.cos(angle), y0 + r * np.sin(angle)]


def _arc_length_increment(start_radius, pitch, angle_increment):
    """Evaluate the analytic arc length over a nonnegative angular interval.

    The primitive is
    (r * hypot(r, pitch) + pitch**2 * asinh(r / pitch)) / (2 * pitch).
    Subtracting two large primitives loses precision for short intervals far
    from the center. The product and logarithm differences are rearranged
    below to retain the small radial increment explicitly.
    """
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        radial_increment = pitch * angle_increment
        end_radius = start_radius + radial_increment
        start_speed = np.hypot(start_radius, pitch)
        end_speed = np.hypot(end_radius, pitch)

        # (end_radius + start_radius) / (end_speed + start_speed), scaled
        # so neither sum overflows. It also gives the speed difference
        # divided by the radial increment.
        radius_speed_ratio = (
            end_radius / end_speed + start_radius / end_speed
        ) / (1 + start_speed / end_speed)
        log_increment = np.log1p(
            (radial_increment / start_speed)
            * (1 + radius_speed_ratio)
            / (1 + start_radius / start_speed)
        )
        length = angle_increment * (
            end_speed / 2 + (start_radius / 2) * radius_speed_ratio
        ) + (pitch / 2) * log_increment

    if not np.all(np.isfinite(length)):
        raise ValueError("Arc-length calculation exceeded floating-point range")
    return length


def _angles_at_arc_lengths(start_angle, distances, width, r0, space):
    """Invert arc length for a batch of distances from start_angle.

    Safeguarded Newton iterations solve each nonnegative distance separately.
    Speed increases along the spiral, so distance / starting_speed bounds
    the angular increment from above. Steps outside the bracket fall back to
    bisection. Converged entries are frozen while other entries continue.
    """
    distances = np.asarray(distances, dtype=float)
    pitch = _spiral_pitch(width, space)
    with np.errstate(over="ignore", invalid="ignore"):
        start_radius = r0 + width / 2 + pitch * start_angle
        start_speed = np.hypot(start_radius, pitch)
    if not np.isfinite(start_speed) or start_speed <= 0:
        raise ValueError(
            "Spiral geometry cannot be represented for arc-length solving"
        )

    lower = np.zeros_like(distances)
    with np.errstate(over="ignore", invalid="ignore"):
        upper = distances / start_speed
    if not np.all(np.isfinite(upper)):
        raise ValueError("Requested arc length exceeds floating-point range")
    angle_increment = upper.copy()
    tolerance = _ARC_LENGTH_RELATIVE_TOLERANCE * distances

    for _ in range(_ARC_LENGTH_MAX_ITERATIONS):
        length = _arc_length_increment(start_radius, pitch, angle_increment)
        residual = length - distances
        converged = np.abs(residual) <= tolerance
        if np.all(converged):
            with np.errstate(over="ignore", invalid="ignore"):
                angles = start_angle + angle_increment
            if not np.all(np.isfinite(angles)) or np.any(
                (distances > 0) & (angles <= start_angle)
            ):
                raise ValueError(
                    "Requested arc length is outside the representable "
                    "angular range"
                )
            if np.any((np.diff(distances) > 0) & (np.diff(angles) <= 0)):
                raise ValueError(
                    "Requested sampling intervals are too small for distinct angles"
                )
            return angles

        lower = np.where((~converged) & (residual < 0), angle_increment, lower)
        upper = np.where((~converged) & (residual > 0), angle_increment, upper)
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            end_speed = np.hypot(
                start_radius + pitch * angle_increment, pitch
            )
            candidate = angle_increment - residual / end_speed
        inside_bracket = (
            np.isfinite(candidate) & (candidate > lower) & (candidate < upper)
        )
        candidate = np.where(
            inside_bracket, candidate, lower + (upper - lower) / 2
        )
        angle_increment = np.where(converged, angle_increment, candidate)

    raise ValueError(
        f"Arc-length solver did not converge within "
        f"{_ARC_LENGTH_MAX_ITERATIONS} iterations"
    )


def _sample_point(angle, backbone_width, r0, space, rotation):
    """Evaluate one centerline point and verify its radius, speed, and normal."""
    _require_geometry(angle, "angle")
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        radius = _require_geometry(
            r_fi(angle, backbone_width, r0, space), "radius", positive=True
        )
        _require_geometry(
            np.hypot(radius, _spiral_pitch(backbone_width, space)),
            "centerline speed", positive=True,
        )
        position = np.asarray(polar_to_cartesian(angle, radius, 0, 0, rotation))
        normal = np.asarray(e_p_fi(angle, backbone_width, r0, space, rotation))
    _require_geometry(position, "centerline position")
    _require_geometry(normal, "outward normal")
    if not np.isclose(np.hypot(normal[0], normal[1]), 1, rtol=1e-12, atol=1e-12):
        raise ValueError(
            "Calculated outward normal cannot be represented as a unit vector"
        )
    return radius, position, normal


def _sample_segment(
    start_angle, length, steps, backbone_width, r0, space, rotation,
    accurate_lengths, curved_boundaries=False, retain_angles=False,
):
    """Return positions/normals, the end angle, and maximum radius.

    Curved mode retains only its three anchors; legacy integration still
    evaluates every fixed substep to preserve the original placements.
    """
    angle = start_angle
    if accurate_lengths:
        distances = np.linspace(0, length, steps + 1)
        sample_angles = _angles_at_arc_lengths(
            start_angle, distances, backbone_width, r0, space
        )
        if np.any(np.diff(sample_angles) <= 0):
            raise ValueError(
                "Requested sampling intervals cannot produce distinct angles"
            )

    nominal_step_length = length / steps
    _require_geometry(nominal_step_length, "sampling step length", positive=True)
    positions = []
    normals = []
    retained_angles = []
    previous_position = None
    maximum_radius = 0
    for sample_index in range(steps + 1):
        if accurate_lengths:
            angle = sample_angles[sample_index]
        radius, position, normal = _sample_point(
            angle, backbone_width, r0, space, rotation
        )
        maximum_radius = np.maximum(maximum_radius, radius)
        if previous_position is not None and np.array_equal(
            position, previous_position
        ):
            raise ValueError(
                "Requested sampling intervals cannot produce distinct "
                "centerline positions"
            )
        previous_position = position
        if not curved_boundaries or sample_index in (0, steps // 2, steps):
            positions.append(position)
            normals.append(normal)
            if curved_boundaries or retain_angles:
                retained_angles.append(angle)

        if not accurate_lengths and sample_index != steps:
            # First-order approximation: ds = speed(angle) * d(angle).
            angle = _advance_angle(
                angle, nominal_step_length, backbone_width, r0, space
            )

    path = _SegmentPath(
        np.asarray(positions), np.asarray(normals),
        np.asarray(retained_angles) if curved_boundaries or retain_angles else None,
    )
    return path, angle, maximum_radius


def _build_paths(
    inputs, step_counts, backbone_width, r0, space, rotation, accurate_lengths,
    curved_boundaries=False, curved_labels=False,
):
    """Place segments consecutively along the spiral, skipping their gaps."""
    paths = []
    angle = 0
    maximum_radius = 0
    for segment_index, steps in enumerate(step_counts):
        try:
            path, angle, segment_radius = _sample_segment(
                angle, inputs.lengths[segment_index], steps, backbone_width,
                r0, space, rotation, accurate_lengths, curved_boundaries,
                retain_angles=curved_labels,
            )
        except ValueError as error:
            raise ValueError(
                f"Invalid geometry for segment {segment_index + 1}: {error}"
            ) from error
        maximum_radius = np.maximum(maximum_radius, segment_radius)
        paths.append(path)

        gap = inputs.gaps[segment_index]
        # A final gap has no following segment and no visible effect.
        if segment_index + 1 == len(step_counts):
            continue
        if accurate_lengths:
            if gap > 0:
                angle = _angles_at_arc_lengths(
                    angle, [gap], backbone_width, r0, space
                )[0]
        else:
            angle = _advance_angle(angle, gap, backbone_width, r0, space)

    return paths, maximum_radius


def _build_polygon(path, width, text, label_color, font_size, label_padding):
    """Offset a sampled centerline into a closed polygon and place its label."""
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        offsets = path.normals * width / 2
        outside = path.positions + offsets
        inside = path.positions - offsets
    _require_geometry(outside, "outside boundary")
    _require_geometry(inside, "inside boundary")
    if np.any(np.all(outside == inside, axis=1)):
        raise ValueError(
            "Segment width is too small to distinguish its boundaries "
            "at this radius"
        )
    # Walk out along one boundary and back along the other to enclose the strip.
    # Repeating the starting vertex closes the perpendicular end cap.
    vertices = np.concatenate((outside, inside[::-1], outside[:1]))

    midpoint_index = len(path.positions) // 2
    midpoint = path.positions[midpoint_index]
    midpoint_normal = path.normals[midpoint_index]
    if text == "":
        # An invisible label needs no offset, which may itself overflow.
        label_position = midpoint.copy()
    else:
        with np.errstate(over="ignore", invalid="ignore"):
            label_position = midpoint + midpoint_normal * (width / 2 + label_padding)
        _require_geometry(label_position, "label position")
    # The text baseline is parallel to the tangent, facing opposite traversal.
    # No extra rotation is applied to keep labels upright on both sides.
    rotation = (
        np.arctan2(midpoint_normal[1], midpoint_normal[0]) * 180 / np.pi - 90
    )
    label = _Label(label_position, rotation, text, label_color, font_size)
    return _SegmentPolygon(vertices, label)


def _boundary_sample(angle, width, backbone_width, r0, space, rotation):
    """Evaluate the exact normal offsets and their angular derivatives."""
    radius, position, normal = _sample_point(
        angle, backbone_width, r0, space, rotation
    )
    pitch = _spiral_pitch(backbone_width, space)
    speed = np.hypot(radius, pitch)
    phase = angle + rotation
    radial = np.array([np.cos(phase), np.sin(phase)])
    angular = np.array([-radial[1], radial[0]])
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        tangent = pitch * radial + radius * angular
        # N = (r * radial - pitch * angular) / speed. Differentiate
        # in this rotating frame, using ratios to avoid squared radii.
        normal_derivative = (
            2 * (pitch / speed) * radial + (radius / speed) * angular
            - normal * ((radius / speed) * (pitch / speed))
        )
        offset = (width / 2) * normal
        derivative_offset = (width / 2) * normal_derivative
        positions = np.array([position + offset, position - offset])
        derivatives = np.array([
            tangent + derivative_offset, tangent - derivative_offset
        ])
    _require_geometry(positions, "curved boundary positions")
    _require_geometry(derivatives, "curved boundary derivatives")
    if np.array_equal(positions[0], positions[1]):
        raise ValueError("Segment width cannot be resolved at this radius")
    return _BoundarySample(positions, derivatives)


def _boundary_controls(start, end, angle_span):
    """Convert endpoint positions/derivatives to two cubic Hermite curves."""
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        controls = np.stack([
            start.positions,
            start.positions + (angle_span / 3) * start.derivatives,
            end.positions - (angle_span / 3) * end.derivatives,
            end.positions,
        ], axis=1)
    return _require_geometry(controls, "Bezier control points")


def _boundary_curve_error(controls, samples):
    """Estimate both boundary errors at quarter, half, and three-quarter angle."""
    maximum_error = 0
    # Work relative to the starting point to avoid adding large coordinates
    # merely to subtract them again when checking a small approximation error.
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        relative_controls = controls - controls[:, :1, :]
        for fraction, sample in zip((0.25, 0.5, 0.75), samples):
            complement = 1 - fraction
            approximation = (
                3 * complement**2 * fraction * relative_controls[:, 1, :]
                + 3 * complement * fraction**2 * relative_controls[:, 2, :]
                + fraction**3 * relative_controls[:, 3, :]
            )
            actual = sample.positions - controls[:, 0, :]
            difference = approximation - actual
            errors = np.hypot(difference[:, 0], difference[:, 1])
            _require_geometry(errors, "Bezier approximation error")
            maximum_error = max(maximum_error, float(np.max(errors)))
    return maximum_error


def _build_curved_polygon(
    path, width, text, label_color, font_size, label_padding,
    backbone_width, r0, space, rotation, tolerance, vertex_budget,
):
    """Refine both offset boundaries together, preserving the label midpoint.

    Cubics match the exact endpoints and angular derivatives. Three probes
    estimate their error; a separate angular cap prevents a long interval
    from hiding whole turns between the probes. This is an error estimate,
    not a rigorous bound on the deviation everywhere along the curve.
    """
    label = _build_polygon(
        path, width, text, label_color, font_size, label_padding
    ).label
    anchors = path.angles
    # One start, two straight end-cap/closing vertices, and six vertices per
    # paired interval (three for each boundary). Reserve all of these.
    maximum_intervals = (vertex_budget - 3) // 6
    minimum_intervals = sum(
        max(1, int(np.ceil(span / _MAX_CURVE_ANGLE)))
        for span in np.diff(anchors)
    )
    if minimum_intervals > maximum_intervals:
        raise ValueError("Curved geometry exceeds the 1,000,000-vertex limit")
    anchor_samples = [
        _boundary_sample(angle, width, backbone_width, r0, space, rotation)
        for angle in anchors
    ]
    # Right half first on the stack: depth-first processing emits left-to-right
    # intervals, and the exact label midpoint is an explicit boundary join.
    pending = [
        (anchors[1], anchors[2], anchor_samples[1], anchor_samples[2], 0),
        (anchors[0], anchors[1], anchor_samples[0], anchor_samples[1], 0),
    ]
    accepted = []
    while pending:
        start_angle, end_angle, start, end, depth = pending.pop()
        span = end_angle - start_angle
        midpoint = start_angle + span / 2
        midpoint_sample = None
        if span <= _MAX_CURVE_ANGLE:
            controls = _boundary_controls(start, end, span)
            probe_angles = start_angle + span * np.array([0.25, 0.5, 0.75])
            if np.any(np.diff(np.r_[start_angle, probe_angles, end_angle]) <= 0):
                raise ValueError(
                    "Curved boundary probes cannot be resolved at this angle"
                )
            samples = [
                _boundary_sample(angle, width, backbone_width, r0, space, rotation)
                for angle in probe_angles
            ]
            if _boundary_curve_error(controls, samples) <= tolerance:
                accepted.append(controls)
                continue
            midpoint_sample = samples[1]

        if depth >= _MAX_CURVE_DEPTH:
            raise ValueError(
                "Curve refinement did not meet curve_tolerance within "
                f"{_MAX_CURVE_DEPTH} subdivisions; increase curve_tolerance"
            )
        if not start_angle < midpoint < end_angle:
            raise ValueError("Curve refinement exceeds angular precision")
        if len(accepted) + len(pending) + 2 > maximum_intervals:
            raise ValueError(
                "Curved geometry exceeds the 1,000,000-vertex limit; "
                "increase curve_tolerance or reduce the number of turns"
            )
        if midpoint_sample is None:
            midpoint_sample = _boundary_sample(
                midpoint, width, backbone_width, r0, space, rotation
            )
        pending.append((
            midpoint, end_angle, midpoint_sample, end, depth + 1
        ))
        pending.append((
            start_angle, midpoint, start, midpoint_sample, depth + 1
        ))

    vertices = np.empty((6 * len(accepted) + 3, 2))
    codes = np.full(len(vertices), _Path.CURVE4, dtype=np.uint8)
    vertices[0] = accepted[0][0, 0]
    codes[0] = _Path.MOVETO
    index = 1
    for controls in accepted:
        vertices[index:index + 3] = controls[0, 1:]
        index += 3
    # End cap joins the outside endpoint to the inside endpoint.
    vertices[index] = accepted[-1][1, 3]
    codes[index] = _Path.LINETO
    index += 1
    for controls in reversed(accepted):
        # Reversing a cubic reverses both its endpoints and control points.
        vertices[index:index + 3] = controls[1, [2, 1, 0]]
        index += 3
    vertices[index] = vertices[0]
    codes[index] = _Path.CLOSEPOLY
    return _SegmentPolygon(vertices, label, codes)


def _build_polygons(
    paths, inputs, colors, label_padding, curved_boundaries, tolerance,
    backbone_width, r0, space, rotation, curved_labels=False,
):
    """Build straight or curved shapes, sharing one curved-vertex budget."""
    polygons = []
    used_vertices = 0
    for segment_index, path in enumerate(paths):
        arguments = (
            path, inputs.widths[segment_index], inputs.labels[segment_index],
            colors.labels[segment_index], inputs.font_sizes[segment_index],
            label_padding,
        )
        try:
            if curved_boundaries:
                # Every remaining segment needs at least two paired intervals.
                reserved = 15 * (len(paths) - segment_index - 1)
                polygon = _build_curved_polygon(
                    *arguments, backbone_width, r0, space, rotation, tolerance,
                    _MAX_CURVE_VERTICES - used_vertices - reserved,
                )
                used_vertices += len(polygon.vertices)
            else:
                polygon = _build_polygon(*arguments)
        except ValueError as error:
            raise ValueError(
                f"Invalid boundary for segment {segment_index + 1}: {error}"
            ) from error
        if curved_labels and polygon.label.text:
            curve = _LabelCurve(
                float(path.angles[len(path.angles) // 2]),
                float(inputs.widths[segment_index] / 2 + label_padding),
                float(backbone_width), r0, space, rotation,
            )
            polygon = polygon._replace(label=polygon.label._replace(curve=curve))
        polygons.append(polygon)
    return polygons


def _checked_plot_extent(maximum_radius, backbone_width, space):
    """Ensure the full axis span and its reciprocal can be represented."""
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        extent = maximum_radius + space + backbone_width / 2
        _require_geometry(extent, "plot extent", positive=True)
        span = _require_geometry(2 * extent, "axis span", positive=True)
        _require_geometry(1 / span, "inverse axis span", positive=True)
    return extent


def _check_text_render_size(font_size, dpi, name):
    """Bound raster font metrics before asking the renderer to measure text."""
    with np.errstate(over="ignore", invalid="ignore"):
        font_pixels = (font_size / 72) * dpi
    if not np.isfinite(font_pixels) or font_pixels > _MAX_RASTER_DIMENSION:
        raise ValueError(
            f"{name} font size exceeds the raster dimension limit; "
            "reduce font size or dpi"
        )


def _check_label_render_sizes(polygons, dpi):
    """Reject excessive font sizes before raster text metrics are requested."""
    for segment in polygons:
        if segment.label.text == "":
            continue
        _check_text_render_size(segment.label.font_size, dpi, "Label")


def _check_tight_raster_size(figure, dpi):
    """Check label-expanded bounds without allocating the full output image."""
    original_dpi = figure.dpi
    try:
        figure.set_dpi(dpi)
        # A one-pixel renderer provides text metrics at the output resolution.
        # get_tightbbox returns inches, so the usual dimension check applies.
        renderer = _RendererAgg(1, 1, dpi)
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            bounds = figure.get_tightbbox(renderer)
        _validate_raster_dimensions(
            (bounds.width, bounds.height), dpi, "Label-expanded raster output"
        )
        # Freeze the checked crop so savefig cannot expand it after validation.
        return bounds.frozen()
    except (OverflowError, FloatingPointError, ZeroDivisionError) as error:
        raise ValueError("Raster output bounds cannot be represented") from error
    finally:
        figure.set_dpi(original_dpi)


def _artwork_bounds(axes, renderer, artists=None):
    """Measure the actual shapes and labels, excluding the empty axes box."""
    bounds = []
    for artist in ((*axes.patches, *axes.texts) if artists is None else artists):
        if (not artist.get_visible() or getattr(artist, "_spiral_join_coverage", False)
                or getattr(artist, "_spiral_layout_helper", False)):
            continue
        box = artist.get_window_extent(renderer)
        _require_geometry(box.extents, "display artwork bounds")
        if isinstance(artist, matplotlib.patches.Patch):
            # Patch extents describe the path, excluding its outline stroke.
            # The display fitter selects round joins, which fit within this
            # half-linewidth padding even at sharp polygon corners.
            stroke_padding = renderer.points_to_pixels(artist.get_linewidth()) / 2
            _require_geometry(stroke_padding, "display outline padding")
            box = box.padded(stroke_padding)
        _require_geometry(box.extents, "padded display artwork bounds")
        bounds.append(box)
    if not bounds:
        raise ValueError("The visualization has no visible shapes or labels")
    return _Bbox.union(bounds)


def _add_strip_title(figure, axes, title, font_size, color, padding, bold=False, artists=None):
    """Place literal title text above the complete artwork, including labels.

    Convert the measured display position back to data coordinates so the
    display crop can resize the axes without moving the title relative to it.
    """
    axes.apply_aspect()
    renderer = _RendererAgg(1, 1, figure.dpi)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        bounds = _artwork_bounds(axes, renderer, artists)
        position = [bounds.x0 + bounds.width / 2,
                    bounds.y1 + renderer.points_to_pixels(padding)]
        _require_geometry(position, "title display position")
        x, y = axes.transData.inverted().transform(position)
        _require_geometry([x, y], "title position")
    artist = axes.text(
        x, y, title, fontsize=font_size, color=color,
        fontweight="bold" if bold else "normal",
        horizontalalignment="center", verticalalignment="bottom",
        multialignment="center", linespacing=1.2, clip_on=False, usetex=False,
    )
    # Titles are plain text even when surrounding Matplotlib styles enable math.
    if hasattr(artist, "set_parse_math"):
        artist.set_parse_math(False)


def _add_strip_colorbar(
    figure, axes, minimum, maximum, colormap_name, suffix, width_percent, font_size, label_color,
    artists=None,
):
    """Draw a compact scale below the measured artwork using ordinary artists.

    Positions start in display pixels, then become data coordinates so the
    existing display and saved-image crops include the bar and its two labels.
    Constant data use the same midpoint colour as the segments and one label.
    Opaque blocks overlap slightly to hide rendering seams. Reject overlapping
    endpoint labels rather than silently altering the requested bar width.
    """
    axes.apply_aspect()
    renderer = _RendererAgg(1, 1, figure.dpi)
    points = renderer.points_to_pixels(1)
    bounds = _artwork_bounds(axes, renderer, artists)
    width = _require_geometry(bounds.width * (width_percent / 100), "colorbar width", positive=True)
    left = bounds.x0 + (bounds.width - width) / 2
    top = bounds.y0 - 12 * points
    bottom = top - 8 * points
    inverse = axes.transData.inverted()
    colormap = plt.get_cmap(colormap_name)
    constant = minimum == maximum
    samples = 1 if constant else 256
    palette = [
        _checked_rgba(colormap(0.5 if constant else index / (samples - 1)), "colorbar color")
        for index in range(samples)
    ]
    # Overpaint opaque neighbours slightly to hide vector-viewer seams.
    # Transparent samples must retain their original, nonoverlapping areas.
    overlap = min(width / samples, 0.5 * points) if all(color[3] == 1 for color in palette) else 0
    label_artists = []
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        for index in range(samples):
            corners = inverse.transform([
                [left + width * index / samples, bottom],
                [left + min(width, width * (index + 1) / samples + overlap), top],
            ])
            _require_geometry(corners, "colorbar rectangle")
            size = _require_geometry(corners[1] - corners[0], "colorbar dimensions", positive=True)
            axes.add_patch(_Rectangle(
                corners[0], size[0], size[1],
                facecolor=palette[index],
                edgecolor="none", linewidth=0, antialiased=False, clip_on=False,
            ))
        labels = [format(minimum, ".6g"), format(maximum, ".6g")]
        if not constant and labels[0] == labels[1]:
            labels = [format(minimum, ".17g"), format(maximum, ".17g")]
        if suffix:
            labels = [label + " " + suffix for label in labels]
        ticks = [(left + width / 2, labels[0], "center")] if constant else [
            (left, labels[0], "center"), (left + width, labels[1], "center")
        ]
        for x, text, alignment in ticks:
            tick = inverse.transform([[x, top], [x, bottom - 3 * points]])
            position = inverse.transform([x, bottom - 6 * points])
            _require_geometry(tick, "colorbar tick")
            _require_geometry(position, "colorbar label position")
            axes.add_patch(_PathPatch(
                _Path(tick, [_Path.MOVETO, _Path.LINETO]), fill=False,
                edgecolor="#4b5563", linewidth=0.6, clip_on=False,
            ))
            artist = axes.text(
                *position, text, fontsize=font_size, color=label_color,
                horizontalalignment=alignment, verticalalignment="top",
                clip_on=False, usetex=False,
            )
            if hasattr(artist, "set_parse_math"):
                artist.set_parse_math(False)
            label_artists.append(artist)
    if not constant and label_color[3] != 0:
        label_bounds = [artist.get_window_extent(renderer) for artist in label_artists]
        for bbox in label_bounds:
            _require_geometry(bbox.extents, "colorbar label bounds")
        if label_bounds[0].x1 + 2 * points > label_bounds[1].x0:
            raise ValueError(
                "Colorbar labels overlap; increase colorbar_width_percent, "
                "reduce colorbar_fontsize, or shorten colorbar_suffix"
            )


def _disable_automatic_layout(figure):
    """Keep measured artwork positions stable during saving and display."""
    if hasattr(figure, "set_layout_engine"):
        figure.set_layout_engine("none")
    else:
        figure.set_tight_layout(False)
        figure.set_constrained_layout(False)


def _fit_display_to_artwork(figure, axes):
    """Crop the display canvas while preserving physical scale and aspect.

    Map the measured pixel crop back to data coordinates, then give that view
    the corresponding physical canvas size. Geometry and font sizes stay
    intact. The axes fill the new canvas so notebook tight cropping cannot
    restore the unused area. Labels may initially lie outside the old axes.
    """
    dpi = _numeric_scalar(figure.dpi, "display figure.dpi", positive=True)
    # The crop supplies its own layout; an automatic layout pass must not
    # reposition the axes after their measured pixel placement is restored.
    _disable_automatic_layout(figure)
    for outline in axes.patches:
        outline.set_joinstyle("round")
    axes.apply_aspect()
    renderer = _RendererAgg(1, 1, dpi)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        padding = renderer.points_to_pixels(_DISPLAY_PADDING_POINTS)
        crop = _artwork_bounds(axes, renderer).padded(padding)
        _require_geometry(crop.extents, "display crop")
        size_inches = np.array([crop.width, crop.height]) / dpi
    _validate_raster_dimensions(size_inches, dpi, "Cropped display canvas")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        limits = axes.transData.inverted().transform([
            [crop.x0, crop.y0], [crop.x1, crop.y1]
        ])
        _require_geometry(limits, "cropped data limits")
        spans = _require_geometry(
            np.abs(limits[1] - limits[0]), "cropped data spans", positive=True
        )
        _require_geometry(1 / spans, "inverse cropped data spans", positive=True)
    figure.set_size_inches(size_inches, forward=True)
    axes.set_position([0, 0, 1, 1])
    axes.set_xlim(limits[0, 0], limits[1, 0])
    axes.set_ylim(limits[0, 1], limits[1, 1])
    axes.apply_aspect()
    _require_geometry(axes.transData.get_matrix(), "cropped plot transformation")


def _add_join_coverage(axes, polygons, widths, colors, gaps, edge_linewidth, antialiased):
    """Cover rasterization seams at zero-gap joints without adding outlines.

    Clip each short underpainting stroke to the union of its neighbouring
    shapes. Only opaque fills qualify, so translucent colours do not accumulate
    extra opacity. The real polygons determine the crop and cover this paint.
    """
    if not antialiased or gaps is None:
        return
    for index in range(1, len(polygons)):
        if gaps[index - 1] != 0:
            continue
        neighbours = (index - 1, index)
        if any(len(colors.fills[i]) == 4 and colors.fills[i][3] != 1 for i in neighbours):
            continue
        if edge_linewidth > 0 and any(
            len(colors.edges[i]) != 4 or colors.edges[i][3] != 0
            for i in neighbours
        ):
            continue
        narrower = min(neighbours, key=lambda i: widths[i])
        segment = polygons[narrower]
        if narrower == index:
            edge = segment.vertices[[0, -2]]
        else:
            # Both straight and cubic boundaries traverse the outside first,
            # then cross the end cap and return along the inside boundary.
            middle = (len(segment.vertices) - 1) // 2
            edge = segment.vertices[[middle - 1, middle]]
        paths = [
            _Path(polygons[i].vertices, polygons[i].codes, closed=True)
            for i in neighbours
        ]
        coverage = _PathPatch(
            _Path(edge), fill=False, edgecolor=colors.fills[narrower],
            linewidth=0.9, capstyle="butt", antialiased=True, zorder=0,
        )
        coverage._spiral_clip_path = _Path.make_compound_path(*paths)
        coverage.set_clip_path(coverage._spiral_clip_path, axes.transData)
        coverage.set_in_layout(False)
        coverage._spiral_join_coverage = True
        axes.add_patch(coverage)


def _validate_curved_label_text(text):
    """This experimental glyph layout has no shaping or multiline engine."""
    for char in text:
        category = _unicode.category(char)
        name = _unicode.name(char, "")
        if char in "\n\r\t" or category in ("Zl", "Zp") or category[0] in ("M", "C") or (
            category.startswith("L") and not any(script in name for script in ("LATIN", "GREEK", "CYRILLIC"))
        ):
            raise ValueError(
                "Experimental curved labels require single-line Latin, Greek, "
                "Cyrillic text or common symbols without combining marks"
            )


def _curved_label_guide(axes, curve, half_length):
    """Sample a normal-offset guide in pixels, retaining its exact midpoint.

    Extend beyond segment caps as needed, up to one full turn. The centerline
    radius stays positive and each angular step is at most pi/256.
    """
    axes.apply_aspect()
    probe = _boundary_sample(curve.angle, 2 * curve.offset, curve.backbone,
                             curve.r0, curve.space, curve.rotation)
    transform = axes.transData
    scale = np.linalg.norm(transform.transform([1, 0]) - transform.transform([0, 0]))
    speed = np.linalg.norm(probe.derivatives[0]) * scale
    _require_geometry(speed, "curved label guide speed", positive=True)
    span = min(np.pi, max(0.02, half_length / speed * 1.1))
    pitch = _spiral_pitch(curve.backbone, curve.space)
    available = curve.angle + (curve.r0 + curve.backbone / 2) / pitch
    left_limit = min(np.pi, available * (1 - 1e-12))
    for _ in range(12):
        left_span = min(span, left_limit)
        left = np.linspace(curve.angle - left_span, curve.angle,
                           max(16, int(np.ceil(left_span / (np.pi / 256)))) + 1)
        right = np.linspace(curve.angle, curve.angle + span,
                            max(16, int(np.ceil(span / (np.pi / 256)))) + 1)
        angles = np.concatenate([left, right[1:]])
        points = []
        for angle in angles:
            _, position, normal = _sample_point(angle, curve.backbone, curve.r0, curve.space, curve.rotation)
            points.append(position + curve.offset * normal)
        pixels = transform.transform(points)
        _require_geometry(pixels, "curved label guide")
        lengths = np.concatenate([[0.], np.cumsum(np.linalg.norm(np.diff(pixels, axis=0), axis=1))])
        midpoint = lengths[len(left) - 1]
        if np.any(np.diff(lengths) <= 0):
            raise ValueError("Curved label guide cannot be resolved at this scale")
        if min(midpoint, lengths[-1] - midpoint) >= half_length:
            return pixels, lengths, midpoint
        if span >= np.pi:
            break
        span = min(np.pi, span * 2)
    raise ValueError("Curved label is too long for its guide; reduce labels1_fontsize or shorten labels1_text")


def _add_curved_label(figure, axes, label, artist=None, dynamic=False):
    """Place vector glyphs along an offset curve as one compound path."""
    _validate_curved_label_text(label.text)
    pixels_per_point = _RendererAgg(1, 1, figure.dpi).points_to_pixels(1)
    properties = _FontProperties(size=label.font_size)
    metrics = _TextToPath()
    def text_width(text):
        return metrics.get_text_width_height_descent(text, properties, ismath=False)[0]
    letters = []
    advance = 0.
    previous = ""
    vertical = []
    for char in label.text:
        char_width = text_width(char)
        if previous:
            advance += text_width(previous + char) - text_width(previous) - char_width
        # Whitespace advances the text but has no visible outline. Avoid
        # constructing empty TextPaths, which fail in some Matplotlib versions.
        if not char.isspace():
            glyph = _TextPath((0, 0), char, size=label.font_size, prop=properties, usetex=False)
            letters.append((advance, char_width, glyph))
            if len(glyph.vertices):
                bounds = glyph.get_extents()
                vertical.extend([bounds.y0, bounds.y1])
        advance += char_width
        previous = char
    if not vertical:
        return None
    total = _require_geometry(advance * pixels_per_point, "curved label width", positive=True)
    pixels, lengths, midpoint = _curved_label_guide(axes, label.curve, total / 2 + pixels_per_point)
    vertical_shift = -(min(vertical) + max(vertical)) / 2
    inverse = axes.transData.inverted()
    glyph_paths = []
    vertices_used = 0
    for start, char_width, glyph in letters:
        if not len(glyph.vertices):
            continue
        # Match the existing labels' direction, opposite spiral traversal.
        distance = midpoint - ((start + char_width / 2) * pixels_per_point - total / 2)
        interval = int(np.clip(np.searchsorted(lengths, distance) - 1, 0, len(lengths) - 2))
        fraction = (distance - lengths[interval]) / (lengths[interval + 1] - lengths[interval])
        origin = pixels[interval] + fraction * (pixels[interval + 1] - pixels[interval])
        tangent = pixels[interval] - pixels[interval + 1]
        tangent /= np.linalg.norm(tangent)
        normal = np.array([-tangent[1], tangent[0]])
        local = (glyph.vertices + [-char_width / 2, vertical_shift]) * pixels_per_point
        mapped = inverse.transform(origin + local[:, :1] * tangent + local[:, 1:] * normal)
        _require_geometry(mapped, "curved label glyph")
        vertices_used += len(mapped)
        if vertices_used > _MAX_CURVE_VERTICES:
            raise ValueError("Curved label outlines exceed the 1,000,000-vertex limit")
        glyph_paths.append(_Path(mapped, glyph.codes))
    compound = _Path.make_compound_path(*glyph_paths)
    if artist is None:
        patch_type = _ResponsiveCurvedLabel if dynamic else _PathPatch
        artist = patch_type(compound, facecolor=label.color, edgecolor="none", linewidth=0,
                            clip_on=False, zorder=3)
        if dynamic:
            artist._strip_label = label
        axes.add_patch(artist)
    else:
        artist.set_path(compound)
    return artist


def _check_plot_render_sizes(strip, dpi):
    """Guard saved raster text sizes after shared input validation and plotting."""
    for artist in strip.artists:
        if hasattr(artist, "get_fontsize"):
            _check_text_render_size(artist.get_fontsize(), dpi, "Text")
        elif isinstance(artist, _ResponsiveCurvedLabel):
            _check_text_render_size(artist._strip_label.font_size, dpi, "Curved label")


class _ResponsiveCurvedLabel(_PathPatch):
    """Rebuild point-sized glyphs when the caller changes the panel layout."""

    def _refresh_reference_path(self):
        # Embedded plots scale their reference glyphs with transData. Sampling
        # a new guide at each panel size introduces avoidable rounding drift.
        reference = self._proportional_reference
        label = self._strip_label._replace(font_size=self._reference_font_size)
        key = (label.text, label.curve, label.font_size,
               _FontProperties(size=label.font_size).get_fontconfig_pattern())
        if key != getattr(self, "_reference_path_key", None):
            _add_curved_label(reference.figure, reference, label, artist=self)
            self._reference_path_key = key

    def _refresh_path(self):
        if self.axes is not None and not getattr(self, "_reference_measurement", False):
            if hasattr(self, "_proportional_reference"):
                self._refresh_reference_path()
            else:
                _add_curved_label(self.axes.figure, self.axes, self._strip_label, artist=self)

    def draw(self, renderer):
        self._refresh_path()
        super().draw(renderer)

    def get_window_extent(self, renderer=None):
        self._refresh_path()
        return super().get_window_extent(renderer)


class SpiralStripPlot:
    """Artists returned by plot_spiral_strip; the caller owns their figure.

    segments and labels follow input order (missing labels are None).
    artists includes join coverage, optional title and colorbar artists.
    mappable is available for value-based coloring, otherwise None.
    Call fit() after changing layout, sizes, or label text to refit the panel.
    """

    def __init__(self, ax, segments, labels, artists, mappable,
                 title_options=None, colorbar_options=None):
        self.ax = ax
        self.segments = segments
        self.labels = labels
        self.artists = artists
        self.mappable = mappable
        self._base_artists = artists
        self._decorations = ()
        self._title_options = title_options
        self._colorbar_options = colorbar_options
        self._proportional_layout = None

    def _update_decorations(self):
        for artist in self._decorations:
            if artist.axes is self.ax:
                artist.remove()
        previous = set(self.ax.get_children())
        if self._title_options is not None:
            _add_strip_title(self.ax.figure, self.ax, *self._title_options,
                             artists=self._base_artists)
        if self._colorbar_options is not None:
            title_artists = tuple(a for a in self.ax.get_children() if a not in previous)
            _add_strip_colorbar(self.ax.figure, self.ax, *self._colorbar_options,
                                artists=self._base_artists + title_artists)
        self._decorations = tuple(a for a in self.ax.get_children() if a not in previous)
        self.artists = self._base_artists + self._decorations
        return self.artists

    def fit(self):
        """Fit these artists within the axes without resizing the figure."""
        if self._proportional_layout is not None:
            self._proportional_layout.fit()
        else:
            _fit_embedded_artwork(self.ax, self.artists, self._update_decorations)
        return self

    def remove(self):
        """Remove this strip's artists, preserving other axes content."""
        for artist in self.artists:
            if artist.axes is self.ax:
                artist.remove()


class _ScaleController(_Artist):
    """Update physical font/stroke sizes after Matplotlib resolves panel layout."""

    def __init__(self, layout):
        super().__init__()
        self.layout = layout
        self._spiral_layout_helper = True
        self.set_zorder(-1e12)
        self.set_in_layout(False)

    def draw(self, renderer):
        self.layout.sync()
        self.stale = False


class _ProportionalLayout:
    """Preserve a standalone reference in data coordinates and scale all styles.

    The reference Figure is unmanaged and never displayed or rasterized. Only
    its transforms and one-pixel text metrics are used; artists remain native
    Matplotlib objects in the caller's axes.
    """

    def __init__(self, strip, reference_axes):
        self.strip = strip
        self.reference_axes = reference_axes
        reference_axes.apply_aspect()
        matrix = reference_axes.transData.get_matrix()
        self.reference_inches_per_unit = float(np.hypot(matrix[0, 0], matrix[1, 0])) / reference_axes.figure.dpi
        self.styles = []
        for artist in strip.artists:
            if isinstance(artist, _ResponsiveCurvedLabel):
                artist._proportional_reference = reference_axes
                artist._reference_font_size = artist._strip_label.font_size
                self.styles.append([artist, "curve", artist._strip_label.font_size, 1.])
            elif hasattr(artist, "get_fontsize"):
                self.styles.append([artist, "font", artist.get_fontsize(), 1.])
            if isinstance(artist, matplotlib.patches.Patch):
                self.styles.append([artist, "stroke", artist.get_linewidth(), 1.])

    @staticmethod
    def _value(artist, kind):
        if kind == "curve":
            return artist._strip_label.font_size
        return artist.get_fontsize() if kind == "font" else artist.get_linewidth()

    @staticmethod
    def _set(artist, kind, value):
        if kind == "curve":
            artist._strip_label = artist._strip_label._replace(font_size=value)
        elif kind == "font":
            artist.set_fontsize(value)
        else:
            artist.set_linewidth(value)

    def _styles_at_scale(self, scale):
        for entry in self.styles:
            artist, kind, base, previous_scale = entry
            if artist.axes is not self.strip.ax:
                continue
            current = self._value(artist, kind)
            # Retain user changes to native artists between drawing operations.
            if not np.isclose(current, base * previous_scale, rtol=1e-12, atol=0):
                base = current / previous_scale
                entry[2] = base
            if kind in ("font", "curve"):
                if base * scale < 1:
                    raise ValueError("Panel too small to preserve typography; enlarge the panel or use larger reference font sizes")
                _check_text_render_size(base * scale, artist.figure.dpi, "Scaled text")
            self._set(artist, kind, base * scale)
            if kind == "curve":
                artist._reference_font_size = base
            entry[3] = scale

    def fit(self):
        ax = self.strip.ax
        reference = self.reference_axes
        reference.apply_aspect()
        renderer = _RendererAgg(1, 1, reference.figure.dpi)
        self._styles_at_scale(1.)
        artists = tuple(a for a in self.strip.artists if a.axes is ax and not isinstance(a, _ScaleController))
        # Patch.get_transform() includes its local geometry transform (for
        # Rectangle, the unit square -> bar block). Restoring that composite
        # with set_transform would apply the local transform a second time.
        transforms = [
            (a, a.get_data_transform() if isinstance(a, matplotlib.patches.Patch)
             else a.get_transform())
            for a in artists
        ]
        try:
            for artist in artists:
                artist.set_transform(reference.transData)
                if isinstance(artist, _ResponsiveCurvedLabel):
                    artist._reference_measurement = True
                    artist._refresh_reference_path()
            crop = _artwork_bounds(reference, renderer, artists).padded(
                renderer.points_to_pixels(_DISPLAY_PADDING_POINTS)
            )
            limits = reference.transData.inverted().transform(crop.get_points())
            _require_geometry(limits, "proportional panel limits")
        finally:
            for artist, transform in transforms:
                artist.set_transform(transform)
                if isinstance(artist, _ResponsiveCurvedLabel):
                    artist._reference_measurement = False
        ax.set_xlim(limits[:, 0])
        ax.set_ylim(limits[:, 1])
        ax.set_aspect("equal", adjustable="box")
        self.sync()

    def sync(self):
        ax = self.strip.ax
        ax.apply_aspect()
        matrix = ax.transData.get_matrix()
        inches_per_unit = float(np.hypot(matrix[0, 0], matrix[1, 0])) / ax.figure.dpi
        scale = _require_geometry(inches_per_unit / self.reference_inches_per_unit,
                                  "proportional text scale", positive=True)
        self._styles_at_scale(scale)


def _embed_reference(strip, axes):
    """Move reference artists into the requested panel without copying artwork."""
    reference = strip.ax
    previous = set(axes.get_children())
    view = (axes.get_xlim(), axes.get_ylim(), axes.get_aspect(), axes.get_adjustable(), axes.axison)
    layout = _ProportionalLayout(strip, reference)
    try:
        for artist in strip.artists:
            artist.remove()
            artist.set_transform(axes.transData)
            artist.set_clip_box(None)
            artist.set_clip_path(None)
            if hasattr(artist, "_spiral_clip_path"):
                artist.set_clip_path(artist._spiral_clip_path, axes.transData)
            elif artist.get_clip_on():
                artist.set_clip_path(axes.patch)
            axes.add_artist(artist)
        strip.ax = axes
        strip._proportional_layout = layout
        controller = _ScaleController(layout)
        axes.add_artist(controller)
        strip.artists += (controller,)
        axes.axis("off")
        strip.fit()
        return strip
    except Exception:
        for artist in tuple(axes.get_children()):
            if artist not in previous:
                artist.remove()
        xlim, ylim, aspect, adjustable, axison = view
        axes.set_xlim(xlim)
        axes.set_ylim(ylim)
        axes.set_aspect(aspect, adjustable=adjustable)
        axes.axison = axison
        axes.apply_aspect()
        raise


class _StripNormalize(_Normalize):
    """Value normalization matching strip colors, including extreme/constant data."""

    def __call__(self, value, clip=None):
        data, scalar = self.process_value(value)
        divisor = max(abs(self.vmin), abs(self.vmax)) or 1.
        lower, upper = self.vmin / divisor, self.vmax / divisor
        scaled = np.ma.array(data / divisor, copy=True)
        if lower == upper:
            scaled[:] = 0.5
        else:
            scaled = (scaled - lower) / (upper - lower)
        if (self.clip if clip is None else clip):
            scaled = np.ma.clip(scaled, 0., 1.)
        return scaled[0] if scalar else scaled

    def inverse(self, value):
        divisor = max(abs(self.vmin), abs(self.vmax)) or 1.
        # Convex interpolation avoids overflowing vmax-vmin.
        value = np.asarray(value)
        return ((1 - value) * (self.vmin / divisor) + value * (self.vmax / divisor)) * divisor


def _fit_embedded_artwork(axes, artists, update=None):
    """Iteratively include point-sized text and strokes in panel data limits."""
    figure = axes.figure
    renderer = _RendererAgg(1, 1, figure.dpi)
    for _ in range(24):
        axes.apply_aspect()
        if update is not None:
            artists = update()
        frame = axes.get_window_extent(renderer)
        _require_geometry([frame.width, frame.height], "embedded axes size", positive=True)
        crop = _artwork_bounds(axes, renderer, artists).padded(
            renderer.points_to_pixels(_DISPLAY_PADDING_POINTS)
        )
        # Do not shrink a fitted view: this keeps refitting stable when labels
        # have fixed physical sizes while the geometry scales with the panel.
        if (crop.x0 >= frame.x0 - 0.05 and crop.x1 <= frame.x1 + 0.05
                and crop.y0 >= frame.y0 - 0.05 and crop.y1 <= frame.y1 + 0.05):
            return
        bounds = _Bbox.union([frame, crop])
        limits = axes.transData.inverted().transform(bounds.get_points())
        _require_geometry(limits, "embedded artwork limits")
        axes.set_xlim(limits[:, 0])
        axes.set_ylim(limits[:, 1])
    raise ValueError("The strip does not fit this panel; enlarge it or reduce label sizes/padding")


def _render_strip(
    axes, polygons, widths, colors, maximum_radius, backbone_width,
    space, edge_linewidth, antialiased, figure_dpi,
    title="", title_fontsize=12, title_color="black", title_pad=8,
    title_bold=False, gaps=None, colorbar=None, mappable=None, fit=True,
):
    """Draw native artists into supplied axes; the caller owns the figure."""
    if fit:
        # Measure exactly the normal standalone subplot before fitting the
        # complete composition uniformly into the caller's panel.
        reference_dpi = _validate_figure_canvas()
        reference = _Figure(figsize=matplotlib.rcParams["figure.figsize"], dpi=reference_dpi)
        _disable_automatic_layout(reference)
        reference_axes = reference.add_subplot(1, 1, 1)
        strip = _render_strip(
            reference_axes, polygons, widths, colors, maximum_radius, backbone_width,
            space, edge_linewidth, antialiased, reference_dpi,
            title, title_fontsize, title_color, title_pad, title_bold,
            gaps=gaps, colorbar=colorbar, mappable=mappable, fit=False,
        )
        return _embed_reference(strip, axes)
    extent = _checked_plot_extent(maximum_radius, backbone_width, space)
    for segment in polygons:
        if segment.codes is not None:
            # A Bezier lies within its control-point convex hull. Including
            # the controls keeps even small approximation overshoots visible.
            extent = max(extent, float(np.max(np.abs(segment.vertices))))
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        span = _require_geometry(2 * extent, "axis span", positive=True)
        _require_geometry(1 / span, "inverse axis span", positive=True)
    # Agg text metrics are also used to position artwork for vector exports.
    _check_label_render_sizes(polygons, figure_dpi)
    if colorbar is not None:
        _check_text_render_size(colorbar[5], figure_dpi, "Colorbar labels")
    if title:
        _check_text_render_size(title_fontsize, figure_dpi, "Title")
    figure = axes.figure
    previous_artists = set(axes.get_children())
    previous_view = (axes.get_xlim(), axes.get_ylim(), axes.get_aspect(),
                     axes.get_adjustable(), axes.axison)
    completed = False
    segment_artists, label_artists = [], []
    try:
        axes.set_ylim(-extent, extent)
        axes.set_xlim(-extent, extent)
        axes.set_aspect("equal", adjustable="box")
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            _require_geometry(axes.transData.get_matrix(), "plot transformation")

        _add_join_coverage(
            axes, polygons, widths, colors, gaps, edge_linewidth, antialiased
        )
        for segment_index, segment in enumerate(polygons):
            patch_options = dict(
                fill=True,
                facecolor=colors.fills[segment_index],
                edgecolor=colors.edges[segment_index],
                linewidth=edge_linewidth,
                antialiased=antialiased,
                # Wider segments appear above narrower ones if they overlap.
                zorder=widths[segment_index] / backbone_width,
            )
            if segment.codes is None:
                patch = Polygon(segment.vertices, closed=True, **patch_options)
            else:
                patch = _PathPatch(
                    _Path(segment.vertices, segment.codes), **patch_options
                )
            axes.add_patch(patch)
            segment_artists.append(patch)
            label = segment.label
            label_artist = None
            if label.text != "":
                if label.curve is not None:
                    label_artist = _add_curved_label(figure, axes, label, dynamic=True)
                    label_artists.append(label_artist)
                    continue
                with np.errstate(over="ignore", invalid="ignore"):
                    _require_geometry(
                        axes.transData.transform(label.position),
                        "display label position",
                    )
                label_x, label_y = label.position
                artist = axes.text(
                    label_x,
                    label_y,
                    label.text,
                    fontsize=label.font_size,
                    horizontalalignment="center",
                    verticalalignment="center",
                    rotation=label.rotation,
                    rotation_mode="default",
                    color=label.color,
                    usetex=False,
                )
                if hasattr(artist, "set_parse_math"):
                    artist.set_parse_math(False)
                label_artist = artist
            label_artists.append(label_artist)

        axes.axis("off")
        artists = tuple(artist for artist in axes.get_children() if artist not in previous_artists)
        result = SpiralStripPlot(
            axes, tuple(segment_artists), tuple(label_artists), artists, mappable,
            (title, title_fontsize, title_color, title_pad, title_bold) if title else None,
            colorbar,
        )
        if fit:
            result.fit()
        else:
            # Standalone cropping supplies its own layout after plotting.
            result._update_decorations()
        completed = True
        return result
    finally:
        if not completed:
            # A failed embedded call must not leave a partially drawn strip.
            for artist in tuple(axes.get_children()):
                if artist not in previous_artists:
                    artist.remove()
            xlim, ylim, aspect, adjustable, axison = previous_view
            axes.set_xlim(xlim)
            axes.set_ylim(ylim)
            axes.set_aspect(aspect, adjustable=adjustable)
            axes.axison = axison
            axes.apply_aspect()


def draw_spiral_strip(
    image_filename=False,
    dpi=300,
    r0=10,
    space=15,
    fi0_deg=45,
    number_of_segments=0,
    width=20,
    segment_length=40,
    maximum_length_of_subsegment=10,
    segment_color='random',
    values=None,
    colormap_name='coolwarm',
    segment_edge_linecolor='same_as_segment',
    segment_edge_linewidth=0.3,
    labels1_text=None,
    labels1_fontsize=4,
    labels1_color='same_as_segment',
    labels1_pad=3,
    antialiased=True,
    gap_between_consecutive_segments=0,
    accurate_lengths=False,
    show=True,
    curved_boundaries=False,
    curve_tolerance=0.01,
    title=None,
    title_fontsize=12,
    title_color='black',
    title_pad=8,
    title_bold=False,
    show_colorbar=False,
    colorbar_suffix='',
    colorbar_width_percent=60,
    colorbar_fontsize=6,
    colorbar_labelcolor='#6b7280',
    curved_labels=False,
    transparent=False,
):
    """Create a spiral strip, optionally save it, and optionally display it.

    Parameters
    ----------
    image_filename : str, path-like, or False, default False
        False disables saving. Otherwise, supply a nonempty text output path
        in an existing directory. The extension selects a registered
        Matplotlib format. Without an extension, the
        configured default format is appended. File-like objects are not
        accepted.
    dpi : float, default 300
        Positive resolution for saved raster output. Display uses the
        configured figure DPI. Canvas and cropped raster
        dimensions are limited to 32,768 pixels per dimension and
        100,000,000 pixels total.
    r0 : float, default 10
        Nonnegative approximate inner clearance, in plot coordinates.
    space : float, default 15
        Nonnegative addition to the radial pitch between full turns. This is
        not an exact shortest clearance between the strip boundaries.
    fi0_deg : float, default 45
        Finite rotation in degrees, reduced modulo 360 before conversion to
        radians. The unrotated centerline starts on the x-axis.
    number_of_segments : int, default 0
        Must be supplied as a positive integer.
    width : float or one-dimensional sequence, default 20
        Positive perpendicular widths. Their maximum sets the common spiral.
    segment_length : float or one-dimensional sequence, default 40
        Positive requested centerline arc lengths, in plot coordinates.
    maximum_length_of_subsegment : float, default 10
        Positive nominal sampling step limit. Smaller steps improve boundary
        smoothness for straight edges and the legacy length approximation.
        Step counts are even and at least two per segment. With both accurate
        lengths and curved boundaries enabled, adaptive refinement replaces
        these fixed steps; this argument remains validated but is not used.
    segment_color : color or sequence of colors, default "random"
        Fill colors; also accepts "random" or "by_values_and_colormap".
    values : one-dimensional sequence or None, default None
        One finite numeric value per segment when supplied. Required for
        "by_values_and_colormap"; other color modes do not use these values.
    colormap_name : str, default "coolwarm"
        Colormap for value-based fills. Each dataset is normalized separately;
        constant datasets use its midpoint.
    segment_edge_linecolor : color or sequence, default "same_as_segment"
        Outline colors; "same_as_segment" copies the fill colors. In a
        per-segment sequence, mix this value with fixed colors to match only
        selected segments. The sequence must contain exactly one entry per segment.
    segment_edge_linewidth : float, default 0.3
        Nonnegative outline width in typographic points.
    labels1_text : one-dimensional sequence or None, default None
        One label per segment. Entries are converted to strings; "" hides
        an individual label, and None hides all labels.
        Labels are literal text, limited to 10,000 characters per entry and
        200,000 in total. Invalid Unicode/control characters are rejected.
        Tabs and line breaks are allowed; line endings are normalized.
    labels1_fontsize : float or one-dimensional sequence, default 4
        Positive font sizes in typographic points.
    labels1_color : color or sequence, default "same_as_segment"
        Text colors; also accepts "same_as_segment" or "random". Per-segment
        sequences may mix "same_as_segment" with fixed colors; each matching
        entry uses its own segment's resolved fill, including random fills.
    labels1_pad : float, default 3
        Nonnegative outward distance from the boundary to the label center,
        in plot coordinates. Text extents are not included in this distance.
    antialiased : bool, default True
        Antialiasing setting passed to the polygon renderer.
    gap_between_consecutive_segments : float or sequence, default 0
        Nonnegative centerline distances omitted after each segment. The
        final gap has no visible effect.
    accurate_lengths : bool, default False
        False uses first-order angular stepping. True solves arc lengths
        with safeguarded Newton iterations, targeting relative error 1e-10
        subject to floating-point precision. This includes samples, label
        midpoints, and gaps; boundary shapes remain rendering approximations.
    show : bool, default True
        Display using Matplotlib after any requested save. With a GUI backend,
        wait until the plot windows are closed. With an inline backend, show
        the figure in the notebook. Requires a display-capable backend.
        The display is cropped to the shapes, outlines, complete labels, and title,
        with a two-point margin, preserving equal scaling and font sizes.
        At least one of a filename or show=True must be selected.
    curved_boundaries : bool, default False
        False joins sampled boundary points with straight lines. True uses
        adaptive cubic Bezier curves matching exact boundary positions and
        angular derivatives, with straight end caps. Endpoint and midpoint
        placement still follows accurate_lengths. No extra dependency is needed.
    curve_tolerance : float, default 0.01
        Positive boundary error tolerance in plot coordinates. In curved mode,
        each interval is checked at three interior angles on both boundaries
        and subdivided when the estimated error exceeds this tolerance.
        Angular spans are also limited to pi/4. The estimate is not a rigorous
        global error bound. Smaller tolerances generally require more curves.
        Ignored when curved_boundaries=False, but must still be positive/finite.
    title : str or None, default None
        Optional plain-text title centered above the complete graphic and its
        segment labels. None or blank text omits the title. Newlines are allowed.
        Limited to 10,000 characters; invalid control/surrogate characters are
        rejected. The title is included in both saved and displayed crops.
    title_fontsize : float, default 12
        Positive title font size in typographic points.
    title_color : color, default "black"
        One Matplotlib color for the title.
    title_pad : float, default 8
        Nonnegative gap in typographic points above the artwork and its labels.
    title_bold : bool, default False
        Use bold type for the title; segment label weights are unchanged.
    show_colorbar : bool, default False
        Add a horizontal colorbar below the complete artwork with only minimum
        and maximum ticks. Requires segment_color="by_values_and_colormap".
        Constant data show one centered tick and the midpoint color. The bar
        uses ordinary rectangles and text with 12-point spacing, and is
        included in both saved and displayed crops. Overlapping endpoint
        labels raise ValueError; widen the bar or reduce the label size.
    colorbar_suffix : str, default ""
        Optional plain-text units appended to each value with one separating
        space, e.g. "°C". Single line, at most 100 characters.
    colorbar_width_percent : float, default 60
        Bar width as a percentage of the complete graphic width before adding
        the bar, including the title and segment labels. Greater than 0 and at
        most 100. Label text can expand the final crop.
    colorbar_fontsize : float, default 6
        Positive tick-label font size in typographic points, at most 10,000.
    colorbar_labelcolor : color, default "#6b7280"
        One Matplotlib color for the colorbar's value labels, grey by default.
    curved_labels : bool, default False
        Follow the outer-offset curve with segment labels (experimental).
        Single-line Latin, Greek, Cyrillic and common symbols without combining
        marks are supported. Glyphs are vector paths in every export format.
        Labels may extend beyond segment ends and overlap other labels.
    transparent : bool, default False
        True removes the figure and axes backgrounds for display and saving.
        False uses the configured Matplotlib background colors and explicitly
        disables savefig transparency. Saved transparency requires a supporting
        format, such as PNG, SVG, or PDF. Segment and text colors are unchanged.

    Returns
    -------
    None
        Saves and/or displays the image, then closes the figure.

    Raises
    ------
    TypeError
        If number_of_segments is not an integer, a flag is not a Boolean,
        a numeric argument contains non-real types or Booleans, the output
        path is neither False nor a text path, or a value-based colormap name
        is not a string, or title is neither a string nor None.
    ValueError
        If numeric inputs are nonfinite or violate sign/shape constraints,
        masked data are supplied, colors or the output format are invalid,
        geometry exceeds 1,000,000 centerline points or floating-point range,
        lengths or widths cannot be resolved, raster limits are exceeded,
        the accurate solver fails, curved geometry exceeds 1,000,000 stored
        vertices or its refinement/precision limits, or both outputs are disabled.
    OSError
        If the output directory does not exist, the filename is a directory,
        or the actual save fails because of permissions or filesystem errors.
        Other renderer errors propagate from Matplotlib.

    Notes
    -----
    Per-segment numeric scalars and single colors are repeated for every
    segment. Numeric arguments must contain real Python/NumPy numbers;
    strings, Booleans, complex values, and masked arrays are rejected.
    Per-segment sequences must contain exactly number_of_segments entries.
    Geometry expands outward in input order. Boundaries are normal offsets
    approximated by line segments or cubic curves; turn overlaps and
    inner-boundary folds are not detected. Labels follow the local tangent
    without collision avoidance. Curved boundaries preserve the centerline
    label midpoint and limit refinement depth to 50 per initial half-segment.
    The configured figure canvas is checked before construction, including
    display-only calls and vector output. Raster output fixes its label-expanded
    crop before saving; these pixel limits do not apply to vector bounds.
    """
    show = _boolean(show, "show")
    transparent = _boolean(transparent, "transparent")
    dpi = _numeric_scalar(dpi, "dpi", positive=True)
    if isinstance(image_filename, (bool, np.bool_)):
        if image_filename:
            raise TypeError("image_filename must be False or a text path")
        image_filename = False
    if image_filename is False and not show:
        raise ValueError("Supply image_filename or set show=True (or both)")
    output_target = None if image_filename is False else _validate_output_target(image_filename, dpi)
    _validate_figure_canvas()
    figure, axes = plt.subplots()
    try:
        _disable_automatic_layout(figure)
        if transparent:
            figure.patch.set_facecolor("none")
            axes.patch.set_facecolor("none")
        strip = plot_spiral_strip(
            axes, fit=False,
            r0=r0,
            space=space,
            fi0_deg=fi0_deg,
            number_of_segments=number_of_segments,
            width=width,
            segment_length=segment_length,
            maximum_length_of_subsegment=maximum_length_of_subsegment,
            segment_color=segment_color,
            values=values,
            colormap_name=colormap_name,
            segment_edge_linecolor=segment_edge_linecolor,
            segment_edge_linewidth=segment_edge_linewidth,
            labels1_text=labels1_text,
            labels1_fontsize=labels1_fontsize,
            labels1_color=labels1_color,
            labels1_pad=labels1_pad,
            antialiased=antialiased,
            gap_between_consecutive_segments=gap_between_consecutive_segments,
            accurate_lengths=accurate_lengths,
            curved_boundaries=curved_boundaries,
            curve_tolerance=curve_tolerance,
            title=title,
            title_fontsize=title_fontsize,
            title_color=title_color,
            title_pad=title_pad,
            title_bold=title_bold,
            show_colorbar=show_colorbar,
            colorbar_suffix=colorbar_suffix,
            colorbar_width_percent=colorbar_width_percent,
            colorbar_fontsize=colorbar_fontsize,
            colorbar_labelcolor=colorbar_labelcolor,
            curved_labels=curved_labels,
        )
        if output_target is not None:
            output_bounds = "tight"
            if output_target.is_raster:
                _check_plot_render_sizes(strip, dpi)
                output_bounds = _check_tight_raster_size(figure, dpi)
            figure.savefig(
                output_target.filename, format=output_target.format, dpi=dpi,
                bbox_inches=output_bounds, pad_inches=0, transparent=transparent,
            )
            print(f"Saved spiral strip to: {output_target.filename}")
        if show:
            _fit_display_to_artwork(figure, axes)
            # Save first: a blocking display can unregister the figure on exit.
            plt.show(block=True)
    finally:
        plt.close(figure)


def plot_spiral_strip(
    ax, *,
    r0=10,
    space=15,
    fi0_deg=45,
    number_of_segments=0,
    width=20,
    segment_length=40,
    maximum_length_of_subsegment=10,
    segment_color='random',
    values=None,
    colormap_name='coolwarm',
    segment_edge_linecolor='same_as_segment',
    segment_edge_linewidth=0.3,
    labels1_text=None,
    labels1_fontsize=4,
    labels1_color='same_as_segment',
    labels1_pad=3,
    antialiased=True,
    gap_between_consecutive_segments=0,
    accurate_lengths=False,
    curved_boundaries=False,
    curve_tolerance=0.01,
    title=None,
    title_fontsize=12,
    title_color='black',
    title_pad=8,
    title_bold=False,
    show_colorbar=False,
    colorbar_suffix='',
    colorbar_width_percent=60,
    colorbar_fontsize=6,
    colorbar_labelcolor='#6b7280',
    curved_labels=False,
    fit=True,
):
    """Draw a strip in an existing Matplotlib axes and return SpiralStripPlot.

    Accepts the geometry, colors, labels, title, and colorbar arguments of
    draw_spiral_strip. Does not create a managed figure or display, save, resize,
    or close the caller's figure. An unmanaged reference measures the normal
    standalone layout. Fonts, strokes, colorbar, and spacing scale uniformly
    to preserve that layout's proportions, including after panel resizing.
    ax must be an unshared, linear, rectilinear Matplotlib Axes; axes inside
    a SubFigure are supported. Sets equal aspect, limits, and hides axis
    decorations, but preserves existing artists and the figure layout engine.
    Titles and colorbars default off; use ax.set_title, ax.annotate, and
    figure.colorbar(result.mappable, ax=ax) for standard customization.
    The result exposes ax, segments, labels (None for omitted labels), all
    artists, and mappable (None unless coloring by values). After changing
    the panel layout or label sizes, call figure.canvas.draw() then result.fit()
    before displaying/saving. Point-sized styles update at draw time automatically.
    fit defaults to True. Set fit=False to defer panel fitting; this is used
    by draw_spiral_strip, whose standalone crop supplies its own layout.
    Embedded rendering errors remove newly added artists and restore axes
    limits, aspect, and axis visibility. No existing artists are removed.
    """
    if not isinstance(ax, _Axes):
        raise TypeError("ax must be a Matplotlib Axes")
    if ax.name != "rectilinear" or ax.get_xscale() != "linear" or ax.get_yscale() != "linear":
        raise ValueError("ax must use rectilinear, linear coordinates")
    if len(ax.get_shared_x_axes().get_siblings(ax)) > 1 or len(ax.get_shared_y_axes().get_siblings(ax)) > 1:
        raise ValueError("ax must not share x or y limits with other axes")
    fit = _boolean(fit, "fit")
    accurate_lengths = _boolean(accurate_lengths, "accurate_lengths")
    antialiased = _boolean(antialiased, "antialiased")
    curved_labels = _boolean(curved_labels, "curved_labels")
    curved_boundaries = _boolean(curved_boundaries, "curved_boundaries")
    title_bold = _boolean(title_bold, "title_bold")
    show_colorbar = _boolean(show_colorbar, "show_colorbar")
    if not isinstance(colorbar_suffix, str):
        raise TypeError("colorbar_suffix must be a string")
    if len(colorbar_suffix) > 100 or any(
        ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF
        or ord(char) in (0xFFFE, 0xFFFF) for char in colorbar_suffix
    ):
        raise ValueError("colorbar_suffix must be valid single-line text with at most 100 characters")
    colorbar_suffix = colorbar_suffix.strip()
    colorbar_width_percent = _numeric_scalar(colorbar_width_percent, "colorbar_width_percent", positive=True)
    if colorbar_width_percent > 100:
        raise ValueError("colorbar_width_percent must be greater than 0 and at most 100")
    colorbar_fontsize = _numeric_scalar(colorbar_fontsize, "colorbar_fontsize", positive=True)
    colorbar_labelcolor = _checked_rgba(colorbar_labelcolor, "colorbar_labelcolor")
    if colorbar_fontsize > 10000:
        raise ValueError("colorbar_fontsize must not exceed 10,000 points")
    if show_colorbar and not (
        isinstance(segment_color, str) and segment_color == "by_values_and_colormap"
    ):
        raise ValueError("show_colorbar requires segment_color='by_values_and_colormap'")
    if title is None:
        title = ""
    elif not isinstance(title, str):
        raise TypeError("title must be a string or None")
    if len(title) > 10000 or any(
        ord(char) < 32 and char not in "\t\n\r"
        or 0xD800 <= ord(char) <= 0xDFFF or ord(char) in (0xFFFE, 0xFFFF)
        for char in title
    ):
        raise ValueError("title must be valid text with at most 10,000 characters")
    title = title.replace("\r\n", "\n").replace("\r", "\n") if title.strip() else ""
    title_fontsize = _numeric_scalar(title_fontsize, "title_fontsize", positive=True)
    title_pad = _numeric_scalar(title_pad, "title_pad", nonnegative=True)
    title_color = _checked_rgba(title_color, "title_color")
    if isinstance(number_of_segments, (bool, np.bool_)) or not isinstance(
        number_of_segments, (int, np.integer)
    ):
        raise TypeError("number_of_segments must be an integer")
    if number_of_segments < 1:
        raise ValueError("number_of_segments must be greater than zero")
    # Each segment needs at least three samples; reject before array allocation.
    if number_of_segments > _MAX_PATH_POINTS // 3:
        raise ValueError(
            "Requested geometry exceeds the 1,000,000 path-point limit"
        )
    count = int(number_of_segments)
    if curved_boundaries and count > _MAX_CURVE_VERTICES // 15:
        raise ValueError("Curved geometry exceeds the 1,000,000-vertex limit")

    inputs = _prepare_segment_inputs(
        count, width, segment_length, labels1_fontsize,
        gap_between_consecutive_segments, labels1_text, values,
    )
    if curved_labels:
        if sum(map(len, inputs.labels)) > 20000:
            raise ValueError("Experimental curved labels are limited to 20,000 characters in total")
        for text in inputs.labels:
            _validate_curved_label_text(text)
    maximum_step_length = _numeric_scalar(
        maximum_length_of_subsegment,
        "maximum_length_of_subsegment",
        positive=True,
    )
    r0 = _numeric_scalar(r0, "r0", nonnegative=True)
    space = _numeric_scalar(space, "space", nonnegative=True)
    fi0_deg = _numeric_scalar(fi0_deg, "fi0_deg")
    labels1_pad = _numeric_scalar(labels1_pad, "labels1_pad", nonnegative=True)
    segment_edge_linewidth = _numeric_scalar(
        segment_edge_linewidth, "segment_edge_linewidth", nonnegative=True
    )
    curve_tolerance = _numeric_scalar(
        curve_tolerance, "curve_tolerance", positive=True
    )
    figure_dpi = _numeric_scalar(ax.figure.dpi, "figure.dpi", positive=True)
    canvas_figure = ax.figure
    while not hasattr(canvas_figure, "get_size_inches"):
        canvas_figure = canvas_figure.figure
    _validate_raster_dimensions(canvas_figure.get_size_inches(), figure_dpi, "Figure canvas")
    backbone_width = _validate_backbone(inputs.widths, r0, space)

    if curved_boundaries and accurate_lengths:
        # Only anchors are required: exact start, arc-length midpoint, and end.
        step_counts = [2] * count
    else:
        # Retain the original integration density and placements in legacy mode.
        step_counts = _substep_counts(inputs.lengths, maximum_step_length)
    colors = _prepare_colors(
        count, segment_color, labels1_color, segment_edge_linecolor,
        inputs.values, colormap_name,
    )

    # Normalize before conversion so even very large finite degree values
    # do not overflow during multiplication by pi.
    rotation = np.remainder(fi0_deg, 360) * np.pi / 180
    paths, maximum_radius = _build_paths(
        inputs, step_counts, backbone_width, r0, space, rotation,
        accurate_lengths, curved_boundaries, curved_labels=curved_labels,
    )
    polygons = _build_polygons(
        paths, inputs, colors, labels1_pad, curved_boundaries, curve_tolerance,
        backbone_width, r0, space, rotation,
        curved_labels=curved_labels,
    )
    mappable = None
    if isinstance(segment_color, str) and segment_color == "by_values_and_colormap":
        mappable = _ScalarMappable(
            norm=_StripNormalize(vmin=float(np.min(inputs.values)), vmax=float(np.max(inputs.values))),
            cmap=plt.get_cmap(colormap_name),
        )
        mappable.set_array(inputs.values.copy())
    return _render_strip(
        ax, polygons, inputs.widths, colors, maximum_radius,
        backbone_width, space, segment_edge_linewidth, antialiased, figure_dpi,
        title, title_fontsize, title_color, title_pad, title_bold,
        gaps=inputs.gaps,
        colorbar=(float(np.min(inputs.values)), float(np.max(inputs.values)),
                  colormap_name, colorbar_suffix, colorbar_width_percent, colorbar_fontsize,
                  colorbar_labelcolor)
        if show_colorbar else None,
        mappable=mappable, fit=fit,
    )
