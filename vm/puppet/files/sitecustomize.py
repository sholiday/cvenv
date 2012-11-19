# install the apport exception handler if available
try:
    import apport_python_hook
except ImportError:
    pass
else:
    apport_python_hook.install()

# Include site-packages, used by Thrift
import sys
sys.path.append('/usr/lib/python2.7/site-packages')