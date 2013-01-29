from __future__ import division
from setting import db_connection
from iterPreprocess import preprocessWords, ctgryName, freqByService  
from collections import Counter
import re
import sys
from subprocess import *
import math
from hierachy_tree import chooseSimKSynsets
from nltk.corpus import wordnet as wn
import os

dbsoesvm = db_connection['soesvm']
dboesvm = db_connection['oesvm']
dbTest = db_connection['testSet']
dbTrain = db_connection['trainSet']

#This method calculate frequency of each preprocessd words. The return value contains also contain initialCategory.
def frequency(apiID):
  freqEntry = {}
  freqEntry['wordlist'] = dbTest.frequency.find({'api_id':apiID})[0]['wordlist']
  freqEntry['category'] = initialCategory(freqEntry['wordlist'])
  return freqEntry

#For semantic oesvm, we need a initial category for transform words to synset
#cnt is a frequency word Counter
def initialCategory(cnt):
  dCnt = dict(cnt)
  ctgry = ''
  maxSum = -1
  for entry in dbTrain.wordKfirf.find():
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
    if dbTrain.wordSynsetMap.find({'category':category, 'word': word}).count():
      synset = dbTrain.wordSynsetMap.find({'category':category, 'word': word})[0]['synset'].replace('.','__')
      newWordlist[synset] = newWordlist.get(synset, 0) + freqEntry['wordlist'][word]
    else:
      cnt = Counter({synset: sum(dbTrain.wordKfirf.find({'category':category})[0]['wordlist'].get(lemma.name, 0) for lemma in synset.lemmas) for synset in chooseSimKSynsets(word, 3, category = ctgryName.get(category, category))})
      synset = cnt.most_common()[0][0].name.replace('.','__')
      newWordlist[synset] = newWordlist.get(synset, 0) + freqEntry['wordlist'][word]
    wordToSynsetMap[word] = synset.replace('__','.')
  freqEntry['wordlist'] = newWordlist
  print freqEntry
  return freqEntry, wordToSynsetMap, category

#This method calculates the kfidfdf for the new document words. You should see that the document frequency actuall includes this new document.
def kfidfdf(beta, category, omega, freqEntry, isSynset):
  if isSynset:
    dbMethod = dbsoesvm
  else:
    dbMethod = dboesvm
  totalFreq = 0
  documentTotalNumber = dbTrain.synsetFrequency.count() 
  for word in freqEntry['wordlist']:
    #sum all keywords in one api frequency
    totalFreq += freqEntry['wordlist'][word]
  kfidfdfEntry = {'vector':{}}
  tfidfEntry = {'vector':{}}
  rankList = dbTrain.synsetKfirf.find({'category': category})[0]['wordlist']
  rankList = Counter(rankList)
  if omega < len(rankList):
    omega = len(rankList) - 1
  most_commonList = rankList.most_common()
  maxKfirf = most_commonList[omega][1]
  for word in freqEntry['wordlist']:
    if dbMethod.wordIndexMap.find({'word':word}).count():
    #calculate api with this word count in all the repos
      wordDocumentFreq = dbMethod.documentFreq.find()[0][word] + 1
      tfidf = freqEntry['wordlist'][word]/totalFreq * math.log(documentTotalNumber+1 / (wordDocumentFreq + 1 ), 10)
      tfidfEntry['vector'][str(dbMethod.wordIndexMap.find({'word': word})[0]['index'])] = [tfidf, word]
      if maxKfirf >  rankList.get(word, -1):
        kfidfdfEntry['vector'][str(dbMethod.wordIndexMap.find({'word':word})[0]['index'])] = [tfidf, word]
      else:
        rank = [k[0] for k in most_commonList].index(word)
        kfidfdfEntry['vector'][str(dbMethod.wordIndexMap.find({'word':word})[0]['index'])] = [tfidf * (1 + (1 - math.floor(rank / math.sqrt( omega )) / math.sqrt( omega ) ) * beta), word] 
  return kfidfdfEntry, tfidfEntry 
   
#This method writes a line to testing file for libSVM.
def generateFilesforSvm(category, vectorEntry, testFile, pWCtgry):
  #abitrary assigned 0
  if category == pWCtgry:
    testFile.write('1')
  else:
    testFile.write('0')
  for key in sorted(int(k) for k in vectorEntry['vector']):
    testFile.write(' ' + str(key) + ':' + str(vectorEntry['vector'][str(key)][0]))
  testFile.write('\n')

#This method generates vector for a test document, and use generateFilesforSvm to write one line to testFile
def generateFiles(apiID, testFiles, pWCtgry):
  freqEntry, wordToSynsetMap, initialCtgry = synsetFrequency(frequency(apiID))
  vectorEntry = kfidfdf(0.5, 'Travel', 100, freqEntry, True)[0]
  generateFilesforSvm('Travel', vectorEntry, testFiles['soesvm'], pWCtgry)
  vectorEntry = kfidfdf(0.5, 'Travel', 100, freqEntry, True)[1]
  generateFilesforSvm('Travel', vectorEntry, testFiles['synsetsvm'], pWCtgry)
  freqEntry = frequency(apiID)
  vectorEntry = kfidfdf(0.5, 'Travel', 100, freqEntry, False)[0]
  generateFilesforSvm('Travel', vectorEntry, testFiles['oesvm'], pWCtgry)
  vectorEntry = kfidfdf(0.5, 'Travel', 100, freqEntry, False)[0]
  generateFilesforSvm('Travel', vectorEntry, testFiles['svm'], pWCtgry)

#This method can use libSVM to test testFile with modelFile, and output result to predictTestFile
def predict(modelFileName, testFileName):
  cmd = 'svm-predict "{0}" "{1}" "{2}"'.format(testFileName, modelFileName, './test/result_' + testFileName.split('/')[-1])
  print('Testing...')
  p = Popen(cmd, shell = True)
  p.communicate()
  p.wait()
  """
  line = f_result.readline()
  print line
  if line.rstrip('\n') == '1':
    return {'category': 'Travel', 'wordToSynsetCtgry': initialCtgry, 'wordToSynsetMap': wordToSynsetMap}
  else:
    return {'category': 'non-Travel', 'wordToSynsetCtgry': initialCtgry, 'wordToSynsetMap': wordToSynsetMap}
  """

#the following is main part
if __name__ == '__main__':
  testFiles = {}
  testFileNames = {}
  modelFileNames = {}
  testFileNames['soesvm'] = './test/soesvm'
  testFileNames['synsetsvm'] = './test/synsetsvm'
  testFileNames['oesvm'] = './test/oesvm'
  testFileNames['svm'] = './test/svm'
  modelFileNames['soesvm'] = './model/master/modelforsoesvm'
  modelFileNames['synsetsvm'] = './model/master/modelforsynsetsvm'
  modelFileNames['oesvm'] = './model/master/modelforoesvm'
  modelFileNames['svm'] = './model/master/modelforsvm'
  f_Truth = open('./test/testTruth', 'w')
  for entry in dbTest.apis.find():
    freqEntry, wordToSynsetMap, initialCtgry = synsetFrequency(frequency(entry['id']))
    f_Truth.write(initialCtgry + ' ' +entry['category'] + ' ' + entry['id'] + '\n')
  """
  freqByService(dbTest)
  for key, value in testFileNames.iteritems():
    testFiles[key] = open(value, 'w')
  for entry in dbTest.apis.find():
    generateFiles(entry['id'], testFiles, entry['category'])
    f_Truth.write(entry['category'] + ' ' + entry['id'] + '\n')
  f_Truth.close()
  """
  for key, value in testFileNames.iteritems():
    predict(modelFileNames[key], value)
  for key, value in testFiles.iteritems():
    value.close()
    
  """
  programPath = '.'
  if len(sys.argv) != 2:
    print 'error: Need one directory'
  else:
    absPath = os.path.abspath(sys.argv[1])
    result = {}
    for dirpath, dirs, files in os.walk(absPath):
      for filename in files:
        f = open(os.path.join(dirpath, filename))
        content = '' 
        for line in f:
          content += line
          result[os.path.join(dirpath, filename)] = predict(programPath + '/model/iteration/modelforsoesvm', content, programPath + '/test/predict_result', programPath + '/test/svm_test') 
    print result
  """
