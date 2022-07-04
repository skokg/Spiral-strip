# The Spiral Strip python package

<p align="center">
<img src="https://user-images.githubusercontent.com/100854268/177124517-5c479fcd-9904-4ba4-85af-c7a4b28c7503.png" width="350">
</p>

--- Description:

The package includes the python code for drawing images of Spiral strip graphics. The graphic consists of color-coded segments arranged in a spiral. The width and length of each individual segment can be different, which can be used to convey additional information. The package includes several graphics examples based on climate, population size, and historical data. For a detailed description of the Spiral Strip graphic please refer to the open access paper listed below in the references section.

--- Usage:

function draw_spiral_strip(image_filename, r0, space, fi0_deg, number_of_segments, width, segment_length, maximum_length_of_subsegment, segment_color, values, colormap_name, segment_edge_linecolor, segment_edge_linewidth, labels1_text, labels1_fontsize, labels1_color, labels1_pad, antialiased, gap_between_consecutive_segments, dpi)

--- Function arguments:

Please look at the paper mentioned in the references section for a more detailed explanation of some of the arguments.

- image_filename - string. The filename (optionally also including the path) of the image to be created (it can be a vector (e.g., pdf, eps) or raster format (e.g., png, gif, jpg)). 

- number_of_segments - int. The number of segments.

- width - float or list of floats (default width = 10). The widths of all segments

- segment_length - float or list of floats (dafault segment_length = 40). The leangth of all segments

- r0 - float (default = 10). The approximate distance of the first element from the center of the coordinate system

- space - float (default = 15). The space (the width of the gap region) between the segments in two consequent loops.

- fi0_deg - float (default = 45). The angle, in degrees, between the x-axis and line that links the center of the coordinate system and the spiral starting point. 

- segment_color - matplotlib color or list of matplotlib colors (default = "random"). The colors of segment polygons. The color can be specified as a string or other color format recognized by matplotlib  (e.g., RGB tuple, named colors, hex string). There a two custom options defined. If segment_color="random", then the segment colors are randomly generated. If segment_color="by_values_and_colormap" then the colors are determined via the value and colormap_name arguments. 

- values - list of floats or None (default = None). The numerical values are related to the segments. They are used to determine the color with the help of colormap prescribed by the colormap_name. The smallest value in the list will be assigned the first color in the colormap, while the largest value will be the last color. 

- colormap_name - string (default = "coolwarm"). The name of the matplotlib's colormap to be used to determine the colors of segments.

- labels1_text - None or list of strings (default = None). The text for labels of segments. If the string for some label is "", then no label is displayed. 

- labels1_fontsize - float or list of floats (default = 4). The font size of text for the labels of segments.

- labels1_color - matplotlib color or list of matplotlib colors  (default = "same_as_segment"). The color of text for the labels of segments. There a two custom options defined. If labels1_color="random", then the colors are randomly generated. If labels1_color="same_as_segment" then the colors are identical to the colors of the corresponding segment polygons. 

- labels1_pad - float (default = 3). The width of space between the segment polygon and the corresponding label. 

- gap_between_consecutive_segments - float or list of floats (default = 0). The gap size between consequitive segments. 

- maximum_length_of_subsegment - float (default = 10). The maximum length of stepsize when the polygons are drawn. Typically the value of 10 is OK, but if the borders of the segment's polygons do not look smooth, the value can be reduced to improve the appearance. 

- segment_edge_linewidth - float (default = 0.3). The linewidth of the outlines of the segment polygon. Setting segment_edge_linewidth=0, might cause white lines to appear between consequitive segments. 

- segment_edge_linecolor - matplotlib color or list of matplotlib colors  (default = "same_as_segment"). The color of the outlines of the segment polygons. There is a  custom option defined. If segment_edge_linecolor="same_as_segment" then the colors are identical to the fill colors of the corresponding segment polygons.  

- dpi - float (default = 300). This argument only affects the raster images. Increasing the dpi value will increase the resolution of generated raster images.

- antialiased - True or False (default = True). This argument only affects the raster images. If set to true, antialiasing will be used when converting the segment polygons to a raster format, thereby improving their appearance. 


--- Return value:

No return value. If there are no errors, the function will create a file specified with the image_filename argument.

--- Required python libraries:

The code requires the following python libraries to be installed: numpy and matplotlib.

--- Examples:

All the examples, along with the image shown at the top, are taken from the open-access paper listed below in the references section which is available at https://www.mdpi.com/2076-3417/12/13/6609. The paper and the images it contains are published under the CC BY 4.0 license (https://creativecommons.org/licenses/by/4.0/). Please refer to the paper for a more detailed description and discussion of the examples. 

- Examples 1-4 (source code in file example_01_to_04.py) show a hundred years of average yearly 2-m temperatures in Ljubljana, Slovenia, in the period of 1917–2017. The colder years are represented in more bluish colors, and the warmer in more reddish. The time in all strips increases towards the center of the spiral. The title in Example 4 was manually added to the image after it was produced. 

<p align="center">
<img src="https://user-images.githubusercontent.com/100854268/177120401-82a1ee2e-2a0c-46a2-b899-1963f894f9cd.png" width="700">
</p>

- Example 5 (source code in file example_05.py) shows the increase in world population in the period of 1900–2021. The colors depend on the population size, with the width being proportional to population size. The labels intermittently depict the year and population size, with the years shown in gray, while the population size is colored identically to the polygons. The population size is expressed in billions (e.g., 1.7 B represents 1.7 billion). The title was manually added to the image after it was produced. 

<p align="center">
<img src="https://user-images.githubusercontent.com/100854268/177123296-7aad54ae-7871-48e8-9155-31fd4e946cf7.png" width="350">
</p>

- Example 6 (source code in file example_06.py) shows the seven deadliest wars in human history. The length of each spiral segment is proportional to the war’s duration, and its area size to its death toll. The death toll is expressed in millions (e.g., 9.9 M represents 9.9 million). The title and labels were manually added to the image after it was produced. 

<p align="center">
<img src="https://user-images.githubusercontent.com/100854268/177123329-d9c259bf-d366-47d2-ba6f-9bfd8d0b3b38.png" width="450">
</p>

--- Author:

Gregor Skok (Gregor.Skok@fmf.uni-lj.si)

--- References:

Skok G. Spiral Strip. Applied Sciences. 2022; 12(13):6609. https://doi.org/10.3390/app12136609 

