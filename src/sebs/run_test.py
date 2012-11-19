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

"""Runs a test.

Usage:
  run_test.py OPTIONS COMMAND

Options:
  -d DIRECTORY    Run the command in the given directory.  Should probably be
                  a relative path for -r to work correctly.
  -r REMOTE_SPEC  Run the command remotely via SSH.  REMOTE_SPEC takes the form
                  USER@HOST:PATH.  The "USER@HOST" part is passed to ssh
                  verbatim ("USER@" may be omitted) to specify the remote
                  host.  PATH is the absolute path on that host which
                  corresponds to the current directory (the directory in which
                  run_test.py is executing, NOT the directory given by -d).
"""

import getopt
import os
import pipes
import sys

class UsageError(Exception):
  pass

def main(argv):
  try:
    opts, args = getopt.getopt(sys.argv[1:], "d:r:h", ["--help"])
  except getopt.error, message:
    raise UsageError(message)

  directory = None
  remote_spec = None

  for name, value in opts:
    if name in ("-h", "--help"):
      print __doc__
      return 0
    elif name == "-d":
      directory = value
    elif name == "-r":
      remote_spec = value

  # TODO(kenton):  Fix PYTHONPATH so it doesn't contain the test runner par
  #   file (or maybe make single-file Python binaries not use a par).

  if remote_spec is None:
    executable = args[0]
    if executable.find("/") >= 0:
      executable = os.path.join(os.getcwd(), executable)
    if directory is not None:
      os.chdir(directory)
    print executable, args
    os.execvp(executable, args)

  else:
    host, remote_dir = remote_spec.split(":", 1)

    if args[0].find("/") >= 0:
      args[0] = os.path.join(remote_dir, args[0])

    quoted_command = " ".join([pipes.quote(arg) for arg in args])

    if directory is not None:
      remote_dir = os.path.join(remote_dir, directory)

    cd_prefix = "cd %s && " % pipes.quote(remote_dir)
    quoted_command = cd_prefix + quoted_command

    print ["ssh", host, quoted_command]
    os.execvp("ssh", ["ssh", host, quoted_command])

if __name__ == "__main__":
  try:
    sys.exit(main(sys.argv))
  except UsageError, error:
    print >>sys.stderr, error.message
    print >>sys.stderr, "for help use --help"
    sys.exit(2)
