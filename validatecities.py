#!/usr/bin/env python

"""
This script provides a solution to challenge problem #3: "Fuzz-ography".
The script sequence structure is summarized in the following logical outline:
    
    (I) Definition of Constants: creates input and output file names, column
    headers, etc.
    
    (II) Definition of Functions: create some routines to help deal with text
    handling, especially garbled or off-nominal spellings.
    
    (III) Read in Country Map File: creates Python dictionary with country
    code to country name mapping, plus an inverse mapping as well.

    (IV) Read in City Spelling File: creates a large master lookup table with
    around 3 million place names to aid in city name validation.
    
    (V) Read in Airport Spelling File: creates a smaller lookup table with
    names of cities that are large enough to have airports, to aid in 
    lat/lon geocoding (city names in the master spelling lookup file are
    often redundant and can't always be isolated to a single lat/lon point,
    so this gives a way of "guessing" a lat/lon assignment based on city size
    and prominence).
    
    (VI) Process Input File: attempts to validate city names, using resources
    generated in parts II through V.
    
    (VII) Generate Unique Cities File: generates a sorted list of unique input
    cities with their validated output names and dumps to a .csv file for
    user review.
    
Author: Andrew L. Stachyra
Date: 6/29/2013    
"""

import sys
import csv
import re
from operator import itemgetter
import difflib
from math import floor
import datetime

t0 = datetime.datetime.now()

# Expected file names for problem 3
unvalid_file = "Problem 3 Input Data.txt"
countrymap_file = "Problem 3 Input Data - Country Map.txt"
# download.maxmind.com/download/worldcities/worldcitiespop.txt.gz
cityspelling_file = "worldcitiespop.txt" # www.maxmind.com/en/worldcities
# openflights.svn.sourceforge.net/viewvc/openflights/openflights/data/airports.dat
airports_file = "airports.dat" # openflights.org/data.html

# Output file names
processed_file = "processed_cities.csv"
unique_file = "unique_cities.csv"
# Column header names for output files
column_headers = "'InputCity','InputCountryAbbrev','Quality'," + \
                 "'OutputCityASCII','OutputCityAccent'," + \
                 "'OutputCountryName','Latitude','Longitude'\n"

# Make sure that print statements to stdout are immediately flushed to screen
def flprt(msg):
    print(msg)
    sys.stdout.flush()

# When common substrings are found between s and some other string, delete
# the common substring and break s into two halves
def breakstring(s, start, size):
    return [s[0:start], s[start+size:len(s)]]

# Clean up nuisance characters, extra spaces, and any numbers except for
# leading numbers followed by some characters in the alphabet
def cleanup(s):
    cls = s.upper()
    cls = cls.replace('-', ' ')
    cls = cls.replace('.', ' ')
    cls = cls.replace(',', ' ')
    cls = cls.replace('/', ' ')    
    cls = cls.replace('(', '')
    cls = cls.replace(')', '')
    cls = cls.replace('\\', '')
    cls = cls.replace('"', '')
    cls = cls.replace('?', '')
    cls = cls.replace("'S", "S")
    cls = cls.replace("'", " ")
    cls = cls.replace("`", " ")
    leadnum = re.findall('^[0-9]+', cls)
    if len(leadnum) == 0: # Usual case: string does not start with a number
        cls = re.sub('[0-9]+', '', cls)
    else: # Less common: string *does* start with a number
        trail = re.sub('[0-9]+', '', cls)
        # If there are alphabetic characters, use the leading number plus those
        if any([c in trail for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]):
            cls = leadnum[0] + re.sub('[0-9]+', '', cls)
        # If the string consists of *only* numeric characters, null it out
        else: 
            cls = ''
    cls = re.sub(' +', ' ', cls)
    cls = cls.rstrip().lstrip()
    return cls

# Attempt to fix spelling mistakes, if possible
def fixspelling(badcity, candidates):

    if len(badcity) == 0:
        return []
           
    # First part of algorithm: search for precisely matching sub-tokens or
    # pairs of complete city name strings with a large number of letters
    # (> 70%) in common.  Strictly speaking, this part isn't actually
    # technically necessary; one could in principle proceed directly to the
    # substring matching step which is implemented in part 2, however, the
    # difflibs module which is used to implement that part of the overall
    # algorithm is computationally expensive so we attempt to screen away
    # the majority of the grossly unlikely matches first by using this series
    # of two quick albeit somewhat rough matching tests during stage one.
    idx = []
    ctytoken = badcity.split()
    for ii in range(len(candidates)):
        cndtoken = candidates[ii].split()
        matched = False
        # If there are exact matches between any long tokens, add this
        # candidate city to the idx list
        for ij in ctytoken:
            if len(ij) > 2:
                for ik in cndtoken:
                    if len(ik) > 2 and ij == ik:
                        match = True                      
        if matched:
            idx.append(ii)
            continue
 
        # If 70% of letters are in common overall, then add to idx list
        ctyall = re.sub(' +', '', badcity)
        cndall = re.sub(' +', '', candidates[ii])
        if sum([c in cndall for c in set(ctyall)]) >= \
        floor(0.7 * len(set(ctyall+cndall))):
            idx.append(ii)
    
    # Second part of algorithm: search for long matching substrings. Candidate
    # cities which have a lot of matching substrings constitute a likely match
    minfrac = 1 # Optimal value will be as close to zero as possible
    city = []
    cand = []
    totlen = []
    mididx = [] # Index into candidates list of likely matches
    for ii in idx:
        city.append(re.sub(' +', '', badcity)) # Get rid of all spaces
        cand.append(re.sub(' +', '', candidates[ii])) # Get rid of all spaces
        totlen.append(len(city[-1]) + len(cand[-1]))
        # Find matching substring
        sm = difflib.SequenceMatcher(None, city[-1], cand[-1])
        match = sm.find_longest_match(0, len(city[-1]), 0, len(cand[-1]))
        # Throw away matching substring and cleave remainder into two tokens
        city[-1] = breakstring(city[-1], match.a, match.size)
        cand[-1] = breakstring(cand[-1], match.b, match.size) 
        # Loop through the two tokens and look for more matching substrings
        newcty = []
        newcnd = []
        for ij in range(len(city[-1])):    
            sm = difflib.SequenceMatcher(None, city[-1][ij], cand[-1][ij])
            match = sm.find_longest_match(0, len(city[-1][ij]), 0, len(cand[-1][ij]))
            newcty.extend(breakstring(city[-1][ij], match.a, match.size))
            newcnd.extend(breakstring(cand[-1][ij], match.b, match.size))
        # The newcty and newcnd variables at this point should each consist
        # of a list containing four string tokens (with some of them possibly
        # equal to ''; i.e., effectively empty) that have had large matching
        # substrings (if any are found) removed from between them.  Glue
        # these tokens back together to form a single string again.
        city[-1] = ""
        for token in newcty:
            city[-1] = city[-1] + token
        cand[-1] = ""
        for token in newcnd:
            cand[-1] = cand[-1] + token
        # For pairs of city/cand strings that had a lot of matching substrings,
        # this value should be small; hopefully close to zero.  Treat these as
        # a "short list" of good matches
        frac = float(len(city[-1]) + len(cand[-1]))/totlen[-1]
        if frac < minfrac: # New best match; discard all previous best matches
            for ij in range(len(city)-1):
                city.pop(0)
                cand.pop(0)
                totlen.pop(0)
            mididx = []
            mididx.append(ii)
            minfrac = frac
        elif frac == minfrac: # Indistinguishable from previous best match
            mididx.append(ii)
        else: # Poor match; discard
            city.pop(-1)
            cand.pop(-1)
            totlen.pop(-1)
    
    # By the time the algorithm reaches this stage, indices into the candidates
    # list should point to city names which share a large number of common
    # substrings with the badcity.  For example, if badcity = "COPEHNAGEN",
    # then "COPENHAGEN" is likely to have been selected from the candidates
    # list as a possible match, because "COPE" and "AGEN" will have been
    # recognized as common substrings, even though the sequence "HN" is
    # backwards relative to the expeceted "NH".  This brings us around to part
    # three of the algorithm: after pre-selecting a very small number of
    # cities which have large numbers of matching substrings, choose the
    # best candidate by trying to match as many of the leftover letters as
    # possible in any order you can.
    finalidx = []
    minfrac = 1
    for ii in range(len(mididx)):
        sm = difflib.SequenceMatcher(None, city[ii], cand[ii])
        match = sm.find_longest_match(0, len(city[ii]), 0, len(cand[ii]))
        # Find matching substrings and "cross them out" so to speak
        while match.size > 0:
            city[ii] = city[ii].replace(city[ii][match.a:(match.a +\
            match.size)], '')
            cand[ii] = cand[ii].replace(cand[ii][match.b:(match.b +\
            match.size)], '')
            sm = difflib.SequenceMatcher(None, city[ii], cand[ii])
            match = sm.find_longest_match(0, len(city[ii]), 0, len(cand[ii]))
        # This metric measures how successfully the substring matching strategy
        # has been.  A smaller value (as close to zero as possible) indicates
        # a better match
        frac = float(len(city[ii]) + len(cand[ii]))/totlen[ii]
        if frac < minfrac: # New best match
            finalidx = []
            finalidx.append(mididx[ii])
            minfrac = frac
        elif frac == minfrac: # Consistent with previous best match
            finalidx.append(mididx[ii])
            
    return finalidx

# Read in the country code file as a dictionary (first 3 lines), and then
# create an inverse lookup for use with airports_file
with open(countrymap_file, "r") as file:
    alldata = csv.reader(file, delimiter = "|")
    ctrymap = dict(alldata)
    invcmap = {v: k for k, v in ctrymap.items()}
    invcmap['South Korea'] = 'KR'
    invcmap['North Korea'] = 'KP'
    invcmap['Korea'] = 'KP'
    invcmap['Russia'] = 'RU'
    invcmap['Moldova'] = 'MD'
    invcmap['Macedonia'] = 'MK'
    invcmap['Montenegro'] = 'ME'
    invcmap['Iran'] = 'IR'
    invcmap['Syria'] = 'SY'
    invcmap['Palestine'] = 'PS'
    invcmap['West Bank'] = 'PS'
    invcmap['Brunei'] = 'BN'
    invcmap['Ecuador'] = 'EC'
    invcmap['Laos'] = 'LA'
    invcmap['Vietnam'] = 'VN'
    invcmap['Burma'] = 'MM'
    invcmap['East Timor'] = 'TL'
    invcmap['Macau'] = 'MO'
    invcmap['Micronesia'] = 'FM'
    invcmap['Libya'] = 'LY'
    invcmap['Tanzania'] = 'TZ'
    invcmap['Congo (Brazzaville)'] = 'CD'
    invcmap['Congo (Kinshasa)'] = 'CG'
    invcmap['Western Sahara'] = 'EH'
    invcmap['South Sudan'] = 'UNKNOWN'
    invcmap['Guernsey'] = 'GG'
    invcmap['Jersey'] = 'JE'
    invcmap['Isle of Man'] = 'IM'
    invcmap['Falkland Islands'] = 'FK'
    invcmap['Virgin Islands'] = 'VI'
    invcmap['British Virgin Islands'] = 'VG'
    invcmap['Svalbard'] = 'SJ'
    invcmap['Wake Island'] = 'UM'
    invcmap['Christmas Island'] = 'CX'
    invcmap['South Georgia and the Islands'] = 'GS'
    invcmap['Midway Islands'] = 'US'
    invcmap['British Indian Ocean Territory'] = 'GB'
    invcmap['Johnston Atoll'] = 'UNKNOWN'
    invcmap['Antarctica'] = 'MULTIPLE'
    flprt("Country code directory is successfully loaded...")

# Read in the city spelling / master geocode file as a list within a
# dictionary which is keyed by country
flprt("Loading third party city spelling dictionary, " + 
      "please wait about two minutes...")
ctspell = {}
with open(cityspelling_file, "r") as file:
    alldata = csv.reader(file, delimiter = ",")
    alldata.next() # Skip column headers in first line
    for ctry, city, acccity, reg, pop, lat, lon in alldata:
        ctry = ctry.upper() # Convert to upper case to match other files
        city = city.upper()
        if ctry in ctspell.keys(): # Usual case: append another city
            ctspell[ctry].append([city, cleanup(city), acccity, float(lat),
                                  float(lon)])
        else: # First time a new country is encountered
            ctspell[ctry] = [[city, cleanup(city), acccity, float(lat),
                              float(lon)]]
    flprt("Third party city spelling directory is successfully loaded; " +
          "{0} elapsed".format(datetime.datetime.now()-t0))

# Read in the airport supplementary geocode file as a list within a
# dictionary which is keyed by country and city
airports = {}
with open(airports_file, "r") as file:
    alldata = csv.reader(file, delimiter = ',', quotechar = '"')
    for apid, name, city, country, iatafaa, icao, lat, lon, alt, tz,\
    dst in alldata:
        # Skip pre-averaged latitiude/longitude values for about a dozen
        # major cities; we'll compute this ourselves for all of them later,
        # not just a tiny subset
        if name == "All Airports":
            pass
        # Check whether the country name appears in the inverse country map
        if country in invcmap.keys():
            ctry = invcmap[country]
        else:
            ctry = 'NO KEY'
        # Get rid of nuisance characters
        city = cleanup(city)
        if ctry in airports.keys():
            # New airport for a city already previously encountered
            if city in airports[ctry].keys():
                airports[ctry][city].append([float(lat), float(lon)])
            # New city encountered
            else:
                airports[ctry][city] = [[float(lat), float(lon)]]
        # New country encountered
        else:
            airports[ctry] = {}
            airports[ctry][city] = [[float(lat), float(lon)]]
# For cities with multiple ports, take city location as average of all
# port latitudes and longitudes
for ii in airports.keys():
    for ij in airports[ii].keys():
        lat = [airports[ii][ij][ik][0] for ik in range(len(airports[ii][ij]))]
        lon = [airports[ii][ij][ik][1] for ik in range(len(airports[ii][ij]))]   
        airports[ii][ij] = [sum(lat)/len(lat), sum(lon)/len(lon)]
flprt("Third party airports directory is successfully loaded...")

flprt("Data validation in process, please wait; " +
      "periodic progress updates will be provided every 3 minutes or so...")
prevseen = {}
unqlst = []
s = "'{0}','{1}',{2},'{3}','{4}','{5}',{6},{7}\n" # Output format string
# Read in the unvalidated file line by line and attempt to correct it
with open(unvalid_file, "r") as infile, open(processed_file, "w") as outfile:
    # Print column headers to output file
    outfile.writelines(column_headers)               
    alldata = csv.reader(infile, delimiter = "|", quotechar="'")
    alldata.next() # Skip column headers in first line
    ii = 1 # Line counter (this seems to be only way to do it in Python)
    for city, ctry in alldata:
        matched = False
        # Skip time-consuming search, if we've encounterd this city before
        if ctry in prevseen.keys(): # Country has previously been encountered
            if city in prevseen[ctry].keys(): # City was previously encountered
                outfile.writelines(prevseen[ctry][city])
                if not ii%10000: # Send periodic status update to stdout
                    flprt("    {0} lines finished; ".format(ii) +
                          "{0} elapsed".format(datetime.datetime.now()-t0))
                ii = ii + 1
                continue
        else: # New country encountered
            prevseen[ctry] = {}
        if ctry in ctspell.keys(): # Country code is recognized
            for ij in range(2):
                if not matched:
                    if ij == 0:
                        # Use the raw city name on the first attempt at a match
                        usecity = city
                    else:
                        # If that doesn't produce a match, use a slightly
                        # cleaned up version of the city name on the 2nd pass
                        usecity = cleanup(city)
                    # Find all matches to city within this country
                    idx = [ik for ik in range(len(ctspell[ctry])) if
                           ctspell[ctry][ik][ij] == usecity]
                    if len(idx) == 1: # Case 1 or 4: exactly one match
                        v = [city, ctry, (3*ij + 1), ctspell[ctry][idx[0]][0],
                             ctspell[ctry][idx[0]][2], ctrymap[ctry],
                             ctspell[ctry][idx[0]][3], ctspell[ctry][idx[0]][4]]
                        matched = True
                    elif len(idx) > 1: # Case 2 & 3 or 5 & 6, multiple matches
                        # Attempt to select best lat and lon as the one which
                        # belongs to the match that has an airport
                        if usecity in airports[ctry].keys(): 
                            # Case 2 or 5: found airport
                            v = [city, ctry, (3*ij + 2),
                                 ctspell[ctry][idx[0]][0],
                                 ctspell[ctry][idx[0]][2], ctrymap[ctry],
                                 airports[ctry][usecity][0],
                                 airports[ctry][usecity][1]]
                        else:
                            # Case 3 or 6: multiple matches (presumably from
                            # different states, provinces, or regions) but no
                            # airport
                            v = [city, ctry, (3*ij + 3),
                                 ctspell[ctry][idx[0]][0],
                                 ctspell[ctry][idx[0]][2], ctrymap[ctry],
                                 '', '']
                        matched = True
            if not matched:
                # Final attempt: search for looser matches and treat those
                # cases as spelling errors in need of auto-correction
                candidates = [ctspell[ctry][ik][1] for ik in 
                              range(len(ctspell[ctry]))]
                idx = fixspelling(cleanup(city), candidates)
                if len(idx) > 0:
                    # Case 7: best guess as to spelling
                    v = [city, ctry, 7, ctspell[ctry][idx[0]][0],
                         ctspell[ctry][idx[0]][2], ctrymap[ctry],
                         ctspell[ctry][idx[0]][3], ctspell[ctry][idx[0]][4]]
                else:
                    # Case 8: city not recognized
                    v = [city, ctry, 8, '', '', ctrymap[ctry], '', '']
        else: # Case 9: country code is not recognized
            v = [city, ctry, 9, '', '', '', '', '']
        # Add this city to the dictionary of previously seen cities, and to the
        # list of unique cities (basically same underlying data, but different
        # formating) and also write it to the output file
        prevseen[ctry][city] = s.format(v[0], v[1], v[2], v[3], v[4], v[5],
                                        v[6], v[7])
        outfile.writelines(prevseen[ctry][city])
        unqlst.append(v)
        if not ii%10000: # Send periodic status update to stdout
            flprt("    {0} lines finished; ".format(ii) +
                  "{0} elapsed".format(datetime.datetime.now()-t0))
        ii = ii + 1
    flprt("Data validation is finished; " +
          "{0} elapsed!".format(datetime.datetime.now()-t0))

flprt("Dumping unique cities list to output file; please wait...")
# Sort the list of unique cities by quality indicator first, then
# alphabetically by country, and finally alphabetically by city
unqlst = sorted(unqlst, key=itemgetter(2, 1, 0))
with open(unique_file, "w") as outfile:
    # Print column headers to output file
    outfile.writelines(column_headers)
    # Print data to the output file
    writer = csv.writer(outfile, quotechar = "'", quoting=csv.QUOTE_NONNUMERIC,
                        lineterminator='\n')
    writer.writerows(unqlst)
flprt("All finished!  " +
      "Total elapsed time: {0}".format(datetime.datetime.now()-t0))