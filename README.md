# The Spiral Strip Python package

<p align="center">
<img src="https://user-images.githubusercontent.com/100854268/177124517-5c479fcd-9904-4ba4-85af-c7a4b28c7503.png" width="350" alt="Spiral Strip graphic">
</p>

## Description

The package includes Python code for drawing Spiral Strip graphics. The graphic consists of color-coded segments arranged in a spiral. The width and length of each segment can vary to convey additional information. The package includes examples based on climate, population size, and historical data. For a detailed description of the visualization methodology, please refer to the open-access paper listed in the References section.

## Usage

Download `spiralstrip.py` from the [Spiral-strip GitHub repository](https://github.com/skokg/Spiral-strip), then place it beside your script or in a directory on Python's import path.

Use `draw_spiral_strip` to create a separate graphic, display it, and optionally save it to a file:

```python
from spiralstrip import draw_spiral_strip

# Display a graphic.
draw_spiral_strip(number_of_segments=4, values=[1, 2, 3, 4], segment_color="by_values_and_colormap")

# Save a PNG and display the graphic.
draw_spiral_strip("spiral.png", number_of_segments=4, values=[1, 2, 3, 4], segment_color="by_values_and_colormap", dpi=500)

# Save an SVG without displaying it.
draw_spiral_strip("spiral.svg", number_of_segments=4, show=False)
```

Use `plot_spiral_strip` to draw into an existing Matplotlib axes. This interface allows you to add your own titles and other elements, and combine multiple Spiral Strip graphics using subplots or subfigures:

```python
import matplotlib.pyplot as plt
from spiralstrip import plot_spiral_strip

fig, ax = plt.subplots(figsize=(5, 5), dpi=150)
strip = plot_spiral_strip(ax, number_of_segments=4, values=[1, 2, 3, 4], segment_color="by_values_and_colormap")
ax.set_title("My spiral strip")
fig.canvas.draw()
strip.fit()
fig.savefig("spiral.pdf", bbox_inches="tight", pad_inches=0.02)
plt.show()
plt.close(fig)
```

The plot interface accepts the geometry and appearance arguments described below, but uses an `ax` argument instead of `image_filename`, `dpi`, `show`, and `transparent`. Your script controls saving and display. For a transparent export, use `fig.savefig(..., transparent=True)`. Use unshared, linear, rectilinear axes; after changing the layout or strip labels, draw the canvas and call `strip.fit()` before saving. A combined 2×2 example is included in `example_01_to_04.py`.

## Function arguments

Please refer to the paper for a more detailed explanation of the spiral geometry. Defaults below apply to `draw_spiral_strip`; the plot interface shares the geometry and appearance defaults. Supply a positive `number_of_segments`. Per-segment lists must contain exactly one entry per segment, and numerical inputs must be finite.

- `image_filename` — String or path (default `False`). The filename, optionally including a path, of the image to save. The extension selects a format supported by Matplotlib, such as PNG, SVG, PDF, EPS, or JPEG. `False` disables saving.
- `show` — Boolean (default `True`). Display the graphic. At least saving or display must be enabled. Display requires a suitable Matplotlib backend; use `show=False` on a server without a display.
- `number_of_segments` — Integer (default `0`). The number of segments; must be supplied as a positive integer.
- `width` — Number or list of numbers (default `20`). Positive segment widths. One number applies to every segment; a list sets each width individually.
- `segment_length` — Number or list of numbers (default `40`). Positive segment centerline lengths. One number applies to every segment.
- `r0` — Number (default `10`). The approximate distance of the first segment from the center of the coordinate system; must be nonnegative.
- `space` — Number (default `15`). The spacing between segments in consecutive spiral loops; must be nonnegative.
- `fi0_deg` — Number (default `45`). The angle, in degrees, between the x-axis and the line connecting the spiral center to its starting point.
- `segment_color` — Matplotlib color or list of colors (default `"random"`). Colors may be named colors, hex strings, RGB/RGBA tuples, or other Matplotlib color formats. `"random"` generates softened random colors. `"by_values_and_colormap"` assigns colors using `values` and `colormap_name`.
- `values` — List of numbers or `None` (default `None`). One value per segment, required for value-based coloring. The minimum and maximum map to the first and last colormap colors; constant data use the midpoint color.
- `colormap_name` — String (default `"coolwarm"`). The Matplotlib colormap used for value-based segment colors.
- `labels1_text` — List of labels or `None` (default `None`). One label per segment. An empty string hides an individual label; `None` hides all labels.
- `labels1_fontsize` — Number or list of numbers (default `4`). Positive segment label font sizes in points.
- `labels1_color` — Matplotlib color or list of colors (default `"same_as_segment"`). `"same_as_segment"` matches each segment's fill color; `"random"` generates random label colors. A list may mix fixed colors and `"same_as_segment"` entries.
- `labels1_pad` — Number (default `3`). Nonnegative outward distance from a segment boundary to its label center, in plot coordinates.
- `gap_between_consecutive_segments` — Number or list of numbers (default `0`). Nonnegative gaps along the centerline after each segment. One number applies to every segment; the final gap has no visible effect.
- `segment_edge_linewidth` — Number (default `0.3`). Nonnegative segment outline width in points. Set it to `0` to disable outlines.
- `segment_edge_linecolor` — Matplotlib color or list of colors (default `"same_as_segment"`). Outline colors. A list may mix fixed colors and `"same_as_segment"` entries; `"none"` makes outlines transparent.
- `dpi` — Number (default `300`). Positive export resolution for raster images. Matplotlib's `figure.dpi` controls display resolution separately.
- `antialiased` — Boolean (default `True`). Enable antialiasing when rendering segment polygons.
- `curved_boundaries` — Boolean (default `True`). Use adaptive cubic Bézier boundaries; set `False` for adaptively subdivided straight edges. Both modes use accurate centerline lengths and `curve_tolerance` to determine boundary detail automatically.
- `curve_tolerance` — Number (default `0.01`). Positive boundary approximation tolerance in plot coordinates for both straight and curved boundaries. Smaller values generally require more edges or curves.
- `curved_labels` — Boolean (default `False`, experimental). Make segment labels follow the segment curvature. Supports single-line Latin, Greek, Cyrillic, and common symbols without combining marks. These labels export as curves; long labels may overlap neighboring labels.
- `title` — String or `None` (default `None`). Optional title above the graphic. Blank text omits the title; multiline titles are supported.
- `title_fontsize` — Number (default `12`). Positive title font size in points.
- `title_color` — Matplotlib color (default `"black"`). Title color.
- `title_pad` — Number (default `8`). Nonnegative spacing in points between the artwork, including its labels, and the title.
- `title_bold` — Boolean (default `False`). Use a bold title.
- `show_colorbar` — Boolean (default `False`). Add a horizontal colorbar below the graphic. Requires value-based segment coloring. Only the minimum and maximum values are labeled; constant data show one centered value.
- `colorbar_suffix` — String (default `""`). Optional units appended to the colorbar values, for example `"°C"`.
- `colorbar_width_percent` — Number (default `60`). Colorbar width as a percentage of the graphic width, including the title and segment labels. Must be greater than `0` and at most `100`.
- `colorbar_fontsize` — Number (default `6`). Positive colorbar label font size in points.
- `colorbar_labelcolor` — Matplotlib color (default `"#6b7280"`). Colorbar label color, gray by default.
- `transparent` — Boolean (default `False`). Remove the figure and axes backgrounds for display and saving. Use a format that supports transparency, such as PNG, SVG, or PDF.

Additional arguments for `plot_spiral_strip`:

- `ax` — The existing Matplotlib axes to draw into, supplied as the first argument.
- `fit` — Boolean (default `True`). Automatically fit the axes to the complete graphic, including labels, title, and colorbar.

Detailed restrictions are documented in the function docstrings.

## Return value

`draw_spiral_strip` returns `None`. It saves and/or displays the graphic, then closes the figure. When saving a file, it prints the filename.

`plot_spiral_strip` returns a `SpiralStripPlot` object. Its artists are accessible through `strip.segments` and `strip.labels`. Use `strip.fit()` to update the framing, or `strip.remove()` to remove the strip. The caller manages the figure.

## Required Python libraries

The code requires NumPy and Matplotlib.

## Examples

The examples are based on the open-access paper listed in the References section. Please refer to the paper for a detailed description and discussion of the examples. The current example scripts also include titles and other options added to the library since publication.

- **Examples 1–4** (source code in [example_01_to_04.py](https://github.com/skokg/Spiral-strip/blob/v2.0/example_01_to_04.py)) show average yearly 2-m temperatures in Ljubljana, Slovenia, during 1917–2017. Colder years appear in bluish colors and warmer years in reddish colors. Time increases toward the center of the spiral. The file includes separate graphics using `draw_spiral_strip` and `plot_spiral_strip`, plus a combined 2×2 Matplotlib figure using `plot_spiral_strip`.

- **Example 5** (source code in [example_05.py](https://github.com/skokg/Spiral-strip/blob/v2.0/example_05.py)) shows world population during 1900–2021. Segment colors depend on population size, and widths are proportional to population size. Labels alternate between the year and population size. Years appear in gray; population labels match the segment colors. Population is expressed in billions (for example, 1.7 B means 1.7 billion). This example uses `draw_spiral_strip`.

- **Example 6** (source code in [example_06.py](https://github.com/skokg/Spiral-strip/blob/v2.0/example_06.py)) shows seven historical wars using the estimates in the example dataset. Segment lengths are proportional to duration, and segment areas represent estimated deaths. This example uses `draw_spiral_strip` and displays the segments without labels.

## Author

Gregor Skok (Gregor.Skok@fmf.uni-lj.si)

## References

Skok G. Spiral Strip. *Applied Sciences*. 2022; 12(13):6609. [https://doi.org/10.3390/app12136609](https://doi.org/10.3390/app12136609)

## License

The Python code's license is provided in [LICENSE](https://github.com/skokg/Spiral-strip/blob/v2.0/LICENSE).
