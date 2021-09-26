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


# The main function which is called first
# The function gives a prompt for entering the username, and then
# displays a menu of actions for that particular user
def menu():

    user = input("$ Enter a user >>> ")

    # Don't use my API key !!!
    headers = {
        'x-rapidapi-host': "jikan1.p.rapidapi.com",
        'x-rapidapi-key': "72f87896d3msh622499ddf3ab002p1c35b1jsn11141231d626"
        }

    # New folder created to store all the json files
    pwd = "data/"
    if not os.path.exists(pwd):
        os.makedirs(pwd)

    # All the json files that need to be created and used
    animelist_file = pwd + user + "_animelist.json"
    recolist_file = pwd + user + "_recolist.json"
    recolist_file_temp = pwd + user + "_recolist_temp.json"
    recolist_file_backup = pwd + user + "_recolist_backup.json"
    recommendation_file = pwd + user + "_recommendation.json"
    network_file = pwd + user + "_network.json"

    while True:

        print("\n")
        print("+------------+  MENU  +------------+")
        print("|                                  |")
        print("| 1. Import a MyanimeList          |")
        print("| 2. Import Recommendations        |")
        print("| 3. Check skipped recommendations |")
        print("| 4. Compute a recommendation list |")
        print("| 5. Print anime recommendation    |")
        print("| 6. Compute a network of anime    |")
        print("| 7. Quit                          |")
        print("|                                  |")
        print("+----------------------------------+\n")
        choice = input("$ Enter your choice >>> ")


        # Import the user's animelist and store it into animelist.json file
        if choice == '1':

            animelist = get_animelist(user, headers)
            list_json = json.dumps(animelist, indent = 4)
            with open(animelist_file, "w") as outfile:
                outfile.write(list_json)
            length = len(animelist)

            print("  Added (" + str(length) + ") entries")


        # Open the animelist.json and import the recommendations for each anime into recolist.json
        # The entries for each anime are requested sequentially and added to recolist.json,
        # thus the process can be halted at anytime without losing data.
        if choice == '2':

            with open(animelist_file, 'r') as openfile:
                animelist = json.load(openfile)
            length = len(animelist)

            try:
                f = open(recolist_file)

            except FileNotFoundError:

                reco_json = json.dumps([], indent = 4)
                with open(recolist_file, "w") as outfile:
                    outfile.write(reco_json)
                with open(recolist_file_backup, "w") as outfile:
                    outfile.write(reco_json)

            with open(recolist_file, 'r') as openfile:
                recolist_old = json.load(openfile)
            index = len(recolist_old)

            print("\n  Found " + str(index) + " entries .....")
            print("  ADDING .....\n")

            skip = 0
            done = 0
            none = 0

            # Going through the remaining entries from the animelist.json
            # to import their recommendations to recolist.json
            for i in range(index,length):

                with open(recolist_file, 'r') as openfile:
                    recolist_old = json.load(openfile)

                anime = animelist[i]
                recos = get_recos(anime["mal_id"], headers, 5)
                if recos:
                    if recos[0] == "TMT":
                        recos = "SKIP"
                        print("  [SKIP]\t" + str(anime["mal_id"]) + "\t" + str(anime["title"]))
                        skip += 1
                    else:
                        print("  [DONE]\t" + str(anime["mal_id"]) + "\t" + str(anime["title"]))
                        done += 1
                if not recos:
                    recos = "NONE"
                    print("  [NONE]\t" + str(anime["mal_id"]) + "\t" + str(anime["title"]))
                    none += 1

                recolist_old.extend([recos])
                reco_json = json.dumps(recolist_old, indent = 4)
                with open(recolist_file, 'w') as outfile:
                    outfile.write(reco_json)
                with open(recolist_file_backup, "w") as outfile:
                    outfile.write(reco_json)

            print("  Added (" + str(done) + ") entries, Skipped (" + str(skip) + ") entries and Found (" + str(done) + ") null entries")


        # Go through the skipped imports and try to import them again
        # The entries are added in one go, thus halting will lose all new data
        if choice == '3':

            with open(animelist_file, 'r') as openfile:
                animelist = json.load(openfile)
            with open(recolist_file, 'r') as openfile:
                recolist = json.load(openfile)
            anime_id_list = [anime["mal_id"] for anime in animelist]

            print("\n  SEARCHING .....\n")

            recolist_temp = []
            index = 0
            for item in recolist:
                anime = animelist[index]
                if item == "SKIP":
                    recos = get_recos(anime["mal_id"], headers, 5)
                    if recos:
                        if recos[0] == "TMT":
                            recos = "SKIP"
                            text = "[SKIP]"
                        else:
                            text = "[CRTD]"
                    if not recos:
                        text = "[OKAY]"
                        recos = "NONE"

                    recolist_temp.extend([recos])
                    print("  " + text + " " + str(anime["mal_id"]) + "\t" + str(anime["title"]))
                else:
                    recolist_temp.extend([recolist[index]])
                index += 1

            list_json = json.dumps(recolist_temp, indent = 4)
            with open(recolist_file, "w") as outfile:
                outfile.write(list_json)

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


        if choice == '7' or choice == 'q':
            break

menu()
