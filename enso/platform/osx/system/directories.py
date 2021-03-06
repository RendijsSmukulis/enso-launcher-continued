# Copyright (c) 2008, Humanized, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    1. Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#
#    2. Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
#    3. Neither the name of Enso nor the names of its contributors may
#       be used to endorse or promote products derived from this
#       software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY Humanized, Inc. ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL Humanized, Inc. BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


# ----------------------------------------------------------------------------
#
#   enso.system
#
# ----------------------------------------------------------------------------

"""
    This module provides access to important end-user system folders.
"""

# ----------------------------------------------------------------------------
# Imports
# ----------------------------------------------------------------------------

import os


# ----------------------------------------------------------------------------
# Module variables
# ----------------------------------------------------------------------------


# ----------------------------------------------------------------------------
# Functions
# ----------------------------------------------------------------------------

def get_user_home_dir():
    return os.path.expanduser("~")

def get_enso_local_conf_dir():
    return os.path.join(get_user_home_dir(), "Library", "Application Support", "enso")

def get_enso_cache_dir():
    return os.path.join(get_user_home_dir(), "Library", "Caches", "enso")
    
    
# Enso special folder - Local data storage
SPECIALFOLDER_ENSOLOCAL = get_enso_local_conf_dir()

# Enso special folder - Enso's Learn As Open Commands
SPECIALFOLDER_ENSOLEARNAS = os.path.join(
    get_enso_local_conf_dir(), "learned_shortcuts"
    )

# Enso special folder - Enso's script commands
SPECIALFOLDER_ENSOCOMMANDS = os.path.join(
    get_enso_local_conf_dir(), "commands"
    )
    
