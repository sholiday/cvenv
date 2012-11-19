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
import os
import shutil

from sebs.filesystem import DiskDirectory, VirtualDirectory, MappedDirectory
from sebs.helpers import typecheck

class _WorkingDirMapping(MappedDirectory.Mapping):
  """Sometimes we want to put all build output (including intermediates) in
  a different directory, e.g. when cross-compiling.  We also want to put the
  "mem" subdirectory into a VirtualDirectory.  This class implements a
  mapping which can be used with MappedDirectory to accomplish these things."""

  def __init__(self, source_dir, output_dir, mem_dir, env_dir, alt_configs):
    super(_WorkingDirMapping, self).__init__()
    self.__source_dir = source_dir
    self.__output_dir = output_dir
    self.__mem_dir = mem_dir
    self.__env_dir = env_dir
    self.__alt_configs = alt_configs

    if env_dir.exists("$config"):
      self.__configured_env = set(env_dir.read("$config").split(","))
    else:
      self.__configured_env = set()

  def map(self, filename):
    # Note:  We intentionally consider any directory name starting with "src"
    #   (including, e.g., "src-unofficial") as a source directory.
    if filename.startswith("src"):
      return (self.__source_dir, filename)
    elif filename.startswith("mem/"):
      return (self.__mem_dir, filename[4:])
    elif filename.startswith("env/"):
      env_name = filename[4:]
      self.__update_env(env_name)
      return (self.__env_dir, env_name)
    elif filename.startswith("alt/"):
      parts = filename[4:].split("/", 1)
      config = self.__alt_configs.get(parts[0])
      if len(parts) > 1 and config is not None:
        return (config.root_dir, parts[1])
      else:
        return (self.__output_dir, filename)
    else:
      return (self.__output_dir, filename)

  def __update_env(self, filename):
    """Every time an environment variable is accessed we check to see if it has
    changed."""

    if filename.startswith("set/"):
      env_name = filename[4:]
    else:
      env_name = filename

    # We only update from the environment for variables that were not explicitly
    # configured.
    if env_name not in self.__configured_env:
      if filename.startswith("set/"):
        if env_name in os.environ:
          value = "true"
        else:
          value = "false"
      else:
        value = os.environ.get(env_name, "")

      if not self.__env_dir.exists(filename) or \
         self.__env_dir.read(filename) != value:
        # Value has changed.  Update.
        self.__env_dir.write(filename, value)

def _restore_pickle(obj, dir, filename):
  if dir is not None:
    filename = dir.get_disk_path(filename)
  if os.path.exists(filename):
    db = open(filename, "rb")
    obj.restore(cPickle.load(db))
    db.close()

def _save_pickle(obj, dir, filename):
  if dir is not None:
    filename = dir.get_disk_path(filename)
  db = open(filename, "wb")
  cPickle.dump(obj.save(), db, cPickle.HIGHEST_PROTOCOL)
  db.close()

class Configuration(object):
  def __init__(self, output_path, all_configs = None):
    # We want to make sure to construct only one copy of each config, even
    # if configs refer to each other or multiple configs refer to a shared
    # config.  So, all_configs maps names to configs that we have already
    # constructed.
    if all_configs is None:
      # Note that if we just make all_configs default to {} in the method
      # signature, then Python will create a single empty map to use as the
      # default value for all calls rather than create a new one every call.
      # Since we modify all_configs during this method, we would be modifying
      # the shared default value, which would be bad.  If you don't understand
      # what I mean, try typing the following into the interpreter and then
      # calling it several times with no argument:
      #   def f(l = []):
      #     l.append("foo")
      #     return l
      # Ouchies.
      all_configs = {}
    if output_path is None:
      all_configs[""] = self
    else:
      all_configs[output_path] = self

    self.name = output_path
    self.source_dir = DiskDirectory(".")
    if output_path is None:
      self.output_dir = self.source_dir
    else:
      self.source_dir.mkdir(output_path)
      self.output_dir = DiskDirectory(output_path)
    self.mem_dir = VirtualDirectory()
    self.env_dir = VirtualDirectory()
    _restore_pickle(self.mem_dir, self.output_dir, "mem.pickle")
    _restore_pickle(self.env_dir, self.output_dir, "env.pickle")
    self.alt_configs = {}
    self.__make_root_dir()

    self.alt_configs["host"] = self

    if self.env_dir.exists("$mappings"):
      mappings = self.env_dir.read("$mappings").split(":")
      for mapping in mappings:
        if mapping == "":
          continue
        alias, name = mapping.split("=", 1)
        if name in all_configs:
          self.alt_configs[alias] = all_configs[name]
        else:
          if name == "":
            name = None
          self.alt_configs[alias] = Configuration(name, all_configs)

  def __make_root_dir(self):
    self.mapping = _WorkingDirMapping(self.source_dir, self.output_dir,
                                      self.mem_dir, self.env_dir,
                                      self.alt_configs)
    self.root_dir = MappedDirectory(self.mapping)

  def save(self):
    if not self.mem_dir.empty():
      _save_pickle(self.mem_dir, self.root_dir, "mem.pickle")
    if not self.env_dir.empty():
      _save_pickle(self.env_dir, self.root_dir, "env.pickle")

  def getenv(self, name):
    if self.root_dir.read("env/set/" + name) == "true":
      return self.root_dir.read("env/" + name)
    else:
      return None

  def clean(self, expunge=False):
    for dir in ["tmp", "bin", "lib", "share", "include", "mem", "env"]:
      if self.root_dir.exists(dir):
        shutil.rmtree(self.root_dir.get_disk_path(dir))

    for file in [ "mem.pickle", "env.pickle" ]:
      if self.root_dir.exists(file):
        os.remove(self.root_dir.get_disk_path(file))

    self.mem_dir = VirtualDirectory()

    if expunge:
      # Try to remove the output directory itself -- will fail if not empty.
      outdir = self.root_dir.get_disk_path(".")
      if outdir.endswith("/."):
        # rmdir doesn't like a trailing "/.".
        outdir = outdir[:-2]
      try:
        os.rmdir(outdir)
      except os.error:
        pass
    else:
      # Restore the parts of env.pickle that were set explicitly.
      new_env_dir = VirtualDirectory()

      if self.env_dir.exists("$mappings"):
        new_env_dir.write("$mappings", self.env_dir.read("$mappings"))
      if self.env_dir.exists("$config"):
        locked_vars = self.env_dir.read("$config")
        new_env_dir.write("$config", locked_vars)

        for var in locked_vars.split(","):
          if var != "":
            new_env_dir.write(var, self.env_dir.read(var))
            new_env_dir.write("set/" + var,
              self.env_dir.read("set/" + var))

      self.env_dir = new_env_dir

    self.__make_root_dir()

  def get_all_linked_configs(self):
    result = set()
    self.__get_all_linked_configs_recursive(result)
    return result

  def __get_all_linked_configs_recursive(self, result):
    if self in result:
      return

    result.add(self)
    for link in self.alt_configs.values():
      link.__get_all_linked_configs_recursive(result)
