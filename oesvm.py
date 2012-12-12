from __future__ import division
import re
from preprocess import keeplist, ctgryName,freqByCategory,wordToSynset, SynsetwithCategry
from hierachy_tree import chooseSimKSynsets
import numpy as np
import math
from setting import db_connection
import copy
import sys
from collections import Counter
from nltk.corpus import wordnet as wn
from subprocess import *
from cutrow import cutrow

if len(sys.argv) < 2:
  print 'usage: analysis <db_name>'
  sys.exit()

dbRepo = db_connection[sys.argv[1]]
dboesvm = db_connection['oesvm']
dbsoesvm = db_connection['soesvm']
#set up train set and test set
def consTrainSetAndTestSet(category, trainSetPercent, testSetSize, isSynset):
  if isSynset:
    freqTable = dbRepo.synsetFrequency
    dbSvm = dbsoesvm
  else:
    freqTable = dbRepo.frequency
    dbSvm = dboesvm
  testSet = list(freqTable.find({'category': category}))
  #old newCtgry is train + true_test, now is whole catgory set
  dbSvm.newCtgry.insert(testSet)
  for entry in testSet:
    api = dbRepo.synsetFrequency.find({'api_id':entry['api_id']})[0]
    dbsoesvm.newCtgry.insert(api)
    
  trainSetSize = int(trainSetPercent * len(testSet))
  trainSet = []
  for i in range(trainSetSize):
    index = np.random.randint(0, len(testSet), 1)
    trainSet.append(testSet[index])
    del testSet[index]
  tempTestSetSize = len(testSet)
  testSetNotInCtgry = list(freqTable.find({'category':{'$ne':category}}))
  #there are tempTestSetSize apis within Categry in TestSet now. We need TestSetSize - tempTestSetSize more not from Categry
  for i in range(trainSetSize):
    index = np.random.randint(0, len(testSetNotInCtgry), 1)
    #trainSet should have one trainSetSize category apis and one not trainSetSize category apis.
    trainSet.append(testSetNotInCtgry[index])
    del testSetNotInCtgry[index]
  lst = copy.deepcopy(testSetNotInCtgry)
  while len(testSet) < testSetSize and len(lst) > 0:
    index = np.random.randint(0, len(lst), 1)
    testSet.append(lst[index])
    del lst[index]
  dbSvm.train.insert(trainSet)
  dbSvm.test.insert(testSet)
  dbSvm.trainandtest.insert(trainSet)
  dbSvm.trainandtest.insert(testSet)
  freqTable = dbRepo.synsetFrequency
  dbSvm = dbsoesvm
  for entry in trainSet:
    api = freqTable.find({'api_id':entry['api_id']})[0]
    dbSvm.train.insert(api)
    dbSvm.trainandtest.insert(api)
  for entry in testSet:
    api = freqTable.find({'api_id':entry['api_id']})[0]
    dbSvm.test.insert(api)
    dbSvm.trainandtest.insert(api)
  

#this method cacultes kfirf for training category based on the whole category words(in newCtgry).
def kfirf(alpha, isSynset):
  if isSynset:
    table = dbRepo.synsetFreqbyCtgry
    dbSvm = dbsoesvm
  else:
    table = dbRepo.freqbyCtgry
    dbSvm = dboesvm
  ctgryCount = table.count()
  for entry in dbSvm.freqinCtgry.find():
    kfirfEntry = copy.deepcopy(entry)
    cnt = Counter(entry['wordlist'])
    maxFreq = cnt.most_common()[0][1]
    for word in cnt:
      ctgryWithWord = 0
      totalCount = 0
      print word
      for i in table.find({'wordlist.' + word :{'$exists':True}}):
        ctgryWithWord += 1
        totalCount += i['wordlist'][word]
      print cnt[word],'/', maxFreq, '*( alpha * (1 -', ctgryWithWord, '/', ctgryCount, ') + (1 - alpha) * ', cnt[word], '/', totalCount, ')'
      kfirfEntry['wordlist'][word] = cnt[word]/maxFreq * (alpha * (1 - ctgryWithWord/ctgryCount) + (1 - alpha) * cnt[word]/totalCount)
      #print word, kfirfEntry['wordlist'][word]  
    dbSvm.kfirf.insert(kfirfEntry)

#this method caculates kf-idfdf for all the key words in train set and test set regarding to a category(param)

def kfidfdf(beta, category, omega, isSynset):
  if isSynset:
    freqTable = dbRepo.synsetFrequency
    dbSvm = dbsoesvm
  else:
    freqTable = dbRepo.frequency
    dbSvm = dboesvm
  # sum all apis
  apiCount = freqTable.find().count()
  #wordSet is for generate index for words
  wordSet = set()
  for entry in dbSvm.trainandtest.find():
    for word in entry['wordlist']:
      wordSet.add(word)
  wordSet = list(wordSet)
  rankList = dbSvm.kfirf.find({'category': category})[0]['wordlist']
  rankList = Counter(rankList)
  if omega < len(rankList):
    omega = len(rankList) - 1
  apiWithWordCount = {}
  #calculate kfidfdf for all words in train and test set
  for entry in dbSvm.trainandtest.find():
    del entry['_id']
    totalFreq = 0
    for word in entry['wordlist']:
      #sum all keywords in one api frequency
      totalFreq += entry['wordlist'][word]
    kfidfdfEntry = {'api':'','vector':{}}
    kfidfEntry = {'api':'','vector':{}}
    for word in entry['wordlist']:
      #calculate api with this word count in all the repos
      if not apiWithWordCount.has_key(word):
        apiWithWordCount[word] = 0
        for api in freqTable.find({}, {'_id': 0,'wordlist.' + word: 1}):
          if api['wordlist'] != {}:
            apiWithWordCount[word] += 1
      raw_kfidf = entry['wordlist'][word]/totalFreq * math.log( apiCount / ( apiWithWordCount[word] + 1 ), 10)
      kfidfEntry['vector'][str(wordSet.index(word)+1)] = [raw_kfidf, word]
      #if (word == 'travel' or word == 'amaze') and (entry['api_id'] == 'http://www.programmableweb.com/api/cleartrip'):
      print word, entry['api_id'], "raw_kfidf = ", raw_kfidf, "word freq in api = ", entry['wordlist'][word], "totalFreq =", totalFreq, "log(", apiCount, "/(", apiWithWordCount[word], "+1))"
      if rankList.most_common()[omega][1] >  rankList.get(word, -1):
        kfidfdfEntry['vector'][str(wordSet.index(word)+1)] = [raw_kfidf, word]
      else:
        rank = [k[0] for k in rankList.most_common()].index(word)
        kfidfdfEntry['vector'][str(wordSet.index(word)+1)] = [raw_kfidf * (1 + (1 - math.floor(rank / math.sqrt( omega )) / math.sqrt( omega ) ) * beta), word] 
    kfidfdfEntry['api'] = entry['api_id']
    kfidfEntry['api'] = entry['api_id']
    dbSvm.kfidfdf.insert(kfidfdfEntry)
    dbSvm.kfidf.insert(kfidfEntry)

#generate files for training and experiments.(oe)svm_train is the training set. (oe)svm_test is the test set
#(oe)svm[true false]_test is test sets generated from the whole test set. One's category is Target, while the other one is not
def generateFilesforSvm(category, svmType, isSynset):
  #todo: add support for isSynset is False. Actually it should work well now. However each time, we should refresh the oesvm kfidf kfirf, kfidfdf every time we change between synset or not synset(word)
  if isSynset:
    path = './rawdataset/master/synset/'
    dbSvm = dbsoesvm
  else:
    path = './rawdataset/master/word/'
    dbSvm = dboesvm
  if svmType == 'svm':
    table = dbSvm.kfidf
  else:
    table = dbSvm.kfidfdf
  train = open(path + svmType + 'train', 'w')
  test = open(path + svmType + 'test', 'w')
  true_train = open(path + svmType + 'true_train', 'w')
  true_test = open(path + svmType + 'true_test', 'w')
  false_train = open(path + svmType + 'false_train', 'w')
  false_test = open(path + svmType + 'false_test', 'w')
  for entry in table.find():
    if dbSvm.train.find({'api_id' : entry['api']}).count():
      f = train
      t_f = true_train
      f_f = false_train
    else:
      f = test
      t_f = true_test
      f_f = false_test
    if category == dbRepo.apis.find({'id':entry['api']})[0]['category']:
        f.write(entry['api'] + ' 1')
        t_f.write(entry['api'] + ' 1')
        for key in sorted(int(k) for k in entry['vector']):
          t_f.write(' ' + str(key) + ':' + str(entry['vector'][str(key)][0]))
        t_f.write('\n')
    else:
        f.write(entry['api'] + ' 0')
        f_f.write(entry['api'] + ' 0')
        for key in sorted(int(k) for k in entry['vector']):
          f_f.write(' ' + str(key) + ':' + str(entry['vector'][str(key)][0]))
        f_f.write('\n')
    for key in sorted(int(k) for k in entry['vector']):
      f.write(' ' + str(key) + ':' + str(entry['vector'][str(key)][0]))
    f.write('\n')

    
#This method builds new Synset Frequency table
def frequencySynset():
  f = open('XXXX','w')
  for entry in dbRepo.frequency.find():
    newWordlist = {}
    for word in entry['wordlist']:
      if word not in keeplist:
        continue
      if dbRepo.wordSynsetMap.find({'word': word, 'category': entry['category']}).count():
        synset = dbRepo.wordSynsetMap.find({'word': word, 'category': entry['category']})[0]['synset']
        newWordlist[re.sub('\.','__',synset)] = newWordlist.get(re.sub('\.','__',synset), 0) + entry['wordlist'][word]
      else:
        f.write(word+' '+entry['category']+'\n')
      #because when conducting real test and training. Words in test set not always in train set, so we should assign a synset for it.
        cnt = Counter({synet: sum(dbRepo.kfirfbyCtgry.find({'category':entry['category']})[0]['wordlist'].get(lemma.name, 0) for lemma in wn.synset(synset).lemmas) for synset in chooseSimKSynsets(word, 3, category = ctgryName.get(entry['category'], entry['category']))})
        synset = cnt.most_common()[0]
        newWordlist[re.sub('\.','__',synset)] = newWordlist.get(re.sub('\.','__',synset), 0) + entry['wordlist'][word]
    entry['wordlist'] = newWordlist
    dbRepo.synsetFrequency.insert(entry)

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

#generate basic wordTosynset in PW db
"""
wordToSynset()
#refine wordTosynset in PW db by change word having synset in Category Tree
#SynsetwithCategry()
#build new synset frequency table in PW db
frequencySynset()
#construct Train Set and Test Set
consTrainSetAndTestSet('Travel', 0.8, 7200, True)
#consTrainSetAndTestSet('Travel', 0.8, 7200, False)
#generate dbSvm.freqinCtgry for calculate kfirf
freqByCategory(dboesvm.newCtgry, dboesvm.freqinCtgry)
freqByCategory(dbsoesvm.newCtgry, dbsoesvm.freqinCtgry)
#generate dbSvm.synsetFreqbyCtgry for calculate kfirf
freqByCategory(dbRepo.synsetFrequency, dbRepo.synsetFreqbyCtgry)
#calculte kfirf for every word in current category
kfirf(0.4, True)
kfirf(0.4, False)
#calculte kfidfdf regarding to "Travel"
kfidfdf(0.5, "Travel", 100, True)
kfidfdf(0.5, "Travel", 100, False)
#generateFiles for libsvm, oesvm using kfidfdf, svm using kfidf
generateFilesforSvm('Travel', 'oesvm', True)
generateFilesforSvm('Travel', 'oesvm', False)
generateFilesforSvm('Travel', 'svm', True)
generateFilesforSvm('Travel', 'svm', False)
cutrow()
svmHelper('./dataset/master/word/oesvmtrain', './dataset/master/word/oesvmtrain', './model/master/modelforoesvm', 'predict_test_file_oesvm')
svmHelper('./dataset/master/synset/oesvmtrain', './dataset/master/synset/oesvmtrain', './model/master/modelforsoesvm', 'predict_test_file_soesvm')
svmHelper('./dataset/master/word/svmtrain', './dataset/word/master/svmtrain', './model/master/modelforsvm', 'predict_test_file_svm')
svmHelper('./dataset/master/synset/svmtrain', './dataset/master/synset/svmtrain', './model/master/modelforsynsetsvm', 'predict_test_file_synsetsvm')
"""
#filter with keeplist

"""
frequencySynset()
freqByCategory(dbRepo.synsetFrequency, dbRepo.synsetFreqbyCtgry)
consTrainSetAndTestSetFilter()
freqByCategory(dbsoesvm.newCtgry, dbsoesvm.freqinCtgry)
kfirf(0.4, True)
kfidfdf(0.5, "Travel", 100, True)
generateFilesforSvm('Travel', 'oesvm', True)
generateFilesforSvm('Travel', 'svm', True)
cutrow()
svmHelper('./dataset/master/synset/oesvmtrain', './dataset/master/synset/oesvmtrain', './model/master/modelforsoesvm', 'predict_test_file_soesvm')
svmHelper('./dataset/master/synset/svmtrain', './dataset/master/synset/svmtrain', './model/master/modelforsynsetsvm', 'predict_test_file_synsetsvm')
"""
svmHelper('./dataset/test/synset/oesvmtrain', './dataset/test/synset/oesvmtrain', './dataset/test/modelforsoesvm', 'predict_test_file_soesvm')
svmHelper('./dataset/test/synset/svmtrain', './dataset/test/synset/svmtrain', './dataset/test/modelforsynsetsvm', 'predict_test_file_synsetsvm')
svmHelper('./dataset/test/word/oesvmtrain', './dataset/test/word/oesvmtrain', './dataset/test/modelforoesvm', 'predict_test_file_oesvm')
svmHelper('./dataset/test/word/svmtrain', './dataset/test/word/svmtrain', './dataset/test/modelforsvm', 'predict_test_file_svm')
