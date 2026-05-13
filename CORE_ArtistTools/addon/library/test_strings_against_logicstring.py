# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

#!/usr/bin/env python3
# test a string or list of strings against search terms and logic operators


def testStringsAgainstLogicString(userstrings, userlogicstring):
    """This function takes two inputs. The first is a string or list of strings
    to be checked. The second is a single string with search terms and C++ style logical operators.
    The function returns a list of string values that match the search pattern provided.
    """
    # this list stores the test pattern for each test
    resultlist = []  # list of strings found valid against tests
    testlist = []
    # these are lists of lists. Use test number as index to get proper list
    # notlists[0], for example, contains all terms (for first test) that must NOT be found in
    # search string to return a TRUE result
    notlists = []
    andlists = []

    ###### SETUP. Convert userlogicstring into simple lists that can be tested ######
    # split logicstring into multiple tests by OR operator
    testlist = userlogicstring.lower().split("||")

    # strip leading and trailing spaces
    for i, t in enumerate(testlist):
        testlist[i] = t.strip()

    # Find NOTs. Any item after a NOT goes into NOTlist
    splitbynots = []
    # splitbyspaces = []
    # assemblenots = []
    # assembleands = []
    startnum = 0

    for test in testlist:
        splitbynots = test.split("!")
        for sn, st in enumerate(splitbynots):
            splitbynots[sn] = st.strip()

        # remove nots to their own list leaving only ANDs behind
        # determine whether first item was a not and set offset
        startnum = 0 if test[0] == "!" else 1
        # working lists to assemble information
        assemblenots = []
        assembleands = []
        splitbyspaces = []

        for n in range(len(splitbynots)):
            splitbyspaces = splitbynots[n].split(" ")
            # capture the first item whether AND or NOT
            if n >= startnum:
                assemblenots.append(splitbyspaces[0])
                splitbyspaces.pop(0)
            else:
                assembleands.append(splitbyspaces[0])

        assembleands.extend([x for x in splitbyspaces if x != "&&" and x not in assembleands])
        notlists.append(assemblenots)
        andlists.append(assembleands)

    ###### Prepare user test string ######
    if isinstance(userstrings, list):
        userstrings = list(userstrings)

    ###### Test ######
    for st in userstrings:
        st = st.lower()
        test_result = True  # noqa E712
        for c, test in enumerate(testlist):
            test_result = True  # noqa E712

            for andterm in andlists[c]:
                if andterm not in st:
                    test_result = False  # noqa E712
            for notterm in notlists[c]:
                if notterm in st:
                    test_result = False  # noqa E712
            if test_result:
                break  # we can skip any other tests for this string
        # append current string if valid
        if test_result:
            resultlist.append(st)

    return resultlist


if __name__ == "__main__":

    ################################################################
    # ----------  test  ----------
    ################################################################
    testlist = ["pinkbublegum", "pewpew", "beetle", "retro__metal__pop"]
    resultlist = testStringsAgainstLogicString(testlist, "gum && ink || __")

    print("result:", resultlist)
