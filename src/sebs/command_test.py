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

import cStringIO
import subprocess
import unittest

from sebs.core import Artifact, Action, DefinitionError, ContentToken, Context
from sebs.command import CommandContext, ArtifactEnumerator, Command, \
                         EchoCommand, EnvironmentCommand, DoAllCommand, \
                         ConditionalCommand, SubprocessCommand
from sebs.filesystem import VirtualDirectory

def _print_command(command):
  out = cStringIO.StringIO()
  command.print_(out)
  return out.getvalue()

class MockCommandContext(CommandContext):
  def __init__(self, dir, diskpath_prefix = None):
    self.__dir = dir
    self.subprocess_args = None
    self.subprocess_kwargs = None
    self.subprocess_result = (0, "", None)
    self.diskpath_prefix = diskpath_prefix

  def get_disk_path(self, artifact, use_temporary=True):
    if self.diskpath_prefix is None:
      if use_temporary:
        raise NotImplementedError
      else:
        return None
    else:
      return self.diskpath_prefix + artifact.filename

  def read(self, artifact):
    return self.__dir.read(artifact.filename)

  def write(self, artifact, content):
    self.__dir.write(artifact.filename, content)

  def subprocess(self, args, **kwargs):
    assert self.subprocess_kwargs is None  # Should not call twice.
    self.subprocess_args = args
    self.subprocess_kwargs = kwargs
    return self.subprocess_result

class MockRuleContext(Context):
  def __init__(self, *kwargs):
    self.__map = {}
    for artifact in kwargs:
      self.__map[artifact.filename] = artifact

  def environment_artifact(self, env_name):
    return self.__map["env/" + env_name]

  def environment_set_artifact(self, env_name):
    return self.__map["env/set/" + env_name]

class MockArtifactEnumerator(ArtifactEnumerator):
  def __init__(self, readable_artifacts = {}):
    self.readable_artifacts = readable_artifacts
    self.reads = []
    self.inputs = []
    self.outputs = []

  def add_input(self, artifact):
    self.inputs.append(artifact)

  def add_output(self, artifact):
    self.outputs.append(artifact)

  def read(self, artifact):
    self.reads.append(artifact)
    if artifact in self.readable_artifacts:
      return self.readable_artifacts[artifact]
    else:
      return None

class MockCommand(Command):
  def __init__(self, name, inputs = [], outputs = [], fails=False):
    self.name = name
    self.inputs = inputs
    self.outputs = outputs
    self.fails = fails

  def enumerate_artifacts(self, artifact_enumerator):
    for input in self.inputs:
      artifact_enumerator.add_input(input)
    for output in self.outputs:
      artifact_enumerator.add_output(output)

  def run(self, context, log):
    log.write("Ran MockCommand %s\n" % self.name)
    return not self.fails

  def print_(self, output):
    output.write("mock_command %s\n" % self.name)

class CommandTest(unittest.TestCase):
  def testEchoCommand(self):
    dir = VirtualDirectory()
    output = Artifact("foo", None)
    command = EchoCommand("bar", output)

    enumerator = MockArtifactEnumerator()
    command.enumerate_artifacts(enumerator)
    self.assertEquals([], enumerator.reads)
    self.assertEquals([], enumerator.inputs)
    self.assertEquals([output], enumerator.outputs)

    context = MockCommandContext(dir)
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertEquals("bar", dir.read("foo"))
    self.assertEquals("", log.getvalue())

    self.assertEquals("echo 'bar' > foo\n", _print_command(command))

  def testEnvironmentCommand(self):
    dir = VirtualDirectory()
    bar = Artifact("env/BAR", None)
    bar_set = Artifact("env/set/BAR", None)
    output = Artifact("foo", None)
    command = EnvironmentCommand(MockRuleContext(bar, bar_set), "BAR", output)

    enumerator = MockArtifactEnumerator({bar_set: "false"})
    command.enumerate_artifacts(enumerator)
    self.assertEquals([bar_set], enumerator.reads)
    self.assertEquals([], enumerator.inputs)
    self.assertEquals([output], enumerator.outputs)

    enumerator = MockArtifactEnumerator({bar_set: "true"})
    command.enumerate_artifacts(enumerator)
    self.assertEquals([bar_set], enumerator.reads)
    self.assertEquals([bar], enumerator.inputs)
    self.assertEquals([output], enumerator.outputs)

    context = MockCommandContext(dir)

    dir.write("env/set/BAR", "false")
    log = cStringIO.StringIO()
    self.assertFalse(command.run(context, log))
    self.assertFalse(dir.exists("foo"))
    self.assertEquals("Environment variable not set: BAR\n", log.getvalue())

    dir.write("env/set/BAR", "true")
    dir.write("env/BAR", "baz")
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertEquals("baz", dir.read("foo"))
    self.assertEquals("", log.getvalue())

    self.assertEquals("echo $BAR > foo\n", _print_command(command))

  def testEnvironmentCommandWithDefault(self):
    bar = Artifact("env/BAR", None)
    bar_set = Artifact("env/set/BAR", None)
    default = Artifact("default", None)
    output = Artifact("foo", None)
    command = EnvironmentCommand(MockRuleContext(bar, bar_set),
                                 "BAR", output, default)

    enumerator = MockArtifactEnumerator({bar_set: "false"})
    command.enumerate_artifacts(enumerator)
    self.assertEquals([bar_set], enumerator.reads)
    self.assertEquals([default], enumerator.inputs)
    self.assertEquals([output], enumerator.outputs)

    enumerator = MockArtifactEnumerator({bar_set: "true"})
    command.enumerate_artifacts(enumerator)
    self.assertEquals([bar_set], enumerator.reads)
    self.assertEquals([bar], enumerator.inputs)
    self.assertEquals([output], enumerator.outputs)

    dir = VirtualDirectory()
    dir.write("env/set/BAR", "true")
    dir.write("env/BAR", "baz")
    context = MockCommandContext(dir)
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertEquals("baz", dir.read("foo"))
    self.assertEquals("", log.getvalue())

    dir = VirtualDirectory()
    dir.write("env/set/BAR", "false")
    dir.write("default", "qux")
    context = MockCommandContext(dir)
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertEquals("qux", dir.read("foo"))
    self.assertEquals("", log.getvalue())

    self.assertEquals("echo ${BAR:$(default)} > foo\n", _print_command(command))

  def testDoAllCommand(self):
    dir = VirtualDirectory()

    inputs = [ Artifact("input1", None), Artifact("input2", None) ]
    outputs = [ Artifact("output1", None), Artifact("output2", None) ]

    mock_command1 = MockCommand("command1", inputs[:1], outputs[:1])
    mock_command2 = MockCommand("command2", inputs[1:], outputs[1:])
    command = DoAllCommand([mock_command1, mock_command2])

    enumerator = MockArtifactEnumerator()
    command.enumerate_artifacts(enumerator)
    self.assertEquals([], enumerator.reads)
    self.assertEquals(inputs, enumerator.inputs)
    self.assertEquals(outputs, enumerator.outputs)

    context = MockCommandContext(dir)
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertEquals("Ran MockCommand command1\n"
                      "Ran MockCommand command2\n", log.getvalue())

    mock_command2.fails = True
    log = cStringIO.StringIO()
    self.assertFalse(command.run(context, log))
    self.assertEquals("Ran MockCommand command1\n"
                      "Ran MockCommand command2\n", log.getvalue())

    mock_command1.fails = True
    log = cStringIO.StringIO()
    self.assertFalse(command.run(context, log))
    self.assertEquals("Ran MockCommand command1\n", log.getvalue())

    self.assertEquals("mock_command command1\n"
                      "mock_command command2\n", _print_command(command))

  def testConditionalCommand(self):
    dir = VirtualDirectory()

    inputs = [ Artifact("input1", None), Artifact("input2", None) ]
    outputs = [ Artifact("output1", None), Artifact("output2", None) ]
    condition = Artifact("condition", None)

    mock_command1 = MockCommand("command1", inputs[:1], outputs[:1])
    mock_command2 = MockCommand("command2", inputs[1:], outputs[1:])
    command = ConditionalCommand(condition, mock_command1, mock_command2)

    enumerator = MockArtifactEnumerator()
    command.enumerate_artifacts(enumerator)
    self.assertEquals([condition], enumerator.reads)
    self.assertEquals([], enumerator.inputs)
    self.assertEquals([], enumerator.outputs)

    enumerator = MockArtifactEnumerator({condition: "true"})
    command.enumerate_artifacts(enumerator)
    self.assertEquals([condition], enumerator.reads)
    self.assertEquals(inputs[:1], enumerator.inputs)
    self.assertEquals(outputs[:1], enumerator.outputs)

    enumerator = MockArtifactEnumerator({condition: "false"})
    command.enumerate_artifacts(enumerator)
    self.assertEquals([condition], enumerator.reads)
    self.assertEquals(inputs[1:], enumerator.inputs)
    self.assertEquals(outputs[1:], enumerator.outputs)

    enumerator = MockArtifactEnumerator({condition: "blah"})
    command.enumerate_artifacts(enumerator)
    self.assertEquals([condition], enumerator.reads)
    self.assertEquals([], enumerator.inputs)
    self.assertEquals([], enumerator.outputs)

    context = MockCommandContext(dir)

    dir.write("condition", "true")
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertEquals("Ran MockCommand command1\n", log.getvalue())

    mock_command1.fails = True
    log = cStringIO.StringIO()
    self.assertFalse(command.run(context, log))
    self.assertEquals("Ran MockCommand command1\n", log.getvalue())

    dir.write("condition", "false")
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertEquals("Ran MockCommand command2\n", log.getvalue())

    mock_command2.fails = True
    log = cStringIO.StringIO()
    self.assertFalse(command.run(context, log))
    self.assertEquals("Ran MockCommand command2\n", log.getvalue())

    dir.write("condition", "blah")
    log = cStringIO.StringIO()
    self.assertFalse(command.run(context, log))
    self.assertEquals(
        "Condition artifact was not true or false: %s\n" % condition,
        log.getvalue())

    self.assertEquals(
        "if condition {\n"
        "  mock_command command1\n"
        "} else {\n"
        "  mock_command command2\n"
        "}\n",
        _print_command(command))

  def testConditionalCommandWithNoElse(self):
    dir = VirtualDirectory()

    inputs = [ Artifact("input1", None), Artifact("input2", None) ]
    outputs = [ Artifact("output1", None), Artifact("output2", None) ]
    condition = Artifact("condition", None)

    mock_command1 = MockCommand("command1", inputs[:1], outputs[:1])
    command = ConditionalCommand(condition, mock_command1)

    enumerator = MockArtifactEnumerator()
    command.enumerate_artifacts(enumerator)
    self.assertEquals([condition], enumerator.reads)
    self.assertEquals([], enumerator.inputs)
    self.assertEquals([], enumerator.outputs)

    enumerator = MockArtifactEnumerator({condition: "true"})
    command.enumerate_artifacts(enumerator)
    self.assertEquals([condition], enumerator.reads)
    self.assertEquals(inputs[:1], enumerator.inputs)
    self.assertEquals(outputs[:1], enumerator.outputs)

    enumerator = MockArtifactEnumerator({condition: "false"})
    command.enumerate_artifacts(enumerator)
    self.assertEquals([condition], enumerator.reads)
    self.assertEquals([], enumerator.inputs)
    self.assertEquals([], enumerator.outputs)

    enumerator = MockArtifactEnumerator({condition: "blah"})
    command.enumerate_artifacts(enumerator)
    self.assertEquals([condition], enumerator.reads)
    self.assertEquals([], enumerator.inputs)
    self.assertEquals([], enumerator.outputs)

    context = MockCommandContext(dir)

    dir.write("condition", "true")
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertEquals("Ran MockCommand command1\n", log.getvalue())

    mock_command1.fails = True
    log = cStringIO.StringIO()
    self.assertFalse(command.run(context, log))
    self.assertEquals("Ran MockCommand command1\n", log.getvalue())

    dir.write("condition", "false")
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertEquals("", log.getvalue())

    dir.write("condition", "blah")
    log = cStringIO.StringIO()
    self.assertFalse(command.run(context, log))
    self.assertEquals(
        "Condition artifact was not true or false: %s\n" % condition,
        log.getvalue())

    self.assertEquals(
        "if condition {\n"
        "  mock_command command1\n"
        "}\n",
        _print_command(command))

class SubprocessCommandTest(unittest.TestCase):
  def setUp(self):
    self.__action = Action(None, "dummy", "dummy")
    self.__artifact = Artifact("filename", None)
    self.__dir = VirtualDirectory()

  def testVerifyArgs(self):
    action = self.__action
    artifact = self.__artifact

    self.assertRaises(TypeError, SubprocessCommand, action, [0])
    self.assertRaises(TypeError, SubprocessCommand, action, [[0]])
    self.assertRaises(TypeError, SubprocessCommand, action, [artifact, 0])

    SubprocessCommand(action, ["foo"])
    SubprocessCommand(action, [artifact])
    SubprocessCommand(action, [artifact])
    SubprocessCommand(action, [[artifact]])
    SubprocessCommand(action, [[artifact]])
    SubprocessCommand(action, [artifact.contents()])

  def testEnumerateArtifacts(self):
    action = self.__action

    inputs = [ Artifact("input1", None), Artifact("input2", None) ]
    outputs = [ Artifact("output1", action), Artifact("output2", action) ]

    command = SubprocessCommand(action, ["foo", inputs[0], outputs[0]],
                                implicit = [inputs[1], outputs[1]])
    enumerator = MockArtifactEnumerator()
    command.enumerate_artifacts(enumerator)
    self.assertEquals([], enumerator.reads)
    self.assertEquals(set(inputs), set(enumerator.inputs))
    self.assertEquals(set(outputs), set(enumerator.outputs))

    stdout = Artifact("stdout", None)
    stderr = Artifact("stderr", None)
    exit_code = Artifact("error_code", None)
    command = SubprocessCommand(action, inputs + outputs,
                                capture_stdout = stdout,
                                capture_stderr = stderr,
                                capture_exit_status = exit_code)
    enumerator = MockArtifactEnumerator()
    command.enumerate_artifacts(enumerator)
    self.assertEquals([], enumerator.reads)
    self.assertEquals(set(inputs), set(enumerator.inputs))
    self.assertEquals(set(outputs + [stdout, stderr, exit_code]),
                      set(enumerator.outputs))

  def testFormatArgs(self):
    artifact = self.__artifact

    self.__dir.write(self.__artifact.filename, "content")

    self.assertFormattedAs(["foo"], ["foo"])
    self.assertFormattedAs([artifact], ["disk/filename"], "filename")
    self.assertFormattedAs([artifact.contents()],
                           ["content"], "$(filename)")
    self.assertFormattedAs([["foo"]], ["foo"])
    self.assertFormattedAs([[artifact]], ["disk/filename"], "filename")
    self.assertFormattedAs([[artifact.contents()]],
                           ["content"], "$(filename)")

    self.assertFormattedAs(["foo", ["bar", ["baz", "qux"], "corge"], "grault"],
                           ["foo", "barbazquxcorge", "grault"])

    self.assertFormattedAs(["(", artifact, ")"],
                           ["(", "disk/filename", ")"],
                           "( filename )")
    self.assertFormattedAs([["(", artifact, ")"]],
                           ["(disk/filename)"],
                           "(filename)")

    self.__dir.write(self.__artifact.filename, "content   with\nspaces")

    self.assertFormattedAs(["(", artifact.contents(), ")"],
                           ["(", "content", "with", "spaces", ")"],
                           "( $(filename) )")
    self.assertFormattedAs([["(", artifact.contents(), ")"]],
                           ["(content   with\nspaces)"],
                           "($(filename))")

    self.assertFormattedAs(["(", SubprocessCommand.Quoted(["foo bar", "baz"]),
                            ")"],
                           ["(", "'foo bar' baz", ")"])
    self.assertFormattedAs([SubprocessCommand.Quoted(["'hello'"])],
                           ["\"'hello'\""])
    self.assertFormattedAs([SubprocessCommand.Quoted(["(", artifact, ")"])],
                           ["'(' disk/filename ')'"],
                           "'(' filename ')'")

  def assertFormattedAs(self, args, result, printed = None):
    context = MockCommandContext(self.__dir, diskpath_prefix = "disk/")
    command = SubprocessCommand(self.__action, list(args))
    self.assertTrue(command.run(context, cStringIO.StringIO()))
    self.assertEquals(result, context.subprocess_args)

    if printed is None:
      printed = " ".join(result)
    self.assertEquals(printed + "\n", _print_command(command))

  def testRedirectStreams(self):
    # No redirection.
    command = SubprocessCommand(self.__action, ["foo"])
    context = MockCommandContext(self.__dir)
    context.subprocess_result = (0, "some text", None)
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertTrue(context.subprocess_kwargs["stdout"] is subprocess.PIPE)
    self.assertTrue(context.subprocess_kwargs["stderr"] is subprocess.STDOUT)
    self.assertEquals("some text", log.getvalue())
    self.assertEquals("foo\n", _print_command(command))

    # Redirect stdout.
    command = SubprocessCommand(self.__action, ["foo"],
                                capture_stdout = self.__artifact)
    context = MockCommandContext(self.__dir)
    context.subprocess_result = (0, "some text", "error text")
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertTrue(context.subprocess_kwargs["stdout"] is subprocess.PIPE)
    self.assertTrue(context.subprocess_kwargs["stderr"] is subprocess.PIPE)
    self.assertEquals("some text", self.__dir.read("filename"))
    self.assertEquals("error text", log.getvalue())
    self.assertEquals("foo > filename\n", _print_command(command))

    # Redirect stderr.
    command = SubprocessCommand(self.__action, ["foo"],
                                capture_stderr = self.__artifact)
    context = MockCommandContext(self.__dir)
    context.subprocess_result = (0, "some text", "error text")
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    # TODO(kenton): Uncomment when bug with writing to log is solved.
    #self.assertTrue(context.subprocess_kwargs["stdout"] is log)
    self.assertTrue(context.subprocess_kwargs["stdout"] is subprocess.PIPE)
    self.assertTrue(context.subprocess_kwargs["stderr"] is subprocess.PIPE)
    self.assertEquals("some text", log.getvalue())
    self.assertEquals("error text", self.__dir.read("filename"))
    self.assertEquals("foo 2> filename\n", _print_command(command))

    # Redirect both.
    command = SubprocessCommand(self.__action, ["foo"],
                                capture_stdout = self.__artifact,
                                capture_stderr = Artifact("file2", None))
    context = MockCommandContext(self.__dir)
    context.subprocess_result = (0, "output", "error")
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertTrue(context.subprocess_kwargs["stdout"] is subprocess.PIPE)
    self.assertTrue(context.subprocess_kwargs["stderr"] is subprocess.PIPE)
    self.assertEquals("output", self.__dir.read("filename"))
    self.assertEquals("error", self.__dir.read("file2"))
    self.assertEquals("foo > filename 2> file2\n", _print_command(command))

    # Redirect both to same destination.
    command = SubprocessCommand(self.__action, ["foo"],
                                capture_stdout = self.__artifact,
                                capture_stderr = self.__artifact)
    context = MockCommandContext(self.__dir)
    context.subprocess_result = (0, "combined text", None)
    log = cStringIO.StringIO()
    self.assertTrue(command.run(context, log))
    self.assertTrue(context.subprocess_kwargs["stdout"] is subprocess.PIPE)
    self.assertTrue(context.subprocess_kwargs["stderr"] is subprocess.STDOUT)
    self.assertEquals("combined text", self.__dir.read("filename"))
    self.assertEquals("foo > filename 2>&1\n", _print_command(command))

  def testExitStatus(self):
    command = SubprocessCommand(self.__action, ["foo"])

    context = MockCommandContext(self.__dir)
    context.subprocess_result = (0, "", None)
    self.assertTrue(command.run(context, cStringIO.StringIO()))

    context = MockCommandContext(self.__dir)
    context.subprocess_result = (1, "", None)
    self.assertFalse(command.run(context, cStringIO.StringIO()))

    context = MockCommandContext(self.__dir)
    context.subprocess_result = (-1, "", None)
    self.assertFalse(command.run(context, cStringIO.StringIO()))

    # Redirect exit status.
    command = SubprocessCommand(self.__action, ["foo"],
                                capture_exit_status = self.__artifact)
    self.assertEquals("foo && echo true > filename || echo false > filename\n",
                      _print_command(command))

    context = MockCommandContext(self.__dir)
    context.subprocess_result = (0, "", None)
    self.assertTrue(command.run(context, cStringIO.StringIO()))
    self.assertEquals("true", self.__dir.read("filename"))

    context = MockCommandContext(self.__dir)
    context.subprocess_result = (1, "", None)
    self.assertTrue(command.run(context, cStringIO.StringIO()))
    self.assertEquals("false", self.__dir.read("filename"))

if __name__ == "__main__":
  unittest.main()
