import sys
import os

def cutrow():
  for dirpath, dirs, files in os.walk("./rawdataset/master"):
    for file_name in files:
      f_path = os.path.join(dirpath, file_name)
      f = open(f_path, 'r')
      nf = open(f_path.replace('raw',''), 'w')
      for line in f:
        nf.write(line.partition(' ')[2])
  
