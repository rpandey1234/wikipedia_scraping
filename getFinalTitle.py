#!/usr/bin/python 

import sys, re
import urllib
from xml.dom.minidom import parse, parseString
import xml.dom.minidom

def replace_spaces(str):
  return re.sub("\s", "_", str) 

# returns string which is final title, if any, or empty string
def final_title(input_title, LANGUAGE_CODE):
	url_safe_title = replace_spaces(input_title)
	#http://en.wikipedia.org/w/api.php?action=query&redirects&format=xml&titles=theocracies
	url = 'http://' + LANGUAGE_CODE + '.wikipedia.org/w/api.php?action=query&redirects&format=xml&titles=' + url_safe_title
	dom = xml.dom.minidom.parse(urllib.urlopen(url))
	pagesNode = dom.getElementsByTagName("page")
	if len(pagesNode) == 0:
		return ""
	else:
		p = pagesNode[0]
		title = p.getAttributeNode("title").nodeValue
  	return title

def main():
	input_title = "immunotoxic"
	input_title = "Theocracies"
	print "Input title: " + input_title
	output_title = final_title(input_title, "en")
	print "output_title: " + output_title

if __name__ == "__main__":
  main()