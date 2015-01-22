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

from gi.repository import GObject, Gio, GLib, Polkit
import re, os, sys, subprocess
from time import sleep

import pyalpm
from multiprocessing import Process
import threading

ABS_PATH = os.path.abspath(__file__)
DIR_PATH = os.path.dirname(os.path.dirname(ABS_PATH)) + "/"

import config, common, aur
import urllib, requests

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

def format_error(data):
    errstr = data[0].strip("\n")
    errno = data[1]
    detail = data[2]
    if detail:
        # detail is a list of "\n" terminated strings
        return "{}:\n".format(errstr) + "".join(i for i in detail)
    else:
        return errstr

class InstallerModule():
    def __init__(self):
        self.validTypes = ["package"]
        self.service = None

    def priority_for_collection(self, collect_type):
        if collect_type in self.validTypes:
            return 1
        return 0
    
    def get_service(self):
        if self.service is None:
            self.service = InstallerService()
        self.service.set_parent_module(self)
        return self.service

class InstallerService(GObject.GObject):
    __gsignals__ = {
        "EmitTransactionDone": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_STRING,)),
        "EmitTransactionError": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING,)),
        "EmitAvailableUpdates": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_BOOLEAN, GObject.TYPE_BOOLEAN,)),
        "EmitStatus": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING,)),
        "EmitRole": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_STRING,)),
        "EmitNeedDetails": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_BOOLEAN,)),
        "EmitIcon": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_STRING,)),
        "EmitTarget": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_STRING,)),
        "EmitPercent": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_FLOAT,)),
        "EmitDownloadPercentChild":(GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_FLOAT, GObject.TYPE_STRING,)),
        "EmitDownloadChildStart": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_BOOLEAN,)),
        "EmitLogError": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_STRING,)),
        "EmitLogWarning": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_STRING,)),
        "EmitTransactionStart": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_STRING,)),
        "EmitReloadConfig": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_STRING,)),
        "EmitTransactionConfirmation": (GObject.SIGNAL_RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
        "EmitTransactionCancellable": (GObject.SIGNAL_RUN_LAST, None, (GObject.TYPE_BOOLEAN,)),
        "EmitTerminalAttached": (GObject.SIGNAL_RUN_LAST, None, (GObject.TYPE_BOOLEAN,)),
        "EmitConflictFile": (GObject.SIGNAL_RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING,)),
        "EmitChooseProvider": (GObject.SIGNAL_RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
        "EmitMediumRequired": (GObject.SIGNAL_RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_STRING))
    }

    def __init__(self):
        GObject.GObject.__init__(self)
        self.t = None
        self.task = None
        self.error = ""
        self.warning = ""
        self.providers = []
        self.previous_status = ""
        self.previous_role = ""
        self.previous_icon = ""
        self.previous_target = ""
        self.previous_percent = 0
        self.total_size = 0
        self.already_transferred = 0
        self.aur_transferred = 0
        #self.local_packages = set()
        self.aur_updates_checked = False
        self.aur_updates_pkgs = []
        self.localdb = None
        self.syncdbs = None
        self.cancel_download = False
        self._get_handle()
        self.client_response = True
        self.lock_trans = threading.Lock()
        self.client_condition = threading.Condition()
        self.provider_data = None
        self.inUpdate = False
        self.build_proc = None
        self.details = False
        self.available_updates = (False, [])
        self.to_add = set()
        self.to_remove = set()
        self.to_update = set()
        self.to_load = set()
        self.to_mark_as_dep = set()
        self.make_depends = set()
        self.build_depends = set()
        self.to_build = []
        self.base_devel = ("autoconf", "automake", "binutils", "bison", "fakeroot", 
                           "file", "findutils", "flex", "gawk", "gcc", "gettext", 
                           "grep", "groff", "gzip", "libtool", "m4", "make", "patch", 
                           "pkg-config", "sed", "sudo", "texinfo", "util-linux", "which")
        self.colors_regexp = re.compile("\\033\[(\d;)?\d*m")
        #mycode
        self.lastedSearch = {}
        self.status_local_dir = Gio.file_new_for_path(self.handle.dbpath + "local")
        self.status_sync_dir = Gio.file_new_for_path(self.handle.dbpath + "sync")
        self.monitor_local = self.status_local_dir.monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self.monitor_sync = self.status_sync_dir.monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self.module = None
        if self.monitor_local:
            self.monitor_local.connect("changed", self._changed)
        if self.monitor_sync:
            self.monitor_sync.connect("changed", self._changed)
        self._init_configuration()

    def _changed(self, monitor, file1, file2, evt_type):
        self._get_handle()
        self.lastedSearch = {}
        pass

    def need_root_access(self):
        return True

    def have_terminal(self):
        return False

    def set_terminal(self, terminal):
        pass

    def is_service_idle(self):
        return not self.lock_trans.locked()

    def load_cache(self, forced=False, async=False, collect_type=None):
        pass

    def have_cache(self, collect_type=None):
        return True

    def set_parent_module(self, module):
        self.module = module

    def get_parent_module(self):
        return self.module

    def _init_configuration(self):
        self.config = {}
        self.config["EnableAUR"] = config.enable_aur
        self.config["RemoveUnrequiredDeps"] = config.recurse
        self.config["RefreshPeriod"] = config.refresh_period

    def get_cache_folder(self, collect_type=None):
        return ""

    def search_files(self, path, loop, result):
        '''Return the package that ships the given file.
        Return None if no package ships it.
        '''
        local_packages = []
        result.append(local_packages)
        try:
            print(path)
            if path is not None:
                # resolve symlinks in directories
                (dir, name) = os.path.split(path)
                resolved_dir = os.path.realpath(dir)
                if os.path.isdir(resolved_dir):
                    file = os.path.join(resolved_dir, name)

                if self._likely_packaged(path):
                    local_packages.append(self._get_file_package(path))
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        sleep(0.1)
        loop.quit()

    def get_all_local_packages(self, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            syncdbs = self.handle.get_syncdbs()
            localdb = self.handle.get_localdb()
            for repo in syncdbs:
                for pkg in repo.pkgcache:
                    if(not pkg.name in local_packages):
                        if localdb.get_pkg(pkg.name):
                            local_packages.append(pkg.name)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        sleep(0.1)
        loop.quit()

    def get_all_remote_packages(self, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            syncdbs = self.handle.get_syncdbs()
            localdb = self.handle.get_localdb()
            for repo in syncdbs:
                for pkg in repo.pkgcache:
                    if(not pkg.name in local_packages):
                        if not localdb.get_pkg(pkg.name):
                            local_packages.append(pkg.name)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        sleep(0.1)
        loop.quit()

    def get_package_info(self, loop, result, pkg_id, collect_type):
        loop.quit()

    def get_local_packages(self, packages, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            sync_pkg = None
            for pkg in self.localdb.pkgcache:
                for db in self.syncdbs:
                    sync_pkg = db.get_pkg(pkg.name)
                    if sync_pkg:
                        break
                if not sync_pkg:
                    local_packages.append(pkg.name)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        sleep(0.1)
        loop.quit()

    def get_remote_packages(self, packages, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            syncdbs = self.handle.get_syncdbs()
            localdb = self.handle.get_localdb()
            for repo in syncdbs:
                for pkg in repo.pkgcache:
                    if(packages == pkg.name) and (not pkg.name in local_packages):
                        if not localdb.get_pkg(pkg.name):
                                local_packages.append(pkg.name)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        sleep(0.1)
        loop.quit()

    def get_local_search(self, pattern, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            syncdbs = self.handle.get_syncdbs()
            localdb = self.handle.get_localdb()
            for repo in syncdbs:
                for pkg in repo.pkgcache:
                    if((pattern in pkg.name) and (not pkg.name in local_packages)):
                        if localdb.get_pkg(pkg.name):
                            local_packages.append(pkg.name)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        sleep(0.1)
        loop.quit()
                    
    def get_remote_search(self, pattern, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            matchWordsPattern = pattern.split(",")
            quickList = self._get_quick_search(pattern)
            if(quickList):
                for pkgName in quickList:
                    if(self._is_matching(matchWordsPattern, pkgName)):
                        local_packages.append(pkgName)
            else:
                syncdbs = self.handle.get_syncdbs()
                localdb = self.handle.get_localdb()
                for repo in syncdbs:
                    for pkg in repo.pkgcache:
                        if((pattern in pkg.name) and (not pkg.name in local_packages)):
                            if not localdb.get_pkg(pkg.name):
                                local_packages.append(pkg.name)
                self._try_to_save(pattern, local_packages)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        sleep(0.1)
        loop.quit()

    def _get_local_packages(self):
        local_packages = set()
        sync_pkg = None
        for pkg in self.localdb.pkgcache:
            for db in self.syncdbs:
                sync_pkg = db.get_pkg(pkg.name)
                if sync_pkg:
                    break
            if not sync_pkg:
                local_packages.add(pkg.name)
        return local_packages

    def _likely_packaged(self, file):
        '''Check whether the given file is likely to belong to a package.'''
        pkg_whitelist = ["/bin/", "/boot", "/etc/", "/initrd", "/lib", "/sbin/",
                         "/opt", "/usr/", "/var"]  # packages only ship executables in these directories

        whitelist_match = False
        for i in pkg_whitelist:
            if file.startswith(i):
                whitelist_match = True
                break
        return whitelist_match and not file.startswith("/usr/local/") and not \
            file.startswith("/var/lib/")

    def _get_file_package(self, file):
        '''Return the package a file belongs to.
        Return None if the file is not shipped by any package.
        '''
        # check if the file is a diversion
        dpkg = subprocess.Popen(["pacman", "-Qo", file],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = dpkg.communicate()[0].decode("UTF-8")
        if dpkg.returncode == 0 and out:
            outList = out.split()
            pkg = outList[-2]# + "-" +outList[-1]
            return pkg

        fname = os.path.splitext(os.path.basename(file))[0].lower()

        all_lists = []
        likely_lists = []
        for f in glob.glob("/var/lib/dpkg/info/*.list"):
            p = os.path.splitext(os.path.basename(f))[0].lower().split(":")[0]
            if p in fname or fname in p:
                likely_lists.append(f)
            else:
                all_lists.append(f)

        # first check the likely packages
        match = self.__fgrep_files(file, likely_lists)
        if not match:
            match = self.__fgrep_files(file, all_lists)

        if match:
            return os.path.splitext(os.path.basename(match))[0].split(":")[0]

        return None

    def __fgrep_files(self, pattern, file_list):
        '''Call fgrep for a pattern on given file list and return the first
        matching file, or None if no file matches.'''

        match = None
        slice_size = 100
        i = 0

        while not match and i < len(file_list):
            p = subprocess.Popen(["fgrep", "-lxm", "1", "--", pattern] +
                                 file_list[i:(i + slice_size)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out = p.communicate()[0].decode("UTF-8")
            if p.returncode == 0:
                match = out
            i += slice_size

        return match

    def _get_handle(self):
        self.handle = config.handle()
        self.localdb = self.handle.get_localdb()
        self.syncdbs = self.handle.get_syncdbs()
        self.handle.dlcb = self._on_cb_dl
        self.handle.totaldlcb = self._on_dlcb_total
        self.handle.eventcb = self._on_cb_event
        self.handle.questioncb = self._on_cb_question
        self.handle.progresscb = self._on_cb_progress
        self.handle.logcb = self._on_cb_log

    def _check_finished_commit(self):
        if self.task.is_alive():
            return True
        else:
            self._get_handle()
            return False

    def _try_to_save(self, pattern, unInstalledPackages):
        listKeys = self.lastedSearch.keys()
        length = len(listKeys)
        minVal = -1
        oldPattern = None
        if(length > 100):
            for key in listkeys:
                if (self.lastedSearch[key][1] < minVal) or (minVal < 0):
                   minVal = self.lastedSearch[key][1]
                   oldPattern = key
            if oldPattern:
                #delete de old element and reorder the key list
                del self.lastedSearch[oldPattern]
                for key in listkeys:
                    if (self.lastedSearch[key][1] > minVal):
                       self.lastedSearch[key][1] = self.lastedSearch[key][1] - 1
                       length = length - 1
               
        if(len(unInstalledPackages) > 0):
            self.lastedSearch[pattern] = [unInstalledPackages, length]

    def _get_quick_search(self, pattern):
        for key in self.lastedSearch:
            if(key in pattern):
                return self.lastedSearch[key][0]
        return None

    def _is_matching(self, matchWordsPattern, packageName):
        for word in matchWordsPattern:
            if(word in packageName):
                return True
        return False

    def _on_cb_event(self, id=None, event=None, tupel=None):
        if tupel == None:
            tupel = event
            event = id
        status = self.previous_status
        role = self.previous_role
        icon = self.previous_icon
        if event == "ALPM_EVENT_CHECKDEPS_START":
            status = _("Checking dependencies")+"..."
            role = status+"\n"
            icon = "cinnamon-installer-search"
        elif event == "ALPM_EVENT_CHECKDEPS_DONE":
            if self.warning:
                self.EmitLogWarning(self.warning)
                self.warning = ""
        elif event == "ALPM_EVENT_FILECONFLICTS_START":
            status = _("Checking file conflicts")+"..."
            role = status+"\n"
            icon = "cinnamon-installer-search"
        elif event == "ALPM_EVENT_FILECONFLICTS_DONE":
            pass
        elif event == "ALPM_EVENT_RESOLVEDEPS_START":
            status = _("Resolving dependencies")+"..."
            role = status+"\n"
            icon = "cinnamon-installer-setup"
        elif event == "ALPM_EVENT_RESOLVEDEPS_DONE":
            if self.warning:
                self.EmitLogWarning(self.warning)
                self.warning = ""
        elif event == "ALPM_EVENT_INTERCONFLICTS_START":
            status = _("Checking inter conflicts")+"..."
            role = status+"\n"
            icon = "cinnamon-installer-search"
        elif event == "ALPM_EVENT_INTERCONFLICTS_DONE":
            if self.warning:
                self.EmitLogWarning(self.warning)
                self.warning = ""
        elif event == "ALPM_EVENT_ADD_START":
            string = _("Installing {pkgname}").format(pkgname = tupel[0].name)
            status = string+"..."
            role = "{} ({})...\n".format(string, tupel[0].version)
            icon = "cinnamon-installer-install"
        elif event == "ALPM_EVENT_ADD_DONE":
            formatted_event = "Installed {pkgname} ({pkgversion})".format(pkgname = tupel[0].name, pkgversion = tupel[0].version)
            common.write_log_file(formatted_event)
        elif event == "ALPM_EVENT_REMOVE_START":
            string = _("Removing {pkgname}").format(pkgname = tupel[0].name)
            status = string+"..."
            role = "{} ({})...\n".format(string, tupel[0].version)
            icon = "cinnamon-installer-delete"
        elif event == "ALPM_EVENT_REMOVE_DONE":
            formatted_event = "Removed {pkgname} ({pkgversion})".format(pkgname = tupel[0].name, pkgversion = tupel[0].version)
            common.write_log_file(formatted_event)
        elif event == "ALPM_EVENT_UPGRADE_START":
            string = _("Upgrading {pkgname}").format(pkgname = tupel[1].name)
            status = string+"..."
            role = "{} ({} => {})...\n".format(string, tupel[1].version, tupel[0].version)
            icon = "cinnamon-installer-update"
        elif event == "ALPM_EVENT_UPGRADE_DONE":
            formatted_event = "Upgraded {pkgname} ({oldversion} -> {newversion})".format(pkgname = tupel[1].name, oldversion = tupel[1].version, newversion = tupel[0].version)
            common.write_log_file(formatted_event)
        elif event == "ALPM_EVENT_DOWNGRADE_START":
            string = _("Downgrading {pkgname}").format(pkgname = tupel[1].name)
            status = string+"..."
            role = "{} ({} => {})...\n".format(string, tupel[1].version, tupel[0].version)
            icon = "cinnamon-installer-install"
        elif event == "ALPM_EVENT_DOWNGRADE_DONE":
            formatted_event = "Downgraded {pkgname} ({oldversion} -> {newversion})".format(pkgname = tupel[1].name, oldversion = tupel[1].version, newversion = tupel[0].version)
            common.write_log_file(formatted_event)
        elif event == "ALPM_EVENT_REINSTALL_START":
            string = _("Reinstalling {pkgname}").format(pkgname = tupel[0].name)
            status = string+"..."
            role = "{} ({})...\n".format(string, tupel[0].version)
            icon = "cinnamon-installer-install"
        elif event == "ALPM_EVENT_REINSTALL_DONE":
            formatted_event = "Reinstalled {pkgname} ({pkgversion})".format(pkgname = tupel[0].name, pkgversion = tupel[0].version)
            common.write_log_file(formatted_event)
        elif event == "ALPM_EVENT_INTEGRITY_START":
            status = _("Checking integrity")+"..."
            role = status+"\n"
            icon = "cinnamon-installer-search"
            self.already_transferred = 0
        elif event == "ALPM_EVENT_INTEGRITY_DONE":
            pass
        elif event == "ALPM_EVENT_LOAD_START":
            status = _("Loading packages files")+"..."
            role = status+"\n"
            icon = "cinnamon-installer-search"
        elif event == "ALPM_EVENT_LOAD_DONE":
            pass
        elif event == "ALPM_EVENT_DELTA_INTEGRITY_START":
            status = _("Checking delta integrity")+"..."
            role = status+"\n"
            icon = "cinnamon-installer-search"
        elif event == "ALPM_EVENT_DELTA_INTEGRITY_DONE":
            pass
        elif event == "ALPM_EVENT_DELTA_PATCHES_START":
            status = _("Applying deltas")+"..."
            role = status+"\n"
            icon = "cinnamon-installer-setup"
        elif event == "ALPM_EVENT_DELTA_PATCHES_DONE":
            pass
        elif event == "ALPM_EVENT_DELTA_PATCH_START":
            status = _("Generating {} with {}").format(tupel[0], tupel[1])+"..."
            role = status+"\n"
            icon = "cinnamon-installer-setup"
        elif event == "ALPM_EVENT_DELTA_PATCH_DONE":
            status = _("Generation succeeded!")
            role = status+"\n"
        elif event == "ALPM_EVENT_DELTA_PATCH_FAILED":
            status = _("Generation failed.")
            role = status+"\n"
        elif event == "ALPM_EVENT_SCRIPTLET_INFO":
            status =_("Configuring {pkgname}").format(pkgname = self.previous_target)+"..."
            role = tupel[0]
            icon = "cinnamon-installer-setup"
            self.EmitNeedDetails(True)
        elif event == "ALPM_EVENT_RETRIEVE_START":
            status = _("Downloading")+"..."
            role = status+"\n"
            icon = "cinnamon-installer-download"
        elif event == "ALPM_EVENT_DISKSPACE_START":
            status = _("Checking available disk space")+"..."
            role = status+"\n"
            icon = "cinnamon-installer-search"
        elif event == "ALPM_EVENT_OPTDEP_REQUIRED":
            print("Optionnal deps exist")
        elif event == "ALPM_EVENT_DATABASE_MISSING":
            #status =_("Database file for {} does not exist").format(tupel[0])+"..."
            #role = status
            pass
        elif event == "ALPM_EVENT_KEYRING_START":
            status = _("Checking keyring")+"..."
            role = status+"\n"
            icon = "cinnamon-installer-search"
        elif event == "ALPM_EVENT_KEYRING_DONE":
            pass
        elif event == "ALPM_EVENT_KEY_DOWNLOAD_START":
            status = _("Downloading required keys")+"..."
            role = status+"\n"
        elif event == "ALPM_EVENT_KEY_DOWNLOAD_DONE":
            pass
        if status != self.previous_status:
            self.previous_status = status
            self.EmitStatus(status, status)
        if role != self.previous_role:
            self.previous_role != role
            self.EmitRole(role)
        if icon != self.previous_icon:
            self.previous_icon = icon
            self.EmitIcon(icon)
        print(str(event))

    def _on_cb_question(self, event, data_tupel, extra_data):
        if event == "ALPM_QUESTION_INSTALL_IGNOREPKG":
            return 0 # Do not install package in IgnorePkg/IgnoreGroup
        if event == "ALPM_QUESTION_REPLACE_PKG":
            self.warning += _("{pkgname1} will be replaced by {pkgname2}").format(pkgname1 = data_tupel[0].name, pkgname2 = data_tupel[1].name)+"\n"
            return 1 # Auto-remove conflicts in case of replaces
        if event == "ALPM_QUESTION_CONFLICT_PKG":
            self.warning += _("{pkgname1} conflicts with {pkgname2}").format(pkgname1 = data_tupel[0], pkgname2 = data_tupel[1])+"\n"
            return 1 # Auto-remove conflicts
        if event == "ALPM_QUESTION_CORRUPTED_PKG":
            return 1 # Auto-remove corrupted pkgs in cache
        if event == "ALPM_QUESTION_REMOVE_PKGS":
            return 1 # Do not upgrade packages which have unresolvable dependencies
        if event == "ALPM_QUESTION_SELECT_PROVIDER":
            ## In this case we populate providers with different choices
            ## the client will have to release transaction and re-init one 
            ## with the chosen package added to it
            self.providers.append(([pkg.name for pkg in data_tupel[0]], data_tupel[1]))
            return 0 # return the first choice, this is not important because the transaction will be released
        if event == "ALPM_QUESTION_IMPORT_KEY":
            ## data_tupel = (revoked(int), length(int), pubkey_algo(string), fingerprint(string), uid(string), created_time(int))
            if data_tupel[0] is 0: # not revoked
                return 1 # Auto get not revoked key
            if data_tupel[0] is 1: # revoked
                return 0 # Do not get revoked key

    def _on_cb_log(self, level, line):
        _logmask = pyalpm.LOG_ERROR | pyalpm.LOG_WARNING
        if not (level & _logmask):
            return
        if level & pyalpm.LOG_ERROR:
            #self.EmitLogError(line)
            _error = _("Error: ")+line
            self.EmitRole(_error)
            self.EmitNeedDetails(True)
            print(line)
        elif level & pyalpm.LOG_WARNING:
            self.warning += line
            _warning = _("Warning: ")+line
            self.EmitRole(_warning)
        elif level & pyalpm.LOG_DEBUG:
            line = "DEBUG: " + line
            print(line)
        elif level & pyalpm.LOG_FUNCTION:
            line = "FUNC: " + line
            print(line)

    def _on_dlcb_total(self, _total_size):
        self.total_size = _total_size

    def _on_cb_dl(self, _target, _transferred, _total):
        if _target.endswith(".db"):
            status = _("Refreshing {repo}").format(repo = _target.replace(".db", ""))+"..."
            role = ""
            icon = "cinnamon-installer-refresh"
        else:
            status = _("Downloading {pkgname}").format(pkgname = _target.replace(".pkg.tar.xz", ""))+"..."
            role = status+"\n"
            icon = "cinnamon-installer-download"
        if self.total_size > 0:
            percent = round((_transferred+self.already_transferred)/self.total_size, 2)
            if _transferred+self.already_transferred <= self.total_size:
                target = "{transferred}/{size}".format(transferred = common.format_size(_transferred+self.already_transferred), size = common.format_size(self.total_size))
            else:
                target = ""
        else:
            percent = round(_transferred/_total, 2)
            target = ""
        if status != self.previous_status:
            self.previous_status = status
            self.EmitStatus(status, status)
        if role != self.previous_role:
            self.previous_role = role
            self.EmitRole(role)
        if icon != self.previous_icon:
            self.previous_icon = icon
            self.EmitIcon(icon)
        if target != self.previous_target:
            self.previous_target = target
            self.EmitTarget(target)
        if percent != self.previous_percent:
            self.previous_percent = percent
            self.EmitPercent(100*percent)
        elif _transferred == _total:
            self.already_transferred += _total

    def _on_cb_progress(self, event=None, target=None, _percent=None, n=None, i=None):
        if i == None:
            i = n
            n = _percent
            _percent = target
            target = event
            event = i
        if event and event in ("ALPM_PROGRESS_ADD_START", "ALPM_PROGRESS_UPGRADE_START",
                               "ALPM_PROGRESS_DOWNGRADE_START", "ALPM_PROGRESS_REINSTALL_START", "ALPM_PROGRESS_REMOVE_START"):
            percent = round(((i-1)/n)+(_percent/(100*n)), 2)
        else:
            percent = round(_percent/100, 2)
        if target != self.previous_target:
            self.previous_target = target
        if percent >= self.previous_percent + 1:
            self.EmitTarget("{}/{}".format(str(i), str(n)))
            self.previous_percent = percent
            self.EmitPercent(100*percent)

    def _set_pkg_reason(self, pkgname, reason):
        error = ""
        try:
            pkg = self.localdb.get_pkg(pkgname)
            if pkg:
                self.handle.set_pkgreason(pkg, reason)
        except Exception:
            e = sys.exc_info()[1]
            error = format_error(e.args)
        return error

    def _policykit_test(self, sender, connexion, action):
        bus = dbus.SystemBus()
        proxy_dbus = connexion.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus/Bus", False)
        dbus_info = dbus.Interface(proxy_dbus, "org.freedesktop.DBus")
        sender_pid = dbus_info.GetConnectionUnixProcessID(sender)
        proxy_policykit = bus.get_object("org.freedesktop.PolicyKit1", "/org/freedesktop/PolicyKit1/Authority", False)
        policykit_authority = dbus.Interface(proxy_policykit, "org.freedesktop.PolicyKit1.Authority")

        Subject = ("unix-process", {"pid": dbus.UInt32(sender_pid, variant_level=1),
        "start-time": dbus.UInt64(0, variant_level=1)})
        # We would like an infinite timeout, but dbus-python won't allow it.
        # Pass the longest timeout dbus-python will accept
        (is_authorized,is_challenge,details) = policykit_authority.CheckAuthorization(Subject, action, {"": ""}, dbus.UInt32(1), "",timeout=2147483)
        return is_authorized

    '''
    def _set_pkg_reason(self, pkgname, reason, sender=None, connexion=None):
        try:
            authorized = self._policykit_test(sender, connexion, "org.manjaro.pamac.commit")
        except dbus.exceptions.DBusException:
            e = sys.exc_info()[1]
            return _("Authentication failed")
        else:
            if authorized:
                error = ""
                try:
                    pkg = self.localdb.get_pkg(pkgname)
                    if pkg:
                        self.handle.set_pkgreason(pkg, reason)
                except Exception:
                    e = sys.exc_info()[1]
                    error = format_error(e.args)
                return error
           else :
                return _("Authentication failed")
    '''
    def _check_updates(self, success=None, nosuccess=None, collect_type=None):
        if success:
            success("")
        syncfirst = False
        updates = []
        _ignorepkgs = set()
        self._get_handle()
        for group in self.handle.ignoregrps:
            db = self.localdb
            grp = db.read_grp(group)
            if grp:
                name, pkg_list = grp
                for pkg in pkg_list:
                    _ignorepkgs.add(pkg.name)
        for name in self.handle.ignorepkgs:
            pkg = self.localdb.get_pkg(name)
            if pkg:
                _ignorepkgs.add(pkg.name)
        if config.syncfirst:
            for name in config.syncfirst:
                pkg = self.localdb.get_pkg(name)
                if pkg:
                    candidate = pyalpm.sync_newversion(pkg, self.syncdbs)
                    if candidate:
                        syncfirst = True
                        updates.append((candidate.name, candidate.version, candidate.db.name, "", candidate.download_size))
        if not updates:
            local_packages = set()
            if config.enable_aur:
                if not self.aur_updates_checked:
                    local_packages = self._get_local_packages()
                    local_packages -= _ignorepkgs
            for pkg in self.localdb.pkgcache:
                if not pkg.name in _ignorepkgs:
                    candidate = pyalpm.sync_newversion(pkg, self.syncdbs)
                    if candidate:
                        updates.append((candidate.name, candidate.version, candidate.db.name, "", candidate.download_size))
                        local_packages.discard(pkg.name)
            if config.enable_aur:
                if not self.aur_updates_checked:
                    if local_packages:
                        self.aur_updates_pkgs = aur.multiinfo(local_packages)
                        self.aur_updates_checked = True
                for aur_pkg in self.aur_updates_pkgs:
                    if self.localdb.get_pkg(aur_pkg.name):
                        comp = pyalpm.vercmp(aur_pkg.version, self.localdb.get_pkg(aur_pkg.name).version)
                        if comp == 1:
                            updates.append((aur_pkg.name, aur_pkg.version, aur_pkg.db.name, aur_pkg.tarpath, aur_pkg.download_size))
        self.EmitAvailableUpdates(syncfirst, updates)

    def _refresh_pylamp(self, force_update):
        print("Refresh")
        def refresh():
            self.target = ""
            self.percent = 0
            error = ""
            for db in self.syncdbs:
                try:
                    self.t = self.handle.init_transaction()
                    db.update(force = bool(force_update))
                    self.t.release()
                except pyalpm.error:
                    e = sys.exc_info()[1]
                    print(str(e))
                    error += format_error(e.args)
                    break
            if error:
                self.EmitTransactionError(_("Transaction fail:"), error)
            else:
                self.EmitTransactionDone("")
        self.task = Process(target=refresh)
        self.task.start()
        GObject.timeout_add(100, self._check_finished_commit)

    '''
    def _init_trans(self, options):
        error = ""
        try:
            #self.subject = Polkit.UnixProcess.new(os.getppid())
            #self.subject.set_uid(0)
            #self._get_handle()
            self.t = self.handle.init_transaction(**options)
            print("Init:" + self.t.flags)
        except pyalpm.error:
            e = sys.exc_info()[1]
            print(str(e))
            error = format_error(e.args)
        finally:
            return error
    '''

    def _init_trans(self, **options):
        error = ""
        try:
            #self.subject = Polkit.UnixProcess.new(os.getppid())
            #self.subject.set_uid(0)
            #self._get_handle()
            self.t = self.handle.init_transaction(**options)
            #print("Init:" + self.t.flags)
        except pyalpm.error:
            e = sys.exc_info()[1]
            print(str(e))
            error = format_error(e.args)
        finally:
            return error

    def _sys_upgrade(self, downgrade):
        error = ""
        try:
            self.t.sysupgrade(downgrade = bool(downgrade))
        except pyalpm.error:
            e = sys.exc_info()[1]
            error = format_error(e.args)
            self.t.release()
        finally:
            return error

    def _remove_pkg(self, pkgname):
        error = ""
        try:
            pkg = self.localdb.get_pkg(pkgname)
            if pkg is not None:
                self.t.remove_pkg(pkg)
        except pyalpm.error:
            e = sys.exc_info()[1]
            error = format_error(e.args)
        finally:
            return error

    def _add_pkg(self, pkgname):
        error = ""
        try:
            for db in self.syncdbs:
                # this is a security, in case of virtual package it will
                # choose the first provider, the choice should have been
                # done by the client
                pkg = pyalpm.find_satisfier(db.pkgcache, pkgname)
                if pkg:
                    self.t.add_pkg(pkg)
                    break
        except pyalpm.error:
            e = sys.exc_info()[1]
            error = format_error(e.args)
        finally:
            return error

    def _load_file(self, tarball_path):
        error = ""
        try:
            pkg = self.handle.load_pkg(tarball_path)
            if pkg:
                self.t.add_pkg(pkg)
        except pyalpm.error:
            error = _("{pkgname} is not a valid path or package name").format(pkgname = tarball_path)
        finally:
            return error

    def _check_extra_modules(self):
        to_add = set(pkg.name for pkg in self.t.to_add)
        to_remove = set(pkg.name for pkg in self.t.to_remove)
        to_check = [pkg for pkg in self.t.to_add]
        already_checked = set(pkg.name for pkg in to_check)
        depends = [to_check]
        # get installed kernels and modules
        pkgs = self.localdb.search("linux")
        installed_kernels = set()
        installed_modules = set()
        for pkg in pkgs:
            match = re.match("(linux[0-9]{2,3})(.*)", pkg.name)
            if match:
                installed_kernels.add(match.group(1))
                if match.group(2):
                    installed_modules.add(match.group(2))
        for pkg in self.t.to_add:
            match = re.match("(linux[0-9]{2,3})(.*)", pkg.name)
            if match:
                installed_kernels.add(match.group(1))
                if match.group(2):
                    installed_modules.add(match.group(2))
        # check in to_remove if there is a kernel and if so, auto-remove the corresponding modules 
        for pkg in self.t.to_remove:
            match = re.match("(linux[0-9]{2,3})(.*)", pkg.name)
            if match:
                if not match.group(2):
                    installed_kernels.discard(match.group(1))
                    for module in installed_modules:
                        pkgname = match.group(1)+module
                        if not pkgname in to_remove:
                            _pkg = self.localdb.get_pkg(pkgname)
                            if _pkg:
                                # Check we won't remove a third party kernel
                                third_party = False
                                for provide in _pkg.provides:
                                    if "linux=" in provide:
                                        third_party = True
                                if not third_party:
                                    to_remove.add(pkgname)
                                    self.t.remove_pkg(_pkg)
        # start loops to check pkgs
        i = 0
        while depends[i]:
            # add a empty list for new pkgs to check next loop
            depends.append([])
            # start to check one pkg
            for pkg in depends[i]:
                # check if the current pkg is a kernel and if so, check if a module is required to install
                match = re.match("(linux[0-9]{2,3})(.*)", pkg.name)
                if match:
                    if not match.group(2): # match pkg is a kernel
                        for module in installed_modules:
                            pkgname = match.group(1) + module
                            if not self.localdb.get_pkg(pkgname):
                                for db in self.syncdbs:
                                    _pkg = db.get_pkg(pkgname)
                                    if _pkg:
                                        if not _pkg.name in already_checked:
                                            depends[i+1].append(_pkg)
                                            already_checked.add(_pkg.name)
                                        if not _pkg.name in to_add | to_remove:
                                            to_add.add(_pkg.name)
                                            self.t.add_pkg(_pkg)
                                        break
                # check if the current pkg is a kernel module and if so, install it for all installed kernels
                match = re.match("(linux[0-9]{2,3})(.*-modules)", pkg.name)
                if match:
                    for kernel in installed_kernels:
                        pkgname = kernel + match.group(2)
                        if not self.localdb.get_pkg(pkgname):
                            for db in self.syncdbs:
                                _pkg = db.get_pkg(pkgname)
                                if _pkg:
                                    if not _pkg.name in already_checked:
                                        depends[i+1].append(_pkg)
                                        already_checked.add(_pkg.name)
                                    if not _pkg.name in to_add | to_remove:
                                        to_add.add(_pkg.name)
                                        self.t.add_pkg(_pkg)
                                    break
                for depend in pkg.depends:
                    found_depend = pyalpm.find_satisfier(self.localdb.pkgcache, depend)
                    if not found_depend:
                        for db in self.syncdbs:
                            found_depend = pyalpm.find_satisfier(db.pkgcache, depend)
                            if found_depend:
                                break
                    if found_depend:
                        # add the dep in list to check its deps in next loop 
                        if not found_depend.name in already_checked:
                            depends[i+1].append(found_depend)
                            already_checked.add(found_depend.name)
            i += 1
            # end of the loop

    def _prepare_pyalpm(self):
        error = ""
        self.providers.clear()
        self._check_extra_modules()
        try:
            self.t.prepare()
        except pyalpm.error:
            e = sys.exc_info()[1]
            error = format_error(e.args)
            self.t.release()
        else:
            for pkg in self.t.to_remove:
                if pkg.name in config.holdpkg:
                    error = _("The transaction cannot be performed because it needs to remove {pkgname1} which is a locked package").format(pkgname1 = pkg.name)
                    self.t.release()
                    break
        finally:
            try:
                summ = len(self.t.to_add) + len(self.t.to_remove)
            except pyalpm.error:
                return [((), error)]
            if summ == 0:
                self.t.release()
                return [((), _("Nothing to do"))]
            elif error:
                return [((), error)]
            elif self.providers:
                return self.providers
            else:
                return [((), "")]

    def _to_remove_pyalpm(self):
        _list = []
        try:
            for pkg in self.t.to_remove:
                _list.append((pkg.name, pkg.version))
        except:
            pass
        return _list

    def _to_add_pyalpm(self):
        _list = []
        try:
            for pkg in self.t.to_add:
                _list.append((pkg.name, pkg.version, pkg.download_size))
        except:
            pass
        return _list

    def cancel(self):
        def interrupt():
            try:
                self.t.interrupt()
            except:
                pass
            finally:
                self.release_all()
                #common.rm_lock_file()
        if self.task:
            self.task.terminate()
        interrupt()

    def commit(self):
        if not self.client_response:
            self.client_condition.acquire()
            self.client_response = True
            self.client_condition.notify()
            self.client_condition.release()
        error = ""
        try:
            self.t.commit()
        except pyalpm.error:
            e = sys.exc_info()[1]
            error = format_error(e.args)
        except Exception:
            pass
        finally:
            self.t.release()
            if self.warning:
                self.EmitLogWarning(self.warning)
                self.warning = ""
            if error:
                self.EmitTransactionError(_("Transaction fail:"), error)
            else:
                self.EmitTransactionDone(_("Transaction successfully finished"))
            self.release_all()
    '''
    def commit(self, success, nosuccess, sender=None, connexion=None):
        def commit():
            error = ""
            try:
                self.t.commit()
            except pyalpm.error:
                e = sys.exc_info()[1]
                error = format_error(e.args)
            #except dbus.exceptions.DBusException:
                #pass
            finally:
                self.t.release()
                if self.warning:
                    self.EmitLogWarning(self.warning)
                    self.warning = ""
                if error:
                    self.EmitTransactionError(_("Transaction fail:"), error)
                else:
                    self.EmitTransactionDone(_("Transaction successfully finished"))
        success("")
        try:
            authorized = self._policykit_test(sender,connexion, "org.manjaro.pamac.commit")
        except dbus.exceptions.DBusException:
            e = sys.exc_info()[1]
            self.EmitTransactionError(_("Transaction fail:"), _("Authentication failed"))
        else:
            if authorized:
                self.task = Process(target=commit)
                self.task.start()
                GObject.timeout_add(100, self.check_finished_commit)
            else :
                self.t.release()
                self.EmitTransactionError(_("Transaction fail:"), _("Authentication failed"))
    '''
    def release_all(self):
        try:
            if not self.client_response:
                self.client_condition.acquire()
                self.client_response = True
                self.client_condition.notify()
                self.client_condition.release()
            self.t.release()
            self.lock_trans.release()
            #common.rm_pid_file()
        except:
            pass

    def write_config(self, array, collect_type=None):
        sender = None
        connexion = None
        need_update = False
        if array["EnableAUR"] != self.config["EnableAUR"]:
            need_update = True
        if array["RemoveUnrequiredDeps"] != self.config["RemoveUnrequiredDeps"]:
            need_update = True
        if array["RefreshPeriod"] != self.config["RefreshPeriod"]:
            need_update = True
        if need_update:
            try:
                authorized = self._policykit_test(sender,connexion, "org.manjaro.pamac.write_config")
            except dbus.exceptions.DBusException:
                e = sys.exc_info()[1]
                self.EmitLogError(_("Authentication failed"))
            else:
                if authorized:
                    self._write_config(array)
                else:
                    self.EmitLogError(_("Authentication failed"))

    def _write_config(self, array):
        error = ""
        with open(config.INSTALLER_PATH, "r") as conffile:
            data = conffile.readlines()
        i = 0
        while i < len(data):
            line = data[i].strip()
            if len(line) == 0:
                i += 1
                continue
            if line[0] == "#":
                line = line.lstrip("#")
            if line == "\n":
                i += 1
                continue
            old_key, equal, old_value = [x.strip() for x in line.partition("=")]
            for tupel in array:
                new_key = tupel[0]
                new_value = tupel[1]
                if old_key == new_key:
                    # i is equal to the line number where we find the key in the file
                    if new_key in config.SINGLE_OPTIONS:
                        data[i] = "{} = {}\n".format(new_key, new_value)
                    elif new_key in config.BOOLEAN_OPTIONS:
                        if new_value == "False": 
                            data[i] = "#{}\n".format(new_key)
                        else:
                            data[i] = "{}\n".format(new_key)
            i += 1
        with open(config.INSTALLER_PATH, "w") as conffile:
            conffile.writelines(data)
        self.EmitReloadConfig("")
#Mycode
    def prepare_transaction_install(self, pkgs, collect_type=None, cascade = True, recurse = False):
        self.EmitTransactionStart("")
        self.to_add = set()
        self.to_update = set()
        self.to_load = set()
        self.to_remove = set()
        error = self._get_pkgs_to_install(pkgs)
        if error != "":
            self.EmitTransactionError(_("Transaction fail:"), error)
        elif ((len(self.to_add) == 0) and (len(self.to_load) == 0) and (len(self.to_build) == 0)):
            error = _("{pkgname} is not a valid path or package name").format(pkgname = name)
            self.EmitTransactionError(_("Transaction fail:"), error)
        else:
            if self.to_build:
                # check if packages in to_build have deps or makedeps which need to be install first
                error += self.check_to_build()
            if not error:
                if len(self.to_add) > 0 or len(self.to_remove) > 0 or len(self.to_load) > 0:
                    self.EmitTransactionCancellable(True)
                    trans_flags = {"cascade": cascade, "recurse": recurse}
                    error += self.init_transaction(**trans_flags)
                    if not error:
                        for name in self.to_add:
                            error += self._add_pkg(name)
                        for name in self.to_remove:
                            error += self._remove_pkg(name)
                        for path in self.to_load:
                            error += self._load_file(path)
                        if not error:
                            error += self._prepare(trans_flags)
                else:
                    self.EmitTransactionError(_("Transaction fail:"), _("Nothing to do"))
                if not error:
                    dependencies = self._get_dependencies()
                    print("Dep:" + str(dependencies))
                    info_conf = self._get_transaction_summary(dependencies)
                    print("Info:" + str(info_conf["dependencies"]))
                    self.EmitTransactionConfirmation(info_conf)
            if error:
                ##show error?
                print("hola")
                self.release_all()
                self.EmitTransactionError(_("Transaction fail:"), error)

    def prepare_transaction_remove(self, pkgs, collect_type=None, cascade = True, recurse = False):
        self.EmitTransactionStart("")
        self.to_add = set()
        self.to_update = set()
        self.to_load = set()
        self.to_remove = set()
        error = self._get_pkgs_to_remove(pkgs)
        if error:
            self.EmitTransactionError(_("Transaction fail:"), error)
        else:
            if self.to_build:
                # check if packages in to_build have deps or makedeps which need to be install first
                error += self.check_to_build()
            if not error:
                if len(self.to_add) > 0 or len(self.to_remove) > 0 or len(self.to_load) > 0:
                    self.EmitTransactionCancellable(True)
                    trans_flags = {"cascade": cascade, "recurse": recurse}
                    error += self.init_transaction(**trans_flags)
                    if not error:
                        for name in self.to_add:
                            error += self._add_pkg(name)
                        for name in self.to_remove:
                            error += self._remove_pkg(name)
                        for path in self.to_load:
                            error += self._load_file(path)
                        if not error:
                            error += self._prepare(trans_flags)
                else:
                    self.EmitTransactionError(_("Transaction fail:"),_("Nothing to do"))
                if not error:
                    dependencies = self._get_dependencies()
                    print("Dep:" + str(dependencies))
                    info_conf = self._get_transaction_summary(dependencies)
                    print("Info:" + str(info_conf["dependencies"]))
                    self.EmitTransactionConfirmation(info_conf)
            if error:
                ##show error?
                self.release_all()
                self.EmitTransactionError(_("Transaction fail:"), error)

    def prepare_transaction_commit(self, packages_status, collect_type=None): #new and need to be tested to_update and to_load at less?
        self.EmitTransactionStart("")
        self.to_add = set()
        self.to_update = set()
        self.to_load = set()
        self.to_remove = set()
        error_install = self._get_pkgs_to_install(packages_status["install"])
        error_remove = self._get_pkgs_to_remove(packages_status["remove"])
        if error_install or error_remove:
            self.EmitTransactionError(_("Transaction fail:"), "")
        else:
            if self.to_build:
                # check if packages in to_build have deps or makedeps which need to be install first
                error += self.check_to_build()
            if not error:
                if len(self.to_add) > 0 or len(self.to_remove) > 0 or len(self.to_load) > 0:
                    self.EmitTransactionCancellable(True)
                    trans_flags = {"cascade": cascade, "recurse": recurse}
                    error += self.init_transaction(**trans_flags)
                    if not error:
                        for name in self.to_add:
                            error += self._add_pkg(name)
                        for name in self.to_remove:
                            error += self._remove_pkg(name)
                        for path in self.to_load:
                            error += self._load_file(path)
                        if not error:
                            error += self._prepare(trans_flags)
                else:
                    self.EmitTransactionError(_("Transaction fail:"),_("Nothing to do"))
                if not error:
                    dependencies = self._get_dependencies()
                    print("Dep:" + str(dependencies))
                    info_conf = self._get_transaction_summary(dependencies)
                    print("Info:" + str(info_conf["dependencies"]))
                    self.EmitTransactionConfirmation(info_conf)
            if error:
                ##show error?
                self.release_all()
                self.EmitTransactionError(_("Transaction fail:"), error)

    def _get_pkgs_to_install(self, pkgs):
        error = ""
        for name in pkgs:
            if ".pkg.tar." in name:
                full_path = abspath(name)
                self.to_load.add(full_path)
            elif self._get_syncpkg(name):
                self.to_add.add(name)
            else:
                aur_pkg = None
                if config.enable_aur:
                    aur_pkg = aur.info(name)
                    if aur_pkg:
                        self.to_build.append(aur_pkg)
                if not aur_pkg:
                    if error:
                        error += "\n"
                    error += _("{pkgname} is not a valid path or package name").format(pkgname = name)
        return error

    def _get_pkgs_to_remove(self, pkgs):
        error = ""
        for name in pkgs:
            print(name)
            if self._get_localpkg(name):
                print("get local")
                self.to_remove.add(name)
        if len(self.to_remove) == 0:
            error = _("{pkgname} is not a valid path or package name").format(pkgname = name)
        return error
#Transaction

    def _get_localpkg(self, name):
        return self.localdb.get_pkg(name)

    def _get_syncpkg(self, name):
        for repo in self.syncdbs:
            pkg = repo.get_pkg(name)
            if pkg:
                return pkg
        return None

    def refresh_cache(force_update = False, collect_type=None):
        self.EmitTransactionStart("")
        self.EmitTransactionCancellable(True)
        self.EmitIcon("cinnamon-installer-refresh")
        self.EmitStatus(_("Refreshing")+"...", _("Refreshing")+"...")
        self.EmitTarget("")
        self.EmitPercent(0)
        self._refresh_pylamp(force_update)

    def init_transaction(self, **options):
        return self._init_trans(**options)
        #return _init_trans(dbus.Dictionary(options, signature="sb"))

    def check_to_build(self):
        self.make_depends = set()
        self.build_depends = set()
        # check if base_devel packages are installed
        for name in self.base_devel:
            if not pyalpm.find_satisfier(self.localdb.pkgcache, name):
                self.make_depends.add(name)
        already_checked = set()
        build_order = []
        i = 0
        error = ""
        while i < len(self.to_build):
            pkg = self.to_build[i]
            # if current pkg is not in build_order add it at the end of the list
            if not pkg.name in build_order:
                build_order.append(pkg.name)
            # download end extract tarball from AUR
            srcdir = aur.get_extract_tarball(pkg)
            if srcdir:
                # get PKGBUILD and parse it to create a new pkg object with makedeps and deps 
                new_pkgs = aur.get_pkgs(srcdir + "/PKGBUILD")
                for new_pkg in new_pkgs:
                    print("checking " + new_pkg.name)
                    # check if some makedeps must be installed
                    for makedepend in new_pkg.makedepends:
                        if not makedepend in already_checked:
                            if not pyalpm.find_satisfier(self.localdb.pkgcache, makedepend):
                                print("found make dep: " + makedepend)
                                for db in self.syncdbs:
                                    provider = pyalpm.find_satisfier(db.pkgcache, makedepend)
                                    if provider:
                                        break
                                if provider:
                                    self.make_depends.add(provider.name)
                                    already_checked.add(makedepend)
                                else:
                                    # current makedep need to be built
                                    raw_makedepend = common.format_pkg_name(makedepend)
                                    if raw_makedepend in build_order:
                                        # add it in build_order before pkg
                                        build_order.remove(raw_makedepend)
                                        index = build_order.index(pkg.name)
                                        build_order.insert(index, raw_makedepend)
                                    else:
                                        # get infos about it
                                        makedep_pkg = aur.info(raw_makedepend)
                                        if makedep_pkg:
                                            # add it in to_build so it will be checked 
                                            self.to_build.append(makedep_pkg)
                                            # add it in build_order before pkg
                                            index = build_order.index(pkg.name)
                                            build_order.insert(index, raw_makedepend)
                                            # add it in already_checked and to_add_as_as_dep 
                                            already_checked.add(raw_makedepend)
                                            self.to_mark_as_dep.add(raw_makedepend)
                                        else:
                                            if error:
                                                error += "\n"
                                            error += _("{pkgname} depends on {dependname} but it is not installable").format(pkgname = pkg.name, dependname = makedepend)
                    # check if some deps must be installed or built
                    for depend in new_pkg.depends:
                        if not depend in already_checked:
                            if not pyalpm.find_satisfier(self.localdb.pkgcache, depend):
                                print("found dep: " + depend)
                                for db in self.syncdbs:
                                    provider = pyalpm.find_satisfier(db.pkgcache, depend)
                                    if provider:
                                        break
                                if provider:
                                    # current dep need to be installed
                                    self.build_depends.add(provider.name)
                                    already_checked.add(depend)
                                else:
                                    # current dep need to be built
                                    raw_depend = common.format_pkg_name(depend)
                                    if raw_depend in build_order:
                                        # add it in build_order before pkg
                                        build_order.remove(raw_depend)
                                        index = build_order.index(pkg.name)
                                        build_order.insert(index, raw_depend)
                                    else:
                                        # get infos about it
                                        dep_pkg = aur.info(raw_depend)
                                        if dep_pkg:
                                            # add it in to_build so it will be checked 
                                            self.to_build.append(dep_pkg)
                                            # add it in build_order before pkg
                                            index = build_order.index(pkg.name)
                                            build_order.insert(index, raw_depend)
                                            # add it in already_checked and to_add_as_as_dep 
                                            already_checked.add(raw_depend)
                                            self.to_mark_as_dep.add(raw_depend)
                                        else:
                                            if error:
                                                error += "\n"
                                            error += _("{pkgname} depends on {dependname} but it is not installable").format(pkgname = pkg.name, dependname = depend)
            else:
                if error:
                    error += "\n"
                error += _("Failed to get {pkgname} archive from AUR").format(pkgname = pkg.name)
            i += 1
        if error:
            return error
        # add pkgname in make_depends and build_depends in to_add and to_mark_as_dep
        for name in self.make_depends:
            self.to_add.add(name)
            self.to_mark_as_dep.add(name)
        for name in self.build_depends:
            self.to_add.add(name)
            self.to_mark_as_dep.add(name)
        # reorder to_build following build_order
        self.to_build.sort(key = lambda pkg: build_order.index(pkg.name))
        #print("order:" + build_order)
        print("to build:" + self.to_build)
        print("makedeps:" + self.make_depends)
        print("builddeps:" + self.build_depends)
        return error

    '''
    def run(self, cascade = True, recurse = False):
        if self.to_add or self.to_remove or self.to_load or self.to_build:
            error = ""
            if self.to_build:
                # check if packages in to_build have deps or makedeps which need to be install first
                error += self.check_to_build()
            if not error:
                if self.to_add or self.to_remove or self.to_load:
                    self.EmitTransactionCancellable(True)
                    trans_flags = {"cascade": cascade, "recurse": recurse}
                    error += self.init_transaction(**trans_flags)
                    if not error:
                        for name in self.to_add:
                            error += self._add_pkg(name)
                        for name in self.to_remove:
                            error += self._remove_pkg(name)
                        for path in self.to_load:
                            error += self._load_file(path)
                        if not error:
                            error += self._prepare(trans_flags)
                if not error:
                    dependencies = self._get_dependencies()
                    print("Dep:" + str(dependencies))
                    info_conf = self._get_transaction_summary(dependencies)
                    print("Info:" + str(info_conf["dependencies"]))
                    self.EmitTransactionConfirmation(info_conf)
            if error:
                ##show error?
                self.release_all()
                self.EmitTransactionError(_("Transaction fail:"), error)
                return(error)
        else:
            return (_("Nothing to do"))
    '''
    def _prepare(self, trans_flags):
        error = ""
        ret = self._prepare_pyalpm()
        # ret type is a(ass) so [([""], "")]
        if ret[0][0]: # providers are emitted
            self.release_all()#Release?
            for item in ret:
                print("chossee providers?")
                self._choose_provides(item)
            error += self.init_transaction(**trans_flags)
            if not error:
                for name in self.to_add:
                    error += self._add_pkg(name)
                for name in self.to_remove:
                    error += self._remove_pkg(name)
                for path in self.to_load:
                    error += self._load_file(path)
                print("outttttttttttttttt1")
                #if not error:
                    #ret = self._prepare_pyalpm()
                    #if ret[0][1]:
                    #    error = str(ret[0][1])
        elif ret[0][1]: # an error is emitted
            error = str(ret[0][1])
        print("outttttttttttttttt")
        return(error)

    def _client_confirm_trans(self):
        return self.client_response

    def _choose_provides(self, data):
        if len(data) > 1:
            print("Seeee>" + str(data))
            virtual_dep = str(data[1])
            print("Seeee2>" + virtual_dep)
            providers = data[0]
            self.provider_data = { "title": "", "description": "", "providers": [] }
            self.provider_data["title"] = _("{pkgname} is provided by {number} packages.").format(pkgname = virtual_dep, number = str(len(providers)))
            self.provider_data["description"] = _("Please choose those you would like to install:")
            for name in providers:
                self.provider_data["providers"].append(str(name))
            print("call")
            self.EmitChooseProvider(self.provider_data)

    def resolve_config_file_conflict(self, replace, old, new):
         print("what?")

    def resolve_medium_required(self, medium):
         print("what?")

    def resolve_package_providers(self, provider_select):
        if provider_select and provider_select in self.provider_data["providers"]:
            self.to_add.append(provider_select)
        else:
            self.to_add.add(self.provider_data["providers"][0])# add first provider
        if not self.client_response:
            self.client_condition.acquire()
            self.client_response = True
            self.client_condition.notify()
            self.client_condition.release()

    def _check_finished_build(self, data):
        def handle_timeout(*args):
            raise Exception("timeout")
        def no_handle_timeout(*args):
            try:
                pass
            except:
                pass
        path = data[0]
        pkg = data[1]
        if self.build_proc.poll() is None:
            # Build no finished : read stdout to push it to text_buffer
            # add a timeout to stop reading stdout if too long
            # so the gui won't freeze
            signal.signal(signal.SIGALRM, handle_timeout)
            signal.setitimer(signal.ITIMER_REAL, 0.05) # 50 ms timeout
            try:
                line = self.build_proc.stdout.readline().decode(encoding="UTF-8")
                line = re.sub(colors_regexp, "", line)
                #print(line.rstrip("\n"))
                progress_buffer.insert_at_cursor(line)
            except Exception:
                pass
            else:
                signal.signal(signal.SIGALRM, no_handle_timeout)
            finally:
                #progress_bar.pulse()
                self.EmitPercent(200)
                return True
        elif self.build_proc.poll() == 0:
            # Build successfully finished
            built = []
            # parse again PKGBUILD to have new pkg objects in case of a pkgver() function
            # was used so pkgver was changed during build process
            new_pkgs = aur.get_pkgs(path + "/PKGBUILD")
            # find built packages
            for new_pkg in new_pkgs:
                for item in os.listdir(path):
                    if os.path.isfile(os.path.join(path, item)):
                        # add a * before pkgver if there an epoch variable
                        if fnmatch.fnmatch(item, "{}-*{}-*.pkg.tar.?z".format(new_pkg.name, new_pkg.version)):
                            built.append(os.path.join(path, item))
                            break
            if built:
                print("successfully built:" + str(built))
                self.build_proc = None
                if pkg in self.to_build:
                    self.to_build.remove(pkg)
                # install built packages
                error = ""
                error += self.init_transaction()
                if not error:
                    for pkg_path in built:
                        error += self._load_file(pkg_path)
                    if not error:
                        error += self._prepare()
                        if not error:
                            if self._to_remove_pyalpm():
                                dependencies = self._get_dependencies()
                                print("Dep:" + str(dependencies))
                                info_conf = self._get_transaction_summary(dependencies)
                                print("Info:" + str(info_conf["dependencies"]))
                                self.EmitTransactionConfirmation(info_conf)
                            else:
                                self._finalize()
                    if error:
                        self.release_all()
                        self.EmitTransactionError(error, error)
            else:
                self.EmitTransactionError(_("Build process failed."), _("Build process failed."))
            return False
        elif self.build_proc.poll() == 1:
            # Build finish with an error
            self.EmitTransactionError(_("Build process failed."), _("Build process failed."))
            return False

    def Download(self, url_list, path):
        def write_file(f, chunk):
            if self.cancel_download:
                if ftp:
                    ftp.quit()
                raise Exception("Download cancelled")
                return
            f.write(chunk)
            self.aur_transferred += len(chunk)
            if total_size > 0:
                percent = round(self.aur_transferred/total_size, 2)
                if self.aur_transferred <= total_size:
                    target = "{transferred}/{size}".format(transferred = common.format_size(self.aur_transferred), size = common.format_size(total_size))
                else:
                    target = ""
            if target != self.previous_target:
                self.previous_target = target
                self.EmitTarget(target)
            if percent >= self.previous_percent + 1:
                self.previous_percent = percent
                self.EmitPercent(100*percent)
        error = ""
        self.cancel_download = False
        ftp = None
        total_size = 0
        self.aur_transferred = 0
        parsed_urls = []
        self.EmitIcon("cinnamon-installer-download")
        self.EmitTransactionCancellable(True)
        for url in url_list:
            url_components = urlparse(url)
            if url_components.scheme:
                parsed_urls.append(url_components)
        print(parsed_urls)
        for url_components in parsed_urls:
            if url_components.scheme == "http":
                print("hola")
                total_size += int(requests.get(url).headers["Content-Length"])
                print("bye")
            elif url_components.scheme == "ftp":
                ftp = FTP(url_components.netloc)
                ftp.login("anonymous", "")
                total_size += int(ftp.size(url_components.path))
        print(str(total_size))
        for url_components in parsed_urls:
            filename = url_components.path.split("/")[-1]
            print(filename)
            status = _("Downloading {pkgname}").format(pkgname = filename)+"..."
            role = status+"\n"
            if status != self.previous_status:
                self.previous_status = status
                self.EmitStatus(status, status)
            if role != self.previous_role:
                self.previous_role != role
                self.EmitRole(role)
            with open(os.path.join(path, filename), "wb") as f:
                if url_components.scheme == "http":
                    try:
                        r = requests.get(url, stream = True)
                        for chunk in r.iter_content(1024):
                            if self.cancel_download:
                                raise Exception("Download cancelled")
                                break
                            else:
                                write_file(f, chunk)
                    except Exception:
                        e = sys.exc_info()[1]
                        print(str(e))
                        self.cancel_download = False
                elif url_components.scheme == "ftp":
                    try:
                        ftp = FTP(url_components.netloc)
                        ftp.login("anonymous", "") 
                        ftp.retrbinary("RETR "+url_components.path, write_file, f, blocksize=1024)
                    except Exception:
                        e = sys.exc_info()[1]
                        print(str(e))
                        self.cancel_download = False
        return error

    '''
    def build_next(self, pkg, path):
        # Build successfully finished
        built = []
        # parse again PKGBUILD to have new pkg objects in case of a pkgver() function
        # was used so pkgver was changed during build process
        new_pkgs = aur.get_pkgs(path + "/PKGBUILD")
        # find built packages
        for new_pkg in new_pkgs:
            for item in os.listdir(path):
                if os.path.isfile(os.path.join(path, item)):
                    # add a * before pkgver if there an epoch variable
                    if fnmatch.fnmatch(item, "{}-*{}-*.pkg.tar.?z".format(new_pkg.name, new_pkg.version)):
                        built.append(os.path.join(path, item))
                        break
        if built:
            print("successfully built:" + built)
            self.build_proc = None
            if pkg in self.to_build:
                self.to_build.remove(pkg)
            # install built packages
            
            return built
        return None
    '''

    def _build_next(self):
        pkg = self.to_build[0]
        path = os.path.join(aur.srcpkgdir, aur.get_name(pkg))
        new_pkgs = aur.get_pkgs(path + "/PKGBUILD")
        # sources are identicals for splitted packages
        # (not complete) download(new_pkgs[0].source, path)
        action = _("Building {pkgname}").format(pkgname = pkg.name)+"..."
        self.EmitStatus(action, action)
        self.EmitRole(action+"\n")
        self.EmitIcon("cinnamon-installer-setup")
        self.EmitTarget("")
        self.EmitPercent(0)
        self.EmitCancellable(True)
        self.EmitNeedDetails(True)
        self.build_proc = subprocess.Popen(["makepkg", "-cf"], cwd = path, stdout = subprocess.PIPE, stderr=subprocess.STDOUT)
        GObject.timeout_add(100, self._check_finished_build, (path, pkg))

    def _finalize(self):
        if self._to_add_pyalpm() or self._to_remove_pyalpm():
            try:
                self.commit()
            except Exception:
                e = sys.exc_info()[1]
                print(str(e))
                self.release_all()
        elif self.to_build:
            # packages in to_build have no deps or makedeps
            # so we build and install the first one
            # the next ones will be built by the caller
            self._build_next()
            #return True
        #return self.to_build

    def mark_needed_pkgs_as_dep(self):
        for name in self.to_mark_as_dep.copy():
            if self._get_localpkg(name):
                error = self._set_pkg_reason(name, pyalpm.PKG_REASON_DEPEND)
                if error:
                    print(str(error))
                else:
                    self.to_mark_as_dep.discard(name)

    def check_updates(self, collect_type=None):
        self.EmitTransactionStart("")
        action = _("Checking for updates")+"..."
        self.EmitStatus(action, action)
        self.EmitRole(action+"\n")
        self.EmitIcon("cinnamon-installer-search")
        self.EmitTarget("")
        self.EmitPercent(0)
        self.EmitCancellable(False)
        self.EmitNeedDetails(False)
        self._check_updates(None, None)

    def _get_transaction_summary(self, dependencies, show_updates = True):
        infoConf = { "title": "", "description": "", "dependencies": {} }
        for index, msg in enumerate(["Install",
                                     "Reinstall",
                                     "Remove",
                                     "Purge",
                                     "Upgrade",
                                     "Downgrade",
                                     "Skip upgrade",
                                     "Build"]):
            if len(dependencies[index]) > 0:
                listPiter = infoConf["dependencies"]["%s" % msg] = []
                for pkg in dependencies[index]:
                    for object in self._map_package(pkg):
                        listPiter.append(str(object))
        msg = _("Please take a look at the list of changes below.")
        title = ""
        if len(infoConf["dependencies"].keys()) == 1:
            if len(dependencies[0]) > 0:
                title = _("Additional software has to be installed")
            elif len(dependencies[1]) > 0:
                title = _("Additional software has to be re-installed")
            elif len(dependencies[2]) > 0:
                title = _("Additional software has to be removed")
            elif len(dependencies[3]) > 0:
                title = _("Additional software has to be purged")
            elif len(dependencies[4]) > 0:
                title = _("Additional software has to be upgraded")
            elif len(dependencies[5]) > 0:
                title = _("Additional software has to be downgraded")
            elif len(dependencies[6]) > 0:
                title = _("Updates will be skipped")
        else:
            title = _("Additional changes are required")

        total_size = self._estimate_size(dependencies)
        if total_size < 0:
            msg += "\n"
            msg += (_("%sB of disk space will be freed.") %
                    self._format_size(total_size))
        elif total_size > 0:
            msg += "\n"
            msg += (_("%sB more disk space will be used.") %
                    self._format_size(total_size))

        infoConf["title"] = title
        infoConf["description"] = msg
        return infoConf

    def _map_package(self, pkg):
        return [pkg]

    def _get_dependencies(self, pkgToTrans=None):
                            #In  RI  Re  Pu  Up  Do  Sk  Bu
        transaction_dict = [ [], [], [], [], [], [], [], [] ]
        for pkg in self.to_build:
            transaction_dict[7].append(pkg.name+" "+pkg.version)
        _to_remove = sorted(self._to_remove_pyalpm())
        for name, version in _to_remove:
            #if name not in self.pkgToTrans:
            transaction_dict[2].append(name+" "+version)
        others = sorted(self._to_add_pyalpm())
        for name, version, dsize in others:
            #if name not in self.pkgToTrans:
            pkg = self._get_localpkg(name)
            if pkg:
                comp = pyalpm.vercmp(version, pkg.version)
                if comp == 1:
                    transaction_dict[4].append((name+" "+version, dsize))
                elif comp == 0:
                    transaction_dict[1].append((name+" "+version, dsize))
                elif comp == -1:
                    transaction_dict[5].append((name+" "+version, dsize))
            else:
                transaction_dict[0].append((name+" "+version, dsize))
        return transaction_dict
    '''
    def get_transaction_sum(self):
        transaction_dict = {"to_remove": [], "to_build": [], "to_install": [], "to_update": [], "to_reinstall": [], "to_downgrade": []}
        for pkg in self.to_build:
            transaction_dict["to_build"].append(pkg.name+" "+pkg.version)
        _to_remove = sorted(self._to_remove_pyalpm())
        for name, version in _to_remove:
            transaction_dict["to_remove"].append(name+" "+version)
        others = sorted(self._to_add_pyalpm())
        for name, version, dsize in others:
            pkg = self._get_localpkg(name)
            if pkg:
                comp = executer.pyalpm.vercmp(version, pkg.version)
                if comp == 1:
                    transaction_dict["to_update"].append((name+" "+version, dsize))
                elif comp == 0:
                    transaction_dict["to_reinstall"].append((name+" "+version, dsize))
                elif comp == -1:
                    transaction_dict["to_downgrade"].append((name+" "+version, dsize))
            else:
                transaction_dict["to_install"].append((name+" "+version, dsize))
        #~ if transaction_dict["to_build"]:
            #~ print("To build:" + str([name for name in transaction_dict["to_build"]]))
        #~ if transaction_dict["to_install"]:
            #~ print("To install:" + str([name for name, size in transaction_dict["to_install"]]))
        #~ if transaction_dict["to_reinstall"]:
            #~ print("To reinstall:" + str([name for name, size in transaction_dict["to_reinstall"]]))
        #~ if transaction_dict["to_downgrade"]:
            #~ print("To downgrade:" + str([name for name, size in transaction_dict["to_downgrade"]]))
        #~ if transaction_dict["to_remove"]:
            #~ print("To remove:" + str([name for name in transaction_dict["to_remove"]]))
        #~ if transaction_dict["to_update"]:
            #~ print("To update:" + str([name for name, size in transaction_dict["to_update"]]))
        return transaction_dict
    '''
    def _estimate_size(self, dependecies):
        dsize = 0
        if dependecies[0]:#install
            i = 0
            while i < len(dependecies[0]):
                dsize += dependecies[0][i][1]
                i += 1
        if dependecies[1]:#reinstall
            i = 0
            while i < len(dependecies[1]):
                dsize += dependecies[1][i][1]
                i += 1
        #if dependecies[2]:#remove
        #    i = 1
        #    while i < len(dependecies[2]):
        #        dsize -= dependecies2][i][1]
        #        i += 1
        if dependecies[4]:#update
            i = 0
            while i < len(dependecies[4]):
                dsize += dependecies[4][i][1]
                i += 1
        if dependecies[5]:#downgrade
            i = 0
            while i < len(dependecies[5]):
                dsize += dependecies[5][i][1]
                i += 1
        return dsize

    '''
    def set_transaction_sum(self, show_updates = True):
        dsize = 0
        
        self.mainApp._transactionSum.clear()
        transaction_dict = self.get_transaction_sum()
        self.mainApp._sumTopLabel.set_markup("<big><b>{}</b></big>".format(_("Transaction Summary")))
        if transaction_dict["to_remove"]:
            self.mainApp._transactionSum.append([_("To remove")+":", transaction_dict["to_remove"][0]])
            i = 1
            while i < len(transaction_dict["to_remove"]):
                self.mainApp._transactionSum.append(["", transaction_dict["to_remove"][i]])
                i += 1
        if transaction_dict["to_downgrade"]:
            self.mainApp._transactionSum.append([_("To downgrade")+":", transaction_dict["to_downgrade"][0][0]])
            dsize += transaction_dict["to_downgrade"][0][1]
            i = 1
            while i < len(transaction_dict["to_downgrade"]):
                self.mainApp._transactionSum.append(["", transaction_dict["to_downgrade"][i][0]])
                dsize += transaction_dict["to_downgrade"][i][1]
                i += 1
        if transaction_dict["to_build"]:
            self.mainApp._transactionSum.append([_("To build")+":", transaction_dict["to_build"][0]])
            i = 1
            while i < len(transaction_dict["to_build"]):
                self.mainApp._transactionSum.append(["", transaction_dict["to_build"][i]])
                i += 1
        if transaction_dict["to_install"]:
            self.mainApp._transactionSum.append([_("To install")+":", transaction_dict["to_install"][0][0]])
            dsize += transaction_dict["to_install"][0][1]
            i = 1
            while i < len(transaction_dict["to_install"]):
                self.mainApp._transactionSum.append(["", transaction_dict["to_install"][i][0]])
                dsize += transaction_dict["to_install"][i][1]
                i += 1
        if transaction_dict["to_reinstall"]:
            self.mainApp._transactionSum.append([_("To reinstall")+":", transaction_dict["to_reinstall"][0][0]])
            dsize += transaction_dict["to_reinstall"][0][1]
            i = 1
            while i < len(transaction_dict["to_reinstall"]):
                self.mainApp._transactionSum.append(["", transaction_dict["to_reinstall"][i][0]])
                dsize += transaction_dict["to_reinstall"][i][1]
                i += 1
        if show_updates:
            if transaction_dict["to_update"]:
                self.mainApp._transactionSum.append([_("To update")+":", transaction_dict["to_update"][0][0]])
                dsize += transaction_dict["to_update"][0][1]
                i = 1
                while i < len(transaction_dict["to_update"]):
                    self.mainApp._transactionSum.append(["", transaction_dict["to_update"][i][0]])
                    dsize += transaction_dict["to_update"][i][1]
                    i += 1
        else:
            for name, size in transaction_dict["to_update"]:
                dsize += size
        if dsize == 0:
            self.mainApp._sumBottomLabel.set_markup("")
        else:
            self.mainApp._sumBottomLabel.set_markup("<b>{} {}</b>".format(_("Total download size:"), common.format_size(dsize)))
    '''

    def system_upgrade(self, show_updates = True, downgrade = False, collect_type=None):
        syncfirst, updates = self.available_updates
        if updates:
            self.EmitTransactionStart("")
            ########progress_buffer
            self.to_update.clear()
            self.to_add.clear()
            self.to_remove.clear()
            self.EmitStatus(_("Preparing")+"...", _("Preparing")+"...")
            self.EmitIcon("cinnamon-installer--setup")
            self.EmitTarget("")
            self.EmitPercent(0)
            ########progress_buffer.delete(progress_buffer.get_start_iter(), progress_buffer.get_end_iter())
            self.EmitTransactionCancellable(False)
            #progress_expander.set_visible(True)
            #ProgressWindow.show()
            for name, version, db, tarpath, size in updates:
                if db == "AUR":
                    # call AURPkg constructor directly to avoid a request to AUR
                    infos = {"name": name, "version": version, "Description": "", "URLPath": tarpath}
                    pkg = aur.AURPkg(infos)
                    self.to_build.append(pkg)
                else:
                    self.to_update.add(name)
            error = ""
            if syncfirst:
                self.EmitTransactionCancellable(True)
                error += self.init_transaction()
                if not error:
                    for name in self.to_update:
                        error += self._add_pkg(name)
                        if not error:
                            error += self._prepare()
            else:
                if self.to_build:
                    # check if packages in to_build have deps or makedeps which need to be install first
                    # grab errors differently here to not break regular updates
                    _error = self.check_to_build()
                if self.to_update or self.to_add:
                    self.EmitTransactionCancellable(True)
                    error += self.init_transaction()
                    if not error:
                        if self.to_update:
                            error += self._sys_upgrade(downgrade)
                        _error = ""
                        for name in self.to_add:
                            _error += self._add_pkg(name)
                        if _error:
                            print(str(_error))
                        if not error:
                            error += self._prepare()
            if not error:
                dependencies = self._get_dependencies()
                if show_updates or len(dependencies) != 0:
                    print("Dep:" + str(dependencies))
                    info_conf = self._get_transaction_summary(dependencies)
                    print("Info:" + str(info_conf["dependencies"]))
                    self.EmitTransactionConfirmation(info_conf)
                else:
                    self._finalize()
            if error:#ShowError?
                self.release_all()
            return error

    def EmitStatus(self, status, translation):
        self.emit("EmitStatus", status, translation)

    def EmitRole(self, role):
        self.emit("EmitRole", role)

    def EmitNeedDetails(self, need):
        self.emit("EmitNeedDetails", need)

    def EmitIcon(self, icon):
        self.emit("EmitIcon", icon)

    def EmitTarget(self, target):
        self.emit("EmitTarget", target)

    def EmitPercent(self, percent):
        self.emit("EmitPercent", percent)

    def EmitDownloadPercentChild(self, id, img, name, percent, details):
        self.emit("EmitDownloadPercentChild", id, img, name, percent, details)

    def EmitDownloadChildStart(self, restar_all):
        self.emit("EmitDownloadChildStart", restar_all)

    def EmitLogError(self, message):
        self.emit("EmitLogError", message)

    def EmitLogWarning(self, message):
        self.emit("EmitLogWarning", message)

    def EmitAvailableUpdates(self, syncfirst, updates):
        self.emit("EmitAvailableUpdates", syncfirst, updates)

    def EmitTransactionStart(self, message):
        self.lock_trans.acquire()
        self.emit("EmitTransactionStart", message)

    def EmitTransactionDone(self, message):
        self.emit("EmitTransactionDone", message)

    def EmitTransactionError(self, title, description):
        self.emit("EmitTransactionError", title, description)

    def EmitTransactionConfirmation(self, info_config):
        self.emit("EmitTransactionConfirmation", info_config)
        self.client_response = False
        self.client_condition.acquire()
        while not self._client_confirm_trans():
            self.client_condition.wait()
        self.client_condition.release()

    def EmitTransactionCancellable(self, cancellable):
        self.emit("EmitTransactionCancellable", cancellable)

    def EmitTerminalAttached(self, attached):
        self.emit("EmitTerminalAttached", attached)

    def EmitConflictFile(self, old, new):
        self.emit("EmitConflictFile", old, new)

    def EmitMediumRequired(self, medium, title, desc):
        self.emit("EmitMediumRequired", medium, title, desc)

    def EmitChooseProvider(self, info_prov):
        self.emit("EmitChooseProvider", info_prov)
        self.client_response = False
        self.client_condition.acquire()
        while not self._client_confirm_trans():
            self.client_condition.wait()
        self.client_condition.release()

    def EmitReloadConfig(self, message):
        # recheck aur updates next time
        self.aur_updates_checked = False
        # reload config
        config.installer_conf.reload()
        self.emit("EmitReloadConfig", message)
