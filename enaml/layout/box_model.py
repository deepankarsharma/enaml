#------------------------------------------------------------------------------
#  Copyright (c) 2012, Enthought, Inc.
#  All rights reserved.
#------------------------------------------------------------------------------
from .constraint_variable import ConstraintVariable


class BoxModel(object):
    """ A class which provides a simple constraints var box model.

    Primitive Variables:
        left, top, width, height

    Derived Variables:
        right, bottom, v_center, h_center

    """
    def __init__(self, owner):
        """ Initialize a BoxModel.

        Parameters
        ----------
        owner : string
            A string which uniquely identifies the owner of this box 
            model.

        """
        owner = str(owner)
        for primitive in ('left', 'top', 'width', 'height'):
            var = ConstraintVariable(primitive, owner)
            setattr(self, primitive, var) 
        self.right = self.left + self.width
        self.bottom = self.top + self.height
        self.v_center = self.top + self.height / 2.0
        self.h_center = self.left + self.width / 2.0


class PaddingBoxModel(BoxModel):
    """ Provides ConstraintVariables describing a box with padding.

    Primitive Variables:
        padding_[left|right|top|bottom]
    
    Derived Variables:
        contents_[left|top|right|bottom|width|height|v_center|h_center]
    
    """
    def __init__(self, owner):
        super(PaddingBoxModel, self).__init__(owner)
        for primitive in ('left', 'right', 'top', 'bottom'):
            attr = 'padding_' + primitive
            var = ConstraintVariable(primitive, owner)
            setattr(self, attr, var)
        self.contents_left = self.left + self.padding_left
        self.contents_top = self.top + self.padding_top
        self.contents_right = self.right - self.padding_right
        self.contents_bottom = self.bottom - self.padding_bottom
        self.contents_width = self.contents_right - self.contents_left
        self.contents_height = self.contents_bottom - self.contents_top
        self.contents_v_center = self.contents_top + self.contents_height / 2.0
        self.contents_h_center = self.contents_left + self.contents_width / 2.0

