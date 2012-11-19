# Read more about puppet here:
# http://docs.puppetlabs.com/guides/language_guide.html

notice("Running configure scripts,
this make take a long time for the first boot...")

import "common.pp"
include users
include development