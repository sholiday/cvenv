#! /usr/bin/python
# Scalable Extendable Build System
# Copyright (c) 2009 Kenton Varda and contributors.  All rights reserved.
# Portions copyright Google, Inc.
# http://code.google.com/p/sebs
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of the SEBS project nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Constructs a par file from a set of Python sources.

Usage:
  make_py_binary.py -m MAIN_MODULE -o PARFILE [-p PYTHONPATH] SOURCE_FILES
"""

import getopt
import os
import stat
import sys
import tempfile
import zipfile

class UsageError(Exception):
  pass

def main(argv):
  try:
    opts, args = getopt.getopt(sys.argv[1:], "hm:o:p:", ["--help"])
  except getopt.error, message:
    raise UsageError(message)

  main_module = None
  output = None
  path = []

  for name, value in opts:
    if name in ("-h", "--help"):
      print __doc__
      return 0
    elif name == "-m":
      main_module = value
    elif name == "-o":
      output = value
    elif name == "-p":
      path.extend(value.split(":"))

  if main_module is None:
    raise UsageError("Missing required flag -m.")
  if output is None:
    raise UsageError("Missing required flag -o.")

  temporary = tempfile.NamedTemporaryFile()
  tempname = temporary.name
  temporary.close()

  zip = zipfile.ZipFile(tempname, "w")

  for file in args:
    arcname = file
    for dir in path:
      if file.startswith(dir + "/"):
        arcname = file[(len(dir) + 1):]
        break
    zip.write(file, arcname)

  zip.close()

  fd = os.open(output, os.O_WRONLY | os.O_TRUNC | os.O_CREAT, 0777)
  file = os.fdopen(fd, "w")

  file.write(
      "#! /bin/sh\n"
      "PYTHONPATH=`which $0`:\"$PYTHONPATH\" python -m %s \"$@\" || exit 1\n"
      "exit 0\n" % main_module)

  temporary = open(tempname, "rb")
  file.write(temporary.read())
  temporary.close()
  os.remove(tempname)

  file.close()

if __name__ == "__main__":
  try:
    sys.exit(main(sys.argv))
  except UsageError, error:
    print >>sys.stderr, error.message
    print >>sys.stderr, "for help use --help"
    sys.exit(2)
