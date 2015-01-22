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

import os, sys

ABS_PATH = os.path.abspath(__file__)
DIR_PATH = os.path.dirname(os.path.dirname(ABS_PATH)) + "/"

import config

import gettext, locale
LOCALE_PATH = DIR_PATH + "locale"
DOMAIN = "cinnamon-installer"
locale.bindtextdomain(DOMAIN , LOCALE_PATH)
locale.bind_textdomain_codeset(DOMAIN , "UTF-8")
gettext.bindtextdomain(DOMAIN, LOCALE_PATH)
gettext.bind_textdomain_codeset(DOMAIN , "UTF-8")
gettext.textdomain(DOMAIN)
_ = gettext.gettext

def format_size(size):
    KiB_size = size / 1024
    if KiB_size < 1000:
        size_string = _("%.1f KiB") % (KiB_size)
        return size_string
    else:
        size_string = _("%.2f MiB") % (KiB_size / 1024)
        return size_string

def format_pkg_name(name):
    unwanted = [">","<","="]
    for i in unwanted:
        index = name.find(i)
        if index != -1:
            name = name[0:index]
    return name

PID_FILE = "/tmp/installer.pid"
LOCK_FILE = os.path.join(config.pacman_conf.options["DBPath"], "db.lck")

def lock_file_exists():
    return os.path.isfile(LOCK_FILE)

def pid_file_exists():
    return os.path.isfile(PID_FILE)

def write_pid_file():
    with open(PID_FILE, "w") as _file:
        _file.write(str(os.getpid()))

def rm_pid_file():
    if os.path.isfile(PID_FILE):
        os.remove(PID_FILE)

def rm_lock_file():
    if os.path.isfile(LOCK_FILE):
        os.remove(LOCK_FILE)

import time

def write_log_file(string):
    with open("/var/log/Cinnamon-Installer.log", "a") as logfile:
        logfile.write(time.strftime("[%Y-%m-%d %H:%M]") + " {}\n".format(string))
