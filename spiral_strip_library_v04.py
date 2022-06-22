import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

def dldfi_fi(fi, width, r0, space):
	return(np.sqrt( (2*r0+width)*(2*r0+width)/4 + (fi*(2*r0+width)*(space+width))/(2*np.pi) + ((1+fi*fi)*(space+width)*(space+width))/(4*np.pi*np.pi) ))

def e_p_fi(fi, width, r0, space, fi0):
	dx=((space+width)*np.cos(fi+fi0)-(np.pi*(2*r0+width)+fi*(space+width))*np.sin(fi+fi0))/(2*np.pi)
	dy=((space+width)*np.sin(fi+fi0)+(np.pi*(2*r0+width)+fi*(space+width))*np.cos(fi+fi0))/(2*np.pi)
	dl=np.sqrt(dx*dx+dy*dy)
	return([dy/dl,-dx/dl])

def r_fi(fi, width, r0, space):
	return(r0+width/2+((width+space)/(2*np.pi))*fi)

def polar_to_cartesian(fi, r, x0, y0, fi0):
	x=x0+r*np.cos(fi+fi0)
	y=y0+r*np.sin(fi+fi0)
	return([x,y])

def draw_spiral_strip(image_filename, dpi=300, r0=10, space=15, fi0_deg=45, number_of_segments = 0, width=20, segment_length=40, maximum_length_of_subsegment=10, segment_color="random", values=None, colormap_name='coolwarm', segment_edge_linecolor="same_as_segment", segment_edge_linewidth=0.3, labels1_text=None, labels1_fontsize=4, labels1_color="same_as_segment", labels1_pad=3, antialiased = True, gap_between_consecutive_segments = 0):
	
	if type(number_of_segments) is not int:
		print("ERROR: number_of_segments needs to be of type int")
		return(None)
	
	if number_of_segments < 1:
		print("ERROR: number_of_segments needs to be > 0")
		return(None)
	
	# check if width is a sequnce and create a vector if it is not
	if not isinstance(width, (list, np.ndarray)):
		width = np.full(number_of_segments, width)
	
	# check if  segment_length is a sequnce and create a vector if it is not
	if not isinstance(segment_length, (list, np.ndarray)):
		segment_length = np.full( number_of_segments, segment_length)
	
	# check if segment_color is a sequnce and create a vector if it is not
	if not isinstance(segment_color, (list, np.ndarray)):
		old_segment_color=segment_color
		if old_segment_color == "random":
			segment_color = []
			for ie in range(0,number_of_segments):
				segment_color.append(np.random.rand(3))
		elif (old_segment_color == "by_values_and_colormap"):
			segment_color = []
			values_normalized = (values - np.min(values))/np.ptp(values)
			cmap = matplotlib.cm.get_cmap(colormap_name)
			for ie in range(0,number_of_segments):
				segment_color.append(cmap(values_normalized[ie]))
		else:
			segment_color = np.full( number_of_segments, old_segment_color)
	
	
	# check if labels1_text is None and create a vector of empty strings if necessary
	if labels1_text is None:
		labels1_text = np.full( number_of_segments, "")
	
	# check if segment_color is a sequnce and create a vector if it is not
	if not isinstance(labels1_color, (list, np.ndarray)):
		old_labels1_color=labels1_color
		labels1_color = np.full( number_of_segments, old_labels1_color)
		if isinstance(old_labels1_color, (str)):
			if old_labels1_color == "same_as_segment":
				labels1_color = []
				for ie in range(0,number_of_segments):
					labels1_color.append(segment_color[ie])
			if old_labels1_color == "random":
				labels1_color = []
				for ie in range(0,number_of_segments):
					labels1_color.append(np.random.rand(3))
	
	# check if  labels1_fontsize is a sequnce and create a vector if it is not
	if not isinstance(labels1_fontsize, (list, np.ndarray)):
		labels1_fontsize = np.full( number_of_segments, labels1_fontsize)
	
	# checks segment_edge_color values and create a vector
	if segment_edge_linecolor == "same_as_segment":
		segment_edge_linecolor = segment_color.copy()
	else:
		segment_edge_linecolor = np.full( number_of_segments, segment_edge_linecolor)
	
	# check if spacing is a sequnce and create a vector if it is not
	if not isinstance(gap_between_consecutive_segments, (list, np.ndarray)):
		gap_between_consecutive_segments = np.full(number_of_segments, gap_between_consecutive_segments)

	fi0 = fi0_deg*np.pi/180
	fi=0
	r_max=0
	width_max=np.amax(width)
	
	path_segments = []
	for ie in range(0,number_of_segments):
		number_of_substeps_per_segment=int(np.ceil(segment_length[ie]/maximum_length_of_subsegment))
		# if necessary change to even number so the labels will be positioned in the middle of segments
		if number_of_substeps_per_segment % 2 != 0:
			number_of_substeps_per_segment+=1
		
		dl=segment_length[ie]/number_of_substeps_per_segment
		#print(str(ie)+" "+str(number_of_substeps_per_segment))
		segment = []
		for it in range(0,number_of_substeps_per_segment+1):
			r=r_fi(fi=fi,width=width_max,r0=r0,space=space)
			r_max=np.maximum(r_max,r)
			xy=polar_to_cartesian(fi=fi, r=r, x0=0, y0=0, fi0=fi0)
			e_p=e_p_fi(fi=fi, width=width_max, r0=r0, space=space, fi0=fi0)

			segment.append([xy[0],xy[1],r,fi,e_p[0],e_p[1]])
			#print(str(r)+" "+str(fi*180/np.pi)+" "+str(xy[0])+" "+str(xy[1]))
			
			#print(" ".join(list(map(str, segment))) )
			
			if it != number_of_substeps_per_segment:
				fi+=dl/dldfi_fi(fi=fi,width=width_max,r0=r0,space=space)
		
		# add spacing
		fi+=gap_between_consecutive_segments[ie]/dldfi_fi(fi=fi,width=width_max,r0=r0,space=space)
		
		path_segments.append(np.asarray(segment))
		#print("\n")
	
	fi0 = fi0_deg*np.pi/180
	polygon_segments = []
	for ips, path_segment in enumerate(path_segments):
		outside_path = []
		inside_path = []
		for ip, point in enumerate(path_segment):
			
			dx = point[4]*width[ips]/2
			dy = point[5]*width[ips]/2
			
			outside_path.append([point[0]+dx,point[1]+dy])
			inside_path.append([point[0]-dx,point[1]-dy])
		
		
		inside_path.reverse()
		path = outside_path + inside_path
		
		# add again the starting point at the endo to close the polygon
		path.append(path[0])
		
		# text position and orientation info
		middle_point=path_segment[int(len(path_segment)/2)]
		x=middle_point[0]+middle_point[4]*(width[ips]/2+labels1_pad)
		y=middle_point[1]+middle_point[5]*(width[ips]/2+labels1_pad)
		text_orientation = np.arctan2(middle_point[5], middle_point[4])*180/np.pi - 90
		text_info = [x,y,text_orientation,labels1_text[ips], labels1_color[ips],labels1_fontsize[ips]]
		
		polygon_segments.append([np.asarray(path),text_info])
	
	
	fig, ax = plt.subplots()
	plt.ylim([-(r_max+space+width_max/2), (r_max+space+width_max/2)])
	plt.xlim([-(r_max+space+width_max/2), (r_max+space+width_max/2)])
	
	ax.set_aspect('equal', adjustable='box')
	
	#values_normalized = (values - np.min(values))/np.ptp(values)
	#cmap = matplotlib.cm.get_cmap(colormap_name)
	
	for ie in range(0,number_of_segments):
		#rgba = cmap(np.random.rand(1)[0])
		polygonX = Polygon(polygon_segments[ie][0], closed=True, fill=True, facecolor=segment_color[ie], edgecolor=segment_edge_linecolor[ie], linewidth=segment_edge_linewidth, antialiased = antialiased, zorder = width[ie]/width_max)
		ax.add_patch(polygonX)
		
		# add thin lines at the start and finish to remove the white lines that happen drue to antialiasing
		
		if labels1_text[ie] != "":
			ax.text(polygon_segments[ie][1][0], polygon_segments[ie][1][1], str(polygon_segments[ie][1][3]), fontsize=polygon_segments[ie][1][5], horizontalalignment="center", verticalalignment = "center",rotation =  polygon_segments[ie][1][2], rotation_mode = "default", color = polygon_segments[ie][1][4])
		#ax.plot( path_segments[ie][:,0], path_segments[ie][:,1], 'o-')
		#ax.plot( path_segments[ie][:,0], path_segments[ie][:,1], 'o-', color=segment_color[ie])
		#ax.plot( polygon_segments[ie][1][0], polygon_segments[ie][1][1], 'o-')
		
	
	#ax.grid(color='b', linestyle='-', linewidth=0.1)
	ax.axis("off")
	
	#plt.plot(0, 0, 'o-')
	#plt.title('Masked and NaN data')
	#plt.show()
	plt.savefig(image_filename, dpi=dpi, bbox_inches='tight', pad_inches=0)
	plt.close()
	#return(path_segments)
	#return(polygon_segments)



