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

from gi.repository import GObject, Gtk, GLib, Gio
import os, time, difflib, re, gettext, locale, sys

found_terminal = True
try:
    import pty
    from gi.repository import Vte
except (ImportError, Exception):
    found_terminal = False

ABS_PATH = os.path.abspath(__file__)
DIR_PATH = os.path.dirname(os.path.dirname(ABS_PATH)) + "/"

LOCALE_PATH = DIR_PATH + "locale"
DOMAIN = "cinnamon-installer"
locale.bindtextdomain(DOMAIN , LOCALE_PATH)
locale.bind_textdomain_codeset(DOMAIN , "UTF-8")
gettext.bindtextdomain(DOMAIN, LOCALE_PATH)
gettext.bind_textdomain_codeset(DOMAIN , "UTF-8")
gettext.textdomain(DOMAIN)
_ = gettext.gettext

CI_STATUS = {
    "RESOLVING_DEPENDENCIES": "Resolving dep",
    "SETTING_UP": "Setting up",
    "LOADING_CACHE": "Loading cache",
    "AUTHENTICATING": "authenticating",
    "DOWNLOADING": "Downloading",
    "DOWNLOADING_REPO": "Downloading repo",
    "RUNNING": "Running",
    "COMMITTING": "Committing",
    "INSTALLING": "Installing",
    "REMOVING": "Removing",
    "CHECKING": "Checking",
    "FINISHED": "Finished",
    "WAITING": "Waiting",
    "WAITING_LOCK": "Waiting lock",
    "WAITING_MEDIUM": "Waiting medium",
    "WAITING_CONFIG_FILE": "Waiting config file",
    "CANCELLING": "Cancelling",
    "CLEANING_UP": "Cleaning up",
    "QUERY": "Query",
    "DETAILS": "Details",
    "UNKNOWN": "Unknown"
}

#__all__ = ("DiffView")

#(COLUMN_ID,
# COLUMN_PACKAGE) = list(range(2))

#class DummyFile(object):
#    def write(self, x): pass

class ControlWindow(object):
    def __init__(self, mainApp, transaction=None):
        self.mainApp = mainApp
        #self.debconf = True
        self._expanded_size = None
        self.terminal = None
        self._download_map = {}
        self.trans = None
        if transaction is not None:
            self.set_transaction(transaction)
        self.mainApp.builder.set_translation_domain(DOMAIN)

        self.mainApp._terminalExpander.connect("notify::expanded", self._on_expanded)
        self.mainApp._progressColumn.set_cell_data_func(self.mainApp._progressCell, self._data_progress, None)
        self.mainApp._confActionColumn.set_cell_data_func(self.mainApp._confImgCell, self._render_package_icon, None)
        self.mainApp._confActionColumn.set_cell_data_func(self.mainApp._confDesCell, self._render_package_desc, None)

        self.signals = {
                        "on_chooseButton_clicked"            : self._on_chooseButton_clicked,
                        "on_terminalTextView_allocate"       : self._on_terminalTextView_allocate, #terminalTextView Installer
                        "on_chooseToggleCell_toggled"        : self._on_chooseToggleCell_toggled,  #terminalTextView ChooseDialog
                        "on_preferencesCloseButton_clicked"  : self._on_preferencesCloseButton_clicked, #PreferencesWindow
                        "on_preferencesWindow_delete_event"  : self._on_preferencesWindow_delete_event,
                        "on_preferencesAceptButton_clicked"  : self._on_preferencesAceptButton_clicked,
                        "on_progressCloseButton_clicked"     : self._on_progressCloseButton_clicked,
                        "on_progressCancelButton_clicked"    : self._on_progressCancelButton_clicked
                       }

        self.mainApp.builder.connect_signals(self.signals)
        self.details = False#Que es esto kit
        self.transaction_done = True#Que es esto pac update after install
        self.tag_count = 0
        self.not_close_on_finished = False

    def set_transaction(self, transaction):
        self.disconnect_all_signals()
        self.trans = transaction
        self.connect_all_signals()
        if found_terminal and self.trans.have_terminal():
            self.terminal = Vte.Terminal()
            self._master, self._slave = pty.openpty()
            self._ttyname = os.ttyname(self._slave)
            self.terminal.set_size(80, 24)
            self.terminal.set_pty_object(Vte.Pty.new_foreign(self._master))
            self.mainApp._terminalBox.pack_start(self.terminal, True, True, 0)
            self.trans.set_terminal(self._ttyname)
            self.terminal.hide()
        else:
            pass #we need to destroy the terminal

    def set_not_close_on_finished(self):
        self.not_close_on_finished = True

    def restar_window(self):
        self.mainApp._terminalTextBuffer.delete(self.mainApp._terminalTextBuffer.get_start_iter(),
                                                self.mainApp._terminalTextBuffer.get_end_iter())
        self.mainApp._cancelButton.set_visible(False)
        self.mainApp._closeButton.set_visible(False)
        self.mainApp._actionImage.set_from_icon_name("cinnamon-installer-setup", Gtk.IconSize.BUTTON)
        self.mainApp._terminalExpander.set_sensitive(True)
        self.mainApp._terminalExpander.set_expanded(False)
        self.mainApp._statusLabel.set_text(_("Preparing")+"...")
        self.mainApp._roleLabel.set_text(_("Preparing")+"...")
        self.mainApp._progressBar.set_text("")
        self.mainApp._progressBar.set_fraction(0)
        if (self.terminal):
            self.mainApp._terminalTextView.hide()
        else:
            self.mainApp._terminalTextView.show()

    def _on_terminalTextView_allocate(self, *args):
        #auto-scrolling method
        adj = self.mainApp._terminalTextView.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

    def _on_chooseToggleCell_toggled(self, *args):
        # Bug line?
        self.mainApp._chooseList[line][0] = not self.mainApp._chooseList[line][0]

    def _on_preferencesCloseButton_clicked(self, *args):
        self.mainApp._preferencesWindow.hide()

    def _on_preferencesWindow_delete_event(self, *args):
        self.mainApp._preferencesWindow.hide()
        # return True is needed to not destroy the window
        return True

    def _on_preferencesAceptButton_clicked(self, *args):
        data = []
        data.append(("EnableAUR", str(self.mainApp._enableAURButton.get_active())))
        data.append(("RemoveUnrequiredDeps", str(self.mainApp._removeUnrequiredDepsButton.get_active())))
        data.append(("RefreshPeriod", str(self.mainApp._refreshPeriodSpinButton.get_value_as_int())))
        self.trans.write_config(data)
        self.mainApp._preferencesWindow.hide()

    def _on_progressCloseButton_clicked(self, *args):
        self.exiting("")

    def _on_progressCancelButton_clicked(self, *args):
        self.exiting("")

    def _on_chooseButton_clicked(self, *args):# no existe
        self.mainApp._chooseDialog.hide()
        #for row in self.mainApp._chooseList:
        #    if row[0] is True:
        #        self.trans.resolve_package_providers(row[1].split(":")[0]) # split done in case of optdep choice

    def _on_expanded(self, expander, param):
        # Make the dialog resizable if the expander is expanded
        # try to restore a previous size
        if not expander.get_expanded():
            self._expanded_size = ((self.terminal and self.terminal.get_visible()),
                                   self.mainApp._mainWindow.get_size())
            self.mainApp._mainWindow.set_resizable(False)
        elif self._expanded_size:
            self.mainApp._mainWindow.set_resizable(True)
            term_visible, (stored_width, stored_height) = self._expanded_size
            # Check if the stored size was for the download details or
            # the terminal widget
            if term_visible != (self.terminal and self.terminal.get_visible()):
                # The stored size was for the download details, so we need
                # get a new size for the terminal widget
                self._resize_to_show_details()
            else:
                self.mainApp._mainWindow.resize(stored_width, stored_height)
        else:
            self.mainApp._mainWindow.set_resizable(True)
            self._resize_to_show_details()

    def _resize_to_show_details(self):
        win_width, win_height = self.mainApp._mainWindow.get_size()
        exp_width = self.mainApp._terminalExpander.get_allocation().width
        exp_height = self.mainApp._terminalExpander.get_allocation().height
        if self.terminal and self.terminal.get_visible():
            terminal_width = self.terminal.get_char_width() * 80
            terminal_height = self.terminal.get_char_height() * 24
            self.mainApp._mainWindow.resize(terminal_width - exp_width,
                               terminal_height - exp_height )
        else:
            self.mainApp._mainWindow.resize(win_width + 100, win_height)

    def _data_progress(self, column, cell, model, iter, data):
        try:
            progress = model.get_value(iter, 1)
            if progress == -1:
                cell.props.pulse = progress
            else:
                cell.props.value = progress
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))

    def _render_package_icon(self, column, cell, model, iter, data):
        """Data func for the Gtk.CellRendererPixbuf which shows the package. Override
        this method if you want to show custom icons for a package or map it to applications.
        """
        path = model.get_path(iter)
        if path.get_depth() == 0:
            cell.props.visible = False
        else:
            cell.props.visible = True
        cell.props.icon_name = "applications-other"

    def _render_package_desc(self, column, cell, model, iter, data):
        """Data func for the Gtk.CellRendererText which shows the package. Override
        this method if you want to show more information about a package or map it to applications.
        """
        value = model.get_value(iter, 0)
        if not value:
            return
        try:
            pkg_name, pkg_version = value.split("=")[0:2]
        except ValueError:
            pkg_name = value
            pkg_version = None
        if pkg_version:
            text = "%s (%s)" % (pkg_name, pkg_version)
        else:
            text = "%s" % pkg_name
        cell.set_property("markup", text)

    def run(self):
        self.mainApp.run()

    def show(self):
        self.transaction_done = False
        self.restar_window()
        self.mainApp.show()

    def exiting(self, msg):
        self.exec_percent(100)
        self.exec_target("100%")
        self.transaction_done = True
        self.trans.cancel()
        self.mainApp._roleLabel.set_markup("<big><b>%s</b></big>" % _("Finished"))
        self.mainApp._statusLabel.set_markup(CI_STATUS["FINISHED"])
        self.mainApp._terminalExpander.set_expanded(self.not_close_on_finished)
        self.mainApp._cancelButton.set_visible(False)
        self.mainApp._closeButton.set_visible(self.not_close_on_finished)
        self.mainApp._terminalExpander.set_sensitive(self.not_close_on_finished)
        if not self.not_close_on_finished:
            self.mainApp.hide()
            self.mainApp.exit()
        self.not_close_on_finished = False
        print(msg)

    def handler_confirm_deps(self, service, conf_info):
        GObject.idle_add(self.exec_confirm_deps, conf_info)
        time.sleep(0.1) 

    def handler_choose_provider(self, service, info_prov):
        GObject.idle_add(self.exec_choose_provider, info_prov)
        time.sleep(0.1)

    def handler_config_change(self, service, data):
        GObject.idle_add(self.exec_config_change, data)
        time.sleep(0.1)

    def handler_transaction_start(self, service, message):
        GObject.idle_add(self.exec_transaction_start, message)
        time.sleep(0.05)

    def handler_transaction_done(self, service, message):
        GObject.idle_add(self.exec_transaction_done, message)
        time.sleep(0.1)

    def handler_transaction_error(self, service, title, message):
        GObject.idle_add(self.exec_transaction_error, title, message)
        time.sleep(0.1)

    def handler_status(self, service, status, translation):
        GObject.idle_add(self.exec_status, status, translation)
        time.sleep(0.05)

    def handler_role(self, service, role_translate):
        GObject.idle_add(self.exec_role, role_translate)
        time.sleep(0.05)

    def handler_icon(self, service, icon_name):
        GObject.idle_add(self.exec_icon, icon_name)
        time.sleep(0.05)

    def handler_percent(self, service, percent):
        GObject.idle_add(self.exec_percent, percent)
        time.sleep(0.05)

    def handler_target(self, service, text):
        GObject.idle_add(self.exec_target, text)
        time.sleep(0.05)

    def handler_need_details(self, service, need):
        GObject.idle_add(self.exec_need_details, need)
        time.sleep(0.1)

    def handler_updates(self, service, syncfirst, updates):
        GObject.idle_add(self.exec_updates, syncfirst, updates)
        time.sleep(0.1)

    def handler_cancellable_changed(self, service, cancellable):
        GObject.idle_add(self.exec_cancellable_changed, cancellable)
        time.sleep(0.1)

    def handler_start_childs(self, service, restar_all):
        GObject.idle_add(self.exec_start_childs, restar_all)
        time.sleep(0.1)

    def handler_percent_childs(self, service, id, img, name, percent, details):
        GObject.idle_add(self.exec_percent_childs, id, img, name, percent, details)
        time.sleep(0.1)

    def handler_terminal_attached(self, service, attached):
        GObject.idle_add(self.exec_terminal_attached, attached)
        time.sleep(0.1)

    def handler_medium_required(self, service, medium, title, drive):
        GObject.idle_add(self.exec_medium_required, medium, title, drive)
        time.sleep(0.1)

    def handler_conflict_file(self, service, old, new):
        GObject.idle_add(self.exec_conflict_file, old, new)
        time.sleep(0.1)

    def handler_log_error(self, service, msg):
        GObject.idle_add(self.exec_log_error, (msg))
        time.sleep(0.1)

    def handler_log_warning(self, service, msg):
        GObject.idle_add(self.exec_log_warning, (msg))
        time.sleep(0.1)

    def exec_confirm_deps(self, conf_info):
        if len(conf_info["dependencies"]) > 0:
            confirmation = self.mainApp.show_conf(conf_info)
        else:
            confirmation = True
        if confirmation:
            self.trans.commit()
        else:
            self.trans.cancel()
            self.exec_transaction_error(_("Transaction canceled:"), _("Transaction fail."), )
            self.exiting("")
        ''' For pac
        self.mainApp._confDialog.hide()
        self.trans.finalize()
        if not self.trans.details:
            self.trans.release()
            self.exiting("")
        '''

    def exec_transaction_start(self, message):
        self.mainApp._cancelButton.hide()
        self.mainApp._terminalExpander.set_sensitive(True)
        self.mainApp._downloadScrolled.hide()
        if self.terminal:
            self.terminal.show()
            self.mainApp._terminalTextView.hide()
        else:
            self.mainApp._terminalTextView.show()

    def exec_transaction_done(self, message):
        end_iter = self.mainApp._terminalTextBuffer.get_end_iter()
        self.mainApp._terminalTextBuffer.insert(end_iter, str(message))
        self.exiting("")

    def exec_transaction_error(self, title, message):
        self.mainApp.show_error(title, message)
        if self.terminal:
            self.terminal.show()
            self.mainApp._terminalTextView.hide()
        else:
            self.mainApp._terminalTextView.show()
        self.mainApp._terminalExpander.set_expanded(True)
        self.not_close_on_finished = True
        self.exiting("")

    def exec_status(self, status, translation):
        if translation != "":
            self.mainApp._statusLabel.set_markup(translation)
        elif status in CI_STATUS:
            self.mainApp._statusLabel.set_markup(CI_STATUS[status])
        else:
            self.mainApp._statusLabel.set_markup(CI_STATUS["UNKNOWN"])
        if status in ("DOWNLOADING", "DOWNLOADING_REPO"):
            self.mainApp._downloadScrolled.show()
            self.mainApp._terminalTextView.hide()
            if self.terminal:
                self.terminal.hide()
        elif status == "DETAILS":
            if self.terminal:
                self.terminal.show()
                self.mainApp._terminalTextView.hide()
            else:
                self.mainApp._terminalTextView.show()
            self.not_close_on_finished = True
            self.mainApp._terminalExpander.set_expanded(True)
        else:
            self.mainApp._downloadScrolled.hide()
            if self.terminal:
                self.terminal.show()
                self.mainApp._terminalTextView.hide()
            else:
                self.mainApp._terminalTextView.show()

    def exec_role(self, role_translate):
        end_iter = self.mainApp._terminalTextBuffer.get_end_iter()
        self.mainApp._terminalTextBuffer.insert(end_iter, role_translate+"\n")
        self.mainApp._roleLabel.set_markup("<big><b>%s</b></big>" % role_translate)

    def exec_icon(self, icon_name):
        if icon_name is None:
            icon_name = Gtk.STOCK_MISSING_IMAGE
        self.mainApp._actionImage.set_from_icon_name(icon_name, Gtk.IconSize.BUTTON)

    def exec_percent(self, percent):
        if percent > 100:
            self.mainApp._progressBar.set_fraction(1)
            self.mainApp._progressBar.pulse()
            if percent > 200:
                self.mainApp._progressBar.set_text("")
        else:
            self.mainApp._progressBar.set_fraction(float(percent)/100)

    def exec_target(self, text):
        self.mainApp._progressBar.set_text(text)

    def exec_need_details(self, need):
        if self.terminal:
            self.terminal.show()
            self.mainApp._terminalTextView.hide()
        else:
            self.mainApp._terminalTextView.show()
        self.mainApp._terminalExpander.set_expanded(need)
        self.not_close_on_finished = need

    def exec_updates(self, syncfirst=True, updates=None):
        #syncfirst, updates = update_data
        if self.transaction_done:
            self.exiting("")
        elif updates:
            self.mainApp._errorDialog.format_secondary_text(_("Some updates are available.\nPlease update your system first"))
            response = self.mainApp._errorDialog.run()
            if response:
                self.mainApp._errorDialog.hide()
                self.exiting("")

    def exec_cancellable_changed(self, cancellable):
        self.mainApp._cancelButton.set_visible(True)
        self.mainApp._cancelButton.set_sensitive(cancellable)

    def exec_start_childs(self, restar_all):
        self.mainApp._downloadTreeView.get_model().clear()
        self._download_map = {}

    def exec_percent_childs(self, id, img, name, percent, details):
        model = self.mainApp._downloadTreeView.get_model()
        if percent > 100:
            percent = 100
        try:
            iter = self._download_map[id]
        except KeyError:
            adj = self.mainApp._downloadTreeView.get_vadjustment()
            is_scrolled_down = (adj.get_value() + adj.get_page_size() ==
                                adj.get_upper())
            iter = model.append((img, percent, name, details, id))
            self._download_map[id] = iter
            if is_scrolled_down:
                # If the treeview was scrolled to the end, do this again
                # after appending a new item
                self.mainApp._downloadTreeView.scroll_to_cell(model.get_path(iter),
                    None, False, False, False)
        else:
            if not model.get_value(iter, 0) == img:
                model.set_value(iter, 0, img)
            model.set_value(iter, 1, percent)
            model.set_value(iter, 2, name)
            model.set_value(iter, 3, details)

    def exec_terminal_attached(self, attached):
        if attached and self.terminal:
            self.mainApp._terminalExpander.set_sensitive(True)

    def exec_medium_required(self, medium, title, drive):
        if self.mainApp.show_question(title, desc):
            self.trans.resolve_medium_required(medium)
        else:
             self.trans.cancel()

    def exec_conflict_file(self, old, new):
        self._create_file_diff(old, new)
        replace = self.mainApp.show_file_conf()
        self.trans.resolve_config_file_conflict(replace, old, new)

    def exec_log_error(self, msg):
        textbuffer = self.mainApp._terminalTextBuffer
        end_iter = self.mainApp._terminalTextBuffer.get_end_iter()
        tags = textbuffer.get_tag_table()
        name = "error"+str(self.tag_count)
        tag_default = Gtk.TextTag.new(name)
        tag_default.set_properties(background="red")
        tags.add(tag_default)
        self._insert_tagged_text(end_iter, textbuffer, msg + "\n", name)
        self.tag_count += 1
        if self.terminal:
            self.terminal.show()
            self.mainApp._terminalTextView.hide()
        else:
            self.mainApp._terminalTextView.show()
        self.mainApp._terminalExpander.set_expanded(True)
        self.not_close_on_finished = True

    def exec_log_warning(self, msg):
        textbuffer = self.mainApp._terminalTextBuffer
        end_iter = self.mainApp._terminalTextBuffer.get_end_iter()
        tags = textbuffer.get_tag_table()
        name = "warning"+str(self.tag_count)
        tag_default = Gtk.TextTag.new(name)
        tag_default.set_properties(background="yellow")
        tags.add(tag_default)
        self._insert_tagged_text(end_iter, textbuffer, msg, name)
        self.tag_count += 1

    def exec_choose_provider(self, info_prov):
        provider_selected = None
        if len(info_prov["providers"]) > 0:
            confirmation = self.mainApp.show_providers(info_prov)
            if confirmation:
                provider_selected  = set()
                for row in self.mainApp.choose_list:
                    if row[0] is True:
                        provider_selected .add(row[1].split(":")[0]) # split done in case of optdep choice
        else:
            confirmation = True
        if confirmation:
            self.trans.resolve_package_providers(provider_selected)##we need to select a provider really
            print("fixmeee no real provider")
        else:
            self.trans.release()
            self.exec_transaction_error(_("Transaction canceled:"), _("Transaction fail."), )
            self.trans.release()
            self.exiting("")

    def exec_config_change(self, data):
        pass

    def _create_file_diff(self, from_path, to_path):
        """Show the difference between two files."""
        #FIXME: Use gio
        REGEX_RANGE = "^@@ \-(?P<from_start>[0-9]+)(?:,(?P<from_context>[0-9]+))? " \
                      "\+(?P<to_start>[0-9]+)(?:,(?P<to_context>[0-9]+))? @@"
        ELLIPSIS = "[…]\n"
        self.mainApp._fileConfTextView.set_size_request(-1, 200)
        textbuffer = self.mainApp._fileConfTextView.get_buffer()
        self.mainApp._fileConfTextView.set_property("editable", False)
        self.mainApp._fileConfTextView.set_cursor_visible(False)
        tags = textbuffer.get_tag_table()
        #FIXME: How to get better colors?
        tag_default = Gtk.TextTag.new("default")
        tag_default.set_properties(font="Mono")
        tags.add(tag_default)
        tag_add = Gtk.TextTag.new("add")
        tag_add.set_properties(font="Mono",
                               background="#8ae234")
        tags.add(tag_add)
        tag_remove = Gtk.TextTag.new("remove")
        tag_remove.set_properties(font="Mono",
                                  background="#ef2929")
        tags.add(tag_remove)
        tag_num = Gtk.TextTag.new("number")
        tag_num.set_properties(font="Mono",
                               background="#eee")
        tags.add(tag_num)
        try:
            with open(from_path) as fp:
                from_lines = fp.readlines()
            with open(to_path) as fp:
                to_lines = fp.readlines()
        except IOError:
            return

        line_number = 0
        iter = textbuffer.get_start_iter()
        for line in difflib.unified_diff(from_lines, to_lines, lineterm=""):
            if line.startswith("@@"):
                match = re.match(REGEX_RANGE, line)
                if not match:
                    continue
                line_number = int(match.group("from_start"))
                if line_number > 1:
                    self._insert_tagged_text(iter, self.ELLIPSIS, "default")
            elif line.startswith("---") or line.startswith("+++"):
                continue
            elif line.startswith(" "):
                line_number += 1
                self._insert_tagged_text(iter, textbuffer, str(line_number), "number")
                self._insert_tagged_text(iter, textbuffer, line, "default")
            elif line.startswith("-"):
                line_number += 1
                self._insert_tagged_text(iter, textbuffer, str(line_number), "number")
                self._insert_tagged_text(iter, textbuffer, line, "remove")
            elif line.startswith("+"):
                spaces = " " * len(str(line_number))
                self._insert_tagged_text(iter, textbuffer, spaces, "number")
                self._insert_tagged_text(iter, textbuffer, line, "add")

    def _insert_tagged_text(self, iter, textbuffer, text, tag):
        #self.textbuffer.insert_with_tags_by_name(iter, text, tag)
        offset = iter.get_offset()
        textbuffer.insert(iter, text)
        iterOffset = textbuffer.get_iter_at_offset(offset)
        textbuffer.apply_tag_by_name(tag, iterOffset, iter)

    def connect_all_signals(self):
        if self.trans:
            self.trans.connect("EmitTransactionConfirmation", self.handler_confirm_deps)
            self.trans.connect("EmitTransactionDone", self.handler_transaction_done)
            self.trans.connect("EmitTransactionError", self.handler_transaction_error)
            self.trans.connect("EmitTransactionCancellable", self.handler_cancellable_changed)
            self.trans.connect("EmitTransactionStart", self.handler_transaction_start)
            self.trans.connect("EmitAvailableUpdates", self.handler_updates)
            self.trans.connect("EmitStatus", self.handler_status)
            self.trans.connect("EmitRole", self.handler_role)
            self.trans.connect("EmitIcon", self.handler_icon)
            self.trans.connect("EmitTarget", self.handler_target)
            self.trans.connect("EmitPercent", self.handler_percent)
            self.trans.connect("EmitDownloadChildStart", self.handler_start_childs)
            self.trans.connect("EmitDownloadPercentChild", self.handler_percent_childs)
            self.trans.connect("EmitTerminalAttached", self.handler_terminal_attached)
            self.trans.connect("EmitNeedDetails", self.handler_need_details)
            self.trans.connect("EmitLogError", self.handler_log_error)
            self.trans.connect("EmitLogWarning", self.handler_log_warning)
            self.trans.connect("EmitConflictFile", self.handler_conflict_file)
            self.trans.connect("EmitChooseProvider", self.handler_choose_provider)
            self.trans.connect("EmitReloadConfig", self.handler_config_change)
            self.trans.connect("EmitMediumRequired", self.handler_medium_required)

    def disconnect_all_signals(self):    
        if self.trans:
            self.trans.disconnect_all_signals()
    '''
    def get_updates(self):
        self.updateGtk()
        self.status_handler(None, _("Checking for updates")+"...")
        self.icon_handler(None, "cinnamon-installer-search")
        self.target_handler(None, "")
        self.percent_handler(None, 0)
        self.mainApp._cancelButton.set_visible(False)
        self.mainApp._closeButton.set_visible(False)
        self.mainApp._terminalExpander.set_sensitive(False)
        self.mainApp.show()
        self.trans.checkUpdates()

    def refresh(self, force_update = False):
        self.updateGtk()
        self.status_handler(None, _("Refreshing")+"...")
        self.icon_handler(None, "cinnamon-installer-refresh")
        self.target_handler(None, "")
        self.percent_handler(None, 0)
        self.mainApp._cancelButton.set_visible(True)
        self.mainApp._closeButton.set_visible(False)
        self.mainApp._terminalExpander.set_sensitive(True)
        self.mainApp.show()
        self.trans.Refresh(force_update)

    def sysupgrade(self, show_updates = True, downgrade = False):
        self.status_handler(None, _("Preparing")+"...")
        self.icon_handler(None, "cinnamon-installer-setup")
        self.target_handler(None, "")
        self.percent_handler(None, 0)
        self.mainApp._terminalTextBuffer.delete(self.mainApp._terminalTextBuffer.get_start_iter(), self.mainApp._terminalTextBuffer.get_end_iter())
        self.mainApp._cancelButton.set_visible(False)
        self.mainApp._closeButton.set_visible(False)
        self.mainApp._terminalExpander.set_sensitive(True)
        self.mainApp.show()
        self.mainApp._cancelButton.set_visible(True)
        time.sleep(0.1)
        self.trans.sysupgrade(show_updates, downgrade)

    def finalize(self):
        pass

        if not self.trans.finalize():
            # packages in to_build have no deps or makedeps 
            # so we build and install the first one
            # the next ones will be built by the caller
            pkg = self.trans.to_build[0]
            path = self.trans.get_build_path(pkg)
            new_pkgs = self.trans.get_new_build(path)
            # sources are identicals for splitted packages
            # (not complete) download(new_pkgs[0].source, path)
            action = _("Building {pkgname}").format(pkgname = pkg.name)+"..."
            self.mainApp._statusLabel.set_text(action)
            self.action_long_handler(None, action+"\n")
            self.mainApp._cancelButton.set_visible(True)
            self.mainApp._closeButton.set_visible(False)
            self.mainApp._terminalExpander.set_sensitive(True)
            self.mainApp._terminalExpander.set_expanded(True)
            self.trans.build_proc(path)
            time.sleep(0.1)
            poll = self.trans.build_proc.poll()
            if poll is None:
                # Build no finished : read stdout to push it to text_buffer
                # add a timeout to stop reading stdout if too long
                # so the gui won't freeze
                self.trans.build_to_finished()
            elif poll == 0:
                # Build successfully finished
                build = self.trans.build_next(path, pkg)
                if build:
                    error = self.trans.build_more(build)
                    if error == "":
                        if self.trans.to_Remove():
                            self.trans.set_transaction_sum()
                            self.mainApp._confDialog.show_all()
                            self.updateGtk()
                        else:
                            self.trans.finalize()
                    else:
                        self.mainApp._cancelButton.set_visible(False)
                        self.mainApp._closeButton.set_visible(True)
                        self.log_error(error)
                else:
                    poll == 1
                
            if poll == 1:
                # Build finish with an error
                self.mainApp._cancelButton.set_visible(False)
                self.mainApp._closeButton.set_visible(True)
                self.action_long_handler(None, _("Build process failed."))
    '''

class MainApp():
    """Graphical progress for installation/fetch/operations.
    This widget provides a progress bar, a terminal and a status bar for
    showing the progress of package manipulation tasks.
    """
    def __init__(self):
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("cinnamon-installer")
        self.builder.add_from_file(DIR_PATH + "gui/main.ui")
        self._mainWindow = self.builder.get_object("Installer")
        self._appNameLabel = self.builder.get_object("appNameLabel")
        self._cancelButton = self.builder.get_object("cancelButton")
        self._closeButton = self.builder.get_object("closeButton")
        self._terminalExpander = self.builder.get_object("terminalExpander")
        self._terminalTextView = self.builder.get_object("terminalTextView")
        self._terminalTextBuffer = self._terminalTextView.get_buffer()
        self._terminalScrolled = self.builder.get_object("terminalScrolledWindow")
        self._terminalBox = self.builder.get_object("terminalBox")
        self._downloadScrolled = self.builder.get_object("downloadScrolledWindow")
        self._downloadTreeView = self.builder.get_object("downloadTreeView")
        self._downloadListModel = self.builder.get_object("downloadListModel")
        self._progressColumn = self.builder.get_object("progressColumn")
        self._nameColumn = self.builder.get_object("nameColumn")
        self._descriptionColumn = self.builder.get_object("descriptionColumn")
        self._progressCell = self.builder.get_object("progressCell")
        self._nameCell = self.builder.get_object("nameCell")
        self._descriptionCell = self.builder.get_object("descriptionCell")

        self._progressBar = self.builder.get_object("progressBar")
        self._roleLabel = self.builder.get_object("roleLabel")
        self._statusLabel = self.builder.get_object("statusLabel")
        self._actionImage = self.builder.get_object("actionImage")
        self._confTopLabel = self.builder.get_object("confTopLabel")
        self._confBottomLabel = self.builder.get_object("confBottomLabel")

        self._infoDialog = self.builder.get_object("InfoDialog")
        self._errorDialog = self.builder.get_object("ErrorDialog")
        self._errorDetails = self.builder.get_object("errorDetails")
        self._errorExpander = self.builder.get_object("errorBoxExpander")

        self._confDialog = self.builder.get_object("ConfDialog")
        self._confTreeView = self.builder.get_object("configTreeView")
        self._confScrolledWindow = self.builder.get_object("confScrolledWindow")
        self._confActionColumn = self.builder.get_object("confActionColumn")
        self._confImgCell = self.builder.get_object("confImgCell")
        self._confDesCell = self.builder.get_object("confDesCell")

        self._fileConfDialog = self.builder.get_object("FileConfDialog")
        self._fileConfTextView = self.builder.get_object("fileConfTextView")

        self._chooseDialog = self.builder.get_object("ChooseDialog")
        #self._chooseLabelModel = self.builder.get_object("chooseLabelModel")

        self._questionDialog = self.builder.get_object("QuestionDialog")
        self._warningDialog = self.builder.get_object("WarningDialog")
        self._preferencesWindow = self.builder.get_object("PreferencesWindow")

        #self._transactionSum = self.builder.get_object("transaction_sum")

        #self._downloadList = self.builder.get_object("download_list")
        #self._column_download = self.builder.get_object("column_download")

        self._chooseList = self.builder.get_object("chooseListModel")
        self._chooseToggleCell = self.builder.get_object("chooseToggleCell")
        self._enableAURButton = self.builder.get_object("enableAURButton")
        self._removeUnrequiredDepsButton = self.builder.get_object("RemoveUnrequiredDepsButton")
        self._refreshPeriodSpinButton = self.builder.get_object("refreshPeriodSpinButton")
        #refreshPeriodLabel = self.builder.get_object("refreshPeriodLabel")
        #self._mainWindow.connect("delete-event", self.closeWindows)
        self._init_common_values()
        self.loop = GObject.MainLoop()
        self.time_id = 0

    def _init_common_values(self):
        self._statusLabel.set_max_width_chars(15)
        self._treestoreModel = None
        #self.set_title("")
        #self.mainApp._progressBar.set_size_request(350, -1)

    def show(self):
        try :
            if not self._mainWindow.get_visible():
                self._mainWindow.show()
                GObject.idle_add(self._windows_start)
                #GObject.timeout_add(1500, self._windows_start)
                #self._mainWindow.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
                #self.time_id = GObject.timeout_add(1500, self._windows_start)
                self.loop.run()
        except Exception:
            e = sys.exc_info()[1]
            print("Error: " + str(e))

    def _windows_start(self):
        #print("release")
        self.loop.quit()
        if(self.time_id > 0):
            GObject.source_remove(self.time_id)
            self.time_id = 0

    def run(self):
        self.loop.run()
        #Gtk.main() #commented spices

    def exit(self):
        self.loop.quit()
        #Gtk.main_quit()#commented spices

    def hide(self):
        model = self._downloadTreeView.get_model()
        model.clear()
        self._mainWindow.hide()

    def closeWindows(self, windows, event):
        Gtk.main_quit()

    def show_info(self, title, message):
        self._infoDialog.set_markup("<b>%s</b>" % title)
        self._infoDialog.format_secondary_markup(message)
        response = self._infoDialog.run()
        if response:
            self._infoDialog.hide()

    def show_providers(self, info_prov):
        self._chooseDialog.set_markup("<b>%s</b>" % info_prov["title"])
        self._chooseDialog.format_secondary_markup(info_prov["description"])
        list_providers = info_prov["providers"]##need to be filled.
        self._chooseList.clear()
        for name in providers:
            self._chooseList.append([False, str(name)])
        lenght = len(self.to_add)
        response = self._chooseDialog.run()
        if response:
            self._errorDialog.hide()

    def show_error(self, title, message, details=None):
        self._errorDialog.set_markup("<b>%s</b>" % title)
        self._errorDialog.format_secondary_markup(message)
        if details:
            self._errorExpander.set_visible(True)
            self._errorDetails.set_text(details)
        response = self._errorDialog.run()
        if response:
            self._errorDialog.hide()

    def show_question(self, title, message):
        self._questionDialog.set_markup("<b>%s</b>" % title)
        self._questionDialog.format_secondary_markup(message)
        response = self._questionDialog.run()
        self._questionDialog.hide()
        return (response == Gtk.ResponseType.YES)

    def show_conf(self, infoConf):
        if(self._treestoreModel is None):
            self._treestoreModel = Gtk.TreeStore(GObject.TYPE_STRING)
            self._confTreeView.set_model(self._treestoreModel)
        else:
            self._treestoreModel.clear()
        packages_list = infoConf["dependencies"]
        for msg in packages_list:
            piter = self._treestoreModel.append(None, ["<b>%s</b>" % msg])
            collect = packages_list[msg]
            for package in packages_list[msg]:
                self._treestoreModel.append(piter, [package])
        if len(self._treestoreModel) == 1:
            filtered_store = self._treestoreModel.filter_new(
                Gtk.TreePath.new_first())
            self._confTreeView.expand_all()
            self._confTreeView.set_model(filtered_store)
            self._confTreeView.set_show_expanders(False)
            if len(filtered_store) < 6:
                #self._mainWindow.set_resizable(False)
                self._confScrolledWindow.set_policy(Gtk.PolicyType.AUTOMATIC,
                                         Gtk.PolicyType.NEVER)
            else:
                self._confTreeView.set_size_request(350, 200)
        else:
            self._confTreeView.set_size_request(350, 200)
            self._confTreeView.collapse_all()
        self._confDialog.set_markup("<b>%s</b>" % infoConf["title"])
        self._confDialog.format_secondary_markup(infoConf["description"])
        res = self._confDialog.run()
        self._confDialog.hide()
        return res == Gtk.ResponseType.OK

    def show_file_conf(self):
        res = self._fileConfDialog.run()
        self._fileConfDialog.hide()
        return res == Gtk.ResponseType.OK
