
# import Spiral strip functions from the library file
from spiral_strip_library_v04 import *

# -----------------------------------
# Example 6: Deadliest wars
# -----------------------------------

# The data about the death toll of wars was obtained from the wikipedia page "List of wars by death toll" (https://en.wikipedia.org/wiki/List_of_wars_by_death_toll). Only the data from the seven deadlies wars were used. If the death tall for a particular war was given as a range, the middle value between the the upper and lower estimate was used. 
#
# List of deadliest wars:
# - World War II (1939-1945) 85M deaths
# - World War I (1914-1918) 28M deaths
# - Second Sino-Japanese War (1937-1945) 22.5M deaths
# - Chinese Civil War (1927-1949) 9.846M deaths
# - Russian Civil War (1917-1922) 7.0M deaths
# - Second Congo War (1998-2003) 3.95M deaths
# - Korean War (1950-1953) 3.0M deaths

duration = [ 7,  5,  9, 23,  6,  6,  4]
deaths = [ 85., 28., 22.5, 9.846, 7., 3.95, 3. ]

color1='#e82b33'
color2='#31aae0'
segment_color=[]
for il in range(len(duration)):
	segment_color.append(color1)
	segment_color.append(color2)

segment_color=segment_color[0:len(duration)]

width = []
segment_length = []
for il in range(len(duration)):
	segment_length.append(duration[il]*35)
	width.append(deaths[il]*10/duration[il])

draw_spiral_strip(image_filename="example06.pdf", r0=10, space=0, fi0_deg=0, number_of_segments = len(duration), width=width, segment_length=segment_length, maximum_length_of_subsegment=10, segment_color = segment_color, values=None, colormap_name=None, labels1_text=None, labels1_fontsize=6, labels1_color="dimgray", labels1_pad=10, antialiased = True, gap_between_consecutive_segments = 20, dpi=300)

