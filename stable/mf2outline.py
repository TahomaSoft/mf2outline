#!/usr/bin/env python

#mf2outline version 20141204

#This program has been written by Linus Romer for the 
#Metaflop project by Marco Mueller and Alexis Reigel.

#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

#Copyright 2014 by Linus Romer

import os
import sys
import fontforge
import psMat # this is from python-fontforge
import glob
import subprocess
import tempfile
import shutil
import argparse
import math

# splitList will split a comma-separated string to a list of words
def splitList(a):
	lst = [] 
	for s in a:
		lst += s.split (",")
	return lst
	
# bytesToInt converts an array of bytes b to an integer n
# int.from_bytes() could replace this (python 3.2)
def bytesToInt(b): 
	shift = (len(b)-1)*8
	n = 0L
	for i in b:
		n = n  + (long (ord (i)) << shift)
		shift = shift - 8
	return n

# findWord will return -1, if the word does not appear in wordlist, else it returns the index of the word
def findWord(word,wordlist):
	i = 0
	while i < len(wordlist):
		if word == wordlist[i]:
			return i
		i += 1
	return -1
						
# importEps will import the eps-file named "eps" into the glyph "glyph"
def importEps(glyph,eps): 
	with open(eps, "r") as epsfile:
		futurefore = fontforge.layer()  # this will be the future foreground
		isWhite = False # is the current drawing/filling color white?
		linewidth = 0; # linewidth in postscript (in MF/MP this is the pen width)
		for line in epsfile:
			if not line[0] == "%": # omit comments
				words = line.split()
				# search the lines for several key words and process 
				# them in the right priority order
				
				# search for "setrgbcolor"
				index = findWord("setrgbcolor",words)
				if index >= 0: # word appears 
					if (words[index-1] == "0" 
					and words[index-2] == "0"
					and words[index-3] == "0"):
						isWhite = False
					elif (words[index-1] == "1" 
					and words[index-2] == "1"
					and words[index-3] == "1"):
						isWhite = True
					else:
						print "I do not understand this color"
						
				# search for "setlinewidth"
				index = findWord("setlinewidth",words)
				if index >= 0: # word appears 
					if (words[index-3] == "dtransform"
					and words[index-2] == "truncate"
					and words[index-1] == "idtransform"):
						linewidth = float(words[index-4])
					elif (words[index-6] == "dtransform"   
					and words[index-5] == "exch"
					and words[index-4] == "truncate"
					and words[index-3] == "exch"
					and words[index-2] == "idtransform"
					and words[index-1] == "pop"): # widths are exchanged
						if index-8 < 0: # value is on the last line
							linewidth = float(lastwords[len(lastwords)-1])
						else:
							linewidth = float(words[index-8])
					else:
						print "I do not understand this linewidth"
				
				# search for "newpath"
				index = findWord("newpath",words)
				if index >= 0: # word appears 
					contour = fontforge.contour()
					
				# search for "moveto"
				index = findWord("moveto",words)
				if index >= 0: # word appears 
					contour.moveTo(float(words[index-2]),float(words[index-1]))
				
				# search for "lineto"
				index = findWord("lineto",words)
				if index >= 0: # word appears 
					contour.lineTo(float(words[index-2]),float(words[index-1]))
					
				# search for "curveto"
				index = findWord("curveto",words)
				if index >= 0: # word appears 
					contour.cubicTo(
						(float(words[index-6]),float(words[index-5])),
						(float(words[index-4]),float(words[index-3])),
						(float(words[index-2]),float(words[index-1])))
				
				# search for "closepath"
				if "closepath" in words: 
					contour.closed = True
					# correct the direction
					if contour.isClockwise() == -1:
						contour.transform(psMat.scale(10)) # dirty trick
						if (isWhite and contour.isClockwise()) or (not isWhite and not contour.isClockwise()): # dirty trick
							contour.reverseDirection() # dirty trick
						contour.transform(psMat.scale(.1)) # dirty trick
					else:
						if (isWhite and contour.isClockwise()) or (not isWhite and not contour.isClockwise()):
							contour.reverseDirection()

				# search for "fill and stroke"
				if ("fill" in words) or ("stroke" in words): 
					if ("stroke" in words) and (linewidth != 0):
						templayer = fontforge.layer()
						templayer += contour
						if "fill" in words:
							if templayer.selfIntersects(): # this will seldom happen; the Q of cmr is an exception
								templayer.removeOverlap()
								templayer.correctDirection()
								templayer.stroke("circular",linewidth,"round","round","removeinternal") 
								templayer.removeOverlap()
							else:
								templayer.stroke("circular",linewidth,"round","round","removeinternal") 
						else:
							templayer.stroke("circular",linewidth)
						templayer.round(2) # we have set the epsilon to the tenth of one unit 
						futurefore += templayer
						futurefore.removeOverlap()

					else: # only "fill" in words or linewidth zero
						contour.round(2)
						if isWhite:
							# ceck additionally for intersections:
							# that will avoid negative contours
							# on the white paper
							
							# there are now two ways: the "exclude" way and the "intersect" way
							# we will check first, if the white area is a subset of the black area:
							whitelayer = fontforge.layer()
							whitelayer += contour
							blacklayer = futurefore.dup() 
							blacklayer.exclude(whitelayer) # exclude blacklayer from whitelayer and store it as blacklayer
							if blacklayer.isEmpty(): # now do it the "intersect" way
								contour.reverseDirection() # make it black
								templayer = futurefore.dup() 
								templayer += contour
								templayer.intersect() # now this may be black or white but should be white!
								for i in range(0,len(templayer)):
									if templayer[i].isClockwise() == -1:
										templayer[i].transform(psMat.scale(10)) # dirty trick
										if templayer[i].isClockwise(): # dirty trick
											templayer[i].reverseDirection() # dirty trick
											
										templayer[i].transform(psMat.scale(.1)) # dirty trick
									else:
										if templayer[i].isClockwise(): 
											templayer[i].reverseDirection() 
								futurefore += templayer
								futurefore.removeOverlap()
							else: # do it the intersection way
								contour.reverseDirection() # make it black
								whitelayer = fontforge.layer()
								whitelayer += contour
								blacklayer = futurefore.dup() 
								whitelayer.exclude(blacklayer) # exclude the whitelayer from the blacklayer and store the rests in whitelayer
								futurefore = whitelayer.dup()
								futurefore.correctDirection()
						else:
							futurefore += contour
							futurefore.removeOverlap()
				
				# search for "showpage"
				if "showpage" in words: 	
					print "-------- Letter %s finished ---------" % code
					
				lastwords = words # keep the last line in mind
		glyph.foreground = futurefore

# defragment will remove contours with tiny area from glyph
def defragment(font):
	for glyph in font.glyphs():	
		futurefore = fontforge.layer()
		for i in range(0,len(glyph.foreground)):
			contourlayer = fontforge.layer()
			contourlayer += glyph.foreground[i]
			if not contourlayer[0].isClockwise:
				contourlayer[0].reverseDirection()
			contourlayer.stroke("circular",1,"round","round","removeexternal") 
			if not contourlayer.isEmpty():
				futurefore += glyph.foreground[i]
		glyph.foreground = futurefore

# this class will help to manage tfm-files (TeX font metrics)
class Tfmetric:
	# read the documentation of the tftopl program to understand
	# this class better.
	
	# read a number n consisting of m bytes from the array of bytes
	def readNumber(self,m):
		n = bytesToInt(self.tail[0:m])
		self.tail = self.tail[m:]
		return n
	
	# fixword is a 4-byte representation of a binary fraction 
	def readFixword(self):
		return (self.readNumber(4)/16.0) / (1<<16);
	
	# read m fixwords and return them in an array
	def readFixwords(self,m):
		fixwords = [0.0]*m
		for i in range (0,m):
			fixwords[i] = self.readFixword()
		return fixwords
	
	# read m charinfo (consisting each of 4 bytes) that will be 
	# put into 6 fields (containing only indices of an array that
	# will be read later)
	def readCharinfo(self): 
		nc = self.ec - self.bc + 1 # number of codes/characters
		charinfo = [[0 for i in range(6)] for j in range(nc)]
		for i in range (0,nc):
			charinfo[i][0] = self.readNumber(1) # width_index 
			temp = self.readNumber(1) # height_index and depth_index 
			charinfo[i][1] = (temp & 0xf0) >> 4 # height_index (times 4)
			charinfo[i][2] = (temp & 0x0f) # depth_index 
			temp = self.readNumber(1) # italic_index and tag
			charinfo[i][3] = (temp & 0xfc) >> 6 # italic index (times 4), 6 bits
			charinfo[i][4] = (temp & 0x3) # tag
			charinfo[i][5] = self.readNumber(1) # remainder
		return charinfo
		
	def __init__ (self,f): # f is the filename of the tfm file
		self.orig = (open(f).read())
		self.tail = self.orig
		# file header:
		self.lf = self.readNumber(2) # length of the entire file
		self.lh = self.readNumber(2) # length of the header data
		self.bc = self.readNumber(2) # smallest character code in the font 
		self.ec = self.readNumber(2) # largest character code in the font 
		self.nw = self.readNumber(2) # number of words in the width table 
		self.nh = self.readNumber(2) # number of words in the height table 
		self.nd = self.readNumber(2) # number of words in the depth table 
		self.ni = self.readNumber(2) # number of words in the italic correction table 
		self.nl = self.readNumber(2) # number of words in the lig/kern table 
		self.nk = self.readNumber(2) # number of words in the kern table 
		self.ne = self.readNumber(2) # number of words in the extensible character table 
		self.np = self.readNumber(2) # number of font parameter words 
		# file body:
		# header array:
		self.checksum = self.readNumber(4) # 32-bit check sum
		self.designsize = self.readFixword() # design size of the font in TeX points
		# jump to the char_info array
		self.tail = self.orig[4*(6+self.lh):]
		self.charinfo = self.readCharinfo()
		# width array
		self.width = self.readFixwords(self.nw)
		# height array
		self.height = self.readFixwords(self.nh)
		# depth array
		self.depth = self.readFixwords(self.nd)
		# italic array
		self.italic = self.readFixwords(self.ni)
		# jump (at the moment) directly to the end of orig:
		# (remember that a word has 4 bytes)
		self.tail = self.orig[4*(6+self.lh+(self.ec-self.bc+1)+self.nw+self.nh+self.nd+self.ni+self.nl+self.nk+self.ne):]
		# param array
		self.slant = self.readFixword()
		self.space = self.readFixword()
		self.space_stretch = self.readFixword()
		self.space_shrink = self.readFixword()
		self.x_height = self.readFixword()
		self.quad = self.readFixword()
		self.extra_space = self.readFixword()
		# remove the rest (which should be empty)
		del self.tail
	
	# return the width of the char with code c
	def getCharwidth(self,c):
		return self.width[self.charinfo[c-self.bc][0]]*self.designsize
		
	# return the height of the char with code c
	def getCharheight(self,c):
		return self.height[self.charinfo[c-self.bc][1]]*self.designsize
		
	# return the depth of the char with code c
	def getChardepth(self,c):
		return self.depth[self.charinfo[c-self.bc][2]]*self.designsize
		
	# return the italic correction of the char with code c
	def getCharitalic(self,c):
		return self.italic[self.charinfo[c-self.bc][3]]*self.designsize
	
if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Generate outline fonts from Metafont sources.")
	parser.add_argument("mfsource", help="The file name of the Metafont source file")
	parser.add_argument("-v", "--verbose",
		action='store_true',
		default=False,
		help="explain what is being done")
	parser.add_argument("-vv", "--veryverbose",
		action='store_true',
		default=False,
		help="explain very detailed what is being done")
	parser.add_argument("--designsize", 
		dest="designsize",
		metavar="SIZE",
		type=float,
		default=10.0,
		help="The first guess of the design size will be SIZE (default: 10.0)")	
	parser.add_argument("--magnification", 
		dest="magnification",
		metavar="MAG",
		type=float,
		default=1.0,
		help="Set magnification for MF to MAG - larger is more exact but slower (default: 1.0)")
	parser.add_argument("--raw",
		action="store_true",
		dest="raw",
		default=False,
		help="Do not remove overlaps, round to int, add extrema, add hints...")
	parser.add_argument("--polygoncircle",
		action="store_true",
		dest="polygoncircle",
		default=False,
		help="Use polygon pens instead of circle/elliptic pens")
	parser.add_argument("--cmspecials",
		action="store_true",
		dest="cmspecials",
		default=False,
		help="Use special methods to import Computer Modern; this may override other options")
	parser.add_argument("--defragment",
		action="store_true",
		dest="defragment",
		default=False,
		help="Remove contours with tiny areas - you probably do not need it")
	parser.add_argument("--errorstopmode",
		action="store_true",
		dest="errorstopmode",
		default=False,
		help="Stop on all errors")
	parser.add_argument("-f", "--formats",
		action="append",
		dest="formats",
		default=[],
		help="Which formats to generate (choices: sfd, afm, pfa, pfb, otf, ttf, eoff, svg, tfm)")
	parser.add_argument("--encoding", 
		dest="encoding",
		metavar="ENC",
		type=str,
		default="t1",
		help="The font encoding of the Metafont source (default: t1)")	
	parser.add_argument("--fullname", 
		dest="fullname",
		metavar="FULL",
		type=str,
		default="Unknown",
		help="The full name of the font with modifiers and possible spaces")	
	parser.add_argument("--fontname", 
		dest="fontname",
		metavar="NAME",
		type=str,
		default="Unknown",
		help="The full name of the font with modifiers and without spaces")	
	parser.add_argument("--familyname", 
		dest="familyname",
		metavar="FAM",
		type=str,
		default="Unknown",
		help="The name of the font family")		
	parser.add_argument("--fullname-as-filename",
		action="store_true",
		dest="fullnameasfilename",
		default=False,
		help="Use the fullname for the name of the output file")
	parser.add_argument("--fontversion", 
		dest="version",
		metavar="VERS",
		type=str,
		default="001.001",
		help="The version of the font (default: 001.001)")	
	parser.add_argument("--copyright", 
		dest="copyright",
		metavar="COPY",
		type=str,
		default="",
		help="The copyright notice of the font")		
	parser.add_argument("--vendor", 
		dest="vendor",
		metavar="VEND",
		type=str,
		default="",
		help="The vendor of the font (limited to 4 characters)")	
	parser.add_argument("--weight", 
		dest="weight",
		metavar="WGT",
		type=int,
		default=500,
		help="The OS/2 weight of the font (default: 500)")		
	parser.add_argument("--width", 
		dest="width",
		metavar="WDT",
		type=int,
		default=5,
		help="The OS/2 width of the font (default: 5)")		
	args = parser.parse_args()
	
	args.formats = splitList(args.formats)
	if args.formats == []:
		args.formats = ["otf"] # make "otf" default format
		
	if args.veryverbose:
		args.verbose=True

	if not (os.path.isfile(args.mfsource) or os.path.isfile(args.mfsource+".mf")):
		print "Cannot find your specified source file '%s'" % args.mfsource
		exit(1)
		
	if args.verbose:
		print "Creating font file..." 
	font = fontforge.font()
	
	if args.verbose:
		print "Setting general font information..." 
	if args.encoding == "t1":
		fontforge.loadEncodingFile("t1.enc")
		font.encoding="T1Encoding"
	elif args.encoding == "ot1":
		fontforge.loadEncodingFile("ot1.enc")
		font.encoding="OT1Encoding"
	else:
		print "I do not know this encoding but will continue with t1" 
		fontforge.loadEncodingFile("t1.enc")
		font.encoding="T1Encoding"
	font.fullname = args.fullname
	font.fontname = args.fontname
	font.familyname = args.familyname
	font.version = args.version
	font.copyright = args.copyright
	font.os2_vendor = args.vendor
	font.os2_weight = args.weight
	if font.os2_weight == 100:
		font.weight = "Thin"
	elif font.os2_weight == 200:
		font.weight = "Extra-Light"
	elif font.os2_weight == 300:
		font.weight = "Light"
	elif font.os2_weight == 400:
		font.weight = "Book"
	elif font.os2_weight == 500:
		font.weight = "Medium"
	elif font.os2_weight == 600:
		font.weight = "Demi-Bold"
	elif font.os2_weight == 700:
		font.weight = "Bold"
	elif font.os2_weight == 800:
		font.weight = "Heavy"
	elif font.os2_weight == 900:
		font.weight = "Black"
	else:
		print "I do not understand your specified weight but will continue with 500..."
		font.os2_weight = 500
		font.weight = "Medium"
		
	if args.verbose:
		print "Running METAPOST for tfm and glyphs definition..." 
	mfsource = os.path.abspath("%s" % args.mfsource)
	tempdir = tempfile.mkdtemp()
	mpargs = ['mpost',
	'&%s/mfpolygoncircle' % os.path.split(os.path.abspath(sys.argv[0]))[0] 
	if args.polygoncircle 
	else '&%s/epsilon' % os.path.split(os.path.abspath(sys.argv[0]))[0] 
	if args.cmspecials 
	else '&mfplain',
	'\mode=localfont;',
	'mag:=%s;' % (1003.75/args.designsize*args.magnification), 
	'errorstopmode;' if args.errorstopmode else 'nonstopmode;',
	'outputtemplate:="%c.eps";',
	'input %s;' % mfsource,
	'bye']
	subprocess.call(
		mpargs,
		stdout = subprocess.PIPE, 
		stderr = subprocess.PIPE,
		cwd = tempdir
		)
	
	generalname = os.path.splitext(os.path.basename(args.mfsource))[0]	
	if args.fullnameasfilename:
		outputname = font.fullname
	else:
		outputname = generalname
	if args.verbose:
		print "Reading the tfm file..."
	metric = Tfmetric("%s/%s.tfm" % (tempdir, generalname)) 
	if metric.designsize != args.designsize:
		args.designsize = metric.designsize 
		if args.verbose:
			print "The correct designsize is %s, hence I have to run METAPOST again..." % metric.designsize 
		mpargs[3] = 'mag:=%s;' % (1003.75/args.designsize*args.magnification)
		subprocess.call(
			mpargs,
			stdout = subprocess.PIPE, 
			stderr = subprocess.PIPE,
			cwd = tempdir
			)
	font.design_size = args.designsize
	font.italicangle = -math.atan(metric.slant)/math.pi*180
			
	if args.verbose:
		print "Importing glyphs..."
	transformation = psMat.scale(1.0/args.magnification) # redo the magnification
	eps_files = glob.glob(os.path.join(tempdir, "*.eps"))
	for file in eps_files:
		code  = int(os.path.splitext(os.path.basename(file))[0])
		if args.veryverbose:
			print "Importing the glyph with code number %s" % code
		if not (args.encoding == "t1" and code == 23): #do not yet care about the cwm 
			glyph = font.createMappedChar(code)
			if args.cmspecials:
				importEps(glyph,file)
			else:
				glyph.importOutlines(file, ("toobigwarn", "correctdir"))
			glyph.transform(transformation)
		
	if args.verbose:
		print "Adding glyph metrics..."
	for glyph in font.glyphs():
		glyph.width = int (round (metric.getCharwidth(glyph.encoding) / args.designsize * 1000)) 
	font.mergeFeature("%s/%s.tfm" % (tempdir, generalname))
	#font.texparameters[1]=metric.slant
	if args.encoding == "t1":
		font.createMappedChar(23) #add empty cwm
		font[23].width = 0
		font.encoding = "unicode" #add space for non-TeX
		font.createChar(32)
		font[32].width = int (round (metric.space * 1000))  
		font.encoding = "T1Encoding"
		font.encoding = "compacted"
	
	if not args.raw:
		if args.verbose:
			print "General finetuning in fontforge..."
		font.selection.all()
		if args.defragment:
			if args.veryverbose:
				print "Removing tiny fragments"
			defragment(font)
		if args.veryverbose:
			print "Simplifying"
		font.simplify()
		if args.veryverbose:
			print "Rounding"
		font.round()
		if args.veryverbose:
			print "Removing overlaps"
		font.removeOverlap()
		if args.veryverbose:
			print "Correcting directions"
		font.correctDirection()
		if args.veryverbose:
			print "Adding extrema"
		font.addExtrema()
		if args.veryverbose:
			print "Simplifying"
		font.simplify()
		if args.veryverbose:
			print "Rounding"
		font.round()
		if args.veryverbose:
			print "Simplifying"
		font.simplify()
		if args.veryverbose:
			print "Rounding"
		font.round()
		if args.veryverbose:
			print "Hinting"
		font.autoHint()
	
	if ("sfd" in args.formats):
		if args.verbose:
			print "Saving '%s.sfd' ..." % outputname
		font.save("%s.sfd" % outputname)
	if ("otf" in args.formats):
		if args.verbose:
			print "Generating '%s.otf' ..." % outputname
		font.generate("%s.otf" % outputname)
	if ("pfa" in args.formats):
		if args.verbose:
			print "Generating '%s.pfa' and '%s.afm' ..." % (outputname,outputname)
		font.generate("%s.pfa" % outputname)
	if ("pfb" in args.formats):
		if args.verbose:
			print "Generating '%s.pfb' and '%s.afm' ..." % (outputname,outputname)
		font.generate("%s.pfb" % outputname)
	if ("afm" in args.formats):
		if args.verbose:
			print "Generating '%s.afm' ..." % outputname
		font.generate("%s.afm" % outputname)
	if ("ttf" in args.formats):
		if args.verbose:
			print "Generating '%s.ttf' ..." % outputname
		font.generate("%s.ttf" % outputname)
	if ("eoff" in args.formats):
		if args.verbose:
			print "Generating '%s.eoff' ..." % outputname
		font.generate("%s.eoff" % outputname)
	if ("svg" in args.formats):
		if args.verbose:
			print "Generating '%s.svg' ..." % outputname
		font.generate("%s.svg" % outputname)
	if ("tfm" in args.formats):
		if args.verbose:
			print "Saving '%s.tfm' ..." % outputname
		shutil.copyfile("%s/%s.tfm" % (tempdir, generalname), "%s.tfm" % outputname) 
	
	shutil.rmtree(tempdir)
	exit(0)
