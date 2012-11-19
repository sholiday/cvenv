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

import os

from sebs.core import Rule, Test, Artifact, Action, Context, DefinitionError, \
                      ArgumentSpec
from sebs.filesystem import Directory
from sebs.helpers import typecheck
import sebs.command as command

class _ContextImpl(Context):
  def __init__(self, loader, filename, root_dir):
    typecheck(loader, Loader)
    typecheck(filename, basestring)

    self.__loader = loader
    self.filename = filename
    self.full_filename = os.path.join("src", filename)
    self.directory = os.path.dirname(filename)
    self.timestamp = root_dir.getmtime(self.full_filename)
    self.__root_dir = root_dir

  def local_filename(self, artifact):
    if isinstance(artifact, str):
      return artifact
    typecheck(artifact, Artifact)

    parts = artifact.filename.split("/")
    if parts[0] not in ["src", "tmp", "mem"]:
      return None

    parts = parts[1:]
    dir_parts = self.directory.split("/")
    if len(parts) < len(dir_parts) or parts[:len(dir_parts)] != dir_parts:
      return None
    return "/".join(parts[len(dir_parts):])

  def source_artifact(self, filename):
    if isinstance(filename, Artifact):
      return filename
    self.__validate_artifact_name(filename)

    return self.__loader.source_artifact(
      os.path.join("src", self.directory, filename))

  def source_artifact_list(self, filenames):
    typecheck(filenames, list)

    result = []
    for filename in filenames:
      if isinstance(filename, Artifact):
        result.append(filename)
      else:
        self.__validate_artifact_name(filename)
        full_name = os.path.join("src", self.directory, filename)
        had_match = False
        for filename in self.__root_dir.expand_glob(full_name):
          result.append(self.__loader.source_artifact(filename))
          had_match = True
        if not had_match:
          result.append(self.__loader.source_artifact(full_name))

    return result

  def environment_artifact(self, env_name):
    self.__validate_env_name(env_name)

    return self.__loader.source_artifact(
      os.path.join("env", env_name))

  def environment_set_artifact(self, env_name):
    self.__validate_env_name(env_name)

    return self.__loader.source_artifact(
      os.path.join("env/set", env_name))

  def intermediate_artifact(self, filename, action, configured_name=None):
    self.__validate_artifact_name(filename, configured_name)
    typecheck(action, Action)

    if configured_name is not None:
      configured_name = ["tmp/%s/" % self.directory] + configured_name

    return self.__loader.derived_artifact(
      os.path.join("tmp", self.directory, filename), action,
      configured_name = configured_name)

  def memory_artifact(self, filename, action):
    self.__validate_artifact_name(filename)
    typecheck(action, Action)

    return self.__loader.derived_artifact(
      os.path.join("mem", self.directory, filename), action)

  def output_artifact(self, directory, filename, action, configured_name=None):
    typecheck(directory, basestring)
    self.__validate_artifact_name(filename, configured_name)
    typecheck(action, Action)

    if directory not in ("bin", "include", "lib", "share"):
      raise DefinitionError(
        "'%s' is not a valid output directory." % directory)

    if configured_name is not None:
      # caihsiaoster: use tree structure for binary
      configured_name = [directory + "/" + self.directory + "/"] + configured_name
#      configured_name = [directory + "/"] + configured_name

    return self.__loader.derived_artifact(
      # caihsiaoster: use tree structure for library
      os.path.join(directory, self.directory, filename), action,
      configured_name = configured_name)
#      os.path.join(directory, filename), action,
#      configured_name = configured_name)

  def configured_artifact(self, artifact, configuration):
    typecheck(artifact, Artifact)
    typecheck(configuration, basestring)
    return Artifact(os.path.join("alt", configuration, artifact.filename),
                    alt_artifact = artifact, alt_config = configuration);

  def action(self, *vargs, **kwargs):
    return Action(*vargs, **kwargs)

  def __validate_artifact_name(self, filename, configured_name=None):
    typecheck(filename, basestring)
    normalized = os.path.normpath(filename).replace("\\", "/")
    if filename != normalized:
      raise DefinitionError(
        "File '%s' is not a normalized path name.  Please use '%s' "
        "instead." % (filename, normalized))

    if filename.startswith("../") or filename.startswith("/"):
      raise DefinitionError(
        "File '%s' points outside the surrounding directory.  To "
        "include a file from another directory, that directory must explicitly "
        "export it." % filename)

    # TODO(kenton):  Some sort of validation of configured_name.

  def __validate_env_name(self, name):
    typecheck(name, basestring)
    if not name.replace("_", "").isalnum():
      raise DefinitionError(
        "'%s' is not a valid environment  variable name" % name)

class BuildFile(object):
  def __init__(self, vars):
    self.__dict__.update(vars)

class _Builtins(object):
  def __init__(self, loader, context):
    typecheck(loader, Loader)
    typecheck(context, _ContextImpl)
    self.Rule = Rule
    self.Test = Test
    self.ArgumentSpec = ArgumentSpec
    self.Artifact = Artifact
    self.Action = Action
    self.DefinitionError = DefinitionError
    self.typecheck = typecheck

    self.Command            = command.Command
    self.EchoCommand        = command.EchoCommand
    self.EnvironmentCommand = command.EnvironmentCommand
    self.DoAllCommand       = command.DoAllCommand
    self.ConditionalCommand = command.ConditionalCommand
    self.SubprocessCommand  = command.SubprocessCommand
    self.DepFileCommand     = command.DepFileCommand
    self.MirrorCommand      = command.MirrorCommand

    self.__loader = loader
    self.__context = context
    parts = context.filename.rsplit("/", 1)
    if len(parts) == 1:
      self.__prefix = ""
    else:
      self.__prefix = parts[0] + "/"

  def import_(self, name):
    typecheck(name, str)

    if (self.__loader is None):
      raise DefinitionError("Imports must occur at file load time.")

    # Absolute imports start with "//".
    if name.startswith("//"):
      name = name[2:]
    else:
      name = self.__prefix + name
    (result, timestamp) = self.__loader.load_with_timestamp(name)
    if timestamp > self.__context.timestamp:
      self.__context.timestamp = timestamp
    return result

  def disable(self):
    self.__loader = None

class Loader(object):
  def __init__(self, root_dir):
    typecheck(root_dir, Directory)

    self.__loaded_files = {}
    self.__source_artifacts = {}
    self.__derived_artifacts = {}
    self.__root_dir = root_dir

  def load(self, targetname):
    """Load a SEBS file.  The filename is given relative to the root of
    the source tree (the "src" directory).  Returns an object whose fields
    correspond to the globals defined in that file."""

    return self.load_with_timestamp(targetname)[0]

  def load_with_timestamp(self, targetname):
    """Like load(), but returns a tuple where the second element is the target's
    timestamp.  This is most-recent modification time of the SEBS file defining
    the target and those that it imports."""

    typecheck(targetname, basestring)

    parts = targetname.rsplit(":", 1)

    (file, context) = self.load_file(parts[0])

    if len(parts) == 1:
      return (file, context.timestamp)
    else:
      try:
        target = eval(parts[1], file.__dict__.copy())
      except Exception, e:
        raise DefinitionError("%s: %s" % (targetname, e.message))
      return (target, context.timestamp)

#  def __load_file(self, filename):
  def load_file(self, filename):
    """Load a SEBS file.  The filename is given relative to the root of
    the source tree (the "src" directory).  Returns an object whose fields
    correspond to the globals defined in that file."""

    typecheck(filename, basestring)

    normalized = os.path.normpath(filename).replace("\\", "/")
    if filename != normalized:
      raise DefinitionError(
        "'%s' is not a normalized path name.  Please use '%s' instead." %
        (filename, normalized))

    if filename.startswith("../") or filename.startswith("/"):
      raise DefinitionError(
        "'%s' is not within src." % filename)

    if self.__root_dir.isdir("src/" + filename):
      filename = filename + "/SEBS"

    if filename in self.__loaded_files:
      existing = self.__loaded_files[filename]
      if existing is None:
        raise DefinitionError("File recursively imports itself: %s", filename)
      return existing

    context = _ContextImpl(self, filename, self.__root_dir)
    builtins = _Builtins(self, context)

    def run():
      # TODO(kenton):  Remove SEBS itself from PYTHONPATH before parsing, since
      #   SEBS files should not be importing the SEBS implementation.
      vars = { "sebs": builtins }
      self.__root_dir.execfile(context.full_filename, vars)
      return vars

    self.__loaded_files[filename] = None
    try:
      vars = context.run(run)
    finally:
      del self.__loaded_files[filename]

    # Prohibit lazy imports.
    builtins.disable()

    # Copy the vars before deleting anything because any functions defined in
    # the file still hold a reference to the original map as part of their
    # environment, so modifying the original map could break those functions.
    vars = vars.copy()

    # Delete "builtins", but not if the user replaced them with their own defs.
    if "sebs" in vars and vars["sebs"] is builtins:
      del vars["sebs"]

    for name, value in vars.items():
      if isinstance(value, Rule) and value.context is context:
        # Set label on rule instance.
        value.label = name
      if name.startswith("_"):
        # Delete private variable.
        del vars[name]

    build_file = BuildFile(vars)
    self.__loaded_files[filename] = (build_file, context)
    return (build_file, context)

  def source_artifact(self, filename):
    typecheck(filename, basestring)

    if filename in self.__source_artifacts:
      return self.__source_artifacts[filename]

    result = Artifact(filename, None)
    self.__source_artifacts[filename] = result
    return result

  def derived_artifact(self, filename, action, configured_name=None):
    typecheck(filename, basestring)
    typecheck(action, Action)

    if filename in self.__derived_artifacts:
      raise DefinitionError(
        "Two different rules claim to build file '%s'.  Conflicting rules are "
        "'%s' and '%s'." %
        (filename, action.rule.name,
         self.__derived_artifacts[filename].action.rule.name))

    filename = os.path.normpath(filename).replace("\\", "/")
    result = Artifact(filename, action, configured_name = configured_name)
    self.__derived_artifacts[filename] = result
    return result
