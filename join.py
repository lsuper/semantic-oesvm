#from pymongo import Connection
from fetch import db
#db_connection = Connection("localhost",27017)
#db = db_connection["PW"]

def insert_Pair():
  entries = db.mashups.find()
  document = db.pairs
  for entry in entries:
    mashup_id = entry["id"]
    for api_id in entry['apis'].values():
      document.insert({"api":api_id,"mashup":mashup_id})
