#------------------------------------------------------------------------------
#  Copyright (c) 2011, Enthought, Inc.
#  All rights reserved.
#------------------------------------------------------------------------------
import wx

from .wx_base_component import WXBaseComponent
from ..component import AbstractTkComponent

class WXComponent(WXBaseComponent, AbstractTkComponent):
    """ A wxPython implementation of Component.

    A WXComponent is not meant to be used directly. It provides some
    common functionality that is useful to all widgets and should
    serve as the base class for all other classes.

    .. note:: This is not a HasTraits class.

    """
    #: The WX widget created by the component
    widget = None

    #--------------------------------------------------------------------------
    # Setup Methods
    #--------------------------------------------------------------------------
    def create(self):
        style = wx.NO_BORDER
        self.widget = wx.Window(self.parent_widget(), style=style)

    def bind(self):
        super(WXComponent, self).bind()

    #--------------------------------------------------------------------------
    # Implementation
    #--------------------------------------------------------------------------
    @property
    def toolkit_widget(self):
        """ A property that returns the toolkit specific widget for this
        component.

        """
        return self.widget

    def size(self):
        """ Return the size of the internal toolkit widget as a
        (width, height) tuple of integers.

        """
        widget = self.widget
        return widget.GetSizeTuple()

    def size_hint(self):
        """ Returns a (width, height) tuple of integers which represent
        the suggested size of the widget for its current state. This
        value is used by the layout manager to determine how much
        space to allocate the widget.

        """
        widget = self.widget
        size_hint = widget.GetBestSize()
        return (size_hint.width, size_hint.height)

    def resize(self, width, height):
        """ Resizes the internal toolkit widget according the given
        width and height integers.

        """
        widget = self.widget
        new_size = wx.Size(width, height)
        widget.SetSize(new_size)

    def set_min_size(self, min_width, min_height):
        """ Set the hard minimum width and height of the widget. A widget
        will not be able to be resized smaller than this value.

        """
        widget = self.widget
        widget.SetSizeHints(min_width, min_height)

    def pos(self):
        """ Returns the position of the internal toolkit widget as an
        (x, y) tuple of integers. The coordinates should be relative to
        the origin of the widget's parent.

        """
        widget = self.widget
        return widget.GetPositionTuple()

    def move(self, x, y):
        """ Moves the internal toolkit widget according to the given
        x and y integers which are relative to the origin of the
        widget's parent.

        """
        widget = self.widget
        widget.MoveXY(x, y)

    def geometry(self):
        """ Returns an (x, y, width, height) tuple of geometry info
        for the internal toolkit widget. The semantic meaning of the
        values are the same as for the 'size' and 'pos' methods.

        """
        widget = self.widget
        rectangle = widget.GetRect()
        return rectangle.asTuple()

    def set_geometry(self, x, y, width, height):
        """ Sets the geometry of the internal widget to the given
        x, y, width, and height values. The semantic meaning of the
        values is the same as for the 'resize' and 'move' methods.

        """
        widget = self.widget
        widget.SetDimensions(x, y, width, height)

    def on_resize(self, event):
        """ Triggers a relayout of the shell object since the component
        has been resized.

        """
        shell = self.shell_obj
        shell.do_layout()

    def parent_widget(self):
        """ Returns the logical wx.Window parent for this component.

        Since some parents may wrap non-Window objects (like sizers),
        this method will walk up the tree of parent components until a
        wx.Window is found or None if no wx.Window is found.

        Returns
        -------
        result : wx.Window or None

        """
        # FIXME: is this still necessary?
        shell_parent = self.shell_obj.parent
        while shell_parent:
            widget = shell_parent.toolkit_widget
            if isinstance(widget, wx.Window):
                return widget
            shell_parent = shell_parent.parent

    def child_widgets(self):
        """ Iterates over the parent's children and yields the
        toolkit widgets for those children.

        """
        shell = self.shell_obj
        for child in shell.children:
            yield child.toolkit_widget
