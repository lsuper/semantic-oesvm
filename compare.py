#from pymongo import Connection
from subprocess import call

import setting
db_connection = setting.db_connection
#this compare method is a brute force one. It compare all fields in entries between two dump db
#return the diff dumpdir1, dumpdir2
def compare(dumpdir1, dumpdir2):
  diff_file = {"apis": open(setting.working_path + "/files/diff/diff_apis_" + dumpdir1.rpartition("/")[2] + "_" + dumpdir2.rpartition("/")[2], "w"), "mashups": open(setting.working_path + "/files/diff/diff_mashups_" + dumpdir1.rpartition("/")[2] + "_" + dumpdir2.rpartition("/")[2], "w")} 
  diff_pairs_file = open(setting.working_path + "/files/diff/diff_pairs_" + dumpdir1.rpartition("/")[2] + "_" + dumpdir2.rpartition("/")[2], "w") 
 # 1 restore databases
  call([setting.db_path + "/bin/mongorestore", "-d", "temp1", setting.working_path + "/dump/" + dumpdir1])
  call([setting.db_path + "/bin/mongorestore", "-d", "temp2", setting.working_path + "/dump/" + dumpdir2])
  #db_connection = Connection("localhost",27017)
  db1 = db_connection["temp1"]
  db2 = db_connection["temp2"]
  lst = ["apis", "mashups"]
 
  result = "Comparison between " + dumpdir1 + "and" + dumpdir2 + "\n"  
  # 2 compare each entry
  for kind in lst:
    add_lst = []
    del_lst = []
    update_lst = []
    #find added entries
    for entry1 in db1[kind].find():
      entry1.pop("_id")
      cursor = db2[kind].find({"id":entry1["id"]})
      #This means db1 add entry to db2
      if cursor.count() == 0:
        add_lst.append(entry1)
      else:
        entry2 = cursor[0]
        entry2.pop("_id")
        if entry1 != entry2:
          #list to store updated field in an entry
          update_field_lst = []
          for key in entry1:
            if entry1[key] != entry2[key]:
              update_field_lst.append({key:[entry1[key],entry2[key]]})
          update_lst.append({entry1["id"]:update_field_lst})
    #find deleted entries
    for entry2 in db2[kind].find():
      entry2.pop("_id")
      cursor = db1[kind].find({"id":entry2["id"]})
      #This means db1 delete entry from db2
      if cursor.count() == 0:
        del_lst.append(entry2)
    
    result += kind + " result:\n"
    result += "++++++++++add " + str(len(add_lst)) + " entries\n"
    diff_file[kind].write("++++++++++add " + str(len(add_lst)) + " entries\n")
    for entry in add_lst:
      result += str(entry)
      diff_file[kind].write(str(entry))
    result += "\n++++++++++\n----------delete " + str(len(del_lst)) + " entries\n"
    diff_file[kind].write("\n++++++++++\n----------delete " + str(len(del_lst)) + " entries\n")
    for entry in del_lst:
      result += str(entry)
      diff_file[kind].write(str(entry))
    result += "\n----------\n>>>>>>>>>>update " + str(len(update_lst)) + " entries\n"
    diff_file[kind].write("\n----------\n>>>>>>>>>>update " + str(len(update_lst)) + " entries\n")
    for entry in update_lst:
      result += str(entry)
      diff_file[kind].write(str(entry))
    result += "\n>>>>>>>>>>"
    diff_file[kind].write("\n>>>>>>>>>>\n")
    
  add_lst = []
  del_lst = []  
  for entry in db1.pairs.find():
    entry.pop("_id")
    if db2.pairs.find(entry).count() == 0:
      add_lst.append(entry)
  for entry in db2.paris.find():
    entry.pop("_id")
    if db1.pairs.find(entry).count() == 0:
      del_lst.append(entry)
  
  result += "pair result:\n"
  result += "++++++++++add " + str(len(add_lst)) + " entries\n"
  diff_pairs_file.write("++++++++++add " + str(len(add_lst)) + " entries\n")
  for entry in add_lst:
    result += str(entry)
    diff_pairs_file.write(str(entry))
  result += "\n++++++++++\n----------delete " + str(len(del_lst)) + " entries\n"
  diff_pairs_file.write("\n++++++++++\n----------delete " + str(len(del_lst)) + " entries\n")
  for entry in del_lst:
    result += str(entry)
    diff_pairs_file.write(str(entry))
  result += "\n----------\n"
  diff_pairs_file.write("\n----------\n")
 # 3 drop databases
  db_connection.drop_database("temp1")  
  db_connection.drop_database("temp2")
  return result
