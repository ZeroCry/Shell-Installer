#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# Cinnamon Installer
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

from __future__ import print_function

import sys, os

try:
    from SettingsInstallerWidgets import SidePage, SectionBg
    import XletInstallerSettings as XletSettings
    from SpicesInstaller import Spice_Harvester
    from threading import Thread, Lock
    #from Spices import *
    try: #aparently not needed
        import urllib2
    except:
        import urllib.request as urllib2
    try:
        import html2text
    except:
        html2text = None
    try:
        import json
    except ImportError:
        import simplejson as json
    import gettext
    import locale
    import time
    from gi.repository import Gio, Gtk, GObject, Gdk, GdkPixbuf, Pango, GLib
    import dbus
    import cgi
    import subprocess
    import datetime
    from functools import cmp_to_key
except Exception:
    e = sys.exc_info()[1]
    print(str(e))
    sys.exit(1)

#'markup',"<span color='#0000FF'>%s</span>" % _("More info")

home = os.path.expanduser("~")

SHOW_ALL = 0
SHOW_ACTIVE = 1
SHOW_INACTIVE = 2
SHOW_INSTALLED = 3
SHOW_ONLINE = 4
SHOW_BROKEN = 5
SHOW_SETTINGS = 6

SETTING_TYPE_NONE = 0
SETTING_TYPE_INTERNAL = 1
SETTING_TYPE_EXTERNAL = 2

ROW_SIZE = 32

class SurfaceWrapper:
    def __init__(self, surface):
        self.surface = surface

class ExtensionSidePage (SidePage):
    SORT_NAME = 0
    SORT_RATING = 1
    SORT_DATE_EDITED = 2
    SORT_ENABLED = 3
    SORT_REMOVABLE = 4  

    def __init__(self, name, icon, keywords, content_box, collection_type, module=None):
        SidePage.__init__(self, name, icon, keywords, content_box, -1, module=module)
        self.collection_type = collection_type
        self.themes = collection_type == "theme"
        self.icons = []
        self.run_once = False
        # Find the enabled extensions
        if not self.themes:
            self.settings = Gio.Settings.new("org.cinnamon")
            self.enabled_extensions = self.settings.get_strv("enabled-%ss" % (self.collection_type))
            self.settings.connect(("changed::enabled-%ss") % (self.collection_type), lambda x,y: self._enabled_extensions_changed())
        else:
            self.settings = Gio.Settings.new("org.cinnamon.theme")
            self.enabled_extensions = [self.settings.get_string("name")]
            self.settings.connect("changed::name", lambda x,y: self._enabled_extensions_changed())
        self.model = None
        self.treeview = None
        self.last_col_selected = None
        self.progress_window = None
        self.extensions_is_loading = False
        self.extensions_is_loaded = False
        self.spicesData = None
        self.modelfilter = None

    def load(self, window=None):
        if window is not None:
            self.window = window

        self.running_uuids = None
        self._proxy = None
        self.extra_page = None
        self._signals = []

        self.progress_window = self.builder.get_object("progress_window")
        self.progresslabel = self.builder.get_object('progresslabel')
        self.progressbar = self.builder.get_object("progressbar")
        self.progress_button_abort = self.builder.get_object("btnProgressAbort")
        self.package_details = self.builder.get_object("package_details")
        self.package_details.connect_after("switch-page", self.on_change_current_page)

        scrolledWindow = Gtk.ScrolledWindow()   
        scrolledWindow.set_shadow_type(Gtk.ShadowType.ETCHED_IN)   
        scrolledWindow.set_border_width(6)
        extensions_vbox = Gtk.VBox()

        self.search_entry = self.builder.get_object("search_entry")
        self.search_entry.set_placeholder_text(_("Search"))


        self.add_widget(extensions_vbox)
        extensions_vbox.expand = True

        self.treeview = Gtk.TreeView()
        self.treeview.set_rules_hint(True)
        self.treeview.set_has_tooltip(True)

        cr = Gtk.CellRendererToggle()
        cr.connect("toggled", self.check_toggled, self.treeview)
        self.column1 = Gtk.TreeViewColumn(_("Act."), cr)
        self.column1.set_clickable(True)
        self.column1.set_cell_data_func(cr, self.celldatafunction_checkbox)
        self.column1.connect("clicked", self.on_column_clicked)

        cr = Gtk.CellRendererPixbuf()
        self.column2 = Gtk.TreeViewColumn(_("Icon"), cr)
        self.column2.set_min_width(50)
        self.column2.set_clickable(True)
        self.column2.set_cell_data_func(cr, self.icon_cell_data_func, 4)
        self.column2.connect("clicked", self.on_column_clicked)

        cr = Gtk.CellRendererText()
        self.column3 = Gtk.TreeViewColumn(_("Name"), cr, markup=1, background=17)
        self.column3.set_expand(True)
        self.column3.set_clickable(True)
        self.column3.connect("clicked", self.on_column_clicked)

        cr.set_property('wrap-mode', Pango.WrapMode.WORD_CHAR)
        cr.set_property('wrap-width', 160)

        cr = Gtk.CellRendererText()
        cr.set_property('xalign', 1.0)
        self.column4 = Gtk.TreeViewColumn("Score", cr, markup=14, background=17)
        self.column4.set_alignment(1.0)
        self.column4.set_clickable(True)
        #self.column4.set_expand(True)
        self.column4.connect("clicked", self.on_column_clicked)

        cr = Gtk.CellRendererText()
        cr.set_property('xalign', 1.0)
        self.column5 = Gtk.TreeViewColumn(_("Installed"), cr, background=17)
        self.column5.set_alignment(1.0)
        #self.column5.set_expand(True)
        self.column5.set_clickable(True)
        self.column5.set_cell_data_func(cr, self.installed_cell_data_func)
        self.column5.connect("clicked", self.on_column_clicked)

        cr = Gtk.CellRendererText()
        cr.set_property('xalign', 1.0)
        self.column6 = Gtk.TreeViewColumn(_("Available"), cr, background=17)
        self.column6.set_alignment(1.0)
        self.column6.set_clickable(True)
        #self.column6.set_expand(True)
        self.column6.set_cell_data_func(cr, self.available_cell_data_func)
        self.column6.connect("clicked", self.on_column_clicked)

        cr = Gtk.CellRendererPixbuf()
        cr.set_property("stock-size", Gtk.IconSize.DND)
        self.actionColumn = Gtk.TreeViewColumn(_("Uninstall"), cr, icon_name=10)
        #self.actionColumn.set_expand(True)
        self.actionColumn.set_clickable(True)
        self.actionColumn.set_cell_data_func(cr, self.action_cell_data_func)
        self.actionColumn.connect("clicked", self.on_column_clicked)

        cr = Gtk.CellRendererPixbuf()
        cr.set_property("stock-size", Gtk.IconSize.DND)
        self.isActiveColumn = Gtk.TreeViewColumn(_("Status"), cr, icon_name=11)
        #self.isActiveColumn.set_expand(True)
        self.isActiveColumn.set_clickable(True)
        self.isActiveColumn.set_cell_data_func(cr, self._is_active_data_func)
        self.isActiveColumn.connect("clicked", self.on_column_clicked)

        self.treeview.append_column(self.column1)
        self.treeview.append_column(self.column2)
        self.treeview.append_column(self.column3)
        self.treeview.append_column(self.column4)
        self.treeview.append_column(self.column5)
        self.treeview.append_column(self.column6)
        self.treeview.append_column(self.actionColumn)
        self.treeview.append_column(self.isActiveColumn)

        self.treeview.set_headers_visible(True)
        if not self.extensions_is_loading and not self.extensions_is_loaded:
            if not self.model:
                #self.model = Gtk.TreeStore(str, str, int, int, str, str, int, bool, str, int, str, str, str, int, int, int, int, str, object)
                #                          uuid, desc, enabled, max-instances, icon, name, read-only, hide-config-button, ext-setting-app, edit-date, read-only icon, active icon, schema file name (for uninstall), settings type, score, markinstall, installed_date, color

                #self.modelfilter = self.model.filter_new()
                #self.modelfilter.set_visible_func(self.only_active)
                #self.treeview.set_model(self.modelfilter)
                self.load_extensions()
            else:
                self.on_load_extensions_finished()

        self.showFilter = SHOW_ALL

        self.treeview.connect('button_press_event', self.on_button_press_event)
        self.treeview.connect("query-tooltip", self.on_treeview_query_tooltip)
        self.treeview.get_selection().connect("changed", lambda x: self._selection_changed())
        self.treeview.connect('motion_notify_event', self._on_motion_notify_event)
        if self.themes:
            self.treeview.connect("row-activated", self.on_row_activated)

        self.treeview.set_search_column(5)
        x =  Gtk.Tooltip()
        x.set_text("test")
        self.treeview.set_tooltip_cell(x, None, self.actionColumn, None)
        self.treeview.set_search_entry(self.search_entry)           

        scrolledWindow.add(self.treeview)

        self.instanceButton = self.builder.get_object("xlet_add")

        self.instanceButton.set_sensitive(False)

        self.configureButton = self.builder.get_object("xlet_configure")
        self.configureButton.set_label(_("Configure"))

        self.extConfigureButton = self.builder.get_object("xlet_ext_configure")
        self.extConfigureButton.set_label(_("Configure"))

        self.back_to_list_button = self.builder.get_object("back_to_list")

        self.restoreButton = self.builder.get_object("xlet_restore")

        self.category_settings_scroll = self.builder.get_object("category_settings_scroll")
        self.category_settings_box = self.builder.get_object("category_settings_box")
        self.packages_box = self.builder.get_object("packages_box")
        #self.packages_manager_paned = self.builder.get_object("packages_manager_paned")

        self.filter_iconview = self.builder.get_object("filter_iconview")
        self.store_filter = Gtk.ListStore(str,    str,    int,    str)
        if self.collection_type == "applet":
            self.store_filter.append([_("All"), "cs-default-applications", SHOW_ALL, self.collection_type])#cs-sources
            self.store_filter.append([_("Installed"), "cs-xlet-installed", SHOW_INSTALLED, self.collection_type])
            self.store_filter.append([_("Online"), "cs-xlet-update", SHOW_ONLINE, self.collection_type])
            self.store_filter.append([_("Active"), "cs-xlet-running", SHOW_ACTIVE, self.collection_type])
            self.store_filter.append([_("Inactive"), "cs-xlet-error", SHOW_INACTIVE, self.collection_type])
            self.store_filter.append([_("Broken"), "gtk-dialog-error", SHOW_BROKEN, self.collection_type])
        elif self.collection_type == "desklet":
            self.store_filter.append([_("All"), "cs-default-applications", SHOW_ALL, self.collection_type])
            self.store_filter.append([_("Installed"), "cs-xlet-installed", SHOW_INSTALLED, self.collection_type])
            self.store_filter.append([_("Online"), "cs-xlet-update", SHOW_ONLINE, self.collection_type])
            self.store_filter.append([_("Active"), "cs-xlet-running", SHOW_ACTIVE, self.collection_type])
            self.store_filter.append([_("Inactive"), "cs-xlet-error", SHOW_INACTIVE, self.collection_type])
            self.store_filter.append([_("Broken"), "gtk-dialog-error", SHOW_BROKEN, self.collection_type])
            self.store_filter.append([_("Settings"), "cs-cat-prefs", SHOW_SETTINGS, self.collection_type])
        elif self.collection_type == "extension":
            self.store_filter.append([_("All"), "cs-default-applications", SHOW_ALL, self.collection_type])
            self.store_filter.append([_("Installed"), "cs-xlet-installed", SHOW_INSTALLED, self.collection_type])
            self.store_filter.append([_("Online"), "cs-xlet-update", SHOW_ONLINE, self.collection_type])
            self.store_filter.append([_("Active"), "cs-xlet-running", SHOW_ACTIVE, self.collection_type])
            self.store_filter.append([_("Inactive"), "cs-xlet-error", SHOW_INACTIVE, self.collection_type])
            self.store_filter.append([_("Broken"), "gtk-dialog-error", SHOW_BROKEN, self.collection_type])

        elif self.collection_type == "theme":
            self.store_filter.append([_("All"), "cs-default-applications", SHOW_ALL, self.collection_type])
            self.store_filter.append([_("Installed"), "cs-xlet-installed", SHOW_INSTALLED, self.collection_type])
            self.store_filter.append([_("Online"), "cs-xlet-update", SHOW_ONLINE, self.collection_type])
            self.store_filter.append([_("Active"), "cs-xlet-running", SHOW_ACTIVE, self.collection_type])
            self.store_filter.append([_("Inactive"), "cs-xlet-error", SHOW_INACTIVE, self.collection_type])
            self.store_filter.append([_("Settings"), "cs-cat-prefs", SHOW_SETTINGS, self.collection_type])

        extensions_vbox.pack_start(scrolledWindow, True, True, 0)

        self.configureButton.hide()
        self.configureButton.set_no_show_all(True)
        self.extConfigureButton.hide()
        self.extConfigureButton.set_no_show_all(True)

        self.install_button = self.builder.get_object("xlet_install")
        #self.install_button.set_label(_("Install or update selected items"))
        self.install_button.set_label(_("Ok"))
        self.install_button.set_tooltip_text(_("Install or update selected items"))
        self.select_updated = self.builder.get_object("xlet_update")
        self.select_updated.set_label(_("Select updated"))
        self.reload_button = self.builder.get_object("xlet_reload")

        self.reload_button.set_label(_("Update"))
        self.reload_button.set_tooltip_text(_("Refresh list"))

        self.select_updated.hide()
        self.select_updated.set_no_show_all(True)
        self.install_list = []
        self.update_list = {}
        self.current_num_updates = 0

        # if not self.spices.get_webkit_enabled(self.collection_type):
        #     getmore_label.set_sensitive(False)
        #     self.reload_button.set_sensitive(False)

        self.extra_page = self.getAdditionalPage()

        self.content_box.show_all()

        if not self.themes:
            try:
                Gio.DBusProxy.new_for_bus(Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None,
                                          "org.Cinnamon", "/org/Cinnamon", "org.Cinnamon", None, self._on_proxy_ready, None)
            except dbus.exceptions.DBusException:
                e = sys.exc_info()[1]
                print("Error %s" % str(e))
                self._proxy = None

        self.display_filters()
        self.search_entry.grab_focus()
        self.disconnect_handlers()
        self.connect_handlers()

    def on_column_clicked(self, column):
        list_col = self.treeview.get_columns()
        for col in list_col:
            col.set_sort_indicator(False)
        self.last_col_selected
        if column == self.column1:
            self.change_column_state(column, 15)
        if column == self.column2:
            self.change_column_state(column, 4)
        if column == self.column3:
            self.change_column_state(column, 5)
        if column == self.column4:
            self.change_column_state(column, 14)
        if column == self.column5:
            self.change_column_state(column, 9)
        if column == self.column6:
            self.change_column_state(column, 16)
        if column == self.actionColumn:
            self.change_column_state(column, 6)
        if column == self.isActiveColumn:
            self.change_column_state(column, 15)#11

    def change_column_state(self, column, pos):
        if self.last_col_selected:
            if column.get_sort_order() == Gtk.SortType.DESCENDING:
                self.model.set_sort_column_id(pos, Gtk.SortType.ASCENDING)
                column.set_sort_order(Gtk.SortType.ASCENDING)
            else:
                self.model.set_sort_column_id(pos, Gtk.SortType.DESCENDING)
                column.set_sort_order(Gtk.SortType.DESCENDING)
        else:
            self.model.set_sort_column_id(pos, Gtk.SortType.ASCENDING)
            column.set_sort_order(Gtk.SortType.ASCENDING)
        column.set_sort_indicator(True)
        self.last_col_selected = column

    def set_installer(self, spices_installer):
        self.spices = spices_installer
        self.spices.connect('EmitTransactionStart', self._on_trans_start)
        self.spices.connect('EmitTransactionDone', self._on_trans_done)
        self.spices.connect('EmitTarget', self._on_target_change)
        self.spices.connect('EmitPercent', self._on_percent_change)
        self.spices.connect('EmitTransactionCancellable', self._on_cancellable_change)
        self.spices.connect('EmitTransactionError', self._on_trans_error)

    def _on_trans_start(self, srv, text):
        if self.progress_window:
            GObject.idle_add(self.trans_start, text)
            time.sleep(0.1)
        else:
            print("false start trans")

    def _on_trans_done(self, srv, text):
        if self.progress_window:
            GObject.idle_add(self.trans_done, text)
            time.sleep(0.1)

    def _on_target_change(self, srv, text):
        if self.progress_window:
            GObject.idle_add(self.target_change, text)
            time.sleep(0.1)

    def _on_percent_change(self, srv, precent):
        if self.progress_window:
            GObject.idle_add(self.percent_change, precent)
            time.sleep(0.1)

    def _on_cancellable_change(self, srv, cancel):
        if self.progress_window:
            GObject.idle_add(self.cancellable_change, cancel)
            time.sleep(0.1)

    def _on_trans_error(self, srv, title, desc):
        if self.progress_window:
            GObject.idle_add(self.trans_error, title, desc)
            time.sleep(0.1)

    def trans_start(self, text):
        self.progressbar.set_fraction(0)
        self.progresslabel.set_text(text)
        self.progress_bar_pulse()
        self.progress_window.show()

    def trans_done(self, text):
        self.progressbar.set_fraction(0)
        self.progresslabel.set_text("")
        self.progress_window.hide()

    def target_change(self, text):
        self.progressbar.set_text(text)

    def percent_change(self, precent):
        if precent > 1 or precent < 0:
            self.progress_bar_pulse()
        else:
           self.progressbar.set_fraction(precent)

    def cancellable_change(self, cancel):
        self.progress_button_abort.set_sensitive(cancel)

    def trans_error(self, title, desc):
        self.spices.errorMessage(title, desc)
        print("error")

    def progress_bar_pulse(self):       
        count = 0
        self.progressbar.set_pulse_step(0.1)
        while count < 1:
            time.sleep(0.1)
            self.progressbar.pulse()
            count += 1
            while Gtk.events_pending():
                Gtk.main_iteration()

    def prepare_swapper(self, filters):
        ##Added one filter to init
        added_keys = filters.keys()
        sorted_keys = sorted(added_keys, key=cmp_to_key(locale.strcoll))
        if len(sorted_keys) > 0:
            self.set_current_module(filters[sorted_keys[0]])
            #                                 Label   Icon    Filter, cat
            self.store_filter = Gtk.ListStore(str,    str,    int,    str)
            for filter_name in sorted_keys:
                if filter_name != self.fileName:
                    self.filters[filter_name] = filters[filter_name]
                    fl = self.filters[filter_name]
                    # Don't allow item names (and their translations) to be more than 30 chars long. It looks ugly and it creates huge gaps in the icon views
                    name = unicode(fl.name,'utf-8')
                    if len(name) > 30:
                        name = "%s..." % name[:30]
                    self.store_filter.append([name, fl.icon, fl])
        self.min_label_length = 0
        self.min_pix_length = 0
        #self.validate_label_space(self.store_filter)

    def display_filters(self):
        self.min_label_length = 60
        self.min_pix_length = 100
        model = self.filter_iconview.get_model()
        if not model:
            area = self.filter_iconview.get_area()
            self.filter_iconview.set_item_width(self.min_pix_length - 50)

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
            css_data = "GtkIconView {         \
               background-color: transparent; \
            }                                 \
            GtkIconView.view.cell:selected {  \
               background-color: blue;        \
            }"
            css_provider.load_from_data(css_data.encode())#@selected_bg_color
            c = self.filter_iconview.get_style_context()
            c.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        #self.filter_iconview.connect("item-activated", self.side_view_nav)
        #self.filter_iconview.connect("button-release-event", self.categories_button_press)
        #self.filter_iconview.connect("keynav-failed", self.on_keynav_failed)
        #self.filter_iconview.show_all()

    def filter_button_press(self, widget, event):
        if event.button == 1:
            self.side_view_nav(widget, None)

    def side_view_nav(self, side_view, path):
        selected_items = side_view.get_selected_items()
        if len(selected_items) > 0:
            self.go_to_sidepage(selected_items[0])

    def go_to_sidepage(self, path):
        iterator = self.store_filter.get_iter(path)
        action = self.store_filter.get_value(iterator, 2)
        categ = self.store_filter.get_value(iterator, 3)
        self.buildModule(categ, action)

    def buildModule(self, categ, action):
       if action == SHOW_SETTINGS and self.extra_page:
           self.category_settings_scroll.show()
           childs = self.category_settings_box.get_children()
           for ch in childs:
               self.category_settings_box.remove(ch)
           if not self.extra_page.get_parent():
               self.category_settings_box.pack_start(self.extra_page, True, True, 0)
           self.category_settings_box.show_all()
           self.packages_box.hide()
       else:
           if (action == SHOW_ALL or action == SHOW_ACTIVE or action == SHOW_INACTIVE
              or action == SHOW_INSTALLED or action == SHOW_ONLINE or action == SHOW_BROKEN):
               self.showFilter = action
               self.modelfilter.refilter()
           self.category_settings_scroll.hide()
           self.packages_box.show_all()

    def set_select_filter(self, filter_select):
        if self.filter_iconview:
            iter = self.store_filter.get_iter_first()
            while iter is not None:
                filter_iter = self.store_filter.get_value(iter, 2)
                if filter_select == filter_iter:
                    path = self.store_filter.get_path(iter)
                    self.filter_iconview.select_path(path)
                    break
                iter = self.store_filter.iter_next(iter)

    def build(self):
        SidePage.build(self)
        self.reload_extention()

    def reload_extention(self): #Possible, we need to do that externally when we have different client modules?
        self.disconnect_handlers()
        self.connect_handlers()
        self._selection_changed()
        self.refresh_update_button()
        self.filter_iconview.set_model(self.store_filter)
        if self.collection_type == "applet":
            self.instanceButton.set_tooltip_text(_("Add to panel"))
        elif self.collection_type == "desklet":
            self.instanceButton.set_tooltip_text(_("Add to desktop"))
        elif self.collection_type == "extension":
            self.instanceButton.set_tooltip_text(_("Add to Cinnamon"))
        elif self.collection_type == "theme":
            self.instanceButton.set_tooltip_text(_("Apply theme"))
        else:
            self.instanceButton.set_tooltip_text(_("Add"))
        self.instanceButton.set_label(_("Add"))
        if not self.themes:
            self.restoreButton.set_tooltip_text(_("Restore to default"))
        else:
            self.restoreButton.set_tooltip_text(_("Restore default theme"))
        self.restoreButton.set_label(_("Restore"))

        if self.extra_page and not self.extra_page.get_parent():
           self.category_settings_box.pack_start(self.extra_page, True, True, 0)
        self.category_settings_scroll.hide()
        self.packages_box.show_all()
        if self.modelfilter:
            self.modelfilter.refilter()
        self.set_select_filter(0) #bug on pix

    def connect_handlers(self):
        self.instanceButton.connect("clicked", lambda x: self._add_another_instance())
        self.configureButton.connect("clicked", self._configure_extension)
        self.extConfigureButton.connect("clicked", self._external_configure_launch)
        self.restoreButton.connect("clicked", lambda x: self._restore_default_extensions())
        self.reload_button.connect("clicked", lambda x: self.load_extensions(True))
        self.install_button.connect("clicked", lambda x: self._install_extensions(self.install_list))
        self.select_updated.connect("clicked", lambda x: self.select_updated_extensions())
        self.search_entry.connect('changed', self.on_entry_refilter)
        self.filter_iconview.connect("item-activated", self.side_view_nav)
        self.filter_iconview.connect("button-release-event", self.filter_button_press)

    def disconnect_handlers(self):
        GObject.signal_handlers_destroy(self.instanceButton)
        GObject.signal_handlers_destroy(self.configureButton)
        GObject.signal_handlers_destroy(self.extConfigureButton)
        GObject.signal_handlers_destroy(self.restoreButton)
        GObject.signal_handlers_destroy(self.reload_button)
        GObject.signal_handlers_destroy(self.install_button)
        GObject.signal_handlers_destroy(self.select_updated)
        GObject.signal_handlers_destroy(self.search_entry)
        GObject.signal_handlers_destroy(self.filter_iconview)

    def refresh_running_uuids(self):
        try:
            if self._proxy:
                self.running_uuids = self._proxy.GetRunningXletUUIDs('(s)', self.collection_type)
            else:
                self.running_uuids = None
        except:
            self.running_uuids = None

    def _on_proxy_ready (self, object, result, data=None):
        self._proxy = Gio.DBusProxy.new_for_bus_finish(result)
        self._proxy.connect("g-signal", self._on_signal)
        self._enabled_extensions_changed()

    def _on_signal(self, proxy, sender_name, signal_name, params):
        for name, callback in self._signals:
            if signal_name == name:
                callback(*params)

    def connect_proxy(self, name, callback):
        self._signals.append((name, callback))

    def disconnect_proxy(self, name):
        for signal in self._signals:
            if name in signal:
                self._signals.remove(signal)
                break

    def check_third_arg(self):
        found = False
        if self.model and len(sys.argv) > 2 and not self.run_once:
            for row in self.model:
                uuid = self.model.get_value(row.iter, 0)
                if uuid == sys.argv[2]:
                    path = self.model.get_path(row.iter)
                    filtered = self.treeview.get_model().convert_child_path_to_path(path)
                    if filtered is not None:
                        self.treeview.get_selection().select_path(filtered)
                        self.treeview.scroll_to_cell(filtered, None, False, 0, 0)
                        self.run_once = True
                        if self.configureButton.get_visible() and self.configureButton.get_sensitive():
                            found = True
                            self.configureButton.clicked()
                        elif self.extConfigureButton.get_visible() and self.extConfigureButton.get_sensitive():
                            found = True
                            self.extConfigureButton.clicked()
        if not found:
            self.back_to_list_button.clicked()
            

    def icon_cell_data_func(self, column, cell, model, iter, data=None):
        checked = model.get_value(iter, 15)
        if checked == 3:
            cell.set_property("cell-background","yellow")
        elif checked == 2:
            cell.set_property("cell-background","red")
        elif checked == -2:
            cell.set_property("cell-background","green")
        else:
            cell.set_property("cell-background","white")
        wrapper = model.get_value(iter, 18)
        if not wrapper:
            img = None
            icon_filename = model.get_value(iter, 4)
            if not self.themes:
                w = ROW_SIZE + 5
                h = ROW_SIZE + 5
            else:
                w = -1
                h = 60
            if w != -1:
                w = w * self.window.get_scale_factor()
            h = h * self.window.get_scale_factor()

            if not os.path.exists(icon_filename):
                theme = Gtk.IconTheme.get_default()
                if theme.has_icon(icon_filename):
                    img = theme.load_icon(icon_filename, h, 0)
                elif theme.has_icon("cs-%ss" % (self.collection_type)):
                    img = theme.load_icon("cs-%ss" % (self.collection_type), h, 0)
            else:
                try:
                    img = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_filename, w, h)
                except:
                    theme = Gtk.IconTheme.get_default()
                    if theme.has_icon("cs-%ss" % (self.collection_type)):
                        img = theme.load_icon("cs-%ss" % (self.collection_type), h, 0)
            surface = Gdk.cairo_surface_create_from_pixbuf (img, self.window.get_scale_factor(), self.window.get_window())
            wrapper = SurfaceWrapper(surface)
            surface = model.set_value(iter, 18, wrapper)

        cell.set_property("surface", wrapper.surface)

    def installed_cell_data_func(self, column, cell, model, iter, data=None):
        date_av = model.get_value(iter, 16)
        date_int = model.get_value(iter, 9)
        installed = model.get_value(iter, 15) > 0
        if date_av > 0:
            time = datetime.datetime.fromtimestamp(date_av).strftime('%Y-%m-%d\n%H:%M:%S')
            cell.set_property("markup", time)
        elif installed and date_int > 0:
            time = datetime.datetime.fromtimestamp(date_int).strftime('%Y-%m-%d\n%H:%M:%S')
            cell.set_property("markup", time)
        else:
            cell.set_property("markup", "")

    def available_cell_data_func(self, column, cell, model, iter, data=None):
        date_int = model.get_value(iter, 9)
        if date_int > 0:
            time = datetime.datetime.fromtimestamp(date_int).strftime('%Y-%m-%d\n%H:%M:%S')
            cell.set_property("markup", '<b><span color="#0000FF">%s</span></b>' % (time))
        else:
            cell.set_property("markup", "")

    def action_cell_data_func(self, column, cell, model, iter, data=None):
        checked = model.get_value(iter, 15)
        if checked == 3:
            cell.set_property("cell-background","yellow")
        elif checked == 2:
            cell.set_property("cell-background","red")
        elif checked == -2:
            cell.set_property("cell-background","green")
        else:
            cell.set_property("cell-background","white")

    def getAdditionalPage(self):
        return None

    def on_treeview_query_tooltip(self, treeview, x, y, keyboard_mode, tooltip):
        data = treeview.get_path_at_pos(x, y)
        if data:
            path, column, x, y=data
            iter = self.modelfilter.get_iter(path)
            if column.get_property('title')== _("Uninstall") and iter != None:
                if not self.modelfilter.get_value(iter, 6):
                    tooltip.set_text(_("Cannot be uninstalled"))
                    return True
                else:
                    return False
            elif column.get_property('title') == _("Status") and iter != None:
                can_update = self.modelfilter.get_value(iter, 16) > 0
                if can_update:
                    tooltip.set_text(_("Update available"))
                    return True
                count = self.modelfilter.get_value(iter, 2)
                markup = ""
                if count == 0:
                    installed = self.modelfilter.get_value(iter, 15) > 0
                    if installed:
                        tooltip.set_text(_("Installed and up-to-date"))
                    return True
                if count > 0:
                    markup += _("In use")
                    if count > 1:
                        markup += _("\n\nInstance count: %d") % count
                    tooltip.set_markup(markup)
                    return True
                if count < 0:
                    markup += _("Problem loading - please check Looking Glass or your system's error log")
                    tooltip.set_markup(markup)
                    return True
            elif column.get_property('title') == _("Score"):
                tooltip.set_text(_("Popularity"))
                return True
            elif column.get_property('title') == _("Available"):
                tooltip.set_text(_("More info"))
                return True
        return False

    def model_sort_func(self, model, iter1, iter2, data=None):
        s1 = ((not model[iter1][6]), model[iter1][5])
        s2 = ((not model[iter2][6]), model[iter2][5])
        return (s1 > s2) - (s1 < s2)

    def on_row_activated(self, treeview, path, column): # Only used in themes
        iter = self.modelfilter.get_iter(path)
        uuid = self.modelfilter.get_value(iter, 0)
        name = self.modelfilter.get_value(iter, 5)
        self.enable_extension(uuid, name)

    def check_toggled(self, renderer, path, treeview):
        iter = self.modelfilter.get_iter(path)
        if (iter != None):
            uuid = self.modelfilter.get_value(iter, 0)
            checked = self.modelfilter.get_value(iter, 15)
            if abs(checked) > 1:
                self.check_mark(uuid, False)
            else:
                self.check_mark(uuid, True)

    def check_mark(self, uuid, shouldMark=True, shouldUpdate=True): #fixme
        if self.model:
            for row in self.model:
                if uuid == self.model.get_value(row.iter, 0):
                    mark = self.model.get_value(row.iter, 15)
                    if shouldMark:
                        if mark == 0:
                            mark = -2
                            self.model.set_value(row.iter, 17, "green")
                        elif mark == 1:
                            can_update = self.model.get_value(row.iter, 16) > 0
                            if can_update and shouldUpdate:
                                mark = 3
                                self.model.set_value(row.iter, 17, "yellow")
                            else:
                                mark = 2
                                self.model.set_value(row.iter, 17, "red")
                    else:
                        if mark == -2:
                            mark = 0
                        elif mark == 2 or mark == 3:
                            mark = 1
                        self.model.set_value(row.iter, 17, "white")
                    self.model.set_value(row.iter, 15, mark)
                    #date = self.model.get_value(row.iter, 9)

            if not shouldMark:
                newExtensions = []
                for i_uuid, is_update, is_active in self.install_list:
                    if uuid != i_uuid:
                        newExtensions += [(i_uuid, is_update, is_active)]
                self.install_list = newExtensions
            else:
                if uuid not in self.install_list:
                    is_update = self.model.get_value(row.iter, 16) < 0
                    is_active = self.model.get_value(row.iter, 2) > 0
                    self.install_list += [(uuid, is_update, is_active)]

            if len(self.install_list) > 0:
                self.install_button.set_sensitive(True)
            else:
                self.install_button.set_sensitive(False)

    def celldatafunction_checkbox(self, column, cell, model, iter, data=None): #fixme
        checked = model.get_value(iter, 15)
        cell.set_property("activatable", True)#not installed or can_update
        if abs(checked) > 1:
            cell.set_property("active", True)
            if checked == 3:
                cell.set_property("cell-background","yellow")
            elif checked == 2:
                cell.set_property("cell-background","red")
            elif checked == -2:
                cell.set_property("cell-background","green")
        else:
            cell.set_property("active", False)
            cell.set_property("cell-background","white")

    def view_details(self, uuid):
        self.spices.show_detail(self.collection_type, uuid, lambda x: self.check_mark(uuid, True))

    def on_button_press_event(self, widget, event):
        if event.button == 1:
            data = widget.get_path_at_pos(int(event.x),int(event.y))
            if data:
                path, column, x, y = data
                if column.get_property('title') == _("Available"):
                    iter = self.modelfilter.get_iter(path)
                    uuid = self.modelfilter.get_value(iter, 0)
                    self.view_details(uuid)
                    return False

        elif event.button == 3:
            data = widget.get_path_at_pos(int(event.x),int(event.y))
            res = False
            if data:
                sel=[]
                path, col, cx, cy=data
                indices = path.get_indices()
                iter = self.modelfilter.get_iter(path)

                for i in self.treeview.get_selection().get_selected_rows()[1]:
                    sel.append(i.get_indices()[0])

                if sel:
                    popup = Gtk.Menu()
                    popup.attach_to_widget(self.treeview, None)

                    uuid = self.modelfilter.get_value(iter, 0)
                    name = self.modelfilter.get_value(iter, 5)
                    checked = self.modelfilter.get_value(iter, 2)
                    mark_install = self.modelfilter.get_value(iter, 15)
                    can_update = self.modelfilter.get_value(iter, 16) > 0
                    can_modify = self.modelfilter.get_value(iter, 6)
                    marked = abs(mark_install) > 1
                    installed = mark_install > 0

                    if self.should_show_config_button(self.modelfilter, iter):
                        item = Gtk.MenuItem(_("Configure"))
                        item.connect('activate', lambda x: self._item_configure_extension())
                        item.set_sensitive(checked > 0)
                        popup.add(item)
                        popup.add(Gtk.SeparatorMenuItem())

                    if self.should_show_ext_config_button(self.modelfilter, iter):
                        item = Gtk.MenuItem(_("Configure"))
                        item.connect('activate', lambda x: self._external_configure_launch())
                        item.set_sensitive(checked > 0)
                        popup.add(item)
                        popup.add(Gtk.SeparatorMenuItem())

                    if not self.themes:
                        if checked != 0:
                            if self.collection_type == "applet":
                                item = Gtk.MenuItem(_("Remove from panel"))
                            elif self.collection_type == "desklet":
                                item = Gtk.MenuItem(_("Remove from desktop"))
                            elif self.collection_type == "extension":
                                item = Gtk.MenuItem(_("Remove from Cinnamon"))
                            else:
                                item = Gtk.MenuItem(_("Remove")) 
                            item.connect('activate', lambda x: self.disable_extension(uuid, name, checked))
                            popup.add(item)

                        max_instances = self.modelfilter.get_value(iter, 3)
                        can_instance = installed and checked != -1 and (max_instances == -1 or ((max_instances > 0) and (max_instances > checked)))

                        if can_instance:
                            if self.collection_type == "applet":
                                item = Gtk.MenuItem(_("Add to panel"))
                            elif self.collection_type == "desklet":
                                item = Gtk.MenuItem(_("Add to desktop"))
                            elif self.collection_type == "extension":
                                item = Gtk.MenuItem(_("Add to Cinnamon"))
                            elif self.collection_type == "theme":
                                item = Gtk.MenuItem(_("Apply theme"))
                            else:
                                item = Gtk.MenuItem(_("Add"))
                            item.connect('activate', lambda x: self.enable_extension(uuid, name))
                            popup.add(item)
                    elif installed and checked <= 0:
                        item = Gtk.MenuItem(_("Apply theme"))
                        item.connect('activate', lambda x: self.enable_extension(uuid, name))
                        popup.add(item)

                    if installed:
                        popup.add(Gtk.SeparatorMenuItem())

                    item_install = Gtk.MenuItem(_("Install"))
                    item_uninstall = Gtk.MenuItem(_("Uninstall"))
                    if can_modify:
                        if installed:
                            schema_filename = self.modelfilter.get_value(iter, 12)
                            item_uninstall.connect('activate', lambda x: self.uninstall_extension(uuid, name, schema_filename))
                            item_uninstall.set_sensitive(True)
                            item_install.set_sensitive(False)
                        else:
                            item_install.connect('activate', lambda x: self.install_extension(uuid, not can_update, checked > 0))
                            item_install.set_sensitive(True)
                            item_uninstall.set_sensitive(False)
                    else:
                        item_install.set_sensitive(False)
                        item_uninstall.set_sensitive(False)
                    popup.add(item_uninstall)
                    popup.add(item_install)

                    popup.add(Gtk.SeparatorMenuItem())
                    if (marked):
                        item = Gtk.MenuItem(_("Unmark"))
                        popup.add(item)
                        item.connect('activate', lambda x: self.check_mark(uuid, False))
                    elif can_modify:
                        if installed:
                            if can_update:
                                item_upgrade = Gtk.MenuItem(_("Mark for upgrade"))
                                popup.add(item_upgrade)
                                item_upgrade.connect('activate', lambda x: self.check_mark(uuid, True))
                            item = Gtk.MenuItem(_("Mark for remove"))
                        else:
                            item = Gtk.MenuItem(_("Mark for installation"))
                        popup.add(item)
                        item.connect('activate', lambda x: self.check_mark(uuid, True, False))

                    popup.add(Gtk.SeparatorMenuItem())
                    item = Gtk.MenuItem(_("More info"))
                    if can_modify:
                        item.connect('activate', lambda x: self.view_details(uuid))
                    else:
                        item.set_sensitive(False)
                    popup.add(item)

                    popup.show_all()
                    popup.popup(None, None, None, None, event.button, event.time)

                # Only allow context menu for currently selected item
                if indices[0] not in sel:
                    return False

            return True
   
    def _is_active_data_func(self, column, cell, model, iter, data=None):
        update_change = False
        uuid = model.get_value(iter, 0)
        enabled = model.get_value(iter, 2) > 0
        error = model.get_value(iter, 2) < 0
        checked = model.get_value(iter, 15)
        installed = checked > 0
        can_update = model.get_value(iter, 16) > 0
        if installed:
            if error and (not self.themes):
                icon = "cs-xlet-error"
            elif (enabled) and (not can_update):
                icon = "cs-xlet-running"
            elif can_update:
                icon = "cs-xlet-update"
                if not uuid in self.update_list: 
                    self.update_list[uuid] = True
                    update_change = True
            else:
                icon = "cs-xlet-installed"
            if (not can_update) and (uuid in self.update_list.keys()):
                del self.update_list[uuid]
        else:
            icon = ""

        if checked == 3:
            cell.set_property("cell-background","yellow")
        elif checked == 2:
            cell.set_property("cell-background","red")
        elif checked == -2:
            cell.set_property("cell-background","green")
        else:
            cell.set_property("cell-background","white")
        cell.set_property('icon-name', icon)
        if update_change:
            self.refresh_update_button()

    def version_compare(self, uuid, date):
        installed = False
        can_update = False
        is_active = False

        installed_iter = self.model.get_iter_first()
        while installed_iter != None:
            installed_uuid = self.model.get_value(installed_iter, 0)
            if uuid == installed_uuid:
                installed_mark = self.model.get_value(installed_iter, 15)
                if installed_mark > 0:
                    installed = True
                    installed_date = self.model.get_value(installed_iter, 9)
                    can_update = date > installed_date
                    is_active = self.model.get_value(installed_iter, 2) > 0
                    break
            installed_iter = self.model.iter_next(installed_iter)
        return installed, can_update, is_active

    def _on_motion_notify_event(self, widget, event):
        data = widget.get_path_at_pos(int(event.x),int(event.y))
        if data:
            path, column, x, y=data
            iter = self.modelfilter.get_iter(path)
            if column.get_property('title')== _("Available") and iter != None:
                self.treeview.get_window().set_cursor(Gdk.Cursor.new(Gdk.CursorType.HAND2))
                return
        self.treeview.get_window().set_cursor(Gdk.Cursor.new(Gdk.CursorType.ARROW))

    def only_active(self, model, iterr, data=None):
        query = self.search_entry.get_buffer().get_text().lower()
        empty = (query == "")
        extensionName = model.get_value(iterr, 5)
        if extensionName == None:
            return False

        if not (query.lower() in extensionName.lower()):
            return False

        if self.showFilter == SHOW_ALL:
            return True
        if self.showFilter == SHOW_ACTIVE:
            return (model.get_value(iterr, 2) > 0)
        if self.showFilter == SHOW_INACTIVE:
            return (model.get_value(iterr, 2) <= 0)
        if self.showFilter == SHOW_BROKEN:
            return (model.get_value(iterr, 2) < 0)
        #can_update = model.get_value(iterr, 16) > 0         #SHOW_SETTINGS = 6
        if self.showFilter == SHOW_INSTALLED:
            return (model.get_value(iterr, 15) > 0)
        if self.showFilter == SHOW_ONLINE:
            return (model.get_value(iterr, 15) <= 0)
        return False

    def on_entry_refilter(self, widget, data=None):
        self.modelfilter.refilter()

    def install_extension(self, uuid, is_update, is_active):
        install_list = []
        install_list += [(uuid, is_update, is_active)]
        self.install_extensions(install_list)
        

    def _install_extensions(self, install_list):
            dialog = Gtk.MessageDialog(transient_for = None,
                                       modal = True,
                                       message_type = Gtk.MessageType.WARNING)
            esc = cgi.escape("This action is not implemented yet")
            dialog.set_markup(esc)

            dialog.add_button(_("Close"), 2)
            dialog.set_default_response(2)

            dialog.show_all()
            response = dialog.run()
            dialog.hide()
            dialog.destory()

    def install_extensions(self, install_list):
        if len(install_list) > 0:
            self.spices.install_all(self.collection_type, install_list, self.install_finished)
    
    def install_finished(self, need_restart):
        for row in self.model:
            self.model.set_value(row.iter, 2, 0)
        self.install_button.set_sensitive(False)
        self.install_list = []
        self.load_extensions()
        if need_restart:
            self.show_info(_("Please restart Cinnamon for the changes to take effect"))

    def enable_extension(self, uuid, name):
        if not self.themes:
            if self.collection_type in ("applet", "desklet"):
                extension_id = self.settings.get_int(("next-%s-id") % (self.collection_type))
                self.settings.set_int(("next-%s-id") % (self.collection_type), (extension_id+1))
            else:
                extension_id = 0
            self.enabled_extensions.append(self.toSettingString(uuid, extension_id))

            if self._proxy:
                self.connect_proxy("XletAddedComplete", self.xlet_added_callback)

            self.settings.set_strv(("enabled-%ss") % (self.collection_type), self.enabled_extensions)
        else:
            if uuid == "STOCK":
                self.settings.set_string("name", "")
            else:
                self.settings.set_string("name", name)

    def xlet_added_callback(self, success, uuid):
        if not success:
            self.disable_extension(uuid, "", 0)

            msg = _("""
There was a problem loading the selected item, and it has been disabled.\n\n
Check your system log and the Cinnamon LookingGlass log for any issues.
Please contact the developer.""")

            dialog = Gtk.MessageDialog(transient_for = None,
                                       modal = True,
                                       message_type = Gtk.MessageType.ERROR)
            esc = cgi.escape(msg)
            dialog.set_markup(esc)

            if self.do_logs_exist():
                dialog.add_button(_("View logfile(s)"), 1)

            dialog.add_button(_("Close"), 2)
            dialog.set_default_response(2)

            dialog.connect("response", self.on_xlet_error_dialog_response)

            dialog.show_all()
            response = dialog.run()

        self.disconnect_proxy("XletAddedComplete")

        GObject.timeout_add(100, self._enabled_extensions_changed)

    def on_xlet_error_dialog_response(self, widget, id):
        if id == 1:
            self.show_logs()
        elif id == 2:
            widget.destroy()

    def disable_extension(self, uuid, name, checked=0):
        if (checked > 1):
            msg = _("There are multiple instances, do you want to remove all of them?\n\n")
            msg += self.RemoveString

            if not self.show_prompt(msg):
                return
        if not self.themes:
            newExtensions = []
            for enabled_extension in self.enabled_extensions:
                if uuid not in enabled_extension:
                    newExtensions.append(enabled_extension)
            self.enabled_extensions = newExtensions
            self.settings.set_strv(("enabled-%ss") % (self.collection_type), self.enabled_extensions)
        else:
            if self.enabled_extensions[0] == name:
                self._restore_default_extensions()

    def uninstall_extension(self, uuid, name, schema_filename):
        list_uninstall = []
        list_uninstall += [(uuid, name, schema_filename)]
        self.uninstall_extensions(list_uninstall)
        #self.spices.uninstall(self.collection_type, uuid, name, schema_filename, self.on_uninstall_finished)

    def uninstall_extensions(self, list_uninstall):
        list_remove = ""
        for item in list_uninstall:
            if list_remove == "":
                if not self.themes:
                    list_remove = item[0]
                else:
                    list_remove = item[1]
            else:
                if not self.themes:
                    list_remove += ", " + item[0]
                else:
                    list_remove += ", " + item[1]
        if not self.show_prompt(_("Are you sure you want to completely remove %s?") % (list_remove)):
            return
        self.spices.uninstall_all(self.collection_type, list_uninstall, self.on_uninstall_finished)
    
    def on_uninstall_finished(self, uuid=None):
        self.load_extensions()

    def _enabled_extensions_changed(self):
        last_selection = ''
        model, treeiter = self.treeview.get_selection().get_selected()
        self.refresh_running_uuids()

        if self.themes:
            self.enabled_extensions = [self.settings.get_string("name")]
        else:
            self.enabled_extensions = self.settings.get_strv(("enabled-%ss") % (self.collection_type))

        uuidCount = {}
        for enabled_extension in self.enabled_extensions:
            try:
                uuid = self.fromSettingString(enabled_extension)
                if uuid == "":
                    uuid = "STOCK"
                if uuid in uuidCount:
                    uuidCount[uuid] += 1
                else:
                    uuidCount[uuid] = 1
            except:
                pass
        if self.model:
            for row in self.model:
                if not self.themes:
                    uuid = self.model.get_value(row.iter, 0)
                else:
                    if self.model.get_value(row.iter, 0) == "STOCK":
                        uuid = "STOCK"
                    else:
                        uuid = self.model.get_value(row.iter, 5)
                if uuid in uuidCount:
                    if self.running_uuids is not None:
                        if uuid in self.running_uuids:
                            self.model.set_value(row.iter, 2, uuidCount[uuid])
                        else:
                            self.model.set_value(row.iter, 2, -1)
                    else:
                        self.model.set_value(row.iter, 2, uuidCount[uuid])
                else:
                    self.model.set_value(row.iter, 2, 0)
        self._selection_changed()

    def _add_another_instance(self):
        model, treeiter = self.treeview.get_selection().get_selected()
        if treeiter:
            self._add_another_instance_iter(treeiter)

    def select_updated_extensions(self):
        if len(self.update_list) > 1:
            msg = _("This operation will update the selected items.\n\nDo you want to continue?")
        else:
            msg = _("This operation will update the selected item.\n\nDo you want to continue?")
        if not self.show_prompt(msg):
            return
        for row in self.model:
            uuid = self.model.get_value(row.iter, 0)
            if uuid in self.update_list.keys():
                self.check_mark(uuid, True)
        self.install_extensions(self.install_list)

    def refresh_update_button(self):
        num = len(self.update_list)
        text = _("%d updates available!") % (num)
        if text == self.select_updated.get_label():
            return
        self.current_num_updates = num
        if num > 0:
            if num > 1:
                self.select_updated.set_label(_("%d updates available!") % (num))
            else:
                self.select_updated.set_label(_("%d update available!") % (num))
            self.select_updated.show()
        else:
            self.select_updated.hide()

    def _add_another_instance_iter(self, treeiter):
        uuid = self.modelfilter.get_value(treeiter, 0)
        name = self.modelfilter.get_value(treeiter, 5)
        self.enable_extension(uuid, name)
        
    def _selection_changed(self):
        model, treeiter = self.treeview.get_selection().get_selected()
        enabled = False

        if treeiter:
            checked = model.get_value(treeiter, 2)
            max_instances = model.get_value(treeiter, 3)
            mark_install = model.get_value(treeiter, 15)
            enabled = mark_install > 0 and (checked != -1) and (max_instances > checked)

            self.instanceButton.set_sensitive(enabled)

            self.configureButton.set_visible(self.should_show_config_button(model, treeiter))
            self.configureButton.set_sensitive(checked > 0)
            self.extConfigureButton.set_visible(self.should_show_ext_config_button(model, treeiter))
            self.extConfigureButton.set_sensitive(checked > 0)
            self.get_information_for_selected()

    def should_show_config_button(self, model, iter):
        hide_override = model.get_value(iter, 7)
        setting_type = model.get_value(iter, 13)
        return setting_type == SETTING_TYPE_INTERNAL and not hide_override

    def should_show_ext_config_button(self, model, iter):
        hide_override = model.get_value(iter, 7)
        setting_type = model.get_value(iter, 13)
        return setting_type == SETTING_TYPE_EXTERNAL and not hide_override

    def _item_configure_extension(self, widget = None):
        self.configureButton.clicked()

    def _configure_extension(self, widget = None):
        model, treeiter = self.treeview.get_selection().get_selected()
        if treeiter:
            uuid = model.get_value(treeiter, 0)
            self._configure_extension_by_uuid(uuid)

    def _configure_extension_by_uuid(self, uuid):
        settingContainer = XletSettings.XletSetting(uuid, self, self.collection_type)
        if settingContainer.isload:
            settingContainer.show()
        else:
            self.configureButton.set_sensitive(False)

    def _external_configure_launch(self, widget = None):
        model, treeiter = self.treeview.get_selection().get_selected()
        if treeiter:
            app = model.get_value(treeiter, 8)
            if app is not None:
                subprocess.Popen([app])

    def _restore_default_extensions(self):
        if not self.themes:
            if self.collection_type == "applet":
                msg = _("This will restore the default set of enabled applets. Are you sure you want to do this?")
            elif self.collection_type == "desklet":
                msg = _("This will restore the default set of enabled desklets. Are you sure you want to do this?")            
            if self.show_prompt(msg):
                os.system(('gsettings reset org.cinnamon next-%s-id') % (self.collection_type))
                os.system(('gsettings reset org.cinnamon enabled-%ss') % (self.collection_type))
        else:
            os.system("gsettings reset org.cinnamon.theme name")

    def uuid_already_in_list(self, uuid, model):
        installed_iter = model.get_iter_first()
        #if self.themes:
        #    col = 5
        #else:
        #    col = 0
        col = 0
        while installed_iter != None:
            installed_uuid = model.get_value(installed_iter, col)
            if uuid == installed_uuid:
                return installed_iter
            installed_iter = model.iter_next(installed_iter)
        return None

    def load_extensions(self, force=False):
        #self.install_button.set_sensitive(False)
        self.extensions_is_loading = True
        self.update_list = {}
        if self.model:
            self.model.clear()
        self.model_new = Gtk.TreeStore(str, str, int, int, str, str, int, bool, str, int, str, str, str, int, int, int, int, str, object)
        thread = Thread(target = self.spices.load, args=(self.collection_type, self.on_installer_load, force,))
        thread.start()

    def on_load_extensions_finished(self):
        if(self.treeview):
            self.model = self.model_new
            self.model.set_default_sort_func(self.model_sort_func)
            self.model.set_sort_column_id(-1, Gtk.SortType.ASCENDING)
            self.modelfilter = self.model.filter_new()
            self.modelfilter.set_visible_func(self.only_active)
            self.treeview.set_model(self.modelfilter)
        self.extensions_is_loading = False
        if not self.extensions_is_loaded:
            self.extensions_is_loaded = True
            self.check_third_arg()


    def on_installer_load(self, spicesData):
        #print("total spices loaded: %d" % len(spicesData))
        self.load_extensions_by_part(self.model_new)
        self.load_spice_model(spicesData, self.model_new, self.themes, self.collection_type, 
                              self.spices.get_cache_folder(self.collection_type))
        self.spicesData = spicesData
        GObject.idle_add(self.on_load_extensions_finished)

    def load_extensions_by_part(self, model):
        if not self.themes:
            self.load_extensions_in(('%s/.local/share/cinnamon/%ss') % (home, self.collection_type), model,
                                    self.themes, self.collection_type, self.enabled_extensions)
            self.load_extensions_in(('/usr/share/cinnamon/%ss') % (self.collection_type), model, self.themes,
                                    self.collection_type, self.enabled_extensions)
        else:
            self.load_extensions_in(('%s/.themes') % (home), model, self.themes, self.collection_type, self.enabled_extensions)
            self.load_extensions_in('/usr/share', model, self.themes, self.collection_type, self.enabled_extensions, True)
            self.load_extensions_in('/usr/share/themes', model, self.themes, self.collection_type, self.enabled_extensions)


    def load_extensions_in(self, directory, model, is_theme, collection_type, enabled_extensions, stock_theme = False):
        if not is_theme:  # Applet, Desklet, Extension handling
            if os.path.exists(directory) and os.path.isdir(directory):
                extensions = os.listdir(directory)
                extensions.sort()
                for extension in extensions:
                    if self.uuid_already_in_list(extension, model):
                        continue
                    try:
                        if os.path.exists("%s/%s/metadata.json" % (directory, extension)):
                            json_data=open("%s/%s/metadata.json" % (directory, extension)).read()
                            setting_type = 0
                            data = json.loads(json_data)  
                            extension_uuid = data["uuid"]
                            extension_name = data["name"]                                        
                            extension_description = data["description"]                          
                            try: extension_max_instances = int(data["max-instances"])
                            except KeyError: extension_max_instances = 1
                            except ValueError: extension_max_instances = 1

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

                            if os.path.exists("%s/%s/settings-schema.json" % (directory, extension)):
                                setting_type = SETTING_TYPE_INTERNAL

                            try: last_edited = long(data["last-edited"])
                            except KeyError: last_edited = -1
                            except ValueError: last_edited = -1
                            except Exception: last_edited = -1
                            if last_edited == -1:
                                try: last_edited = int(data["last-edited"])
                                except KeyError: last_edited = -1
                                except ValueError: last_edited = -1

                            try: schema_filename = data["schema-file"]
                            except KeyError: schema_filename = ""
                            except ValueError: schema_filename = ""

                            if ext_config_app != "" and not os.path.exists(ext_config_app):
                                ext_config_app = ""

                            if extension_max_instances < -1:
                                extension_max_instances = 1
                                
                            #if self.search_entry.get_text().upper() in (extension_name + extension_description).upper():
                            iter = model.insert_before(None, None)
                            found = 0
                            for enabled_extension in enabled_extensions:
                                if extension_uuid in enabled_extension:
                                    found += 1

                            model.set_value(iter, 0, extension_uuid)
                            #descrip ='<b>%s</b>\n<b><span foreground="#333333" size="xx-small">%s</span></b>\n \
                            #         <i><span foreground="#555555" size="x-small">%s</span></i>' % (extension_name, extension_uuid, extension_description)
                            descrip ='<b>%s</b>\n<b><span foreground="#333333" size="xx-small">%s</span></b>' % (extension_name, extension_uuid)
                            model.set_value(iter, 1, descrip)
                            model.set_value(iter, 2, found)
                            model.set_value(iter, 3, extension_max_instances)

                            icon_extension = ""
                            if "icon" in data:
                                icon_extension = data["icon"]
                            elif os.path.exists("%s/%s/icon.png" % (directory, extension)):
                                icon_extension = "%s/%s/icon.png" % (directory, extension)
                            wrapper = None #We don't want load several time the icons and we want fill the model asyncronous...
                            score = 0
                            installed = 1
                            model.set_value(iter, 4, icon_extension)

                            model.set_value(iter, 5, extension_name)
                            model.set_value(iter, 6, os.access(directory, os.W_OK))
                            model.set_value(iter, 7, hide_config_button)
                            model.set_value(iter, 8, ext_config_app)
                            model.set_value(iter, 9, last_edited)

                            if (os.access(directory, os.W_OK)):
                                icon = ""
                            else:
                                icon = "cs-xlet-system"

                            model.set_value(iter, 10, icon)

                            if (found):
                                icon = "cs-xlet-running"
                            else:
                                icon = ""
                            model.set_value(iter, 11, icon)
                            model.set_value(iter, 12, schema_filename)
                            model.set_value(iter, 13, setting_type)
                            model.set_value(iter, 14, score)
                            model.set_value(iter, 15, installed)
                            model.set_value(iter, 16, -1)
                            model.set_value(iter, 17, "white")
                            model.set_value(iter, 18, wrapper)
                    except Exception:
                        e = sys.exc_info()[1]
                        print("Failed to load extension %s: %s" % (extension, str(e)))
        else: # Theme handling
            if os.path.exists(directory) and os.path.isdir(directory):
                if stock_theme:
                    themes = ["cinnamon"]
                else:
                    themes = os.listdir(directory)
                themes.sort()
                for theme in themes:
                    try:
                        if stock_theme:
                            path = os.path.join(directory, theme, "theme")
                        else:
                            path = os.path.join(directory, theme, "cinnamon")
                        if os.path.exists(path) and os.path.isdir(path):
                            theme_last_edited = -1
                            theme_uuid = ""
                            metadata = os.path.join(path, "metadata.json")
                            if os.path.exists(metadata):
                                json_data=open(metadata).read()
                                data = json.loads(json_data)  
                                try: theme_last_edited = long(data["last-edited"])
                                except KeyError: theme_last_edited = -1
                                except ValueError: theme_last_edited = -1
                                except Exception: last_edited = -1
                                if theme_last_edited == -1:
                                    try: theme_last_edited = int(data["last-edited"])
                                    except KeyError: theme_last_edited = -1
                                    except ValueError: theme_last_edited = -1
                                try: theme_uuid = data["uuid"]
                                except KeyError: theme_uuid = ""
                                except ValueError: theme_uuid = ""
                            if theme_uuid != "" and self.uuid_already_in_list(theme_uuid, model):
                                continue
                            if stock_theme:
                                theme_name = "Cinnamon"
                                theme_uuid = "STOCK"
                            else:
                                theme_name = theme
                            theme_description = ""
                            iter = model.insert_before(None, None)
                            found = 0
                            for enabled_theme in enabled_extensions:
                                if enabled_theme == theme_name:
                                    found = 1
                                elif enabled_theme == "" and theme_uuid == "STOCK":
                                    found = 1
                            icon_extension = ""
                            if os.path.exists(os.path.join(path, "thumbnail.png")):
                                icon_extension = os.path.join(path, "thumbnail.png")
                            else:
                                icon_extension = "/usr/lib/cinnamon-settings/data/icons/themes.svg"
                            wrapper = None #We don't want load several time the icons and we want fill the model asyncronous...
                            score = 0
                            installed = 1
                            model.set_value(iter, 0, theme_uuid)
                            model.set_value(iter, 1, '<b>%s</b>' % (theme_name))
                            model.set_value(iter, 2, found)
                            model.set_value(iter, 3, 1)
                            model.set_value(iter, 4, icon_extension)
                            model.set_value(iter, 5, theme_name)
                            model.set_value(iter, 6, os.access(directory, os.W_OK))
                            model.set_value(iter, 7, True)
                            model.set_value(iter, 8, "")
                            model.set_value(iter, 9, theme_last_edited)

                            if (os.access(directory, os.W_OK)):
                                icon = ""
                            else:
                                icon = "cs-xlet-system"

                            model.set_value(iter, 10, icon)
                            if (found):
                                icon = "cs-xlet-installed"
                            else:
                                icon = ""
                            model.set_value(iter, 11, icon)
                            model.set_value(iter, 13, SETTING_TYPE_NONE)
                            model.set_value(iter, 14, score)
                            model.set_value(iter, 15, installed)
                            model.set_value(iter, 16, -1)
                            model.set_value(iter, 17, "white")
                            model.set_value(iter, 18, wrapper)
                    except Exception:
                        e = sys.exc_info()[1]
                        print("Failed to load extension %s: %s" % (theme, str(e)))

    def load_spice_model(self, spicesData, model, is_theme, collection_type, cache_folder):
        print("total spices loaded: %d" % len(spicesData))
        if not is_theme:
            for uuid in spicesData:
                extensionData = spicesData[uuid]
                extension_name = extensionData['name'].replace('&', '&amp;')
                iter_already = self.uuid_already_in_list(uuid, model)
                if iter_already:
                    try: last_edited = long(extensionData["last_edited"])
                    except KeyError: last_edited = -1
                    except ValueError: last_edited = -1
                    except Exception: last_edited = -1
                    if last_edited == -1:
                        try: last_edited = int(extensionData["last_edited"])
                        except KeyError: last_edited = -1
                        except ValueError: last_edited = -1
                    installed_date = model.get_value(iter_already, 9)
                    if last_edited > installed_date:
                        model.set_value(iter_already, 9, last_edited)
                        model.set_value(iter_already, 16, installed_date)
                    model.set_value(iter_already, 14, int(extensionData['score']))
                    continue
                extension_uuid = uuid
                try: extension_description = extensionData["comments"]
                except KeyError: extension_description = ""
                except ValueError: extension_description = ""
                #if self.search_entry.get_text().upper() in (extension_name + extension_description).upper():
                try:
                    try: extension_max_instances = int(extensionData["max-instances"])
                    except KeyError: extension_max_instances = 1
                    except ValueError: extension_max_instances = 1

                    iter = model.insert_before(None, None)
                    found = 0 #Can not be found otherwise uuid_already_in_list is wrong

                    icon_extension = os.path.join(cache_folder, os.path.basename(extensionData['icon']))
                    wrapper = None #We don't want load several time the icons and we want fill the model asyncronous...
                    os_access = 1 #Can not be found otherwise uuid_already_in_list is wrong
                    hide_config_button = True #Can not be found otherwise uuid_already_in_list is wrong
                    ext_config_app = ""
                    try: last_edited = long(extensionData["last_edited"])
                    except KeyError: last_edited = -1
                    except ValueError: last_edited = -1
                    except Exception: last_edited = -1
                    if last_edited == -1:
                        try: last_edited = int(extensionData["last_edited"])
                        except KeyError: last_edited = -1
                        except ValueError: last_edited = -1
                    setting_type = 0 #Can not be found otherwise uuid_already_in_list is wrong
                    icon_root = "" #Can not be found otherwise uuid_already_in_list is wrong
                    icon_running = "" #Can not be found otherwise uuid_already_in_list is wrong
                    try: schema_filename = extensionData["schema-file"]
                    except KeyError: schema_filename = ""
                    except ValueError: schema_filename = ""
                    #descrip = '<b>%s</b>\n<b><span foreground="#333333" size="xx-small">%s</span></b>\n \
                    #          <i><span foreground="#555555" size="x-small">%s</span></i>' % (extension_name, extension_uuid, extension_description)
                    descrip = '<b>%s</b>\n<b><span foreground="#333333" size="xx-small">%s</span></b>' % (extension_name, extension_uuid)
                    score = int(extensionData['score'])
                    installed = 0
                    model.set_value(iter, 0, extension_uuid)
                    model.set_value(iter, 1, descrip)
                    model.set_value(iter, 2, found)
                    model.set_value(iter, 3, extension_max_instances)
                    model.set_value(iter, 4, icon_extension)
                    model.set_value(iter, 5, extension_name)
                    model.set_value(iter, 6, os_access)
                    model.set_value(iter, 7, hide_config_button)
                    model.set_value(iter, 8, ext_config_app)
                    model.set_value(iter, 9, last_edited)
                    model.set_value(iter, 10, icon_root)
                    model.set_value(iter, 11, icon_running)
                    model.set_value(iter, 12, schema_filename)
                    model.set_value(iter, 13, setting_type)
                    model.set_value(iter, 14, score)
                    model.set_value(iter, 15, installed)
                    model.set_value(iter, 16, -1)
                    model.set_value(iter, 17, "white")
                    model.set_value(iter, 18, wrapper)
                except Exception:
                    e = sys.exc_info()[1]
                    print("Failed to load extension %s: %s" % (extension_name, str(e)))
        else:
            for uuid in spicesData:
                extensionData = spicesData[uuid]
                theme = extensionData['name'].replace('&', '&amp;')
                iter_already = self.uuid_already_in_list(uuid, model)
                if iter_already:
                    try: last_edited = long(extensionData["last_edited"])
                    except KeyError: last_edited = -1
                    except ValueError: last_edited = -1
                    except Exception: last_edited = -1
                    if last_edited == -1:
                        try: last_edited = int(extensionData["last_edited"])
                        except KeyError: last_edited = -1
                        except ValueError: last_edited = -1
                    installed_date = model.get_value(iter_already, 9)
                    if last_edited > installed_date:
                        model.set_value(iter_already, 9, last_edited)
                        model.set_value(iter_already, 16, installed_date)
                    model.set_value(iter_already, 14, int(extensionData['score']))
                    continue
                try:
                    theme_last_edited = -1
                    theme_uuid = uuid
                    try: theme_last_edited = long(extensionData['last_edited'])
                    except KeyError: theme_last_edited = -1
                    except ValueError: theme_last_edited = -1
                    except Exception: theme_last_edited = -1
                    if theme_last_edited == -1:
                        try: theme_last_edited = int(extensionData["last-edited"])
                        except KeyError: theme_last_edited = -1
                        except ValueError: theme_last_edited = -1
                    theme_name = theme
                    #theme_description = ""
                    iter = model.insert_before(None, None)
                    found = 0

                    icon_extension = os.path.join(cache_folder, os.path.basename(extensionData['screenshot']))
                    wrapper = None #We don't want load several time the icons and we want fill the model asyncronous...
                    os_access = 1 #Can not be found otherwise uuid_already_in_list is wrong
                    icon_root = "" #Can not be found otherwise uuid_already_in_list is wrong
                    icon_running = "" #Can not be found otherwise uuid_already_in_list is wrong
                    score = int(extensionData['score'])
                    installed = 0
                    model.set_value(iter, 0, theme_uuid)
                    model.set_value(iter, 1, '<b>%s</b>' % (theme_name))
                    model.set_value(iter, 2, found)
                    model.set_value(iter, 3, 1)
                    model.set_value(iter, 4, icon_extension)
                    model.set_value(iter, 5, theme_name)
                    model.set_value(iter, 6, os_access)
                    model.set_value(iter, 7, True)
                    model.set_value(iter, 8, "")
                    model.set_value(iter, 9, theme_last_edited)
                    model.set_value(iter, 10, icon_root)
                    model.set_value(iter, 11, icon_running)
                    model.set_value(iter, 12, None)
                    model.set_value(iter, 13, SETTING_TYPE_NONE)
                    model.set_value(iter, 14, score)
                    model.set_value(iter, 15, installed)
                    model.set_value(iter, 16, -1)
                    model.set_value(iter, 17, "white")
                    model.set_value(iter, 18, wrapper)
                except Exception:
                    e = sys.exc_info()[1]
                    print("Failed to load extension %s: %s" % (theme, str(e)))

    def show_prompt(self, msg):
        dialog = Gtk.MessageDialog(transient_for = None,
                                   destroy_with_parent = True,
                                   message_type = Gtk.MessageType.QUESTION,
                                   buttons = Gtk.ButtonsType.YES_NO)
        dialog.set_default_size(400, 200)
        esc = cgi.escape(msg)
        dialog.set_markup(esc)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.YES

    def show_info(self, msg):
        dialog = Gtk.MessageDialog(transient_for = None,
                                   modal = True,
                                   message_type = Gtk.MessageType.INFO,
                                   buttons = Gtk.ButtonsType.OK)
        esc = cgi.escape(msg)
        dialog.set_markup(esc)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()

    def get_information_for_selected(self):
        page = self.package_details.get_current_page()
        if page == 0:
            self.get_information()
        elif page == 1:
            self.get_capture()
        elif page == 2:
            self.get_authors()
        elif page == 3:
            self.get_dependencies()
        elif page == 4:
            self.get_state()

    def on_change_current_page(self, arg1, user, b):
        self.get_information_for_selected()

    def get_capture(self):
        pass

    def get_authors(self):
        pass

    def get_dependencies(self):
        pass

    def get_state(self):
        pass

    def get_information(self):
        model, treeiter = self.treeview.get_selection().get_selected()
        if treeiter:
            uuid = model.get_value(treeiter, 0)
            extension_name = model.get_value(treeiter, 5)
            comments = ""
            description = ""
            version = ""
            website = ""
            data = None
            cache_folder = self.spices.get_cache_folder(self.collection_type)
            surface = model.get_value(treeiter, 18).surface
            img_pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, surface.get_width(), surface.get_height())
            if not self.themes:
                directory = ('%s/.local/share/cinnamon/%ss/%s/metadata.json') % (home, self.collection_type, uuid)
                if not os.path.exists(directory):
                    directory = ('/usr/share/cinnamon/%ss/%s/metadata.json') % (self.collection_type, uuid)
                if os.path.exists(directory):
                    data = json.loads(open(directory).read())
                    try: version = data['version']
                    except KeyError: version = ""
                    except ValueError: version = ""
                    try: website = data['website']
                    except KeyError: website = ""
                    except ValueError: website = ""
                    try: comments = data['comments']
                    except KeyError: comments = ""
                    except ValueError: comments = ""
                    try: description = data['description']
                    except KeyError: description = ""
                    except ValueError: description = ""
            else:
                directory = ('%s/.themes/%s/metadata.json') % (home, uuid)
                if not os.path.exists(directory):
                    directory = ('/usr/share/%s/metadata.json') % (uuid)
                    if not os.path.exists(directory):
                        directory = ('/usr/share/themes/%s/metadata.json') % (uuid)
                if os.path.exists(directory):
                    data = json.loads(open(directory).read())
                    try: version = data['version']
                    except KeyError: version = ""
                    except ValueError: version = ""
                    try: website = data['website']
                    except KeyError: website = ""
                    except ValueError: website = ""
                    try: comments = data['comments']
                    except KeyError: comments = ""
                    except ValueError: comments = ""
                    try: description = data['description']
                    except KeyError: description = ""
                    except ValueError: description = ""

            if self.spicesData:
                try: extensionData = self.spicesData[uuid]
                except KeyError: extensionData = None
                except ValueError: extensionData = None
                if extensionData is not None:
                    if not self.themes:
                        if not comments:
                            try: comments = extensionData['comments']
                            except KeyError: comments = ""
                            except ValueError: comments = ""
                        if not description:
                            try: description = extensionData['description']
                            except KeyError: description = ""
                            except ValueError: description = ""
                        if not version:
                            try: version = extensionData['version']
                            except KeyError: version = ""
                            except ValueError: version = ""
                    else:
                        extensionData = self.spicesData[uuid]
                        if not comments:
                            try: comments = extensionData['comments']
                            except KeyError: comments = ""
                            except ValueError: comments = ""
                    if not description:
                        try: description = extensionData['description']
                        except KeyError: description = ""
                        except ValueError: description = ""
                        if not version:
                            try: version = extensionData['version']
                            except KeyError: version = ""
                            except ValueError: version = ""

            description = description.replace("&nbsp;", "")
            if html2text is not None:
                description = html2text.html2text(description)

            name_label = self.builder.get_object("name_label")
            desc_label = self.builder.get_object("desc_label")
            vers_label = self.builder.get_object("vers_label")
            webs_label = self.builder.get_object("webs_label")
            info_image = self.builder.get_object("info_image")
            name_label.set_text(extension_name)
            desc_label.set_text(description)
            vers_label.set_text(version)
            webs_label.set_markup("<a href=\"%s\" title=\"Visit the website\">Website</a>" % (website))
            info_image.set_from_pixbuf(img_pixbuf)
            if comments:
                desc_label.set_text(comments)
             


################################## LOG FILE OPENING SPECIFICS

# Other distros can add appropriate instructions to these two methods
# to open the correct locations

    def do_logs_exist(self):
        return os.path.exists("%s/.cinnamon/glass.log" % (home)) or \
               os.path.exists("%s/.xsession-errors" % (home))

    def show_logs(self):
        glass_path = "%s/.cinnamon/glass.log" % (home)
        if os.path.exists(glass_path):
            subprocess.Popen(["xdg-open", glass_path])

        xerror_path = "%s/.xsession-errors" % (home)
        if os.path.exists(xerror_path):
            subprocess.Popen(["xdg-open", xerror_path])

