import urllib
import bson
from datetime import datetime

import setting

# use constant
timestamp = datetime.utcnow().strftime("%Y_%m_%d_%H_%M_%S")
db = setting.db_connection["PW_" + timestamp]

#This method is used to get entries for both APIs and Mashups from Programmableweb
def getEntries(service_type):
  #the page number for response
  apikey = "?apikey=24aaa22632fe29dd1abee0381f7ae2b6"
  basic_url = "http://api.programmableweb.com/" + service_type + "/-/"
  exception_file = open(setting.working_path + "/files/error/error_"+service_type+"_entries","a")
  page = 1
  url = basic_url + apikey + "&alt=json&page=" + str(page)
  url.encode("UTF-8")
  content = urllib.urlopen(url).read()
  metadata = eval("{"+content.rstrip(";").partition("{")[2])
  errornum = 0
  while eval(metadata["startIndex"]) < eval(metadata["totalResults"]):
    print eval(metadata["startIndex"])
    if service_type == "apis":
      document = db.apis
    else: document = db.mashups
    for entry in metadata["entries"]:
          
      #Pre-processing, make all "." to "_" in mashup's apis's keys for MongoDB
      if service_type == "mashups":
        for key in sorted(entry["apis"]):
          if key.find(".") != -1:
            newkey = key.replace(".","_")
            value = entry["apis"][key]
            del entry["apis"][key]
            entry["apis"][newkey] = value
      #exception handling for mongoDB, and record all the error in file      
      try:
        document.insert(entry)
      except (bson.errors.InvalidStringData, bson.errors.InvalidDocument), e:
        print e," insert"
        errornum += 1
        exception_file.write(str(datetime.now()) + "\n")
        exception_file.write(str(errornum) + " ")
        exception_file.write(str(entry) + "\n")
        exception_file.write(str(e))
        exception_file.write("\n")

    page +=1
    url = basic_url + apikey + "&alt=json&page="+str(page)
    url = url.encode("UTF-8")
    
    #pre-processing for replace all the windows' \r
    content = urllib.urlopen(url).read().replace("\r"," ")

    #exception handling for reading from response, and record all the error in file      
    try:
      metadata = eval("{"+content.rstrip(";").partition("{")[2])
    except Exception,e:
        print e,"reading"
        errornum += 1
        exception_file.write(str(datetime.now()) + "\n")
        exception_file.write(str(errornum) + " ")
        exception_file.write(str(errornum) + " ")
        exception_file.write(str(content) + "\n")
        exception_file.write(str(e) + "\n")
        exception_file.write("\n")
    
  exception_file.close()
  #print metadata["totalResults"]
  #print metadata["entries"][0]

log_file_path = "../log"
#This method check duplicated apis, and write Warning to log
def get_duplicated_apis():
  duplicated_lst = []
  count = 0
  lst = db.apis.group({"id":1},condition = [], initial={'count':0},reduce="function(obj,prev){prev.count++;}")
  for entry in lst:
    if entry["count"] > 1:
      duplicated_lst.append(entry["id"])
  if len(duplicated_lst) > 0:
    log = open(log_file_path, "a")
    log.write(str(len(duplicated_lst)) + " apis duplicated in db:\n")
    for entry in duplicated_lst:
      log.write(str(entry))
  print duplicated_lst, len(duplicated_lst)
  return duplicated_lst, len(duplicated_lst)
   
#This method is used to find duplicated mashups in ProgrammableWeb
def get_duplicated_mashups():
  duplicated_lst = []
  count = 0
  lst = db.mashups.group({"id":1},condition = [], initial={'count':0},reduce="function(obj,prev){prev.count++;}")
  for entry in lst:
    if entry["count"] > 1:
      duplicated_lst.append(entry["id"])
  print duplicated_lst, len(duplicated_lst)
  return duplicated_lst, len(duplicated_lst)

#delete the duplicated mushups in db
def delete_duplicates():
  duplicated_ids = get_duplicated_mashups()[0]
  for duplicated_id in duplicated_ids:
    url = "http://api.programmableweb.com/mashups/"+duplicated_id.rpartition("/")[2]+"?apikey=24aaa22632fe29dd1abee0381f7ae2b6&alt=json"

    #get Programmable responded one for duplicated mashups, and going to delete the other one
    content = urllib.urlopen(url).read()
    metadata = eval("{"+content.rstrip(";").partition("{")[2])
    entries = metadata["entries"]

    #currently each duplicated mashup has two entries and only return 1 when querying by id
    #write to log when detecting more than 1 entries in response
    if len(entries) > 1:
      log = open(log_file_path,"a")
      log.write(str(datetime.now()))
      log.write("Warming:the duplicated mashup returned " + str(len(entries)) + " from API response:\n")
      log.write(entries)
    deleted_entry = {}
    for entry in db.mashups.find(entries[0]['id']):
      if entry != entries[0]:      
        deleted_entry = entry
        db.mashups.remove(entry, True)

    #remove from pair database, but this will remove the shared apis used by duplicated mashups. We should add back one later.
    for api_id in deleted_entry["apis"].values():
      db.pairs.remove({"api":api_id,"mashup":duplicated_id})
      if api_id in db.mashups.find_one({"id":duplicated_id})["apis"].values():
        db.pairs.insert({"api":api_id,"mashup":duplicated_id})

