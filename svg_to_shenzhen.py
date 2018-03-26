#!/usr/bin/python

from __future__ import absolute_import

import argparse
import datetime
import os
from pprint import pformat, pprint
import re
import svg2mod.svg as svg
import sys


#----------------------------------------------------------------------------
DEFAULT_DPI = 96 # 96 as of Inkscape 0.92


#!/usr/bin/python

pcb_header = '''
(kicad_pcb (version 4) (host pcbnew 4.0.7)

	(general
		(links 0)
		(no_connects 0)
		(area 77.052499 41.877835 92.193313 53.630501)
		(thickness 1.6)
		(drawings 8)
		(tracks 0)
		(zones 0)
		(modules 1)
		(nets 1)
	)

	(page A4)
	(layers
		(0 F.Cu signal)
		(31 B.Cu signal)
		(32 B.Adhes user)
		(33 F.Adhes user)
		(34 B.Paste user)
		(35 F.Paste user)
		(36 B.SilkS user)
		(37 F.SilkS user)
		(38 B.Mask user)
		(39 F.Mask user)
		(40 Dwgs.User user)
		(41 Cmts.User user)
		(42 Eco1.User user)
		(43 Eco2.User user)
		(44 Edge.Cuts user)
		(45 Margin user)
		(46 B.CrtYd user)
		(47 F.CrtYd user)
		(48 B.Fab user)
		(49 F.Fab user)
	)

	(setup
		(last_trace_width 0.25)
		(trace_clearance 0.2)
		(zone_clearance 0.508)
		(zone_45_only no)
		(trace_min 0.2)
		(segment_width 0.2)
		(edge_width 0.15)
		(via_size 0.6)
		(via_drill 0.4)
		(via_min_size 0.4)
		(via_min_drill 0.3)
		(uvia_size 0.3)
		(uvia_drill 0.1)
		(uvias_allowed no)
		(uvia_min_size 0.2)
		(uvia_min_drill 0.1)
		(pcb_text_width 0.3)
		(pcb_text_size 1.5 1.5)
		(mod_edge_width 0.15)
		(mod_text_size 1 1)
		(mod_text_width 0.15)
		(pad_size 1.524 1.524)
		(pad_drill 0.762)
		(pad_to_mask_clearance 0.2)
		(aux_axis_origin 0 0)
		(visible_elements FFFFFF7F)
		(pcbplotparams
			(layerselection 0x00030_80000001)
			(usegerberextensions false)
			(excludeedgelayer true)
			(linewidth 0.100000)
			(plotframeref false)
			(viasonmask false)
			(mode 1)
			(useauxorigin false)
			(hpglpennumber 1)
			(hpglpenspeed 20)
			(hpglpendiameter 15)
			(hpglpenoverlay 2)
			(psnegative false)
			(psa4output false)
			(plotreference true)
			(plotvalue true)
			(plotinvisibletext false)
			(padsonsilk false)
			(subtractmaskfromsilk false)
			(outputformat 1)
			(mirror false)
			(drillshape 1)
			(scaleselection 1)
			(outputdirectory ""))
	)

	(net 0 "")

	(net_class Default "This is the default net class."
		(clearance 0.2)
		(trace_width 0.25)
		(via_dia 0.6)
		(via_drill 0.4)
		(uvia_dia 0.3)
		(uvia_drill 0.1)
	)
'''

pcb_footer = '''
)
'''



def main():
		
		args, parser = get_arguments()

		pretty = args.format == 'pretty'
		use_mm = args.units == 'mm'

		if pretty:

				if not use_mm:
						print( "Error: decimil units only allowed with legacy output type" )
						sys.exit( -1 )

				#if args.include_reverse:
						#print(
								#"Warning: reverse footprint not supported or required for" +
								#" pretty output format"
						#)

		# Import the SVG:
		imported = Svg2ModImport(
				args.input_file_name,
				args.module_name,
				args.module_value
		)

		# Pick an output file name if none was provided:
		if args.output_file_name is None:

				args.output_file_name = os.path.splitext(
						os.path.basename( args.input_file_name )
				)[ 0 ]

		# Append the correct file name extension if needed:
		if pretty:
				extension = ""
		else:
				extension = ".mod"
		if args.output_file_name[ - len( extension ) : ] != extension:
				args.output_file_name += extension

		# Create an exporter:
		if pretty:
				exported = Svg2ModExportPretty(
						imported,
						args.output_file_name,
						args.scale_factor,
						args.precision,
						args.dpi,
				)

		# Export the footprint:
		exported.write()


#----------------------------------------------------------------------------

class LineSegment( object ):

		#------------------------------------------------------------------------

		@staticmethod
		def _on_segment( p, q, r ):
				""" Given three colinear points p, q, and r, check if
						point q lies on line segment pr. """

				if (
						q.x <= max( p.x, r.x ) and
						q.x >= min( p.x, r.x ) and
						q.y <= max( p.y, r.y ) and
						q.y >= min( p.y, r.y )
				):
						return True

				return False


		#------------------------------------------------------------------------

		@staticmethod
		def _orientation( p, q, r ):
				""" Find orientation of ordered triplet (p, q, r).
						Returns following values
						0 --> p, q and r are colinear
						1 --> Clockwise
						2 --> Counterclockwise
				"""

				val = (
						( q.y - p.y ) * ( r.x - q.x ) -
						( q.x - p.x ) * ( r.y - q.y )
				)

				if val == 0: return 0
				if val > 0: return 1
				return 2


		#------------------------------------------------------------------------

		def __init__( self, p = None, q = None ):

				self.p = p
				self.q = q


		#------------------------------------------------------------------------

		def connects( self, segment ):

				if self.q.x == segment.p.x and self.q.y == segment.p.y: return True
				if self.q.x == segment.q.x and self.q.y == segment.q.y: return True
				if self.p.x == segment.p.x and self.p.y == segment.p.y: return True
				if self.p.x == segment.q.x and self.p.y == segment.q.y: return True
				return False


		#------------------------------------------------------------------------

		def intersects( self, segment ):
				""" Return true if line segments 'p1q1' and 'p2q2' intersect.
						Adapted from:
							http://www.geeksforgeeks.org/check-if-two-given-line-segments-intersect/
				"""

				# Find the four orientations needed for general and special cases:
				o1 = self._orientation( self.p, self.q, segment.p )
				o2 = self._orientation( self.p, self.q, segment.q )
				o3 = self._orientation( segment.p, segment.q, self.p )
				o4 = self._orientation( segment.p, segment.q, self.q )

				return (

						# General case:
						( o1 != o2 and o3 != o4 )

						or

						# p1, q1 and p2 are colinear and p2 lies on segment p1q1:
						( o1 == 0 and self._on_segment( self.p, segment.p, self.q ) )

						or

						# p1, q1 and p2 are colinear and q2 lies on segment p1q1:
						( o2 == 0 and self._on_segment( self.p, segment.q, self.q ) )

						or

						# p2, q2 and p1 are colinear and p1 lies on segment p2q2:
						( o3 == 0 and self._on_segment( segment.p, self.p, segment.q ) )

						or

						# p2, q2 and q1 are colinear and q1 lies on segment p2q2:
						( o4 == 0 and self._on_segment( segment.p, self.q, segment.q ) )
				)


		#------------------------------------------------------------------------

		def q_next( self, q ):

				self.p = self.q
				self.q = q


		#------------------------------------------------------------------------

#----------------------------------------------------------------------------

class PolygonSegment( object ):

		#------------------------------------------------------------------------

		def __init__( self, points ):

				self.points = points

				if len( points ) < 3:
						print(
								"Warning:"
								" Path segment has only {} points (not a polygon?)".format(
										len( points )
								)
						)


		#------------------------------------------------------------------------

		# KiCad will not "pick up the pen" when moving between a polygon outline
		# and holes within it, so we search for a pair of points connecting the
		# outline (self) to the hole such that the connecting segment will not
		# cross the visible inner space within any hole.
		def _find_insertion_point( self, hole, holes ):

				#print( "      Finding insertion point.  {} holes".format( len( holes ) ) )

				# Try the next point on the container:
				for cp in range( len( self.points ) ):
						container_point = self.points[ cp ]

						#print( "      Trying container point {}".format( cp ) )

						# Try the next point on the hole:
						for hp in range( len( hole.points ) - 1 ):
								hole_point = hole.points[ hp ]

								#print( "      Trying hole point {}".format( cp ) )

								bridge = LineSegment( container_point, hole_point )

								# Check for intersection with each other hole:
								for other_hole in holes:

										#print( "      Trying other hole.  Check = {}".format( hole == other_hole ) )

										# If the other hole intersects, don't bother checking
										# remaining holes:
										if other_hole.intersects(
												bridge,
												check_connects = (
														other_hole == hole or other_hole == self
												)
										): break

										#print( "        Hole does not intersect." )

								else:
										print( "      Found insertion point: {}, {}".format( cp, hp ) )

										# No other holes intersected, so this insertion point
										# is acceptable:
										return ( cp, hole.points_starting_on_index( hp ) )

				print(
						"Could not insert segment without overlapping other segments"
				)


		#------------------------------------------------------------------------

		# Return the list of ordered points starting on the given index, ensuring
		# that the first and last points are the same.
		def points_starting_on_index( self, index ):

				points = self.points

				if index > 0:

						# Strip off end point, which is a duplicate of the start point:
						points = points[ : -1 ]

						points = points[ index : ] + points[ : index ]

						points.append(
								svg.Point( points[ 0 ].x, points[ 0 ].y )
						)

				return points


		#------------------------------------------------------------------------

		# Return a list of points with the given polygon segments (paths) inlined.
		def inline( self, segments ):

				if len( segments ) < 1:
						return self.points

				print( "    Inlining {} segments...".format( len( segments ) ) )

				all_segments = segments[ : ] + [ self ]
				insertions = []

				# Find the insertion point for each hole:
				for hole in segments:

						insertion = self._find_insertion_point(
								hole, all_segments
						)
						if insertion is not None:
								insertions.append( insertion )

				insertions.sort( key = lambda i: i[ 0 ] )

				inlined = [ self.points[ 0 ] ]
				ip = 1
				points = self.points

				for insertion in insertions:

						while ip <= insertion[ 0 ]:
								inlined.append( points[ ip ] )
								ip += 1

						if (
								inlined[ -1 ].x == insertion[ 1 ][ 0 ].x and
								inlined[ -1 ].y == insertion[ 1 ][ 0 ].y
						):
								inlined += insertion[ 1 ][ 1 : -1 ]
						else:
								inlined += insertion[ 1 ]

						inlined.append( svg.Point(
								points[ ip - 1 ].x,
								points[ ip - 1 ].y,
						) )

				while ip < len( points ):
						inlined.append( points[ ip ] )
						ip += 1

				return inlined


		#------------------------------------------------------------------------

		def intersects( self, line_segment, check_connects ):

				hole_segment = LineSegment()

				# Check each segment of other hole for intersection:
				for point in self.points:

						hole_segment.q_next( point )

						if hole_segment.p is not None:

								if (
										check_connects and
										line_segment.connects( hole_segment )
								): continue

								if line_segment.intersects( hole_segment ):

										#print( "Intersection detected." )

										return True

				return False


		#------------------------------------------------------------------------

		# Apply all transformations and rounding, then remove duplicate
		# consecutive points along the path.
		def process( self, transformer, flip ):

				points = []
				for point in self.points:

						point = transformer.transform_point( point, flip )

						if (
								len( points ) < 1 or
								point.x != points[ -1 ].x or
								point.y != points[ -1 ].y
						):
								points.append( point )

				if (
						points[ 0 ].x != points[ -1 ].x or
						points[ 0 ].y != points[ -1 ].y
				):
						#print( "Warning: Closing polygon. start=({}, {}) end=({}, {})".format(
								#points[ 0 ].x, points[ 0 ].y,
								#points[ -1 ].x, points[ -1 ].y,
						#) )

						points.append( svg.Point(
								points[ 0 ].x,
								points[ 0 ].y,
						) )

				#else:
						#print( "Polygon closed: start=({}, {}) end=({}, {})".format(
								#points[ 0 ].x, points[ 0 ].y,
								#points[ -1 ].x, points[ -1 ].y,
						#) )

				self.points = points


		#------------------------------------------------------------------------

#----------------------------------------------------------------------------

class Svg2ModImport( object ):

		#------------------------------------------------------------------------

		def __init__( self, file_name, module_name, module_value ):

				self.file_name = file_name
				self.module_name = module_name
				self.module_value = module_value

				print( "Parsing SVG..." )
				self.svg = svg.parse( file_name )


		#------------------------------------------------------------------------

#----------------------------------------------------------------------------

class Svg2ModExport( object ):

		#------------------------------------------------------------------------

		@staticmethod
		def _convert_decimil_to_mm( decimil ):
				return float( decimil ) * 0.00254


		#------------------------------------------------------------------------

		@staticmethod
		def _convert_mm_to_decimil( mm ):
				return int( round( mm * 393.700787 ) )


		#------------------------------------------------------------------------

		def _get_fill_stroke( self, item ):

				fill = True
				stroke = True
				stroke_width = 0.0

				if item.style is not None and item.style != "":

						for property in item.style.split( ";" ):

								nv = property.split( ":" );
								name = nv[ 0 ].strip()
								value = nv[ 1 ].strip()

								if name == "fill" and value == "none":
										fill = False

								elif name == "stroke" and value == "none":
										stroke = False

								elif name == "stroke-width":
										value = value.replace( "px", "" )
										stroke_width = float( value ) * 25.4 / float(self.dpi)

				if not stroke:
						stroke_width = 0.0
				elif stroke_width is None:
						# Give a default stroke width?
						stroke_width = self._convert_decimil_to_mm( 1 )

				return fill, stroke, stroke_width


		#------------------------------------------------------------------------

		def __init__(
				self,
				svg2mod_import,
				file_name,
				scale_factor = 1.0,
				precision = 20.0,
				use_mm = True,
				dpi = DEFAULT_DPI,
		):
				if use_mm:
						# 25.4 mm/in;
						scale_factor *= 25.4 / float(dpi)
						use_mm = True
				else:
						# PCBNew uses "decimil" (10K DPI);
						scale_factor *= 10000.0 / float(dpi)

				self.imported = svg2mod_import
				self.file_name = file_name
				self.scale_factor = scale_factor
				self.precision = precision
				self.use_mm = use_mm
				self.dpi = dpi
				self.edgecut_mode = False

		#------------------------------------------------------------------------

		def _calculate_translation( self ):

				min_point, max_point = self.imported.svg.bbox()

				# Center the drawing:
				adjust_x = min_point.x + ( max_point.x - min_point.x ) / 2.0
				adjust_y = min_point.y + ( max_point.y - min_point.y ) / 2.0

				self.translation = svg.Point(
						0.0 - adjust_x,
						0.0 - adjust_y,
				)


		#------------------------------------------------------------------------

		# Find and keep only the layers of interest.
		def _prune( self, items = None ):



				if items is None:

						self.layers = {}
						for name in self.layer_map.iterkeys():
								self.layers[ name ] = None

						items = self.imported.svg.items
						self.imported.svg.items = []
				
				contain_fmask = False
				contain_bmask = False

				for item in items:
					if not isinstance( item, svg.Group ):
						continue
					if item.name == "Drill":
						self.imported.svg.items.append( item )
					if item.name == "F.Mask":
						if (len(item.items)) > 0:
							contain_fmask = True
					if item.name == "B.Mask":
						if (len(item.items)) > 0:
							contain_bmask = True
					

				for item in items:

						if not isinstance( item, svg.Group ):
								continue							

						for name in self.layers.iterkeys():
								
								#if re.search( name, item.name, re.I ):
								if name == item.name:
										print( "Found SVG layer: {}".format( item.name ) )
										self.imported.svg.items.append( item )
										self.layers[ name ] = item

										if (item.name == "F.Cu" and contain_fmask == False):
											fmask = item
											fmask.name = "F.Mask"
											self.imported.svg.items.append( fmask )
											self.layers[ fmask.name ] = fmask											

										if (item.name == "B.Cu" and contain_bmask == False):
											fmask = item
											fmask.name = "B.Mask"
											self.imported.svg.items.append( fmask )
											self.layers[ fmask.name ] = fmask	

								
										break
						else:
								self._prune( item.items )


		#------------------------------------------------------------------------

		def _write_items( self, items, layer, flip = False ):

				for item in items:

						if isinstance( item, svg.Group ):
								self._write_items( item.items, layer, flip )
								continue

						elif isinstance( item, svg.Path ):

								segments = [
										PolygonSegment( segment )
										for segment in item.segments(
												precision = self.precision
										)
								]

								for segment in segments:
										segment.process( self, flip )

								if len( segments ) > 1:
										points = segments[ 0 ].inline( segments[ 1 : ] )

								elif len( segments ) > 0:
										points = segments[ 0 ].points

								fill, stroke, stroke_width = self._get_fill_stroke( item )

								if not self.use_mm:
										stroke_width = self._convert_mm_to_decimil(
												stroke_width
										)

								print( "    Writing polygon with {} points".format(
										len( points ) )
								)
								# print "debok " , fill
								self._write_polygon(
										points, layer, fill, stroke, stroke_width
								)

						else:
								print( "Unsupported SVG element: {}".format(
										item.__class__.__name__
								) )


		#------------------------------------------------------------------------

		def _write_module( self, front ):

				module_name = self._get_module_name( front )

				min_point, max_point = self.imported.svg.bbox()
				min_point = self.transform_point( min_point, flip = False )
				max_point = self.transform_point( max_point, flip = False )

				label_offset = 1200
				label_size = 600
				label_pen = 120

				if self.use_mm:
						label_size = self._convert_decimil_to_mm( label_size )
						label_pen = self._convert_decimil_to_mm( label_pen )
						reference_y = min_point.y - self._convert_decimil_to_mm( label_offset )
						value_y = max_point.y + self._convert_decimil_to_mm( label_offset )
				else:
						reference_y = min_point.y - label_offset
						value_y = max_point.y + label_offset

				self._write_module_header(
						label_size, label_pen,
						reference_y, value_y,
						front,
				)

				for name, group in self.layers.iteritems():

						if group is None or name == "Edge.Cuts" : continue

						layer = self._get_layer_name( name, front )

						#print( "  Writing layer: {}".format( name ) )
						self._write_items( group.items, layer, not front )

				self._write_module_footer( front )

				

		#------------------------------------------------------------------------

		def _write_edge_cuts( self, front ):

				module_name = self._get_module_name( front )

				min_point, max_point = self.imported.svg.bbox()
				min_point = self.transform_point( min_point, flip = False )
				max_point = self.transform_point( max_point, flip = False )

				label_offset = 1200
				label_size = 600
				label_pen = 120

				if self.use_mm:
						label_size = self._convert_decimil_to_mm( label_size )
						label_pen = self._convert_decimil_to_mm( label_pen )
						reference_y = min_point.y - self._convert_decimil_to_mm( label_offset )
						value_y = max_point.y + self._convert_decimil_to_mm( label_offset )
				else:
						reference_y = min_point.y - label_offset
						value_y = max_point.y + label_offset


				for name, group in self.layers.iteritems():

						if group is None: continue
						if (name == "Edge.Cuts"):
							layer = self._get_layer_name( name, front )
							self._write_items( group.items, layer, not front )

				
		#------------------------------------------------------------------------

		def _write_footprint( self, front ):

				dip_footprint = """
				(module SMD_Packages:SO-16-N (layer F.Cu) (tedit 0) (tstamp 5AAF3D82)
					(at %f %f %f)
					(descr "Module CMS SOJ 16 pins large")
					(tags "CMS SOJ")
					(path /5AAF3111)
					(attr smd)
					(fp_text reference U1 (at 0.127 -1.27 45) (layer F.SilkS)
					(effects (font (size 1 1) (thickness 0.15)))
					)
					(fp_text value 74HC595 (at 0 1.27 45) (layer F.Fab)
					(effects (font (size 1 1) (thickness 0.15)))
					)
					(fp_line (start -5.588 -0.762) (end -4.826 -0.762) (layer F.SilkS) (width 0.15))
					(fp_line (start -4.826 -0.762) (end -4.826 0.762) (layer F.SilkS) (width 0.15))
					(fp_line (start -4.826 0.762) (end -5.588 0.762) (layer F.SilkS) (width 0.15))
					(fp_line (start 5.588 -2.286) (end 5.588 2.286) (layer F.SilkS) (width 0.15))
					(fp_line (start 5.588 2.286) (end -5.588 2.286) (layer F.SilkS) (width 0.15))
					(fp_line (start -5.588 2.286) (end -5.588 -2.286) (layer F.SilkS) (width 0.15))
					(fp_line (start -5.588 -2.286) (end 5.588 -2.286) (layer F.SilkS) (width 0.15))
					
					(model SMD_Packages.3dshapes/SO-16-N.wrl
					(at (xyz 0 0 0))
					(scale (xyz 0.5 0.4 0.5))
					(rotate (xyz 0 0 0))
					)
				)
				"""

				module_name = self._get_module_name( front )

				min_point, max_point = self.imported.svg.bbox()
				min_point = self.transform_point( min_point, flip = False )
				max_point = self.transform_point( max_point, flip = False )

				label_offset = 1200
				label_size = 600
				label_pen = 120

				if self.use_mm:
						label_size = self._convert_decimil_to_mm( label_size )
						label_pen = self._convert_decimil_to_mm( label_pen )
						reference_y = min_point.y - self._convert_decimil_to_mm( label_offset )
						value_y = max_point.y + self._convert_decimil_to_mm( label_offset )
				else:
						reference_y = min_point.y - label_offset
						value_y = max_point.y + label_offset


				for name, group in self.layers.iteritems():

						if group is None: continue
						if (name == "F.Cu" or name == "B.Cu"):
							layer = self._get_layer_name( name, front )
							for item in group.items:
								# item.transform()
								if isinstance( item, svg.Rect ) and hasattr(item, "type"):
									# print "DEBOK RECT"

									start_xy = self.transform_point(item.segments()[0][0]*1.0666794869689005, not front)
									end_xy =  self.transform_point(item.segments()[0][2]*1.0666794869689005, not front)

									center_x = start_xy.x + (end_xy.x - start_xy.x)/2
									center_y = start_xy.y + (end_xy.y - start_xy.y)/2
									
									# foot_coord = self.transform_point(item.segments()[0][2]*1.0666794869689005, not front)
									# print vars(item)

									if (item.type == "dip16"):
										self.output_file.write(dip_footprint % (center_x, center_y, -1 * float(item.rotation) ))
									
									# print item.P1*1.0666794869689005, item.P2*1.0666794869689005

								if isinstance( item, svg.Path ):
									# print "DEBOK PATH"
									# print (item.items)
									# new = svg.Point(item.segments()[0][0])
									# print item.segments()[0][0]
									# (12.568,1.972)
									# (273.000,193.906)
									# print item.segments()
									# print ( self.transform_point(item.segments()[0][0], not front ))
									continue

				


		#------------------------------------------------------------------------

		def _write_polygon_filled( self, points, layer, stroke_width = 0.0 ):

				self._write_polygon_header( points, layer )

				for point in points:
						self._write_polygon_point( point )

				self._write_polygon_footer( layer, stroke_width )


		#------------------------------------------------------------------------

		def _write_polygon_outline( self, points, layer, stroke_width ):

				prior_point = None
				for point in points:

						if prior_point is not None:
								# self.edgecut_mode = False
								if (self.edgecut_mode):
									self._write_edgecut_segment(
											prior_point, point, layer, stroke_width
									)
								else:
									self._write_polygon_segment(
											prior_point, point, layer, stroke_width
									)									
								

						prior_point = point


		#------------------------------------------------------------------------

		def transform_point( self, point, flip = False ):

				transformed_point = svg.Point(
						( point.x + self.translation.x ) * self.scale_factor,
						( point.y + self.translation.y ) * self.scale_factor,
				)

				if flip:
						transformed_point.x *= -1

				if self.use_mm:
						transformed_point.x = round( transformed_point.x, 12 )
						transformed_point.y = round( transformed_point.y, 12 )
				else:
						transformed_point.x = int( round( transformed_point.x ) )
						transformed_point.y = int( round( transformed_point.y ) )

				return transformed_point


		#------------------------------------------------------------------------

		def write( self ):

				self._prune()

				# Must come after pruning:
				translation = self._calculate_translation()

				print( "Writing module file: {}".format( self.file_name ) )
				self.output_file = open( self.file_name, 'w' )

				self._write_pcb_header()
				self._write_library_intro()

				self._write_module( front = True )
				self.edgecut_mode = True
				self._write_edge_cuts( front = True)

				self.edgecut_mode = False

				self._write_footprint(front = True)
				self._write_wirepad()
				self._write_pcb_footer()

				self.output_file.close()
				self.output_file = None


		#------------------------------------------------------------------------

#----------------------------------------------------------------------------

class Svg2ModExportPretty( Svg2ModExport ):

		layer_map = {
				#'inkscape-name' : kicad-name,
				'F.Cu' :    "F.Cu",
				'B.Cu' :    "B.Cu",				
				'Adhes' : "{}.Adhes",
				'Paste' : "{}.Paste",
				'F.SilkS' : "F.SilkS",
				'B.SilkS' : "B.SilkS",				
				'F.Mask' :  "F.Mask",
				'B.Mask' :  "B.Mask",				
				'CrtYd' : "{}.CrtYd",
				'Fab' :   "{}.Fab",
				'Edge.Cuts' : "Edge.Cuts"
		}


		#------------------------------------------------------------------------

		def _get_layer_name( self, name, front ):

				if front:
						return self.layer_map[ name ].format("F")
				else:
						return self.layer_map[ name ].format("B")


		#------------------------------------------------------------------------

		def _get_module_name( self, front = None ):

				return self.imported.module_name


		#------------------------------------------------------------------------

		def _write_pcb_header( self ):
			self.output_file.write(pcb_header)

		def _write_pcb_footer( self ):
			self.output_file.write(pcb_footer)
		
		def _write_wirepad( self ):
			root = (self.imported.svg.root)

			pad_string = ""
			count = 0

			pad_template = """
				(module Wire_Pads:SolderWirePad_single_0-8mmDrill (layer F.Cu) (tedit 0) (tstamp 5ABD66D0)
					(at %f %f)
					(pad %d thru_hole circle (at 0 0) (size 1.99898 1.99898) (drill 0.8001) (layers *.Cu *.Mask))
				)
			"""

			items = self.imported.svg.items
			for item in items:
				# print item.name
				if (item.name == "Drill"): 
					# item.transform()

					for drill in item.items:
						count = count + 1
						# print drill.matrix.vect
						old_center = drill.center
						# drill.transform(item.matrix)
						new_center = drill.center

						# transx = ((new_center.x - old_center.x) * 2 ) / (96/25.4)
						# transy = ((new_center.y - old_center.y) * 2 ) / (96/25.4)

						test = svg.Point(drill.center.x*1.0666794869689005,drill.center.y*1.0666794869689005)
						new_pad = self.transform_point(test)
						pad_x = new_pad.x
						pad_y = new_pad.y
						pad_string = pad_string + pad_template % (pad_x, pad_y, count)
			
			self.output_file.write(pad_string)


		

		#------------------------------------------------------------------------

		def _write_library_intro( self ):

				self.output_file.write( """(module {0} (layer F.Cu) (tedit {1:8X})
	(attr smd)
	(descr "{2}")
	(tags {3})
""".format(
		self.imported.module_name, #0
		int( round( os.path.getctime( #1
				self.imported.file_name
		) ) ),
		"Imported from {}".format( self.imported.file_name ), #2
		"svg2mod", #3
)
				)


		#------------------------------------------------------------------------

		def _write_module_footer( self, front ):

				self.output_file.write( "\n)" )


		#------------------------------------------------------------------------

		def _write_module_header(
				self,
				label_size,
				label_pen,
				reference_y,
				value_y,
				front,
		):
				if front:
						side = "F"
				else:
						side = "B"

				self.output_file.write(
"""  (fp_text reference {0} (at 0 {1}) (layer {2}.SilkS) hide
		(effects (font (size {3} {3}) (thickness {4})))
	)
	(fp_text value {5} (at 0 {6}) (layer {2}.SilkS) hide
		(effects (font (size {3} {3}) (thickness {4})))
	)""".format(

		self._get_module_name(), #0
		reference_y, #1
		side, #2
		label_size, #3
		label_pen, #4
		self.imported.module_value, #5
		value_y, #6
)
				)


		#------------------------------------------------------------------------

		def _write_modules( self ):

				self._write_module( front = True )


		#------------------------------------------------------------------------

		def _write_polygon( self, points, layer, fill, stroke, stroke_width ):

				if fill:
						self._write_polygon_filled(
								points, layer, stroke_width
						)

				# Polygons with a fill and stroke are drawn with the filled polygon
				# above:
				if stroke and not fill:

						self._write_polygon_outline(
								points, layer, stroke_width
						)


		#------------------------------------------------------------------------

		def _write_polygon_footer( self, layer, stroke_width ):

				self.output_file.write(
						"    )\n    (layer {})\n    (width {})\n  )".format(
								layer, stroke_width
						)
				)


		#------------------------------------------------------------------------

		def _write_polygon_header( self, points, layer ):

						self.output_file.write( "\n  (fp_poly\n    (pts \n" )


		#------------------------------------------------------------------------

		def _write_polygon_point( self, point ):

						self.output_file.write(
								"      (xy {} {})\n".format( point.x, point.y )
						)


		#------------------------------------------------------------------------

		def _write_polygon_segment( self, p, q, layer, stroke_width ):

				self.output_file.write(
						"""\n  (fp_line
		(start {} {})
		(end {} {})
		(layer {})
		(width {})
	)""".format(
		p.x, p.y,
		q.x, q.y,
		layer,
		stroke_width,
)
				)

		#------------------------------------------------------------------------

		def _write_edgecut_segment( self, p, q, layer, stroke_width ):

				self.output_file.write(
						"""\n  (gr_line
		(start {} {})
		(end {} {})
		(layer {})
		(width {})
	)""".format(
		p.x, p.y,
		q.x, q.y,
		layer,
		stroke_width,
)
				)


		#------------------------------------------------------------------------

#----------------------------------------------------------------------------

def get_arguments():

		parser = argparse.ArgumentParser(
				description = (
						'Convert Inkscape SVG drawings to KiCad footprint modules.'
				)
		)

		#------------------------------------------------------------------------

		parser.add_argument(
				'-i', '--input-file',
				type = str,
				dest = 'input_file_name',
				metavar = 'FILENAME',
				help = "name of the SVG file",
				required = True,
		)

		parser.add_argument(
				'-o', '--output-file',
				type = str,
				dest = 'output_file_name',
				metavar = 'FILENAME',
				help = "name of the module file",
		)

		parser.add_argument(
				'--name', '--module-name',
				type = str,
				dest = 'module_name',
				metavar = 'NAME',
				help = "base name of the module",
				default = "svg2mod",
		)

		parser.add_argument(
				'--value', '--module-value',
				type = str,
				dest = 'module_value',
				metavar = 'VALUE',
				help = "value of the module",
				default = "G***",
		)

		parser.add_argument(
				'-f', '--factor',
				type = float,
				dest = 'scale_factor',
				metavar = 'FACTOR',
				help = "scale paths by this factor",
				default = 1.0,
		)

		parser.add_argument(
				'-p', '--precision',
				type = float,
				dest = 'precision',
				metavar = 'PRECISION',
				help = "smoothness for approximating curves with line segments (float)",
				default = 10.0,
		)

		parser.add_argument(
				'--front-only',
				dest = 'front_only',
				action = 'store_const',
				const = True,
				help = "omit output of back module (legacy output format)",
				default = False,
		)

		parser.add_argument(
				'--format',
				type = str,
				dest = 'format',
				metavar = 'FORMAT',
				choices = [ 'legacy', 'pretty' ],
				help = "output module file format (legacy|pretty)",
				default = 'pretty',
		)

		parser.add_argument(
				'--units',
				type = str,
				dest = 'units',
				metavar = 'UNITS',
				choices = [ 'decimil', 'mm' ],
				help = "output units, if output format is legacy (decimil|mm)",
				default = 'mm',
		)

		parser.add_argument(
				'-d', '--dpi',
				type = int,
				dest = 'dpi',
				metavar = 'DPI',
				help = "DPI of the SVG file (int)",
				default = DEFAULT_DPI,
		)    
		
		return parser.parse_args(), parser


		#------------------------------------------------------------------------

#----------------------------------------------------------------------------
#print "ok"
main()


#----------------------------------------------------------------------------
# vi: set et sts=4 sw=4 ts=4:
