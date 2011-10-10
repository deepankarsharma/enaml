#-----------------------------------------------------------------------------
#  Copyright (c) 2011, Enthought, Inc.
#  All rights reserved.
#------------------------------------------------------------------------------
def test_collector():
    """ Discover and collect tests for the Enaml Package.

        .. note :: addapted from the unittest2
    """
    import os
    import sys
    from unittest import TestLoader

    # import __main__ triggers code re-execution
    __main__ = sys.modules['__main__']
    setupDir = os.path.abspath(os.path.dirname(__main__.__file__))

    return TestLoader().discover(setupDir)
