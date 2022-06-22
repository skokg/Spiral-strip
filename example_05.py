
# import Spiral strip functions from the library file
from spiral_strip_library_v04 import *

# -----------------------------------
# Example 5: World population growth
# -----------------------------------

year = [ 2021, 2020, 2019, 2018, 2017, 2016, 2015, 2014, 2013, 2012, 2011, 2010, 2009, 2008, 2007, 2006, 2005, 2004, 2003, 2002, 2001, 2000, 1999, 1998, 1997, 1996, 1995, 1994, 1993, 1992, 1991, 1990, 1989, 1988, 1987, 1986, 1985, 1984, 1983, 1982, 1981, 1980, 1979, 1978, 1977, 1976, 1975, 1974, 1973, 1972, 1971, 1970, 1969, 1968, 1967, 1966, 1965, 1964, 1963, 1962, 1961, 1960, 1959, 1958, 1957, 1956, 1955, 1954, 1953, 1952, 1951, 1950, 1949, 1948, 1947, 1946, 1945, 1944, 1943, 1942, 1941, 1940, 1939, 1938, 1937, 1936, 1935, 1934, 1933, 1932, 1931, 1930, 1929, 1928, 1927, 1926, 1925, 1924, 1923, 1922, 1921, 1920, 1919, 1918, 1917, 1916, 1915, 1914, 1913, 1912, 1911, 1910, 1909, 1908, 1907, 1906, 1905, 1904, 1903, 1902, 1901, 1900 ] 

# The yearly world population data in the period 1900-2021 is calculated via a seventh order polynomial that was fitted to the population data freely available on ourworldindata.org (https://ourworldindata.org/world-population-growth). Their data is based on the UN World Population Prospects (https://population.un.org/wpp/Download/Standard/Population/) and the Gapminder (https://www.gapminder.org/data/documentation/gd003/) datasets. The polynomial provides reasonably good estimates of the world population, with errors for any year in the period being smaller than 0.05 billion compared to the ourworldindata.org dataset.

y=np.asarray(year)-1900
population = 1.67275 -0.00114*y + 0.00181*pow(y,2) -8.14647E-5*pow(y,3) + 1.68001E-6*pow(y,4) -1.51827E-8*pow(y,5) + 5.88222E-11*pow(y,6) -7.04717E-14*pow(y,7)

width=population/np.amax(population)*60

population_normalized = (population - np.min(population))/np.ptp(population)
cmap = matplotlib.cm.get_cmap("coolwarm")
segment_color=[]
labels_str = []
labels1_color = []
labels1_fontsize = []
for il in range(len(year)):
	segment_color.append(cmap(population_normalized[il]))
	if (year[il]-1905) % 10 == 0:
		labels_str.append(str(year[il]))
		labels1_color.append("#A9ABAE")
		labels1_fontsize.append(4)
	elif year[il] % 10 == 0:
		labels_str.append(str(np.round(population[il],1))+"B")
		labels1_color.append(cmap(population_normalized[il]))
		labels1_fontsize.append(6)
	else:
		labels_str.append("")
		labels1_color.append("#A9ABAE")
		labels1_fontsize.append(4)

draw_spiral_strip(image_filename="example05.pdf", r0=10, space=0, fi0_deg=45, number_of_segments = len(population), width=width, segment_length=4.5, maximum_length_of_subsegment=10, segment_color=segment_color, values=population, colormap_name='coolwarm', labels1_text=labels_str, labels1_fontsize=labels1_fontsize, labels1_color=labels1_color, labels1_pad=3, dpi=300)

