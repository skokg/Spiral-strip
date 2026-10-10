
# Import the standalone and embedded plotting interfaces.
import matplotlib.pyplot as plt
from spiralstrip import draw_spiral_strip, plot_spiral_strip

# ----------------------------------------
# Examples 1-4: Temperature spiral strips
# ----------------------------------------

# They data values represent the average yearly 2-m temperatures in Ljubljana in the period 1917-2017. The yearly averages were calculated form the monthly average temperatures in the same priod, which were kindly provided by the Slovenian Environment Agency.

temperature = [ 11.9, 11.7, 12.2, 12.6, 11.6, 12.0 , 11.8, 10.7, 11.7, 11.6, 12.1, 11.4, 10.4, 10.7, 11.6, 11.8, 11.4, 12.2, 11.0 , 11.0 , 10.8, 9.8, 10.8, 11.9, 10.8, 11.4, 10.3, 11.1, 10.8, 10.9, 10.0 , 9.9, 9.7, 9.9, 10.5, 10.7, 10.1, 9.4, 10.3, 9.3, 10.7, 9.9, 10.7, 10.8, 10.0 , 10.0 , 10.0 , 10.1, 9.9, 10.2, 10.7, 10.8, 9.4, 10.0 , 9.7, 9.4, 10.9, 10.5, 10.5, 10.6, 10.3, 8.9, 9.7, 9.3, 10.1, 9.8, 10.9, 10.9, 10.6, 10.4, 10.1, 10.5, 10.4, 9.6, 10.3, 9.4, 8.8, 8.4, 10.0 , 9.6, 10.0 , 10.5, 9.9, 10.8, 9.0 , 9.4, 9.4, 10.6, 9.0 , 10.0 , 10.0 , 10.2, 9.3, 9.3, 10.1, 9.2, 9.9, 10.2, 9.1, 9.7, 9.2 ]

year = [ 2017, 2016, 2015, 2014, 2013, 2012, 2011, 2010, 2009, 2008, 2007, 2006, 2005, 2004, 2003, 2002, 2001, 2000, 1999, 1998, 1997, 1996, 1995, 1994, 1993, 1992, 1991, 1990, 1989, 1988, 1987, 1986, 1985, 1984, 1983, 1982, 1981, 1980, 1979, 1978, 1977, 1976, 1975, 1974, 1973, 1972, 1971, 1970, 1969, 1968, 1967, 1966, 1965, 1964, 1963, 1962, 1961, 1960, 1959, 1958, 1957, 1956, 1955, 1954, 1953, 1952, 1951, 1950, 1949, 1948, 1947, 1946, 1945, 1944, 1943, 1942, 1941, 1940, 1939, 1938, 1937, 1936, 1935, 1934, 1933, 1932, 1931, 1930, 1929, 1928, 1927, 1926, 1925, 1924, 1923, 1922, 1921, 1920, 1919, 1918, 1917 ]

# Example 1: Ljubljana temperatures basic
# - Uses draw_spiral_strip, which creates its own figure, saves a PNG, and displays the graphic.
draw_spiral_strip(image_filename='example_01.png', show=True, dpi=300, title='Ljubljana temperatures 1917–2017', title_color='#9ca3af', number_of_segments=len(temperature), values=temperature, segment_color='by_values_and_colormap', colormap_name='coolwarm', r0=10, space=15, fi0_deg=45, width=20, segment_length=40, maximum_length_of_subsegment=2, segment_edge_linewidth=0, labels1_text=None, labels1_fontsize=4, labels1_color='same_as_segment', labels1_pad=3)

# Example 2: Temperatures with years, outlines, and color bar
# - Uses draw_spiral_strip, which creates its own figure, saves an SVG, and displays the graphic.
draw_spiral_strip(image_filename='example_02.svg', show=True, dpi=300, title='Ljubljana temperatures 1917–2017', title_color='#9ca3af', number_of_segments=len(temperature), values=temperature, segment_color='by_values_and_colormap', colormap_name='coolwarm', r0=10, space=15, fi0_deg=45, width=20, segment_length=40, maximum_length_of_subsegment=2, labels1_text=year, labels1_fontsize=4, labels1_color='same_as_segment', labels1_pad=4, segment_edge_linewidth=0.3, segment_edge_linecolor='#4b5563', show_colorbar=True, colorbar_suffix='°C')

# Example 3: Short, wide segments
# - Uses draw_spiral_strip, which creates its own figure and displays the graphic without saving a file.
draw_spiral_strip(image_filename=False, show=True, dpi=300, title='Ljubljana temperatures 1917–2017', title_color='#9ca3af', number_of_segments=len(temperature), values=temperature, segment_color='by_values_and_colormap', colormap_name='coolwarm', r0=10, space=15, fi0_deg=45, width=30, segment_length=10, maximum_length_of_subsegment=2, segment_edge_linewidth=0, labels1_text=year, labels1_fontsize=4, labels1_color='same_as_segment', labels1_pad=3)

# Example 4: Open-centered temperature strip
# - Uses plot_spiral_strip, which draws into supplied Matplotlib axes; this script saves the PDF and displays the figure.
fig, ax = plt.subplots(figsize=(5, 5))
strip = plot_spiral_strip(ax, title='Ljubljana temperatures 1917–2017', title_color='#9ca3af', number_of_segments=len(temperature), values=temperature, segment_color='by_values_and_colormap', colormap_name='coolwarm', r0=120, space=15, fi0_deg=45, width=30, segment_length=60, maximum_length_of_subsegment=2, segment_edge_linewidth=0, labels1_text=None, labels1_fontsize=4, labels1_color='same_as_segment', labels1_pad=3)
fig.canvas.draw()
strip.fit()
fig.savefig("example_04.pdf", bbox_inches="tight", pad_inches=0)
print("Saved spiral strip to: example_04.pdf")
plt.show(block=True)
plt.close(fig)

# Combined example: the same four strips in a caller-owned 2x2 figure.
# - Uses plot_spiral_strip, which draws into supplied Matplotlib axes so multiple graphics can share one figure.
# Fonts, outlines, and colorbar scale with each panel automatically.
fig, axes = plt.subplots(2, 2, figsize=(8, 8), layout="constrained")
fig.get_layout_engine().set(rect=(0, 0, 1, 0.92))
fig.suptitle("Ljubljana temperatures 1917–2017", color="#9ca3af", fontsize=16, y=0.98)

# Example 1: Ljubljana temperatures basic
# - Uses plot_spiral_strip to draw into the upper-left axes of the shared figure.
strip_1 = plot_spiral_strip(axes[0, 0], number_of_segments=len(temperature), values=temperature, segment_color='by_values_and_colormap', colormap_name='coolwarm', r0=10, space=15, fi0_deg=45, width=20, segment_length=40, maximum_length_of_subsegment=2, segment_edge_linewidth=0, labels1_text=None, labels1_fontsize=4, labels1_color='same_as_segment', labels1_pad=3)

# Example 2: Temperatures with years, outlines, and color bar
# - Uses plot_spiral_strip to draw into the upper-right axes of the shared figure.
strip_2 = plot_spiral_strip(axes[0, 1], number_of_segments=len(temperature), values=temperature, segment_color='by_values_and_colormap', colormap_name='coolwarm', r0=10, space=15, fi0_deg=45, width=20, segment_length=40, maximum_length_of_subsegment=2, labels1_text=year, labels1_fontsize=4, labels1_color='same_as_segment', labels1_pad=4, segment_edge_linewidth=0.3, segment_edge_linecolor='#4b5563', show_colorbar=True, colorbar_suffix='°C')

# Example 3: Short, wide segments
# - Uses plot_spiral_strip to draw into the lower-left axes of the shared figure.
strip_3 = plot_spiral_strip(axes[1, 0], number_of_segments=len(temperature), values=temperature, segment_color='by_values_and_colormap', colormap_name='coolwarm', r0=10, space=15, fi0_deg=45, width=30, segment_length=10, maximum_length_of_subsegment=2, segment_edge_linewidth=0, labels1_text=year, labels1_fontsize=4, labels1_color='same_as_segment', labels1_pad=3)

# Example 4: Open-centered temperature strip
# - Uses plot_spiral_strip to draw into the lower-right axes of the shared figure.
strip_4 = plot_spiral_strip(axes[1, 1], number_of_segments=len(temperature), values=temperature, segment_color='by_values_and_colormap', colormap_name='coolwarm', r0=120, space=15, fi0_deg=45, width=30, segment_length=60, maximum_length_of_subsegment=2, segment_edge_linewidth=0, labels1_text=None, labels1_fontsize=4, labels1_color='same_as_segment', labels1_pad=3)

# Resolve the shared title and layout before fitting labels and colorbars.
fig.canvas.draw()
for strip in (strip_1, strip_2, strip_3, strip_4):
    strip.fit()
# Add annotations or save the whole grid with fig.savefig(...).
plt.show(block=True)
plt.close(fig)
