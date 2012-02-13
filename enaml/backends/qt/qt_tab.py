#------------------------------------------------------------------------------
#  Copyright (c) 2011, Enthought, Inc.
#  All rights reserved.
#------------------------------------------------------------------------------
from .qt_container import QtContainer

from ...components.tab import AbstractTkTab


class QtTab(QtContainer, AbstractTkTab):
    """ A Qt implementation of the Tab component.
    
    """
    #--------------------------------------------------------------------------
    # Setup Methods 
    #--------------------------------------------------------------------------
    def initialize(self):
        """ Initialize the attributes of the tab.

        """
        super(QtTab, self).initialize()
        shell = self.shell_obj
        self.set_title(shell.title)
        self.set_icon(shell.icon)

    #--------------------------------------------------------------------------
    # Implementation
    #--------------------------------------------------------------------------
    def shell_title_changed(self, title):
        """ The change handler for the 'title' attribute on the shell 
        object.

        """
        self.set_title(title)
    
    def shell_icon_changed(self, icon):
        """ The change handler for the 'icon' attribute on the shell
        object.

        """
        self.set_icon(icon)
    
    #--------------------------------------------------------------------------
    # Widget Update Methods 
    #--------------------------------------------------------------------------
    def set_title(self, title):
        """ Sets the title of this tab in the parent tab widget.

        """
        # We use got through the shell's parent object to get at the
        # tab widget for two reasons: 1) The TabWidget maintains an 
        # internal QStackedWidget control which is actually the parent 
        # of the tab, and 2) If the Tab was generated by an include
        # then the parents end up in a transitory state where logic
        # can break down. Accessing the tab widget through the parent
        # shell is therefore the safest option.
        widget = self.widget
        tab_widget = self.shell_obj.parent.toolkit_widget
        idx = tab_widget.indexOf(widget)
        if idx != -1:
            tab_widget.setTabText(idx, title)
     
    def set_icon(self, icon):
        """ Sets the icon of this tab in the parent tab widget.

        """
        # XXX handle icons
        pass

