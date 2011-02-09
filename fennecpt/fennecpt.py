#!/usr/bin/env python2.6
# -*- coding: utf-8 -*-

import Queue
import datetime
import os.path
import platform
import shutil
import tempfile
import threading
import time
import wx
import ConfigParser

from devicemanager import DeviceManager

# FIXME: Seems that the default font size for text ctrls varies across 
# platform.  There might be some generic way to do it, but I haven't figured
# it out so far...
TEXT_CTRL_HEIGHT = 20
if wx.Platform == '__WXGTK__':
    TEXT_CTRL_HEIGHT = 26


class AndroidDevice(object):
    name = 'Android'
    id = 'android'
    profile_dir = '/data/data/org.mozilla.fennec/mozilla'
    fennec_exec_path = 'org.mozilla.fennec'


class PythonDevice(object):
    name = 'Python (test)'
    id = 'python'
    profile_dir = os.path.expanduser('~/.mozilla/fennec')
    fennec_exec_path = 'fennec'  # rely on binary being in path

DEVICES = [AndroidDevice, PythonDevice]

DEFAULT_DEVICE_PORT = 20701

TAG_NAME = 'FPMTAG'

CONFIG_FILE_NAME = 'fpm.ini'
DEV_PROFILES_CONFIG_FILE_NAME = 'devices.ini'
PROFILES_DIR_NAME = 'profiles'

EVT_FPM_ID = wx.NewId()

def EVT_FPM(win, func):
    """Define Result Event."""
    win.Connect(-1, -1, EVT_FPM_ID, func)


class FptEvent(wx.PyEvent):
    """ Generic event for notifications from WorkerThread to FPMFrame. """
    
    def __init__(self, event_type, data):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_FPM_ID)
        self.event_type = event_type
        self.data = data


class FennecProfileTool(object):
    """
    Main business logic for managing and transferring profiles, plus control of fennec
    on remote device.
    """
    
    def __init__(self, local_profile_dir, device_class, dm, status_cb=None):
        self.local_profile_dir = local_profile_dir
        self.device_class = device_class
        self.dm = dm
        self.status_cb = status_cb
        self.default_profile = ''
        self.installed_profile = ''
        self.check_default_profile()

    def update_status(self, msg):
        if self.status_cb:
            self.status_cb(msg)

    def clear_status(self):
        if self.status_cb:
            self.status_cb('')

    def profiles(self):
        self.update_status('Checking profiles...')
        profile_list = os.listdir(self.local_profile_dir)
        profile_list.sort()
        self.clear_status()
        return profile_list

    def delete_profile(self, local_profile_name):
        self.update_status('Deleting profile %s...' % local_profile_name)
        local_profile_path = os.path.join(self.local_profile_dir, local_profile_name)
        if os.path.exists(local_profile_path):
            shutil.rmtree(local_profile_path)
        self.clear_status()

    def find_default_profile(self, files):
        for f in files:
            if f.find('.default') != -1:
                return f
        return ''

    def check_default_profile(self):
        self.default_profile = self.find_default_profile(self.dm.listFiles(self.device_class.profile_dir))
        if not self.default_profile:
            self.launch_fennec()
            time.sleep(15)  # wait enough time for fennec to initialize
            self.kill_fennec()
        self.default_profile = self.find_default_profile(self.dm.listFiles(self.device_class.profile_dir))
        if TAG_NAME in self.dm.listFiles(self.remote_profile_path()) and os.listdir(self.local_profile_dir):
            self.set_current_profile()
            return
        self.get_profile()

    def set_current_profile(self):
        self.installed_profile = ''
        tag_path = os.path.join(self.remote_profile_path(), TAG_NAME)
        if self.dm.fileExists(tag_path):
            self.installed_profile = self.dm.catFile(tag_path).strip()

    def remote_profile_path(self):
        return self.device_class.profile_dir + '/' + self.default_profile
    
    def get_profile(self, new_tag=''):
        """ If 'tag' is given, replace local tag (if it exists) with that value """
        local_dir = tempfile.mkdtemp(dir=self.local_profile_dir)
        self.update_status('Downloading profile...')
        print 'getting directory %s' % self.remote_profile_path()
        self.dm.getDirectory(self.remote_profile_path(), local_dir)
        print 'got directory as %s' % local_dir
        tag = ''
        local_tag_file = os.path.join(local_dir, TAG_NAME) 
        if not new_tag and os.path.exists(local_tag_file):
            try:
                tag = file(local_tag_file, 'r').read().strip()
                print 'got tag: %s' % tag
            except IOError:
                pass
        
        if not tag:
            print 'no tag'
            if new_tag:
                tag = new_tag
            else:
                # no tag; give it a default name but don't overwrite any existing profiles
                tag_base = '%s_default_as_of_%s' % (self.dm.host, datetime.date.today().isoformat())
                tag = tag_base
                i = 0
                while os.path.exists(os.path.join(self.local_profile_dir, tag)):
                    i += 1
                    tag = tag_base + '.%d' % i
            local_tag_path = os.path.join(local_dir, TAG_NAME)
            file(local_tag_path, 'w').write(tag + '\n')
            self.dm.pushFile(local_tag_path, self.remote_profile_path() + '/' + TAG_NAME)
        local_profile_path = os.path.join(self.local_profile_dir, tag)
        if os.path.exists(local_profile_path):
            shutil.rmtree(local_profile_path)
        os.rename(local_dir, local_profile_path)
        self.installed_profile = tag
        self.clear_status()

    def switch_profile(self, local_profile_name, replace_tag='', no_copy=False):
        """ gets current profile, changing tag if given, then pushes new profile """
        # update the tag file, in case the directory was renamed
        if not no_copy:
            self.get_profile(replace_tag)
        local_profile_path = os.path.join(self.local_profile_dir, local_profile_name)
        file(os.path.join(local_profile_path, TAG_NAME), 'w').write(local_profile_name + '\n')
        self.update_status('Removing current profile...')
        self.dm.removeDir(self.remote_profile_path())
        self.update_status('Uploading new profile...')
        self.dm.pushDir(local_profile_path, self.remote_profile_path())
        self.clear_status()
        self.installed_profile = local_profile_name

    def launch_fennec_with_profile(self, local_profile_name, replace_tag='', no_copy=False):
        if self.fennec_running():
            self.kill_fennec()
        self.switch_profile(local_profile_name, replace_tag, no_copy)
        self.launch_fennec()

    def launch_fennec(self):
        self.update_status('Launching fennec...')
        # for some reason, we need to pass an empty string in order to get the
        # regular start page to appear
        self.dm.fireProcess('%s ""' % self.device_class.fennec_exec_path)
        self.clear_status()

    def kill_fennec(self):
        self.update_status('Killing fennec...')
        self.dm.killProcess(self.device_class.fennec_exec_path)        
        self.clear_status()

    def fennec_running(self):
        return self.dm.processExist(self.device_class.fennec_exec_path)


class WorkerThread(threading.Thread):
    """ Thread for long-running device operations. """

    def __init__(self, notify_window, queue):
        threading.Thread.__init__(self)
        self.notify_window = notify_window
        self.queue = queue
        self.fpm = None
        self.setDaemon(1)
        self.start()
    
    def run(self):
        abort = False
        while not abort:
            event = self.queue.get()
            print 'worker thread got event: %s' % event[0]
            if event[0] == 'abort':
                abort = True
            elif event[0] == 'open':
                self.open_connection(event[1:])
            elif event[0] == 'get_profiles':
                data = [self.fpm.installed_profile]
                data.extend(self.fpm.profiles())
                wx.PostEvent(self.notify_window, FptEvent('profiles', data))
            elif event[0] == 'fennec_running':
                wx.PostEvent(self.notify_window, FptEvent('fennec_running', (self.fpm.fennec_running(),)))
            elif event[0] == 'launch_fennec_with_profile':
                local_profile_name = event[1]
                replace_tag = event[2]
                no_copy = event[3]
                self.fpm.launch_fennec_with_profile(local_profile_name, replace_tag, no_copy)
                self.set_status('')
            elif event[0] == 'delete_profile':
                local_profile_name = event[1]
                self.fpm.delete_profile(local_profile_name)
        self.dm = None
    
    def open_connection(self, args):
        host = args[0]
        port = args[1]
        device_class = args[2]
        profiles_path = args[3]
        self.fpm = None
        dm = DeviceManager(host, port)
        dm.debug = 3
        if not dm._sock:
            dm = None
            wx.PostEvent(self.notify_window, FptEvent('conn_failed', ('%s:%d' % (host, port),)))
        if dm:
            self.fpm = FennecProfileTool(profiles_path, device_class, dm, self.set_status)
            if not self.fpm.default_profile:
                self.fpm = None
                wx.PostEvent(self.notify_window, FptEvent('no_default_profile', (host,)))
            else:
                wx.PostEvent(self.notify_window, FptEvent('connected', (dm.host,)))

    def set_status(self, status):
        wx.PostEvent(self.notify_window, FptEvent('status', (status,)))


class DeviceProfile(object):
    """ Represents connection information for an agent-driven device. """
    
    host = ''
    port = DEFAULT_DEVICE_PORT
    device_class = None
    save_as = ''
    
    def __eq__(self, other):
        return self.host == other.host and \
               self.port == other.port and \
               self.device_class == other.device_class and \
               self.save_as == other.save_as

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        s = '%s %s:%d' % (self.device_class.id, self.host, self.port)
        if self.save_as:
            s += ' (%s)' % self.save_as
        return s

    def from_cfg(self, cfg, section):
        self.save_as = section
        self.host = cfg.get(section, 'host')
        self.port = cfg.getint(section, 'port')
        device_class_name = cfg.get(section, 'device')
        for d in DEVICES:
            if d.__name__ == device_class_name:
                self.device_class = d
                break
    
    def to_cfg(self, cfg):
        if not cfg.has_section(self.save_as):
            cfg.add_section(self.save_as)
        cfg.set(self.save_as, 'host', self.host)
        cfg.set(self.save_as, 'port', str(self.port))
        cfg.set(self.save_as, 'device', self.device_class.__name__)

    @classmethod
    def load_cfg(cls, cfg):
        profiles = []
        for s in cfg.sections():
            profile = DeviceProfile()
            try:
                profile.from_cfg(cfg, s)
            except ConfigParser.NoOptionError:
                continue
            profiles.append(profile)
        return profiles


class ConnectionDialog(wx.Dialog):
    """ Dialog for opening a new connection.  Can save and load device profiles. """
    
    def __init__(self, *args, **kwds):
        kwds["style"] = wx.DEFAULT_DIALOG_STYLE
        wx.Dialog.__init__(self, *args, **kwds)
        self.dev_profiles = []
        self.delete_profile_cb = None
        self.label_saved_profiles = wx.StaticText(self, -1, "Saved connections:")
        self.list_box_saved_profiles = wx.ListBox(self, -1, choices=[])
        self.Bind(wx.EVT_LISTBOX, self.select_saved_profile, self.list_box_saved_profiles)
        self.Bind(wx.EVT_LISTBOX_DCLICK, self.select_return_saved_profile, self.list_box_saved_profiles)
        wx.EVT_KEY_UP(self.list_box_saved_profiles, self.list_key_up)
        self.label_host = wx.StaticText(self, -1, "Host/IP:")
        self.text_ctrl_host = wx.TextCtrl(self, -1, "")
        self.label_port = wx.StaticText(self, -1, "Port:")
        self.text_ctrl_port = wx.TextCtrl(self, -1, str(DEFAULT_DEVICE_PORT))
        self.label_device_type = wx.StaticText(self, -1, "Device type:")
        self.radio_btn_devices = []
        for device_class in DEVICES:
            self.radio_btn_devices.append((device_class, wx.RadioButton(self, -1, device_class.name)))
        self.label_save_profile = wx.StaticText(self, -1, "Save as:")
        self.text_ctrl_save_profile = wx.TextCtrl(self, -1, "")

        self.__set_properties()
        self.__do_layout()

    def set_controls_default(self):
        self.text_ctrl_host.SetValue('')
        self.text_ctrl_port.SetValue(str(DEFAULT_DEVICE_PORT))
        self.text_ctrl_save_profile.SetValue('')
        for i, btn_device in enumerate(self.radio_btn_devices):
            self.radio_btn_devices[i][1].SetValue(i == 0)

    def __set_properties(self):
        self.SetTitle("Open device connection")
        self.list_box_saved_profiles.SetMinSize((200, 315))
        self.text_ctrl_host.SetMinSize((160, TEXT_CTRL_HEIGHT))
        self.text_ctrl_port.SetMinSize((160, TEXT_CTRL_HEIGHT))
        self.text_ctrl_save_profile.SetMinSize((160, TEXT_CTRL_HEIGHT))

    def __do_layout(self):
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_controls = wx.FlexGridSizer(4, 2, 5, 5)
        main_sizer.Add(left_sizer, 0, 0, 0)
        main_sizer.Add(right_sizer, 0, 0, 0)
        left_sizer.Add(self.label_saved_profiles, 0, wx.ALL, 10)
        left_sizer.Add(self.list_box_saved_profiles, 1, wx.LEFT|wx.RIGHT|wx.BOTTOM, 10)
        grid_sizer_controls.Add(self.label_host, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_controls.Add(self.text_ctrl_host, 0, 0, 0)
        grid_sizer_controls.Add(self.label_port, 0, wx.ALIGN_CENTER_VERTICAL|wx.TOP, 5)
        grid_sizer_controls.Add(self.text_ctrl_port, 0, wx.TOP, 5)
        grid_sizer_controls.Add(self.label_device_type, 0, wx.ALIGN_CENTER_VERTICAL|wx.TOP, 5)
        sizer_device_types = wx.BoxSizer(wx.VERTICAL)
        for device_class, radio_btn in self.radio_btn_devices:
            sizer_device_types.Add(radio_btn, 0, wx.TOP, 5)
        grid_sizer_controls.Add(sizer_device_types, 1, wx.EXPAND|wx.TOP, 5)
        grid_sizer_controls.Add(self.label_save_profile, 0, wx.ALIGN_CENTER_VERTICAL|wx.TOP, 5)
        grid_sizer_controls.Add(self.text_ctrl_save_profile, 0, wx.TOP, 5)
        right_sizer.Add(grid_sizer_controls, 10, wx.ALL|wx.EXPAND, 10)
        button_sizer = self.CreateSeparatedButtonSizer(wx.OK|wx.CANCEL)
        if button_sizer:
            # FIXME: guh, hack until I can figure out how to do this better
            prop = 11
            if wx.Platform == '__WXGTK__':
                prop = 7
            right_sizer.Add((0,0), prop, wx.EXPAND)
            right_sizer.Add(button_sizer, 0, wx.EXPAND|wx.ALL|wx.ALIGN_BOTTOM, 10)
        self.SetSizer(main_sizer)
        main_sizer.Fit(self)
        self.text_ctrl_host.SetFocus()
        self.Layout()
        self.Centre()
    
    def select_return_saved_profile(self, event):
        self.select_saved_profile(event)
        if self.IsModal():
            self.EndModal(wx.ID_OK)
        else:
            self.SetReturnCode(wx.ID_OK)
            # close?
    
    def select_saved_profile(self, event):
        selection = self.list_box_saved_profiles.GetSelection()
        if selection == wx.NOT_FOUND:
            return
        profile = self.dev_profiles[selection]
        self.text_ctrl_host.SetValue(profile.host)
        self.text_ctrl_port.SetValue(str(profile.port))
        self.text_ctrl_save_profile.SetValue(profile.save_as)
        for device_class, radio_btn in self.radio_btn_devices:
            radio_btn.SetValue(device_class == profile.device_class)

    def set_device_profiles(self, dev_profiles):
        self.dev_profiles = dev_profiles[:]
        self.dev_profiles.sort(key=lambda x: x.save_as)
        self.list_box_saved_profiles.Set(map(lambda x: x.save_as, self.dev_profiles))

    def list_key_up(self, event):
        keycode = event.GetKeyCode()
        selection = self.list_box_saved_profiles.GetSelection()
        if selection == wx.NOT_FOUND or event.GetKeyCode() != wx.WXK_DELETE or not self.delete_profile_cb:
            return
        profile = self.dev_profiles[selection]
        self.delete_profile_cb(profile)
        self.dev_profiles.pop(selection)
        self.set_controls_default()
        self.list_box_saved_profiles.Set(map(lambda x: x.save_as, self.dev_profiles))

    def set_delete_profile_cb(self, cb):
        self.delete_profile_cb = cb

    def GetValues(self):
        profile = DeviceProfile()
        profile.host = self.text_ctrl_host.GetValue()
        profile.port = int(self.text_ctrl_port.GetValue())
        profile.save_as = self.text_ctrl_save_profile.GetValue()
        for device_class, radio_btn in self.radio_btn_devices:
            if radio_btn.GetValue():
                profile.device_class = device_class
                break
        return profile


class RadioChoiceDialog(wx.Dialog):
    """
    wx.SingleChoiceDialog uses a huge list box to display alternatives.  This class 
    uses radio buttons to generate a much more compact dialog.
    """

    def __init__(self, parent, message, title, choices, *args, **kwds):
        kwds["style"] = wx.DEFAULT_DIALOG_STYLE
        wx.Dialog.__init__(self, parent, *args, **kwds)
        self.label_message = wx.StaticText(self, -1, message)
        self.radios = []
        for c in choices:
            self.radios.append(wx.RadioButton(self, -1, c))
        self.SetTitle(title)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.label_message, 0, wx.ALL, 10)
        for r in self.radios:
            main_sizer.Add(r, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, 10)
        button_sizer = self.CreateSeparatedButtonSizer(wx.OK|wx.CANCEL)
        if button_sizer:
            main_sizer.Add(button_sizer, 0, wx.EXPAND|wx.ALL|wx.ALIGN_BOTTOM, 10)
        self.SetSizer(main_sizer)
        main_sizer.Fit(self)
        self.Layout()
        self.Centre()
    
    def GetSelection(self):
        for i, r in enumerate(self.radios):
            if r.GetValue():
                return i
        return wx.NOT_FOUND


class FPMFrame(wx.Frame):
    """ Main window. """

    STATE_IDLE = 1
    STATE_LAUNCH_CHECK_PROFILES = 2
    STATE_LAUNCH_CHECK_RUNNING = 3
    
    def __init__(self, *args, **kwds):
        kwds["style"] = wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.Bind(wx.EVT_CLOSE, self.quit, self)
        
        self.FennecProfileTool_menubar = wx.MenuBar()
        wxglade_tmp_menu = wx.Menu()
        menuItem = wxglade_tmp_menu.Append(wx.NewId(), "Open", "", wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, self.open_connection, menuItem)
        menuItem = wxglade_tmp_menu.Append(wx.ID_EXIT, "Quit", "", wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, self.quit, menuItem)
        self.FennecProfileTool_menubar.Append(wxglade_tmp_menu, "File")
        self.SetMenuBar(self.FennecProfileTool_menubar)
        self.FennecProfileTool_statusbar = self.CreateStatusBar(2, 0)
        self.panel = wx.Panel(self, -1, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL)
        self.label_profile_list = wx.StaticText(self.panel, -1, "Available profiles:")
        self.list_box_profiles = wx.ListBox(self.panel, -1, choices=[])
        self.Bind(wx.EVT_LISTBOX, self.select_profile, self.list_box_profiles)
        self.Bind(wx.EVT_LISTBOX_DCLICK, self.launch_fennec, self.list_box_profiles)
        wx.EVT_KEY_UP(self.list_box_profiles, self.profile_list_key_up)
        self.button_launch = wx.Button(self.panel, -1, "Launch Fennec")
        self.select_profile()
        self.Bind(wx.EVT_BUTTON, self.launch_fennec, self.button_launch)
        EVT_FPM(self, self.fpm_event)

        self.state = self.STATE_IDLE
        self.queue = Queue.Queue()
        self.worker = WorkerThread(self, self.queue)

        self.__set_properties()
        self.__do_layout()
        self.profile_map = {}

    def __set_properties(self):
        self.SetTitle("Fennec Profile Tool")
        self.SetSize((438, 400))
        self.FennecProfileTool_statusbar.SetStatusWidths([-1, -1])
        FennecProfileTool_statusbar_fields = ["Not connected."]
        for i in range(len(FennecProfileTool_statusbar_fields)):
            self.FennecProfileTool_statusbar.SetStatusText(FennecProfileTool_statusbar_fields[i], i)

    def __do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.label_profile_list, 0, wx.LEFT|wx.TOP|wx.EXPAND, 10)
        sizer.Add(self.list_box_profiles, 100, wx.ALL|wx.EXPAND, 10)
        sizer.Add(self.button_launch, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.ALIGN_RIGHT, 10)
        self.panel.SetSizer(sizer)
        self.panel.Layout()

    def fpm_event(self, event):
        print 'ui got event: %s' % event.event_type
        if event.event_type == 'conn_failed':
            self.set_status('Not connected.', 0)
            self.show_msg('Could not connect to device at %s.' % event.data[0], 'Error connecting',
                          wx.OK | wx.ICON_ERROR)
        elif event.event_type == 'no_default_profile':
            self.show_msg('There is no default profile on the device.  Please create one and reconnect.',
                          'No default profile', wx.OK | wx.ICON_ERROR)
        elif event.event_type == 'connected':
            self.set_status('Connected to %s.' % event.data[0], 0)
            self.queue.put(('get_profiles',))
        elif event.event_type == 'profiles':
            installed_profile = event.data[0]
            profiles = event.data[1:]
            if self.state == self.STATE_IDLE:
                self.profile_map = {}
                selections = []
                for i, p in enumerate(profiles):
                    self.profile_map[i] = p
                    if p == installed_profile:
                        selections.append(p + ' (installed)')
                    else:
                        selections.append(p)
                self.list_box_profiles.Set(selections)
            elif self.state == self.STATE_LAUNCH_CHECK_PROFILES:
                self.launch_fennec_check_profile(installed_profile, profiles)
        elif event.event_type == 'fennec_running':
            fennec_running = event.data[0]
            if self.state == self.STATE_LAUNCH_CHECK_RUNNING:
                self.launch_fennec_check_running(fennec_running)
        elif event.event_type == 'status':
            status = event.data[0]
            self.set_status(status)

    def disable_ui(self):
        self.list_box_profiles.Disable()
        self.button_launch.Disable()
    
    def enable_ui(self):
        self.list_box_profiles.Enable()
        self.enable_launch_if_selection()

    def set_status(self, msg, field=1):
        if msg:
            self.disable_ui()
        else:
            self.enable_ui()
        self.FennecProfileTool_statusbar.SetStatusText(msg, field)

    def init(self):
        if not self.find_profile():
            self.show_msg('Could not find a reasonable place for FPM configuration!', 'No FPM config', wx.OK | wx.ICON_ERROR)
            self.quit()
        self.open_connection()

    def enable_launch_if_selection(self):
        self.button_launch.Enable(self.list_box_profiles.GetSelection() != wx.NOT_FOUND)

    def select_profile(self, event=None):
        self.enable_launch_if_selection()

    def quit(self, event=None):
        self.queue.put(('abort',))
        self.worker.join(3)
        self.Destroy()

    def profile_list_key_up(self, event):
        keycode = event.GetKeyCode()
        selection = self.list_box_profiles.GetSelection()
        if selection == wx.NOT_FOUND or event.GetKeyCode() != wx.WXK_DELETE:
            return
        
        selected_profile = self.profile_map[self.list_box_profiles.GetSelection()]
        result = self.show_msg('Really delete profile "%s"?' % selected_profile,
                               'Delete profile', wx.OK | wx.CANCEL | wx.ICON_WARNING)
        if result == wx.ID_OK:
            self.queue.put(('delete_profile', selected_profile))
            self.queue.put(('get_profiles',))

    def launch_fennec_check_profile(self, installed_profile, profiles):
        newtag = ''
        no_copy = False
        overwrite = False
        if installed_profile in profiles:
            while not (newtag or no_copy or overwrite):
                dlg = RadioChoiceDialog(None, 'The profile "%s" exists on the local machine.  Do you want to...' % installed_profile,
                    'Profile exists', ['Overwrite the current profile?', 'Copy the profile locally under a new name?',
                                       'Don\'t copy it locally?'])
                result = dlg.ShowModal()
                if result == wx.ID_CANCEL:
                    dlg.Destroy()
                    return
                choice = dlg.GetSelection()
                if choice == 0:
                    newtag = ''
                    overwrite = True
                elif choice == 1:
                    newnamedlg = wx.TextEntryDialog(None, 'New profile name:', 'New profile')
                    if wx.ID_OK == newnamedlg.ShowModal():
                        entered_name = newnamedlg.GetValue()
                        if entered_name == installed_profile:
                            self.show_msg('That\'s the same name!', 'Same name')
                        elif not entered_name:
                            self.show_msg('You must enter a profile name.', 'No name given')
                        else:
                            newtag = entered_name
                    newnamedlg.Destroy()
                elif choice == 2:
                    no_copy = True
                dlg.Destroy()
        selected_profile = self.profile_map[self.list_box_profiles.GetSelection()]
        self.set_status('Launching fennec...')
        self.queue.put(('launch_fennec_with_profile', selected_profile, newtag, no_copy))
        self.state = self.STATE_IDLE
        self.queue.put(('get_profiles',))

    def launch_fennec_check_running(self, fennec_running):
        if fennec_running:
            result = self.show_msg('Fennec is currently running; the current process will be killed and restarted with the new profile.',
                                   'Fennec running', wx.OK | wx.CANCEL | wx.ICON_WARNING)
            if result == wx.ID_CANCEL:
                self.state = self.STATE_IDLE
                return
        self.state = self.STATE_LAUNCH_CHECK_PROFILES
        self.queue.put(('get_profiles',))                

    def launch_fennec(self, event):
        self.state = self.STATE_LAUNCH_CHECK_RUNNING
        self.queue.put(('fennec_running',))

    def delete_profile(self, profile_name):
        print 'removing %s' % profile_name
        self.dev_profiles_cfg.remove_section(profile_name.save_as)
        self.dev_profiles_cfg.write(file(self.dev_profile_cfg_file_path, 'w'))

    def open_connection(self, event=None):
        selected_device_profile = None
        dlg = ConnectionDialog(None)
        dlg.set_delete_profile_cb(self.delete_profile)
        device_profiles = DeviceProfile.load_cfg(self.dev_profiles_cfg)
        dlg.set_device_profiles(device_profiles)
        if dlg.ShowModal() == wx.ID_OK: 
            selected_device_profile = dlg.GetValues()
        if selected_device_profile:
            print 'selected profile: %s' % selected_device_profile
            if selected_device_profile.save_as:
                if selected_device_profile not in device_profiles:
                    selected_device_profile.to_cfg(self.dev_profiles_cfg)
                    self.dev_profiles_cfg.write(file(self.dev_profile_cfg_file_path, 'w'))
            self.set_status('Connecting to %s:%d...' % (selected_device_profile.host, selected_device_profile.port), 0)
            self.queue.put(('open', selected_device_profile.host, selected_device_profile.port, selected_device_profile.device_class, self.profiles_path))
        dlg.Destroy()

    def show_msg(self, msg, title, options):
        dlg = wx.MessageDialog(None, msg, title, options)
        result = dlg.ShowModal()
        dlg.Destroy()
        return result

    def find_profile(self):
        path = None
        if platform.system() == "Darwin":
            # Use FSFindFolder
            from Carbon import Folder, Folders
            pathref = Folder.FSFindFolder(Folders.kUserDomain,
                                          Folders.kApplicationSupportFolderType,
                                          Folders.kDontCreateFolder)
            basepath = pathref.FSRefMakePath()
            path = os.path.join(basepath, "FennecPT")
        elif platform.system() == "Windows":
            # Use SHGetFolderPath
            import ctypes
            SHGetFolderPath = ctypes.windll.shell32.SHGetFolderPathW
            SHGetFolderPath.argtypes = [ctypes.c_void_p,
                                        ctypes.c_int,
                                        ctypes.c_void_p,
                                        ctypes.c_int32,
                                        ctypes.c_wchar_p]
            CSIDL_APPDATA = 26
            path_buf = ctypes.create_unicode_buffer(1024)
            if SHGetFolderPath(0, CSIDL_APPDATA, 0, 0, path_buf) == 0:
                path = os.path.join(path_buf.value, "Mozilla", "FennecPT")
        else: # Assume POSIX
            # Pretty simple in comparison, eh?
            path = os.path.expanduser("~/.mozilla/fennecpt")
        if path is None:
            return False
        if not os.path.exists(path):
            os.makedirs(path)
        self.cfg = ConfigParser.SafeConfigParser()
        self.cfg_file_path = os.path.join(path, CONFIG_FILE_NAME) 
        if os.path.exists(self.cfg_file_path):
            self.cfg.read(self.cfg_file_path)
        self.dev_profiles_cfg = ConfigParser.SafeConfigParser()
        self.dev_profile_cfg_file_path = os.path.join(path, DEV_PROFILES_CONFIG_FILE_NAME)
        if os.path.exists(self.dev_profile_cfg_file_path):
            self.dev_profiles_cfg.read(self.dev_profile_cfg_file_path)
        self.profiles_path = os.path.join(path, PROFILES_DIR_NAME)
        if not os.path.exists(self.profiles_path):
            os.makedirs(self.profiles_path)
        return True
    

class FPMApp(wx.App):

    def __init__(self):
        wx.App.__init__(self, 0)
    
    def OnInit(self):
        wx.InitAllImageHandlers()
        MyFPMFrame = FPMFrame(None, -1, "")
        self.SetTopWindow(MyFPMFrame)
        MyFPMFrame.CenterOnScreen()
        MyFPMFrame.Show()
        MyFPMFrame.init()
        return 1

def main():
    fpm = FPMApp()
    fpm.MainLoop()


if __name__ == "__main__":
    main()
