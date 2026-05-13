# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

#!/usr/bin/env python3
# tools to search manifest

import csv
import os
from difflib import SequenceMatcher as SM


def CORE_CheckAssetNameAgainstManifest(
    csv_filepath: str, assetname: str, searchterms: str, column: str = "", fuzzy: float = 0.8, cat: int = 0
) -> list[str]:
    """
    Effortlessly verify that an asset name is unique and get context on similarly-named items
    csv_file: reader for csv file

    csv_filepath: filepath to csv file

    assetname: string name for asset

    searchterms: comma delimited string of search terms

    column: column of csv file to read, can specify a column number or the name of the column. default is 0.

    fuzzy: float value, 0 to 1, representing match ratio at which to report a match. default is 0.8.

    cat: how many directories to concatenate to determine asset name. For vehicles this is 3 which
        combines /make/model/year directories to get vehicle name
        default value for this is 0 which skips concatentation and looks at the actual asset name instead of
        deriving the name from directories.
    """

    # clean searchlist
    searchlist = ""
    if len(searchterms) > 0:
        searchlist = searchterms.split(",")
        searchlist = [x.strip(" ") for x in searchlist]

    csv_filepath = os.path.normpath(csv_filepath)
    csv_file = csv.reader(open(csv_filepath, "r"), delimiter=",")

    rslt_asset = []
    rslt_fuzzy = []
    rslt_search = []
    result_str_list = []
    fields = next(csv_file)

    # convert list to dictionary
    # determine column number to read
    fields_dict = {fields[i]: i for i in range(0, len(fields), 1)}
    if column:
        if isinstance(column, int):
            index = column
        else:
            index = fields_dict.get(column)
    else:
        index = 0

    # loop through csv and search terms
    for row in csv_file:

        val = row[index]
        part = val.split("/")

        # find name from csv file
        if cat and cat < len(part):
            temparray = []
            for c in reversed(range(cat)):
                temparray.append(part[(-(c + 2))])
            foundasset = "_".join(temparray)
        else:
            foundasset = part[-1].split(".")[0]

        # print( "foundasset:",foundasset)

        # build asset list (exact matches)
        if (assetname) == foundasset:
            if val not in rslt_asset:
                rslt_asset.append(val)

        # build fuzzy list
        if fuzzy > 0.01:
            fuz = SM(None, (assetname), foundasset).ratio()
            if fuz > fuzzy:
                if val not in rslt_asset:
                    rslt_fuzzy.append(val)

        # build list of items including search terms
        if searchlist:
            for each in searchlist:
                if each in foundasset:
                    if val not in rslt_search:
                        rslt_search.append(val)

    # assetname results
    print(("\nASSET NAME: " + assetname))
    result_str_list.append("ASSET NAME: " + assetname)

    if rslt_asset:
        for line in rslt_asset:

            print(line)
            result_str_list.append(line)
    else:
        print(("...not found in manifest"))
        result_str_list.append("...not found in manifest")

    # fuzzy results
    if fuzzy > 0.01:
        if rslt_fuzzy:
            print("\nSIMILAR ITEMS: ")
            result_str_list.extend((" ", "SIMILAR ITEMS: "))

            for line in rslt_fuzzy:

                print(line)
                result_str_list.append(line)

    # search term results

    if searchlist:
        print("\nSEARCH TERMS: ")
        result_str_list.extend((" ", "SEARCH TERMS: "))

        print(searchlist)
        result_str_list.append(str(searchlist))

        if rslt_search:
            for line in rslt_search:

                print(line)
                result_str_list.append(line)
        else:
            print(("...none found"))
            result_str_list.append("...none found")

    return result_str_list  # ("Finished")


if __name__ == "__main__":

    # -------------------
    # EDIT VARIABLES HERE
    # -------------------
    csv_filepath = "C:/file.csv"
    assetname = "land_rover_defender_2022"
    searchterms = ()  # put search terms in quotes and separate with commas i.e. searchterms =("clowns","cars")
    vehicles = (
        True  # this will find vehicle names using their folder structure instead of the filename which will be generic
    )
    # -------------------
    # -------------------

    cat = 0
    if vehicles == True:  # noqa E721
        cat = 3
        print("...\n")
        CORE_CheckAssetNameAgainstManifest(csv_filepath, assetname, searchterms, "_Path", 0.8, cat)
        print("\n...")
