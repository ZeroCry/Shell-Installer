#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# Cinnamon Installer
#
# Authors: Lester Carballo Pérez <lestcape@gmail.com>
#
#
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation; either version 2 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
#  USA

from __future__ import print_function

import sys, os, pwd, grp, stat

def get_user():
    if "SUDO_USER" in os.environ:
        return os.environ["SUDO_USER"]
    elif "PKEXEC_UID" in os.environ:
        return pwd.getpwuid(int(os.environ["PKEXEC_UID"])).pw_name
    else:
        return pwd.getpwuid(os.getuid()).pw_name

def get_home(user=None):
    if user:
        return os.path.expanduser("~" + user)
    else:
        return os.path.expanduser("~" + get_user())

def get_standar_mode():
    return 0o755 #stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH | stat.S_IEXEC

def set_mode(path, mode):
    if (os.path.exists(path)) and (stat.S_IMODE(os.stat(path).st_mode) != mode):
        os.chmod(path, mode)

def get_user_id(user):
    return pwd.getpwnam(user).pw_uid

def get_group_id(group):
    return grp.getgrnam(group).gr_gid

def set_propietary_id(path, uid, gid):
    if (os.path.exists(path)) and (os.geteuid() == 0):
        st = os.stat(path)
        if (st.st_uid != uid) or (st.st_gid != gid):
            os.chown(path, uid, gid)

def set_propietary(path, user):
    if (os.path.exists(path)) and (os.geteuid() == 0):
        uid = get_user_id(user)
        gid = get_group_id(user)
        st = os.stat(path)
        if (st.st_uid != uid) or (st.st_gid != gid):
            os.chown(path, uid, gid)

def rec_mkdir(path, mode=None, prop=None):
    if os.path.exists(path):
        return

    rec_mkdir(os.path.split(path)[0], mode)

    if os.path.exists(path):
        return
    if mode:
        os.mkdir(path, mode)
    else:
        os.mkdir(path)

    if prop:
        set_propietary_id(path, prop[0], prop[1])

def removeEmptyFolders(path):
    if not os.path.isdir(path):
        return

    # remove empty subfolders
    files = os.listdir(path)
    if len(files):
        for f in files:
            fullpath = os.path.join(path, f)
            if os.path.isdir(fullpath):
                removeEmptyFolders(fullpath)

    # if folder empty, delete it
    files = os.listdir(path)
    if len(files) == 0:
        print("Removing empty folder:" + path)
        os.rmdir(path)
