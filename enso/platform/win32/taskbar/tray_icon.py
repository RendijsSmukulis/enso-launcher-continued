import logging
import os
import time
import win32api # @UnresolvedImport
import win32con # @UnresolvedImport
import win32gui # @UnresolvedImport
import winerror  # @UnresolvedImport

from inspect import getargspec
from enso.platform.win32.graphics import get_cursor_pos


class SysTrayIcon(object):

    MENU_ITEM_ID_ABOUT = 1023
    MENU_ITEM_ID_EXIT = 1024
    free_menu_id = 1025

    def __init__(self,
                 icon,
                 hover_text,
                 menu_options,
                 on_quit=None,
                 default_menu_index=None,
                 window_class_name = "EnsoTrayWndClass",):

        self.default_icon = icon
        self.hover_text = hover_text
        self.notify_id = None
        self._on_quit = None
        if on_quit:
            if not callable(on_quit):
                raise Exception("SysTrayIcon on_quit parameter must be callable")
            self._on_quit = on_quit
        self.custom_menu_items = {}

        self.WM_ONLOAD = win32gui.RegisterWindowMessage("SystrayOnLoad")
        self.WM_CREATED = win32gui.RegisterWindowMessage("TaskbarCreated")
        message_map = {
                self.WM_CREATED : self._on_restart,
                self.WM_ONLOAD: self._on_load,
                win32con.WM_DESTROY: self._on_destroy,
                win32con.WM_COMMAND: self._on_command,
                win32con.WM_USER + 20 : self._on_taskbar_notify,
        }

        # Register the Window class.
        self._window_class = win32gui.WNDCLASS()
        self._window_class.hInstance = win32api.GetModuleHandle(None)  # @UndefinedVariable
        self._window_class.lpszClassName = window_class_name
        self._window_class.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW;
        self._window_class.hCursor = win32api.LoadCursor(0, win32con.IDC_ARROW)  # @UndefinedVariable
        self._window_class.hbrBackground = win32con.COLOR_WINDOW
        self._window_class.lpfnWndProc = message_map # could also specify a wndproc.

        # Don't blow up if class already registered to make testing easier
        try:
            self.class_atom = win32gui.RegisterClass(self._window_class)
        except win32gui.error, err_info:
            if err_info.winerror != winerror.ERROR_CLASS_ALREADY_EXISTS:
                raise

        # Create the helper Window
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(
            self.class_atom,
            window_class_name, #Title same as class-name
            style,
            0,
            0,
            win32con.CW_USEDEFAULT,
            win32con.CW_USEDEFAULT,
            0,
            0,
            self._window_class.hInstance,
            None)
        win32gui.UpdateWindow(self.hwnd)

        self._create_icons()


    def _create_icons(self):
        # Try and find a custom icon
        hinst =  win32api.GetModuleHandle(None)  # @UndefinedVariable

        """
        iconPathName = os.path.abspath(os.path.join( os.path.split(sys.executable)[0], "pyc.ico" ))
        if not os.path.isfile(iconPathName):
            # Look in DLLs dir, a-la py 2.5
            iconPathName = os.path.abspath(os.path.join( os.path.split(sys.executable)[0], "DLLs", "pyc.ico" ))
        if not os.path.isfile(iconPathName):
            # Look in the source tree.
            iconPathName = os.path.abspath(os.path.join( os.path.split(sys.executable)[0], "..\\PC\\pyc.ico" ))
        if os.path.isfile(iconPathName):
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            hicon = win32gui.LoadImage(hinst, iconPathName, win32con.IMAGE_ICON, 0, 0, icon_flags)
        else:
            print "Can't find a Python icon file - using default"
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        """
        hicon = None
        if os.path.isfile(self.default_icon):
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            try:
                hicon = win32gui.LoadImage(hinst,
                                       self.default_icon,
                                       win32con.IMAGE_ICON,
                                       0,
                                       0,
                                       icon_flags)
            except:
                logging.error("Can't load icon file - using default.")

        if not hicon:
            logging.error("Can't find icon file - using default.")
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

        self.hicon = hicon

        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        nid = (self.hwnd, 0, flags, win32con.WM_USER + 20, hicon, self.hover_text)
        self.notify_id = nid
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        except win32gui.error:
            # This is common when windows is starting, and this code is hit
            # before the taskbar has been created.
            # Keep running anyway - when explorer starts, we get the
            # TaskbarCreated message.
            logging.warning("Failed to add the taskbar icon - is explorer running?")

    def _on_load(self, hwnd, msg, wparam, lparam):
        pass

    def _on_restart(self, hwnd, msg, wparam, lparam):
        self._create_icons()

    def _on_destroy(self, hwnd, msg, wparam, lparam):
        win32gui.PostQuitMessage(0) # Terminate the current thread.

    def _on_taskbar_notify(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_LBUTTONUP:
            if self.on_leftclick:
                self.on_leftclick(self)
        elif lparam == win32con.WM_LBUTTONDBLCLK:
            if self.on_doubleclick:
                self.on_doubleclick(self)
        elif lparam == win32con.WM_RBUTTONUP:
            if self.on_rightclick:
                self.on_rightclick(self)
        return 1

    def _on_command(self, hwnd, msg, wparam, lparam):
        id = win32api.LOWORD(wparam)  # @UndefinedVariable
        if id == self.MENU_ITEM_ID_ABOUT:
            if self.on_about:
                self.on_about(self)
        elif id == self.MENU_ITEM_ID_EXIT:
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0))
            self.on_quit()
            win32gui.DestroyWindow(self.hwnd)
            win32gui.UnregisterClass(self.class_atom, self._window_class.hInstance)
        elif id in self.custom_menu_items:
            if callable(self.custom_menu_items[id]['func']):
                try:
                    self.custom_menu_items[id]['func'](self)
                except Exception, e:
                    logging.error("Error executing menu item func: %s" % self.custom_menu_items[id]['text'])
                    logging.error(e)
        else:
            logging.info("Unknown command %d", id)

    def on_quit(self, systray):
        # Execute custom on_quit function if specified
        if self._on_quit and callable(self._on_quit):
            try:
                self._on_quit(systray)
            except Exception as e:
                logging.error("tay_icon.on_quit() failed: %s", e)

    def on_about(self, systray):
        pass

    def on_doubleclick(self, systray):
        pass

    def on_leftclick(self, systray):
        pass

    def on_rightclick(self, systray):
        #self.change_tooltip("You right clicked me.")
        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu( menu, win32con.MF_STRING, 1023, "About")
        if len(self.custom_menu_items) > 0:
            for menu_item in self.custom_menu_items.itervalues():
                if callable(menu_item['func']):
                    try:
                        is_checked = menu_item['func'](self, get_state = True)
                    except Exception, e:
                        print e
                else:
                    is_checked = False
                flags = win32con.MF_STRING | (win32con.MF_CHECKED if is_checked else 0)
                win32gui.AppendMenu( menu, flags, menu_item['id'], menu_item['text'])

        win32gui.AppendMenu( menu, win32con.MF_SEPARATOR, -1, "")
        win32gui.AppendMenu( menu, win32con.MF_STRING, 1024, "E&xit")
        win32gui.SetMenuDefaultItem(menu, 0, True)
        pos = get_cursor_pos()
        # From MSDN:
        # To display a context menu for a notification icon, the current window must be the foreground window
        # before the application calls TrackPopupMenu or TrackPopupMenuEx. Otherwise, the menu will not disappear
        # when the user clicks outside of the menu or the window that created the menu (if it is visible).
        # However, when the current window is the foreground window, the second time this menu is displayed,
        # it displays and then immediately disappears. To correct this, you must force a task switch
        # to the application that called TrackPopupMenu. This is done by posting a benign message to the window
        # or thread.
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, pos[0], pos[1], 0, self.hwnd, None)
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)

    def add_menu_item(self, text, func):
        assert len(text) > 0
        assert callable(func)
        assert len(getargspec(func)[0]) == 2 and getargspec(func)[0][1] == 'get_state', "Second function argument must be 'get_state'"
        self.custom_menu_items[self.free_menu_id] = { 'id':self.free_menu_id, 'text':text, 'func':func }
        self.free_menu_id += 1

    def change_tooltip(self, text):
        # Try and find a custom icon
        if self.notify_id:
            message = win32gui.NIM_MODIFY
        else:
            message = win32gui.NIM_ADD
        self.notify_id = (self.hwnd,
                          0,
                          win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
                          win32con.WM_USER + 20,
                          self.hicon,
                          text)
        try:
            win32gui.Shell_NotifyIcon(message, self.notify_id)
        except:
            pass

    def main_thread(self):
        win32gui.PumpMessages()

# vim:set tabstop=4 shiftwidth=4 expandtab:
