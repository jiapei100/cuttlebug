import wx
import wx.lib.customtreectrl as ct
HIT_TEXT = 1
HIT_BUTTON = 2
HIT_ICON = 3

CT_DEFAULT_STYLE = 0
CT_FULL_ROW_HIGHLIGHT = 1

def get_default_buttons():
    plus = wx.Bitmap('plus.png')
    minus = wx.Bitmap('minus.png')
    return plus, minus

class CuttleTreeItem(object):
    def __init__(self,name):
        self.name = name
        self.children = []
        self.expanded = False
        self.level = 0
        self.full_extents = (0,0,0,0)
        self.text_extents = (0,0,0,0)
        self.button_extents = (0,0,0,0)
        self.icon = None

    def Expand(self):
        if self.children:
            self.expanded = True

    def Collapse(self):
        self.expanded = False

    def Toggle(self):
        if self.expanded:
            self.Collapse()
        else:
            self.Expand()

    def AppendItem(self, item):
        self.children.append(item)
    
class CuttleTreeCtrl(wx.Control):
    
    def __init__(self, parent, id=wx.ID_ANY, style=CT_DEFAULT_STYLE):
        wx.Control.__init__(self, parent, id)
        self.style = style
        self.plus, self.minus = get_default_buttons()
        self.__x_margin = 2
        self.__y_margin = 2
        self.__indent = 8
        self.Clear()
        self.SetBackgroundColour(wx.WHITE)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_LEFT_DCLICK, self.on_left_dclick)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)

    def on_left_dclick(self, evt):
        pt = evt.GetPosition()
        flag, item = self.hit_test(pt)
        if item and flag == HIT_TEXT:
            self.Toggle(item)

    def on_left_down(self, evt):
        pt = evt.GetPosition()
        flag, item = self.hit_test(pt)
        if item:
            if flag == HIT_BUTTON:
                self.Toggle(item)
            else:
                self.__selected_item = item
                self.Refresh()
                print "Tree item %s clicked!" % item.name

    def AppendItem(self, parent, name):
        item = CuttleTreeItem(name)
        item.level = parent.level + 1
        parent.AppendItem(item)
        self.Refresh()
        return item
    
    def Collapse(self, item):
        item.Collapse()
        self.Refresh()
        return item

    def Expand(self, item):
        item.Expand()
        self.Refresh()
        return item
    
    def Toggle(self, item):
        item.Toggle()
        self.Refresh()
        return item

    def __walk_expanded(self, root=None):
        if not root: root = self.__root
        if root:
            yield root
            if root.expanded:
                for item in root.children:
                    for child in self.__walk_expanded(item): yield child
    def Clear(self):
        self.__root = None
        self.__custom_item_fonts = {}
        self.__shown_items = set()
        self.__selected_item = None
    
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        self.Draw(dc)
        
    def __draw_item(self, dc, item, x, y):
        BUTTON_MARGIN = 4
        TEXT_MARGIN = 2
        dcwidth, dcheight = self.GetClientSize()
        tw,th = dc.GetTextExtent(item.name)
        bw,bh = self.plus.GetSize()

        height = max(th+2*TEXT_MARGIN, bh+2*BUTTON_MARGIN)
        width = bw + 2*BUTTON_MARGIN + tw

        button_x = x+BUTTON_MARGIN
        button_y = y+(height/2) - (bh/2)

        if item == self.__selected_item:
            dc.SetBrush(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)))
            if self.style & CT_FULL_ROW_HIGHLIGHT:
                dc.DrawRectangle(self.__x_margin, y, dcwidth-(self.__x_margin*2), height)
            else:
                dc.DrawRectangle(x,y,width+TEXT_MARGIN,height)

        if item.expanded:
            dc.DrawBitmap(self.minus, button_x,button_y)
        else:
            if item.children:
                dc.DrawBitmap(self.plus, button_x,button_y)

        text_x = x+(2*BUTTON_MARGIN) + bw
        text_y = y+(height/2) - (th/2)

        dc.DrawText(item.name, text_x,text_y)
        button_extents = (button_x,button_y,button_x+bw, button_y+bh) if item.children else (0,0,0,0)
        text_extents = (text_x,text_y,text_x+tw, text_y+th)
        full_extents = (x,y,x+width,y+height)
        return full_extents, text_extents, button_extents

    
    def Draw(self, dc):
        width, height = self.GetClientSize()
        if not width or not height: return
        backColour = self.GetBackgroundColour()
        backBrush = wx.Brush(backColour, wx.SOLID)
        dc.SetBackground(backBrush)
        dc.Clear()
        x,y = self.__x_margin, self.__y_margin
        item_y = y
        self.__shown_items = set()
        dc.SetFont(self.GetFont())
        for item in self.__walk_expanded():
            item_x = x + self.__indent*item.level
            item.full_extents, item.text_extents, item.button_extents = self.__draw_item(dc, item, item_x, item_y)
            self.__shown_items.add(item)
            item_y += item.full_extents[3]-item.full_extents[1]
            
    def hit(self, point, extents):
        return point[0] >= extents[0] and point[0] <= extents[2] and point[1] >= extents[1] and point[1] <= extents[3]
    
    def hit_test(self, pt):
        for item in self.__shown_items:
            if self.hit(pt, item.full_extents):
                if self.hit(pt, item.text_extents):
                    return (HIT_TEXT, item)
                elif self.hit(pt, item.button_extents):
                    return (HIT_BUTTON, item)

        return (0, None)

    def OnEraseBackground(self, evt):
        pass
    
    def AddRoot(self, name, ctrl=None):
        if self.__root:
            raise Exception("CuttleTreeCtrl can only have one root item")
        else:
            self.__root = CuttleTreeItem(name)
            return self.__root

if __name__ == "__main__":
    app = wx.PySimpleApp()    
    frame = wx.Frame(None)
    tree = CuttleTreeCtrl(frame, style=CT_FULL_ROW_HIGHLIGHT)
    root = tree.AddRoot("Root item")
    tree.Expand(root)
    for x in range(4):
        item = tree.AppendItem(root, "Item %d" % x)
        for y in range(3):
            tree.AppendItem(item, "Subitem %d" % y)
    frame.Show()
    app.MainLoop()
