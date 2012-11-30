#from pymongo import Connection
from fetch import db
import setting

#this method is just for statistical use
def mashup_without_api():
  lst = []
  for mashup in db.mashups.find():
    if db.pairs.find({"mashup":mashup["id"]}).count() == 0:
      lst.append(mashup["id"])
  print lst,len(lst)
  return lst

def api_without_mashup():
  lst = []
  for api in db.apis.find():
    if db.pairs.find({"api":api["id"]}).count():
      lst.append(api["id"])
  print len(lst)
  return lst

exception_file_path = setting.working_path + "/files/errors/exception_api_not_in_db"
def api_notin_db():
  lst = []
  for api in db.pairs.distinct("api"):
    num = db.apis.find({"id":api}).count() 
    if num == 0:
      print api,num
      lst.append(api)
      exception_file = open(exception_file, "a")
      exception_file.write(str(len(lst)) + "apis not in db but used by apis")
      for entry in lst:
        exception_file.write(str(entry))
  return lst 

