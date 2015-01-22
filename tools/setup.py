#!/usr/bin/env python
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

try:
    import sys, py_compile, os, pwd, grp, shutil, stat, subprocess, gettext
    #from distutils.core import setup
    #from distutils import cmd
    #from distutils.command.install_data import install_data as _install_data
    #from distutils.command.build import build as _build
except Exception:
    e = sys.exc_info()[1]
    print(str(e))
    sys.exit(1)

def get_home():
    if "SUDO_USER" in os.environ:
        return os.path.expanduser("~" + os.environ["SUDO_USER"])
    elif "PKEXEC_UID" in os.environ:
        return os.path.expanduser("~" + pwd.getpwuid(int(os.environ["PKEXEC_UID"])).pw_name)
    else:
        return os.path.expanduser("~" + pwd.getpwuid(os.getuid()).pw_name)

ABS_PATH = os.path.abspath(__file__)
DIR_PATH = os.path.dirname(os.path.dirname(ABS_PATH)) + "/"

HOME_PATH = get_home()
INSTALL_PATH = "/usr/lib/cinnamon-installer/"
LOCAL_PATH = os.path.join(HOME_PATH, ".local/share/cinnamon-installer/")

LOCALE_PATH = "/usr/share/locale"
POLKIT_PATH = "/usr/share/polkit-1/actions/"
SCHEMAS_PATH = "/usr/share/glib-2.0/schemas/"
CROND_PATH = "/etc/cron.daily/"
DBUS_PATH = "/usr/share/dbus-1/services/"
SETTING_MODULE_PATH = "/usr/lib/cinnamon-settings/modules/"

try:
    import msgfmt.make
except Exception:
    def make(src, dest):
        parts = os.path.splitext(src)
        if parts[len(parts) - 1] == ".po":
            subprocess.call(["msgfmt", "-c", src, "-o", dest])

def reloadAsRoot(options):
    try:
        if is_program_in_system("pkexec"):
            os.execvp("pkexec", ["pkexec", ABS_PATH, options])
            print("reload as root")
            return True
        if is_program_in_system("gksudo"):
            message = _("The program %s is requesting elevated privileges to perform a change on your system.\nEnter the root password to allow this task.") % ("Cinnamon Installer")
            os.execvp("gksudo", ["gksudo", "--message", message, ABS_PATH + " " + options])
            print("reload as root")
            return True
    except Exception:
        e = sys.exc_info()[1]
        print("fail to load as root")
        print(str(e))
    return False

def is_program_in_system(programName):
    path = os.getenv("PATH")
    for p in path.split(os.path.pathsep):
        p = os.path.join(p, programName)
        if os.path.exists(p) and os.access(p, os.X_OK):
            return True
    return False

def copyTree(src, out):
    if not os.path.exists(out):
        os.makedirs(out)
    source = os.listdir(src)
    for filename in source:
        srcfile = os.path.join(src, filename)
        outfile = os.path.join(out, filename)
        if os.path.isfile(srcfile):
            shutil.copy(srcfile, out)
            print("copy " + srcfile + " to " + outfile)
        else:
            copyTree(srcfile, outfile)

def setPermisions(installed_path):
    tragetFile = os.path.join(installed_path, "cinnamon-installer.py")
    st = os.stat(tragetFile)
    os.chmod(tragetFile, st.st_mode | stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH | stat.S_IEXEC)
    tragetTools = os.path.join(installed_path, "tools")
    source = os.listdir(tragetTools)
    for filename in source:
        tragetFile = os.path.join(tragetTools, filename)
        st = os.stat(tragetFile)
        os.chmod(tragetFile, st.st_mode | stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH | stat.S_IEXEC)

def compilePy(folderModules, installed_path):
    traget = os.path.join(installed_path, folderModules)
    source = os.listdir(traget)
    for filename in source:
        lastPos = len(filename)
        if (filename[lastPos-3:lastPos] == ".py") and (filename[0:3] == "ci_"):
            tragetFile = os.path.join(traget, filename)
            py_compile.compile(tragetFile)

def installPolicy(installed_path):
    traget = os.path.join(installed_path, "config/policy")
    source = os.listdir(traget)
    for filename in source:
        srcFile = os.path.join(traget, filename)
        outFile = os.path.join(POLKIT_PATH, filename)
        shutil.copyfile(srcFile, outFile)

def installSchema(installed_path):
    traget = os.path.join(installed_path, "config/schemas")
    source = os.listdir(traget)
    for filename in source:
        srcFile = os.path.join(traget, filename)
        outFile = os.path.join(SCHEMAS_PATH, filename)
        shutil.copyfile(srcFile, outFile)
        os.system("glib-compile-schemas " + SCHEMAS_PATH)

def installCronD(installed_path):
    srcFile = os.path.join(installed_path, "tools/cinnamon-installer")
    outFile = os.path.join(CROND_PATH, "cinnamon-installer")
    shutil.copyfile(srcFile, outFile)
    st = os.stat(srcFile)
    os.chmod(outFile, st.st_mode | stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH | stat.S_IEXEC)

def installLocale(dest_path, installed_path):
    po_dir = os.path.join(installed_path, "po")
    for path, names, filenames in os.walk(po_dir):
        for f in filenames:
            if f.endswith(".po"):
                lang = f[:-3]
                src = os.path.join(path, f)
                locale = os.path.join(dest_path, lang, "LC_MESSAGES")
                dest = os.path.join(locale, "cinnamon-installer.mo")
                if not os.path.exists(locale):
                    os.makedirs(locale)
                if not os.path.exists(dest):
                    print("Compiling %s" % src)
                    make(src, dest)
                else:
                    src_mtime = os.stat(src)[8]
                    dest_mtime = os.stat(dest)[8]
                    if src_mtime > dest_mtime:
                        print("Compiling %s" % src)
                        make(src, dest)
    # Remove po folder.

def createIcons(dest_path, installed_path):
    srcFile = os.path.join(installed_path, "gui/img/cinnamon-installer.svg")
    outFile = os.path.join(dest_path, "cinnamon-installer.svg")
    if not os.path.exists(dest_path):
        os.makedirs(dest_path)
    shutil.copyfile(srcFile, outFile)

def generateDesktop(dest_path, installed_path, locale):
    menuName = "Cinnamon Installer"
    menuComment = "Install packages, applets, desklets, extensions and themes."
    desktopFile = open(os.path.join(dest_path, "cinnamon-installer.desktop"), "w")
    desktopFile.writelines("[Desktop Entry]\n")
    desktopFile.writelines("Name=Cinnamon Installer\n")
    gettext.install("cinnamon", "/usr/share/locale")
    for directory in os.listdir(locale):
        if os.path.isdir(os.path.join(locale, directory)):
            try:
                language = gettext.translation("cinnamon-installer", locale, languages=[directory])
                language.install()
                desktopFile.writelines("Name[%s]=%s\n" % (directory, _(menuName)))
            except:
                pass
    for directory in os.listdir(locale):
        if os.path.isdir(os.path.join(locale, directory)):
            try:
                language = gettext.translation("cinnamon-installer", locale, languages=[directory])
                language.install()
                desktopFile.writelines("Comment[%s]=%s\n" % (directory, _(menuComment)))
            except:
                pass

    desktopFile.writelines("Exec=cinnamon-installer --manager applets\n")
    desktopFile.writelines("Icon=cinnamon-installer\n")
    desktopFile.writelines("Terminal=false\n")
    desktopFile.writelines("Type=Application\n")
    desktopFile.writelines("Encoding=UTF-8\n")
    desktopFile.writelines("OnlyShowIn=X-Cinnamon;\n")
    desktopFile.writelines("Categories=GNOME;GTK;Settings;DesktopSettings;\n")
    desktopFile.writelines("StartupNotify=false\n")
    tragetFile = os.path.join(dest_path, "cinnamon-installer.desktop")
    st = os.stat(tragetFile)
    os.chmod(tragetFile, st.st_mode | stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH | stat.S_IEXEC)

def generateInitFile(dest_path, installed_path):
    if not os.path.exists(dest_path):
        os.makedirs(dest_path)
    tragetFile = os.path.join(dest_path, "cinnamon-installer")
    f = open(tragetFile, "w")
    f.write("#!/usr/bin/env python\n")
    f.write("# -*- coding:utf-8 -*-\n")
    f.write("#\n#\n")
    f.write("# Authors: Lester Carballo Pérez <lestcape@gmail.com>\n")
    f.write("#\n")
    f.write("#  This program is free software; you can redistribute it and/or\n")
    f.write("#  modify it under the terms of the GNU General Public License as\n")
    f.write("#  published by the Free Software Foundation; either version 2 of the\n")
    f.write("#  License, or (at your option) any later version.\n")
    f.write("#\n")
    f.write("#  This program is distributed in the hope that it will be useful,\n")
    f.write("#  but WITHOUT ANY WARRANTY; without even the implied warranty of\n")
    f.write("#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n")
    f.write("#  GNU General Public License for more details.\n")
    f.write("#  You should have received a copy of the GNU General Public License\n")
    f.write("#  along with this program; if not, write to the Free Software\n")
    f.write("#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307\n")
    f.write("#  USA\n\n")
    f.write("from __future__ import print_function\n\n")
    f.write("import os, sys\n\n")
    f.write("os.execvp('" + os.path.join(installed_path, "cinnamon-installer.py") + "', ('',) + tuple(sys.argv[1:]))")
    f.close()
    #os.chmod(tragetFile, 0644)
    st = os.stat(tragetFile)
    os.chmod(tragetFile, st.st_mode | stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH | stat.S_IEXEC)

def installDbusService(installed_path):
    traget = os.path.join(installed_path, "config/dbus")
    source = os.listdir(traget)
    for filename in source:
        srcFile = os.path.join(traget, filename)
        outFile = os.path.join(DBUS_PATH, filename)
        shutil.copyfile(srcFile, outFile)

def installSettingsModule(installed_path):
    if not os.path.exists(installed_path):
        install()
    dest_path = os.path.join(SETTING_MODULE_PATH, "cs_installer.py")
    shutil.copyfile(os.path.join(installed_path, "lib/cs_installer.py"), dest_path)
    st = os.stat(dest_path)
    os.chmod(dest_path, st.st_mode | stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH | stat.S_IEXEC)
    py_compile.compile(dest_path)

def removeTree(installed_path):
    if os.path.exists(installed_path):
        shutil.rmtree(installed_path)

def removeIcons(installed_path):
    dest_path = os.path.join(installed_path, "cinnamon-installer.svg")
    if os.path.isfile(dest_path):
        os.remove(dest_path)

def removeDesktop(installed_path):
    dest_path = os.path.join(installed_path, "cinnamon-installer.desktop")
    if os.path.isfile(dest_path):
        os.remove(dest_path)

def removeInitFile(installed_path):
    dest_path = os.path.join(installed_path, "cinnamon-installer")
    if os.path.isfile(dest_path):
        os.remove(dest_path)

def removeDbusService(installed_path):
    dest_path = os.path.join(DBUS_PATH, "org.cinnamon.Installer.service")
    if os.path.isfile(dest_path):
        os.remove(dest_path)

def removeLocale(installed_path):
    source = os.listdir(installed_path)
    for filename in source:
        dest_path = os.path.join(installed_path, filename, "LC_MESSAGES", "cinnamon-installer.mo")
        if os.path.isfile(dest_path):
            os.remove(dest_path)
            if not os.listdir(os.path.dirname(dest_path)):
                shutil.rmtree(os.path.dirname(os.path.dirname(dest_path)))

def removePolicy(installed_path):
    dest_path = os.path.join(POLKIT_PATH, "org.cinnamon.installer.policy")
    if os.path.isfile(dest_path):
        os.remove(dest_path)

def removeSchema(installed_path):
    dest_path = os.path.join(SCHEMAS_PATH, "org.cinnamon.installer.xml")
    if os.path.isfile(dest_path):
        os.remove(dest_path)
        os.system("glib-compile-schemas " + SCHEMAS_PATH)

def removeCronD(installed_path):
    dest_path = os.path.join(CROND_PATH, "cinnamon-installer")
    if os.path.isfile(dest_path):
        os.remove(dest_path)

def removeSettingsModule(installed_path):
    dest_path = os.path.join(SETTING_MODULE_PATH, "cs_installer.py")
    if os.path.isfile(dest_path):
        os.remove(dest_path)
    dest_path = os.path.join(SETTING_MODULE_PATH, "cs_installer.pyc")
    if os.path.isfile(dest_path):
        os.remove(dest_path)

def cleanOld():
    if os.path.isfile("/usr/sbin/cinnamon-installer"):
        shutil.rmtree("/usr/sbin/cinnamon-installer")

def removeInstaller(installed_path):
    print("remove")

def install():
    cleanOld()
    copyTree(DIR_PATH, INSTALL_PATH)
    setPermisions(INSTALL_PATH)
    installLocale(LOCALE_PATH, INSTALL_PATH)
    compilePy("settings_modules", INSTALL_PATH)
    compilePy("installer_modules", INSTALL_PATH)
    createIcons("/usr/share/pixmaps", INSTALL_PATH)
    generateInitFile("/usr/bin", INSTALL_PATH)
    generateDesktop("/usr/share/applications", INSTALL_PATH, LOCALE_PATH)
    installPolicy(INSTALL_PATH)
    installSchema(INSTALL_PATH)
    installCronD(INSTALL_PATH)
    removeInstaller(LOCAL_PATH)
    #installDbusService(INSTALL_PATH)

def uninstall():
    cleanOld()
    removeSettingsModule(INSTALL_PATH)
    removeTree(INSTALL_PATH)
    removeIcons("/usr/share/pixmaps")
    removeDesktop("/usr/share/applications")
    removeInitFile("/usr/bin")
    removeLocale(LOCALE_PATH)
    removePolicy(INSTALL_PATH)
    removeSchema(INSTALL_PATH)
    removeCronD(INSTALL_PATH)
    removeDbusService(INSTALL_PATH)

def copyLocal():
    copyTree(DIR_PATH, LOCAL_PATH)
    setPermisions(LOCAL_PATH)
    installLocale(os.path.join(HOME_PATH, ".local/share/locale"), LOCAL_PATH)
    compilePy("settings_modules", LOCAL_PATH)
    compilePy("installer_modules", LOCAL_PATH)
    createIcons(os.path.join(HOME_PATH, ".icons"), LOCAL_PATH)
    generateInitFile(os.path.join(HOME_PATH, "bin"), LOCAL_PATH)
    generateDesktop(os.path.join(HOME_PATH, ".local/share/applications"), LOCAL_PATH , os.path.join(HOME_PATH, ".local/share/locale"))

def removeLocal():
    removeTree(LOCAL_PATH)
    removeIcons(os.path.join(HOME_PATH, ".icons"))
    removeDesktop(os.path.join(HOME_PATH, ".local/share/applications"))
    removeInitFile(os.path.join(HOME_PATH, "bin"))
    removeLocale(os.path.join(HOME_PATH, ".local/share/locale"))

def printHelp():
    print("Help: -i to install")
    print("    : -u to uninstall")
    print("    : -c to copy local")
    print("    : -r to remove local")
    print("    : -m to install cinnamon setting module")
    print("    : -d to delete cinnamon setting module")

if __name__ == "__main__":
    if (len(sys.argv) > 1):
        root = ["-i", "-u", "-m", "-d"]
        if (os.geteuid() != 0) and (sys.argv[1] in root):
            reloadAsRoot(sys.argv[1])
        elif (sys.argv[1] == "-i"):
            install()
        elif (sys.argv[1] == "-u"):
            uninstall()
        elif (sys.argv[1] == "-c"):
            copyLocal()
        elif (sys.argv[1] == "-r"):
            removeLocal()
        elif (sys.argv[1] == "-m"):
            installSettingsModule(INSTALL_PATH)
        elif (sys.argv[1] == "-d"):
            removeSettingsModule(INSTALL_PATH)
        else:
            printHelp()
    else:
        printHelp()
