FennecPT, the Fennec Profile Tool
====================================

FennecPT manages profiles for Android and other mobile devices running the
Mozilla SUTAgent.  There is no easy way to use more than one profile in
Fennec, so FennecPT keeps profiles on a local machine and transfers them
back and forth to the mobile device as required.

FennecPT is available, for now, at http://people.mozilla.com/~mcote/fennecpt/


Installation
------------

FennecPT is written in Python and uses the wxPython libraries for GUI aspects.

NOTE: This is currently just a prototype.  There is no pretty installer yet,
though there certainly will be in the future.  For now, you can get the raw
Python files (Python 2.6+ and wxPython 2.8+ required), which should work
on any modern Linux or OS X system, or get the MS Windows archive, which
contains an executable and all necessary Python libraries (packaged by
py2exe).

Linux instructions:
  Nothing special, just run "./fennecpt.py".
  
Mac OS X instructions:
  Owing to some weirdness vis-a-vis 64-bit Python and the wxPython libraries,
  run the shell script "./fennecpt.mac.sh", which forces the use of 32-bit
  Python.
 
Windows instructions:
  The Windows package was created with py2exe, which packages up all the
  necessary Python libraries.  However, if you don't have Visual Studio 2008
  installed, you'll need to get the Visual C++ 2008 Redistributable Package.
  You can Google for it or find a copy at
  http://people.mozilla.com/~mcote/fennecpt/vcredist_x86.exe.  After
  installing, unzip the fennecpt archive somewhere and run fennecpt.exe.

 
Usage
-----

When FennecPT starts, it will prompt the user for a hostname/IP address,
port, and device type.  If you enter something into the "Save as" text
box, the device information will be saved and available in the future
in the menu on the left.

After connecting, FennecPT will check the device for the current Fennec
profile.  If none exists, it will launch Fennec for a few seconds in
order to create one.  FennecPT will retrieve the current profile if
no local copy exists with the same name (see below about naming
profiles).  If the current profile has no name, meaning that the device
has not been previously accessed by FennecPT, the default name
"<host/IP>_default_as_of_<current date>" will be used. 

The main window lists all the Fennec profiles previously saved to the
local machine by FennecPT.  You can launch Fennec on the remote device
using any profile.  Since Fennec can really only have one profile at a
time, when you launch Fennec you will have to decide what to do with
the currently installed profile.  You can choose to

- overwrite the local copy.  This will replace the local profile copy
  with the copy as it currently exists on the remote device.
 
- save the profile under a new name.  This will retrieve the current
  profile and save it under the given name.

- not copy it locally at all.  The current profile on the remote device
  will be lost.

FennecPT will then upload the chosen profile and launch Fennec.

Example:

Start FennecPT for the first time and connect to a device that has a
fresh Fennec install.  FennecPT will launch Fennec, creating a new
profile, and then will kill Fennec.  The default profile will be
retrieved and named, for example, 192.168.1.1_default_as_of_2010-11-24.

Choose the default profile and click "Launch Fennec".  Choose "Don't
copy it locally" because the local copy should be exactly the same,
since it was just retrieved.

Fennec should be started.  Go to any random website and bookmark it.

Now go back to FennecPT.  Choose the default profile again and click
"Launch Fennec".  A warning will be presented that Fennec is currently
running; just click "Ok".  When the "Profile exists" dialog appears,
this time, since we made a change to the profile, choose "Copy the
profile locally under a new name".  Enter "new bookmark".  The profile
will be downloaded and the old default profile uploaded, then Fennec
will be launched.

Notice that the bookmark we added previously is not in the list.

Now back to FennecPT.  As before, the default profile will be marked
"(installed)".  Choose the new profile, "new bookmark", and click
"Launch Fennec".  Again, we can choose "Don't copy it locally" since
we made no changes to the current profile.  After Fennec is launched,
notice that the site we bookmarked is in the list this time.

You can try adding more bookmarks and launching the default profile,
choosing "Overwrite the current profile", so the next time you
launch Fennec with the "new bookmark" profile, all the bookmarks
will be visible.
