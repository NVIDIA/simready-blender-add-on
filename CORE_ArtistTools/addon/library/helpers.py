# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import re
import subprocess


def combine_lists(lst):
    st = ""
    for each in lst:
        st += each
    return st


def clean_text(txt):
    st = txt.strip().lower()
    stlst = re.findall(r"[a-z0-9_-]+", st)

    # st = combine_lists(stlst)
    st = ""
    for each in stlst:
        st += each

    result1 = re.search(r"[_]{2}", st)

    result2 = re.search(r"[-]{2}", st)

    if result1 or result2:
        st = st.replace("-", "")
        st = st.replace("_", "")

    return st


def copy_string(txt):
    print("txt", txt)
    subprocess.run("clip", universal_newlines=True, input=txt)


def check_user_sel(objs, report=True, empties=True, geo=True):
    if objs and empties:
        return True
    else:
        return False
