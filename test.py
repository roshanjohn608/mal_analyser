import mysql.connector
import requests
import json
import itertools
import math
import os
from collections import Counter

# Get the animelist of the given user, filtered by the status "Completed"
# Returns a list of dicts, with each dict having the details of an anime
def get_animelist(user, headers):

    url = "https://jikan1.p.rapidapi.com/user/" + user + "/animelist/completed"
    page_number = 1
    animelist = []

    # One page can only return 300 anime, thus the loop over all pages
    while True:
        print("  Getting page no: " + str(page_number))
        querystring = {"page":str(page_number)}
        response = requests.request("GET", url, headers=headers, params=querystring)
        page_content = response.json().get("anime")

        if not page_content:
            break

        animelist.extend(page_content)
        page_number += 1

    return(animelist)


# Get the recommendations for a particular anime
# Returns a list of dicts, with each dict having the details of a recommendation
# In the case of the anime havnig no recommendations, returns a null value
# In the case of a response timeout, returns a list containing "TMT"
def get_recos(id, headers, timeout):

    url = "https://jikan1.p.rapidapi.com/anime/" + str(id) + "/recommendations"
    try:
        response = requests.request("GET", url, headers=headers, timeout = timeout)
        recolist = response.json().get("recommendations")
    except:
        recolist = ["TMT"]

    return recolist


# Get the mean for an animelist, and the stats required to calculate
# the scoring for an anime recommendation
# Returns the mean as an integer and the recolist(stats) as a list of list of dicts
# recolist contains a list of items, which are lists of recommendations for an anime
def get_stats(animelist, recolist):

    mean = 0
    count = 0
    animelist = sorted(animelist, key=lambda x:x["score"], reverse = True)
    animelist = [ x for x in animelist if x["score"] != 0]
    for key, group in itertools.groupby(animelist, lambda x:x["score"]):
        s = len(list(group))
        count += s
        mean += s * key
    mean = math.floor(mean/count)

    for recos in recolist:
        if recos != "NONE":
            total_recos = sum([ reco["recommendation_count"] for reco in recos])
            for reco in recos:
                reco["recommendation_count"] = reco["recommendation_count"] * reco["recommendation_count"] /total_recos

    return mean, recolist

def sql_input_user(mydb, mycursor):

    user = input("$ Enter a user >>> ")
    sql = "SELECT userID FROM users WHERE name = '" + user + "'"
    mycursor.execute(sql)
    myresult = mycursor.fetchall()
    if myresult:
        userID = myresult[0][0]
    if not myresult:
        sql_add = "INSERT INTO users(name) VALUES('" + user + "')"
        mycursor.execute(sql_add)
        mydb.commit()
        sql = "SELECT userID FROM users WHERE name = '" + user + "'"
        mycursor.execute(sql)
        myresult = mycursor.fetchall()
        userID = myresult[0][0]

    return userID

def sql_get_animetitle(malID, mydb, mycursor):

    sql = "SELECT title FROM anime WHERE malID = " + str(malID)
    mycursor.execute(sql)
    myresult = mycursor.fetchall()
    title = myresult[0][0]
    return title

def sql_get_user(userID, mydb, mycursor):

    sql = "SELECT name FROM users WHERE userID = " + str(userID)
    mycursor.execute(sql)
    myresult = mycursor.fetchall()
    name = myresult[0][0]
    return name


# The main function which is called first
# The function gives a prompt for entering the username, and then
# displays a menu of actions for that particular user
def menu():

    mydb = mysql.connector.connect(
      host = "localhost",
      user = "furry_tail",
      password = "qwerty@123",
      database = "mal_analyser"
    )

    mycursor = mydb.cursor()

    # Don't use my API key !!!
    headers = {
        'x-rapidapi-host': "jikan1.p.rapidapi.com",
        'x-rapidapi-key': "72f87896d3msh622499ddf3ab002p1c35b1jsn11141231d626"
        }

    userID = sql_input_user(mydb, mycursor)
    user = sql_get_user(userID, mydb, mycursor)

    while True:

        print("\n  ID : " + str(userID) + "\t\t NAME : " + user + "\n")
        print("+------------+  MENU  +------------+")
        print("|                                  |")
        print("| 1. Import a MyanimeList          |")
        print("| 2. Import Recommendations        |")
        print("| 3. Check skipped recommendations |")
        print("| 4. Compute a recommendation list |")
        print("| 5. Print anime recommendation    |")
        print("| 6. Compute a network of anime    |")
        print("| 7. Change the current user       |")
        print("| 8. Quit                          |")
        print("|                                  |")
        print("+----------------------------------+\n")
        choice = input("$ Enter your choice >>> ")


        if choice == '7':

            userID = sql_input_user(mydb, mycursor)


        # Import the user's animelist and store it into animelist.json file
        if choice == '1':

            animelist = get_animelist(user, headers)
            anime_vals = [(x["mal_id"], x["title"]) for x in animelist]
            animelist_vals = [(x["mal_id"], userID , x["score"]) for x in animelist]
            sql = "INSERT INTO anime (malID, title) VALUES (%s, %s)"
            mycursor.executemany(sql, anime_vals)
            mydb.commit()
            sql = "INSERT INTO animelists VALUES (%s, %s, %s)"
            mycursor.executemany(sql, animelist_vals)
            mydb.commit()
            length = len(animelist)

            print("  Added (" + str(length) + ") entries")


        # Open the animelist.json and import the recommendations for each anime into recolist.json
        # The entries for each anime are requested sequentially and added to recolist.json,
        # thus the process can be halted at anytime without losing data.
        if choice == '2':

            sql = "SELECT malID FROM animelists WHERE userID = " + str(userID)
            mycursor.execute(sql)
            myresult = mycursor.fetchall()
            animelist = [[x[0], sql_get_animetitle(x[0],mydb,mycursor)] for x in myresult]

            skip = 0
            done = 0
            none = 0

            for anime in animelist:

                recos = get_recos(anime[0], headers, 5)
                if recos:
                    if recos[0] == "TMT":
                        print("  [SKIP]\t" + str(anime[0]) + "\t" + str(anime[1]))
                        skip += 1
                        sql = "INSERT INTO recolists VALUES (%s, %s, %s, %s)"
                        recolist_vals = (anime[0], anime[0], 0, "SKIP")
                        mycursor.execute(sql, recolist_vals)
                        mydb.commit()
                    else:
                        print("  [DONE]\t" + str(anime[0]) + "\t" + str(anime[1]))
                        done += 1
                        for x in recos:
                            sql2 = "SELECT * FROM anime WHERE malID = " + str(x["mal_id"])
                            mycursor.execute(sql2)
                            myresult = mycursor.fetchall()
                            if not myresult:
                                sql = "INSERT INTO anime (malID, title) VALUES (%s, %s)"
                                anime_vals = (x["mal_id"], x["title"])
                                mycursor.execute(sql, anime_vals)
                                mydb.commit()
                        sql = "INSERT INTO recolists VALUES (%s, %s, %s, %s)"
                        recolist_vals = [(x["mal_id"], anime[0], x["recommendation_count"], "DONE") for x in recos]
                        mycursor.executemany(sql, recolist_vals)
                        mydb.commit()
                if not recos:
                    print("  [NONE]\t" + str(anime[0]) + "\t" + str(anime[1]))
                    none += 1
                    sql = "INSERT INTO recolists VALUES (%s, %s, %s, %s)"
                    recolist_vals = (anime[0], anime[0], 0, "NONE")
                    mycursor.execute(sql, recolist_vals)
                    mydb.commit()


            print("  Added (" + str(done) + ") entries, Skipped (" + str(skip) + ") entries and Found (" + str(done) + ") null entries")


        # Go through the skipped imports and try to import them again
        # The entries are added in one go, thus halting will lose all new data
        if choice == '3':

            sql = "SELECT forID FROM recolists WHERE status = 'SKIP'"
            mycursor.execute(sql)
            myresult = mycursor.fetchall()
            animelist = [[x[0], sql_get_animetitle(x[0],mydb,mycursor)] for x in myresult]

            for anime in animelist:
                recos = get_recos(anime[0], headers, 5)
                print(anime)
                if recos:
                    if recos[0] == "TMT":
                        text = "[SKIP]"
                    else:
                        text = "[DONE]"
                        sql = "DELETE FROM recolists where forID = " + str(anime[0])
                        mycursor.execute(sql)
                        mydb.commit()
                        for x in recos:
                            sql2 = "SELECT * FROM anime WHERE malID = " + str(x["mal_id"])
                            mycursor.execute(sql2)
                            myresult = mycursor.fetchall()
                            if not myresult:
                                sql = "INSERT INTO anime (malID, title) VALUES (%s, %s)"
                                anime_vals = (x["mal_id"], x["title"])
                                mycursor.execute(sql, anime_vals)
                                mydb.commit()
                        sql = "INSERT INTO recolists VALUES (%s, %s, %s, %s)"
                        recolist_vals = [(x["mal_id"], anime[0], x["recommendation_count"], "DONE") for x in recos]
                        mycursor.executemany(sql, recolist_vals)
                        mydb.commit()
                if not recos:
                    text = "[NONE]"
                    sql = "DELETE FROM recolists where forID = " + str(anime[0])
                    mycursor.execute(sql)
                    mydb.commit()
                    sql = "INSERT INTO recolists VALUES (%s, %s, %s, %s)"
                    recolist_vals = (anime[0], anime[0], 0, "NONE")
                    mycursor.execute(sql, recolist_vals)
                    mydb.commit()

                print("  " + text + " " + str(anime[0]) + "\t" + str(anime[1]))


        # Create a recommendation score for each anime,
        # based on the number of times it is recommended,
        # the user rating for the anime it is recommended for,
        # and the mean user rating.

        # The recommendation score for a particular anime I, is:
        # Score = ∑ ( (Uj^2 - M^2) * (Cij^2 / Tj) ) for all (J) in (N)
        # where,    (N) is the total number of anime in the user animelist
        #           (Uj) is the user rating for the (J)th anime
        #           (M) is the mean user rating
        #           (Cij) is the number of times anime (I) has been recommended for an anime (J)
        #           (Tj) is the total number of recommendations that anime (J) has

        # The final scores are added to recommendation.json as a list of 2-element lists
        # The first element is the anime name, and the second element is the recommendation score
        if choice == '4':

            with open(animelist_file, 'r') as openfile:
                animelist = json.load(openfile)
            with open(recolist_file, 'r') as openfile:
                recolist = json.load(openfile)

            print("  Checking imported recommendations for flaws .....", end = ' ')

            if True:

                print("DONE\n")

                mean, recolist = get_stats(animelist, recolist)

                for i in range(0,len(animelist)):
                    recos = recolist[i]
                    anime = animelist[i]
                    if recos != "NONE":
                        for reco in recos:
                            score = (anime["score"] * anime["score"]) - (mean * mean)
                            reco["score"] = score * reco["recommendation_count"]

                list_json = json.dumps(recolist, indent = 4)
                with open(recolist_file_temp, "w") as outfile:
                    outfile.write(list_json)

                recolist_temp = []
                for item in recolist:
                    if item != "NONE" and item != "SKIP":
                        recolist_temp.extend(item)

                recolist_temp = [item for item in recolist_temp if item["mal_id"] not in [anime["mal_id"] for anime in animelist]]
                recolist_temp = [[anime["title"],anime["score"]] for anime in recolist_temp]
                recolist_temp = sorted(recolist_temp, key=lambda x:x[0])

                recolist_final = []
                for key, group in itertools.groupby(recolist_temp, lambda x:x[0]):
                    s = sum([reco[1] for reco in group])
                    recolist_final.extend([[key,s]])

                recolist_final = sorted(recolist_final, key=lambda x:x[1], reverse = True)

                for reco in recolist_final[:100]:
                    print("  " + str(reco[1]) + "\t" + str(reco[0]))

                list_json = json.dumps(recolist_final, indent = 4)
                with open(recommendation_file, "w") as outfile:
                    outfile.write(list_json)

            else:
                print("ERROR")


        if choice == '5':

            while True:
                id = input("\n$ Enter the anime id or (q) to quit >>> ")
                if id == 'q':
                    break
                recolist = get_recos(id, headers, 60)
                for item in recolist:
                    print("  " + str(item))


        if choice == '6':

            with open(animelist_file, 'r') as openfile:
                animelist = json.load(openfile)
            with open(recolist_file, 'r') as openfile:
                recolist = json.load(openfile)

            print("  Checking imported recommendations for flaws .....", end = ' ')

            if True:

                print("DONE\n")

                recolist_temp = []
                for item in recolist:
                    if item != "SKIP":
                        recolist_temp.extend(item)

                recolist_temp = [[anime["title"],anime["recommendation_count"]] for anime in recolist_temp]
                recolist_temp = sorted(recolist_temp, key=lambda x:x[0])

                recolist_final = []
                for key, group in itertools.groupby(recolist_temp, lambda x:x[0]):
                    s = sum([reco[1] for reco in group])
                    recolist_final.extend([[key,s]])

                recolist_final = sorted(recolist_final, key=lambda x:x[1], reverse = True)

                for reco in recolist_final:
                    print("  " + str(reco[1]) + "\t" + str(reco[0]))

                list_json = json.dumps(recolist_final, indent = 4)
                with open(network_file, "w") as outfile:
                    outfile.write(list_json)

            else:
                print("ERROR")


        if choice == '8' or choice == 'q':
            if mydb.is_connected():
                mycursor.close()
                mydb.close()
            break

menu()
