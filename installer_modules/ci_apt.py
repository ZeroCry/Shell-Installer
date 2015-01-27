#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# Cinnamon Installer
#
# Authors: Lester Carballo Pérez <lestcape@gmail.com>
#
# Froked from Ubuntu aptdaemon
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

import subprocess, os, glob, fnmatch, signal, re, sys, time, stat
from gi.repository import Gtk, GObject, Polkit
from threading import Thread

ABS_PATH = os.path.abspath(__file__)
DIR_PATH = os.path.dirname(os.path.dirname(ABS_PATH)) + "/"

import aptdaemon.client
import aptdaemon.errors
from aptdaemon.enums import *

import apt_pkg, apt
from apt.cache import FilteredCache
from defer import inline_callbacks
from defer.utils import deferable

# i18n
import gettext, locale
LOCALE_PATH = DIR_PATH + "locale"
DOMAIN = "cinnamon-installer"
locale.bindtextdomain(DOMAIN , LOCALE_PATH)
locale.bind_textdomain_codeset(DOMAIN, "UTF-8")
gettext.bindtextdomain(DOMAIN, LOCALE_PATH)
gettext.bind_textdomain_codeset(DOMAIN, "UTF-8")
gettext.textdomain(DOMAIN)
#_ = gettext.gettext
_ = lambda msg: gettext.dgettext("aptdaemon", msg)

from gi.repository import GObject, Gtk, GLib, Gio

CI_STATUS = {
    "status-resolving-dep": "RESOLVING_DEPENDENCIES",
    "status-setting-up": "SETTING-UP",
    "status-loading-cache": "LOADING_CACHE",
    "status-authenticating": "AUTHENTICATING",
    "status-downloading": "DOWNLOADING",
    "status-downloading-repo": "DOWNLOADING_REPO",
    "status-running": "RUNNING",
    "status-committing": "COMMITTING",
    #"status-installing": "INSTALLING",
    #"status-removing": "REMOVING",
    "status-finished": "FINISHED",
    "status-waiting": "WAITING",
    "status-waiting-lock": "WAITING_LOCK",
    "status-waiting-medium": "WAITING_MEDIUM",
    "status-waiting-config-file-prompt": "WAITING_CONFIG_FILE",
    "status-cancelling": "CANCELLING",
    "status-cleaning-up": "CLEANING_UP",
    "status-query": "QUERY",
    "status-details": "DETAILS",
    "status-unknown": "UNKNOWN"
}

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

class InstallerService(GObject.GObject, aptdaemon.client.AptClient):#aptdaemon.client.AptClient):
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
        aptdaemon.client.AptClient.__init__(self)
        apt_pkg.init()
        self.debconf = True
        self.current_trans = None
        self._ttyname = None
        self.daemon_permission = False
        self._signals = []
        self.lastedSearch = {}
        self.cache = apt.Cache(apt.progress.base.OpProgress())
        #self._cache = apt_pkg.Cache(apt.progress.base.OpProgress())#apt_pkg.GetCache()
        self.status_dir = Gio.file_new_for_path(apt_pkg.config.find_file("Dir::State::status"))
        self.monitor = self.status_dir.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.authorized = False
        self.module = None
        if self.monitor:
            self.monitor.connect("changed", self._changed)

    def _changed(self, monitor, file1, file2, evt_type):
        #self._cache = apt_pkg.Cache(apt.progress.base.OpProgress())
        self.cache = apt.Cache(apt.progress.base.OpProgress())
        self.lastedSearch = {}

    def need_root_access(self):
        return False

    def have_terminal(self):
        return True

    def set_terminal(self, ttyname):
        self._ttyname = ttyname

    def is_service_idle(self):
        return True

    def refresh_cache(force_update = False, collect_type=None):
        pass

    def release_all(self):
        pass

    def load_cache(self, forced=False, collect_type=None):
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
        #Return the package that ships the given file.
        #Return None if no package ships it.
        if path is not None:
            # resolve symlinks in directories
            (dir, name) = os.path.split(path)
            resolved_dir = os.path.realpath(dir)
            if os.path.isdir(resolved_dir):
                file = os.path.join(resolved_dir, name)

            if not self._likely_packaged(path):
                result.append([]) 
            else:
                result.append(self._get_file_package(path))
        else:
                result.append([]) 
        loop.quit()

    def get_all_local_packages(self, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            listkeys = self.cache.keys()
            for pkgName in listkeys:
                pkg = self.cache[pkgName]
                if(pkg.is_installed) and (not self._packageExistArch(pkgName)):
                    local_packages.append(pkgName)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        loop.quit()

    def get_all_remote_packages(self, loop, result, collect_type=None):
        remote_packages = []
        result.append(remote_packages)
        try:
            listkeys = self.cache.keys()
            for pkgName in listkeys:
                pkg = self.cache[pkgName]
                if(not pkg.is_installed) and (not self._packageExistArch(pkgName)):
                    remote_packages.append(pkgName)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        loop.quit()

    def get_all_packages(self, loop, result, collect_type=None):
        all_packages = []
        result.append(all_packages)
        try:
            listkeys = self.cache.keys()
            for pkgName in listkeys:
                pkg = self.cache[pkgName]
                if (not self._packageExistArch(pkgName)):
                    all_packages.append(pkgName)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        loop.quit()

    def get_package_info(self, loop, result, pkg_id, collect_type):
        loop.quit()

    def get_local_packages(self, packages, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            for pkgName in listkeys:
                pkg = self.cache[pkgName]
                if((pkg.is_installed) and (not self._packageExistArch(pkgName))):
                    local_packages.append(pkgName)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        loop.quit()

    def get_remote_packages(self, packages, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            for pkgName in listkeys:
                pkg = self.cache[pkgName]
                if((not pkg.is_installed) and (not self._packageExistArch(pkgName))):
                    local_packages.append(pkgName)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        loop.quit()

    def get_local_search(self, pattern, loop, result, collect_type=None):
        local_packages = []
        result.append(local_packages)
        try:
            listkeys = self.cache.keys()
            for pkgName in listkeys:
                pkg = self.cache[pkgName]
                if((pkg.is_installed) and (self._isMatching(matchWordsPattern, pkgName)) and
                    (not self._packageExistArch(pkgName))):
                    local_packages.append(pkgName)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        loop.quit()
    '''
    def get_remote_search(self, pattern, loop, result, collect_type=None):
        start_time = time.time()
        local_packages = []
        result.append(local_packages)
        try:
            matchWordsPattern = pattern.split(",")
            quickList = self._getQuickSearch(pattern)
            if(quickList):
                for pkgName in quickList:
                    pkg = self._cache[pkgName]
                    if((pkg.current_state == apt_pkg.CURSTATE_NOT_INSTALLED) and (self._isMatching(matchWordsPattern, pkg.name))):
                        local_packages.append(pkg.name)
            for pkg in self._cache.packages:
                if((pkg.current_state == apt_pkg.CURSTATE_NOT_INSTALLED) and
                    (self._isMatching(matchWordsPattern, pkg.name)) and (not pkg.name in local_packages)):
                    local_packages.append(pkg.name)
            self._tryToSave(pattern, local_packages)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        print(str(time.time() - start_time))
        loop.quit()
    '''
    '''
    def get_remote_search(self, pattern, loop, result, collect_type=None):
        start_time = time.time()
        local_packages = []
        result.append(local_packages)
        try:
            matchWordsPattern = pattern.split(",")
            quickList = self._getQuickSearch(pattern)
            if(quickList):
                for pkgName in quickList:
                    pkg = self.cache[pkgName]
                    if((not pkg.is_installed) and (self._isMatching(matchWordsPattern, pkgName)) and
                        (not self._packageExistArch(pkgName))):
                        local_packages.append(pkgName)
            else:
                listkeys = self.cache.keys()
                for pkgName in listkeys:
                    pkg = self.cache[pkgName]
                    if((not pkg.is_installed) and (self._isMatching(matchWordsPattern, pkgName)) and
                        (not self._packageExistArch(pkgName))):
                        local_packages.append(pkgName)
                self._tryToSave(pattern, local_packages)
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        print(str(time.time() - start_time))
        loop.quit()
    '''
    def get_remote_search(self, pattern, loop, result, collect_type=None):
        start_time = time.time()
        local_packages = []
        result.append(local_packages)
        try:
            matchWordsPattern = pattern.split(",")
            quickList = self._getQuickSearch(pattern)
            if(quickList):
                for pkgName in quickList:
                    pkg = self.cache[pkgName]
                    if((not pkg.is_installed) and (self._isMatching(matchWordsPattern, pkgName)) and
                        (not self._packageExistArch(pkgName))):
                        local_packages.append(pkgName)
            else:
                dpkg = subprocess.Popen(["apt-cache", "search", "--names-only", pattern],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out = dpkg.communicate()[0].decode("UTF-8")
                if dpkg.returncode == 0 and out:
                    pkgs = out.split("\n")
                    for pkgLine in pkgs:
                        pkg = pkgLine.split(" ")
                        if(pkg[0] and pkg[0] != ""):
                            local_packages.append(pkg[0])
        except GLib.GError:
            e = sys.exc_info()[1]
            print(str(e))
        print(str(time.time() - start_time))
        loop.quit()

    def _policykit_test(self, action_id):
        authority = Polkit.Authority.get()
        subject = Polkit.UnixProcess.new(os.getppid())
        mainloop = GObject.MainLoop()
        cancellable = Gio.Cancellable()
        authority.check_authorization(subject, action_id, None, Polkit.CheckAuthorizationFlags.ALLOW_USER_INTERACTION, cancellable, self.check_authorization_cb, mainloop)
        mainloop.run()

    def check_authorization_cb(self, authority, res, loop):
        try:
            result = authority.check_authorization_finish(res)
            if result.get_is_authorized():
                self.authorized = True
            elif result.get_is_challenge():
                self.authorized = False
            else:
                self.authorized = False
        except GObject.GError:
            e = sys.exc_info()[1]
            print("Error checking authorization: %s" % e.message)
            self.authorized = False
        loop.quit()


    def prepare_transaction_install(self, packages, collect_type=None):
        if (self.daemon_permission):
            try:
                self._policykit_test("org.cinnamon.installer.commit")
            except Exception:
                e = sys.exc_info()[1]
                self.authorized = False
                self.EmitLogError(_("Authentication failed"))
                print(str(e))
        else:
            self.authorized = True
        if self.authorized:
            self.install_packages(packages,
                                  reply_handler=self._simulate_trans,
                                  error_handler=self._on_error)
        else:
            self.EmitTransactionError(_("Authentication failed"), _("Authentication failed"))
        self.authorized = False

    def prepare_transaction_remove(self, packages, collect_type=None):
        if (self.daemon_permission):
            try:
                self._policykit_test("org.cinnamon.installer.commit")
            except Exception:
                e = sys.exc_info()[1]
                self.authorized = False
                self.EmitLogError(_("Authentication failed"))
                print(str(e))
        else:
            self.authorized = True
        if self.authorized:
            self.remove_packages(packages,
                                 reply_handler=self._simulate_trans,
                                 error_handler=self._on_error)
        else:
            self.EmitTransactionError(_("Authentication failed"), _("Authentication failed"))
        self.authorized = False

    def prepare_transaction_commit(self, packages_status, collect_type=None): #new and need to be tested
        if (self.daemon_permission):
            try:
                self._policykit_test("org.cinnamon.installer.commit")
            except Exception:
                e = sys.exc_info()[1]
                self.authorized = False
                self.EmitLogError(_("Authentication failed"))
                print(str(e))
        else:
            self.authorized = True
        if self.authorized:
            self._parse_packages_status(packages_status)
            self.commit_packages(packages_status["install"],
                                 packages_status["reinstall"],
                                 packages_status["remove"],
                                 packages_status["purge"],
                                 packages_status["purge"],
                                 packages_status["upgrade"],
                                 packages_status["downgrade"],
                                 reply_handler=self._simulate_trans,
                                 error_handler=self._on_error)
        else:
            self.EmitTransactionError(_("Authentication failed"), _("Authentication failed"))
        self.authorized = False

    def cancel(self):
        if (self.current_trans) and (self.current_trans.cancellable):
            self.current_trans.cancel(reply_handler=self._on_cancel_finished,
                                      error_handler=self._on_cancel_error) 
        else:
            self._on_cancel_finished()

    def _parse_packages_status(self, packages_status):
        if not "install" in packages_status:
            packages_status["install"] = []
        if not "reinstall" in packages_status:
            packages_status["reinstall"] = []
        if not "remove" in packages_status:
            packages_status["remove"] = []
        if not "purge" in packages_status:
            packages_status["purge"] = []
        if not "upgrade" in packages_status:
            packages_status["upgrade"] = []
        if not "downgrade" in packages_status:
            packages_status["downgrade"] = []

    def _on_cancel_finished(self):
        self._signals = []
        print("bye")
        self.current_trans = None

    def _on_cancel_error(self):
        self.current_trans = None

    def _simulate_trans(self, transaction):
        self.EmitTransactionStart("start")
        self._set_transaction(transaction)
        transaction.simulate(reply_handler=lambda: self._confirm_deps(transaction),
                             error_handler=self._on_error)

    def _on_error(self, error):
        print("error-status: " + str(error))
        try:
            raise error
        except aptdaemon.errors.NotAuthorizedError:
            # Silently ignore auth failures
            return
        except aptdaemon.errors.TransactionFailed:
            e = sys.exc_info()[1]
            errorApt = aptdaemon.errors.TransactionFailed(ERROR_UNKNOWN,
                                                       str(e))
        except Exception:
            e = sys.exc_info()[1]
            errorApt = aptdaemon.errors.TransactionFailed(ERROR_UNKNOWN,
                                                       str(e))
        if errorApt:
           self.EmitTransactionError(get_error_string_from_enum(errorApt.code), 
                get_error_description_from_enum(errorApt.code) + " " + errorApt.details)

    def _confirm_deps(self, transaction):
        try:
            #self._set_transaction(transaction)
            info_config = self._get_transaction_summary(transaction)
            self.EmitTransactionConfirmation(info_config)
            if [pkgs for pkgs in transaction.dependencies if pkgs]:
                pass
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))

    def commit(self):
        if self.current_trans is not None:
            self._run(self.current_trans, None, close_on_finished=True, show_error=True,
                    reply_handler=lambda: True,
                    error_handler=self._on_error)

    def _set_transaction(self, transaction):
        """Connect the dialog to the given aptdaemon transaction"""
        for sig in self._signals:
            GLib.source_remove(sig)
        self._signals = []
        self.current_trans = transaction
        self._signals.append(transaction.connect_after("status-changed",
                                                    self._on_status_changed))
        self._signals.append(transaction.connect("status-details-changed",
                                                    self._on_status_details_changed))
        self._signals.append(transaction.connect("role-changed",
                                                    self._on_role_changed))
        self._signals.append(transaction.connect("medium-required",
                                                    self._on_medium_required))
        self._signals.append(transaction.connect("config-file-conflict",
                                                    self._on_config_file_conflict))
        self._signals.append(transaction.connect("progress-changed",
                                                     self._on_progress_changed))
        self._signals.append(transaction.connect("progress-details-changed",
                                                     self._on_progress_details_changed))
        self._signals.append(transaction.connect("cancellable-changed",
                                                      self._on_cancellable_changed))
        self._signals.append(transaction.connect("progress-download-changed",
                                                      self._on_download_changed))
        self._signals.append(transaction.connect("terminal-attached-changed",
                                                      self._on_terminal_attached_changed))
        self._on_role_changed(transaction, transaction.role)
        if self._ttyname:
            transaction.set_terminal(self._ttyname)

    def _on_download_changed(self, transaction, uri, status, desc, full_size, downloaded, message):
        if full_size == 0:
            progress = -1
        else:
            progress = int(downloaded * 100 / full_size)
        if status == DOWNLOAD_DONE:
            progress = 100
        if progress > 100:
            progress = 100
        description = ""
        if status == DOWNLOAD_FETCHING:
            description += (_("Downloaded %sB of %sB") %
                     (apt_pkg.size_to_str(downloaded),
                     apt_pkg.size_to_str(full_size)))
        elif status == DOWNLOAD_DONE:
            if full_size != 0:
                description += _("Downloaded %sB") % apt_pkg.size_to_str(full_size)
            else:
                description += _("Downloaded")
        else:
            description += get_download_status_from_enum(status)
        self.EmitDownloadPercentChild(uri, "cs-packages", desc[:], progress, description)

    def _on_terminal_attached_changed(self, transaction, attached):
        self.EmitTerminalAttached(attached)
    '''
    def _on_status_changed_expander(self, trans, status):
        if status in (STATUS_DOWNLOADING, STATUS_DOWNLOADING_REPO):
            self.mainApp._terminalExpander.set_sensitive(True)
            self.mainApp._downloadScrolled.show()
            self.mainApp._terminalTextView.hide()
            if self.terminal:
                self.terminal.hide()
        elif status == STATUS_COMMITTING:
            self.mainApp._downloadScrolled.hide()
            self.mainApp._terminalTextView.show()
            if self.terminal:
                self.terminal.show()
                self.mainApp._terminalExpander.set_sensitive(True)
            else:
                self.mainApp._terminalExpander.set_expanded(False)
                self.mainApp._terminalExpander.set_sensitive(False)
        else:
            self.mainApp._downloadScrolled.hide()
            self.mainApp._terminalTextView.show()
            if self.terminal:
                self.terminal.hide()
            self.mainApp._terminalExpander.set_sensitive(False)
            self.mainApp._terminalExpander.set_expanded(False)
    '''

    @inline_callbacks
    def _run(self, trans, attach, close_on_finished, show_error,
             reply_handler, error_handler):
        try:
            sig = trans.connect("finished", self._on_finished,
                                            close_on_finished, show_error)
            self._signals.append(sig)
            if attach:
                yield trans.sync()
            else:
                if self.debconf:
                    yield trans.set_debconf_frontend("gnome")
                yield trans.run()
            self.daemon_permission = True
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))
            if error_handler:
                error_handler(e)
            else:
                raise
        else:
            if reply_handler:
                reply_handler()

    def _get_transaction_summary(self, trans):
        #Create a message and the dependencies to be show.
        infoConf = { "title": "", "description": "", "dependencies": {} }
        for index, msg in enumerate([_("Install"),
                                     _("Reinstall"),
                                     _("Remove"),
                                     _("Purge"),
                                     _("Upgrade"),
                                     _("Downgrade"),
                                     _("Skip upgrade")]):
            if trans.dependencies[index]:
                listPiter = infoConf["dependencies"]["%s" % msg] = []
                for pkg in trans.dependencies[index]:
                    for object in self.map_package(pkg):
                        listPiter.append(str(object))
        # If there is only one type of changes (e.g. only installs) expand the
        # tree
        #FIXME: adapt the title and message accordingly
        #FIXME: Should we have different modes? Only show dependencies, only
        #       initial packages or both?
        msg = _("Please take a look at the list of changes below.")
        title = ""
        if len(infoConf["dependencies"].keys()) == 1:
            if trans.dependencies[PKGS_INSTALL]:
                title = _("Additional software has to be installed")
            elif trans.dependencies[PKGS_REINSTALL]:
                title = _("Additional software has to be re-installed")
            elif trans.dependencies[PKGS_REMOVE]:
                title = _("Additional software has to be removed")
            elif trans.dependencies[PKGS_PURGE]:
                title = _("Additional software has to be purged")
            elif trans.dependencies[PKGS_UPGRADE]:
                title = _("Additional software has to be upgraded")
            elif trans.dependencies[PKGS_DOWNGRADE]:
                title = _("Additional software has to be downgraded")
            elif trans.dependencies[PKGS_KEEP]:
                title = _("Updates will be skipped")
        else:
            title = _("Additional changes are required")
        if trans.download:
            msg += "\n"
            msg += (_("%sB will be downloaded in total.") %
                    apt_pkg.size_to_str(trans.download))
        if trans.space < 0:
            msg += "\n"
            msg += (_("%sB of disk space will be freed.") %
                    apt_pkg.size_to_str(trans.space))
        elif trans.space > 0:
            msg += "\n"
            msg += (_("%sB more disk space will be used.") %
                    apt_pkg.size_to_str(trans.space))
        infoConf["title"] = title
        infoConf["description"] = msg
        return infoConf

    def map_package(self, pkg):
        '''Map a package to a different object type, e.g. applications
        and return a list of those.
        By default return the package itself inside a list.
        Override this method if you don't want to store package names
        in the treeview.
        '''
        return [pkg]

    def _on_finished(self, transaction, status, close, show_error):
        self.EmitTransactionCancellable(False)
        self.EmitPercent(100)
        if status == EXIT_FAILED and show_error:
            error = transaction.error
            self.EmitTransactionError(get_error_string_from_enum(error.code),
                 get_error_description_from_enum(error.code) + ", " + error.details)
        else:
            self.EmitTransactionDone("done")

    def _on_status_changed(self, trans, status):
        # Also resize the window if we switch from download details to
        # the terminal window
        status_translate = get_status_string_from_enum(status)
        #print(status + " " + status_translate)
        self.EmitStatus(status, status_translate)

    def _on_status_details_changed(self, transaction, text):
        """Set the status text to the one reported by apt"""
        self.EmitStatus("", text)

    def _on_role_changed(self, transaction, role_enum):
        """Show the role of the transaction in the dialog interface"""
        role = get_role_localised_present_from_enum(role_enum)
        icon_name = get_role_icon_name_from_enum(role_enum)
        self.EmitRole(role)
        self.EmitIcon(icon_name)

    def _on_progress_changed(self, transaction, progress):
        """Update the progress according to the latest progress information"""
        if progress > 0:
            self.EmitPercent(progress)
        else:
            self.EmitPercent(200)

    def _on_progress_details_changed(self, transaction, items_done, items_total,
                             bytes_done, bytes_total, speed, eta):
        """Update the progress bar text according to the latest progress details"""
        if items_total == 0 and bytes_total == 0:
            self.EmitTarget(" ")
        else:
            if speed != 0:
                self.EmitTarget(_("Downloaded %sB of %sB at %sB/s") %
                                          (apt_pkg.size_to_str(bytes_done),
                                          apt_pkg.size_to_str(bytes_total),
                                          apt_pkg.size_to_str(speed)))
            else:
                self.EmitTarget(_("Downloaded %sB of %sB") %
                                          (apt_pkg.size_to_str(bytes_done),
                                          apt_pkg.size_to_str(bytes_total)))

    def _on_cancellable_changed(self, transaction, cancellable):
        """Enable the button if cancel is allowed and disable it in the other case"""
        self.EmitTransactionCancellable(cancellable)

    def _on_medium_required(self, transaction, medium, drive):
        title = _("CD/DVD '%s' is required") % medium
        desc = _("Please insert the above CD/DVD into the drive '%s' to "
                 "install software packages from it.") % drive
        self.EmitMediumRequired(medium, title, desc)

    def resolve_medium_required(self, medium):
        #TRANSLATORS: %s is the name of the CD/DVD drive
        if medium:
            self.current_trans.provide_medium(medium)
        else:
            self.current_trans.cancel()

    def resolve_package_providers(self, provider_select):
        print("What?")

    def check_updates(self, success=None, nosuccess=None, collect_type=None):
        print("not implemented")

    def system_upgrade(self, show_updates = True, downgrade = False, collect_type=None):
        print("not implemented")

    def write_config(self, array, collect_type=None):
        print("not implemented")

    def _on_config_file_conflict(self, transaction, old, new):
        self.EmitConflictFile(old, new)

    def resolve_config_file_conflict(replace, old, new):
        if replace:
            self.current_trans.resolve_config_file_conflict(old, "replace")
        else:
            self.current_trans.resolve_config_file_conflict(old, "keep")

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
          
    def _packageExistArch(self, pkgName):
        lenght = len(pkgName)
        if lenght > 4 and pkgName[lenght-5:lenght] == ":i386":
            try:
                pkg = self.cache[pkgName[0:lenght-5]]
                return True
                #if pkg.is_installed:
                #    print("Installed: " + pkgName)
                #    return True
            except Exception:
                return False
        return False

    ''' '''

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
        divert = "/usr/bin/dpkg-divert"
        if(not GLib.file_test(divert, GLib.FileTest.EXISTS)):
            divert = "/usr/sbin/dpkg-divert"
        if(GLib.file_test(divert, GLib.FileTest.EXISTS)):
            dpkg = subprocess.Popen([divert, "--list", file],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out = dpkg.communicate()[0].decode("UTF-8")
            if dpkg.returncode == 0 and out:
                pkg = out.split()[-1]
                if pkg != "hardening-wrapper":
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

    def EmitStatus(self, status, status_translation):
        if status == "":
            status_ci = "DETAILS"
        else:
            status_ci = CI_STATUS[status]
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

    def EmitTransactionError(self, title, message):
        self.emit("EmitTransactionError", title, message)

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

