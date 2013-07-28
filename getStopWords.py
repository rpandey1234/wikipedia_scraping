#!/usr/bin/python 

import sys
import urllib
from xml.dom.minidom import parse, parseString
import xml.dom.minidom
import collections
import re
import parse_wiki_xml

def getStopWords(LANGUAGE_CODE, NUM_ARTICLES, NUM_WORDS):
  # Get random ids from random api

  num_pages_scraped = 0
  allText = ""
  while (num_pages_scraped < NUM_ARTICLES):
    randUrl = "http://" + LANGUAGE_CODE + ".wikipedia.org/w/api.php?action=query&list=random&format=xml&rnlimit=10"
    pageids = []
    for pageid in parse_wiki_xml.parse_random_articles_xml(urllib.urlopen(randUrl)):
      pageids.append(str(pageid))

    num_pages_scraped += len (pageids)    

    pagesStr = "|".join(pageids)

    pagesStr = pagesStr[0:-1] # get rid of last pipe

    url = 'http://' + LANGUAGE_CODE + '.wikipedia.org/w/api.php?action=query&prop=revisions&redirects&rvprop=content&format=xml&pageids=' + pagesStr
    print "Scraping from url: " + url
  # print "Fetching from " + url

    articles = parse_wiki_xml.parse_articles_xml(urllib.urlopen(url))
    for article in articles:
      if 'content' in article and article['content']:
        allText += article['content']

  print "Length of all articles scraped: " + str(len(allText))
  cnt = collections.Counter()
  words = re.findall(r'\w+', allText.lower())
  mostFrequent = collections.Counter(words).most_common(NUM_WORDS)
  print mostFrequent
  output = ""
  for t in mostFrequent:
  	output += t[0] + "," + str(t[1]) + "\n"
  return output

def main():
  LANGUAGE_CODE = "en"
  NUM_ARTICLES = 1000
  NUM_WORDS = 100
  if len(sys.argv) == 2:
  	LANGUAGE_CODE = sys.argv[1]
  elif len(sys.argv) == 3:
  	LANGUAGE_CODE = sys.argv[1]
  	NUM_ARTICLES = int(sys.argv[2])	
  elif len(sys.argv) == 4:
  	LANGUAGE_CODE = sys.argv[1]
  	NUM_ARTICLES = int(sys.argv[2])	
  	NUM_WORDS = int(sys.argv[2])	
  else:
  	print "Usage: python " + sys.argv[0] + " <2-letter-language-code> <num-articles (1000)> <how-many-to-return (100)>"
  	return
  
  words = getStopWords(LANGUAGE_CODE, NUM_ARTICLES, NUM_WORDS)
  # print words
  filename = "stopWords-" + LANGUAGE_CODE + ".txt"
  with open(filename, "w") as f:
  	f.write(words.encode('utf-8'))
  print "Wrote " + LANGUAGE_CODE + " stop words to " + filename


if __name__ == "__main__":
  main()
