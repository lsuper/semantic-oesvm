from __future__ import division
import re
from iterPreprocess import ctgryName,freqByCategory,wordToSynset, freqByService 
from hierachy_tree import chooseSimKSynsets
import numpy as np
import math
import hashlib
from datetime import datetime
from setting import db_connection
import copy
import sys
from collections import Counter
from nltk.corpus import wordnet as wn
from subprocess import *
from cutrow import cutrow


dbRepo = db_connection['PW_test']
dboesvm = db_connection['oesvm']
dbsoesvm = db_connection['soesvm']

loop = 0
isStop = False
rankList = []
signature = hashlib.md5(str(datetime.now())).hexdigest()
#todo: if you want to compare between oesvm soesvm, init training set should be same. so another method should be written for copy api from soesvm initTrain table to oesvm initTrain table
#set up init Training set and copy the whole repository frequency table for testing
def consInitTrainSetAndTestSet(category, isSynset, db):
  freqTable = dbRepo.frequency
  trainSet = list(freqTable.find({'category': category}))
  #initTrain is just a set for knowing what is the init training set apis
  db.initTrain.drop()
  db.initTrain.insert(trainSet)
  serviceNotInCtgry = list(freqTable.find({'category':{'$ne':category}}))
  #half of the initTrain Set are in category, the other half not.
  halfTrainSetSize = len(trainSet)
  for i in range(halfTrainSetSize):
    index = np.random.randint(0, len(serviceNotInCtgry), 1)
    db.initTrain.insert(serviceNotInCtgry[index])
    del serviceNotInCtgry[index]
  #construct testing set data
  db.frequency.drop()
  db.frequency.insert(list(dbRepo.frequency.find()))
  db.wordKfirf.drop()
  db.wordKfirf.insert(list(dbRepo.wordKfirf.find()))
  if isSynset:
    db.synsetKfirf.drop()
    db.synsetKfirf.insert(list(dbRepo.synsetKfirf.find()))
    db.synsetFrequency.drop() 
    db.synsetFrequency.insert(list(dbRepo.synsetFrequency.find())) 
    db.synsetFreqbyCtgry.drop() 
    db.synsetFreqbyCtgry.insert(list(dbRepo.synsetFreqbyCtgry.find())) 
    db.wordSynsetMap.drop() 
    db.wordSynsetMap.insert(list(dbRepo.wordSynsetMap.find())) 
  db.kfidfdf.insert(list(dbRepo.kfidfdf.find())) 

#this method cacultes kfirf for all categories, store as wordKfirf table for word, as synsetKfrif for synset (isSynset and !isWord)
# all tables used are in db
def kfirf(category, alpha, isSynset, isWord, db):
  if isSynset:
    if isWord:
      freqbyCtgryTable = db.freqbyCtgry
      #db.wordKfirf.drop()
      db.wordKfirf.remove({'category':'Travel'})
    else:
      freqbyCtgryTable = db.synsetFreqbyCtgry
      #db.synsetKfirf.drop()
      db.synsetKfirf.remove({'category':'Travel'})
  else:
    if not isWord:
      print 'Error: oesvm but caculating word kfirf'
      sys.exit()
    freqbyCtgryTable = db.freqbyCtgry
  ctgryCount = freqbyCtgryTable.count()
  for entry in freqbyCtgryTable.find({'category':'Travel'}):
    kfirfEntry = copy.deepcopy(entry)
    cnt = Counter(entry['wordlist'])
    maxFreq = cnt.most_common()[0][1]
    for word in cnt:
      ctgryWithWord = 0
      totalCount = 0
      #print word
      for i in freqbyCtgryTable.find({'wordlist.' + word :{'$exists':True}}):
        ctgryWithWord += 1
        totalCount += i['wordlist'][word]
      #print cnt[word],'/', maxFreq, '*( alpha * (1 -', ctgryWithWord, '/', ctgryCount, ') + (1 - alpha) * ', cnt[word], '/', totalCount, ')'
      kfirfEntry['wordlist'][word] = cnt[word]/maxFreq * (alpha * (1 - ctgryWithWord/ctgryCount) + (1 - alpha) * cnt[word]/totalCount)
      #print word, kfirfEntry['wordlist'][word]  
    if isWord: 
      db.wordKfirf.insert(kfirfEntry)
    else:
      db.synsetKfirf.insert(kfirfEntry)
      

#this method caculates kf-idfdf for all the key words in db frequency table regarding to a category(param)

def kfidfdf(beta, category, omega, isSynset, db):
  if isSynset:
    freqTable = db.synsetFrequency
  else:
    freqTable = db.frequency
  db.kfidfdf.drop()
  db.tfidf.drop()
  # sum all apis
  documentTotalNumber = freqTable.find().count()
  #wordSet is for generate index for words
  wordSet = set()
  for entry in freqTable.find():
    for word in entry['wordlist']:
      wordSet.add(word)
  wordSet = list(wordSet)
  #wordIndexMap is used by new documents which are not in repository
  db.wordIndexMap.drop()
  db.documentFreq.drop()
  for word in wordSet:
    db.wordIndexMap.insert({'word':word, 'index': wordSet.index(word) + 1})
  rankList = db.synsetKfirf.find({'category': category})[0]['wordlist']
  rankList = Counter(rankList)
  if omega < len(rankList):
    omega = len(rankList) - 1
  most_commonList = rankList.most_common()
  maxKfirf = most_commonList[omega][1]
  #calculate kfidfdf for all words in repository
  for entry in freqTable.find():
    del entry['_id']
    totalFreq = 0
    for word in entry['wordlist']:
      #sum all keywords in one api frequency
      totalFreq += entry['wordlist'][word]
    kfidfdfEntry = {'api':'','vector':{}}
    tfidfEntry = {'api':'','vector':{}}
    for word in entry['wordlist']:
      #calculate api with this word count in all the repos
      wordDocumentFreq = 0
      if db.documentFreq.find({'word':word}).count():
        wordDocumentFreq = db.documentFreq.find({'word':word})[0]['df']
      else:
        wordDcoumentFreq = freqTable.find({'wordlist.'+word : {'$exists':True}}).count()
      db.documentFreq.insert({'word':word, 'df':wordDocumentFreq})
      tfidf = entry['wordlist'][word]/totalFreq * math.log( documentTotalNumber / (wordDocumentFreq + 1 ), 10)
      tfidfEntry['vector'][str(wordSet.index(word)+1)] = [tfidf, word]
      #if (word == 'travel' or word == 'amaze') and (entry['api_id'] == 'http://www.programmableweb.com/api/cleartrip'):
      #print word, entry['api_id'], "tfidf = ", tfidf, "word freq in api = ", entry['wordlist'][word], "totalFreq =", totalFreq, "log(", documentTotalNumber, "/(", wordDocumentFreq, "+1))"
      if maxKfirf >  rankList.get(word, -1):
        kfidfdfEntry['vector'][str(wordSet.index(word)+1)] = [tfidf, word]
      else:
        rank = [k[0] for k in most_commonList].index(word)
        kfidfdfEntry['vector'][str(wordSet.index(word)+1)] = [tfidf * (1 + (1 - math.floor(rank / math.sqrt( omega )) / math.sqrt( omega ) ) * beta), word] 
    kfidfdfEntry['api'] = entry['api_id']
    tfidfEntry['api'] = entry['api_id']
    db.kfidfdf.insert(kfidfdfEntry)
    db.tfidf.insert(tfidfEntry)

#generate files for training and experiments.(oe)svm_train is the training set. (oe)svm_test is the test set
#(oe)svm[true false]_test is test sets generated from the whole test set. One's category is Target, while the other one is not
def generateFilesforSvm(category, svmType, isSynset, db):
  #todo: add support for isSynset is False. Actually it should work well now. However each time, we should refresh the oesvm kfidf kfirf, kfidfdf every time we change between synset or not synset(word)
  if isSynset:
    path = './rawdataset/iteration/synset/'
  else:
    path = './rawdataset/iteration/word/'
  if svmType == 'svm':
    table = db.tfidf
  else:
    table = db.kfidfdf
  train = open(path + svmType + 'train', 'w')
  test = open(path + svmType + 'test', 'w')
  true_train = open(path + svmType + 'true_train', 'w')
  true_test = open(path + svmType + 'true_test', 'w')
  false_train = open(path + svmType + 'false_train', 'w')
  false_test = open(path + svmType + 'false_test', 'w')
  #first loop, train and test are different, train is small. test is the whole repository
  if loop == 0: 
    for entry in db.initTrain.find():
      f = train
      t_f = true_train
      f_f = false_train
      vectorEntry = table.find({'api':entry['api_id']})[0]
      if category == entry['category']:
        f.write(vectorEntry['api'] + ' 1')
        t_f.write(vectorEntry['api'] + ' 1')
        for key in sorted(int(k) for k in vectorEntry['vector']):
          t_f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
        t_f.write('\n')
      else:
        f.write(vectorEntry['api'] + ' 0')
        f_f.write(vectorEntry['api'] + ' 0')
        for key in sorted(int(k) for k in vectorEntry['vector']):
          f_f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
        f_f.write('\n')
      for key in sorted(int(k) for k in vectorEntry['vector']):
        f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
      f.write('\n')
    #for test set
    for vectorEntry in table.find():
      f = test
      t_f = true_test
      f_f = false_test
      if category == db.frequency.find({'api_id':vectorEntry['api']})[0]['category']:
        f.write(vectorEntry['api'] + ' 1')
        t_f.write(vectorEntry['api'] + ' 1')
        for key in sorted(int(k) for k in vectorEntry['vector']):
          t_f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
        t_f.write('\n')
      else:
        f.write(vectorEntry['api'] + ' 0')
        f_f.write(vectorEntry['api'] + ' 0')
        for key in sorted(int(k) for k in vectorEntry['vector']):
          f_f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
        f_f.write('\n')
      for key in sorted(int(k) for k in vectorEntry['vector']):
        f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
      f.write('\n')
  #the following loops
  else:
    #for test set
    for vectorEntry in table.find():
      f = test
      t_f = true_test
      f_f = false_test
      print db.frequency.find({'api_id':vectorEntry['api']})[0]
      if category == db.frequency.find({'api_id':vectorEntry['api']})[0]['category']:
        f.write(vectorEntry['api'] + ' 1')
        t_f.write(vectorEntry['api'] + ' 1')
        for key in sorted(int(k) for k in vectorEntry['vector']):
          t_f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
        t_f.write('\n')
      else:
        f.write(vectorEntry['api'] + ' 0')
        f_f.write(vectorEntry['api'] + ' 0')
        for key in sorted(int(k) for k in vectorEntry['vector']):
          f_f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
        f_f.write('\n')
      for key in sorted(int(k) for k in vectorEntry['vector']):
        f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
      f.write('\n')
    #for train set
    for vectorEntry in table.find():
      f = train
      t_f = true_train
      f_f = false_train
      if category == db.frequency.find({'api_id':vectorEntry['api']})[0]['category']:
        f.write(vectorEntry['api'] + ' 1')
        t_f.write(vectorEntry['api'] + ' 1')
        for key in sorted(int(k) for k in vectorEntry['vector']):
          t_f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
        t_f.write('\n')
      else:
        f.write(vectorEntry['api'] + ' 0')
        f_f.write(vectorEntry['api'] + ' 0')
        for key in sorted(int(k) for k in vectorEntry['vector']):
          f_f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
        f_f.write('\n')
      for key in sorted(int(k) for k in vectorEntry['vector']):
        f.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
      f.write('\n')
    
#This method builds new Synset Frequency table using db.frequency table
def frequencySynset(db):
  #db.synsetFrequency.drop()
  db.synsetFrequency.remove({category:'Travel'})
  f = open('XXXX','w')
  for entry in db.frequency.find({category:'Travel'}, timeout = False):
    newWordlist = {}
    for word in entry['wordlist']:
      if db.wordSynsetMap.find({'word': word, 'category': entry['category']}).count():
        synset = db.wordSynsetMap.find({'word': word, 'category': entry['category']})[0]['synset']
        newWordlist[synset.replace('.','__')] = newWordlist.get(synset.replace('.','__'), 0) + entry['wordlist'][word]
      else:
        print 'XXX'
        f.write(word+' '+entry['category']+'\n')
      #because when conducting real test and training. Words in test set not always in train set, so we should assign a synset for it.
        cnt = Counter({synet: sum(db.wordKfirf.find({'category':entry['category']})[0]['wordlist'].get(lemma.name, 0) for lemma in wn.synset(synset).lemmas) for synset in chooseSimKSynsets(word, 3, category = ctgryName.get(entry['category'], entry['category']))})
        synset = cnt.most_common()[0]
        newWordlist[re.sub('\.','__',synset)] = newWordlist.get(re.sub('\.','__',synset), 0) + entry['wordlist'][word]
    entry['wordlist'] = newWordlist
    db.synsetFrequency.insert(entry)

def svmHelper(trainFile, testFile, modelFile, predictTestFile):
  cmd = 'svm-grid "{0}"'.format(trainFile)
  print('Cross validation...')
  f = Popen(cmd, shell = True, stdout = PIPE).stdout

  line = ''
  while True:
    last_line = line
    line = f.readline()
    if not line: break
  c,g,rate = map(float,last_line.split())

  print('Best c={0}, g={1} CV rate={2}'.format(c,g,rate))
  
  cmd = 'svm-train -c {0} -g {1} "{2}" "{3}"'.format(c, g, trainFile, modelFile)
  print('Training...')
  Popen(cmd, shell = True, stdout = PIPE).communicate()


  cmd = 'svm-predict "{0}" "{1}" "{2}"'.format(testFile, modelFile, predictTestFile)
  print('Testing...')
  Popen(cmd, shell = True).communicate()

  print('Output prediction: {0}'.format(predictTestFile))

def checkStability(db, category, isSynset):
  global rankList
  f_ranklist = open('./ranklist/ranklist-'+ signature + '-' +str(loop), 'w')
  if isSynset:
    table = db.synsetKfirf
  else:
    table = db.wordKfirf
  newRankList = []
  for entry in table.find({'category':category}):
    cnt = Counter(entry['wordlist'])
    newRankList = [pair[0] for pair in cnt.most_common()]
  length = min(150, len(newRankList), len(rankList)) 
  if newRankList == rankList:
    isStop = True
  else:
    rankList = newRankList
  f_ranklist.write(' '.join(rankList))
  
#use this function every time you classify a new category or you change any formula
def initialize():
  freqByService(dbRepo)
  freqByCategory(dbRepo.frequency, dbRepo.freqbyCtgry)
  kfirf(category, 0.4, isSynset, True, dbRepo)
  wordToSynset(dbRepo)
  frequencySynset(dbRepo)
  freqByCategory(dbRepo.synsetFrequency, dbRepo.synsetFreqbyCtgry)
  kfirf(category, 0.4, isSynset, False, dbRepo)
  kfidfdf(0.5, "Travel", 100, True, dbRepo)
#Loop
isSynset = True
category = 'Travel'
#initialize()
if isSynset:
  db = dbsoesvm
  svmType = 'synset'
else:
  db = dboesvm
  svmType = 'word'
consInitTrainSetAndTestSet(category, isSynset, db)
checkStability(db, category, isSynset)
loop = 1
while not isStop:
  generateFilesforSvm(category, 'oesvm', isSynset, db)
  cutrow()
  svmHelper('./dataset/iteration/'+ svmType +'/oesvmtrain', './dataset/iteration/' + svmType + '/oesvmtest', './model/iteration/modelforsoesvm', 'predict_test_result')
  f_test = open('./rawdataset/iteration/'+ svmType + '/oesvmtest')
  f_result = open('./predict_test_result')
  #a dict for map lineNum to service <'lineNum':'api_id'>
  lineNumToService = {}
  lineNum = 0
  for line in f_test:
    ID = line.split(' ')[0]
    lineNumToService[lineNum] = ID
    lineNum += 1
  lineNum = 0
  for line in f_result:
    if db.frequency.find({'api_id':lineNumToService[lineNum]}, {'category':1})[0]['category'] == category:
      originCategory = 1
    else:
      originCategory = 0
    if originCategory == 1 and line.rstrip('\n') == '0':
      #remove original travel now non-travel service, because we cannot assign a category for it
      db.frequency.remove({'api_id':lineNumToService[lineNum]})
    if originCategory == 0 and line.rstrip('\n') == '1':
      db.frequency.update({'api_id':ID}, {'$set':{'category': category}})
    lineNum += 1
  #re-build all the table
  freqByCategory(db.frequency, db.freqbyCtgry)
  kfirf(category, 0.4, isSynset, True, db)
  wordToSynset(db)
  frequencySynset(db)
  freqByCategory(db.synsetFrequency, db.synsetFreqbyCtgry)
  kfirf(category, 0.4, isSynset, False, db)
  loop += 1
  print loop
  checkStability(db, category, isSynset)
  kfidfdf(0.5, "Travel", 100, True, db)
