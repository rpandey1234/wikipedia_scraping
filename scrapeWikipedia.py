#!/usr/bin/python 

# Contact: rpandey1234@gmail.com

import sys
import urllib
import re
from xml.dom.minidom import parse, parseString
import xml.dom.minidom

def appendToOut(out, numLeftToRetrieve, LANGUAGE_CODE, LEN_THRESH):
	numWritten = 0
	# Get random ids random api
	randUrl = "http://" + LANGUAGE_CODE + ".wikipedia.org/w/api.php?action=query&list=random&format=xml&rnlimit=" + str(2*numLeftToRetrieve)
	# try to limit calls to api by getting more rand article ids than necessary. 
	randDom = xml.dom.minidom.parse(urllib.urlopen(randUrl))
	randPagesNode = randDom.getElementsByTagName("page")
	pageids = []
	for p in randPagesNode:
		pageids.append(p.getAttributeNode("id").nodeValue)

	pagesStr = ""
	for p in pageids:	
		pagesStr += str(p) + "|"
	pagesStr = pagesStr[0:-1] # get rid of last pipe
	#sample = "http://en.wikipedia.org/w/api.php?action=query&prop=revisions&redirects&rvprop=content&format=xml&pageids=600|736"
	url = 'http://' + LANGUAGE_CODE + '.wikipedia.org/w/api.php?action=query&prop=revisions&redirects&rvprop=content&format=xml&pageids=' + pagesStr
	# print "Fetching from " + url

	dom = xml.dom.minidom.parse(urllib.urlopen(url))
	pagesNode = dom.getElementsByTagName("page")
	for p in pagesNode:
		try:
			# re.DOTALL means match newline
			text = re.sub(r'{{.*?}}', '', p.firstChild.childNodes[0].firstChild.nodeValue, flags=re.DOTALL)
			p.firstChild.childNodes[0].firstChild.nodeValue = text
			aLength = len(text)
			title = p.getAttributeNode("title").nodeValue
			if "user:" in title.lower() or "talk:" in title.lower() \
      or "wikipedia:" in title.lower() or 'template:' in title.lower():
				# only want content articles. This is incomplete, may fail for other languages..
				continue
			if aLength > LEN_THRESH:
				print "\"" + title + "\" has length " + str(aLength)
				# t = dom.createElement("page")
				# t.appendChild(text)
				out.childNodes[0].appendChild(p)
				numWritten += 1
				if numWritten >= numLeftToRetrieve:
					return numWritten
		except:
			pass
	return numWritten

def main():
	LANGUAGE_CODE = "en"
	NUM_ARTICLES = 10
	LEN_THRESH = 3000
	if len(sys.argv) == 2:
		LANGUAGE_CODE = sys.argv[1]
	elif len(sys.argv) == 3:
		LANGUAGE_CODE = sys.argv[1]
		NUM_ARTICLES = int(sys.argv[2])
	elif len(sys.argv) == 4:
		LANGUAGE_CODE = sys.argv[1]
		NUM_ARTICLES = int(sys.argv[2])
		LEN_THRESH = int(sys.argv[3])
	else:
		print "Usage: python " + sys.argv[0] + " <2-letter-language-code (en)> <number-articles-desired (10)> <length-treshold (3000)>"
		return

	out = parseString("<pages language=\"" + LANGUAGE_CODE + "\"></pages>")
	numWritten = 0
	while numWritten < NUM_ARTICLES:
		numWritten += appendToOut(out, NUM_ARTICLES-numWritten, LANGUAGE_CODE, LEN_THRESH)
		
	filename = "output-" + str(NUM_ARTICLES) + "-" + LANGUAGE_CODE + ".xml"
	with open(filename, "w") as f:
		f.write(out.toxml().encode('utf-8'))		
	print "Wrote " + str(numWritten) + " articles to " + filename

if __name__ == "__main__":
  main()
