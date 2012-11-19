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

import cStringIO
#import md5
import hashlib
import os
import subprocess
import tempfile
import signal

from sebs.core import Action, Artifact, ContentToken, DefinitionError
from sebs.filesystem import Directory
from sebs.helpers import typecheck
from sebs.command import CommandContext, Command, ArtifactEnumerator
from sebs.console import ColoredText

class ActionRunner(object):
  """Abstract interface for an object which can execute actions."""

  def __init__(self):
    pass

  def run(self, action, inputs, disk_inputs, outputs, test_result, config,
          real_name_map, lock):
    """Executes the given action.  Returns true if the command succeeds, false
    if it fails.  |inputs| and |outputs| are lists of artifacts that are the
    inputs and outputs of this action, as determined by calling
    enumerate_artifacts on the command.

    TODO(kenton):  Too many arguments, need to organize better."""
    raise NotImplementedError

class _CommandContextImpl(CommandContext):
  def __init__(self, working_dir, pending_message, verbose, real_name_map,lock):
    self.__working_dir = working_dir
    self.__temp_files_for_mem = {}
    self.__pending_message = pending_message
    self.__verbose = verbose
    self.__real_name_map = real_name_map
    self.__lock = lock

    self.__original_text = list(self.__pending_message.text)
    self.__verbose_text = []

  def get_disk_path(self, artifact, use_temporary=True):
    filename = self.__real_name_map[artifact]
    result = self.__working_dir.get_disk_path(filename)
    if result is None and use_temporary:
      if filename in self.__temp_files_for_mem:
        result = self.__temp_files_for_mem[filename]
      else:
        (fd, result) = tempfile.mkstemp(
            suffix = "_" + os.path.basename(filename))
        if self.__working_dir.exists(filename):
          os.write(fd, self.__working_dir.read(filename))
          os.close(fd)
          mtime = self.__working_dir.getmtime(filename)
          os.utime(result, (mtime, mtime))
        else:
          os.close(fd)
        # We don't track whether files are executable so we just set the
        # executable bit on everything just in case.
        os.chmod(result, 0700)
        self.__temp_files_for_mem[filename] = result
    return result

  def get_disk_directory_path(self, dirname):
    result = self.__working_dir.get_disk_path(dirname)
    if result is None:
      raise DefinitionError("Not a disk directory: " + dirname)
    else:
      return result

  def read(self, artifact):
    filename = self.__real_name_map[artifact]
    if filename in self.__temp_files_for_mem:
      file = open(self.__temp_files_for_mem[filename], "rU")
      result = file.read()
      file.close()
      return result
    else:
      return self.__working_dir.read(filename)

  def write(self, artifact, content):
    filename = self.__real_name_map[artifact]
    if filename in self.__temp_files_for_mem:
      file = open(self.__temp_files_for_mem[filename], "wb")
      file.write(content)
      file.close()
    else:
      self.__working_dir.write(filename, content)

  def subprocess(self, args, **kwargs):
    if self.__verbose:
      self.__verbose_text.append("\n  ")
      self.__verbose_text.append(" ".join(args))
      self.__pending_message.update(self.__original_text + self.__verbose_text)
    if "stdin" in kwargs and isinstance(kwargs["stdin"], str):
      stdin_str = kwargs["stdin"]
      kwargs["stdin"] = subprocess.PIPE
    else:
      stdin_str = None
    proc = subprocess.Popen(args, **kwargs)

    self.__lock.release()
    try:
      stdout_str, stderr_str = proc.communicate(stdin_str)
    except:
      # Kill the process if it is still running.
      # Note:  Can't use proc.kill() because it's too new.
      os.kill(proc.pid, signal.SIGKILL)
      raise
    finally:
      self.__lock.acquire()

    if proc.returncode == -signal.SIGINT:
      # Subprocess was killed due to ctrl+C.
      raise KeyboardInterrupt

    return (proc.returncode, stdout_str, stderr_str)

  def status(self, text):
    self.__original_text.append(" ")
    self.__original_text.append(ColoredText(ColoredText.BLUE, text))
    self.__pending_message.update(self.__original_text + self.__verbose_text)

  def resolve_mem_files(self):
    for (filename, diskfile) in self.__temp_files_for_mem.items():
      file = open(diskfile, "rb")
      self.__working_dir.write(filename, file, os.path.getmtime(diskfile))
      file.close()
      os.remove(diskfile)
    self.__temp_files_for_mem = {}

def _config_prefix(config):
  if config.name is None:
    return ""
  else:
    return ColoredText(ColoredText.FUCHSIA, [config.name, ": "])

class SubprocessRunner(ActionRunner):
  """An ActionRunner which actually executes the commands."""

  def __init__(self, console, verbose = False):
    super(SubprocessRunner, self).__init__()

    self.__console = console
    self.__verbose = verbose

  def run(self, action, inputs, disk_inputs, outputs, test_result, config,
          real_name_map, lock):
    typecheck(action, Action)

    pending_message = self.__console.add_pending([
        _config_prefix(config),
        ColoredText(ColoredText.BLUE, [action.verb, ": "]), action.name])

    real_outputs = [ real_name_map[output] for output in outputs ]

    # Make sure the output directories exist.
    # TODO(kenton):  Also delete output files from previous runs?
    for output in real_outputs:
      config.root_dir.mkdir(os.path.dirname(output))

    context = _CommandContextImpl(
        config.root_dir, pending_message, self.__verbose, real_name_map, lock)

    try:
      log = cStringIO.StringIO()
      result = action.command.run(context, log)
      context.resolve_mem_files()

      final_text = [pending_message.text]
      log_text = log.getvalue()
      if log_text != "":
        final_text.append("\n  ")
        final_text.append(log_text.strip().replace("\n", "\n  "))

      if not result:
        # Set modification time of all outputs to zero to make sure they are
        # rebuilt on the next run.
        self.__reset_mtime(config.root_dir, real_outputs)

        pending_message.finish(
            [ColoredText(ColoredText.RED, "ERROR: ")] + final_text)

        return False
    except KeyboardInterrupt:
      # Like above.
      context.resolve_mem_files()
      self.__reset_mtime(config.root_dir, real_outputs)
      pending_message.finish(
            [ColoredText(ColoredText.RED, "CANCEL: "), pending_message.text])
      raise
    except:
      # Like above.
      context.resolve_mem_files()
      self.__reset_mtime(config.root_dir, real_outputs)
      pending_message.finish(
            [ColoredText(ColoredText.RED, "ERROR: "), pending_message.text])
      raise

    if test_result is not None:
      if context.read(test_result) == "true":
        passfail = ColoredText(ColoredText.GREEN, "PASS: ")
      else:
        passfail = ColoredText(ColoredText.RED, "FAIL: ")
      final_text = [passfail] + final_text
    pending_message.finish(final_text)

    return True

  def __reset_mtime(self, dir, real_outputs):
    for output in real_outputs:
      try:
        dir.touch(output, 0)
      except Exception:
        pass

# ====================================================================

class CachingRunner(ActionRunner):
  """A wrapper ActionRunner which checks the contents of input files to
  determine if they have actually changed, and skips the action if not."""

  # TODO(kenton):  I wonder if we could use this to detect when the same
  #   action in different configurations produces identical results, and thus
  #   we can "steal" the result from the other config?  Might not be very
  #   useful in practice, though.

  def __init__(self, sub_runner, console):
    typecheck(sub_runner, ActionRunner)
    self.__sub_runner = sub_runner
    self.__console = console
    self.__cache = {}

  def save(self):
    return self.__cache
  def restore(self, cache):
    self.__cache = cache

  def run(self, action, inputs, disk_inputs, outputs, test_result, config,
          real_name_map, lock):
    (can_skip, hash) = self.__can_skip(
        action, inputs, disk_inputs, outputs, config, real_name_map)
    if can_skip:
      self.__console.write([
          _config_prefix(config),
          ColoredText(ColoredText.CYAN, "no changes: "),
          ColoredText(ColoredText.BLUE, [action.verb, ": "]),
          action.name])

      # Update timestamps so that the builder does not even mark these files
      # dirty if we immediately build again.
      for output in outputs:
        config.root_dir.touch(real_name_map[output])
      return True

    # Clear all outputs from cache since the cached value is now invalid.
    for output in outputs:
      # Set to None instead of actually removing from the map because we'll
      # probably be putting these outputs back into the map momentarily.
      self.__cache[(config.name, real_name_map[output])] = None

    result = self.__sub_runner.run(
        action, inputs, disk_inputs, outputs, test_result, config,
        real_name_map, lock)

    if result:
      # Action succeeded, so record it in the cache.  First we need to refresh
      # the disk input list.
      enumerator = _DiskInputCollector(config.root_dir, real_name_map)
      action.command.enumerate_artifacts(enumerator)

      # Must recompute hash if it was not computed before or if the disk inputs
      # changed.
      if hash is None or set(disk_inputs) != set(enumerator.disk_inputs):
        hash = self.__hash(
            action, inputs, enumerator.disk_inputs, outputs, config.root_dir,
            real_name_map)

      # Set new hash on all outputs.
      for output in outputs:
        self.__cache[(config.name, real_name_map[output])] = hash

    return result

  def __can_skip(self, action, inputs, disk_inputs, outputs, config,
                 real_name_map):
    # There should be no such thing as an action without outputs, but if we
    # see one we'll do the conservative thing and not skip it.
    if len(outputs) == 0:
      return (False, None)

    # Look up the hash of the action which produced these outputs last time.
    last_hash = self.__cache.get((config.name, real_name_map[outputs[0]]))
    if last_hash is None:
      return (False, None)    # Nothing in cache, must re-run.

    # All outputs must have the same hash.
    for output in outputs[1:]:
      if self.__cache.get((config.name, real_name_map[output])) != last_hash:
        return (False, None)

    # All disk inputs must exist.
    for disk_input in disk_inputs:
      if not os.path.exists(disk_input):
        return (False, None)

    # Compute new hash and compare.
    new_hash = self.__hash(
        action, inputs, disk_inputs, outputs, config.root_dir, real_name_map)
    if new_hash != last_hash:
      return (False, new_hash)

    # Make sure all outputs exist.  We do this last to avoid touching the
    # filesystem when we don't have to.
    for output in outputs:
      if not config.root_dir.exists(real_name_map[output]):
        return (False, new_hash)

    return (True, new_hash)

  def __hash(self, action, inputs, disk_inputs, outputs, dir, real_name_map):
    # Security is not a concern here, so MD5 is OK and probably faster than
    # more-secure algorithms.
    # caihsiaoster: replace depracated md5 with hashlib.
    hasher = hashlib.md5()
    #hasher = md5.md5()

    input_names = [real_name_map[input] for input in inputs]
    input_names.sort()
    for input in input_names:
      hasher.update("i")
      hasher.update(str(len(input)))
      hasher.update(" ")
      hasher.update(input)
      content = dir.read(input)
      hasher.update(str(len(content)))
      hasher.update(" ")
      hasher.update(content)
      content = None

    disk_input_names = list(disk_inputs)
    disk_input_names.sort()
    for disk_input in disk_input_names:
      hasher.update("d")
      hasher.update(str(len(disk_input)))
      hasher.update(" ")
      hasher.update(disk_input)
      file = open(disk_input, "rU")
      content = file.read()
      file.close()
      hasher.update(str(len(content)))
      hasher.update(" ")
      hasher.update(content)
      content = None

    output_names = [real_name_map[output] for output in outputs]
    output_names.sort()
    for output in output_names:
      hasher.update("o")
      hasher.update(str(len(output)))
      hasher.update(" ")
      hasher.update(output)

    action.command.hash(hasher)
    return hasher.digest()

class _DiskInputCollector(ArtifactEnumerator):
  def __init__(self, root_dir, real_name_map):
    typecheck(root_dir, Directory)
    self.__root_dir = root_dir
    self.__real_name_map = real_name_map
    self.disk_inputs = []

  def add_input(self, artifact):
    pass

  def add_output(self, artifact):
    pass

  def add_disk_input(self, filename):
    self.disk_inputs.append(filename)

  def read(self, artifact):
    # We assume the artifact is clean since we only use DiskInputCollector after
    # the command has run, and the command would not have been run if any inputs
    # were dirty.
    return self.__root_dir.read(self.__real_name_map[artifact])

  def read_previous_output(self, artifact):
    if self.__root_dir.exists(self.__real_name_map[artifact]):
      return self.__root_dir.read(self.__real_name_map[artifact])
    else:
      return None

# useful for debugging...
#
#class HashInterceptor(object):
#  def __init__(self, hasher):
#    self.__hasher = hasher
#    self.__out = cStringIO.StringIO()
#  def update(self, data):
#    self.__hasher.update(data)
#    self.__out.write(data)
#  def content(self):
#    return self.__out.getvalue()
