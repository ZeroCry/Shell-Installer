#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# Cinnamon Installer
#
# Authors: Lester Carballo Pérez <lestcape@gmail.com>
#
# Original version from: Guillaume Benoit <guillaume@manjaro.org>
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

import os, tarfile, sys, Namcap, urllib, requests

ABS_PATH = os.path.abspath(__file__)
DIR_PATH = os.path.dirname(os.path.dirname(ABS_PATH)) + "/"

# i18n
import gettext, locale
LOCALE_PATH = DIR_PATH + "locale"
DOMAIN = "cinnamon-installer"
locale.bindtextdomain(DOMAIN , LOCALE_PATH)
locale.bind_textdomain_codeset(DOMAIN , "UTF-8")
gettext.bindtextdomain(DOMAIN, LOCALE_PATH)
gettext.bind_textdomain_codeset(DOMAIN , "UTF-8")
gettext.textdomain(DOMAIN)
_ = gettext.gettext

AUR_URL = "http://aur.archlinux.org"
RPC_URL = AUR_URL + "/rpc.php"
SRC_PKG_PATH = "/tmp/installer"

class AURPkg():
    def __init__(self, pkginfo):
        self.db = FakeDB()
        self.isize = None
        self.size = None
        self.download_size = 0
        keys = pkginfo.keys()
        if "URL" in keys:
            self.url = pkginfo["URL"]
        if "URLPath" in keys:
            self.tarpath = pkginfo["URLPath"]
        if "name" in keys:
            self.name = pkginfo["name"]
        else:
            self.name = pkginfo["Name"]
        if "version" in keys:
            self.version = pkginfo["version"]
        else:
            self.version = pkginfo["Version"]
        if "desc" in keys:
            self.desc = pkginfo["desc"]
        else:
            self.desc = pkginfo["Description"]
        if "licenses" in keys:
            self.licenses = pkginfo["licenses"]
        elif "License" in keys:
            self.licenses = [pkginfo["License"]]
        else:
            self.licenses = []
        if "source" in keys:
            self.source = pkginfo["source"]
        else:
            self.source = []
        if "orig_depends" in keys:
            self.depends = pkginfo["orig_depends"]
        else:
            self.depends = []
        if "orig_optdepends" in keys:
            self.optdepends = pkginfo["orig_optdepends"]
        else:
            self.optdepends = []
        #~ if "orig_provides" in keys:
            #~ self.provides = pkginfo["orig_provides"]
        #~ else:
            #~ self.provides = []
        if "orig_makedepends" in keys:
            self.makedepends = pkginfo["orig_makedepends"]
        else:
            self.makedepends = []
        #~ if "replaces" in keys:
            #~ self.replaces = pkginfo["replaces"]
        #~ else:
            #~ self.replaces = []
        #~ if "conflicts" in keys:
            #~ self.conflicts = pkginfo["conflicts"]
        #~ else:
            #~ self.conflicts = []
        #~ if "groups" in keys:
            #~ self.groups = pkginfo["groups"]
        #~ else:
            #~ self.groups = []

    def __repr__(self):
        return "{}-{}".format(self.name, self.version)

    def __eq__(self, other):
        if hasattr(other, "name") and hasattr(other, "version"):
            if self.name == other.name and self.version == other.version:
                return True
        return False

class FakeDB():
    def __init__(self):
        self.name = "AUR"

def get_pkgs(pkgbuild_path):
    pkgbuild_info = Namcap.package.load_from_pkgbuild(pkgbuild_path)
    pkgs = []
    if pkgbuild_info.is_split:
        for infos in pkgbuild_info.subpackages:
            pkg = AURPkg(infos)
            pkgs.append(pkg)
    else:
        pkg = AURPkg(pkgbuild_info)
        pkgs.append(pkg)
    return pkgs

def search(args):
    spec = {"type":"search", "arg":args}
    try:
        r = requests.get(RPC_URL, params = spec)
        r.raise_for_status()
    except Exception:
        e = sys.exc_info()[1]
        print(str(e))
        return []
    else:
        results_dict = r.json()
        results = results_dict["results"]
        pkgs = []
        if results:
            for result in results:
                pkgs.append(AURPkg(result))
        return pkgs

def info(pkgname):
    spec = {"type":"info", "arg":pkgname}
    try:
        r = requests.get(RPC_URL, params = spec)
        r.raise_for_status()
    except Exception:
        e = sys.exc_info()[1]
        print(str(e))
        return []
    else:
        results_dict = r.json()
        if results_dict["type"] == "error":
            print("failed to get infos about {} from AUR".format(pkgname))
            return None
        else:
            result = results_dict["results"]
            if result:
                pkg = AURPkg(result)
                return pkg
            else:
                print("failed to get infos about {} from AUR".format(pkgname))
                return None

def multiinfo(pkgnames):
    spec = {"type":"multiinfo", "arg[]":pkgnames}
    try:
        r = requests.get(RPC_URL, params = spec)
        r.raise_for_status()
    except Exception:
        e = sys.exc_info()[1]
        print(str(e))
        return []
    else:
        results_dict = r.json()
        if results_dict["type"] == "error":
            print("failed to get infos about {} from AUR".format(pkgnames))
            return []
        else:
            pkgs = []
            results = results_dict["results"]
            if results:
                for result in results:
                    pkgs.append(AURPkg(result))
            else:
                print("failed to get infos about {} from AUR".format(pkgnames))
            return pkgs

def get_extract_tarball(pkg):
    try:
        r = requests.get(AUR_URL + pkg.tarpath)
        r.raise_for_status()
    except Exception:
        e = sys.exc_info()[1]
        print(str(e))
        return None
    else:
        if not os.path.exists(SRC_PKG_PATH):
            os.makedirs(SRC_PKG_PATH)
        full_tarpath = os.path.join(SRC_PKG_PATH, os.path.basename(pkg.tarpath))
        try:
            with open(full_tarpath, "wb") as f:
                f.write(r.content)
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))
            return None
        else:
            try:
                tar = tarfile.open(full_tarpath)
                tar.extractall(path = SRC_PKG_PATH)
            except Exception:
                e = sys.exc_info()[1]
                print(str(e))
                return None
            else:
                return os.path.join(SRC_PKG_PATH, get_name(pkg))

def get_name(pkg):
    # the splitext is to remove the original extension
    # which is tar.foo - currently foo is gz, but this can change
    # the rstrip is to remove the trailing tar part.
    if pkg.name not in pkg.tarpath:
        return os.path.splitext(os.path.basename(pkg.tarpath))[0].rstrip(".tar")
    return pkg.name
