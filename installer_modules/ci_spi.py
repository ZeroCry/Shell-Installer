#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# Cinnamon Installer
#
# Authors: Lester Carballo Pérez <lestcape@gmail.com>
# Froked from Cinnamon code at:
# https://github.com/linuxmint/Cinnamon
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

import sys, os

try:
    import tempfile, time, string, shutil, subprocess, signal, cgi, datetime
    from gi.repository import Gtk, GObject
    import threading
except Exception:
    e = sys.exc_info()[1]
    print(str(e))
    sys.exit(1)

try:
    import json
except ImportError:
    import simplejson as json

import SpicesPackages, SystemTools, UtilitiesTools

from gi.repository import GObject

ABS_PATH = os.path.abspath(__file__)
DIR_PATH = os.path.dirname(os.path.dirname(ABS_PATH))

# i18n
import gettext, locale
LOCALE_INSTALL_PATH = os.path.join(DIR_PATH, "locale")
DOMAIN = "cinnamon-installer"
locale.bindtextdomain(DOMAIN , LOCALE_INSTALL_PATH)
locale.bind_textdomain_codeset(DOMAIN , "UTF-8")
gettext.bindtextdomain(DOMAIN, LOCALE_INSTALL_PATH)
gettext.bind_textdomain_codeset(DOMAIN , "UTF-8")
gettext.textdomain(DOMAIN)
_ = gettext.gettext


EFECTIVE_USER = SystemTools.get_user()
EFECTIVE_IDS = [SystemTools.get_user_id(EFECTIVE_USER), SystemTools.get_group_id(EFECTIVE_USER)]
EFECTIVE_MODE = SystemTools.get_standar_mode()
HOME_PATH = SystemTools.get_home(EFECTIVE_USER)

LOCALE_PATH = "%s/.local/share/locale" % HOME_PATH
SETTINGS_PATH = "%s/.cinnamon/configs/" % HOME_PATH

URL_SPICES_HOME = "http://cinnamon-spices.linuxmint.com"

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
    "status-query": "QUERY",
    "status-details": "DETAILS",
    "status-unknown": "UNKNOWN"
}


class InstallerModule():
    def __init__(self):
        self.validTypes = ["applet", "desklet", "extension", "theme"]
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
        self.cache = SpicesPackages.SpiceCache()
        self.index_cache = {}
        self.packages_action = {}
        self.collection_type = None
        self.error = None
        self.has_cache = False
        self.client_response = True
        self.module = None
        self.max_process = 3
        self.cancellable = True
        self.lock_trans = threading.Lock()
        self.client_condition = threading.Condition()
        self.validTypes = self.cache.get_valid_types();
        self.cacheTypesLength = len(self.validTypes)
        self.download_helper = UtilitiesTools.DownloadHelper()
        print("Was create an spices Module")

    def need_root_access(self):
        return False

    def have_terminal(self):
        return False

    def set_terminal(self, ttyname):
        pass

    def is_service_idle(self):
        return not self.lock_trans.locked()

    def load_cache(self, forced=False, collect_type=None):
        self.EmitTransactionStart("Start")
        self.EmitRole("Loading cache...")
        self._internal_load_cache(True, forced, collect_type, self._on_cache_load_finished)
        self.EmitTransactionDone("Finished")

    def _internal_load_cache(self, emit=False, forced=False, collect_type=None, on_finish=None):
        if forced or (not self.cache.is_load(collect_type)):
            if (not collect_type):
                for collect_type in self.validTypes:
                    if emit:
                        self.EmitStatus("status-loading-cache", _("Loading cache for %ss...") % collect_type)
                    self.cache.load_collection_type(collect_type)
                    if on_finish and callable(on_finish):
                        on_finish()
            elif collect_type:
                if emit:
                    self.EmitStatus("status-loading-cache", _("Loading cache for %ss...") % collect_type)
                self.cache.load_collection_type(collect_type, on_finish)

    def _on_cache_load_finished(self):
        print("finished cache_load_finished")

    def have_cache(self, collect_type=None):
        return self.cache.is_load(collect_type)

    def set_parent_module(self, module):
        self.module = module

    def get_parent_module(self):
        return self.module

    def get_cache_folder(self, collect_type=None):
        return self.cache.get_cache_folder(collect_type)

    def search_files(self, path, loop, result):
        pass

    def get_all_local_packages(self, loop, result, collect_type=None):
        try:
            self._internal_load_cache(True, False, collect_type)
            result.append(self.cache.get_local_packages(collect_type))
        except Exception:
            result.append([])
            e = sys.exc_info()[1]
            print(str(e))
        time.sleep(0.1)
        loop.quit()

    def get_all_remote_packages(self, loop, result, collect_type=None):
        try:
            self._internal_load_cache(True, False, collect_type)
            result.append(self.cache.get_remote_packages(collect_type))
        except Exception:
            result.append([])
            e = sys.exc_info()[1]
            print(str(e))
        time.sleep(0.1)
        loop.quit()

    def get_all_packages(self, loop, result, collect_type=None):
        try:
            self._internal_load_cache(True, False, collect_type)
            result.append(self.cache.get_all_packages(collect_type))
        except Exception:
            result.append([])
            e = sys.exc_info()[1]
            print(str(e))
        time.sleep(0.1)
        loop.quit()

    def get_package_info(self, loop, result, pkg_id, collect_type):
        try:
            self._internal_load_cache(True, False, collect_type)
            result.append(self.cache.get_package_info(pkg_id, collect_type))
        except Exception:
            result.append([])
            e = sys.exc_info()[1]
            print(str(e))
        time.sleep(0.1)
        loop.quit()

    def get_local_packages(self, packages, loop, result, collect_type=None):
        pass

    def get_remote_packages(self, packages, loop, result, collect_type=None):
        pass

    def get_local_search(self, pattern, loop, result, collect_type=None):
        pass

    def get_remote_search(self, pattern, loop, result, collect_type=None):
        pass

    def prepare_transaction_install(self, packages, collect_type=None):
        self.packages_action = {}
        self.EmitTransactionStart("start")
        self.EmitRole(_("Preparing to install..."))
        self.EmitIcon("cinnamon-installer-search")
        pkg_list = {}
        self._internal_load_cache(True, False, collect_type)
        if collect_type and collect_type in self.validTypes:
            self.collection_type = collect_type
            for uuid in packages:
                pkg = self.cache.get_package_info(uuid, collect_type)
                if pkg is not None:
                    pkg_list[uuid] = pkg
        else:
            self.collection_type = None
            for uuid in packages:
                for collect_type in self.validTypes:
                    pkg = self.cache.get_package_info(uuid, collect_type)
                    if pkg is not None:
                        pkg_list[uuid] = pkg
                        break # Now the first match, but we can emit a singal EmitConflictFile or other new later.
        total_count = len(pkg_list)
        if total_count > 0:
            self.packages_action["install"] = pkg_list
            info_config = { "title": "", "description": "", "dependencies": {} }
            self.EmitStatus("status-waiting", _("Waiting..."))
            self.EmitTransactionConfirmation(info_config)
            #we ar waiting for a commit
        else:
            self.EmitTransactionDone("Error")

    def prepare_transaction_remove(self, packages, collect_type=None):
        self.packages_action = {}
        self.EmitTransactionStart("start")
        self.EmitRole(_("Preparing to remove..."))
        self.EmitIcon("cinnamon-installer-search")
        pkg_list = {}
        self._internal_load_cache(True, False, collect_type)
        if collect_type and collect_type in self.validTypes:
            self.collection_type = collect_type
            for uuid in packages:
                pkg = self.cache.get_package_info(uuid, collect_type)
                if pkg is not None:
                    pkg_list[uuid] = pkg
        else:
            self.collection_type = None
            for uuid in packages:
                for collect_type in self.validTypes:
                    pkg = self.cache.get_package_info(uuid, collect_type)
                    if pkg is not None:
                        pkg_list[uuid] = pkg
                        break # Now the first match, but we can emit a singal EmitConflictFile or other new later.
        total_count = len(pkg_list)
        if total_count > 0:
            self.packages_action["remove"] = pkg_list
            info_config = { "title": "", "description": "", "dependencies": {} }
            self.EmitStatus("status-waiting", _("Waiting..."))
            self.EmitTransactionConfirmation(info_config)
            #we ar waiting for a commit
        else:
            self.EmitTransactionDone("Error")

    def prepare_transaction_commit(self, packages_status, collect_type=None):
        self.packages_action = {}
        self.EmitTransactionStart("start")
        self.EmitRole(_("Preparing to do a complex transaction..."))
        self.EmitIcon("cinnamon-installer-search")
        self._internal_load_cache(True, False, collect_type)
        if collect_type and collect_type in self.validTypes:
            self.collection_type = collect_type
            for action in packages_status:
                pkg_list = {}
                for uuid in packages_status[action]:
                    pkg = self.cache.get_package_info(uuid, collect_type)
                    if pkg is not None:
                        pkg_list[uuid] = pkg
                self.packages_action[action] = pkg_list
        else:
            self.collection_type = None
            for action in packages_status:
                pkg_list = {}
                for uuid in packages_status[action]:
                    for collect_type in self.validTypes:
                        pkg = self.cache.get_package_info(uuid, collect_type)
                        if pkg is not None:
                            pkg_list[uuid] = pkg
                            break # Now the first match, but we can emit a singal EmitConflictFile or other new later.
                self.packages_action[action] = pkg_list
        total_count = len(self.packages_action.keys())
        if total_count > 0:
            info_config = { "title": "", "description": "", "dependencies": {} }
            self.EmitStatus("status-waiting", _("Waiting..."))
            self.EmitTransactionConfirmation(info_config)
            #we ar waiting for a commit
        else:
            self.EmitTransactionDone("Error")

    def commit(self):
        packages = self.packages_action
        collect_type = self.collection_type
        actions = self.packages_action.keys()
        if not self.client_response:
            self.client_condition.acquire()
            self.client_response = True
            self.client_condition.notify()
            self.client_condition.release()
            try:
                self.EmitStatus("status-committing", _("Committing"))
                if len(actions) > 0:
                    if len(actions) == 1:
                        if "install" in actions:
                            self._install_all(packages["install"])
                        elif "remove" in actions:
                            self._uninstall_all(packages["remove"])
                    else:
                        error = _("The transaction can not be performed, a complex action is not implemented yet.\n\nSorry.")
                        self.EmitTransactionError(error, "")
                        #self._commit_all(packages)
                    #self._internal_load_cache(False, True, collect_type)
                else:
                    raise Exception(_("Nothing to do..."))
            except Exception:
                e = sys.exc_info()[1]
                error = _("The transaction can not be performed.")
                self.EmitTransactionError(error, str(e))
                print(str(e))

    def cancel(self):
        try:
            self.download_helper.cancel_download()
            if self.lock_trans.locked():
                self.lock_trans.release()
            if not self.client_response:
                self.client_condition.acquire()
                self.client_response = True
                self.client_condition.notify()
                self.client_condition.release()
        except:
            pass

    def _on_cancel_finished(self):
        self._signals = []
        self.current_trans = None

    def resolve_config_file_conflict(replace, old, new):
        pass

    def resolve_medium_required(self, medium):
        pass

    def resolve_package_providers(self, provider_select):
        pass

    def check_updates(self, success=None, nosuccess=None, collect_type=None):
        pass

    def system_upgrade(self, show_updates, downgrade, collect_type=None):
        pass

    def write_config(self, array, collect_type=None):
        pass

    def release_all(self):
        pass

    def get_default_icon(self, collect_type):
        return self.cache.get_default_icon(collect_type)

    def refresh_cache(self, force_update=False, collect_type=None):
        url_list = {}
        self.EmitRole(_("Refreshing index..."))
        if collect_type and collect_type in self.validTypes:
            self.EmitStatus("status-downloading", _("Downloading index for %ss" % collect_type))
            cache_folder = self.get_cache_folder(collect_type)
            cache_file = os.path.join(cache_folder, "index.json")
            url_list[self.cache.get_index_url(collect_type)] = {
                "collect-type":collect_type,
                "path":cache_file,
                "force-update":force_update
            }
            self.EmitDownloadPercentChild(collect_type, self.get_default_icon(collect_type), "%s index" % collect_type, 0, "")
        else:
            for collect_type in self.validTypes:
                self.EmitRole(_("Refreshing index."))
                cache_folder = self.get_cache_folder(collect_type)
                cache_file = os.path.join(cache_folder, "index.json")
                url_list[self.cache.get_index_url(collect_type)] = {
                    "collect-type":collect_type,
                    "path":cache_file,
                    "force-update":force_update
                }
                self.EmitDownloadPercentChild(collect_type, self.get_default_icon(collect_type), "%s index" % collect_type, 0, "")
        self.EmitIcon("cinnamon-installer-download")
        self.EmitTransactionCancellable(True)
        self.EmitStatus("status-downloading", _("Downloading index for %ss" % collect_type))
        works = self.download_helper.download_files(url_list, False, self._reporthook_cache, url_list)
        self.EmitStatus("status-running", _("Updatating cache..."))
        self.EmitIcon("cinnamon-installer-update")
        assets_list = []
        if not self.download_helper.is_download_cancelled():
            for url in works:
                if works[url]["error"]:
                    self.EmitLogError(works[url]["error"])
                if works[url]["result"]:
                    collect_type = url_list[url]["collect-type"]
                    assets_list.append(collect_type)
        if len(assets_list) > 0:
            if force_update:
                self._refresh_assets(assets_list)
        else:
            self.EmitTransactionError(_("Download aborted."), "")
            self.EmitTransactionDone("Download Fail")

    def _reporthook_cache(self, url, count, block_size, total_size, pending_downloads, url_list):
        total_count = len(url_list)
        collect_type = url_list[url]["collect-type"]
        force_update = url_list[url]["force-update"]

        percent = int((float(count*block_size)/total_size)*100)
        self.EmitDownloadPercentChild(collect_type, self.get_default_icon(collect_type), "%ss index" % collect_type, percent, "")
        count = float(total_count - pending_downloads)
        if (force_update):
            total_percent = 4*(100*count + percent)/(total_count*5)
        else:
            total_percent = (100*count + percent)/total_count
        self.EmitPercent(total_percent)
        targent = "%s" % (str(int(total_percent)) + "%")
        self.EmitTarget(targent)

    def _refresh_assets(self, assets_list):
        self.EmitDownloadChildStart(False)
        url_list_assets = {}
        for collect_type in assets_list:
            self.EmitStatus("status-loading-cache", _("Refreshing cache for %ss" % collect_type))
            self.EmitIcon("cinnamon-installer-search")
            self.cache.load_collection_type(collect_type)
            assets = self.cache.get_assets_type_to_refresh(collect_type)
            for url in assets:
                url_list_assets[url] = {
                    "collect-type":collect_type,
                    "path":assets[url]["icon"],
                    "uuid":assets[url]["uuid"],
                    "name":assets[url]["name"],
                    "last-edited":assets[url]["last-edited"]
                }
        total_count = len(url_list_assets)
        if total_count > 0:
            self.EmitTransactionCancellable(True)
            self.EmitIcon("cinnamon-installer-download")
            self.EmitStatus("status-downloading", _("Downloading cache for %ss" % collect_type))
            works = self.download_helper.download_files(url_list_assets, False, self._reporthook_assets, url_list_assets)
            can_continue = False
            if not self.download_helper.is_download_cancelled():
                for url in works:
                    if works[url]["error"]:
                        self.EmitLogError(works[url]["error"])
                    if works[url]["result"]:
                        can_continue = True
            if can_continue:
                self.EmitTransactionDone("complete")
            else:
                self.EmitTransactionError(_("Download aborted."), "")
                self.EmitTransactionDone("Download Fail")
        else:
            self.EmitStatus("status-finished", _("We don't find any other thing to update."))
            self.EmitTransactionDone("complete")

    def _reporthook_assets(self, url, count, block_size, total_size, pending_downloads, url_list):
        total_count = len(url_list)
        collect_type = url_list[url]["collect-type"]
        uuid = url_list[url]["uuid"]
        name = url_list[url]["name"]
        last_edited = url_list[url]["last-edited"]
        percent = int((float(count*block_size)/total_size)*100)
        time = datetime.datetime.fromtimestamp(last_edited).strftime("%Y-%m-%d -- %H:%M:%S")
        self.EmitDownloadPercentChild(uuid, self.get_default_icon(collect_type), name, percent, time)
        count = float(total_count - pending_downloads)
        total_percent = 80 + (100*count + percent)/(total_count*5)
        self.EmitPercent(total_percent)
        targent = "%s" % (str(int(total_percent)) + "%")
        self.EmitTarget(targent)

    def _download_packages(self, pkg_download):
        self.abort_download = False
        url_list = {}
        for uuid in pkg_download:
            pkg = pkg_download[uuid]
            url_list[self.cache.get_package_url(pkg["collection"], uuid)] = {
                "collect-type":pkg["collection"],
                "uuid":uuid,
                "path":None,
                "name":pkg["name"],
                "last-edited":pkg["last-edited"]
            }
        total_count = len(url_list)
        pkg_list = {}
        if total_count > 0:
            self.EmitTransactionCancellable(True)
            self.EmitIcon("cinnamon-installer-download")
            self.EmitStatus("status-downloading", _("Downloading packages"))

            works = self.download_helper.download_files(url_list, False, self._reporthook_packages, url_list)
 
            if not self.download_helper.is_download_cancelled():
                for url in works:
                    if works[url]["error"]:
                        self.EmitLogError(works[url]["error"])
                    if works[url]["result"]:
                        collect_type = url_list[url]["collect-type"]
                        uuid = url_list[url]["uuid"]
                        if not collect_type in pkg_list:
                            pkg_list[collect_type] = {}
                        pkg_list[collect_type][uuid] = { 
                            "name": url_list[url]["name"],
                            "path": works[url]["result"],
                            "last-edited": url_list[url]["last-edited"] 
                        }
        return pkg_list

    def _reporthook_packages(self, url, count, block_size, total_size, pending_downloads, url_list):
        total_count = len(url_list)
        collect_type = url_list[url]["collect-type"]
        uuid = url_list[url]["uuid"]
        name = url_list[url]["name"]
        last_edited = url_list[url]["last-edited"]
        percent = int((float(count*block_size)/total_size)*100)
        time = datetime.datetime.fromtimestamp(last_edited).strftime("%Y-%m-%d -- %H:%M:%S")
        self.EmitDownloadPercentChild(uuid, self.get_default_icon(collect_type), name, percent, time)
        count = float(total_count - pending_downloads)
        total_percent = 9*(100*count + percent)/(total_count*10)
        self.EmitPercent(total_percent)
        targent = "%s" % (str(int(total_percent)) + "%")
        self.EmitTarget(targent)

    def _install_all(self, pkg_install):
        self.EmitRole(_("Installing..."))
        pkg_list = self._download_packages(pkg_install)
        total_count = len(pkg_list)
        if total_count > 0:
            schema_filename_list = { "install": {}, "remove": {} }
            self.EmitStatus("status-running", _("Installing..."))
            self.EmitIcon("cinnamon-installer-install")
            compressor = UtilitiesTools.CompressorHelper()
            for collect_type in pkg_list:
                for uuid in pkg_list[collect_type]:
                    file_path = pkg_list[collect_type][uuid]["path"]
                    edited_date = pkg_list[collect_type][uuid]["last-edited"]
                    name = pkg_list[collect_type][uuid]["name"]
                    schema_filename = self._install_single(uuid, name, file_path, edited_date, compressor, collect_type)
                    schema_filename_list["install"][uuid] = [schema_filename, collect_type]
            self._install_and_remove_schema_files(schema_filename_list)
            self.EmitStatus("status-finished", _("Transaction sucefully.."))
            self.EmitTransactionDone("Finished")
            need_restart = False
        else:
            self.EmitStatus("status-finished", _("We don't find any packages to install"))
            self.EmitTransactionDone("complete")
        self.abort_download = False

    def _uninstall_all(self, pkg_remove):
        self.EmitRole(_("Removing..."))
        total_count = len(pkg_remove)
        if total_count > 0:
            schema_filename_list = { "install": {}, "remove": {} }
            self.EmitStatus("status-running", _("Removing..."))
            self.EmitIcon("cinnamon-installer-delete")
            for uuid in pkg_remove:
                collect_type = pkg_remove[uuid]["collection"]
                if pkg_remove[uuid]["schema-file"]:
                    schema_filename_list["remove"][uuid] = [pkg_remove[uuid]["schema-file"], collect_type]
                edited_date = pkg_remove[uuid]["last-edited"]
                self._uninstall_single(uuid, edited_date, collect_type)
            self._install_and_remove_schema_files(schema_filename_list)
            self.EmitStatus("status-finished", _("Transaction sucefully.."))
            self.EmitTransactionDone("Finished")
            need_restart = False
        else:
            self.EmitStatus("status-finished", _("We don't find any packages to install"))
            self.EmitTransactionDone("complete")
        self.abort_download = False

    def _commit_all(self, pkg_status):
        self.EmitRole(_("Installing..."))
        pkg_list = self._download_packages(pkg_install)
        total_count = len(pkg_list)
        if total_count > 0:
            schema_filename_list = { "install": {}, "remove": {} }
            self.EmitStatus("status-running", _("Installing..."))
            self.EmitIcon("cinnamon-installer-install")
            compressor = UtilitiesTools.CompressorHelper()
            for collect_type in pkg_list:
                for uuid in pkg_list[collect_type]:
                    file_path = pkg_list[collect_type][uuid]["path"]
                    edited_date = pkg_list[collect_type][uuid]["last-edited"]
                    name = pkg_list[collect_type][uuid]["name"]
                    schema_filename = self._install_single(uuid, name, file_path, edited_date, compressor, collect_type)
                    schema_filename_list["install"][uuid] = [schema_filename, collect_type]
            self._install_and_remove_schema_files(schema_filename_list)
            self.EmitStatus("status-finished", _("Transaction sucefully.."))
            self.EmitTransactionDone("Finished")
            need_restart = False
        else:
            self.EmitStatus("status-finished", _("We don't find any packages to install"))
            self.EmitTransactionDone("complete")
        self.abort_download = False


    def _install_single(self, uuid, name, file_path, edited_date, compressor, collect_type):
        error_title = uuid
        schema_filename = ""
        try:
            folder_path = tempfile.mkdtemp()
            compressor.set_collection(collect_type)
            compressor.extract_file(file_path, folder_path)
            if collect_type == "theme":
                # Check dir name - it may or may not be the same as the theme name from our spices data
                # Regardless, this will end up being the installed theme name, whether it matched or not
                data_path = os.path.join(folder_path, name)
                if not os.path.exists(data_path):
                    title = os.listdir(folder_path)[0] # We assume only a single folder, the theme name
                    data_path = os.path.join(folder_path, title)
                # Test for correct folder structure - look for cinnamon.css
                file = open(os.path.join(data_path, "cinnamon", "cinnamon.css"), "r")
                file.close()
                md = {}
                md["last-edited"] = edited_date
                md["uuid"] = uuid
                metadata_file = os.path.join(data_path, "cinnamon", "metadata.json")
                final_path = os.path.join(self.cache.get_install_folder(collect_type), name)
            else:
                error_title = uuid
                members = compressor.get_members()
                for file in members:
                    file_locate = os.path.join(folder_path, file.filename)
                    SystemTools.set_propietary_id(file_locate, EFECTIVE_IDS[0], EFECTIVE_IDS[1])
                    SystemTools.set_mode(file_locate, EFECTIVE_MODE)
                    if file.filename[:3] == "po/":
                        parts = os.path.splitext(file.filename)
                        if parts[1] == ".po":
                            this_locale_dir = os.path.join(LOCALE_PATH, parts[0][3:], "LC_MESSAGES")
                            #self.progresslabel.set_text(_("Installing translations for %s...") % title)
                            SystemTools.rec_mkdir(this_locale_dir, EFECTIVE_MODE, EFECTIVE_IDS)
                            #print("/usr/bin/msgfmt -c %s -o %s" % (os.path.join(dest, file.filename), os.path.join(this_locale_dir, "%s.mo" % uuid)))
                            mo_file = os.path.join(this_locale_dir, "%s.mo" % uuid)
                            subprocess.call(["msgfmt", "-c", file_locate, "-o", mo_file])
                            SystemTools.set_propietary_id(mo_file, EFECTIVE_IDS[0], EFECTIVE_IDS[1])
                            SystemTools.set_mode(mo_file, EFECTIVE_MODE)
                            #self.progresslabel.set_text(_("Installing %s...") % (title))
                    elif "gschema.xml" in file.filename:
                        schema_filename = file.filename
                # Test for correct folder structure
                file = open(os.path.join(folder_path, "metadata.json"), "r")
                raw_meta = file.read()
                file.close()
                md = json.loads(raw_meta)
                md["last-edited"] = edited_date
                if schema_filename != "":
                    md["schema-file"] = schema_filename
                metadata_file = os.path.join(folder_path, "metadata.json")
                data_path = folder_path
                final_path = os.path.join(self.cache.get_install_folder(collect_type), uuid)
            raw_meta = json.dumps(md, indent=4)
            file = open(metadata_file, "w+")
            file.write(raw_meta)
            file.close()
            SystemTools.set_propietary_id(metadata_file, EFECTIVE_IDS[0], EFECTIVE_IDS[1])
            SystemTools.set_mode(metadata_file, EFECTIVE_MODE)
            self.EmitStatus("status-cleaning-up", _("Cleaning up..."))
            self.EmitIcon("cinnamon-installer-cleanup")
            if os.path.exists(final_path):
                shutil.rmtree(final_path)
            shutil.copytree(data_path, final_path)
            shutil.rmtree(folder_path)
            os.remove(file_path)
        except Exception:
            e = sys.exc_info()[1]
            schema_filename = ""
            print("Error: " + str(e))
            try:
                shutil.rmtree(folder_path)
                os.remove(file_path)
            except:
                pass
            if not self.abort_download:
                error = _("An error occurred during installation or updating of %s. %s. You may wish to report this incident to the developer.\nIf this was an update, the previous installation is unchanged") % (uuid, str(e))
                self.EmitLogError(error)
        return schema_filename

    def _uninstall_single(self, uuid, edited_date, collect_type):
        error = None
        install_folder = self.cache.get_install_folder(collect_type)
        self.EmitStatus("status-removing", _("Uninstalling %s...") % uuid)
        try:
            if collect_type != "theme":
                shutil.rmtree(os.path.join(install_folder, uuid))
                # Uninstall spice localization files, if any
                if (os.path.exists(LOCALE_PATH)):
                    i19_folders = os.listdir(LOCALE_PATH)
                    for i19_folder in i19_folders:
                        if os.path.isfile(os.path.join(LOCALE_PATH, i19_folder, "LC_MESSAGES", "%s.mo" % uuid)):
                            os.remove(os.path.join(LOCALE_PATH, i19_folder, "LC_MESSAGES", "%s.mo" % uuid))
                        # Clean-up this locale folder
                        SystemTools.removeEmptyFolders(os.path.join(LOCALE_PATH, i19_folder))

                # Uninstall settings file, if any
                if (os.path.exists(os.path.join(SETTINGS_PATH, uuid))):
                    shutil.rmtree(os.path.join(SETTINGS_PATH, uuid))
            else:
                shutil.rmtree(os.path.join(install_folder, uuid))
        except Exception:
            e = sys.exc_info()[1]
            error = _("Problem uninstalling %s. %s. You may need to manually remove it.") % (uuid, str(e))
            self.EmitLogError(error)

    def _install_and_remove_schema_files(self, schema_files, message=""):
        schema_install_list = ""
        schema_remove_list = ""
        for uuid in schema_files["install"]:
            schema = schema_files["install"][uuid][0]
            collect_type = schema_files["install"][uuid][1]
            file_path = os.path.join(self.cache.get_install_folder(collect_type), uuid, schema) 
            schema_install_list = file_path + "," + schema_install_list
        if schema_install_list: schema_install_list = schema_install_list[:-1]

        for uuid in schema_files["remove"]:
            schema = schema_files["remove"][uuid][0]
            schema_remove_list = schema + "," + schema_remove_list
        if schema_remove_list: schema_remove_list = schema_remove_list[:-1]

        if schema_install_list or schema_remove_list:
            tool = os.path.join(DIR_PATH, "tools/schema-installer.py")
            launcher = ""
            if self._is_program_in_system("pkexec"):
                launcher = "pkexec"
            elif os.path.exists("/usr/bin/gksu"):
                launcher = "gksu"
            if os.path.exists(tool) and launcher:
                sentence = _("Please enter your password to install and/or remove the required settings schema files.")
                if message:
                    messg = "<b>%s\n\n%s</b>" % (sentence, message)
                else:
                    messg = "<b>%s</b>" % sentence

                if schema_install_list and schema_remove_list:
                    if launcher == "pkexec":
                        command = [launcher, tool, "-i", "'" + schema_install_list + "'", "-r", schema_remove_list]
                    elif launcher == "gksu":
                        command = [launcher, "--message", messg, tool + " -i ''" + schema_install_list + "'' -r ''" + schema_remove_list + "''"]
                elif schema_install_list:
                    if launcher == "pkexec":
                        command = [launcher, tool, "-i", "'" + schema_install_list + "'"]
                    elif launcher == "gksu":
                        command = [launcher, "--message", messg, tool + " -i ''" + schema_install_list + "''"]
                elif schema_remove_list:
                    if launcher == "pkexec":
                        command = [launcher, tool, "-r", "'" + schema_remove_list + "'"]
                    elif launcher == "gksu":
                        command = [launcher, "--message", messg, tool + " -r ''" + schema_remove_list + "''"]
                p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = p.communicate()
                if err and err.split("\n")[0] == "GNOME_SUDO_PASS":
                    return self._install_and_remove_schema_files(schema_files, _("Wrong password, please try again..."))
                if out and not err:
                    return True

            uuid_install = ""
            uuid_remove = ""
            for uuid in schema_files["install"]:
                uuid_install = uuid_install + ", " + uuid
            for uuid in schema_files["remove"]:
                uuid_remove = uuid_remove + ", " + uuid 
            error = _("Could not install or remove the settings schema files for%s. You will have to perform this step yourself.") % (uuid_install + uuid_remove)
            print(error)
            self.EmitLogError(error)
            return False
        return True

    def _is_program_in_system(self, programName):
        path = os.getenv("PATH")
        for p in path.split(os.path.pathsep):
            p = os.path.join(p, programName)
            if os.path.exists(p) and os.access(p, os.X_OK):
                return True
        return False

    def _client_confirm_trans(self):
        return self.client_response

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
        self.abort_download = True
        self.lock_trans.acquire()
        self.emit("EmitTransactionStart", message)

    def EmitTransactionDone(self, message):
        self.emit("EmitTransactionDone", message)
        self.packages = None
        self.collection_type = None

    def EmitTransactionError(self, title, message):
        self.abort_download = True
        self.emit("EmitTransactionError", title, message)
        self.packages = None
        self.collection_type = None

    def EmitTransactionConfirmation(self, info_config):
        self.client_response = False
        self.emit("EmitTransactionConfirmation", info_config)
        self.client_condition.acquire()
        while not self._client_confirm_trans():
            self.client_condition.wait()
        self.client_condition.release()
        self.packages = None
        self.collection_type = None

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
