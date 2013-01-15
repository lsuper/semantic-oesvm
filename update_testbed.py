from subprocess import call
from fetch import getEntries, delete_duplicates, timestamp
from compare import compare
from check import mashup_without_api, api_without_mashup, api_notin_db
from join import insert_Pair
import setting

#add drop table before get from api
#db name example "PW_2012_09_08_23_17_00"
def update():
  getEntries("apis")
  print "fetch apis done!"
  getEntries("mashups")
  print "fetch mashups done!"
  delete_duplicates()
  print "delete done!"
  api_notin_db()
  print "api not in db"
  insert_Pair()
  print "join table done"
  #call([setting.db_path + "/bin/mongodump", "--db", "PW_" + timestamp,  "-o", setting.working_path + "/dump/"])
  call(["mongodump", "--db", "PW_" + timestamp,  "-o", setting.working_path + "/dump/"])
  print "drop done"
  db = setting.db_connection["utilities"]
  db.dump.insert({"filename" : "PW_" + timestamp})
  print "update all done!"
 """ 
  previous = db.previous.find()[0]["filename"]
  print previous
  compare("PW_" + timestamp, previous)
 # compare("PW_2012_09_20_17_41_01", previous)
  db.previous.remove({"filename" : previous})
  db.previous.insert({"filename" : "PW_" + timestamp})
#  db.previous.insert({"filename" : "PW_2012_09_20_17_41_01"})
  print "compare done"
"""
