#!/usr/bin/python
# -*- coding:utf-8 -*-
#
#
# Authors: Lester Carballo Pérez <lestcape@gmail.com>
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

from gi.repository import Gtk, Gdk, GObject, Pango
import sys, os, subprocess

DIR_PATH = "/usr/lib/cinnamon-installer/"
if not os.path.exists(DIR_PATH):
    ABS_PATH = os.path.abspath(__file__)
    DIR_PATH = os.path.dirname(os.path.dirname(ABS_PATH)) + "/"

LIBS_PATH = os.path.join(DIR_PATH + "lib")
INST_PATH = os.path.join(DIR_PATH + "installer_modules")
SETT_PATH = os.path.join(DIR_PATH + "settings_modules")
if not LIBS_PATH in sys.path:
    sys.path.append(LIBS_PATH)
if not INST_PATH in sys.path:
    sys.path.append(INST_PATH)
if not SETT_PATH in sys.path:
    sys.path.append(SETT_PATH)

try:
    from XletInstallerModules import *
    from SettingsInstallerWidgets import *
    import InstallerProviders, SystemTools
    try:
        import json
    except ImportError:
        import simplejson as json
except Exception:
    e = sys.exc_info()[1]
    print(str(e))
    sys.exit(1)

HOME_PATH = SystemTools.get_home()

Gtk.IconTheme.get_default().append_search_path(os.path.join(DIR_PATH, "gui/img"))
#Gtk.IconTheme.get_default().append_search_path("/usr/share/icons/hicolor/scalable/categories")

class Module:
    def __init__(self, content_box):
        self.keywords = _("installer")
        self.name = "installer"
        self.fileName = "cs_installer"  
        self.comment = _("Manage Cinnamon extensions and packages")
        self.category = "prefs"
        self.icon = "cinnamon-installer"
        self.sidePage = SidePage(_("Cinnamon Installer"), self.icon, self.keywords, content_box, module=self)
        #self.managerBuilder = Gtk.Builder()
        self.modules = {}
        self.categories_view = None
        self.currentModule = None
        self.content_installer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.store = Gtk.ListStore(str,    str,    object)
        self.bar_heights = 0
        self.first_category_done = False
        self.sidePageHacker = CinnamonSettingsSidePageHacker(self)
        self.installer = InstallerProviders.get_default()
        #self.installer.load_cache()#crap

    def on_module_selected(self):
        if not self.loaded:
            print("Loading Installer module")
            self.builder.add_from_file(os.path.join(DIR_PATH, "gui/manager.ui"))
            self.installer.load_module(self.currentModule)
            self.manager_sidepage = self.builder.get_object("manager_sidepage")
            self.general_settings_scroll = self.builder.get_object("general_settings_scroll")
            self.categories_view = self.builder.get_object("categories_view")
            self.load_progress = self.builder.get_object("load_progress")
            self.search_entry = self.builder.get_object("search_entry")
            self.menu_box = self.builder.get_object("menu_box")
            self.packages_manager_paned = self.builder.get_object("packages_manager_paned")
            self.temporal_side_page = self.builder.get_object("temporal_side_page")

            self.xlet_main_box = self.builder.get_object("xlet_main_box")
            self.configure_xlet_button = self.builder.get_object("xlet_configure")
            self.back_to_list_button = self.builder.get_object("back_to_list")

            self.configure_xlet_button.connect("clicked", self._configure_extension)
            self.back_to_list_button.connect("clicked", self.on_back_to_list_button_clicked)

            bg = SectionBg()
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            #vbox.add(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))
            vbox.add(self.manager_sidepage)
            bg.add(vbox)
            self.sidePage.add_widget(bg)
            self.window.resize(800, 600)
            self.temporal_side_page.pack_start(self.content_installer_box, True, True, 0)
            self.displayCategories()
            self.loadGeneralSettings()
        self.buildModule(self.currentModule)

    def checked_installer_arg(self):
        mod_len = len(sys.argv)
        if mod_len > 2 and self.sidePageHacker.sys_arg == self.name:
            if sys.argv[2] == "check-update":
                print("check update")
                self.check_update_silent()

    def check_update_silent(self):
        updates = self.installer.check_update_silent()

    def display_action(self):
        if ((self.sidePageHacker.sys_arg) and (len(sys.argv) > 2) and
            ("cs_" + self.sidePageHacker.sys_arg in self.modules)):
            self.sidePageHacker.sys_arg = None
            self._configure_extension()
        else:
            self.on_back_to_list_button_clicked()

    def _configure_extension(self, widget = None):
        if (not widget) or (widget and widget.get_sensitive()):
            print("configure")
            self.packages_manager_paned.hide()
            self.general_settings_scroll.hide()
            self.xlet_main_box.show()

    def on_back_to_list_button_clicked(self, widget = None):
        self.xlet_main_box.hide()
        self.general_settings_scroll.hide()
        self.packages_manager_paned.show()

    def _setParentRef(self, window, builder = None):
        self.builder = builder
        if self.builder is None:
            self.builder = Gtk.Builder()
        self.builder.add_from_file("/usr/lib/cinnamon-settings/cinnamon-settings-spice-progress.ui")
        self.window = window
        self.sidePage.window = self.window
        #self.sidePage.builder = self.builder
        self.installer.setParentRef(self.window, self.builder)
        modules = self.sidePageHacker._setParentRef(self.window, self.builder)
        self.prepare_swapper(modules)
        self.checked_installer_arg()

    '''
    def build(self, moduleName):
        self.currentModule = self.getModule(moduleName)
        self.sidePage.build()

    def getModule(self, moduleName):
        for mod_filename in self.modules:
            if self.modules[mod_filename].sidePage.name == moduleName:
                return self.modules[mod_filename]
        return None
   '''

    def buildModule(self, module):
        self.set_select_module(module)
        module.sidePage.build()
        self.display_action()
        self.configure_xlet_button.connect("clicked", self._configure_extension)
        self.back_to_list_button.connect("clicked", self.on_back_to_list_button_clicked)

    def set_current_module(self, module):
        self.currentModule = module

    def set_select_module(self, module):
        if self.categories_view:
            iter = self.store.get_iter_first()
            while iter is not None:
                sidePage = self.store.get_value(iter, 2)
                if module.sidePage == sidePage:
                    path = self.store.get_path(iter)
                    self.categories_view.select_path(path)
                    break
                iter = self.store.iter_next(iter)

    def prepare_swapper(self, modules):
        ##Added one module to init
        added_keys = modules.keys()
        sorted_keys = sorted(added_keys, key=cmp_to_key(locale.strcoll))
        if len(sorted_keys) > 0:
            self.set_current_module(modules[sorted_keys[0]])
        else:
            raise Exception("No settings modules found!!")
        #                          Label   Icon    SidePage
        self.store = Gtk.ListStore(str,    str,    object)
        for mod_name in sorted_keys:
           if mod_name != self.fileName:
               self.modules[mod_name] = modules[mod_name]
               self.installer.register_module(self.modules[mod_name])
               sp = self.modules[mod_name].sidePage
               # Don't allow item names (and their translations) to be more than 30 chars long. It looks ugly and it creates huge gaps in the icon views
               name = str(sp.name)
               try:
                   name = unicode(name, "utf-8")
               except:
                   pass
               if len(name) > 30:
                   name = "%s..." % name[:30]
               self.store.append([name, sp.icon, sp])
        self.min_label_length = 0
        self.min_pix_length = 0
        self.validate_label_space(self.store)

    def validate_label_space(self, model):
        char, pix = self.sidePageHacker.get_label_min_width(self.store)
        self.min_label_length = max(char, self.min_label_length)
        self.min_pix_length = max(pix, self.min_pix_length)

        self.min_label_length += 2
        self.min_pix_length += 4

        self.min_label_length = max(self.min_label_length, MIN_LABEL_WIDTH)
        self.min_pix_length = max(self.min_pix_length, MIN_PIX_WIDTH)

        self.min_label_length = min(self.min_label_length, MAX_LABEL_WIDTH)
        self.min_pix_length = min(self.min_pix_length, MAX_PIX_WIDTH)

    def displayCategories(self):
        area = self.categories_view.get_area()
        self.categories_view.set_item_width(self.min_pix_length - 50)

        pixbuf_renderer = Gtk.CellRendererPixbuf()
        text_renderer = Gtk.CellRendererText(ellipsize=Pango.EllipsizeMode.NONE, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                             wrap_width=0, width_chars=self.min_label_length, alignment=Pango.Alignment.CENTER)
        text_renderer.set_alignment(.5, 0)
        area.pack_start(pixbuf_renderer, True, True, False)
        area.pack_start(text_renderer, True, True, False)
        area.add_attribute(pixbuf_renderer, "icon-name", 1)
        pixbuf_renderer.set_property("stock-size", Gtk.IconSize.DIALOG)
        pixbuf_renderer.set_property("follow-state", True)

        area.add_attribute(text_renderer, "text", 0)

        css_provider = Gtk.CssProvider()
        css_data = "GtkIconView {                     \
                       background-color: transparent; \
                    }                                 \
                    GtkIconView.view.cell:selected {  \
                       background-color: blue;        \
                    }"
        css_provider.load_from_data(css_data.encode())#@selected_bg_color
        c = self.categories_view.get_style_context()
        c.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.categories_view.set_model(self.store)
        self.categories_view.connect("item-activated", self.side_view_nav)
        self.categories_view.connect("button-release-event", self.categories_button_press)
        #self.categories_view.connect("keynav-failed", self.on_keynav_failed)
        #self.categories_view.show_all()

    def categories_button_press(self, widget, event):
        if event.button == 1:
            self.side_view_nav(widget, None)

    def side_view_nav(self, side_view, path):
        selected_items = side_view.get_selected_items()
        if len(selected_items) > 0:
            self.go_to_sidepage(selected_items[0])

    def go_to_sidepage(self, path):
        iterator = self.store.get_iter(path)
        sidePage = self.store.get_value(iterator, 2)
        self.buildModule(sidePage.module)

    def loadGeneralSettings(self):
        self.integrate_checkbutton = self.builder.get_object("integrate_checkbutton")
        if os.path.isfile("/usr/lib/cinnamon-settings/modules/cs_installer.py"):
            self.integrate_checkbutton.set_active(True)
        else:
            self.integrate_checkbutton.set_active(False)
        self.integrate_checkbutton.connect("toggled", self.on_integrate_toggled)

        self.installed_color = self.builder.get_object("installed_colorbutton")
        self.reinstalled_color = self.builder.get_object("reinstalled_colorbutton")
        self.removed_color = self.builder.get_object("removed_colorbutton")
        self.updated_color = self.builder.get_object("updated_colorbutton")
        self.installed_color.connect("color-set", self.safe_settings)
        self.reinstalled_color.connect("color-set", self.safe_settings)
        self.removed_color.connect("color-set", self.safe_settings)
        self.updated_color.connect("color-set", self.safe_settings)
        self.load_settings()

    def load_settings(self):
        settings_file = os.path.join(HOME_PATH, ".config/cinnamon-installer.json")
        if os.path.exists(settings_file):
            f = open(settings_file, "r")
            try:
                self.settings = json.load(f)
            except ValueError:
                pass
                try:
                    settings = { }
                    os.remove(settings_file)
                except:
                    pass
                self.safe_settings()
        else:
            self.safe_settings()
            self.settings = { }
        if len(self.settings.keys()) > 0:
            color = Gdk.RGBA()
            color.parse(self.settings["installed-color"])
            self.installed_color.set_rgba(color)
            color.parse(self.settings["reinstalled-color"])
            self.reinstalled_color.set_rgba(color)
            color.parse(self.settings["removed-color"])
            self.removed_color.set_rgba(color)
            color.parse(self.settings["updated-color"])
            self.updated_color.set_rgba(color)

    def safe_settings(self, widget=None):
        settings_file = os.path.join(HOME_PATH, ".config/cinnamon-installer.json")
        self.settings = {}
        self.settings["installed-color"] = self.installed_color.get_rgba().to_string()
        self.settings["reinstalled-color"] = self.reinstalled_color.get_rgba().to_string()
        self.settings["removed-color"] = self.removed_color.get_rgba().to_string()
        self.settings["updated-color"] = self.updated_color.get_rgba().to_string()
        with open(settings_file, "w") as outfile:
            json.dump(self.settings, outfile)

    def on_integrate_toggled(self, menuitem):
        have_module = os.path.isfile("/usr/lib/cinnamon-settings/modules/cs_installer.py")
        if (self.integrate_checkbutton.get_active()):
            if not have_module:
                setup = os.path.join(DIR_PATH, "tools/setup.py")
                p = subprocess.call([setup, "-m"])
                if not os.path.isfile("/usr/lib/cinnamon-settings/modules/cs_installer.py"):
                    self.integrate_checkbutton.set_active(False)   
        else:
            if have_module:
                setup = os.path.join(DIR_PATH, "tools/setup.py")
                p = subprocess.call([setup, "-d"])
                if os.path.isfile("/usr/lib/cinnamon-settings/modules/cs_installer.py"):
                    self.integrate_checkbutton.set_active(True)
