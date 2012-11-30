from __future__ import division
from collections import Counter
from setting import db_connection
import sys
import re

from nltk.corpus import wordnet as wn

from hierachy_tree import chooseSimKSynsets

if len(sys.argv) < 2:
  print 'usage: analysis <db_name>'
  sys.exit()

db = db_connection[sys.argv[1]]

reservedWordList = ['REST', 'WSDL', 'OWL']

stopWordList = ['as', 'make', 'an', 'be', 'or', 'in', 'are', 'let', 'then', 'one', 'ha', 'can', 'service', 'services', 'us',  'do',  'we',  'use',  'user',  'users',  'using',  'allow',  'let',  'more',  'have',  'it',  'let',  'web',  'application',  'information',  'provide',  'well',  'time',  'enable',  'name',  'api',  'apis',  'developer',  'offer',  'include',  'access',  'help',  'site',  'website',  'base',  'database',  'so',  'who'] #'datum'

ctgryName = {'Wiki': 'knowledge', 'Real Estate': 'real_estate', 'blogging': 'blog', 'Backend': 'developer', 'PIM': 'Person Information Management', 'Medical': 'medicine', 'Financial': 'finance'}
#this method add words in tag frequency to the mmost_common word in the list
def handleTag(cnt, tags):
  for tag in tags:
    if cnt.has_key(tag):
      cnt[tag] += cnt.most_common()[0][1]
    else:
      cnt[tag] = cnt.most_common()[0][1]
  
#this method filters the stem words and counts each service's words in description.
def freqByService():
  for api in db.apis.find():
    dscrp = api['description']
    lst = re.split('\s', re.sub('[^\w\-\s]', '', dscrp).strip().lower())
    index = 0
    while index < len(lst):
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
          lst[index] = wn.morphy(word)
          word = lst[index]
        else:
          del lst[index]
          continue
        if len(word) == 1 or word in stopWordList or word.isdigit():
          del lst[index]
          continue
      index += 1
    cnt = Counter(lst)
    cnt = dict(handleTag(cnt, api['tags']))
    newEntry = {}
    newEntry['api_id'] = api['id']
    newEntry['category'] = api['category']
    newEntry['wordlist'] = cnt
    db.frequency.insert(newEntry)

#this method transform wn.synset.tree to a flat list[[synset1, depth], ... ,[synsetn, depthn]]
def getTreesList(tree, depth = 0):
  l = []
  for entry in tree:
    if type(entry) is list:
      l += getTreesList(entry, depth + 1)
    else:
      l += [[entry.name, depth]]
  return l

#this method is for making all words in repo into synset.
#For each service, this method chooses top 3 synset similar to its category and then generates a synsetKfirfSumMap which contains synsets and its corresponding words' summation of kfirf in this category.
#this method chooses in order of the summation of word kfirf in each synset
def wordToSynset():
  #todo: should use freqinctgry(only train)
  for entry in db.freqbyCtgry.find():
    synsetWordMap = {}
    for word in entry['wordlist']:
      for synset in chooseSimKSynsets(word, 3, category = ctgryName.get(entry['category'], entry['category'])):
        if not synsetWordMap.has_key(synset.name):
          synsetWordMap[synset.name] = set([word])
        else:
          synsetWordMap[synset.name].add(word)
    synsetKfirfSumMap = Counter({k:sum(db.kfirfbyCtgry.find({'category':entry['category']})[0]['wordlist'][word] for word in synsetWordMap[k]) for k in synsetWordMap})
    for pair in synsetKfirfSumMap.most_common():
      mostSynset = pair[0]
      for word in synsetWordMap[mostSynset]:
        db.wordSynsetMap.insert({'word': word, 'synset': mostSynset, 'category': entry['category'], 'depth': 100})
      mostSynsetWordSet = synsetWordMap.pop(mostSynset)
      #the synsetWordMap changed for assignment need, while the synsetKfirfSumMap does not change.
      for synset in synsetWordMap:
        synsetWordMap[synset] = synsetWordMap[synset] - mostSynsetWordSet


#deprecated, change the word's synset in wordSynsetMap with synset in category tree.
def SynsetwithCategry():
  hypo = lambda s:s.hyponyms()
  for entry in db.freqbyCtgry.find():
    synsetLists = []
    category = ctgryName.get(entry['category'], entry['category']) 
    if category == 'Other':
      continue
    if category == 'Travel':
      synsetLists.append(getTreesList(wn.synset('travel.n.01').tree(hypo)))
      synsetLists.append(getTreesList(wn.synset('travel.v.03').tree(hypo)))
      synsetLists.append(getTreesList(wn.synset('travel.v.04').tree(hypo)))
      synsetLists.append(getTreesList(wn.synset('travel.v.05').tree(hypo)))
      synsetLists.append(getTreesList(wn.synset('travel.v.06').tree(hypo)))
    else:
      for word in category.split():
        synsets = wn.synsets(word, 'n')   
        synsets += wn.synsets(word, 'v')
        for synset in synsets:
          synsetLists.append(getTreesList(synset.tree(hypo)))
      
    for synsetList in synsetLists:
      for synset in synsetList:
        for lemma in wn.synset(synset[0]).lemmas:
          if db.wordSynsetMap.find({'word': lemma.name, 'category': entry['category']}).count():
            #if the word is in serveral synsets, we can choose the one has the least distance from root
            if db.wordSynsetMap.find({'word': lemma.name, 'category': entry['category']})[0]['depth'] > synset[1]:
              db.wordSynsetMap.remove({'word': lemma.name, 'category': entry['category']})
              db.wordSynsetMap.insert({'word': lemma.name, 'synset': synset[0], 'depth': synset[1], 'category':entry['category']})
              print lemma.name, synset[0], synset[1], entry['category']
          else: 
            db.wordSynsetMap.insert({'word': lemma.name, 'synset': synset[0], 'depth': synset[1], 'category':entry['category']})
            print lemma.name, synset[0], synset[1], entry['category']

import copy
#this method counts words in each category
def freqByCategory(tablefreq, tablefreqbyCtgry):
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

#this method calcultes kfirf for all the categories' word in repository
def kfirf(alpha):
  ctgryCount = db.freqbyCtgry.count()
  for entry in db.freqbyCtgry.find():
    kfirfEntry = copy.deepcopy(entry)
    cnt = Counter(entry['wordlist'])
    maxFreq = cnt.most_common()[0][1]
    for word in cnt:
      ctgryWithWord = 0
      totalCount = 0
      for i in db.freqbyCtgry.find({'wordlist.' + word : {'$exists':True}}):
        ctgryWithWord += 1
        totalCount += i['wordlist'][word]
      print cnt[word],'/', maxFreq, '*( alpha * (1 -', ctgryWithWord, '/', ctgryCount, ') + (1 - alpha) * ', cnt[word], '/', totalCount, ')'
      kfirfEntry['wordlist'][word] = cnt[word]/maxFreq * (alpha * (1 - ctgryWithWord/ctgryCount) + (1 - alpha) * cnt[word]/totalCount)
      print kfirfEntry['wordlist'][word]  
    db.kfirfbyCtgry.insert(kfirfEntry)

import math
#this method caculates kf-idfdf for 50 words this category and 50 words not in this category regarding to a category(param)
def kfidfdf(beta, category, omega):
  kfidfdfEntry = {}
  kfidfdfEntry['category'] = category
  kfidfdfEntry['apilist'] = {}
  db.kfidfdf.remove({'category': category})
  # sum all apis
  apiCount = db.frequency.find().count()
  for entry in db.frequency.find({'category': category}).limit(50):
    del entry['_id']
    totalFreq = 0
    for word in entry['wordlist']:
      #sum all keywords in one api frequency
      totalFreq += entry['wordlist'][word]
    kfidfdfEntryForOneApi = {}
    for word in entry['wordlist']:
      apiWithWordCount = 0
      for api in db.frequency.find({}, {'_id': 0,'wordlist.' + word: 1}):
        if api['wordlist'] != {}:
          apiWithWordCount += 1
      raw_kfidf = entry['wordlist'][word]/totalFreq * math.log( apiCount / ( apiWithWordCount + 1 ), 10 )
      #if (word == 'travel' or word == 'amaze') and (entry['api_id'] == 'http://www.programmableweb.com/api/cleartrip'):
      print word, entry['api_id'], "raw_kfidf = ", raw_kfidf, "word freq in api = ", entry['wordlist'][word], "totalFreq =", totalFreq, "log(", apiCount, "/(", apiWithWordCount, "+1))"
      rankList = db.kfirfbyCtgry.find({'category': category})[0]['wordlist']
      rankList = Counter(rankList)
      if rankList.most_common()[omega][1] >  rankList.get(word, -1):
        kfidfdfEntryForOneApi[word] = raw_kfidf
      else:
        for i in range(len(rankList)):
          if rankList.most_common()[i][0] == word:
            break
        kfidfdfEntryForOneApi[word] = raw_kfidf * (1 + (1 - math.floor(i / math.sqrt( omega )) / math.sqrt( omega ) ) * beta ) 
    kfidfdfEntry['apilist'][re.sub('\.','__',entry['api_id'])] = kfidfdfEntryForOneApi
  #the following is for api not in category
  for entry in db.frequency.find({'category': {'$not':re.compile(category)}}).limit(50):
    del entry['_id']
    totalFreq = 0
    for word in entry['wordlist']:
      #sum all keywords in one api frequency
      totalFreq += entry['wordlist'][word]
    kfidfdfEntryForOneApi = {}
    for word in entry['wordlist']:
      apiWithWordCount = 0
      for api in db.frequency.find({}, {'_id': 0,'wordlist.' + word: 1}):
        if api['wordlist'] != {}:
          apiWithWordCount += 1
      raw_kfidf = entry['wordlist'][word]/totalFreq * math.log( apiCount / ( apiWithWordCount + 1 ), 10 )
      print word, entry['api_id'], "raw_kfidf = ", raw_kfidf, "word freq in api = ", entry['wordlist'][word], "totalFreq =", totalFreq, "log(", apiCount, "/(", apiWithWordCount, "+1))"
      rankList = db.kfirfbyCtgry.find({'category': category})[0]['wordlist']
      rankList = Counter(rankList)
      if rankList.most_common()[omega][1] >  rankList.get(word, -1):
        kfidfdfEntryForOneApi[word] = raw_kfidf
      else:
        for i in range(len(rankList)):
          if rankList.most_common()[i][0] == word:
            break
        kfidfdfEntryForOneApi[word] = raw_kfidf * (1 + (1 - math.floor(i / math.sqrt( omega )) / math.sqrt( omega ) ) * beta ) 
    kfidfdfEntry['apilist'][re.sub('\.','__',entry['api_id'])] = kfidfdfEntryForOneApi
  db.kfidfdf.insert(kfidfdfEntry)
        
#freqByService()
#freqByCategory(db.frequency, db.freqbyCtgry)
#kfirf(0.4)       
#kfidfdf(0.5, "Travel", 100)

