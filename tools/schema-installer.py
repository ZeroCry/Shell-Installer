#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#
# Authors: Lester Carballo Pérez <lestcape@gmail.com>
#
# Froked from Cinnamon code at:
# https://github.com/linuxmint/Cinnamon
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

#from __future__ import print_function

import os, sys, shutil

def install(pos_start, pos_end, length_arg):
    if pos_start != -1:
        if pos_end == -1:
            pos_end = length_arg
        if pos_start < pos_end:
            for i in range(pos_start, pos_end):
                if os.path.isfile(sys.argv[i]):
                    shutil.copyfile(sys.argv[i], "/usr/share/glib-2.0/schemas/%s" % os.path.basename(sys.argv[i]))
            os.system("glib-compile-schemas /usr/share/glib-2.0/schemas/")

def remove(pos_start, pos_end, length_arg):
    if pos_start != -1:
        if pos_end == -1:
            pos_end = length_arg
        if pos_start < pos_end:
            for i in range(pos_start, pos_end):
                if os.path.isfile(sys.argv[i]):
                    os.remove("/usr/share/glib-2.0/schemas/%s" % (sys.argv[1]))      
            os.system("glib-compile-schemas /usr/share/glib-2.0/schemas/")

if __name__ == "__main__":
    length_arg = len(sys.argv)
    pos_install = -1
    pos_remove = -1
    if length_arg > 1:
        for i in range(1, len(sys.argv)):
            if sys.argv[i] == "-i":
                pos_install = i
            if sys.argv[i] == "-i":
                pos_remove = i
        install(pos_install, pos_remove, length_arg)
        remove(pos_remove, pos_install, length_arg)
