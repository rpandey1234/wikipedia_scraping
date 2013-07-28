#!/usr/bin/python 

# Contact: rpandey1234@gmail.com
import logging
import threading
import Queue
import HTMLParser
import annotator
import sys
import re
import urllib
import urllib2
from xml.dom.minidom import parse, parseString
import parse_wiki_xml
import xml.dom.minidom
import wsd2
from bs4 import BeautifulSoup
from optparse import OptionParser

def sanitize_text (text):
  unescaped = HTMLParser.HTMLParser().unescape (text)
  encoded = unescaped.encode('utf-8')
  return encoded

def get_first_para(link_arr, opener, LANGUAGE_CODE):
  output = ""
  output_list = []
  for l in link_arr:
    try:
      # lot of ways this could screw up: bad url, no p tag, stubs, etc, so just catch all errors
      link = "http://" + LANGUAGE_CODE + ".wikipedia.org" + l
      regex = re.compile("wiki/(.*)")
      r = regex.search(link)
      article_title = r.groups()[0]
      if (article_title == "Help:Disambiguation"):
        continue
      infile = opener.open(link)
      html_doc = infile.read()
      soup = BeautifulSoup(html_doc)
      content = soup.find(id="mw-content-text")
      # find only returns first element of result set
      text = content.find('p').get_text()
      addition = article_title + "\t" + text + "\n"
      # print addition
      output_list.append ((article_title, sanitize_text(text)))
      output += sanitize_text(addition)
    except:
      pass
  return output_list

def sensesFromLink(dLink, LANGUAGE_CODE, verbose):
  link = "http://" + LANGUAGE_CODE + ".wikipedia.org" + dLink
  regex = re.compile("wiki/(.*)")
  r = regex.search(dLink)
  article_title = r.groups()[0]
  disamUrl = "http://" + LANGUAGE_CODE + ".wikipedia.org/w/api.php?action=query&prop=revisions&redirects&rvprop=content&redirects&format=xml&titles=" + article_title
  output = ""
  if not verbose:
    logging.info("Getting (quiet) disambiguations for " + article_title + " from " + disamUrl)
    dom = xml.dom.minidom.parse(urllib.urlopen(disamUrl))
    # there should only be one page in the result page
    p = dom.getElementsByTagName("page")[0] 
    rev = p.getElementsByTagName("rev")[0];
    disamText = rev.firstChild.nodeValue
    for line in disamText.splitlines():
      if line != "" and (line[0] == '*' or "\'\'\'" in line) and "[[" in line:
        output += sanitize_text(line) + "\n"
    return output
  else:
    logging.info("Getting (verbose) disambiguations for " + article_title)
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', 'Mozilla/5.0')]
    infile = opener.open(link)
    html_doc = infile.read()
    soup = BeautifulSoup(html_doc)
    content = soup.find(id="mw-content-text")
    disamLinks = []
    for link in content.find_all('a'):
      link_text = link.get('href')
      if 'wiki/' in link_text:
        disamLinks.append(link.get('href'))
    return get_first_para(disamLinks, opener, LANGUAGE_CODE)

def replaceSpaces(str):
  return re.sub("\s", "_", str)    

def is_match(to_find, link_text, lang):
  link_text = re.sub("\(.*\)", "", link_text).strip().lower()
  to_find = to_find.strip().lower()
  return link_text == to_find

def getSenses(word, LANGUAGE_CODE, verbose):
# Swahili:
# http://sw.wikipedia.org/w/index.php?title=Jamii:Makala_zinazotofautisha_maana&from=E
# English:
# http://en.wikipedia.org/w/index.php?title=Category:All_article_disambiguation_pages&pagefrom=a
# Spanish:
# http://es.wikipedia.org/w/index.php?title=Categor%C3%ADa:Wikipedia:Desambiguaci%C3%B3n&pagefrom=mactas
  urlBase = ""
  if (LANGUAGE_CODE == "en"):
    urlBase = "http://en.wikipedia.org/w/index.php?title=Category:All_article_disambiguation_pages&from="
  elif (LANGUAGE_CODE == "es"):
    urlBase = "http://es.wikipedia.org/w/index.php?title=Categor%C3%ADa:Wikipedia:Desambiguaci%C3%B3n&from="
  elif (LANGUAGE_CODE == "sw"):
    urlBase = "http://sw.wikipedia.org/w/index.php?title=Jamii:Makala_zinazotofautisha_maana&from="
  else:
    logging.warning("Found " + LANGUAGE_CODE + ", unsupported LANGUAGE_CODE (must be en, es, or sw)")
    logging.warning("exiting")
    sys.exit(0)
  url = urlBase + replaceSpaces(word)
  url = urlBase + word
  logging.info("Getting disambiguation link from " + url)
  opener = urllib2.build_opener()
  opener.addheaders = [('User-agent', 'Mozilla/5.0')]
  try:
    infile = opener.open(url)
    html_doc = infile.read()
    soup = BeautifulSoup(html_doc)
    allLinks = soup.findAll("div", {'class':'mw-content-ltr'})[1]
    foundL = allLinks.a
    text = ''.join(foundL.findAll(text=True))
    if not is_match(word, text, LANGUAGE_CODE):
      if verbose:
        return []
      else:
        sys.stderr.write("None found")
        return "No disambiguation page found."
    return sensesFromLink(foundL.get('href'), LANGUAGE_CODE, verbose)
  except urllib2.HTTPError:
    return []
    
result_queue = Queue.Queue()
def batchGetListOfSensesSingle (word, LANGUAGE_CODE, verbose):
  global result_queue
  result_queue.put ({'word': word, 'senses': getSenses (word, LANGUAGE_CODE, verbose)})

def batchGetListOfSenses (words, LANGUAGE_CODE, verbose=True):
  global result_queue
  result_queue.queue.clear()

  threads = []
  for word in words:
    t = threading.Thread (target=batchGetListOfSensesSingle, args=(word, LANGUAGE_CODE, verbose))
    t.daemon = True
    t.start()
    threads.append (t)

  for t in threads:
    t.join()
  result_dict = {}
  while not result_queue.empty():
    item = result_queue.get()
    result_dict[item['word']] = item['senses']

  results = []
  for word in words:
    results.append(result_dict[word])
  return results

def main():
  parser = OptionParser()
  parser.add_option("-v", action="store_true", dest="verbose")
  parser.add_option("-q", action="store_false", dest="verbose")
  (options, args) = parser.parse_args()
  LANGUAGE_CODE = "en"
  WORD = "bar"
  if len(sys.argv) == 3:
    LANGUAGE_CODE = sys.argv[2]
  elif len(sys.argv) == 4:
    LANGUAGE_CODE = sys.argv[2]
    WORD = sys.argv[3]
  else:
  	print "Usage: python " + sys.argv[0] + " <-q or -v> <LANGUAGE_CODE> <english-word>"
  	return

  output = getSenses(WORD, LANGUAGE_CODE, options.verbose)
  if options.verbose:
    new_output = ""
    for line in output:
      new_output += line[0] + '\t' + line[1] + '\n'
    output = new_output

  if output:
    filename = "output-" + WORD + "-" + LANGUAGE_CODE + ".txt"
    # print output
    with open(filename, "w") as f:
    	f.write(output)
    logging.info("Wrote Wikipedia senses of " + WORD + " to " + filename)
  else:
    logging.info("Wikipedia senses of " + WORD + " not found")

if __name__ == "__main__":
  main()
