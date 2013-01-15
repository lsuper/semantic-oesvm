from __future__ import division
from collections import Counter
from setting import db_connection
from nltk import PorterStemmer
import sys
import re
import copy

from nltk.corpus import wordnet as wn

from hierachy_tree import chooseSimKSynsets


reservedWordList = ['REST', 'WSDL', 'OWL']

stopWordList = ['as', 'make', 'an', 'be', 'or', 'in', 'are', 'let', 'then', 'one', 'ha', 'can', 'service', 'services', 'us',  'do',  'we',  'use',  'user',  'users',  'using',  'allow',  'let',  'more',  'have',  'it',  'let',  'web',  'application',  'information',  'provide',  'well',  'time',  'enable',  'name',  'api',  'apis',  'developer',  'offer',  'include',  'access',  'help',  'site',  'website',  'base',  'database',  'so',  'who', 'data']


ctgryName = {'Wiki': 'knowledge', 'Real Estate': 'real_estate', 'blogging': 'blog', 'Backend': 'developer', 'PIM': 'Person Information Management', 'Medical': 'medicine', 'Financial': 'finance'}
#preprocess words list (lowercase, remove stop word, stemming, etc.)
def preprocessWords(lst):
  index = 0
  while index < len(lst):
    lst[index] = lst[index].lower()
    word = lst[index]
    if word not in reservedWordList:
      #special handling from java code
      if word == 'financial':
        lst[index] = 'finance'
      #avoid _id is a word in dscrp
      if word == '_id':
        lst[index] = 'id'
      #only VERB and NOUN are saved, do not know if wn.morphy has many speech stem, which will return as wn.morphy(word)
      # if wn.morphy(word, wn.VERB) and wn.morphy(word, wn.NOUN) and wn.morphy(word, wn.VERB) !=  wn.morphy(word, wn.NOUN):
      # print word, wn.morphy(word, wn.VERB), wn.morphy(word, wn.NOUN), wn.morphy(word)
      if wn.morphy(word, wn.VERB) or wn.morphy(word, wn.NOUN):
        if wn.morphy(word) != word:
          lst[index] = wn.morphy(word)
          word = lst[index]
        elif wn.morphy(PorterStemmer().stem_word(word)):
          lst[index] = PorterStemmer().stem_word(word)
          word = lst[index]
      else:
        del lst[index]
        continue
      if len(word) < 3 or word in stopWordList or word.isdigit():
        del lst[index]
        continue
    index += 1
  return lst
  
#this method add words in tag frequency to the mmost_common word in the list
def handleTag(cnt, tags):
  tags = preprocessWords(tags)
  if len(cnt) == 0:
    cnt = Counter(tags)
    return cnt
  else:
    for tag in tags:
      if cnt.has_key(tag):
        cnt[tag] += cnt.most_common()[0][1]
      else:
        cnt[tag] = cnt.most_common()[0][1]
    return cnt
#this method filters the stem words and counts each service's words in description.
#db is the database containig apis
def freqByService(db):
  db.frequency.drop()
  for api in db.apis.find():
    dscrp = api['description']
    lst = re.split('\s', re.sub('[^\w\-\s]', '', dscrp).strip())
    preprocessWords(lst)
    cnt = Counter(lst)
    cnt = dict(handleTag(cnt, api['tags']))
    newEntry = {}
    newEntry['api_id'] = api['id']
    newEntry['category'] = api['category']
    newEntry['wordlist'] = cnt
    db.frequency.insert(newEntry)

#this method is for making all words in repo into synset.
#For each service, this method chooses top 3 synset similar to its category and then generates a synsetKfirfSumMap which contains synsets and its corresponding words' summation of kfirf in this category.
#this method chooses in order of the summation of word kfirf in each synset
def wordToSynset(db, isInit = False):
  if isInit:
    db.wordSynsetMap.drop()
  else:
    db.wordSynsetMap.remove({'category':'Travel'})
  if isInit:
    query = {}
  else:
    query = {'category':'Travel'}
  for entry in db.freqbyCtgry.find(query):
    synsetWordMap = {}
    for word in entry['wordlist']:
      for synset in chooseSimKSynsets(word, 3, category = ctgryName.get(entry['category'], entry['category'])):
        if not synsetWordMap.has_key(synset.name):
          synsetWordMap[synset.name] = set([word])
        else:
          synsetWordMap[synset.name].add(word)
    synsetKfirfSumMap = Counter({k:sum(db.wordKfirf.find({'category':entry['category']})[0]['wordlist'][word] for word in synsetWordMap[k]) for k in synsetWordMap})
    for pair in synsetKfirfSumMap.most_common():
      mostSynset = pair[0]
      for word in synsetWordMap[mostSynset]:
      #Actually we can only insert <word synset> never inserted before.
        if db.wordSynsetMap.find({'word': word, 'synset': mostSynset, 'category': entry['category']}).count() == 0:
          db.wordSynsetMap.insert({'word': word, 'synset': mostSynset, 'category': entry['category'], 'depth': 100})
      """
      mostSynsetWordSet = synsetWordMap.pop(mostSynset)
      #the synsetWordMap changed for assignment need, while the synsetKfirfSumMap does not change.
      for synset in synsetWordMap:
        synsetWordMap[synset] = synsetWordMap[synset] - mostSynsetWordSet
      """


#this method counts words in each category
def freqByCategory(tablefreq, tablefreqbyCtgry):
  tablefreqbyCtgry.drop()
  freqEntry = {}
  for entry in tablefreq.find():
    wordlist = entry['wordlist']
    cnt = Counter(wordlist)
    if tablefreqbyCtgry.find({'category': entry['category']}).count():
      freqEntry = tablefreqbyCtgry.find({'category': entry['category']})[0]
      newWordlist = dict(Counter(freqEntry['wordlist']) + cnt)
      newFreqEntry = {}
      newFreqEntry['category'] = freqEntry['category']
      newFreqEntry['wordlist'] = newWordlist
      tablefreqbyCtgry.remove({'category': freqEntry['category']})
      tablefreqbyCtgry.insert(newFreqEntry)
    else:
      del entry['api_id']
      tablefreqbyCtgry.insert(entry)

