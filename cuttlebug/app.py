import build, gdb, project, settings
import ui.styles as styles
import ui.menu as menu
#import ui.controls as controls
#import ui.views as views

import logging, os
import wx

IDLE = 0
BUILDING = 1
ATTACHED = 2
CONNECTED = 3
RUNNING = 4
class AppEvent(wx.PyEvent):
    def __init__(self, _type, obj=None, data=None):
        super(AppEvent, self).__init__()
        self.SetEventType(_type.typeId)
        self.SetEventObject(obj)
        self.data = data


EVT_APP_PROJECT_OPENED = wx.PyEventBinder(wx.NewEventType())
EVT_APP_PROJECT_CLOSED = wx.PyEventBinder(wx.NewEventType())
EVT_APP_TARGET_CONNECTED = wx.PyEventBinder(wx.NewEventType())
EVT_APP_TARGET_DISCONNECTED = wx.PyEventBinder(wx.NewEventType())
EVT_APP_TARGET_RUNNING = wx.PyEventBinder(wx.NewEventType())
EVT_APP_TARGET_HALTED = wx.PyEventBinder(wx.NewEventType())

class Controller(wx.EvtHandler):

    def __init__(self, frame=None):
        super(Controller, self).__init__()

        self.style_manager = styles.StyleManager()
        self.state = IDLE
        self.gdb = gdb.session
        self.frame = frame
        self.project = None
        self.download_request = False
        try:
            self.settings = settings.Settings.load(".settings")
        except:
            self.settings = settings.Settings.create(".settings")
        
        # Build events
        self.Bind(build.EVT_BUILD_FINISHED, self.on_build_finished)
        self.Bind(build.EVT_BUILD_STARTED, self.on_build_started)
        self.Bind(build.EVT_BUILD_UPDATE, self.on_build_update)
        
 #       self.Bind(gdb.EVT_GDB_UPDATE, self.on_breakpoint_update)
              

    def setup_gdb(self):
        g = gdb.session
        g.mi_log = logging.getLogger('gdb.mi')
        g.console_log = logging.getLogger('gdb.stream')
        g.target_log = logging.getLogger('gdb.stream')
        g.log_log = logging.getLogger('gdb.stream')
        self.error_logger = logging.getLogger('error')
        
        g.Bind(gdb.EVT_GDB_STARTED, self.on_gdb_started)
        g.Bind(gdb.EVT_GDB_FINISHED, self.on_gdb_finished)
        g.Bind(gdb.EVT_GDB_ERROR, self.on_gdb_error)
        g.Bind(gdb.EVT_GDB_STOPPED, self.on_gdb_stopped)
        g.Bind(gdb.EVT_GDB_RUNNING, self.on_gdb_running)
        g.Bind(gdb.EVT_GDB_UPDATE_STACK, self.on_gdb_stack_update)
        #g.Bind(gdb.EVT_GDB_UPDATE_BREAKPOINTS, self.on_update_breakpoints)
        #g.Bind(gdb.EVT_GDB_UPDATE_VARS, self.on_update_vars)
        self.gdb = g
  
    def setup_logs(self):
        pass

    def gdb_input_handler(self, txt):
        if self.state == ATTACHED:
            try:
                self.gdb.command(txt)
            except Exception, e:
                print e
            
    def load_session(self):
        try:
            #settings.load_session()
            project_filename = settings.session_get('project_filename')
            try:
                self.load_project(project_filename)
                open_files = settings.session_get('open_files')
                if open_files:
                    for _file in open_files:
                        self.open_file(_file)
                self.frame.project_view.load_state(settings.session_get('project_view_state'))
            except Exception,  e:
                pass
            
            try:
                perspective = settings.session_get('perspective')
                if perspective:
                    self.frame.manager.LoadPerspective(perspective)
            except Exception, e:
                print "problem loading perspective:", e

        
        except Exception, e:
            self.session = {}
    
    def save_session(self):
        if self.project:
            settings.session_set('project_filename', self.project.filename)
            settings.session_set('open_files', self.frame.editor_view.open_files)
            settings.session_set('project_view_state', self.frame.project_view.save_state())
        if self.frame.editor_maximized:
            settings.session_set('perspective', self.frame.saved_perspective)
        else:
            settings.session_set('perspective', self.frame.manager.SavePerspective())
            
        settings.save_session()
        
    def new_project(self, path):
        if path:
            project_view = self.frame.project_view
            self.project = project.Project.create(path)
            project_view.set_project(self.project)
            menu.manager.publish(menu.PROJECT_OPEN)
            evt = AppEvent(EVT_APP_PROJECT_OPENED, self, data=self.project)
            wx.PostEvent(self, evt)

    def load_project(self, path):
        project_view = self.frame.project_view
        self.project = project.Project.load(path)
        menu.manager.publish(menu.PROJECT_OPEN)
        project_view.set_project(self.project)
        settings.session_set('project_filename', path)
        evt = AppEvent(EVT_APP_PROJECT_OPENED, self, data=self.project)
        if self.gdb:
            self.gdb.cd(self.project.directory)
        wx.PostEvent(self, evt)

    def unload_project(self):
        if self.project:
            self.project = None
            menu.manager.publish(menu.PROJECT_CLOSE)
            self.frame.project_view.set_project(None)
            settings.session_set('project_filename', '')
            self.detach()
            evt = AppEvent(EVT_APP_PROJECT_CLOSED, self)
            wx.PostEvent(self, evt)
            
    def goto(self, _file, line):
        absolute_file = self.project.absolute_path(_file)
        self.frame.editor_view.goto(absolute_file, line)

    def show_error(self, _file, line):
        absolute_file = self.project.absolute_path(_file)
        self.frame.editor_view.show_error(absolute_file, line)
        
    def save_project(self):
        self.project.save()

    def open_file(self, path):
        self.frame.open_file(path)

    def update_settings(self):
        self.settings.save()
        self.frame.editor_view.update_settings()

    def update_styles(self):
        self.frame.editor_view.update_settings()
        
    # STATE MANAGEMENT
    # ==========================================================
    def enter_attached_state(self):
        #project = self.project
        menu.manager.publish(menu.TARGET_ATTACHED)
        #print "Entering the ATTACHED state."
        if self.state == IDLE:
            self.gdb.cd(self.project.directory)
            #self.frame.debug_view.set_model(self.gdb)
            self.frame.runtime_view.set_model(self.gdb)
            self.frame.editor_view.set_model(self.gdb)
            self.project.load_target() # Do this to reload the SFRs for the runtime tree, in case we edited the target file
            self.frame.disassembly_view.set_model(self.gdb)
            self.exit_current_state()
            self.frame.statusbar.set_icon(self.frame.statusbar.CONNECTED)
            self.state = ATTACHED
            self.halt(callback=self.do_post_attach_cmd, download=self.download_request)
                        
        elif self.state == RUNNING:
            self.exit_current_state()
            self.frame.statusbar.set_icon(self.frame.statusbar.CONNECTED)
            self.state = ATTACHED
            if self.download_request:
                self.download()

        elif self.state == ATTACHED:
            if self.download_request:
                self.download()
            #self.frame.statusbar.set_state("Halted")
        else:
            self.error_logger.log(logging.WARN, "Tried to attach from state %d" % self.state)

    def exit_attached_state(self):
        pass

    def enter_running_state(self):
        menu.manager.publish(menu.TARGET_RUNNING)
        if self.state == ATTACHED:
            self.exit_current_state()
            self.frame.statusbar.set_icon(self.frame.statusbar.RUNNING)
            self.frame.statusbar.set_state("Running",blink=True)
            self.state = RUNNING
        else:
            self.error_logger.log(logging.WARN, "Tried to run from state %d" % self.state)

    def exit_running_state(self):
        menu.manager.publish(menu.TARGET_HALTED)

    def enter_idle_state(self):
        self.exit_current_state()
        menu.manager.publish(menu.TARGET_DETACHED)
        self.frame.statusbar.set_icon(self.frame.statusbar.RUNNING)
        self.frame.statusbar.working = False
        self.frame.statusbar.text = ""

        self.state = IDLE

    def exit_idle_state(self):
        pass

    def exit_current_state(self):
        try:
            callable =  {ATTACHED   : self.exit_attached_state,
                         RUNNING    : self.exit_running_state,
                         IDLE       : self.exit_idle_state}[self.state]
            wx.CallAfter(callable)
        except Exception, e:
            print e
            pass

    def enter_state(self, state):
        try:
            callable =  {ATTACHED   : self.enter_attached_state,
                         RUNNING    : self.enter_running_state,
                         IDLE       : self.enter_idle_state}[state]
            wx.CallAfter(callable)
        except Exception, e:
            print e
            pass

    def change_state(self, state):    
        self.enter_state(state)

    def do_post_attach_cmd(self, cmd):
        if self.project.debug.post_attach_cmd:
            self.gdb.command(self.project.debug.post_attach_cmd, self.do_post_post_attach_cmd)
        else:
            if self.download_request:
                self.download()
            
    def do_post_post_attach_cmd(self, result):
        if self.download_request:
            self.download()

    # ==========================================================
    
   
    # STEP
    def step(self):
        if self.state == ATTACHED:
            self.gdb.exec_step()

    def step_over(self):
        if self.state == ATTACHED:
            self.gdb.exec_next()

    def step_instruction(self):
        if self.state == ATTACHED:
            self.gdb.exec_step_instruction()

    def step_out(self):
        if self.state == ATTACHED:
            self.gdb.exec_finish()
    # RUN
    def run(self):
        if self.state == IDLE:
            self.change_state(ATTACHED)
        elif self.state == RUNNING:
            return
        self.gdb.exec_continue(self.on_running)
            
    def on_running(self, result):
        try:
            if result.cls.lower() == "running":
                self.change_state(RUNNING)
                evt = AppEvent(EVT_APP_TARGET_RUNNING, self)
                wx.PostEvent(self, evt)
            elif result.cls.lower() == "stopped":
                print result
            else:
                raise "UNEXPECTED PROBLEM WHILE RUNNING"
        except:
            print result
    def run_to(self, file, line):
        if self.state == ATTACHED:
            self.gdb.exec_until(file, line)

    #
    # BREAKPOINTS
    #
    def set_breakpoint(self, file, line):
        self.gdb.break_insert(self.project.relative_path(file), line, callback=self.on_gdb_done)

    def clear_breakpoint(self, number):
        self.gdb.break_delete(number, callback=self.on_gdb_done)
                    
    def disable_breakpoint(self, number):
        self.gdb.break_disable(number, callback=self.on_gdb_done)

    def enable_breakpoint(self, number):
        self.gdb.break_enable(number, callback=self.on_gdb_done)                

    def clear_breakpoint_byfile(self, file, line):
        for bkpt in self.gdb.breakpoints:
            file = self.project.relative_path(file)
            f, l = self.project.relative_path(bkpt.fullname), bkpt.line
            if l == line and f == file:
                self.gdb.break_delete(self.gdb.breakpoints.get_number(file, line), self.on_gdb_done)

    def disable_breakpoint_byfile(self, file, line):
        for bkpt in self.gdb.breakpoints:
            file = self.project.relative_path(file)
            f, l = self.project.relative_path(bkpt.fullname), bkpt.line
            if l == line and f == file:
                self.gdb.break_disable(self.gdb.breakpoints.get_number(file, line), self.on_gdb_done)

    def enable_breakpoint_byfile(self, file, line):
        for bkpt in self.gdb.breakpoints:
            file = self.project.relative_path(file)
            f, l = self.project.relative_path(bkpt.fullname), bkpt.line
            if l == line and f == file:
                self.gdb.break_enable(self.gdb.breakpoints.get_number(file, line), self.on_gdb_done)

    def on_update_breakpoints(self, evt):
        pass
        #self.frame.editor_view.update_breakpoints()                
        
    def add_watch(self, s):
        self.frame.runtime_view.add_watch(s)
        
    def halt(self, callback=None, download=False):
        self.download_request = download
        self.gdb.exec_interrupt(callback)
        #self.gdb.sig_interrupt()
        
    def set_exec_location(self, file, line, goto=False):
        self.frame.editor_view.set_exec_location(file, line, goto)
        
    def on_halted(self, result):
        self.gdb.update()
       
    def reset(self):
        if self.project.debug.reset_cmd:
            self.gdb.command(self.project.debug.reset_cmd, callback=self.jump_to_entry_point)

    def jump_to_entry_point(self, dummy=None):
            #TODO: This is a hack, not cross-platform compatible.
            wx.CallAfter(self.frame.start_busy, "Jumping to entry point...")
            self.gdb.set("$pc", self.project.program.entry_point, self.on_at_entry_point)

    def on_at_entry_point(self, result):
        wx.CallAfter(self.frame.stop_busy)
        if result.cls == 'error':
            wx.CallAfter(self.frame.error_msg, result.msg)
        else:
            self.frame.statusbar.text = "Ready!"
            self.gdb.halt()
            self.gdb.update()
         
    def download(self):
        self.download_request = False
        if self.state == ATTACHED:
            wx.CallAfter(self.frame.start_busy_frame)
            wx.CallAfter(self.frame.start_busy, "Downloading to target...")
            if self.project.debug.pre_download_cmd:
                self.gdb.command(self.project.debug.pre_download_cmd, callback=self.download_stage_2)
            else:
                self.download_stage_2(None)
        else:
            print "Can't download from state %s" % self.state

    def download_stage_2(self, result):
        self.gdb.set_exec(self.project.absolute_path(self.project.program.target), callback=self.download_stage_3)
        
    def download_stage_3(self, result):
        if not self.project.debug.download_cmd:
            self.gdb.target_download(callback=self.on_downloaded)
        else:
            self.gdb.command(self.project.debug.download_cmd, callback=self.on_downloaded)


    def on_downloaded(self, result):
        wx.CallAfter(self.frame.stop_busy_frame)
        wx.CallAfter(self.frame.stop_busy)
        if result.cls == 'error':
            wx.CallAfter(self.frame.error_msg, result.msg)
        else:
            self.jump_to_entry_point()
            
    # ATTACH TO GDB
    def attach(self, download=False):
        self.download_request = download
        if self.state == IDLE:
            self.gdb.cmd_string = "%s -n -q -i mi" % self.project.debug.gdb_executable
            try:
                self.gdb.start()
            except Exception, e:
                self.frame.error(e)
                return
            wx.CallAfter(self.frame.start_busy, "Attaching to GDB...")
        else:
            print "Cannot attach to process from state %d" % self.state
            
    def on_attach_cmd(self, result):
        self.frame.statusbar.working = False
        self.frame.statusbar.text = ""
        if result.cls == "error":
            self.frame.error_msg(result.msg)
            self.frame.statusbar.working = False
            self.frame.statusbar.text = ""
            self.change_state(IDLE)
        else:
            self.change_state(ATTACHED)
        
    # DETACH FROM TARGET
    def detach(self):
        if self.gdb and self.gdb.attached:
            try:
                self.gdb.quit()
            except:
                pass
        self.change_state(IDLE)
    
    # GDB EVENTS
    def on_gdb_started(self, evt):
        try:
            self.gdb.command('set target-async on')
            self.frame.statusbar.text = "Attaching to target..."
            self.gdb.set_exec(self.project.absolute_path(self.project.program.target))
            self.gdb.command(self.project.debug.attach_cmd, callback=self.on_attach_cmd)
        except Exception, e:
            self.frame.error(e)
            wx.CallAfter(self.frame.stop_busy)

    def on_gdb_finished(self, evt):
        self.detach()
#        self.change_state(IDLE)
    
    def on_gdb_error(self, evt):
        self.error_logger.log(logging.ERROR, evt.data)

    def on_gdb_stack_update(self, evt):
        stack = evt.data
        frame = stack.top
        filename = os.path.normpath(frame.fullname or frame.file)
        line = frame.line
        self.stopped_at(filename, line)
        evt.Skip()

    def on_gdb_stopped(self, evt):
        self.change_state(ATTACHED)
        result = evt.data
        filename, line = None, None
        try:
            filename = os.path.normpath(result.frame.fullname)
            line = int(result.frame.line)            
        except:
            pass
        self.stopped_at(filename, line)

    def stopped_at(self, file=None, line=None):
        if not file:
            self.frame.statusbar.set_state("Halted in the weeds.", color=wx.RED)
        else:
            self.frame.statusbar.set_state("Halted at %s:%d" % (os.path.basename(file), line))
            evt = AppEvent(EVT_APP_TARGET_HALTED, self, data=(file, line))
            wx.PostEvent(self, evt)
            
            
    def on_gdb_running(self, evt):
        self.change_state(RUNNING)
        
    def on_gdb_done(self, data):
        if data.cls == 'error':
            wx.CallAfter(self.frame.error_msg, data.msg)


    #
    # BUILD
    #
    def build(self):
        self.rebuilding = False
        build_process = build.BuildProcess(self.project.build.build_cmd, notify=self, cwd=self.project.directory, target=self.project.absolute_path(self.project.program.target))
        build_process.start()
    
    def clean(self):
        self.rebuilding = False
        build_process = build.BuildProcess(self.project.build.clean_cmd, notify=self, cwd=self.project.directory)
        self.build_process = build_process
        build_process.start()

    def rebuild(self):
        self.rebuilding = True
        build_process = build.BuildProcess(self.project.build.clean_cmd, notify=self, cwd=self.project.directory)
        self.build_process = build_process
        build_process.start()

    def on_build_started(self, evt):
        #build_view = self.frame.build_view
        #self.state = BUILDING
        menu.manager.publish(menu.BUILD_STARTED)
        self.frame.statusbar.working = True
        self.frame.statusbar.text = "Performing build step..."
        self.frame.log_view.clear_build()
        self.frame.log_view.show_pane('Build')
        
    def on_build_finished(self, evt):
        if self.rebuilding:
            self.build()
        #self.state = IDLE
        self.frame.statusbar.working = False
        self.frame.statusbar.text = ""
        menu.manager.publish(menu.BUILD_FINISHED)
        wx.CallAfter(self.frame.project_view.update)

        target = evt.data
        if target:
            result = wx.ID_NO
            if self.settings.debug.load_after_build == 'prompt':
                dlg = wx.MessageDialog(self.frame, "%s Was Modified.  Reload?" % self.project.program.target, "Reload", wx.YES_NO)
                dlg.CenterOnParent()
                result = dlg.ShowModal()

            if self.settings.debug.load_after_build == 'yes' or result == wx.ID_YES:
                if self.state == IDLE:
                    self.attach(download=True)
                elif self.state == RUNNING:
                    self.halt(download=True)
                else:
                    self.download()
                    
    def on_build_update(self, evt):
        wx.CallAfter(self.frame.log_view.update_build,str(evt.data))
        evt.Skip()
