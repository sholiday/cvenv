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

"""
Commands define exactly what an Action does.
"""

import cStringIO
import os
import pipes
import shutil
import subprocess

from sebs.core import Artifact, Action, DefinitionError, ContentToken, \
                      CommandBase, Context
from sebs.helpers import typecheck

class CommandContext(object):
  def get_disk_path(self, artifact, use_temporary=True):
    """Get the on-disk file name of the given artifact.  If the artifact is not
    on-disk already and use_temporary is true, a temporary file representing
    the artifact will be created.  If use_temporary is false, then this method
    returns None if the file does not have a disk path."""
    raise NotImplementedError

  def get_disk_directory_path(self, dirname):
    """Get the on-disk path of a particular directory.  Useful e.g. to get the
    location of the "include" directory for the current configuration in order
    to pass it to the compiler.  Raises an exception if the directory is not
    on disk (e.g. "mem")."""
    raise NotImplementedError

  def read(self, artifact):
    """Read an artifact's contents, returning them as a string."""
    raise NotImplementedError

  def write(self, artifact, content):
    """Replace the artifact's contents with the given string."""
    raise NotImplementedError

  def subprocess(self, args, **kwargs):
    """Runs a subprocess.  The parameters are the same as those to the Popen
    function in the standard subprocess module.  Additionally, the "stdin"
    argument is allowed to be a string, in which case it will be fed into the
    process via a pipe.  Returns a triplet:  (exit_code, stdout, stderr).
    stdout and stderr are the values returned by the communicate() method of
    the Popen object -- i.e. strings if you passed subprocess.PIPE for the
    corresponding parameters, or None otherwise."""
    raise NotImplementedError

  def message(self, text):
    """Provides a message to be printed to the console reporting the result
    of this action."""
    raise NotImplementedError

class ArtifactEnumerator(object):
  def add_input(self, artifact):
    """Report that the given artifact is an input to the command."""
    raise NotImplementedError

  def add_output(self, artifact):
    """Report that the given artifact is an output to the command."""
    raise NotImplementedError

  def add_disk_input(self, filename):
    """Indicates that if the given file has changed since the last time this
    command was run, then then the command needs to be re-run, even if none of
    the inputs added using add_input() have changed.  The file name is an
    on-disk name, either absolute or relative to the working directory.  Note
    that if the file no longer exists at all, this is treated the same as if
    the file had changed."""
    raise NotImplementedError

  def read(self, artifact):
    """If the given artifact exists and is up-to-date, returns its contents as
    a string.  Otherwise, returns None.  Calling this also implies that the
    artifact is an input, as if add_input() were called."""
    raise NotImplementedError

  def read_previous_output(self, artifact):
    """Similar to read(), but the artifact is actually an *output* of this
    command.  If a copy of the artifact exists, left over from a previous
    build, then its contents will be returned.  Otherwise, returns None.

    This is intended to be used together with add_disk_input() to handle .d
    files, e.g. as produced by GCC's -MD option.  These files list all of the
    headers which were included by a C/C++ source file the last time it was
    compiled; if any of these headers have changed then the source file will
    need to be recompiled."""
    raise NotImplementedError

class ScriptWriter(object):
  def add_command(self, text):
    """Add a command which should be executed as part of the current action."""
    raise NotImplementedError

  def echo_expression(self, expression, output_artifact):
    """Returns a shell expression which, when evaluated, will set the contents
    of the given artifact to the expansion of the given expression.  In other
    words, this usually produces:
        'echo "%s" > %s' % (expression, output_artifact.filename)
    But if the output artifact is a memory artifact, it will instead store
    the result to a variable:
        '%s="%s"' % (varname(output_artifact), expression)
    """
    raise NotImplementedError

  def add_input(self, artifact):
    """Report that the given artifact is an input to the command."""
    raise NotImplementedError

  def add_output(self, artifact):
    """Report that the given artifact is an output to the command."""
    raise NotImplementedError

  def artifact_filename_expression(self, artifact):
    """Returns a shell expression which expands to the on-disk name of the
    given artifact.  Calling this method also implies calls to
    add_input() for any artifacts whose contents determine part of this
    artifact's name.  Furthermore, if the artifact is an in-memory artifact then
    this method implies that a temporary file representing it must be created
    for the duration of this action, or until the end of the current
    conditional clause, whichever comes first."""
    raise NotImplementedError

  def artifact_content_expression(self, artifact):
    """Returns a shell expression which expands to the contents of the given
    artifact.  For memory artifacts this is just a simple variable expansion
    whereas for on-disk artifacts it is $(<filename)."""
    raise NotImplementedError

  def get_disk_directory_path(self, dir):
    """Same as CommandContext.get_disk_directory_path()."""
    raise NotImplementedError

  def set_status(self, status_expression):
    """Says that when the action is complete, the given shell expression should
    be expanded and the result printed as the "status" -- a short message
    appearing on the same line as the action name itself indicating the
    result."""
    raise NotImplementedError

  def enter_conditional(self, expression, required_artifacts_for_expression):
    """Begin a block that should only be executed if the given expression
    expands to the word "true".  required_artifacts_for_expression is a list
    of artifacts which must be built before the expression can be evaluated.
    Between a call to enter_conditional() and a corresponding call to
    enter_else() or leave_conditional(), all method calls are interpreted
    as being only relevant if the condition was true."""
    raise NotImplementedError

  def enter_else(self):
    """Called some time after enter_conditional() to move to the "else" clause
    of the conditional.  If no else clause is needed, do not call this; go
    straight to leave_conditional()."""
    raise NotImplementedError

  def leave_conditional(self):
    """Called to end the conditional started by a previous call to
    enter_conditional()."""
    raise NotImplementedError

class Command(CommandBase):
  """Represents something which an Action does, e.g. executing a shell command.
  Command implementations are not allowed to create new Actions or Artifacts --
  they can only use the ones passed to their constructors.  In general, they
  should not have any side effects except for those explicitly allowed."""

  def enumerate_artifacts(self, artifact_enumerator):
    """Calls the ArtifactEnumerator's add_input() and add_output() commands for
    all inputs and outputs that the command is known to have.  This method is
    allowed to call artifact_enumerator.read() and make decisions based on it.
    If read() returns None, then the caller must assume that the list of
    inputs and outputs is incomplete, and in order to get a complete list it
    will need to re-run enumerate_artifacts with the read artifact available."""
    raise NotImplementedError

  def run(self, context, log):
    """Run the command.  Returns True if the command succeeded or False if some
    error occurred -- error details should already have been written to |log|,
    which is a file-like object."""
    raise NotImplementedError

  def print_(self, output):
    """Print a human-readable representation of what the command does.  The
    text should be written to the given output stream."""
    raise NotImplementedError

  def hash(self, hasher):
    """Feeds information to the given hasher which uniquely describes this
    command, so that two commands with the same hash must (barring hash
    collisions) be the same command.  The hasher type is one of those
    provided by the Python hashlib module, or something implementing the
    same interface.  Typically the first thing a hash() method should do
    is call hasher.update() with the command class's own type name.  As a
    rule of thumb, the data you feed to the hasher should be such that it
    would be possible to parse that data in order to reproduce the action,
    although you do not actually need to write any such parser."""
    raise NotImplementedError

  def write_script(self, script_writer):
    """Given a ScriptWriter object, uses it to write a shell script fragment
    corresponding to this command."""
    raise NotImplementedError

def _hash_string_and_length(string, hasher):
  hasher.update(str(len(string)))
  hasher.update(" ")
  hasher.update(string)

# ====================================================================

class EchoCommand(Command):
  """Command which simply writes a string into an artifact."""

  def __init__(self, content, output_artifact):
    typecheck(content, str)
    typecheck(output_artifact, Artifact)
    self.__content = content
    self.__output_artifact = output_artifact

  def enumerate_artifacts(self, artifact_enumerator):
    typecheck(artifact_enumerator, ArtifactEnumerator)
    artifact_enumerator.add_output(self.__output_artifact)

  def run(self, context, log):
    typecheck(context, CommandContext)
    context.write(self.__output_artifact, self.__content)
    return True

  def print_(self, output):
    output.write("echo '%s' > %s\n" %
        (self.__content, self.__output_artifact.filename))

  def hash(self, hasher):
    hasher.update("EchoCommand:")
    _hash_string_and_length(self.__content, hasher)
    _hash_string_and_length(self.__output_artifact.filename, hasher)

  def write_script(self, script_writer):
    script_writer.add_command(
        script_writer.echo_expression(
          pipes.quote(self.__content), self.__output_artifact))

# ====================================================================

class EnvironmentCommand(Command):
  """Command which reads an environment variable and writes the contents into
  an artifact.  If the environment variable is unset, a default value is used.
  The default value may be a simple string or it may be another artifact -- in
  the latter case, the artifact's contents are copied into the output."""

  def __init__(self, rule_context, env_name, output_artifact, default=None,
               set_status=False, error_message_if_unset=None):
    typecheck(rule_context, Context)
    typecheck(env_name, str)
    typecheck(output_artifact, Artifact)
    typecheck(default, [str, Artifact])

    self.__env_name = env_name
    self.__env_artifact = rule_context.environment_artifact(env_name)
    self.__env_set_artifact = rule_context.environment_set_artifact(env_name)
    self.__output_artifact = output_artifact
    self.__default = default
    self.__set_status = set_status
    if default is None and error_message_if_unset is None:
      self.__error_message_if_unset = \
          "Required environment variable not set: %s" % env_name
    else:
      self.__error_message_if_unset = error_message_if_unset

  def enumerate_artifacts(self, artifact_enumerator):
    typecheck(artifact_enumerator, ArtifactEnumerator)

    if artifact_enumerator.read(self.__env_set_artifact) == "true":
      artifact_enumerator.add_input(self.__env_artifact)
    elif self.__default is not None and isinstance(self.__default, Artifact):
      artifact_enumerator.add_input(self.__default)

    artifact_enumerator.add_output(self.__output_artifact)

  def run(self, context, log):
    typecheck(context, CommandContext)

    if context.read(self.__env_set_artifact) == "true":
      value = context.read(self.__env_artifact)
    elif self.__default is None:
      log.write(self.__error_message_if_unset + "\n")
      return False
    elif isinstance(self.__default, Artifact):
      value = context.read(self.__default)
    else:
      value = self.__default

    context.write(self.__output_artifact, value)
    if self.__set_status:
      context.status(value)
    return True

  def print_(self, output):
    if self.__default is None:
      output.write("echo $%s > %s\n" %
          (self.__env_name, self.__output_artifact.filename))
    elif isinstance(self.__default, Artifact):
      output.write("echo ${%s:$(%s)} > %s\n" %
          (self.__env_name, self.__default.filename,
           self.__output_artifact.filename))
    else:
      output.write("echo ${%s:%s} > %s\n" %
          (self.__env_name, self.__default,
           self.__output_artifact.filename))

  def hash(self, hasher):
    hasher.update("EnvironmentCommand:")
    _hash_string_and_length(self.__env_name, hasher)
    _hash_string_and_length(self.__output_artifact.filename, hasher)
    if self.__default is None:
      hasher.update("x")
    elif isinstance(self.__default, Artifact):
      hasher.update("f")
      _hash_string_and_length(self.__default.filename, hasher)
    else:
      hasher.update("s")
      _hash_string_and_length(self.__default, hasher)

  def write_script(self, script_writer):
    if self.__default is None:
      script_writer.add_command(
          "test \"${%s+set}\" = set || die %s" %
          (self.__env_name, pipes.quote(self.__error_message_if_unset)))
      expression = "${%s}" % self.__env_name
    else:
      if isinstance(self.__default, Artifact):
        default = script_writer.artifact_content_expression(self.__default)
      else:
        default = pipes.quote(self.__default)
      expression = "${%s-%s}" % (self.__env_name, default)
    script_writer.add_command(
        script_writer.echo_expression(expression, self.__output_artifact))
    if self.__set_status:
      script_writer.set_status(expression)

# ====================================================================

class DoAllCommand(Command):
  """Command which simply executes some list of commands in order."""

  def __init__(self, subcommands):
    typecheck(subcommands, list, Command)
    self.__subcommands = subcommands

  def enumerate_artifacts(self, artifact_enumerator):
    typecheck(artifact_enumerator, ArtifactEnumerator)
    for command in self.__subcommands:
      command.enumerate_artifacts(artifact_enumerator)

  def run(self, context, log):
    typecheck(context, CommandContext)
    for command in self.__subcommands:
      if not command.run(context, log):
        return False
    return True

  def print_(self, output):
    for command in self.__subcommands:
      command.print_(output)

  def hash(self, hasher):
    hasher.update("DoAllCommand:")
    hasher.update(str(len(self.__subcommands)))
    hasher.update(" ")
    for command in self.__subcommands:
      command.hash(hasher)

  def write_script(self, script_writer):
    for command in self.__subcommands:
      command.write_script(script_writer)

# ====================================================================

class ConditionalCommand(Command):
  """Command which first checks if the contents of some artifact.  The contents
  are expected to be either "true" or "false".  If "true", then true_command
  is executed.  A false_command may optionally be given which is executed if
  the value was false."""

  def __init__(self, condition_artifact, true_command, false_command = None):
    typecheck(condition_artifact, Artifact)
    typecheck(true_command, Command)
    typecheck(false_command, Command)
    self.__condition_artifact = condition_artifact
    self.__true_command = true_command
    self.__false_command = false_command

  def enumerate_artifacts(self, artifact_enumerator):
    typecheck(artifact_enumerator, ArtifactEnumerator)
    value = artifact_enumerator.read(self.__condition_artifact)
    if value == "true":
      self.__true_command.enumerate_artifacts(artifact_enumerator)
    elif value == "false" and self.__false_command is not None:
      self.__false_command.enumerate_artifacts(artifact_enumerator)

  def run(self, context, log):
    typecheck(context, CommandContext)
    value = context.read(self.__condition_artifact)
    if value == "true":
      return self.__true_command.run(context, log)
    elif value == "false":
      if self.__false_command is not None:
        return self.__false_command.run(context, log)
      else:
        return True
    else:
      log.write("Condition artifact was not true or false: %s\n" %
                self.__condition_artifact)
      return False

  def print_(self, output):
    output.write("if %s {\n" % self.__condition_artifact.filename)
    sub_output = cStringIO.StringIO()
    self.__true_command.print_(sub_output)
    output.write(self.__indent(sub_output.getvalue()))
    if self.__false_command is not None:
      output.write("} else {\n")
      sub_output = cStringIO.StringIO()
      self.__false_command.print_(sub_output)
      output.write(self.__indent(sub_output.getvalue()))
    output.write("}\n")

  def __indent(self, text):
    lines = text.split("\n")
    if lines[-1] == "":
      lines.pop()
    return "  %s\n" % "\n  ".join(lines)

  def hash(self, hasher):
    hasher.update("ConditionalCommand:")
    _hash_string_and_length(self.__condition_artifact.filename, hasher)
    self.__true_command.hash(hasher)
    if self.__false_command is None:
      hasher.update("-")
    else:
      hasher.update("+")
      self.__false_command.hash(hasher)

  def write_script(self, script_writer):
    script_writer.enter_conditional(
        "test \"%s\" = true" %
          script_writer.artifact_content_expression(self.__condition_artifact),
        [self.__condition_artifact])
    self.__true_command.write_script(script_writer)
    if self.__false_command is not None:
      script_writer.enter_else()
      self.__false_command.write_script(script_writer)
    script_writer.leave_conditional()

# ====================================================================

class SubprocessCommand(Command):
  """Command which launches a separate process."""

  class DirectoryToken(object):
    """Can be used in an argument list to indicate that the on-disk location
    of the given virtual directory should be used as the argument."""

    def __init__(self, dirname):
      typecheck(dirname, basestring)
      self.dirname = dirname

  class Quoted(object):
    """Can be used in an argument list to indicate that the given sublist of
    args should be interpreted like a top-level arg list, then combined into
    one string using shell quoting rules such that passing said string to
    sh -c would execute the command represented by the arg list.  This can
    be used e.g. to safely pass a command to ssh to be run remotely."""

    def __init__(self, args):
      self.args = args

  def __init__(self, action, args, implicit = [],
               capture_stdout=None, capture_stderr=None,
               capture_exit_status=None, working_dir=None):
    typecheck(action, Action)
    typecheck(args, list)
    typecheck(implicit, list, Artifact)
    typecheck(capture_stdout, Artifact)
    typecheck(capture_stderr, Artifact)
    typecheck(capture_exit_status, Artifact)
    typecheck(working_dir, basestring)

    self.__verify_args(args)

    self.__args = args
    self.__implicit_artifacts = implicit
    self.__action = action
    self.__capture_stdout = capture_stdout
    self.__capture_stderr = capture_stderr
    self.__capture_exit_status = capture_exit_status
    self.__working_dir = working_dir

  def enumerate_artifacts(self, artifact_enumerator):
    if self.__capture_stdout is not None:
      artifact_enumerator.add_output(self.__capture_stdout)
    if self.__capture_stderr is not None:
      artifact_enumerator.add_output(self.__capture_stderr)
    if self.__capture_exit_status is not None:
      artifact_enumerator.add_output(self.__capture_exit_status)

    # All other inputs and outputs are listed in the arguments, or in
    # __implicit_artifacts.  We can identify outputs as the artifacts which are
    # generated by the action which runs this command.  The rest are inputs.
    class DummyContext(CommandContext):
      def __init__(self):
        self.artifacts = set()
      def get_disk_path(self, artifact):
        self.artifacts.add(artifact)
        return ""
      def get_disk_directory_path(self, dirname):
        return ""
      def read(self, artifact):
        self.artifacts.add(artifact)
        return ""

    context = DummyContext()
    context.artifacts.update(self.__implicit_artifacts)
    for dummy in self.__format_args(self.__args, context):
      # We must actually iterate through the results because __format_args()
      # is a generator function.
      pass

    for artifact in context.artifacts:
      if self.__action is not None and artifact.action is self.__action:
        artifact_enumerator.add_output(artifact)
      else:
        artifact_enumerator.add_input(artifact)

  def run(self, context, log):
    formatted_args = list(self.__format_args(self.__args, context))

    # Capture stdout/stderr if requested.
    if self.__capture_stdout is None:
      # The log is not a unix file descriptor, so we must use a pipe and then
      # write to in manually.
      stdout = subprocess.PIPE
    else:
      disk_path = context.get_disk_path(self.__capture_stdout,
                                        use_temporary = False)
      if disk_path is None:
        stdout = subprocess.PIPE
      else:
        stdout = open(disk_path, "wb")

    if self.__capture_stderr is self.__capture_stdout:
      stderr = subprocess.STDOUT
    elif self.__capture_stderr is None:
      # The log is not a unix file descriptor, so we must use a pipe and then
      # write to in manually.
      stderr = subprocess.PIPE
    else:
      disk_path = context.get_disk_path(self.__capture_stderr,
                                        use_temporary = False)
      if disk_path is None:
        stderr = subprocess.PIPE
      else:
        stderr = open(disk_path, "wb")

    env = os.environ.copy()
    # TODO(kenton):  We should *add* src to the existing PYTHONPATH instead of
    #   overwrite, but there is one problem:  The SEBS Python archive may be
    #   in PYTHONPATH, and we do NOT want programs that we run to be able to
    #   take advantage of that to import SEBS implementation modules.
    env["PYTHONPATH"] = "src"

    if self.__working_dir is None:
      cwd = None
    else:
      cwd = os.path.join(os.getcwd(),
                         context.get_disk_directory_path(self.__working_dir))

    exit_code, stdout_text, stderr_text = \
        context.subprocess(formatted_args,
                           stdout = stdout, stderr = stderr,
                           env = env, cwd = cwd)

    if stdout == subprocess.PIPE:
      if self.__capture_stdout is None:
        log.write(stdout_text)
      else:
        context.write(self.__capture_stdout, stdout_text)
    if stderr == subprocess.PIPE:
      if self.__capture_stderr is None:
        log.write(stderr_text)
      else:
        context.write(self.__capture_stderr, stderr_text)

    if self.__capture_exit_status is not None:
      if exit_code == 0:
        context.write(self.__capture_exit_status, "true")
      else:
        context.write(self.__capture_exit_status, "false")
      return True
    else:
      if exit_code == 0:
        return True
      else:
        log.write("Command failed with exit code %d: %s\n" %
            (exit_code, " ".join(formatted_args)))
        return False

  def print_(self, output):
    if self.__working_dir is not None:
      output.write("cd %s && " % self.__working_dir)

    class DummyContext(CommandContext):
      def get_disk_path(self, artifact):
        return artifact.filename
      def get_disk_directory_path(self, dirname):
        return dirname
      def read(self, artifact):
        return "$(<%s)" % artifact.filename

    output.write(" ".join(self.__format_args(self.__args, DummyContext())))

    if self.__capture_stdout is not None:
      output.write(" > %s" % self.__capture_stdout.filename)
    if self.__capture_stderr is not None:
      if self.__capture_stderr is self.__capture_stdout:
        output.write(" 2>&1")
      else:
        output.write(" 2> %s" % self.__capture_stderr.filename)
    if self.__capture_exit_status is not None:
      output.write(" && echo true > %s || echo false > %s" %
          (self.__capture_exit_status.filename,
           self.__capture_exit_status.filename))
    output.write("\n")

  def __verify_args(self, args):
    for arg in args:
      if isinstance(arg, list):
        self.__verify_args(arg)
      elif not isinstance(arg, basestring) and \
           not isinstance(arg, Artifact) and \
           not isinstance(arg, ContentToken) and \
           not isinstance(arg, SubprocessCommand.DirectoryToken) and \
           not isinstance(arg, SubprocessCommand.Quoted):
        raise TypeError("Invalid argument: %s" % arg)

  def __format_args(self, args, context, split_content=True):
    for arg in args:
      if isinstance(arg, basestring):
        yield arg
      elif isinstance(arg, Artifact):
        yield context.get_disk_path(arg)
      elif isinstance(arg, ContentToken):
        content = context.read(arg.artifact)
        if split_content:
          for part in content.split():
            yield part
        else:
          yield content
      elif isinstance(arg, SubprocessCommand.DirectoryToken):
        yield context.get_disk_directory_path(arg.dirname)
      elif isinstance(arg, SubprocessCommand.Quoted):
        sub_formatted = self.__format_args(arg.args, context)
        yield " ".join([pipes.quote(part) for part in sub_formatted])
      elif isinstance(arg, list):
        yield "".join(self.__format_args(
            arg, context, split_content = False))
      else:
        raise AssertionError("Invalid argument.")

  def hash(self, hasher):
    hasher.update("SubprocessCommand:")
    self.__hash_args(self.__args, hasher)
    if self.__capture_stdout is not None:
      hasher.update(">")
      _hash_string_and_length(self.__capture_stdout.filename, hasher)
    if self.__capture_stderr is not None:
      hasher.update("&")
      _hash_string_and_length(self.__capture_stderr.filename, hasher)
    if self.__capture_exit_status is not None:
      hasher.update("?")
      _hash_string_and_length(self.__capture_exit_status.filename, hasher)
    if self.__working_dir is not None:
      hasher.update("/")
      _hash_string_and_length(self.__working_dir, hasher)

    # Hash implicit files in sorted order so that use of hash sets by the
    # creator doesn't cause problems.
    implicit_names = []
    for implicit in self.__implicit_artifacts:
      if implicit.action is self.__action:
        implicit_names.append("+" + implicit.filename)
      else:
        implicit_names.append("-" + implicit.filename)
    implicit_names.sort()
    for implicit in implicit_names:
      _hash_string_and_length(implicit, hasher)

    hasher.update(".")

  def __hash_args(self, args, hasher):
    hasher.update(str(len(args)))
    hasher.update(" ")
    for arg in args:
      if isinstance(arg, basestring):
        hasher.update("s")
        _hash_string_and_length(arg, hasher)
      elif isinstance(arg, Artifact):
        if arg.action is self.__action:
          hasher.update("o")
        else:
          hasher.update("i")
        _hash_string_and_length(arg.filename, hasher)
      elif isinstance(arg, ContentToken):
        hasher.update("c")
        _hash_string_and_length(arg.artifact.filename, hasher)
      elif isinstance(arg, SubprocessCommand.DirectoryToken):
        hasher.update("d")
        _hash_string_and_length(arg.dirname, hasher)
      elif isinstance(arg, SubprocessCommand.Quoted):
        hasher.update("q")
        self.__hash_args(arg.args, hasher)
      elif isinstance(arg, list):
        hasher.update("l")
        self.__hash_args(arg, hasher)
      else:
        raise AssertionError("Invalid argument.")

  def write_script(self, script_writer):
    for artifact in self.__implicit_artifacts:
      if self.__action is not None and artifact.action is self.__action:
        script_writer.add_output(artifact)
      else:
        script_writer.add_input(artifact)

    command_parts = []
    command_parts.append(
        " ".join(self.__script_args(self.__args, script_writer)))

    if self.__capture_stdout is not None:
      command_parts.append(">%s" %
        script_writer.artifact_filename_expression(
          self.__capture_stdout))
    if self.__capture_stderr is not None:
      if self.__capture_stderr is self.__capture_stdout:
        command_parts.append("2>&1")
      else:
        command_parts.append("2>%s" %
          script_writer.artifact_filename_expression(
            self.__capture_stderr))
    if self.__capture_exit_status is not None:
      command_parts.append("&& %s || %s" %
        (script_writer.echo_expression("true", self.__capture_exit_status),
         script_writer.echo_expression("false", self.__capture_exit_status)))

    command = " ".join(command_parts)
    if self.__working_dir is not None:
      raise NotImplementedError(
          "Scripts for SubprocessCommands with working directories are not "
          "implemented.")
      # TODO(kenton):  This doesn't work since all the file names are relative
      #   to the original directory.
      working_dir = script_writer.get_disk_directory_path(self.__working_dir)
      command = "(cd %s && %s)" % (working_dir, command)

    script_writer.add_command(command)

  def __script_args(self, args, script_writer):
    for arg in args:
      if isinstance(arg, basestring):
        yield pipes.quote(arg)
      elif isinstance(arg, Artifact):
        yield script_writer.artifact_filename_expression(arg)
      elif isinstance(arg, ContentToken):
        yield script_writer.artifact_content_expression(arg.artifact)
      elif isinstance(arg, SubprocessCommand.DirectoryToken):
        yield script_writer.get_disk_directory_path(arg.dirname)
      elif isinstance(arg, SubprocessCommand.Quoted):
        raise NotImplementedError(
            "Generating a script for a SubprocessCommand which uses Quoted "
            "is actually really hard, maybe impossible.")
      elif isinstance(arg, list):
        yield "".join(self.__script_args(arg, script_writer))
      else:
        raise AssertionError("Invalid argument.")

# ====================================================================

class DepFileCommand(Command):
  """A Command which produces a dependency list as part of its execution, e.g.
  as GCC does when given the -MD command-line flag.  Wraps some other command
  that does the actual work."""

  def __init__(self, real_command, dep_artifact):
    typecheck(real_command, Command)
    typecheck(dep_artifact, Artifact)
    self.__command = real_command
    self.__dep_artifact = dep_artifact

  def enumerate_artifacts(self, artifact_enumerator):
    self.__command.enumerate_artifacts(artifact_enumerator)

    dep_text = artifact_enumerator.read_previous_output(self.__dep_artifact)
    if dep_text is not None:
      # Parse text that looks like:
      #   foo.o: foo.h bar.h \
      #     baz.h qux.h
      dep_text = dep_text.replace("\\\n", " ")  # remove escaped newlines
      parts = dep_text.split()
      for part in parts:
        # Skip tokens like "foo.o:".  The rest are files.
        if not part.endswith(":"):
          artifact_enumerator.add_disk_input(part)

  def run(self, context, log):
    return self.__command.run(context, log)

  def print_(self, output):
    self.__command.print_(output)

  def hash(self, hasher):
    hasher.update("DepFileCommand:")
    self.__command.hash(hasher)

  def write_script(self, script_writer):
    # TODO(kenton):  Maybe generate the depfile at the time the script is
    #   generated?  But we'd have to make sure to strip out system headers,
    #   and we wouldn't be able to deal with conditional includes very well.
    #   Maybe that doesn't matter.  Alternatively, maybe we could actually
    #   include code in the script to parse depfiles?
    self.__command.write_script(script_writer)

# ====================================================================

class MirrorCommand(Command):
  """A Command which sets up a directory to contain mirrors of a set of files.
  It may use symbolic links, hard links, or copies depending on what the OS
  supports."""

  def __init__(self, artifacts, output_dir, dummy_output_artifact):
    typecheck(artifacts, list)
    typecheck(output_dir, basestring)
    typecheck(dummy_output_artifact, Artifact)

    for artifact in artifacts:
      typecheck(artifact, Artifact)

    self.__artifacts = artifacts
    self.__output_dir = output_dir
    self.__dummy_output_artifact = dummy_output_artifact

  def enumerate_artifacts(self, artifact_enumerator):
    for input in self.__artifacts:
      artifact_enumerator.add_input(input)
    artifact_enumerator.add_output(self.__dummy_output_artifact)

  def run(self, context, log):
    dir = context.get_disk_directory_path(self.__output_dir)

    if not os.path.exists(dir):
      os.makedirs(dir)

    for artifact in self.__artifacts:
      source = context.get_disk_path(artifact, use_temporary=False)
      dest = os.path.join(dir, artifact.real_name(context.read))

      parent = os.path.dirname(dest)
      if not os.path.exists(parent):
        os.makedirs(parent)

      if source is None:
        log.write("%s: cannot create link to virtual file.\n" %
                  artifact.filename)
        return False
      if not os.path.exists(source):
        log.write("%s: file not found.\n" % source)
        return False

      if os.path.lexists(dest):
        os.remove(dest)

      try:
        # TODO(kenton):  Use symbolic links?  It's a bit harder because we would
        #   have to compute the path to dest relative to source, which can be
        #   non-trivial when the paths happen to contain components which are
        #   themselves symlinks (which means that ".." may not go where we
        #   expect).  We could just use absolute paths but that means that the
        #   resulting link tree cannot be used by another machine which happens
        #   to map the working directory to a different absolute path -- this
        #   could be problematic if we ever attempt to implement distributed
        #   tests backed by NFS.
        os.link(source, dest)
      except os.error, message:
        log.write("ln %s %s: %s\n" % (source, dest, message))
        return False

    context.write(self.__dummy_output_artifact,
        "\n".join([artifact.filename for artifact in self.__artifacts]))

    return True

  def print_(self, output):
    output.write("mirror @%s {" % self.__output_dir)
    for artifact in self.__artifacts:
      output.write("  %s\n" % artifact.filename)
    output.write("}")

  def hash(self, hasher):
    hasher.update("MirrorCommand:")
    for artifact in self.__artifacts:
      hasher.update("+")
      _hash_string_and_length(artifact.filename, hasher)
    hasher.update("-")
    _hash_string_and_length(self.__output_dir, hasher)
    _hash_string_and_length(self.__dummy_output_artifact.filename, hasher)

  def write_script(self, script_writer):
    output_dir = script_writer.get_disk_directory_path(self.__output_dir)
    made_dirs = set()

    for input in self.__artifacts:
      script_writer.add_input(input)

      # Make the directory where this file is being linked if it doesn't
      # already exist.
      input_dir = os.path.dirname(os.path.join(output_dir, input.filename))
      if input_dir not in made_dirs:
        made_dirs.add(input_dir)
        script_writer.add_command("mkdir -p %s" % pipes.quote(input_dir))

      # Create the link.
      disk_filename = script_writer.artifact_filename_expression(input)
      script_writer.add_command("ln %s %s/%s" %
          (disk_filename, output_dir, input.filename))

    list = "\n".join([artifact.filename for artifact in self.__artifacts])
    script_writer.add_command(
        script_writer.echo_expression(
          pipes.quote(list), self.__dummy_output_artifact))
