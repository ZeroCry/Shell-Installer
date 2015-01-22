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
from ExtensionInstallerCore import ExtensionSidePage
from gi.repository import GObject
from gi.repository.Gtk import SizeGroup, SizeGroupMode
from SettingsInstallerWidgets import *

import SystemTools

ICON_SIZE = 48
HOME_PATH = SystemTools.get_home() #os.path.expanduser("~")

def sortArr(listSA): #change to support python3
    try:
        listSA.sort(lambda a,b: cmp(a[0].lower(), b[0].lower()))
    except:
        sorted(listSA, key=getKey)

def sortVal(listS):
    try:
        listS.sort(lambda a,b: cmp(a.lower(), b.lower()))
    except:
        sorted(listS)

def getKey(item):
    return item[0]

class Module:
    def __init__(self, content_box):
        self.keywords = _("themes, style")
        self.icon = "cs-themes"
        sidePage = ThemesViewSidePage(_("Themes"), self.icon, self.keywords, content_box, "theme", self)
        self.sidePage = sidePage
        self.comment = _("Manage themes to change how your desktop looks")
        self.name = "themes"
        self.category = "appear"

    def on_module_selected(self):
        if not self.loaded:
            print("Loading Themes module")
            self.sidePage.load()
        #GObject.idle_add(self.refresh_windows)

    def refresh_windows(self):
        width, height = self.sidePage.window.get_size()
        self.sidePage.window.resize(width + 1, height + 1)

    def _setParentRef(self, window, builder):
        self.sidePage.window = window
        self.sidePage.builder = builder

class ThemesViewSidePage (ExtensionSidePage):
    def __init__(self, name, icon, keywords, content_box, collection_type, module):
        ExtensionSidePage.__init__(self, name, icon, keywords, content_box, collection_type, module)
        self.scrolled_window = None

    def toSettingString(self, uuid, instanceId):
        if uuid == "STOCK":
           return ""
        return uuid

    def fromSettingString(self, string):
        return string

    def getAdditionalPage(self):
        if not self.scrolled_window:         
            self.scrolled_window = Gtk.ScrolledWindow()
            self.scrolled_window.label = Gtk.Label.new(_("General Themes Settings"))
            config_vbox = Gtk.VBox()
            config_vbox.set_border_width(5)
            self.scrolled_window.add_with_viewport(config_vbox)
 
            self.if_settings = Gio.Settings.new("org.cinnamon.desktop.interface")
            self.wm_settings = Gio.Settings.new("org.cinnamon.desktop.wm.preferences")
            self.cinnamon_settings = Gio.Settings.new("org.cinnamon.theme")

            section = Section(_("Themes")) 
            try:
                self.icon_chooser = self.create_button_chooser(self.if_settings, "icon-theme", "icons", "icons",
                                                               button_picture_size=ICON_SIZE, menu_pictures_size=ICON_SIZE, num_cols=4)
                self.cursor_chooser = self.create_button_chooser(self.if_settings, "cursor-theme", "icons", "cursors",
                                                               button_picture_size=32, menu_pictures_size=32, num_cols=4)
                self.theme_chooser = self.create_button_chooser(self.if_settings, "gtk-theme", "themes", "gtk-3.0",
                                                               button_picture_size=35, menu_pictures_size=120, num_cols=4)
                self.metacity_chooser = self.create_button_chooser(self.wm_settings, "theme", "themes", "metacity-1",
                                                               button_picture_size=32, menu_pictures_size=100, num_cols=4)
                self.cinnamon_chooser = self.create_button_chooser(self.cinnamon_settings, "name", "themes", "cinnamon",
                                                               button_picture_size=60, menu_pictures_size=100, num_cols=4)
                section.add(self.make_group(_("Window borders"), self.metacity_chooser))
                section.add(self.make_group(_("Icons"), self.icon_chooser)) 
                section.add(self.make_group(_("Controls"), self.theme_chooser))                       
                section.add(self.make_group(_("Mouse Pointer"), self.cursor_chooser))
                section.add(self.make_group(_("Desktop"), self.cinnamon_chooser))
                self.new_themes = True
            except:
                section.add(self._make_group_old(_("Controls"), "org.cinnamon.desktop.interface", "gtk-theme", self._load_gtk_themes_old()))
                section.add(self._make_group_old(_("Icons"), "org.cinnamon.desktop.interface", "icon-theme", self._load_icon_themes_old()))
                section.add(self._make_group_old(_("Window borders"), "org.cinnamon.desktop.wm.preferences", "theme", self._load_window_themes_old()))
                section.add(self._make_group_old(_("Mouse Pointer"), "org.cinnamon.desktop.interface", "cursor-theme", self._load_cursor_themes_old()))
                section.add(self._make_group_old(_("Keybindings"), "org.cinnamon.desktop.interface", "gtk-key-theme", self._load_keybinding_themes_old()))
                self.new_themes = False
            
            config_vbox.add(section)

            config_vbox.add(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))

            section = Section(_("Options"))
            section.add(GSettingsCheckButton(_("Show icons in menus"), "org.cinnamon.settings-daemon.plugins.xsettings", "menus-have-icons", None))
            section.add(GSettingsCheckButton(_("Show icons on buttons"), "org.cinnamon.settings-daemon.plugins.xsettings", "buttons-have-icons", None))                        
            config_vbox.add(section)

            if self.new_themes:
                self.monitors = []
                for path in [os.path.join(HOME_PATH, ".themes"), "/usr/share/themes", os.path.join(HOME_PATH, ".icons"), "/usr/share/icons"]:
                    if os.path.exists(path):
                        file_obj = Gio.File.new_for_path(path)
                        file_monitor = file_obj.monitor_directory(Gio.FileMonitorFlags.SEND_MOVED, None)
                        file_monitor.connect("changed", self.on_file_changed)
                        self.monitors.append(file_monitor)

                self.refresh() 
        return self.scrolled_window

    def on_file_changed(self, file, other, event, data):
        self.refresh()

    def refresh(self):
        choosers = []
        choosers.append((self.cursor_chooser, "cursors", self._load_cursor_themes(), self._on_cursor_theme_selected))
        choosers.append((self.theme_chooser, "gtk-3.0", self._load_gtk_themes(), self._on_gtk_theme_selected))
        choosers.append((self.metacity_chooser, "metacity-1", self._load_metacity_themes(), self._on_metacity_theme_selected))
        choosers.append((self.cinnamon_chooser, "cinnamon", self._load_cinnamon_themes(), self._on_cinnamon_theme_selected))
        choosers.append((self.icon_chooser, "icons", self._load_icon_themes(), self._on_icon_theme_selected))
        for chooser in choosers:
            chooser[0].clear_menu()
            chooser[0].set_sensitive(False)
            chooser[0].progress = 0.0

            chooser_obj = chooser[0]
            path_suffix = chooser[1]
            themes = chooser[2]
            callback = chooser[3]
            payload = (chooser_obj, path_suffix, themes, callback)
            self.refresh_chooser(payload)
            #thread = Thread(target = self.refresh_chooser, args=(payload,))
            #thread.start()
            #thread.start_new_thread(self.refresh_chooser, (payload,))

    def refresh_chooser(self, payload):
        (chooser, path_suffix, themes, callback) = payload

        inc = 1.0
        theme_len = len(themes)
        if theme_len > 0:
            inc = 1.0 / theme_len 
        if path_suffix == "icons":            
            for theme in themes:
                if theme == "default":
                    theme = Gtk.Settings.get_default().get_property('gtk-icon-theme-name')
                icon_theme = Gtk.IconTheme()
                icon_theme.set_custom_theme(theme)
                folder = icon_theme.lookup_icon("folder", ICON_SIZE, Gtk.IconLookupFlags.FORCE_SVG)
                if folder:
                    path = folder.get_filename()
                    chooser.add_picture(path, callback, title=theme, id=theme)
                GObject.timeout_add(5, self.increment_progress, (chooser,inc)) 
        else:
            if path_suffix == "cinnamon":
                chooser.add_picture("/usr/share/cinnamon/theme/thumbnail.png", callback, title="cinnamon", id="cinnamon") 
            for theme in themes:
                theme_name = theme[0]
                theme_path = theme[1]
                for path in ["%s/%s/%s/thumbnail.png" % (theme_path, theme_name, path_suffix), 
                             "/usr/share/cinnamon/thumbnails/%s/%s.png" % (path_suffix, theme_name), 
                             "/usr/share/cinnamon/thumbnails/%s/unknown.png" % path_suffix]:
                    if os.path.exists(path):                    
                        chooser.add_picture(path, callback, title=theme_name, id=theme_name)
                        break
                GObject.timeout_add(5, self.increment_progress, (chooser, inc))
        GObject.timeout_add(500, self.hide_progress, chooser)
        #thread.exit()

    def increment_progress(self, payload):
        (chooser, inc) = payload
        chooser.increment_loading_progress(inc)

    def hide_progress(self, chooser):
        chooser.set_sensitive(True)
        chooser.reset_loading_progress()

    def make_group(self, group_label, widget, add_widget_to_size_group=True):
        self.size_groups = getattr(self, "size_groups", [Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL) for x in range(2)])        
        #box = IndentedHBox()
        box = Gtk.VBox()
        label = Gtk.Label()
        label.set_markup(group_label)
        label.props.xalign = 0.0
        self.size_groups[0].add_widget(label)
        box.pack_start(label, False, False, 0)

        if add_widget_to_size_group:       
            self.size_groups[1].add_widget(widget)
        box.pack_start(widget, False, False, 15)

        return box

    def _make_group_old(self, group_label, root, key, schema):
        self.size_groups = getattr(self, "size_groups", [SizeGroup.new(SizeGroupMode.HORIZONTAL) for x in range(2)])
        
        box = Gtk.HBox()
        label = Gtk.Label()
        label.set_markup(group_label)
        label.props.xalign = 0.0
        self.size_groups[0].add_widget(label)
        box.pack_start(label, False, False, 4)

        w = GSettingsComboBox("", root, key, None, schema)
        self.size_groups[1].add_widget(w)
        box.add(w)
        
        return box
         
    def create_button_chooser(self, settings, key, path_prefix, path_suffix, button_picture_size, menu_pictures_size, num_cols):        
        chooser = PictureChooserButton(num_cols=num_cols, button_picture_size=button_picture_size, menu_pictures_size=menu_pictures_size, has_button_label=True)
        theme = settings.get_string(key)
        chooser.set_button_label(theme)
        chooser.set_tooltip_text(theme)
        if path_suffix == "cinnamon" and theme == "cinnamon":
            chooser.set_picture_from_file("/usr/share/cinnamon/theme/thumbnail.png")
        elif path_suffix == "icons":
            current_theme = Gtk.IconTheme.get_default()
            folder = current_theme.lookup_icon("folder", button_picture_size, 0)
            path = folder.get_filename()
            chooser.set_picture_from_file(path)
        else:
            for path in ["/usr/share/%s/%s/%s/thumbnail.png" % (path_prefix, theme, path_suffix), 
                         os.path.join(HOME_PATH, ".%s/%s/%s/thumbnail.png" % (path_prefix, theme, path_suffix)), 
                         "/usr/share/cinnamon/thumbnails/%s/%s.png" % (path_suffix, theme), 
                         "/usr/share/cinnamon/thumbnails/%s/unknown.png" % path_suffix]:                        
                if os.path.exists(path):
                    chooser.set_picture_from_file(path)
                    break
        #GObject.signal_handlers_destroy(chooser)
        #chooser.connect("button-release-event", self._on_button_clicked)     
        return chooser

    def _on_button_clicked(self, widget, event):
        if event.button == 1:
            widget.menu.show_all()
            widget.menu.popup(None, None, 
                   lambda menu, data: (event.get_root_coords()[0],
                                       event.get_root_coords()[1], True),
                   None, event.button, event.time)

    def _on_icon_theme_selected(self, path, theme):
        try:
            self.if_settings.set_string("icon-theme", theme)
            self.icon_chooser.set_button_label(theme)
            self.icon_chooser.set_tooltip_text(theme)
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))     
        return True

    def _on_metacity_theme_selected(self, path, theme):
        try:
            self.wm_settings.set_string("theme", theme)
            self.metacity_chooser.set_button_label(theme)
            self.metacity_chooser.set_tooltip_text(theme)
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))        
        return True

    def _on_gtk_theme_selected(self, path, theme):
        try:
            self.if_settings.set_string("gtk-theme", theme)
            self.theme_chooser.set_button_label(theme)
            self.theme_chooser.set_tooltip_text(theme)
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))            
        return True

    def _on_cursor_theme_selected(self, path, theme):
        try:
            self.if_settings.set_string("cursor-theme", theme)
            self.cursor_chooser.set_button_label(theme)
            self.cursor_chooser.set_tooltip_text(theme)
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))           
        return True

    def _on_cinnamon_theme_selected(self, path, theme):
        try:
            self.cinnamon_settings.set_string("name", theme)
            self.cinnamon_chooser.set_button_label(theme)
            self.cinnamon_chooser.set_tooltip_text(theme)
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))       
        return True

    def _load_gtk_themes(self):
        """ Only shows themes that have variations for gtk+-3 and gtk+-2 """
        dirs = ("/usr/share/themes", os.path.join(HOME_PATH, ".themes"))
        valid = walk_directories(dirs, lambda d: os.path.exists(os.path.join(d, "gtk-2.0")) and os.path.exists(os.path.join(d, "gtk-3.0")), return_directories=True)
        #valid.sort(lambda a,b: cmp(a[0].lower(), b[0].lower()))
        sortArr(valid)
        res = []
        for i in valid:
            if i[0] == "default":
                i[0] = Gtk.Settings.get_default().get_property('gtk-icon-theme-name')
            res.append((i[0], i[1]))
        return res
    
    def _load_icon_themes(self):
        dirs = ("/usr/share/icons", os.path.join(HOME_PATH, ".icons"))
        valid = walk_directories(dirs, lambda d: os.path.isdir(d) and not os.path.exists(os.path.join(d, "cursors")) and os.path.exists(os.path.join(d, "index.theme")))
        #valid.sort(lambda a,b: cmp(a.lower(), b.lower()))
        sortVal(valid)
        res = []
        for i in valid:
            res.append(i)
        return res
        
    def _load_cursor_themes(self):
        dirs = ("/usr/share/icons", os.path.join(HOME_PATH, ".icons"))
        valid = walk_directories(dirs, lambda d: os.path.isdir(d) and os.path.exists(os.path.join(d, "cursors")), return_directories=True)
        #valid.sort(lambda a,b: cmp(a[0].lower(), b[0].lower()))
        sortArr(valid)
        res = []
        for i in valid:
            res.append((i[0], i[1]))
        return res
        
    def _load_metacity_themes(self):
        dirs = ("/usr/share/themes", os.path.join(HOME_PATH, ".themes"))
        valid = walk_directories(dirs, lambda d: os.path.exists(os.path.join(d, "metacity-1")), return_directories=True)
        #valid.sort(lambda a,b: cmp(a[0].lower(), b[0].lower()))
        sortArr(valid)
        res = []
        for i in valid:
            res.append((i[0], i[1]))
        return res

    def _load_cinnamon_themes(self):
        dirs = ("/usr/share/themes", os.path.join(HOME_PATH, ".themes"))
        valid = walk_directories(dirs, lambda d: os.path.exists(os.path.join(d, "cinnamon")), return_directories=True)
        #valid.sort(lambda a,b: cmp(a[0].lower(), b[0].lower()))
        sortArr(valid)
        res = []        
        for i in valid:
            res.append((i[0], i[1]))
        return res

    def _load_gtk_themes_old(self):
        """ Only shows themes that have variations for gtk+-3 and gtk+-2 """
        dirs = ("/usr/share/themes", os.path.join(HOME_PATH, ".themes"))
        valid = walk_directories(dirs, lambda d: os.path.exists(os.path.join(d, "gtk-2.0")) and os.path.exists(os.path.join(d, "gtk-3.0")))
        #valid.sort(lambda a,b: cmp(a.lower(), b.lower()))
        sortVal(valid)
        res = []
        for i in valid:
            res.append((i, i))
        return res
    
    def _load_icon_themes_old(self):
        dirs = ("/usr/share/icons", os.path.join(HOME_PATH, ".icons"))
        valid = walk_directories(dirs, lambda d: os.path.isdir(d) and not os.path.exists(os.path.join(d, "cursors")) and os.path.exists(os.path.join(d, "index.theme")))
        #valid.sort(lambda a,b: cmp(a.lower(), b.lower()))
        sortVal(valid)
        res = []
        for i in valid:
            res.append((i, i))
        return res
        
    def _load_keybinding_themes_old(self):
        dirs = ("/usr/share/themes", os.path.join(HOME_PATH, ".themes"))
        valid = walk_directories(dirs, lambda d: os.path.isfile(os.path.join(d, "gtk-3.0", "gtk-keys.css")) and os.path.isfile(os.path.join(d, "gtk-2.0-key", "gtkrc")))
        #valid.sort(lambda a,b: cmp(a.lower(), b.lower()))
        sortVal(valid)
        res = []
        for i in valid:
            res.append((i, i))
        return res
        
    def _load_cursor_themes_old(self):
        dirs = ("/usr/share/icons", os.path.join(HOME_PATH, ".icons"))
        valid = walk_directories(dirs, lambda d: os.path.isdir(d) and os.path.exists(os.path.join(d, "cursors")))
        #valid.sort(lambda a,b: cmp(a.lower(), b.lower()))
        sortVal(valid)
        res = []
        for i in valid:
            res.append((i, i))
        return res
        
    def _load_window_themes_old(self):
        dirs = ("/usr/share/themes", os.path.join(HOME_PATH, ".themes"))
        valid = walk_directories(dirs, lambda d: os.path.exists(os.path.join(d, "metacity-1")))
        #valid.sort(lambda a,b: cmp(a.lower(), b.lower()))
        sortVal(valid)
        res = []
        for i in valid:
            res.append((i, i))
        return res
