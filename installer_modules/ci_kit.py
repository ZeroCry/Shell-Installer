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

from gi.repository import PackageKitGlib as packagekit
from gi.repository import GObject, Gio, GLib

import re, os, sys
from time import sleep
from multiprocessing import Process

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

CI_STATUS = {
    "status-resolving-dep": "RESOLVING_DEPENDENCIES",
    "status-setting-up": "SETTING-UP",
    "status-loading-cache": "LOADING_CACHE",
    "status-authenticating": "AUTHENTICATING",
    "status-downloading": "DOWNLOADING",
    "status-downloading-repo": "DOWNLOADING_REPO",
    "status-running": "RUNNING",
    "status-committing": "COMMITTING",
    "status-installing": "INSTALLING",
    "status-removing": "REMOVING",
    "status-finished": "FINISHED",
    "status-waiting": "WAITING",
    "status-waiting-lock": "WAITING_LOCK",
    "status-waiting-medium": "WAITING_MEDIUM",
    "status-waiting-config-file-prompt": "WAITING_CONFIG_FILE",
    "status-cancelling": "CANCELLING",
    "status-cleaning-up": "CLEANING_UP",
    "status-query": "QUERY"
}
'''
def make_locale_string():
    loc = locale.getlocale(locale.LC_MESSAGES)
    if loc[1]:
        return loc[0] + "." + loc[1]
    return loc[0]

def get_installed_files(pkclient, pkgname):
    p = self._get_one_package(pkgname)
    if not p:
        return []
    res = pkclient.get_files((p.get_id(),), None, self._on_progress_changed, None)
    files = res.get_files_array()
    if not files:
        return []
    return files[0].get_property("files")

def _get_one_package(self, pkgname, pfilter=packagekit.FilterEnum.NONE, cache=USE_CACHE):
   LOG.debug("package_one %s", pkgname) #, self._cache.keys()
   ps = self._get_packages(pkgname, pfilter)
   if not ps:
      # also keep it in not found, to prevent further calls of resolve
      if pkgname not in self._notfound_cache_pkg:
          LOG.debug("blacklisted %s", pkgname)
          self._notfound_cache_pkg.append(pkgname)
          return None
   return ps[0]

def _get_packages(self, pkgname, pfilter=packagekit.FilterEnum.NONE):
    """ make sure we're ready and have a working cache """
    if not self._ready:
        return None
    """ resolve a package name into a PkPackage object or return None """
    LOG.debug("fetch packages for %s", pkgname) #, self._cache.keys()
    if pfilter in (packagekit.FilterEnum.NONE, packagekit.FilterEnum.NOT_SOURCE):
        cache_pkg_filter = self._cache_pkg_filter_none
    elif pfilter in (packagekit.FilterEnum.NEWEST,):
        cache_pkg_filter = self._cache_pkg_filter_newest
    else:
        cache_pkg_filter = None
    # if cache and cache_pkg_filter is not None and (pkgname in cache_pkg_filter.keys()):
    # return cache_pkg_filter[pkgname]
    pfilter = 1 << pfilter
    # we never want source packages
    pfilter |= 1 << packagekit.FilterEnum.NOT_SOURCE
    pkgs = []
    if pkgname in self._pkgs_cache:
        pkgs.append(self._pkgs_cache[pkgname])
    if pkgs:
        LOG.debug("Found package: %s" % pkgname)
    #print("Package: " + str(self._pkgs_cache[pkgname]))
    return pkgs
'''

def progress_cb(status_pk, typ, data=None):
    pass
    #if status_pk.get_property("package"):
        #print("Pachet " + str(status_pk.get_property("package")) + " "+ str(status_pk.get_property("package-id")))
        #if status_pk.get_property("package"):
            #print(str(status_pk.get_property("package").get_name()))
    #print(str(typ) + " " + str(status_pk.get_property("package")))

def format_error(data):
    errstr = data[0].strip("\n")
    #errno = data[1]
    #detail = data[2]
    #if detail:
        # detail is a list of "\n" terminated strings
    return "{}:\n".format(errstr) #+ "".join(i for i in detail)
    #else:
    #    return errstr

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
        "EmitTransactionError": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_BOOLEAN,)),
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
        self.previous_package = ""
        self.previous_percent = 0
        self.total_size = 0
        self.already_transferred = 0
        self.aur_updates_checked = False
        self.aur_updates_pkgs = []
        self.localdb = None
        self.syncdbs = None
        self.transID = None
        self.cancelTransaction = None;
        self._current_pkg_to_installed = None;
        self._current_pkg_to_removed = None;
        self.client = packagekit.Client();
        self.lastedSearch = {}
        self.status_dir = Gio.file_new_for_path("/var/lib/PackageKit/transactions.db")
        self.monitor = self.status_dir.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.oldCacheAge = self.client.get_cache_age()
        self.module = None
        if self.monitor:
            self.monitorID = self.monitor.connect("changed", self._changed)

    def _changed(self, monitor, file1, file2, evt_type):
        try:
            result = self.client.get_old_transactions(1, None, self._progress_pcb, None)
            trans = result.get_transaction_array()[0]
            if trans and trans.get_succeeded() and  self.transID != trans.get_id():
                self.transID = trans.get_id()
                role = trans.get_role()
                if (role == packagekit.RoleEnum.INSTALL_PACKAGES or role == packagekit.RoleEnum.REMOVE_PACKAGES or
                    role == packagekit.RoleEnum.ROLE_REFRESH_CACHE or role == packagekit.RoleEnum.ROLE_UPGRADE_SYSTEM):
                    self.lastedSearch = {}
        except GLib.GError:
            e = sys.exc_info()[1]
            error = format_error(e.args)
            print("error " + str(error))
        pass

    def need_root_access(self):
        return False

    def have_terminal(self):
        return False

    def set_terminal(self, terminal):
        pass

    def is_service_idle(self):
        return self.client.idle

    def refresh_cache(force_update = False, collect_type=None):
        pass

    def release_all(self):
        pass

    def load_cache(self, forced=False, async=False, collect_type=None):
        pass

    def have_cache(self, collect_type=None):
        return True

    def set_parent_module(self, module):
        self.module = module

    def get_parent_module(self):
        return self.module

    def get_cache_folder(self, collect_type=None):
        return ""

    def search_files(self, path, loop, result):
        local_packages = []
        result.append(local_packages)
        try:
            print(path)
            resultP = self.client.search_files(packagekit.FilterEnum.INSTALLED, [path,], None, self._progress_cb, None)
            pkgs = resultP.get_package_array()
            if ((pkgs) and (len(pkgs) > 0)):
                local_packages.append(pkgs[0].get_name())
        except GLib.GError:
            e = sys.exc_info()[1]
            error = format_error(e.args)
            print("error " + str(error))
        sleep(0.1)
        loop.quit()

    def get_all_local_packages(self, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            resultP = self.client.get_packages(packagekit.FilterEnum.INSTALLED, None, self._progress_pcb, None);
            pkgs = resultP.get_package_array()
            if pkgs:
                for pkg in pkgs:
                    if (not (pkg.get_name() in local_packages)):
                        local_packages.append(pkg.get_name())
        except GLib.GError:
            e = sys.exc_info()[1]
            error = format_error(e.args)
            print("error " + str(error))
        sleep(0.1)
        loop.quit()

    def get_all_remote_packages(self, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            resultP = self.client.get_packages(packagekit.FilterEnum.NOT_INSTALLED, None, self._progress_pcb, None);
            pkgs = resultP.get_package_array()
            if pkgs:
                for pkg in pkgs:
                    if (not (pkg.get_name() in local_packages)):
                        local_packages.append(pkg.get_name())
        except GLib.GError:
            e = sys.exc_info()[1]
            error = format_error(e.args)
            print("error " + str(error))
        sleep(0.1)
        loop.quit()

    def get_package_info(self, loop, result, pkg_id, collect_type):
        loop.quit()

    def get_local_packages(self, packages, loop, result, collect_type=None):
        result = {}
        try:
            pkgs = self._get_installed(packages)
            if pkgs:
                for pkg in pkgs:
                    if (not (pkg in result)):
                        result[pkg.get_name()] = pkg
        except GLib.GError:
            e = sys.exc_info()[1]
            error = format_error(e.args)
            print("error " + str(error))
            self.EmitTransactionError(str(error), _("Transaction fail."))
            return None
        return result

    def get_remote_packages(self, packages, loop, result, collect_type=None):
        result = {}
        try:
            pkgs = self._get_aviable(packages)
            if pkgs:
                for pkg in pkgs:
                    if (not (pkg in result)):
                        result[pkg.get_name()] = pkg
        except GLib.GError:
            e = sys.exc_info()[1]
            error = format_error(e.args)
            print("error " + str(error))
            self.EmitTransactionError(str(error), _("Transaction fail."))
            return None
        return result

    def get_local_search(self, pattern, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            packages = pattern.split(",")
            result = self.client.search_names(packagekit.FilterEnum.INSTALLED, packages, None, self._progress_pcb, None)
            #result = self.client.search_names_async(packagekit.FilterEnum.NONE, [pattern,], None, self._progress_cb, self._finished_search, None);
            #result = self.client.get_packages(packagekit.FilterEnum.NONE, None, self._progress_cb, None);
            pkgs = result.get_package_array()
            if pkgs:
                for pkg in pkgs:
                    if (not (pkg.get_name() in local_packages)):
                        local_packages.append(pkg.get_name())
        except GLib.GError:
            e = sys.exc_info()[1]
            error = format_error(e.args)
            print("error " + str(error))
        sleep(0.1)
        loop.quit()

    def get_remote_search(self, pattern, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            matchWordsPattern = pattern.split(",")
            quickList = self._getQuickSearch(pattern)
            if(quickList):
                for pkgName in quickList:
                    if(self._isMatching(matchWordsPattern, pkgName)):
                        local_packages.append(pkgName)
            else:
                result = self.client.search_names(packagekit.FilterEnum.NOT_INSTALLED, matchWordsPattern, None, self._progress_pcb, None)
                pkgs = result.get_package_array()
                if pkgs:
                    for pkg in pkgs:
                        if (not (pkg.get_name() in local_packages)) and (pkg.get_info() != packagekit.InfoEnum.INSTALLED):
                        #if (not (pkg.get_name() in local_packages)) and (not (self._isVersionInstalled(pkg.get_name(), pkgs))):
                            local_packages.append(pkg.get_name())
                self._tryToSave(pattern, local_packages)
        except GLib.GError:
            e = sys.exc_info()[1]
            error = format_error(e.args)
            print("error " + str(error))
        sleep(0.1)
        loop.quit()

    def _simulate_transaction_install(self, pkgs):
        ''' Returns a package names list of reverse dependencies
        which will be installed if the packages are installed.'''
        try:
            print("install start")
            #install
            #t_depends = self.client.get_depends(packages, exit_handler=self._on_exit)
            #packages = t_depends.result
            #remove
            #t_requires = self.client.get_requires(packages, exit_handler=self._on_exit)
            result = None
            listToAdd = []
                           #In  Rl  Rm  Pu  Up  Do  Sk
            dependencies = [[], [], [], [], [], [], []]
            if pkgs:
                self.cancelTransaction = Gio.Cancellable();
                for pkg in pkgs:
                    if (not (pkg.get_name() in listToAdd)):
                        listToAdd.append(pkg.get_id())
                if len(listToAdd) > 0:
                    # simulate AddPackages()
                    result = self.client.install_packages(2 ** packagekit.TransactionFlagEnum.SIMULATE,
                                                       listToAdd,
                                                       self.cancelTransaction,
                                                       self._progress_pcb, None)

                if((not self.cancelTransaction) or (self.cancelTransaction and self.cancelTransaction.is_cancelled())):
                    self.EmitTransactionError(_("Transaction cancel when we tray to simulate it:"), _("Transaction fail."))
                elif result:
                    self.cancelTransaction = None
                    listPkgs = result.get_package_array()
                    details = self._get_package_details(listPkgs)
                    if details:
                        for p, det in details:
                            if (p.get_info() == packagekit.InfoEnum.INSTALLED):
                                if det is not None:
                                    dependencies[4].append({"name":p.get_name(), "ver":p.get_version(), "size":det.get_property("size")})
                                else:
                                    dependencies[4].append({"name":p.get_name(), "ver":p.get_version(), "size":0})
                            else:
                                if det is not None:
                                    dependencies[0].append({"name":p.get_name(), "ver":p.get_version(), "size":det.get_property("size")})
                                else:
                                    dependencies[0].append({"name":p.get_name(), "ver":p.get_version(), "size":0})

                    return dependencies
                else:
                    self.EmitTransactionError(_("Nothing changed when we tray to simulate it:"), _("Transaction fail."))

        except GLib.GError:
            e = sys.exc_info()[1]
            self.cancelTransaction = None
            error = format_error(e.args)
            self.EmitTransactionError(str(error), _("Transaction fail."))
            print("error " + str(error))

        return None

    def _simulate_transaction_remove(self, pkgs):
        ''' Returns a package names list of reverse dependencies
        which will be removed if the packages are removed.'''
        error = ""
        try:
            result = None
            listToRemove = []
                           #In  Rl  Rm  Pu  Up  Do  Sk
            dependencies = [[], [], [], [], [], [], []]
            if pkgs:
                self.cancelTransaction = Gio.Cancellable();
                for pkg in pkgs:
                    if (not (pkg.get_name() in listToRemove)):
                        listToRemove.append(pkg.get_id())
                if len(listToRemove) > 0:
                    autoremove = False
                    # simulate RemovePackages()
                    result = self.client.remove_packages(2 ** packagekit.TransactionFlagEnum.SIMULATE,
                                                      listToRemove,
                                                      True, # allow deps
                                                      autoremove,
                                                      self.cancelTransaction,
                                                      self._progress_pcb, None)

                if((not self.cancelTransaction) or (self.cancelTransaction and self.cancelTransaction.is_cancelled())):
                    self.EmitTransactionError(_("Transaction cancel when we tray to simulate it:"), _("Transaction fail."))
                elif result:
                    self.cancelTransaction = None
                    listPkgs = result.get_package_array()
                    details = self._get_package_details(listPkgs)
                    if details:
                        for p, det in details:
                            if (p.get_info() == packagekit.InfoEnum.INSTALLED):
                                if det is not None:
                                    dependencies[4].append({"name":p.get_name(), "ver":p.get_version(), "size":det.get_property("size")})
                                else:
                                    dependencies[4].append({"name":p.get_name(), "ver":p.get_version(), "size":0})
                            else:
                                if det is not None:
                                    dependencies[2].append({"name":p.get_name(), "ver":p.get_version(), "size":det.get_property("size")})
                                else:
                                    dependencies[2].append({"name":p.get_name(), "ver":p.get_version(), "size":0})
                    return dependencies
                else:
                    self.EmitTransactionError(_("Nothing changed when we tray to simulate it:"), _("Transaction fail."))

        except GLib.GError:
            e = sys.exc_info()[1]
            self.cancelTransaction = None
            error = format_error(e.args)
            self.EmitTransactionError(str(error), _("Transaction fail."))
            print("error " + str(error))

    def commit(self):
        if self._current_pkg_to_installed:
            print("add")
            self.add(self._current_pkg_to_installed)
        if self._current_pkg_to_removed:
            print("remove")
            self.remove(self._current_pkg_to_removed)

    def remove(self, pkgs):
        error = ""
        try:
            listToRemove = []
            if pkgs:
                self.cancelTransaction = Gio.Cancellable();
                for pkg in pkgs:
                    if (not (pkg.get_id() in listToRemove)):
                        listToRemove.append(pkg.get_id())
                if len(listToRemove) > 0:
                    autoremove = False
                    res = self.client.remove_packages(packagekit.TransactionFlagEnum.NONE,
                                                      listToRemove,
                                                      True, # allow deps
                                                      autoremove,
                                                      self.cancelTransaction,
                                                      self._progress_cb, None)

                if((not self.cancelTransaction) or (self.cancelTransaction and self.cancelTransaction.is_cancelled())):
                    self.EmitTransactionError(_("Fail to process the removal of package(s) %s:").format(pkgs), _("Transaction cancel."))
                elif not res:
                    self.EmitTransactionError(_("Fail to process the removal of package %s:").format(pkgs), _("Transaction fail."))
                else:
                    self.EmitTransactionDone("")
                self.cancelTransaction = None

        except GLib.GError:
            e = sys.exc_info()[1]
            self.cancelTransaction = None
            error = format_error(e.args)

    def add(self, pkgs):
        error = ""
        try:
            self.cancelTransaction = Gio.Cancellable();
            listToAdd = []
            if pkgs:
                for pkg in pkgs:
                    if (not (pkg.get_id() in listToAdd)):
                        listToAdd.append(pkg.get_id())
                if len(listToAdd) > 0:
                    res = self.client.install_packages(packagekit.TransactionFlagEnum.NONE,
                                                      listToAdd,
                                                      self.cancelTransaction,
                                                      self._progress_cb, None)
                if not res:
                    self.EmitTransactionError(_("Fail to process the installation of package(s) %s:").format(pkgs), _("Transaction fail."))
                elif((not self.cancelTransaction) or (self.cancelTransaction and self.cancelTransaction.is_cancelled())):
                    self.EmitTransactionError(_("Fail to process the installation of package(s) %s:").format(pkgs), _("Transaction cancel."))
                else:
                    self.EmitTransactionDone("")
                self.cancelTransaction = None
        except GLib.GError:
            e = sys.exc_info()[1]
            error = format_error(e.args)
            self.EmitTransactionError(str(error), _("Fail to process the installation of package(s) %s.").format(pkgs))


    def prepare_transaction_install(self, pkgs, collect_type=None):
        to_add = None
        result = self.get_remote_packages(pkgs)
        #if self.releaseTransaction:#checked this...
        #   self.EmitTransactionCancel(_("Transaction fail."), result[0])
        if result and len(result) > 0:
            to_add = []
            notFound = []
            for name in pkgs:
                if not name in result:
                    notFound.append(name)
                else:
                    to_add.append(result[name])
        if len(notFound) > 0:
            to_add = None
            title = _("The package(s) {pkgname} is already installed or not exist:").format(pkgname = str(notFound))
            message = _("Transaction fail.")
            self.EmitTransactionError(title, message)
        elif to_add and len(to_add) > 0:
            result_sim = self._simulate_transaction_install(to_add)
            if result_sim:
                # we need to install packages here
                self._current_pkg_to_installed = to_add
                print(str(self._current_pkg_to_installed))
                self._confirm_deps(result_sim)
        else:
            title = _("Not package(s) {pkgname} founds:").format(pkgname = str(notFound))
            message = _("Transaction fail.")
            self.EmitTransactionError(title, message)

    def prepare_transaction_remove(self, pkgs, collect_type=None):
        to_remove = None
        self._current_pkg = None
        result = self.get_local_packages(pkgs)
        #if self.releaseTransaction:#checked this...
        #   self.EmitTransactionCancel(_("Transaction fail."), result[0])
        if result and len(result) > 0:
            to_remove = []
            notFound = []
            for name in pkgs:
                if not name in result:
                    notFound.append(name)
                else:
                    to_remove.append(result[name])
        if len(notFound) > 0:
            title = _("The package(s) {pkgname} is not already installed or not exist:").format(pkgname = str(notFound))
            message = _("Transaction fail.")
            self.EmitTransactionError(title, message)
        elif to_remove and len(to_remove) > 0:
            result_sim = self._simulate_transaction_remove(to_remove)
            if result_sim:
                # we need to install packages here
                self._current_pkg_to_removed = to_remove
                print(str(self._current_pkg_to_removed))
                self._confirm_deps(result_sim)
        else:
            title = _("Not package(s) {pkgname} founds:").format(pkgname = str(notFound))
            message = _("Transaction fail.")
            self.EmitTransactionError(title, message)

    def prepare_transaction_commit(self, packages_status, collect_type=None): #new and I don't know how do it
        pass #posible we need to implemented this resolving dependencies of the packages.

    def _confirm_deps(self, dependencies):
        dsize = 0
        info_config = self._get_transaction_summary(dependencies)
        self.EmitTransactionConfirmation(info_config)

    def _get_transaction_summary(self, dependencies, show_updates = True):
        infoConf = { "title": "", "description": "", "dependencies": {} }
        for index, msg in enumerate(["Install",
                                     "Reinstall",
                                     "Remove",
                                     "Purge",
                                     "Upgrade",
                                     "Downgrade",
                                     "Skip upgrade"]):
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

        total_size, dsize = self._estimate_size(dependencies)
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

    def resolve_config_file_conflict(self, replace, old, new):
        print("what?")

    def resolve_medium_required(self, medium):
        print("what?")

    def resolve_package_providers(self, provider_select):
        print("what?")

    def add_choose(self, depend):
        print("what?")

    def check_updates(self, success=None, nosuccess=None, collect_type=None):
        print("not implemented")

    def system_upgrade(self, show_updates = True, downgrade = False, collect_type=None):
       print("not implemented")

    def write_config(self, array, collect_type=None):
       print("not implemented")

    def resolve(self, depend):
        transaction_dict = {"to_remove": [], "to_install": [], "to_update": [], "to_reinstall": [], "to_downgrade": []}
        _to_transaction = sorted(result)
        for name, version, dtype, dsize in _to_transaction:
            if (dtype == 1):
                transaction_dict["to_install"].append((name+" "+version, dsize))
            elif (dtype == 2):
                transaction_dict["to_remove"].append(name+" "+version)
            elif (dtype == 3):
                transaction_dict["to_update"].append(name+" "+version)
        '''
        others
        for name, version, dsize in others:
            pkg = self.get_localpkg(name)
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
        '''
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

    def _estimate_size(self, dependencies):
        size_list = [0, 0, 0, 0, 0, 0, 0]
        pos = 0
        for pkg_dep in dependencies:
            for pkg in pkg_dep:
                size_list[pos] += pkg["size"]
        total_size = 0
        total_size += size_list[0]
        total_size += size_list[1]
        total_size += size_list[2]
        total_size += size_list[3]
        total_size += size_list[4]
        total_size += size_list[5]
        total_size += size_list[6]
        return [total_size, size_list]

    def _format_size(self, size):
        unit = "Bt"
        if size > 1000:
            size = size/1000
            unit = "Kb"
            if size > 1000:
                size = size/1000
                unit = "Mb"
                if size > 1000:
                    size = round(size/1000, 2)
                    unit = "Gb"
                else:
                    size = round(size, 2)
            else:
                size = round(size, 2)
        else:
            size = round(size, 2)
        return size

    def _map_package(self, pkg):
        return [pkg]

    def cancel(self):
        try:
            if(self.cancelTransaction):
                self.cancelTransaction.cancel()
                self.cancelTransaction = None
        except Exception:
            e = sys.exc_info()[1]
            print("error " + str(e))
            pass
        sleep(0.1)

    def _isVersionInstalled(self, name, pkgs):
        for pkg in pkgs:
            if (pkg.get_name() == name) and (pkg.get_info() == packagekit.InfoEnum.INSTALLED):
                return True
        return False

    def _get_installed(self, packages):
        result = self.client.resolve(packagekit.FilterEnum.INSTALLED, packages, None, self._progress_pcb, None)
        return result.get_package_array()

    def _get_aviable(self, packages):
        result = self.client.resolve(packagekit.FilterEnum.NOT_INSTALLED, packages, None, self._progress_pcb, None)
        return result.get_package_array()

    def _get_package_details(self, pkgs):
        pkgsId = []
        for pkg in pkgs:
            if (not (pkg.get_id() in pkgsId)):
                pkgsId.append(pkg.get_id())
        try:
            task = packagekit.Task()
            result = task.get_details_sync(pkgsId, None, self._progress_pcb, None)
        except GObject.GError:
            e = sys.exc_info()[1]
            return None
        pkgsDetails = result.get_details_array()
        if not pkgsDetails:
            return None
        resultDetails = []
        currVal = 0
        for pkg in pkgs:
            for details in pkgsDetails:
                if (pkg.get_id() == details.get_property("package-id")):
                    resultDetails.append((pkg, details))
                    break
            if (len(resultDetails) == currVal):
                resultDetails.append((pkg, None))
            currVal = currVal + 1
        return resultDetails

    def _tryToSave(self, pattern, unInstalledPackages):
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

    def _getQuickSearch(self, pattern):
        for key in self.lastedSearch:
            if(key in pattern):
                return self.lastedSearch[key][0]
        return None

    def _isMatching(self, matchWordsPattern, packageName):
        for word in matchWordsPattern:
            if(word in packageName):
                return True
        return False

    def _progress_pcb(self, status_pk, typ, data=None):
        status = self.previous_status
        role = self.previous_role
        icon = self.previous_icon
        if(typ.value_name == "PK_PROGRESS_TYPE_PERCENTAGE"):
           percent = status_pk.get_property("percentage")
           if((percent > 0) and (percent != self.previous_percent)):
               self.previous_percent = percent
               self.EmitPercent(0.2*percent)
               self.EmitTarget(str(int(2*percent/10))+"%")
               #print("Preparing percentage: " + str(percent))
        elif(typ.value_name == "PK_PROGRESS_TYPE_STATUS"):
            if(status_pk.get_property("status") == packagekit.StatusEnum.RUNNING):
                icon = "cinnamon-installer-search"
                status = "RESOLVING_DEPENDENCIES"
                role = status
        if icon != self.previous_icon:
            self.previous_icon = icon
            self.EmitIcon(icon)
        if status != self.previous_status:
            self.previous_status = status
            self.EmitStatus(status, "")
        if role != self.previous_role:
            self.previous_role = role
            self.EmitRole(role)
        #if status_pk.get_property("package"):
        #    print("Pachet " + str(status_pk.get_property("package")))
        #    if status_pk.get_property("package-id"):
        #        print(str(status_pk.get_property("package").get_name()) + " " + str(status_pk.get_property("package-id")))
        #elif(typ.value_name == "PK_PROGRESS_TYPE_ROLE"):
        #    print(packagekit.role_enum_to_string(status_pk.get_property("role")))
        #elif(typ.value_name == "PK_PROGRESS_TYPE_STATUS"):
        #    print(packagekit.status_enum_to_string(status_pk.get_property("status")))
        #print("Preparing: " + str(typ) + " " + str(status_pk.get_property("package")))

    def _progress_cb(self, status_pk, typ, data=None):
        status = self.previous_status
        role = self.previous_role
        icon = self.previous_icon
        target = self.previous_target
        package = self.previous_package
        if(typ.value_name == "PK_PROGRESS_TYPE_PERCENTAGE"):
           percent = status_pk.get_property("percentage")
           if((percent > 0) and (percent != self.previous_percent)):
               self.previous_percent = percent
               self.EmitPercent(0.8*percent + 20)
               target = str(int(20 + 4*percent/5)) + " %"
               #print("percent:" + str(percent))
        elif(typ.value_name == "PK_PROGRESS_TYPE_ROLE"):
            roleProp = status_pk.get_property("role")
            if(roleProp == packagekit.RoleEnum.DOWNLOAD_PACKAGES):
                status = "DOWNLOADING"
            elif(roleProp == packagekit.RoleEnum.INSTALL_PACKAGES):
                status = "INSTALLING"
            elif(roleProp == packagekit.RoleEnum.REMOVE_PACKAGES):
                status = "REMOVING"
        elif(typ.value_name == "PK_PROGRESS_TYPE_STATUS"):
            statusProp = status_pk.get_property("status")
            if(statusProp == packagekit.StatusEnum.DOWNLOAD):
                status = "DOWNLOADING"
                #self.EmitPercent(200)
                role = status
                icon = "cinnamon-installer-download"
            elif(statusProp == packagekit.StatusEnum.COMMIT):
                status = "COMMITTING"
                role = status
            elif(statusProp == packagekit.StatusEnum.TEST_COMMIT):
                status = "COMMITTING"
                role = status
            elif(statusProp == packagekit.StatusEnum.SETUP):
                status = "SETTING-UP"
                role = status
            elif(statusProp == packagekit.StatusEnum.RUNNING):
                status = "RUNNING"
                role = status
            elif(statusProp == packagekit.StatusEnum.SIG_CHECK):
                status = "CHECKING"
                role = status
            elif(statusProp == packagekit.StatusEnum.INSTALL):
                status = "INSTALLING" 
                role = status
                icon = "cinnamon-installer-install"
            elif(statusProp == packagekit.StatusEnum.DEP_RESOLVE):
                status = "RESOLVING_DEPENDENCIES"
                role = status
            elif(statusProp == packagekit.StatusEnum.REMOVE):
                status = "REMOVING"
                role = status
                icon = "cinnamon-installer-delete"
            elif(statusProp == packagekit.StatusEnum.FINISHED):
                status = "FINISHED"
                role = status
                self.previous_percent = -1
            elif(statusProp == packagekit.StatusEnum.WAITING_FOR_AUTH):
                status = "WAITING"
                role = status
                icon = "cinnamon-installer-setup"
        elif(typ.value_name == "PK_PROGRESS_TYPE_PACKAGE"):
            package = status_pk.get_property("package").get_name()
            if self.previous_package != package:
                self.previous_package = package
                send_log = ""
                if self.previous_role == _("Installing")+"...":
                    send_log = _("Installing {pkgname}").format(pkgname = package) + "..."
                elif self.previous_role == _("Removing")+"...":
                    send_log = _("Removing {pkgname}").format(pkgname = package) + "..."
                self.EmitRole(send_log)
        elif(typ.value_name == "PK_PROGRESS_TYPE_ITEM_PROGRESS"):
            progress = status_pk.get_property("item_progress")
            if(progress):
                statusItem = progress.get_status()
                if(statusItem == packagekit.StatusEnum.DOWNLOAD):
                    package = status_pk.get_property("package").get_name()
                    percent = progress.get_percentage()
                    print("name:" + package + " percentages:" + str(percent))

        if package != self.previous_package:
            self.previous_package = package
        if target != self.previous_target:
            self.previous_target = target
            self.EmitTarget(target)
        if status != self.previous_status:
            self.previous_status = status
            self.EmitStatus(status, "")
        if role != self.previous_role:
            self.previous_role = role
            self.EmitRole(role)
        if icon != self.previous_icon:
            self.previous_icon = icon
            self.EmitIcon(icon)

    def EmitStatus(self, status, status_translation):
        if status == "":
            status_ci = "DETAILS"
        else:
            status_ci = status
        self.emit("EmitStatus", status_ci, status_translation)

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
        self.emit("EmitTransactionStart", message)

    def EmitTransactionDone(self, message):
        self.emit("EmitTransactionDone", message)

    def EmitTransactionError(self, title, description):
        self.emit("EmitTransactionError", title, description)

    def EmitTransactionConfirmation(self, info_config):
        self.emit("EmitTransactionConfirmation", info_config)

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
        #self.client_response = False
        #self.client_condition.acquire()
        #while not self._client_confirm_trans():
        #    self.client_condition.wait()
        #self.client_condition.release()

    def EmitReloadConfig(self, message):
        # recheck aur updates next time
        self.aur_updates_checked = False
        # reload config
        config.installer_conf.reload()
        self.emit("EmitReloadConfig", message)
