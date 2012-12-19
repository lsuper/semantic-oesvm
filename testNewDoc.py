from __future__ import division
from setting import db_connection
from iterPreprocess import preprocessWords, ctgryName 
from collections import Counter
import re
import sys
from subprocess import *
import math

dbsoesvm = db_connection['soesvm']

def frequency(content):
  lst = re.split('\s', re.sub('[^\w\-\s]', '', content).strip())
  preprocessWords(lst)
  cnt = Counter(lst)
  freqEntry = {}
  freqEntry['category'] = initialCategory(cnt)
  freqEntry['wordlist'] = cnt
  return freqEntry

#For semantic oesvm, we need a initial category for transform words to synset
#cnt is a frequency word Counter
def initialCategory(cnt):
  dCnt = dict(cnt)
  ctgry = ''
  maxSum = -1
  for entry in dbsoesvm.wordKfirf.find():
    if entry['category'] == 'Other':
      continue
    kfirfSum = 0
    for word in dCnt:
      if word in entry['wordlist']:
        kfirfSum += dCnt[word] * entry['wordlist'][word]
    if kfirfSum > maxSum:
      maxSum = kfirfSum
      ctgry = entry['category']
  return ctgry


#this method generate synsetFrequency Entry for testing doc and wordToSynsetMap
def synsetFrequency(freqEntry):
  category = freqEntry['category']
  newWordlist = {}
  wordToSynsetMap = {}
  for word in freqEntry['wordlist']:
    if dbsoesvm.wordSynsetMap.find({'category':category, 'word': word}).count():
      synset = dbsoesvm.wordSynsetMap.find({'category':category, 'word': word})[0]['synset'].replace('.','__')
      newWordlist[synset] = newWordlist.get(synset, 0) + freqEntry['wordlist'][word]
    else:
      cnt = Counter({synset: sum(dbsoesvm.wordKfirf.find({'category':category})[0]['wordlist'].get(lemma.name, 0) for lemma in wn.synset(synset).lemmas) for synset in chooseSimKSynsets(word, 3, category = ctgryName.get(category, category))})
      synset = cnt.most_common()[0].replace('.','__')
      newWordlist[synset] = newWordlist.get(synset, 0) + freqEntry['wordlist'][word]
    wordToSynsetMap[word] = synset.replace('__','.')
  freqEntry['wordlist'] = newWordlist
  return freqEntry, wordToSynsetMap

def kfidfdf(beta, category, omega, freqEntry):
  totalFreq = 0
  documentTotalNumber = dbsoesvm.synsetFrequency.count() 
  for word in freqEntry['wordlist']:
    #sum all keywords in one api frequency
    totalFreq += freqEntry['wordlist'][word]
  kfidfdfEntry = {'vector':{}}
  tfidfEntry = {'vector':{}}
  rankList = dbsoesvm.synsetKfirf.find({'category': category})[0]['wordlist']
  rankList = Counter(rankList)
  if omega < len(rankList):
    omega = len(rankList) - 1
  most_commonList = rankList.most_common()
  maxKfirf = most_commonList[omega][1]
  for word in freqEntry['wordlist']:
    if dbsoesvm.wordIndexMap.find({'word':word}).count():
    #calculate api with this word count in all the repos
      wordDocumentFreq = dbsoesvm.documentFreq.find()[0][word] + 1
      tfidf = freqEntry['wordlist'][word]/totalFreq * math.log(documentTotalNumber / (wordDocumentFreq + 1 ), 10)
      tfidfEntry['vector'][str(dbsoesvm.wordIndexMap.find({'word': word})[0]['index']+1)] = [tfidf, word]
      if maxKfirf >  rankList.get(word, -1):
        kfidfdfEntry['vector'][str(dbsoesvm.wordIndexMap.find({'word':word})[0]['index']+1)] = [tfidf, word]
      else:
        rank = [k[0] for k in most_commonList].index(word)
        kfidfdfEntry['vector'][str(dbsoesvm.wordIndexMap.find({'word':word})[0]['index']+1)] = [tfidf * (1 + (1 - math.floor(rank / math.sqrt( omega )) / math.sqrt( omega ) ) * beta), word] 
  return kfidfdfEntry, tfidfEntry 
   
def generateFilesforSvm(category, vectorEntry, testFile):
  f = open(testFile, 'w')
  #abitrary assigned 0
  f.write('0')
  for key in sorted(int(k) for k in vectorEntry['vector']):
    f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
  f.write('\n')
  f.close()

def predict(modelFile, content, predictTestFile, testFile):
  freqEntry = synsetFrequency(frequency(content))[0]
  vectorEntry = kfidfdf(0.5, 'Travel', 100, freqEntry)[0]
  generateFilesforSvm('Travel', vectorEntry, testFile)
  cmd = 'svm-predict "{0}" "{1}" "{2}"'.format(testFile, modelFile, predictTestFile)
  print('Testing...')
  p = Popen(cmd, shell = True)
  p.communicate()
  p.wait()
  f_result = open(predictTestFile)
  line = f_result.readline()
  if line.rstrip('\n') == '1':
    return 'Travel'
  else:
    return 'non-Travel' 

#the following is main part
f = open(sys.argv[1])
content = '' 
for line in f:
  content += line
print predict('/home/lsuper/Projects/semantic-oesvm/model/iteration/modelforsoesvm', content, '/home/lsuper/Projects/semantic-oesvm/test/predict_result', '/home/lsuper/Projects/semantic-oesvm/test/svm_test')

