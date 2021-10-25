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


def sql_input_user(user, mydb, mycursor):

    sql = "SELECT userID FROM users WHERE name = '" + user + "'"
    mycursor.execute(sql)
    myresult = mycursor.fetchone()
    if myresult is None:
        sql_add = "INSERT INTO users(name) VALUES('" + user + "')"
        mycursor.execute(sql_add)
        mydb.commit()
        sql = "SELECT userID FROM users WHERE name = '" + user + "'"
        mycursor.execute(sql)
        myresult = mycursor.fetchone()
        userID = myresult[0]
    else:
        userID = myresult[0]

    return userID


def sql_get_anime_details(malID, mydb, mycursor):

    sql = "SELECT * FROM anime WHERE malID = " + str(malID)
    mycursor.execute(sql)
    myresult = mycursor.fetchone()
    return myresult

def sql_get_animelist_score(malID, userID, mydb, mycursor):

    sql = "SELECT score FROM animelists WHERE malID = " + str(malID) + " AND userID = " + str(userID)
    mycursor.execute(sql)
    myresult = mycursor.fetchone()
    score = myresult[0]
    return score


def sql_insert_into_table(table, vals, mydb, mycursor):

    if table == 'anime':
        sql = "SELECT * FROM anime WHERE malID = " + str(vals[0])
    if table == 'animelists':
        sql = "SELECT * FROM animelists WHERE malID = " + str(vals[0]) + " AND userID = " + str(vals[1])
    if table == 'recolists':
         sql = "SELECT * FROM recolists WHERE recoID = " + str(vals[0]) + " AND forID = " + str(vals[1])
    mycursor.execute(sql)
    myresult = mycursor.fetchone()
    if myresult is None:
        sql_add = "INSERT INTO " + table + " VALUES" + str(vals)
        print(sql_add)
        mycursor.execute(sql_add)
        mydb.commit()


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

    user = input("$ Enter a user >>> ")
    userID = sql_input_user(user, mydb, mycursor)

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

        # Import the user's animelist and store it into animelist.json file
        if choice == '1':

            animelist = get_animelist(user, headers)
            anime_vals = [(x["mal_id"], x["title"], 0) for x in animelist]
            for i in anime_vals:
                sql_insert_into_table('anime', i, mydb, mycursor)

            animelist_vals = [(x["mal_id"], userID , x["score"]) for x in animelist]
            for i in animelist_vals:
                sql_insert_into_table('animelists', i, mydb, mycursor)

            length = len(animelist)

            print("  Added (" + str(length) + ") entries")


        # Open the animelist.json and import the recommendations for each anime into recolist.json
        # The entries for each anime are requested sequentially and added to recolist.json,
        # thus the process can be halted at anytime without losing data.
        if choice == '2':

            sql = "SELECT malID FROM animelists WHERE userID = " + str(userID)
            mycursor.execute(sql)
            myresult = mycursor.fetchall()
            animelist = [[x[0], sql_get_anime_details(x[0],mydb,mycursor)[1]] for x in myresult]

            skip = 0
            done = 0
            none = 0

            for anime in animelist:

                recos = get_recos(anime[0], headers, 5)
                if recos:

                    if recos[0] == "TMT":

                        print("  [SKIP]\t" + str(anime[0]) + "\t" + str(anime[1]))
                        skip += 1
                        recolist_vals = (anime[0], anime[0], 0, "SKIP")
                        sql_insert_into_table('recolists', recolist_vals, mydb, mycursor)

                    else:

                        print("  [DONE]\t" + str(anime[0]) + "\t" + str(anime[1]))
                        done += 1

                        for x in recos:
                            anime_vals = (x["mal_id"], x["title"], 0)
                            sql_insert_into_table('anime', anime_vals, mydb, mycursor)

                        recolist_vals = [(x["mal_id"], anime[0], x["recommendation_count"], "DONE") for x in recos]
                        for i in recolist_vals:
                            sql_insert_into_table('recolists', i, mydb, mycursor)

                if not recos:

                    print("  [NONE]\t" + str(anime[0]) + "\t" + str(anime[1]))
                    none += 1
                    recolist_vals = (anime[0], anime[0], 0, "NONE")
                    sql_insert_into_table('recolists', recolist_vals, mydb, mycursor)

            print("  Added (" + str(done) + ") entries, Skipped (" + str(skip) + ") entries and Found (" + str(none) + ") null entries")


        # Go through the skipped imports and try to import them again
        # The entries are added in one go, thus halting will lose all new data
        if choice == '3':

            sql = "SELECT forID FROM recolists WHERE status = 'SKIP'"
            mycursor.execute(sql)
            myresult = mycursor.fetchall()
            animelist = [[x[0], sql_get_anime_details(x[0],mydb,mycursor)[1]] for x in myresult]

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
                            anime_vals = (x["mal_id"], x["title"], 0)
                            sql_insert_into_table('anime', anime_vals, mydb, mycursor)

                        recolist_vals = [(x["mal_id"], anime[0], x["recommendation_count"], "DONE") for x in recos]
                        for i in recolist_vals:
                            sql_insert_into_table('recolists', i, mydb, mycursor)

                if not recos:
                    text = "[NONE]"
                    sql = "DELETE FROM recolists where forID = " + str(anime[0])
                    mycursor.execute(sql)
                    mydb.commit()
                    recolist_vals = (anime[0], anime[0], 0, "NONE")
                    sql_insert_into_table('recolists', recolist_vals, mydb, mycursor)

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

            sql = "SELECT AVG(score) FROM animelists WHERE userID = " + str(userID)
            mycursor.execute(sql)
            myresult = mycursor.fetchone()
            mean = myresult[0]

            sql = "SELECT * FROM recolists WHERE status = 'DONE' AND recoID NOT IN (SELECT malID FROM animelists) AND forID IN (SELECT malID FROM animelists WHERE userID = " + str(userID) + ")"
            mycursor.execute(sql)
            myresult = mycursor.fetchall()

            temp_reco = []
            final_reco = []

            for reco in myresult:

                score_given = sql_get_animelist_score(reco[1], userID, mydb, mycursor)
                score_given = score_given * score_given
                score_given = score_given - (mean * mean)
                score_given = score_given * reco[2]
                temp_reco.extend([[score_given, reco[0]]])

            for key, group in itertools.groupby(temp_reco, lambda x:x[1]):
                score = sum([i[0] for i in group])
                final_reco.extend([[score,key]])

            final_reco = sorted(final_reco, key=lambda x:x[0], reverse = True)

            for reco in final_reco[:100]:
                print("  " + str(reco[0]) + "\t" + str(sql_get_anime_details(reco[1],mydb,mycursor)[1]))


        if choice == '7':

            user = input("$ Enter a user >>> ")
            userID = sql_input_user(user, mydb, mycursor)


        if choice == '8' or choice == 'q':
            if mydb.is_connected():
                mycursor.close()
                mydb.close()
            break

menu()
