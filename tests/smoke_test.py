"""Small, headless checks of an installed Spiral Strip package.

Install the wheel or source archive to check, then run this file directly:
    python tests/smoke_test.py

Requires NumPy, Matplotlib and Pillow, without pytest or a display server.
No source-directory insertion is used: the import should resolve to the
installed package. The resolved module path is printed before the tests.
Images are created in temporary directories and removed on completion.
This suite supplements the more extensive development tests in py_test/.
"""

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

import spiralstrip


class SmokeTests(unittest.TestCase):
    def make_axes(self):
        figure, axes = plt.subplots(figsize=(4, 4), dpi=80)
        self.addCleanup(plt.close, figure)
        return figure, axes

    def test_both_boundary_modes(self):
        for curved in (True, False):
            with self.subTest(curved_boundaries=curved):
                figure, axes = self.make_axes()
                strip = spiralstrip.plot_spiral_strip(
                    axes,
                    number_of_segments=3,
                    width=[8, 12, 16],
                    segment_length=[20, 30, 40],
                    segment_color="steelblue",
                    curved_boundaries=curved,
                )
                figure.canvas.draw()
                self.assertEqual(len(strip.segments), 3)
                for segment in strip.segments:
                    vertices = segment.get_path().vertices
                    self.assertGreater(len(vertices), 2)
                    self.assertTrue(np.isfinite(vertices).all())
                self.assertTrue(np.isfinite(axes.get_xlim()).all())
                self.assertTrue(np.isfinite(axes.get_ylim()).all())

    def test_value_colors_match_mappable(self):
        figure, axes = self.make_axes()
        values = [-2, 0, 4]
        strip = spiralstrip.plot_spiral_strip(
            axes,
            number_of_segments=3,
            values=values,
            segment_color="by_values_and_colormap",
            colormap_name="viridis",
            show_colorbar=True,
            title="Smoke test",
        )
        figure.canvas.draw()
        self.assertIsNotNone(strip.mappable)
        self.assertEqual(len(strip.segments), len(values))
        for segment, value in zip(strip.segments, values):
            np.testing.assert_allclose(
                segment.get_facecolor(), strip.mappable.to_rgba(value)
            )

    def test_embedded_labels_fit_and_remove(self):
        figure, axes = self.make_axes()
        marker, = axes.plot([0], [0], marker="o", label="Caller content")
        size = figure.get_size_inches().copy()
        figures = plt.get_fignums()
        strip = spiralstrip.plot_spiral_strip(
            axes,
            number_of_segments=3,
            segment_color="tomato",
            labels1_text=["A", "", "C"],
        )
        figure.canvas.draw()
        self.assertIs(strip.fit(), strip)
        self.assertEqual(plt.get_fignums(), figures)
        np.testing.assert_array_equal(figure.get_size_inches(), size)
        self.assertEqual(len(strip.labels), 3)
        self.assertEqual(strip.labels[0].get_text(), "A")
        self.assertIsNone(strip.labels[1])
        self.assertEqual(strip.labels[2].get_text(), "C")
        strip.remove()
        self.assertTrue(all(artist.axes is None for artist in strip.artists))
        self.assertIs(marker.axes, axes)
        self.assertTrue(plt.fignum_exists(figure.number))

    def test_standalone_png(self):
        figures = plt.get_fignums()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "spiral.png"
            result = spiralstrip.draw_spiral_strip(
                output,
                number_of_segments=3,
                segment_color=["red", "green", "blue"],
                title="PNG smoke test",
                dpi=80,
                show=False,
            )
            self.assertIsNone(result)
            with Image.open(output) as image:
                self.assertEqual(image.format, "PNG")
                image.load()
                self.assertGreater(min(image.size), 1)
                self.assertTrue(
                    any(low < high for low, high in image.convert("RGB").getextrema())
                )
        self.assertEqual(plt.get_fignums(), figures)

    def test_standalone_svg(self):
        figures = plt.get_fignums()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "spiral.svg"
            spiralstrip.draw_spiral_strip(
                output,
                number_of_segments=3,
                segment_color="steelblue",
                labels1_text=["A", "B", "C"],
                show=False,
            )
            root = ET.parse(output).getroot()
            namespace = "{http://www.w3.org/2000/svg}"
            self.assertEqual(root.tag, namespace + "svg")
            self.assertGreater(len(root.findall(".//" + namespace + "path")), 0)
        self.assertEqual(plt.get_fignums(), figures)

    def test_invalid_inputs_leave_axes_unchanged(self):
        _, axes = self.make_axes()
        before = tuple(axes.get_children())
        cases = [
            {"number_of_segments": 0},
            {"number_of_segments": 3, "width": 0},
            {"number_of_segments": 3, "segment_length": float("nan")},
            {
                "number_of_segments": 3,
                "segment_color": "by_values_and_colormap",
                "values": [1, 2],
            },
        ]
        for options in cases:
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    spiralstrip.plot_spiral_strip(axes, **options)
                self.assertEqual(tuple(axes.get_children()), before)


if __name__ == "__main__":
    print(f"Testing module: {Path(spiralstrip.__file__).resolve()}", flush=True)
    unittest.main(verbosity=2)
