#this code is to generate a tree using hierachy clustering
from setting import db_connection
from Pycluster import treecluster
from nltk.corpus import wordnet as wn
from ete2 import Tree
import numpy as np
from collections import Counter

#this method builds ete2Tree with wn.synset.tree
def getEte2Tree(hypoTree):
  t = Tree()
  for entry in hypoTree:
    if type(entry) is list:
      t.add_child(getEte2Tree(entry))
    else:
      t.name = entry.name
  return t
#the following wordlist is from top 11 words in Travel category
#wordlist1 = ['travel', 'booking', 'data', 'hotel', 'search', 'flight', 'format', 'trip', 'documentation', 'reservation']

#this method generates a newWordList {'n':Words which have Noun Synsets,'v':Words which have Noun Synsets}, all the words are from topk word in categoryi's kfirf table
def generateWordList(category, topk):
  cnt = Counter(db.kfirfbyCtgry.find({'category':category})[0]['wordlist'])
  if len(cnt) < topk:
    wordlist = list(cnt)
  else:
    wordlist = list(cnt.most_common(topk))
  newNounWordlist = []
  newVerbWordlist = []
  for word in wordlist:
    if len(wn.synsets(word[0], wn.NOUN)) > 0:
      newNounWordlist.append(word[0])
    if len(wn.synsets(word[0], wn.VERB)) > 0:
      newVerbWordlist.append(word[0])
  newWordlist = {'n': newNounWordlist, 'v': newVerbWordlist}
  return newWordlist

#Build the Travel forest with Tree from word
def buildCategoryForest(category):
  treeList = []
  hypo = lambda s:s.hyponyms()
  
  treeList.append(getEte2Tree(wn.synset('travel.n.01').tree(hypo)))
  treeList.append(getEte2Tree(wn.synset('travel.v.03').tree(hypo)))
  treeList.append(getEte2Tree(wn.synset('travel.v.04').tree(hypo)))
  treeList.append(getEte2Tree(wn.synset('travel.v.05').tree(hypo)))
  treeList.append(getEte2Tree(wn.synset('travel.v.06').tree(hypo)))
  return treeList
#calculate distance Matrix for words in wordlist
#this one use hoops between two synsets, use ete2 tree's method get_distance to get distance between two sysnsets.
#each word's synset are generated from wordSynsetMap
def calDistanceMatrix(wordlist, treeList):
  synsetList = []
  distanceMatrix = np.zeros(len(wordlist)**2) + 100
  distanceMatrix = distanceMatrix.reshape(10,10)
  for word in wordlist:
    if db.wordSynsetMap.find({'word': word}).count():
      synset = db.wordSynsetMap.find({'word': word})[0]['synset']
    synsetList.append(synset)
  for i in range(len(synsetList)):
    if i == 0:
      for tree in treeList:
        for synset in ['travel.n.01','travel.v.03','travel.v.04','travel.v.05','travel.v.06']:
          for pos1 in tree.search_nodes(name = synset):
            for j in range(len(synsetList) - i - 1):
              for pos2 in tree.search_nodes(name = synsetList[i+j+1]):
                distance = Tree.get_distance(pos1, pos2)
                print synsetList[i], synsetList[i+j+1], wordlist[i], wordlist[i+j+1]
                if distance < distanceMatrix[i][i+j+1]:
                  distanceMatrix[i][i+j+1] = distance
                  distanceMatrix[i+j+1][i] = distance
    else:
      for tree in treeList:
        for pos1 in tree.search_nodes(name = synsetList[i]):
          for j in range(len(synsetList) - i - 1):
            for pos2 in tree.search_nodes(name = synsetList[i+j+1]):
              distance = Tree.get_distance(pos1, pos2)
              print synsetList[i], synsetList[i+j+1], wordlist[i], wordlist[i+j+1]
              if distance < distanceMatrix[i][i+j+1]:
                distanceMatrix[i][i+j+1] = distance
                distanceMatrix[i+j+1][i] = distance
  print distanceMatrix 

#the method calculates similarity between two synsets
def similarity(synset1, synset2):
  sim = synset1.wup_similarity(synset2) 
  if sim is None:
    return 0
  else:
    return sim

#This method chooses Synsets for word, which are Top simk similar to category synsets. You should make sure word has at least one synset in this speech
def chooseSimKSynsets(word, simk = 1, speech = None, category = 'Travel'):
  synsets = {'n':[], 'v':[]}
  if category == 'Travel':
    synsets['n'] = [wn.synset('travel.n.01')]  
    synsets['v'] = [wn.synset('travel.v.03'), wn.synset('travel.v.04'),wn.synset('travel.v.05'),wn.synset('travel.v.06')]  
  else:
    for ctgryWord in category.split():
      if ctgryWord == 'Other':
        ctgryWord == 'entity'
      synsets['n'] += wn.synsets(ctgryWord, 'n')   
      synsets['v'] += wn.synsets(ctgryWord, 'v')
  if speech is None:
    categorySynsets = synsets['n'] + synsets['v']
  else:
    categorySynsets = synsets[speech]  
  SynsetsSim = {}
  for wordSynset in wn.synsets(word, speech):
    SynsetsSim[wordSynset] = sum([similarity(wordSynset,categorySynset) for categorySynset in categorySynsets])
  cnt = Counter(SynsetsSim)
  simKSynsets = [key for key in dict(cnt.most_common(simk))]
  return simKSynsets
      
#this method just calculate  similarity between two word with synsets which make similarity highest
def calSimMatrix1(wordlist):
  simMatrix = np.zeros(len(wordlist)**2)
  simMatrix = simMatrix.reshape(len(wordlist),len(wordlist))
  for i in range(len(wordlist)):
    for synset1 in wn.synsets(wordlist[i]):
      for j in range(len(wordlist) - i -1):
        for synset2 in wn.synsets(wordlist[j]):
          sim = synset1.wup_similarity(synset2)
          if sim > simMatrix[i][i+j+1]:
            simMatrix[i][i+j+1] = sim
            simMatrix[i+j+1][i] = sim
  print simMatrix
  return simMatrix

#this method uses synsets given by chooseSynset to calculate SimMatrix for wordlist
def calSimMatrix2(wordlist, speech, category = 'Travel'):
  size = len(wordlist)
  simMatrix = np.zeros(size**2)
  simMatrix = simMatrix.reshape(size,size)
  synsetlist = [chooseSimKSynsets(word, 1, speech, category)[0] for word in wordlist]
  for i in range(len(wordlist)):
    synset1 = synsetlist[i]
    for j in range(len(wordlist) - i -1):
      synset2 = synsetlist[i+j+1]
      sim = similarity(synset1, synset2)
      simMatrix[i][i+j+1] = sim
      simMatrix[i+j+1][i] = sim
  return simMatrix

#this method transforms a similarity matrix to distance matrix
def simToDistMatrix(simMatrix):
  size = len(simMatrix)
  distMatrix = np.zeros(size**2)
  distMatrix = distMatrix.reshape(size, size)
  for i in range(len(simMatrix)):
    for j in range(len(simMatrix) - i -1):
      if simMatrix[i][i+j+1] == 0:
        distMatrix[i][i+j+1] = -1
        distMatrix[i+j+1][i] = -1
      else:
        dist = 1.0/simMatrix[i][i+j+1]
        distMatrix[i][i+j+1] = dist
        distMatrix[i+j+1][i] = dist
  maxDist = 100 * max(list(distMatrix.reshape(-1)))
  for i in range(len(distMatrix)):
    for j in range(len(distMatrix) - i -1):
      if distMatrix[i][i+j+1] == -1:
        distMatrix[i][i+j+1] = maxDist
        distMatrix[i+j+1][i] = maxDist
  print distMatrix
  return distMatrix

#this method generates tree from PyCluster Tree
def generateTree(tree, wordlist):
  nodeList = []
  for i in range(len(tree)):
    parent = Tree()
    parent.name = str(-(i+1))
    for node in eval(str(tree[i]).split(':')[0]):
      if node >= 0:
        child = Tree()
        child.name = wordlist[node]
        parent.add_child(child)
      else:
        parent.add_child(nodeList[int(-node)-1])
    nodeList.append(parent)
  print nodeList[-1].get_ascii(show_internal=True)
  return nodeList[-1]
  

if __name__ == "__main__":
  db = db_connection['PW_test']
  #tree = buildCategoryForest("Travel")
  #calDistanceMatrix(wordlist1, tree)
  wordlist1 = generateWordList('Travel', 50)
  for speech in ['n', 'v']:
    d = simToDistMatrix(calSimMatrix2(wordlist1[speech], speech, 'Travel'))
    tree = treecluster(method = 'a', dist = 'e', distancematrix = d)
    generateTree(tree, wordlist1[speech])
    print tree
    for i in range(len(wordlist1[speech])):
      print i,wordlist1[speech][i]
