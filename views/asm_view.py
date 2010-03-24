from controls import ListControl
import view
import wx
import settings

class DisassemblyView(view.View):
    def __init__(self, *args, **kwargs):
        super(DisassemblyView, self).__init__(*args, **kwargs)
        self.list = ListControl(self)
        self.list.set_columns(['address', 'instruction'])
        self.list.SetFont(wx.Font(8, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        self.list.auto_size()
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.list, 1, wx.EXPAND)
        self.SetSizer(sizer)
        self.load_positions()

    def save_positions(self):
        cols = self.list.GetColumnCount()
        widths = [self.list.GetColumnWidth(i) for i in range(cols)]
        settings.session_set('asm_view_col_widths', widths)

    def load_positions(self):
        try:
            widths = settings.session_get('asm_view_col_widths')
            cols = self.list.GetColumnCount()
            for i in range(cols):
                self.list.SetColumnWidth(i, widths[i])
        except:
            pass

    def set_model(self, model):
        self.model = model

    def on_target_halted(self, a, b):
        self.save_positions()
        if self.model:
            self.model.data_disassemble(start_addr="$pc-8", end_addr="$pc+8", callback=self.on_disassembled_data)
         
    def update_assembly(self, instructions):
        self.list.Freeze()
        self.list.clear()
        for i, instruction in enumerate(instructions):
            addr = instruction.address
            inst = instruction.inst.replace("\\t", "\t")
            self.list.add_item((addr, inst), bgcolor=wx.Colour(255, 255, 0) if i == len(instructions)/2 else wx.WHITE)
        self.list.Thaw()
        
    def on_disassembled_data(self, dat):
        if dat.cls == 'done':
            instructions = dat['asm_insns']
            wx.CallAfter(self.update_assembly, instructions)