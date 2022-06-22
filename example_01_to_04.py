
# import Spiral strip functions from the library file
from spiral_strip_library_v04 import *

# ----------------------------------------
# Examples 1-4: Temperature spiral strips
# ----------------------------------------

# They data values represent the average yearly 2-m temperatures in Ljubljana in the period 1917-2017. The yearly averages were calculated form the monthly average temperatures in the same priod, which were kindly provided by the Slovenian Environment Agency.

temperature = [ 11.9, 11.7, 12.2, 12.6, 11.6, 12.0 , 11.8, 10.7, 11.7, 11.6, 12.1, 11.4, 10.4, 10.7, 11.6, 11.8, 11.4, 12.2, 11.0 , 11.0 , 10.8, 9.8, 10.8, 11.9, 10.8, 11.4, 10.3, 11.1, 10.8, 10.9, 10.0 , 9.9, 9.7, 9.9, 10.5, 10.7, 10.1, 9.4, 10.3, 9.3, 10.7, 9.9, 10.7, 10.8, 10.0 , 10.0 , 10.0 , 10.1, 9.9, 10.2, 10.7, 10.8, 9.4, 10.0 , 9.7, 9.4, 10.9, 10.5, 10.5, 10.6, 10.3, 8.9, 9.7, 9.3, 10.1, 9.8, 10.9, 10.9, 10.6, 10.4, 10.1, 10.5, 10.4, 9.6, 10.3, 9.4, 8.8, 8.4, 10.0 , 9.6, 10.0 , 10.5, 9.9, 10.8, 9.0 , 9.4, 9.4, 10.6, 9.0 , 10.0 , 10.0 , 10.2, 9.3, 9.3, 10.1, 9.2, 9.9, 10.2, 9.1, 9.7, 9.2 ]

year = [ 2017, 2016, 2015, 2014, 2013, 2012, 2011, 2010, 2009, 2008, 2007, 2006, 2005, 2004, 2003, 2002, 2001, 2000, 1999, 1998, 1997, 1996, 1995, 1994, 1993, 1992, 1991, 1990, 1989, 1988, 1987, 1986, 1985, 1984, 1983, 1982, 1981, 1980, 1979, 1978, 1977, 1976, 1975, 1974, 1973, 1972, 1971, 1970, 1969, 1968, 1967, 1966, 1965, 1964, 1963, 1962, 1961, 1960, 1959, 1958, 1957, 1956, 1955, 1954, 1953, 1952, 1951, 1950, 1949, 1948, 1947, 1946, 1945, 1944, 1943, 1942, 1941, 1940, 1939, 1938, 1937, 1936, 1935, 1934, 1933, 1932, 1931, 1930, 1929, 1928, 1927, 1926, 1925, 1924, 1923, 1922, 1921, 1920, 1919, 1918, 1917 ]

draw_spiral_strip(image_filename="example01.pdf", r0=10, space=15, fi0_deg=45, number_of_segments = len(temperature), width=20, segment_length=40, maximum_length_of_subsegment=2, segment_color="by_values_and_colormap", values=temperature, colormap_name='coolwarm', labels1_text=None, labels1_fontsize=4, labels1_color="same_as_segment", labels1_pad=3, dpi=300 )

draw_spiral_strip(image_filename="example02.pdf", r0=10, space=15, fi0_deg=45, number_of_segments = len(temperature), width=20, segment_length=40, maximum_length_of_subsegment=2, segment_color="by_values_and_colormap", values=temperature, colormap_name='coolwarm', labels1_text=year, labels1_fontsize=4, labels1_color="same_as_segment", labels1_pad=4, dpi=300 )

draw_spiral_strip(image_filename="example03.pdf", r0=10, space=15, fi0_deg=45, number_of_segments = len(temperature), width=30, segment_length=10, maximum_length_of_subsegment=2, segment_color="by_values_and_colormap", values=temperature, colormap_name='coolwarm', labels1_text=year, labels1_fontsize=4, labels1_color="same_as_segment", labels1_pad=3, dpi=300 )

draw_spiral_strip(image_filename="example04.pdf", r0=120, space=15, fi0_deg=45, number_of_segments = len(temperature), width=30, segment_length=60, maximum_length_of_subsegment=2, segment_color="by_values_and_colormap", values=temperature, colormap_name='coolwarm', labels1_text=None, labels1_fontsize=4, labels1_color="same_as_segment", labels1_pad=3, dpi=300 )

