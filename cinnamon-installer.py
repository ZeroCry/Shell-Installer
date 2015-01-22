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

import sys
try:
    reload(sys)
    sys.setdefaultencoding('utf-8')
except Exception:
    pass
    #import importlib
    #importlib.reload(sys)

import os, argparse, stat, subprocess, time

from gi.repository import Gtk, Gdk, GObject, GLib
GObject.threads_init()

ABS_PATH = os.path.abspath(__file__)
DIR_PATH = os.path.dirname(ABS_PATH) + "/"
sys.path.append(DIR_PATH + 'lib')
sys.path.append(DIR_PATH + "installer_modules")

Gtk.IconTheme.get_default().append_search_path(DIR_PATH + "gui/img")

import gettext, locale
LOCALE_PATH = DIR_PATH + 'locale'
DOMAIN = 'cinnamon-installer'
locale.bindtextdomain(DOMAIN , LOCALE_PATH)
locale.bind_textdomain_codeset(DOMAIN , 'UTF-8')
gettext.bindtextdomain(DOMAIN, LOCALE_PATH)
gettext.bind_textdomain_codeset(DOMAIN , 'UTF-8')
gettext.textdomain(DOMAIN)
_ = gettext.gettext

WEB_SITE_URL = "https://github.com/lestcape/Cinnamon-Installer"

importerError = []
try:
    import dbus, dbus.service, dbus.mainloop.glib
except ImportError:
    e = sys.exc_info()[1]

import InstallerProviders, SystemTools

class InstallerService(dbus.service.Object):
    def __init__(self, installerAction):
        self.installerAction = installerAction

    def start(self):
        self.bus_name = dbus.service.BusName('org.cinnamon.Installer', bus = dbus.SessionBus())
        dbus.service.Object.__init__(self, self.bus_name, '/org/cinnamon/Installer')
        self.loop = GObject.MainLoop()
        self.loop.run()

    @dbus.service.signal('org.cinnamon.Installer')
    def SearchResult(self, listPackages):
        # The signal is emitted when this method exits
        # You can have code here if you wish
        pass

    @dbus.service.method(dbus_interface='org.cinnamon.Installer')
    def stop(self):
        self.loop.quit()

    @dbus.service.method(dbus_interface='org.cinnamon.Installer')
    def install(self, packageName):
        self.installerAction.install(packageName)

    @dbus.service.method(dbus_interface='org.cinnamon.Installer')
    def uninstall(self, packageName):
        self.installerAction.uninstall(packageName)

    @dbus.service.method(dbus_interface='org.cinnamon.Installer')
    def uninstallProgram(self, programName):
        self.installerAction.uninstallProgram(programName)

    @dbus.service.method(dbus_interface='org.cinnamon.Installer')
    def updateSpices(self, updateType):
        self.installerAction.updateSpices(updateType)

    @dbus.service.method(dbus_interface='org.cinnamon.Installer')
    def upgradeSpices(self, spicesList):
        self.installerAction.upgradeSpices(spicesList)

    @dbus.service.method(dbus_interface='org.cinnamon.Installer')
    def installSpices(self, spicesList):
        self.installerAction.installSpices(spicesList)

    @dbus.service.method(dbus_interface='org.cinnamon.Installer')
    def uninstallSpices(self, spicesList):
        self.installerAction.uninstallSpices(spicesList)

    @dbus.service.method(dbus_interface='org.cinnamon.Installer', async_callbacks=("reply_handler", "error_handler"))
    def getPackageByName(self, packageName, reply_handler, error_handler):
        listPackages = self.installerAction.getPackageByName(packageName)
        if(len(listPackages) == 0):
            listPackages.append("empty")
        if reply_handler:
            reply_handler(listPackages)
        self.SearchResult(listPackages)
        return listPackages

    @dbus.service.method(dbus_interface='org.cinnamon.Installer')
    def runningAsRoot(self):
        return self.installerAction.runningAsRoot()


    @dbus.service.method(dbus_interface='org.cinnamon.Installer', in_signature='s', out_signature='')
    def validateImport(self, arg):
        self.installerAction.validateImport(arg)

    @dbus.service.method(dbus_interface='org.cinnamon.Installer', in_signature='', out_signature='s')
    def pingRunning(self):
        return "running"

class InstallerClient():
    def __init__(self, installerService):
        self.installerService = installerService
        if(not self.installerService):
            self.installerService = dbus.SessionBus().get_object("org.cinnamon.Installer", "/org/cinnamon/Installer")

    def install(self, packageName):
        installMethod = self.installerService.get_dbus_method("install")
        if(installMethod):
            installMethod(packageName)

    def uninstall(self, packageName):
        uninstallMethod = self.installerService.get_dbus_method("uninstall")
        if(uninstallMethod):
            uninstallMethod(packageName)

    def uninstallProgram(self, programName):
        uninstallProgramMethod = self.installerService.get_dbus_method("uninstallProgram")
        if(uninstallProgramMethod):
            uninstallProgramMethod(programName)

    def upgradeSpices(self, spicesList):
        upgradeSpicesMethod = self.installerService.get_dbus_method("upgradeSpices")
        if(upgradeSpicesMethod):
            upgradeSpicesMethod(spicesList)

    def installSpices(self, spicesList):
        installSpicesMethod = self.installerService.get_dbus_method("installSpices")
        if(installSpicesMethod):
            installSpicesMethod(spicesList)

    def uninstallSpices(self, spicesList):
        uninstallSpicesMethod = self.installerService.get_dbus_method("uninstallSpices")
        if(uninstallSpicesMethod):
            uninstallSpicesMethod(spicesList)

    def updateSpices(self, updateType):
        uninstallSpicesMethod = self.installerService.get_dbus_method("updateSpices")
        if(uninstallSpicesMethod):
            uninstallSpicesMethod(updateType)

    def getPackageByName(self, packageName):
        getPackageByNameMethod = self.installerService.get_dbus_method("getPackageByName")
        if(getPackageByNameMethod):
            return getPackageByNameMethod(packageName)
        return ["error"]

    def runningAsRoot(self):
        getRunningAsRootMethod = self.installerService.get_dbus_method("runningAsRoot")
        if(getRunningAsRootMethod):
            return getRunningAsRootMethod()
        return False

    def printPackageByName(self, packageName):
        listPackage = self.getPackageByName(packageName)
        if listPackage[0] == "error":
            return packageName
        elif listPackage[0] == "empty":
            return "run"
        for p in listPackage:
            print(p)
        return "run"

    def validateImport(self, arg):
        validateImportMethod = self.installerService.get_dbus_method("validateImport")
        if(validateImportMethod):
            validateImportMethod(arg)

    def pingRunning(self):
        pingRunningMethod = self.installerService.get_dbus_method("pingRunning")
        if(pingRunningMethod):
            return (pingRunningMethod() == "running")
        return False

class InstallerAction():
    def __init__(self):
        self.installer = InstallerProviders.get_default()
        self.importerError = self.installer.get_importer_errors()

    def install(self, pkg_names):
        if self.installer.need_root_access("package") and (os.geteuid() != 0):
            self._reloadAsRoot("--ipackage", pkgs_name)
        else:
            pkgs_list = self._create_packages_list(pkg_names)
            self.installer.execute_install("package", pkgs_list)

    def uninstall(self, pkg_names):
        if self.installer.need_root_access("package") and (os.geteuid() != 0):
            self._reloadAsRoot("--upackage", pkg_names)
        else:
            pkgs_list = self._create_packages_list(pkg_names)
            self.installer.execute_uninstall("package", pkgs_list)

    def uninstallProgram(self, program_name):
        if self.installer.need_root_access("package") and (os.geteuid() != 0):
            self._reloadAsRoot("--uprogram", program_name)
        else:
            pkg_names = self.findPackageForProgram(program_name)
            if pkg_names:
                pkgs_list = self._create_packages_list(pkg_names)
                self.installer.execute_uninstall("package", pkgs_list)
            else:
                title = _("Not found any package associated with the program '%s'.") % program_name
                message = _("If you detect any problem or you want to contribute,\n" + \
                      "please visit: <a href='%s'>Cinnamon Installer</a>.") % WEB_SITE_URL
                self.mainAppWindows.show_error(title, message)

    def installSpices(self, spice_ids):
        if self.installer.need_root_access("applet") and (os.geteuid() != 0):
            self._reloadAsRoot("--icinnamon", spice_ids)
        else:
            pkgs_list = self._create_packages_list(spice_ids)
            self.installer.execute_install("applet", pkgs_list)

    def uninstallSpices(self, spice_ids):
        if self.installer.need_root_access("applet") and (os.geteuid() != 0):
            self._reloadAsRoot("--ucinnamon", spice_ids)
        else:
            pkgs_list = self._create_packages_list(spice_ids)
            self.installer.execute_uninstall("applet", pkgs_list)

    def upgradeSpices(self, spicesList):
        self.installer.register_collection("applet")
        if self.installer.need_root_access("applet") and (os.geteuid() != 0):
            self._reloadAsRoot("--rcinnamon", spicesList)
        else:
            self.installer.execute_upgrade(spicesList)

    def updateSpices(self, updateType):
        self.installer.register_collection("applet")
        if self.installer.need_root_access("applet") and (os.geteuid() != 0):
            self._reloadAsRoot("--ucinnamon", spicesList)
        else:
            self.installer.execute_update(spicesList)

    def findPackageForProgram(self, program):
        path = GLib.find_program_in_path(program);
        if path is not None:
            print("Program " + program + " was find in path:" + path)
            self.installer.register_collection("package")
            packageName = self.installer.find_package_by_path(path);
            if packageName is not None:
                print("Program " + program + " was find in package:" + packageName)
                return packageName
        return ""

    def getPackageByName(self, packageName):
        listPackage = ["error"]
        try:
            self.installer.register_collection("package")
            listPackage = self.installer.search_uninstall(packageName)
            if(len(listPackage) == 0):
               listPackage.append("empty")
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))
        return listPackage

    def runningAsRoot(self):
        return (os.geteuid() == 0)

    def printPackageByName(self, packageName):
        listPackage = self.getPackageByName(packageName)
        if listPackage[0] == "error":
            return "error"
        elif listPackage[0] == "empty":
            return "run"
        for p in listPackage:
            print(p)
        return "run"

    def validateImport(self, arg):
        ver = "?"
        try:
            if len(self.importerError) == 0:
                if (arg == "package")or(arg == "install"):
                    ver = self._readVersionFromFile()
                    if (arg == "package") and (self.findPackageForProgram("cinnamon") != "cinnamon"):
                        print("error")
                        title = _("<i>Cinnamon Installer %s</i>, can not find any Cinnamon package on your system.") % ver
                        message = _("You are using Cinnamon desktop?")
                        self.mainAppWindows.show_error(title, message)
                        return False
                    if (arg == "install"):
                        if (True): # is installed
                            print("run")
                            title = _("Appear that <i>Cinnamon Installer %s</i> can run on your OS.") % ver
                            message = _("If you detect any problem or you want to contribute,\n" + \
                                     "please visit: <a href='%s'>Cinnamon Installer</a>.") % WEB_SITE_URL
                            self.mainAppWindows._show_info(title, message)
                            return True
                        else:
                            print("error")
                            title = _("You need to install <i>Cinnamon Installer %s</i> for the first used.") % ver
                            message = _("Appear that your Linux distribution is supported.\n" +\
                                     "If you detect any problem or you want to contribute,\n" + \
                                     "please visit: <a href='%s'>Cinnamon Installer</a>.") % WEB_SITE_URL
                            self.mainAppWindows.show_error(title, message)
                            return False
            else:
                ver = self._readVersionFromFile()
                print("error")
                title = _("Imposible to run <i>Cinnamon Installer %s</i> on your OS.") % ver
                message = _("Your Linux distribution is unsupported or are missing some packages.\n" + \
                          "If you want to contribute to fix the problem, please visit:\n" + \
                          "<a href='%s'>Cinnamon Installer</a>.\n\n") % WEB_SITE_URL

                message += _("<i><u>Error Message:</u></i>")
                for error in self.importerError:
                    message += "\n Module " + str(error[0]) + ":" + str(error[1])
 
                self.mainAppWindows.show_error(title, message)
                return False
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))
            title = _("Some unexpected problem has occurred on <i>Cinnamon Installer %s</i>.") % ver
            message = _("Appear that your Linux distribution is unsupported.\n" +\
                      "If you want to contribute to fix the problem,\n" + \
                      "please visit: <a href='%s'>Cinnamon Installer</a>.\n\n") % WEB_SITE_URL

            self.mainAppWindows.show_error(title, message)
        return True

    def _reloadAsRoot(self, option, value):
        try:
            #pathRealod = "/usr/sbin/cinnamon-installer"
            pathCallBack = os.path.join(DIR_PATH, "cinnamon-installer.py")
            if self._is_program_in_system("pkexec"):
                subprocess.call(["sh", "-c", "pkexec env DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY " + pathCallBack + " " + option + " " + value])
                print("reload as root")
                return True
            elif self._is_program_in_system("gksudo"):
                message = _("The program %s is requesting elevated privileges to perform a change on your system.") % ("Cinnamon Installer")
                message = message + "\n" +_("Enter the root password to allow this task.") 
                subprocess.call(["gksudo", "--message", message, pathCallBack + " " + option + " " + value])
                print("reload as root")
                return True
        except Exception:
            e = sys.exc_info()[1]
            print("fail to load as root")
            print(str(e))
        return False

    def _create_packages_list(self, pkg_names):
        unfilter_pkg_list = pkg_names.split(",")
        pkg_list = []
        for pkg in unfilter_pkg_list:
            if ((pkg != "") and (pkg not in pkg_list)):
                pkg_list.append(pkg)
        return pkg_list

    def _is_program_in_system(self, programName):
        path = os.getenv('PATH')
        for p in path.split(os.path.pathsep):
            p = os.path.join(p, programName)
            if os.path.exists(p) and os.access(p, os.X_OK):
                return True
        return False

    def _configure(self):
        st = os.stat(DIR_PATH + "tools/configure.py")
        os.chmod(DIR_PATH + "tools/configure.py", st.st_mode | stat.S_IEXEC)
        if ((not os.path.isfile("/usr/share/polkit-1/actions/org.cinnamon.installer.policy")) or
            (not os.path.isfile("/usr/share/glib-2.0/schemas/org.cinnamon.installer.xml")) or
            (not os.path.isfile("/usr/sbin/cinnamon-installer"))):
            process = subprocess.Popen("pkexec '"+ DIR_PATH + "tools/configure.py'", shell=True, stdout=subprocess.PIPE)
            process.wait()
            time.sleep(1.2)
            return (process.returncode == 0)
        return True

    def _readVersionFromFile(self):
        try:
            path = DIR_PATH + "ver"
            if os.path.isfile(path):
                infile = open(path, 'r')
                result = infile.readline().rstrip('\r\n')
                float(result) #Test info
                return result
        except Exception:
            pass
        return "0.0"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=_("Process the installer options."))
    group_action = parser.add_mutually_exclusive_group(required=True)
    group_action.add_argument('--service', nargs='?', action='store', type=str, help=_("start/stop Service"))
    group_action.add_argument('--ipackage', nargs='?', action='store', type=str, help=_("Install package by name"))
    group_action.add_argument('--upackage', nargs='?', action='store', type=str, help=_("Uninstall package by name"))
    group_action.add_argument('--uprogram', nargs='?', action='store', type=str, help=_("Uninstall program by name"))
    group_action.add_argument('--qpackage', nargs='?', action='store', type=str, help=_("Query package by name"))
    group_action.add_argument('--qtest', nargs='?', action='store', type=str, help=_("Query for (imports/cinnamon/install)"))
    group_action.add_argument('--ucinnamon', nargs='?', action='store', type=str, help=_("Upgrade cinnamon components"))
    group_action.add_argument('--icinnamon', nargs='?', action='store', type=str, help=_("Install cinnamon components"))
    group_action.add_argument('--rcinnamon', nargs='?', action='store', type=str, help=_("Remove cinnamon components"))
    group_action.add_argument('--ccinnamon', nargs='?', action='store', type=str, help=_("Update cinnamon cache"))
    group_action.add_argument('--manager', nargs='?', action='store', type=str, help=_("Open the installer manager"))
    args = parser.parse_args()
    #cinnamon need to be called --action "colltype [list of type , separator]"
    try:
        # from under sudo
        if(args.service):
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            if(args.service == "start"):
                if dbus.SessionBus().request_name("org.cinnamon.Installer") == dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER:
                    action = InstallerAction()
                    service = InstallerService(action)
                    service.start()
                    print("start service")
            elif(args.service == "stop"):
                if dbus.SessionBus().request_name("org.cinnamon.Installer") != dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER:
                    installerService = dbus.SessionBus().get_object("org.cinnamon.Installer", "/org/cinnamon/Installer")
                    stopMethod = installerService.get_dbus_method("stop")
                    if(stopMethod):
                        stopMethod()
                    print("stop service")
        elif(args.manager): #We need check if installer settings module exist and then call cinnamon-settings instead of the manager
            if os.path.exists("/usr/lib/cinnamon-settings/modules/cs_installer.py"):
                os.execvp("cinnamon-settings", ("", "installer", args.manager))
            else:
                os.execvp(os.path.join(DIR_PATH, "tools/manager.py"), ('', args.manager))
        else:
            client = None;
            try:
                installerService = dbus.SessionBus().get_object("org.cinnamon.Installer", "/org/cinnamon/Installer");
                client = InstallerClient(installerService)
            except Exception:
                e = sys.exc_info()[1]
            if not client:
                client = InstallerAction()

            if(args.qtest):
                client.validateImport(args.qtest)
            elif(args.ipackage):
                client.install(args.ipackage)
            elif(args.upackage):
                client.uninstall(args.upackage)
            elif(args.uprogram):
                client.uninstallProgram(args.uprogram)
            elif(args.qpackage):
                client.printPackageByName(args.qpackage)
            elif(args.ucinnamon):
                client.upgradeSpices(args.ucinnamon)
            elif(args.icinnamon):
                client.installSpices(args.icinnamon)
            elif(args.rcinnamon):
                client.uninstallSpices(args.rcinnamon)
            elif(args.ccinnamon):
                client.updateSpices(args.ccinnamon)
    except Exception:
        e = sys.exc_info()[1]
        print(str(e))
        pass
