Cinnamon-Installer 0.8-Beta
==================

![](https://raw.githubusercontent.com/lestcape/Cinnamon-Installer/master/Capture.png)

Last version release date(0.7): 21 May 2014

Author: [Lester Carballo Pérez](https://github.com/lestcape)

Special thanks to:
Manjaro users and developers they have given their support to make this project possible.

A GUI Packages Manager writing in python, with the ability to support all distros, where you can install Cinnamon desktop.

Install and remove:
--------------
1- Download the program from the [website](https://github.com/lestcape/Cinnamon-Installer/archive/6ea565662fba7f8a9a5ac3d5e441c0b63ae5c239.zip)
2- Unzip the program
3- Give execute permissions to the setup.py file located in the tools folder.

To install: execute on a terminal: setup.py -i
To remove: execute on a terminal: setup.py -u

The idea
--------------
The idea it's allow have an installer and uninstaller, but with the ability to support all
distros, where Cinnamon desktop can be installed. The intention it's not break the current
Cinnamon functionality, not replace, copy or move any code of Cinnamon. It's make more 
options, modify behaviors or any other thing, without create a new unsupported branch, 
damages the image of Cinnamon, or forced the user to use this tools in any way or any form.
But we want to have alternatives always.

For now the support is for:

   - Debian base distros using: [aptdaemon](https://launchpad.net/aptdaemon/) binding and aptdaemon.client example.
   - Manjaro and Arch Linux using: python alpm bindings and pamac like [example](http://git.manjaro.org/core/pamac).
   - Several ways for [install packages](http://www.freedesktop.org/software/PackageKit/pk-matrix.html) using the [PackageKit](http://www.freedesktop.org/software/PackageKit/index.html) service.

The version 0.8, come with several updates and is in progress, there are not any release. Used for tested propouse only.

Abilities
--------------
- The integration mode allow do less click to handle the spices applets, desklets, extensions, they will be accessible always without need to go back and then enter in other session to be only do the same thing... ...
- Will be used a better integration with pkexec, instead of continues used the obsolete gksudo...
- This have a multithreading way for download the metadata of applets desklet, extentions that of course is more faster on that way.
- Handle dependencies for the hard packages (system packages), for some applets or desklets that could have dependencies that can be resolved.
- Allowed you to know if an specific applet could work in the specific Cinnamon version that you have. Some applet could break down Cinnamon, because they are not update to work in your Cinnamon version, for example. Also we can have an alternative database with patched for the not working extensions in some external place. This could be kept by external users, and will can apply the patches for the not working extensions in the installation process, that will be transparent for the final users.
- Provide a service/terminal/a way/ to an external application for install some extension if they want or need to do that.
- Allow a local installation: If you have an applet, desklet... with translation, or a gsetting schema, you will requiere to do an installation. If you copy directly the applet to the corresponding folder, this will not work with translation or you could not access to the settings... there are guys without internet connections that can not perform an install from spices web site.. this guys can not use this applet or at less the applet can not be translate for him.
- Provide a cron.d or a service to call periodically and inform the user for any update of the installed applets, desklets, extentions and themes.
- Cinnamon settings have a powerfull way to build the settings for applets, desklets and extentions using only a json file, but do not exploit all potential that could have. In some contexts, we need more actions that are not available in Cinnamon Settings...
- This application come inside with another that is caller Updater to allow update the main application.


Change log
--------------

0.8-Beta
   - Construction of the system installer applet, desklet, extension and themes, thanks to Cinnamon Settings code.
   - Integrate all installer on one GUI as a plugins.
   - Reworked Cinnamon Settings to integrate online and local tab inside only one.
   - Create an spices plugin to be integrate on the core.

0.7-Beta
   - Suppor Fedora and several more distro with packagekit.

0.67-Beta
   - Suppor ArchLinux

0.65-Beta
   - Fixed some errors on the first load.
   - Show status icons on debian.

0.6-Beta
   - Improved the GUI.
   - Added support for Manjaro, and Arch Linux based distros...

0.5-Beta
   - Improve the search to allow space.
   - Fixed the bug of unistall package on ubuntu 14.04.


0.4-Beta
   - Added translation support.
   - Execution forced to python 3(Cinnamon compatibility).

0.3-Beta
   - Now can report the error to users.
   - Now can display the version.
   - Fixed problem of package no exist.

0.2-Beta
   - Removed the import of apport, now run native on Linux Mint(Cinnamon).

0.1-Beta
   - Initial Release

Anyone is wellcome to contribute...

Thanks. 
