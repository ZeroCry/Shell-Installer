#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# Cinnamon Installer
#
# Authors: Lester Carballo Pérez <lestcape@gmail.com>
#
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

import os, sys, tempfile, time, shutil, datetime
import SystemTools, UtilitiesTools

try:
    try:
        import json
    except ImportError:
        import simplejson as json
    from gi.repository import GObject
except Exception:
    e = sys.exc_info()[1]
    print(str(e))
    #sys.exit(1)

HOME_PATH = SystemTools.get_home()

URL_SPICES_HOME = "http://cinnamon-spices.linuxmint.com"
URL_SPICES_APPLET_LIST = URL_SPICES_HOME + "/json/applets.json"
URL_SPICES_THEME_LIST = URL_SPICES_HOME + "/json/themes.json"
URL_SPICES_DESKLET_LIST = URL_SPICES_HOME + "/json/desklets.json"
URL_SPICES_EXTENSION_LIST = URL_SPICES_HOME + "/json/extensions.json"

ABORT_NONE = 0
ABORT_ERROR = 1
ABORT_USER = 2

SETTING_TYPE_NONE = 0
SETTING_TYPE_INTERNAL = 1
SETTING_TYPE_EXTERNAL = 2

class SpiceCache(GObject.GObject):
    '''
    __gsignals__ = {
        "EmitCacheUpdate": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_BOOLEAN, GObject.TYPE_BOOLEAN,)),
        "EmitCacheUpdateError": (GObject.SIGNAL_RUN_FIRST, None, (GObject.TYPE_BOOLEAN, GObject.TYPE_BOOLEAN,)),
    }
    '''
    def __init__(self):
        GObject.GObject.__init__(self)
        self.valid_types = ["applet","desklet","extension", "theme"];
        self.cache_object = { "applet": {}, "desklet": {}, "extension": {}, "theme": {} }
        self.cache_is_load = { "applet": False, "desklet": False, "extension": False, "theme": False }
        self.cache_types_length = len(self.valid_types)

    def get_valid_types(self):
        return self.valid_types

    def is_valid_type(self, collect_type):
        return (self.valid_types.index(collect_type) != -1)

    def get_local_packages(self, collect_type=None):
        result = {}
        if collect_type:
            if not self.is_load(collect_type):
                self.load_collection_type(collect_type)
            for pkg_id in self.cache_object[collect_type]:
                if self.cache_object[collect_type][pkg_id]["installed-type"]:
                    result[pkg_id] = self.cache_object[collect_type][pkg_id]
        else:
            for collect_type in self.valid_types:
                if not self.is_load(collect_type):
                    self.load_collection_type(collect_type)
                for pkg_id in self.cache_object[collect_type]:
                    if self.cache_object[collect_type][pkg_id]["installed-type"]:
                        result[pkg_id] = self.cache_object[collect_type][pkg_id]
        return result

    def get_remote_packages(self, collect_type=None):
        result = {}
        if collect_type:
            if not self.is_load(collect_type):
                self.load_collection_type(collect_type)
            for pkg_id in self.cache_object[collect_type]:
                if not self.cache_object[collect_type][pkg_id]["installed-type"]:
                    result[pkg_id] = self.cache_object[collect_type][pkg_id]
        else:
            for collect_type in self.valid_types:
                if not self.is_load(collect_type):
                    self.load_collection_type(collect_type)
                for pkg_id in self.cache_object[collect_type]:
                    if not self.cache_object[collect_type][pkg_id]["installed-type"]:
                        result[pkg_id] = self.cache_object[collect_type][pkg_id]
        return result

    def get_all_packages(self, collect_type=None):
        #result = {}
        #if collect_type:
        #    if not self.is_load(collect_type):
        #        self.load_collection_type(collect_type)
        #    for pkg_id in self.cache_object[collect_type]:
        #        result[pkg_id] = self.cache_object[collect_type][pkg_id]
        #else:
        #    for collect_type in self.valid_types:
        #        if not self.is_load(collect_type):
        #            self.load_collection_type(collect_type)
        #        for pkg_id in self.cache_object[collect_type]:
        #            result[pkg_id] = self.cache_object[collect_type][pkg_id]
        #return result
        return self.cache_object[collect_type]

    def is_load(self, collect_type=None):
        if collect_type:#or is loading?
            return self.cache_is_load[collect_type]
        else:
            for collect_type in self.valid_types:
                if self.is_load(collect_type):
                    return True
            return False

    def load(self, callback=None):
        for collect_type in self.cache_object:
            self.load_collection_type(collect_type, callback)

    def load_collection_type(self, collect_type, callback=None):
        self.cache_is_load[collect_type] = True
        self._load_cache_online_type(collect_type)
        cache_installed = self._load_extensions(collect_type)
        self._merge_cache_info(cache_installed, collect_type)
        if callback and callable(callback):
            callback()

    def get_package_info(self, pkg_id, collect_type):
        if not self.is_load(collect_type):
            self.load_collection_type(collect_type)
        return self.cache_object[collect_type][pkg_id]

    def _resolve_id_for_collection(self, collect_type):
        collect_online = self.cache_object[collect_type]
        if collect_type == "theme":
            result = {}
            for pkg_id in collect_online:
                data_online = collect_online[pkg_id]
                icon_basename = self.sanitize_thumb(os.path.basename(data_online["screenshot"])) 
                data_online["icon-filename"] = icon_basename
                data_online["hide-configuration"] = False
                data = data_online["name"]
                try:
                    data = data.encode("UTF-8")
                except:
                    data = str(data)
                remplace_id = str.lower(data)
                result[remplace_id] = data_online
            self.cache_object[collect_type] = result
        else:
            for pkg_id in collect_online:
                data_online = collect_online[pkg_id]
                data_online["name"] = data_online["name"]
                data_online["hide-configuration"] = True
                icon_basename = os.path.basename(data_online["icon"])
                data_online["icon-filename"] = icon_basename

    def _merge_cache_info(self, cache_installed, collect_type):
        self._resolve_id_for_collection(collect_type)
        collect_install = cache_installed[collect_type]
        collect_online = self.cache_object[collect_type]
        cache_folder = self.get_cache_folder(collect_type)
        used_thumbs = []
        for pkg_id in collect_install:
            if not pkg_id in collect_online:
                collect_online[pkg_id] = collect_install[pkg_id]
            else:
                data_install = collect_install[pkg_id]
                data_online = collect_online[pkg_id]
                for key in data_install:
                   if not key in data_online:
                       data_online[key] = data_install[key]
                data_online["hide-configuration"] = data_install["hide-configuration"]
                data_online["settings-type"] = data_install["settings-type"]
                data_online["ext-setting-app"] = data_install["ext-setting-app"]
                data_online["schema-file"] = data_install["schema-file"]
                data_online["installed-folder"] = data_install["installed-folder"]
                data_online["install-edited"] = data_install["install-edited"]
                data_online["max-instances"] = data_install["max-instances"]
                if data_install["icon"]:
                    data_online["icon"] = data_install["icon"]
        for pkg_id in collect_online:
            data_online = collect_online[pkg_id]
            try: data_online["score"] = int(data_online["score"])
            except Exception: data_online["score"] = 0
            try: data_online["max-instances"] = int(data_online["max-instances"])
            except Exception: data_online["max-instances"] = 1
            try: data_online["spices-show"] = "'%s/%ss/view/%s'" % (URL_SPICES_HOME, collect_type, data_online["spices-id"])
            except KeyError: data_online["spices-show"] = ""
            except ValueError: data_online["spices-show"] = ""
            self._fix_last_edited(data_online)
            data_online["uuid"] = str(pkg_id)
            icon_path = ""
            if data_online["icon-filename"]:
                icon_basename = data_online["icon-filename"]
                used_thumbs.append(icon_basename)
                icon_path = os.path.join(cache_folder, icon_basename)
            if not pkg_id in collect_install:
                if icon_path:
                    data_online["icon"] = icon_path
                data_online["settings-type"] = SETTING_TYPE_NONE
                data_online["ext-setting-app"] = ""
                data_online["schema-file"] = ""
                data_online["installed-folder"] = ""
                data_online["collection"] = collect_type
                data_online["install-edited"] = -1
                data_online["max-instances"] = 1
                data_online["installed-type"] = 0
            else:
                can_update = data_online["install-edited"] != -1 and data_online["install-edited"] < data_online["last-edited"]
                if can_update:
                    data_online["installed-type"] = 2
                else:
                    data_online["installed-type"] = 1
            if not data_online["icon"]:
                data_online["icon"] = "cs-%ss" % (collect_type)

            if data_online["install-edited"] > 0:
                data_online["install-ver"] = datetime.datetime.fromtimestamp(data_online["install-edited"]).strftime("%Y-%m-%d\n%H:%M:%S")
            else:
                data_online["install-ver"] = ""
            if data_online["last-edited"] > 0:
                data_online["last-ver"] = datetime.datetime.fromtimestamp(data_online["last-edited"]).strftime("%Y-%m-%d\n%H:%M:%S")
            else:
                data_online["last-ver"] = ""
            
        GObject.idle_add(self._cleanup_obsolete_thumbs, used_thumbs, cache_folder)

    def _load_cache_online_type(self, collect_type):
        self.cache_object[collect_type] = {}
        cache_folder = self.get_cache_folder(collect_type)
        cache_file = os.path.join(cache_folder, "index.json")
        if os.path.exists(cache_file):
            f = open(cache_file, "r")
            try:
                self.cache_object[collect_type] = json.load(f)
            except ValueError:
                pass
                try:
                    self.cache_object[collect_type] = { }
                    os.remove(cache_file)
                except:
                    pass
                e = sys.exc_info()[1]
                print("Please try refreshing the list again. The online cache for %s is corrupted. %s" % (collect_type, str(e)))
                #self.errorMessage(_("Something went wrong with the spices download.  Please try refreshing the list again."), str(e))
        else:
            print("The online cache for %s is empty" % (collect_type))
            self.cache_object[collect_type] = { }

    def on_cache_refresh(self, collect_type, cache_data):
        #print("total spices loaded: %d" % len(cache_data))
        self._load_online_cache_type(collect_type)

    def is_update(self, collect_type, uuid):
        if uuid in self.cache_object[collect_type]:
            return self.cache_object[uuid]["last-edited"] > self.cache_object[uuid]["install-edited"]
        return False

    def get_default_icon(self, collect_type):
        if collect_type:
            return "cs-%ss" % collect_type
        return ""

    def _fix_last_edited(self, cache_data):
        if "last_edited" in cache_data:
            cache_data["last-edited"] = cache_data["last_edited"]
            del cache_data["last_edited"]
        if not "last-edited" in cache_data:
            cache_data["last-edited"] = -1
        else:
            try:
                cache_data["last-edited"] = long(cache_data["last-edited"])
            except:
                try:
                    cache_data["last-edited"] = int(cache_data["last-edited"])
                except:
                    cache_data["last-edited"] = -1
        return cache_data["last-edited"]

    def _load_extensions(self, collect_type):
        cache_installed = { collect_type: {} }
        if collect_type == "theme":
            self._load_extensions_in(cache_installed, collect_type, ("%s/.themes") % (HOME_PATH))
            self._load_extensions_in(cache_installed, collect_type, "/usr/share", True)
            self._load_extensions_in(cache_installed, collect_type, "/usr/share/themes")
        else:
            self._load_extensions_in(cache_installed, collect_type, ("%s/.local/share/cinnamon/%ss") % (HOME_PATH, collect_type))
            self._load_extensions_in(cache_installed, collect_type, ("/usr/share/cinnamon/%ss") % (collect_type))
        return cache_installed

    def _load_extensions_in(self, cache_installed, collect_type, directory, stock_theme = False):
        if collect_type == "theme":  # Theme handling
            if os.path.exists(directory) and os.path.isdir(directory):
                if stock_theme:
                    themes = ["Cinnamon"]
                else:
                    themes = os.listdir(directory)
                themes.sort()
                for theme in themes:
                    if theme in cache_installed[collect_type]:
                        continue  
                    if stock_theme:
                        theme_name = "Cinnamon"
                        theme_uuid = "STOCK"
                        install_folder = os.path.join(directory, "cinnamon/theme")
                    else:
                        theme_name = theme
                        theme_uuid = theme
                        install_folder = os.path.join(directory, theme, "cinnamon")
                    index_id = str.lower(theme_name)
                    try:
                        if os.path.exists(install_folder) and os.path.isdir(install_folder):
                            cache_installed[collect_type][index_id] = {}
                            metadata = os.path.join(install_folder, "metadata.json")
                            if os.path.exists(metadata):
                                json_data=open(metadata).read()
                                data = json.loads(json_data)
                                cache_installed[collect_type][index_id] = data
                            theme_json = os.path.join(install_folder, "theme.json")
                            if os.path.exists(theme_json):
                                json_data=open(theme_json).read()
                                data = json.loads(json_data)
                                if len(data.keys()) > 0:
                                    self._merge_json_data(cache_installed[collect_type][index_id], data[data.keys()[0]])

                            last_edited = -1
                            spices_show = ""
                            last_edited = self._fix_last_edited(cache_installed[collect_type][index_id])
                            if os.path.exists("%s/cinnamon.css" % install_folder):
                                if last_edited == -1:
                                    last_edited = os.path.getmtime("%s/cinnamon.css" % install_folder)
                            else:
                                raise Exception(_("Could not be locallized the file cinnamon.css."))

                            try: theme_uuid = str(cache_installed[collect_type][index_id]["uuid"])
                            except KeyError: theme_uuid = theme
                            except ValueError: theme_uuid = theme
                            theme_description = ""
                            icon = ""
                            if os.path.exists(os.path.join(install_folder, "thumbnail.png")):
                                icon = os.path.join(install_folder, "thumbnail.png")

                            cache_installed[collect_type][index_id]["uuid"] = theme_uuid
                            cache_installed[collect_type][index_id]["description"] = theme_name
                            cache_installed[collect_type][index_id]["max-instances"] = 1
                            cache_installed[collect_type][index_id]["icon"] = icon
                            cache_installed[collect_type][index_id]["name"] = theme_name
                            cache_installed[collect_type][index_id]["hide-configuration"] = True
                            cache_installed[collect_type][index_id]["ext-setting-app"] = ""
                            cache_installed[collect_type][index_id]["last-edited"] = -1
                            cache_installed[collect_type][index_id]["schema-file"] = ""
                            cache_installed[collect_type][index_id]["settings-type"] = SETTING_TYPE_NONE
                            cache_installed[collect_type][index_id]["installed-folder"] = install_folder
                            cache_installed[collect_type][index_id]["install-edited"] = last_edited
                            cache_installed[collect_type][index_id]["file"] = ""
                            cache_installed[collect_type][index_id]["collection"] = collect_type
                            cache_installed[collect_type][index_id]["score"] = 0
                            cache_installed[collect_type][index_id]["icon-filename"] = ""
                    except Exception:
                        e = sys.exc_info()[1]
                        if index_id in cache_installed[collect_type]:
                            del cache_installed[collect_type][index_id]
                        print("Failed to load extension %s: %s" % (theme, str(e)))
        else: # Applet, Desklet, Extension handling
            if os.path.exists(directory) and os.path.isdir(directory):
                extensions = os.listdir(directory)
                extensions.sort()
                for extension in extensions:
                    try:
                        if extension in cache_installed[collect_type]:
                            continue
                        install_folder = "%s/%s" % (directory, extension)
                        if os.path.exists("%s/metadata.json" % install_folder):
                            json_data=open("%s/metadata.json" % install_folder).read()
                            setting_type = 0
                            data = json.loads(json_data)
                            extension_uuid = data["uuid"]
                            cache_installed[collect_type][extension_uuid] = data
                            extension_name = data["name"]                                        
                            extension_description = data["description"]                          
                            try: max_instances = int(data["max-instances"])
                            except KeyError: max_instances = 1
                            except ValueError: max_instances = 1
                            if max_instances < -1:
                                max_instances = 1

                            try: extension_role = data["role"]
                            except KeyError: extension_role = None
                            except ValueError: extension_role = None

                            try: hide_config_button = data["hide-configuration"]
                            except KeyError: hide_config_button = False
                            except ValueError: hide_config_button = False

                            try:
                                ext_config_app = os.path.join(directory, extension, data["external-configuration-app"])
                                setting_type = SETTING_TYPE_EXTERNAL
                            except KeyError: ext_config_app = ""
                            except ValueError: ext_config_app = ""

                            if os.path.exists("%s/settings-schema.json" % install_folder):
                                setting_type = SETTING_TYPE_INTERNAL

                            last_edited = self._fix_last_edited(data)
                            if last_edited == -1:
                                last_edited = os.path.getmtime("%s/metadata.json" % install_folder)
                            try: schema_filename = data["schema-file"]
                            except KeyError: schema_filename = ""
                            except ValueError: schema_filename = ""

                            if ext_config_app != "" and not os.path.exists(ext_config_app):
                                ext_config_app = ""

                            extension_icon = ""
                            if "icon" in data:
                                extension_icon = data["icon"]
                            elif os.path.exists("%s/icon.png" % install_folder):
                                extension_icon = "%s/icon.png" % install_folder

                            cache_installed[collect_type][extension_uuid]["uuid"] = extension_uuid
                            cache_installed[collect_type][extension_uuid]["description"] = extension_description
                            cache_installed[collect_type][extension_uuid]["max-instances"] = max_instances
                            cache_installed[collect_type][extension_uuid]["icon"] = extension_icon
                            cache_installed[collect_type][extension_uuid]["name"] = extension_name
                            cache_installed[collect_type][extension_uuid]["hide-configuration"] = hide_config_button
                            cache_installed[collect_type][extension_uuid]["ext-setting-app"] = ext_config_app
                            cache_installed[collect_type][extension_uuid]["last-edited"] = -1
                            cache_installed[collect_type][extension_uuid]["schema-file"] = schema_filename
                            cache_installed[collect_type][extension_uuid]["settings-type"] = setting_type
                            cache_installed[collect_type][extension_uuid]["installed-folder"] = install_folder
                            cache_installed[collect_type][extension_uuid]["install-edited"] = last_edited
                            cache_installed[collect_type][extension_uuid]["file"] = ""
                            cache_installed[collect_type][extension_uuid]["collection"] = collect_type
                            cache_installed[collect_type][extension_uuid]["score"] = 0
                            cache_installed[collect_type][extension_uuid]["icon-filename"] = ""
                    except Exception:
                        e = sys.exc_info()[1]
                        print("Failed to load extension of %s: %s" % (extension, str(e)))

    def _merge_json_data(self, cache_extensions, data):
        if data:
            for key in data:
                cache_extensions[key] = data[key]

    def _cleanup_obsolete_thumbs(self, used_thumbs, cache_folder):
        trash = []
        flist = os.listdir(cache_folder)
        for f in flist:
            if f not in used_thumbs and f != "index.json":
                trash.append(f)
        for t in trash:
            try:
                os.remove(os.path.join(cache_folder, t))
            except:
                pass

    def get_assets_type_to_refresh(self, collect_type):
        index_cache = self.cache_object[collect_type]
        need_refresh = {}
        for uuid in index_cache:
            icon_path = index_cache[uuid]["icon"]
            if not os.path.isfile(icon_path):
                download_url = self.get_assets_url(collect_type, uuid)
                if download_url:
                    need_refresh[download_url] = index_cache[uuid]
        return need_refresh

    def sanitize_thumb(self, basename):
        return basename.replace("jpg", "png").replace("JPG", "png").replace("PNG", "png")

    def get_cache_folder(self, collect_type):
        cache_folder = "%s/.cinnamon/spices.cache/%s/" % (HOME_PATH, collect_type)

        if not os.path.exists(cache_folder):
            SystemTools.rec_mkdir(cache_folder)
        return cache_folder

    def get_cache_file(self, collect_type):
        return os.path.join(self.get_cache_folder(collect_type), "index.json")

    def get_install_folder(self, collect_type):
        if collect_type in ["applet","desklet","extension"]:
            install_folder = "%s/.local/share/cinnamon/%ss/" % (HOME_PATH, collect_type)
        elif collect_type == "theme":
            install_folder = "%s/.themes/" % (HOME_PATH)
        return install_folder

    def get_index_url(self, collect_type):
        if collect_type == "theme":
            return URL_SPICES_THEME_LIST
        elif collect_type == "extension":
            return URL_SPICES_EXTENSION_LIST
        elif collect_type == "applet":
            return URL_SPICES_APPLET_LIST
        elif collect_type == "desklet":
            return URL_SPICES_DESKLET_LIST
        else:
            return None

    def get_assets_url(self, collect_type, uuid):
        download_url = ""
        if uuid in self.cache_object[collect_type]:
            package = self.cache_object[collect_type][uuid]
            if package["icon-filename"]:
                if collect_type == "theme":
                    download_url = URL_SPICES_HOME + "/uploads/themes/thumbs/" + package["icon-filename"]
                else:
                    download_url = URL_SPICES_HOME + ("/uploads/%ss/%s" % (collect_type, package["icon-filename"]))
        return download_url

    def get_package_url(self, collect_type, uuid):
        download_url = ""
        if uuid in self.cache_object[collect_type]:
            download_url = URL_SPICES_HOME + self.cache_object[collect_type][uuid]["file"]
        return download_url

    def _scrubConfigDirs(self, enabled_list): #We need to do that on some places. Maybe as idle on some this is return?
        active_list = {}
        for enabled in enabled_list:
            if self.collection_type == "applet":
                panel, align, order, uuid, id = enabled.split(":")
            elif self.collection_type == "desklet":
                uuid, id, x, y = enabled.split(":")
            else:
                uuid = enabled
                id = 0
            if uuid not in active_list:
                id_list = []
                active_list[uuid] = id_list
                active_list[uuid].append(id)
            else:
                active_list[uuid].append(id)

        for uuid in active_list.keys():
            if (os.path.exists(os.path.join(SETTINGS_PATH, uuid))):
                dir_list = os.listdir(os.path.join(SETTINGS_PATH, uuid))
                for id in active_list[uuid]:
                    fn = str(id) + ".json"
                    if fn in dir_list:
                        dir_list.remove(fn)
                fn = str(uuid) + ".json"
                if fn in dir_list:
                    dir_list.remove(fn)
                for jetsam in dir_list:
                    try:
                        os.remove(os.path.join(SETTINGS_PATH, uuid, jetsam))
                    except:
                        pass

    def from_setting_string(self, collect_type, string):
        if collect_type == "theme":
            return string
        elif collect_type == "extension":
            return string
        elif collect_type == "applet":
            panel, side, position, uuid, instanceId = string.split(":")
            return uuid
        elif collect_type == "desklet":
            uuid, instanceId, x, y = string.split(":")
            return uuid
        else:
            return None
