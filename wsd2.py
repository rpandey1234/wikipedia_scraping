#!/usr/bin/python 

from collections import Counter
import sys, subprocess, math, re, os, os.path, marshal
import parse_wiki_xml, annotator, listWikiSenses

"""
Counters for sense

'cur_word': Counter of cur words
'cur_word_pos': Counter of POS for cur word
'context_words': Counter of how often a word is a context word
'context_poses': Counter of the POS surrounding a word
'global_context': Dunno about this one
num_examples: Number of paragraphs with this word and a link
"""

GENERAL_WIKI_LINK_RE = re.compile("\[\[" + "([^\[\]]*)" + "\]\]")
SPECIFIC_WIKI_LINK_RE = re.compile("\[\[" + "([^\[\]\|]*)" + "\|" + \
"([^\[\]\|]*)" + "\]\]")
NUM_WHATLINKS_PER_WORD = 20
UNKNOWN = "<unknown>"

PARAGRAPH_SEP = "REMINGTONSEPARATOR"
PARAGRAPH_SEP_SENTENCE= PARAGRAPH_SEP + "!"
SMOOTHING_EPSILON = 0.001
MAX_SENSES = 300
LOCAL_CONTEXT_WINDOW = 3
GLOBAL_CONTEXT_WINDOW = 25

wsd_output_file = None

def replace_spaces(str):
  return re.sub("\s", "_", str)    

def debug(item):
  s = str(item)
  #if wsd_output_file:
  #  wsd_output_file.write('# ' + s + '\n')
  print '# ' + s

def output(str):
  if wsd_output_file:
    wsd_output_file.write(str + '\n')
  print str

"""
Updates the counters.
"""
def update_features(pos_entries, index, counters_for_sense, stop_words):
  cur_word = pos_entries[index]['word']
  counters_for_sense['cur_word'][cur_word] += 1
  
  # Current word feature and current word POS features
  cur_word_pos = pos_entries[index]['pos']
  counters_for_sense['cur_word_pos'][cur_word_pos] += 1   

  # Context word features
  local_context_word_pairs, local_context_pos_pairs = \
    annotator.get_context_list(pos_entries, index, LOCAL_CONTEXT_WINDOW)
  counters_for_sense['context_words'].update(local_context_word_pairs)
  counters_for_sense['context_poses'].update(local_context_pos_pairs)
  
  global_context_set = annotator.get_context_set(pos_entries, index, \
    GLOBAL_CONTEXT_WINDOW) - stop_words
  counters_for_sense['global_context_words'].update(global_context_set)
  counters_for_sense['num_examples'] += 1

"""
Returns a set of at most 5 words that appeared at least 3 times in the global
context of a word.
"""
def get_global_context_words(word_counter):
  return set([word for word, count in word_counter.most_common(5) if count >= 3])

"""
Returns the prob equivalent of the given counter C. Applies add epsilon smoothing
using NUM_EXAMPLES and NUM_TOTAL_FEATURES.
"""
def pfs_with_smoothing(c, num_examples, num_total_features):
  p = {}
  denom = num_examples + SMOOTHING_EPSILON * num_total_features
  log_denom = math.log(denom)
  p[UNKNOWN] = math.log(SMOOTHING_EPSILON) - log_denom
  for w, count in c.iteritems():
    p[w] = math.log(count + SMOOTHING_EPSILON) - log_denom
  return p
    
"""
Gets Bernoulli-like log probs for certain "buzzwords" appearing in the global
context.
"""
def get_global_context_probs(counter, num_examples):
  probs = {}
  for word in get_global_context_words(counter):
    denom = num_examples + 2.0 * SMOOTHING_EPSILON
    present_prob = (counter[word] + SMOOTHING_EPSILON) / denom
    not_present_prob = 1 - present_prob
    probs[word] = (math.log(present_prob), math.log(not_present_prob))
  return probs
  
"""
Returns a dictionary that transforms the counters given into a probabilities.
"""
def counters_to_probs(counters_for_sense, vocab, poses):
  probs_for_sense = {}
  num_examples = counters_for_sense['num_examples']
  
  probs_for_sense['cur_word'] = pfs_with_smoothing(\
    counters_for_sense['cur_word'], num_examples, len(vocab))

  probs_for_sense['cur_word_pos'] = pfs_with_smoothing(\
    counters_for_sense['cur_word_pos'], num_examples, len(poses))

  probs_for_sense['context_words'] = pfs_with_smoothing(\
    counters_for_sense['context_words'], num_examples, \
    len(vocab) * 2 * LOCAL_CONTEXT_WINDOW)

  probs_for_sense['context_poses'] = pfs_with_smoothing(\
    counters_for_sense['context_poses'], num_examples, \
    len(poses) * 2 * LOCAL_CONTEXT_WINDOW)

  counters_for_sense['global_context'] = \
    get_global_context_words(counters_for_sense['context_words'])
  probs_for_sense['global_context_words'] = get_global_context_probs(\
    counters_for_sense['global_context_words'], num_examples)

  return probs_for_sense

def get_stop_words(lang):
  file_name = 'stopWords-' + lang + '.txt'
  words = set()
  with open(file_name, 'r') as f:
    for line in f:
      words.add(line.split(",")[0].strip())
  return words

"""
Should not be necessary anymore.
"""
def preprocess_content(content):
  triple_quote_index = content.find("'''")
  if triple_quote_index >= 0:
    return content[(triple_quote_index + 1):]
  return content

def lookup_prob(probs, key):
  if key in probs:
    return probs[key]
  return probs[UNKNOWN]

"""
Estimates P(pos_entries | sense).
"""
def get_nb_prob(pos_entries, index, probs_for_sense, stop_words):
  cur_word = pos_entries[index]['word']
  prob = lookup_prob(probs_for_sense['cur_word'], cur_word)
  
  cur_word_pos = pos_entries[index]['pos']
  prob += lookup_prob(probs_for_sense['cur_word_pos'], cur_word_pos)

  context_word_pairs, context_pos_pairs = \
    annotator.get_context_list(pos_entries, index, LOCAL_CONTEXT_WINDOW)

  for context_word_pair in context_word_pairs:
    prob += lookup_prob(probs_for_sense['context_words'], context_word_pair)

  for context_pos_pair in context_pos_pairs:
    prob += lookup_prob(probs_for_sense['context_poses'], context_pos_pair)

  global_context_set = annotator.get_context_set(pos_entries, index, \
    GLOBAL_CONTEXT_WINDOW) - stop_words
  for global_context_word, probs_pair in \
    probs_for_sense['global_context_words'].iteritems():
    if global_context_word in global_context_set:
      prob += probs_pair[0] # present log prob
    else:
      prob += probs_pair[1] # not present log prob
    
  return prob

"""
Predicts the sense for word at POS_ENTRIES[INDEX]. Will not NB probs if
PROBS_BY_SENSE has only one sense.
"""
def predict_sense(pos_entries, index, probs_by_sense, stop_words):
  if not probs_by_sense:
    return pos_entries[index]['word']
  
  if len(probs_by_sense) == 1:
    for sense in probs_by_sense:
      return sense

  nb_probs = Counter()
  for sense in probs_by_sense:
    nb_probs[sense] = get_nb_prob(pos_entries, index, probs_by_sense[sense], \
      stop_words)

  top_senses = nb_probs.most_common(5)
  debug(top_senses)
  top_sense, top_prob = top_senses[0]
  return top_sense

"""
Not used anymore.
"""
def get_senses_old(word, lang):
  return [e['title'] for e in listWikiSenses.getListOfSenses(word, lang)]

def get_senses(word, lang):
  output_file_name = 'output-' + word + '-' + lang + '.txt'
  try:
    output = subprocess.check_output(['python', 'listSenses.py', '-q', lang, \
      word])
  except:
    return []
  output_file_contents = ""
  if os.path.exists(output_file_name):
    with open(output_file_name, 'r') as f:
      output_file_contents = f.read()
    remove_if_exists(output_file_name)
  ignored, links = annotator.extract_links(output_file_contents, \
    GENERAL_WIKI_LINK_RE)
  return [link['page'] for link in links]
    

def print_list_lines(list):
  for item in list:
    debug(item)

"""
We are only training on lower case words.
page is something like 'bar (law)'
word is something like 'bar'
"""
def is_valid_keyword(page, word):
  return len(word) > 0 and word[:1].islower() and ':' not in page \
    and word != 'thumb'

"""
Keyword = word to disambiguate
"""
def get_keywords_from_pos_entries(pos_entries):
  keywords = set()
  for entry in pos_entries:
    if annotator.is_link_entry(entry):
      word = entry['word']
      if is_valid_keyword(entry['page'], word):
        keywords.add(word)
  return keywords

"""
Debugging function.
"""
def print_links_in_pos_entries(pos_entries):
  for pos_entry in pos_entries:
    if annotator.is_link_entry(pos_entry):
      debug(pos_entry['link_text_words'])

def get_keywords_in_paragraphs(pos_entries_by_paragraph, lang):
  keywords = set()
  for pos_entries in pos_entries_by_paragraph:
    keywords = keywords.union(get_keywords_from_pos_entries(pos_entries))
  return keywords

"""
Shortens the given string of page content by not including paragraphs that don't have the link in them.
"""
def filter_page_contents(pages, wiki_link_re):
  paragraphs_with_links = []
  for page in pages:
    for paragraph in page["content"].split("\n"):
      if wiki_link_re.search(paragraph):
        paragraphs_with_links.append(paragraph)
  return PARAGRAPH_SEP.join(paragraphs_with_links)

"""
Will actually smush pages into one paragraph separated by REMINGTON!
"""
def get_annotated_paragraphs_in_pages(pages, lang, wiki_link_re):
  linkless_paragraphs = []
  pos_entries_by_paragraph = []
  filtered = filter_page_contents(pages, wiki_link_re)
  a, b = get_annotated_paragraphs(filtered, lang, wiki_link_re)
  if a:
    linkless_paragraphs.extend(a)
    pos_entries_by_paragraph.extend(b)
  return (linkless_paragraphs, pos_entries_by_paragraph)

"""
Will actually treat content as one giant paragraph an return a tuple
with one-item lists.
"""
def get_annotated_paragraphs(content, lang, wiki_link_re):
  linkless_paragraph, pos_entries = \
    annotator.annotate_paragraph(content, lang, wiki_link_re)
  if pos_entries:
    return ([linkless_paragraph], [pos_entries])
  return ([], [])

def output_prediction(keyword, sense):
  link = "[[" + sense + "|" + keyword + "]]"
  output(link)

"""
Dumps VALUE into FILE_NAME inside the cache folder, overwriting any
existing file in the cache.
"""
def insert_into_cache(file_name, value):
  cache_file_name = os.path.join('cache', file_name)
  remove_if_exists(cache_file_name)
  with open(cache_file_name, 'w') as f:
    marshal.dump(value, f)
  
def remove_if_exists(file_name):
  try:
    os.remove(file_name)
  except OSError:
    pass

def get_from_cache(file_name):
  cache_file_name = os.path.join('cache', file_name)
  if not os.path.exists(cache_file_name):
    return None
  item = None
  with open(cache_file_name, 'r') as f:
    item = marshal.load(f)
  return item

def get_pair_from_cache(file_name):
  pair = get_from_cache(file_name)
  if not pair:
    return (None, None)
  return pair

def get_joined_name(list):
  return '-'.join(list)

def get_cache_file_name(file_name):
  cache_file_name = os.path.join('cache', file_name)
  if os.path.exists(cache_file_name):
    return cache_file_name
  return None

def move_to_cache(file_name):
  cache_file_name = os.path.join('cache', file_name) 
  os.rename(file_name, cache_file_name)
  return cache_file_name

def get_sense_link_re(sense):
  sense = re.escape(sense)
  re_str = "\[\[" + sense + "\]\]" + "|" + "\[\[" + sense + "\|([^\[\]]*)\]\]"
  return re.compile(re_str, flags=re.IGNORECASE)

def get_empty_counters_for_sense():
  counters = {'num_examples': 0}
  counter_keys = ['cur_word', 'cur_word_pos', 'context_words', \
    'context_poses', 'global_context_words']
  for key in counter_keys:
    counters[key] = Counter()
  return counters

def add_list_to_vocab(vocab, poses, pos_entries_list):
  for pos_entries in pos_entries_list:
    add_to_vocab(vocab, poses, pos_entries)

def add_to_vocab(vocab, poses, pos_entries):
  for pos_entry in pos_entries:
    vocab.add(pos_entry['word'])
    poses.add(pos_entry['pos'])

"""
TRAINING_DATA is either a list of pos_entry lists or True.
"""
def get_probs_for_sense(sense, lang, vocab, poses, training_data, stop_words):
  pos_entries_by_paragraph = training_data

  if training_data == True or len(pos_entries_by_paragraph) == 0:
    return True
  counters_for_sense = get_empty_counters_for_sense()
  for pos_entries in pos_entries_by_paragraph:
    for i, pos_entry in enumerate(pos_entries):
      if annotator.is_link_entry(pos_entry):
        update_features(pos_entries, i, counters_for_sense, stop_words)

  return counters_to_probs(counters_for_sense, vocab, poses)

def get_probs_by_sense(word, lang, vocab, poses, training_data_by_sense, stop_words):
  probs_by_sense = {}
  if len(training_data_by_sense) <= 1:
    for only_sense in training_data_by_sense:
      probs_by_sense[only_sense] = True

  for sense, training_data_for_sense in training_data_by_sense.iteritems():
    probs = get_probs_for_sense(sense, lang, vocab, poses, training_data_for_sense, \
      stop_words)
    if probs:
      probs_by_sense[sense] = probs
    else:
      debug("Threw out sense " + sense)
  return probs_by_sense

"""
Simply replaces all links with just their text.
"""
def get_linkless_paragraph(content):
  content = SPECIFIC_WIKI_LINK_RE.sub(lambda m: m.group(2), content)
  content = GENERAL_WIKI_LINK_RE.sub(lambda m: m.group(1), content)
  return content

"""
Given annotated paragraphs for just the links of a particular sense,
returns True iff the vast majority of the link texts start with an
uppercase letter (indicating it's most likely an name entity.
"""
def is_likely_lower_sense(pos_entries_by_paragraph):
  num_lower = 0
  num_total = 0
  for pos_entries in pos_entries_by_paragraph:
    for pos_entry in pos_entries:
      if annotator.is_link_entry(pos_entry):
        num_total += 1
        if is_valid_keyword(pos_entry['page'], pos_entry['word']):
          num_lower += 1
  if num_total == 0:
    return False
  fraction = 1.0 * num_lower / num_total
  return fraction >= 0.1

def is_multi_cap(sense):
  tokens = sense.split()
  return len(tokens) >= 2 and tokens[0][0].isupper() and tokens[-1][0].isupper()

"""
Returns training data for a sense. Here training data is a list of
annotated paragraphs, where each annotated paragraph is a list of pos
entries with special link entries for which the sense was the destination
page.
"""
def get_training_data_for_sense_cache(sense, lang):
  if '/' in sense or sense == "Bomb the Bass" or is_multi_cap(sense) or sense == "Kirklees" or sense == "Fallout 2":
    return []
  file_name = get_joined_name(['sense', lang, sense])
  sense_data = get_from_cache(file_name)
  if sense_data:
    debug("# Getting (cached) sense training data for " + sense)
    return sense_data

  debug("Getting sense training data for " + sense)
  
  output_file_name = 'output-' + sense + '-' + lang + '.xml'
  output = subprocess.check_output(['python', 'whatLinksHere.py', \
    sense, lang, str(NUM_WHATLINKS_PER_WORD)])
  
  sense_link_re = get_sense_link_re(sense)
  pos_entries_by_paragraph = []
  if os.path.exists(output_file_name):
    file_size = os.path.getsize(output_file_name)
    debug(file_size)
    pages = parse_wiki_xml.parse_articles_xml(output_file_name)
    ignored, pos_entries_by_paragraph = \
      get_annotated_paragraphs_in_pages(pages, lang, sense_link_re) 
  sense_data = pos_entries_by_paragraph
  if not is_likely_lower_sense(sense_data):
    sense_data = []
  insert_into_cache(file_name, sense_data)
  remove_if_exists(output_file_name)
  return sense_data

"""
Given a word, returns a dictionary mapping sense -> training data.
If there is at most one sense, returns a dictionary where the only key
is the only sense and its value is True. No list of training data is
provided.
"""
def get_training_data_by_keyword_cache(word, lang):
  file_name = get_joined_name(['keyword', lang, word])
  data_by_sense = get_from_cache(file_name)
  if data_by_sense:
    debug("Getting (cached) keyword training data for " + word)
    debug(str(len(data_by_sense)) + " senses found.")
    return data_by_sense
  
  data_by_sense = {}
  senses = get_senses(word, lang)
  num_senses = len(senses)
  debug("Getting keyword training data for " + word)
  debug(str(num_senses) + " senses found.")
  if len(senses) == 0:
    data_by_sense[word] = True
    return data_by_sense
  
  if len(senses) == 1:
    data_by_sense[senses[0]] = True
    return data_by_sense
  
  if len(senses) > MAX_SENSES:
    debug("Too many senses. Truncating to just " + str(MAX_SENSES))
    senses = senses[:MAX_SENSES]

  for sense in senses:
    data_for_sense = get_training_data_for_sense_cache(sense, lang)
    if data_for_sense:
      data_by_sense[sense] = data_for_sense
    else:
      debug("Throwing out sense " + sense + " due to lack of data (may be upper)")
  
  insert_into_cache(file_name, data_by_sense)
  return data_by_sense

def has_no_ambiguity(training_data_by_keyword):
  return len(training_data_by_keyword) <= 1

# TODO: Does not cache yet
def get_required_data_cache(pageid, title, content, lang):
  file_name = get_joined_name(["article", pageid, lang])
  cached = get_from_cache(file_name)
  if cached:
    debug("Getting (cached) required data to disambiguate " + title)
    return cached

  vocab = set()
  poses = set()

  # TODO: Cache?
  linkless_paragraphs, pos_entries_by_paragraph = \
    get_annotated_paragraphs(content, lang, GENERAL_WIKI_LINK_RE)
  add_list_to_vocab(vocab, poses, pos_entries_by_paragraph)
  keywords = get_keywords_in_paragraphs(pos_entries_by_paragraph, lang)
  training_data_by_keyword = {}
  for keyword in keywords:
    training_data_by_keyword[keyword] = \
      get_training_data_by_keyword_cache(keyword, lang)
    if not has_no_ambiguity(training_data_by_keyword[keyword]):
      for sense, data_by_sense in training_data_by_keyword[keyword].iteritems():
        add_list_to_vocab(vocab, poses, data_by_sense)

  to_return = {'doc': pos_entries_by_paragraph, 'vocab': vocab, 'poses': poses, \
          'training_data_by_keyword': training_data_by_keyword}
  insert_into_cache(file_name, to_return)
  return to_return

# TODO: What links here provides no prior for NB 
def wsd_page(pageid, title, content, lang, stop_words):
  required_data = get_required_data_cache(pageid, title, content, lang)

  pos_entries_by_paragraph = required_data['doc']
  vocab = required_data['vocab']
  poses = required_data['poses']
  training_data_by_keyword = required_data['training_data_by_keyword']

  keyword_sense_probs = {}
  for keyword, training_data in training_data_by_keyword.iteritems():
    debug("Training for keyword " + keyword)
    keyword_sense_probs[keyword] = get_probs_by_sense(keyword, lang, vocab, poses, \
      training_data, stop_words)

  for pos_entries in pos_entries_by_paragraph:
    for i, pos_entry in enumerate(pos_entries):
      if annotator.is_link_entry(pos_entry):
        keyword = pos_entry['word']
        if keyword in training_data_by_keyword:
          probs_for_sense = keyword_sense_probs[keyword]
          sense = predict_sense(pos_entries, i, probs_for_sense, stop_words)
          output_prediction(keyword, sense)
    
def wsd(xml_file_name, lang):
  global wsd_output_file
  stop_words = get_stop_words(lang)
  for page in parse_wiki_xml.parse_articles_xml(xml_file_name):
    output_file_base = os.path.join(lang + '2', page['pageid'] + '-' + lang)
    output_file_tmp = output_file_base + '.tmp'
    output_file_name = output_file_base + '.txt'
    debug("Disambiguating " + page['title'])
    if os.path.exists(output_file_name):
      continue
    wsd_output_file = open(output_file_tmp, 'w')
    wsd_page(page['pageid'], page['title'], page['content'], lang, stop_words)
    wsd_output_file.close()
    wsd_output_file = None
    os.rename(output_file_tmp, output_file_name)

if __name__ == '__main__':
  if len(sys.argv) >= 4:
    output_file_name = sys.argv[3]
  if len(sys.argv) == 1:
    wsd("output-1-en.xml", "en")
  elif len(sys.argv) >= 3:
    wsd(sys.argv[1], sys.argv[2])
  else:
    debug("Usage: python wsd2.py articles.xml en <output file name>")
  
