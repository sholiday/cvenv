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

# TODO(kenton):
#
# Commands:
#   build:  Builds targets and dependencies.
#   test:  Builds test rules and executes them.
#   configure:  Lock-in a set of environment variables that will be used in
#     subsequent builds.  Should support setting names for different
#     configurations.
#   script:  Like build, but generates a script containing the actions instead
#     of actually building.  Scripts may be in multiple formats, including
#     Unix shell, Windows batch file, or configure/Makefile pair.
#   placeholders:  Builds a package then constructs "placeholder" sebs files
#     that work as drop-in replacements except that they assume that everything
#     is already built and installed.  Useful for distributing dependents
#     without the dependencies.
#   dist:  Makes a distribution containing some set of directories.
#     Dependencies not in that set are replaced with placeholders.  Build
#     scripts are optionally included.
#   install:  Installs some targets.  Can recursively install dependencies or
#     assume they are already installed.
#   uninstall:  Reverse of install.
#   clean:  Clean some or all of the output from previous SEBS builds.
#   help:  Display help.
#
# ActionRunner that skips actions when the inputs and commands haven't changed.
#
# Background server that accepts commands and doesn't have to reload sebs files.

import cPickle
import getopt
import os
import sys
import threading

from sebs.builder import Builder
from sebs.configuration import Configuration
from sebs.core import Rule, Test
from sebs.helpers import typecheck
from sebs.loader import Loader, BuildFile
from sebs.console import make_console, ColoredText
from sebs.runner import SubprocessRunner, CachingRunner
from sebs.script import ScriptBuilder

class UsageError(Exception):
  pass

def _args_to_rules(loader, args):
  """Given a list of command-line arguments like 'foo/bar.sebs:baz', return an
  iterator of rules which should be built."""

  typecheck(args, list, basestring)

  for arg in args:
    if arg.startswith("src/") or arg.startswith("src\\"):
      # For ease of use, we allow files to start with "src/", so tab completion
      # can be used.
      arg = arg[4:]
    elif arg.startswith("//"):
      # We also allow files to start with "//" which mimics to the syntax given
      # to sebs.import_.
      arg = arg[2:]
    print arg
    target = loader.load(arg)

    if isinstance(target, BuildFile):
      for name, value in target.__dict__.items():
        if isinstance(value, Rule):
          yield value
    elif not isinstance(target, Rule):
      raise UsageError("%s: Does not name a rule." % arg)
    else:
      yield target

def _restore_pickle(obj, filename):
  if os.path.exists(filename):
    db = open(filename, "rb")
    obj.restore(cPickle.load(db))
    db.close()

def _save_pickle(obj, filename):
  db = open(filename, "wb")
  cPickle.dump(obj.save(), db, cPickle.HIGHEST_PROTOCOL)
  db.close()

# ====================================================================

def configure(config, argv):
  try:
    opts, args = getopt.getopt(argv[1:], "C:o", [])
  except getopt.error, message:
    raise UsageError(message)

  output = False
  mappings = {}
  for name, value in opts:
    if name == "-C":
      parts = value.split("=", 1)
      if len(parts) == 1:
        mappings[parts[0]] = parts[0]
      else:
        mappings[parts[0]] = parts[1]
    elif name == "-o":
      output = True

  if output:
    if config.env_dir.exists("$mappings"):
      mappings = config.env_dir.read("$mappings").split(":")
      for mapping in mappings:
        if mapping == "":
          continue
        print "-C" + mapping

    if config.env_dir.exists("$config"):
      locked_vars = config.env_dir.read("$config").split(",")
    else:
      locked_vars = []

    for var in locked_vars:
      if var == "":
        pass
      elif config.env_dir.read("set/" + var) == "true":
        print "%s=%s" % (var, config.env_dir.read(var))
      else:
        print var + "-"

  else:
    locked_vars = []

    for arg in args:
      parts = arg.split("=", 1)
      name = parts[0]

      unset = len(parts) == 1 and name.endswith("-")
      if unset:
        name = name[:-1]

      if not name.replace("_", "").isalnum():
        raise UsageError("%s: Invalid environment variable name." % name)

      if len(parts) == 2:
        value = parts[1]
        is_set = "true"
      elif name in os.environ and not unset:
        value = os.environ[name]
        is_set = "true"
      else:
        value = ""
        is_set = "false"
      config.env_dir.write(name, value)
      config.env_dir.write("set/" + name, is_set)

      locked_vars.append(name)

    config.env_dir.write("$config", ",".join(locked_vars))

    config.env_dir.write("$mappings",
        ":".join(["=".join(mapping) for mapping in mappings.items()]))

# --------------------------------------------------------------------

def build(config, argv):
  try:
    opts, args = getopt.getopt(argv[1:], "vj:", [])
  except getopt.error, message:
    raise UsageError(message)

  runner = None
  caching_runner = None
  verbose = False
  console = make_console(sys.stdout)
  threads = 1

  for name, value in opts:
    if name == "-v":
      verbose = True
    elif name == "-j":
      threads = int(value)

  if runner is None:
    runner = SubprocessRunner(console, verbose)
    caching_runner = CachingRunner(runner, console)
    runner = caching_runner

    # Note that all configurations share a common cache.pickle.
    _restore_pickle(caching_runner, "cache.pickle")

  loader = Loader(config.root_dir)
  builder = Builder(console)

  if argv[0] == "test":
    for rule in _args_to_rules(loader, args):
      if isinstance(rule, Test):
        builder.add_test(config, rule)
  else:
    # caihsiaoster: Support ":all" to build all targets in the sebs
    prefix = args[0].split(":", 1)
    new_args = args
    if prefix[-1] == 'all':
      new_args = []
      for arg in args:
        if arg.startswith("src/") or arg.startswith("src\\"):
          arg = arg[4:]
        elif arg.startswith("//"):
          arg = arg[2:]
        parts = arg.rsplit(":", 1)
        (file, context) = loader.load_file(parts[0])
        for key in file.__dict__.copy():
          new_args.append(str(prefix[0]) + ':' + key)

    #for rule in _args_to_rules(loader, args):
    for rule in _args_to_rules(loader, new_args):
      builder.add_rule(config, rule)

  thread_objects = []
  success = True
  for i in range(0, threads):
    thread_objects.append(
      threading.Thread(target = builder.build, args = [runner]))
    thread_objects[-1].start()
  try:
    for thread in thread_objects:
      thread.join()
  except KeyboardInterrupt:
    if not builder.failed:
      console.write(ColoredText(ColoredText.RED, "INTERRUPTED"))
      builder.failed = True
    for thread in thread_objects:
      thread.join()
  finally:
    _save_pickle(caching_runner, "cache.pickle")

  if builder.failed:
    return 1

  if argv[0] == "test":
    if not builder.print_test_results():
      return 1

  return 0

# --------------------------------------------------------------------

def script(config, argv):
  try:
    opts, args = getopt.getopt(argv[1:], "o:", [])
  except getopt.error, message:
    raise UsageError(message)

  filename = None

  for name, value in opts:
    if name == "-o":
      filename = value

  loader = Loader(config.root_dir)
  builder = ScriptBuilder()

  for rule in _args_to_rules(loader, args):
    if isinstance(rule, Test):
      builder.add_test(rule)
    else:
      builder.add_rule(rule)

  if filename is None:
    out = sys.stdout
  else:
    # Binary mode => Write unix-style newlines regardless of host OS.
    out = open(filename, "wb")

  builder.write(out)

  if filename is not None:
    out.close()
    mask = os.umask(0)
    os.umask(mask)
    os.chmod(filename, 0777 & ~mask)

# --------------------------------------------------------------------

def clean(config, argv):
  try:
    opts, args = getopt.getopt(argv[1:], "", ["expunge"])
  except getopt.error, message:
    raise UsageError(message)

  expunge = False

  for name, value in opts:
    if name == "--expunge":
      expunge = True

  # All configurations share one cache.  It's *probably* harmless to leave it
  # untouched, but then again if the implementation was perfect then "clean"
  # would never be necessary.  So we nuke it.
  # TODO(kenton):  We could load the cache and remove only the entries that
  #   are specific to the configs being cleaned.
  if os.path.exists("cache.pickle"):
    os.remove("cache.pickle")

  for linked_config in config.get_all_linked_configs():
    if linked_config.name is None:
      print "Cleaning default config."
    else:
      print "Cleaning:", linked_config.name

    linked_config.clean(expunge = expunge)

# ====================================================================

def main(argv):
  try:
    opts, args = getopt.getopt(argv[1:], "hc:", ["help", "config="])
  except getopt.error, message:
    raise UsageError(message)

  output_path = None

  for name, value in opts:
    if name in ("-h", "--help"):
      print __doc__
      return 0
    elif name in ("-c", "--config"):
      output_path = value

  config = Configuration(output_path)

  if len(args) == 0:
    raise UsageError("Missing command.")

  try:
    if args[0] in ("build", "test"):
      return build(config, args)
    elif args[0] == "configure":
      return configure(config, args)
    elif args[0] == "script":
      return script(config, args)
    elif args[0] == "clean":
      return clean(config, args)
    else:
      raise UsageError("Unknown command: %s" % args[0])
  finally:
    for linked_config in config.get_all_linked_configs():
      linked_config.save()

if __name__ == "__main__":
  try:
    sys.exit(main(sys.argv))
  except UsageError, error:
    print >>sys.stderr, error.message
    print >>sys.stderr, "for help use --help"
    sys.exit(2)
