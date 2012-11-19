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

# TODO(kenton): Test DryRunner and SubprocessRunner.

import unittest
import cStringIO

from sebs.core import Artifact, Action, Rule, Context, DefinitionError
from sebs.filesystem import VirtualDirectory
from sebs.builder import Builder
from sebs.command import Command
from sebs.console import make_console
from sebs.runner import ActionRunner

class MockRunner(ActionRunner):
  def __init__(self):
    self.actions = []

  def run(self, action, inputs, disk_inputs, outputs, test_result, config,
          real_name_map, lock):
    self.actions.append(action)

    # Hack for testDerivedCondition:  If the action is condition_builder then
    # copy cond_dep to cond.
    if action.name == "condition_builder":
      config.root_dir.write("cond", config.root_dir.read("cond_dep"))

    for artifact in inputs + outputs:
      if artifact not in real_name_map:
        raise AssertionError("%s is not in real_name_map." % artifact)
      if artifact.filename != real_name_map[artifact]:
        raise AssertionError("%s had name %s in real_name_map." %
            (artifact, real_name_map[artifact]))

    return True

class MockContext(Context):
  def __init__(self, filename, full_filename):
    super(MockContext, self).__init__()
    self.filename = filename
    self.full_filename = full_filename
    self.timestamp = 0

class MockCommand(Command):
  def __init__(self, inputs, outputs):
    self.__inputs = inputs
    self.__outputs = outputs

  def enumerate_artifacts(self, artifact_enumerator):
    for input in self.__inputs:
      artifact_enumerator.add_input(input)
    for output in self.__outputs:
      artifact_enumerator.add_output(output)

class ConditionalMockCommand(Command):
  def __init__(self, condition, inputs, conditional_inputs, outputs):
    self.__condition = condition
    self.__inputs = inputs
    self.__conditional_inputs = conditional_inputs
    self.__outputs = outputs

  def enumerate_artifacts(self, artifact_enumerator):
    for input in self.__inputs:
      artifact_enumerator.add_input(input)
    if artifact_enumerator.read(self.__condition) == "true":
      for input in self.__conditional_inputs:
        artifact_enumerator.add_input(input)
    for output in self.__outputs:
      artifact_enumerator.add_output(output)

class MockConfiguration(object):
  def __init__(self, dir):
    self.root_dir = dir

class BuilderTest(unittest.TestCase):
  def setUp(self):
    self.dir = VirtualDirectory()
    self.context = MockContext("mock.sebs", "src/mock.sebs")
    self.rule = Rule(self.context)
    self.console = make_console(cStringIO.StringIO())  # ignore output

  def doBuild(self, *artifacts):
    builder = Builder(self.console)
    runner = MockRunner()
    config = MockConfiguration(self.dir)
    for artifact in artifacts:
      builder.add_artifact(config, artifact)
    builder.build(runner)
    return runner.actions

  def testNoAciton(self):
    input = Artifact("input", None)

    self.assertRaises(DefinitionError, self.doBuild, input)
    self.dir.add("input", 20, "")
    self.assertEqual([], self.doBuild(input))

  def testSimpleAction(self):
    input = Artifact("input", None)
    action = Action(self.rule, "")
    output = Artifact("output", action)
    action.command = MockCommand([input], [output])

    # output doesn't exist.
    self.dir.add("input", 20, "")
    self.assertEqual([action], self.doBuild(output))

    # output exists but is older than input.
    self.dir.add("output", 10, "")
    self.assertEqual([action], self.doBuild(output))

    # output exists and is newer than input.
    self.dir.add("output", 40, "")
    self.assertEqual([], self.doBuild(output))

    # SEBS file is newer than output.
    self.context.timestamp = 50
    self.assertEqual([action], self.doBuild(output))

  def testMultipleInputsAndOutputs(self):
    in1 = Artifact("in1", None)
    in2 = Artifact("in2", None)
    action = Action(self.rule, "")
    out1 = Artifact("out1", action)
    out2 = Artifact("out2", action)
    action.command = MockCommand([in1, in2], [out1, out2])

    # outputs don't exist.
    self.dir.add("in1", 20, "")
    self.dir.add("in2", 40, "")
    self.assertEqual([action], self.doBuild(out1, out2))

    # only one output exists
    self.dir.add("out1", 50, "")
    self.assertEqual([action], self.doBuild(out1, out2))
    self.assertEqual([], self.doBuild(out1))

    # both outputs exist, one is outdated
    self.dir.add("out2", 10, "")
    self.assertEqual([action], self.doBuild(out1, out2))
    self.assertEqual([], self.doBuild(out1))

    # both outputs exist, one is older than *one* of the inputs
    self.dir.add("out2", 30, "")
    self.assertEqual([action], self.doBuild(out1, out2))
    self.assertEqual([], self.doBuild(out1))

    # both outputs exist and are up-to-date.
    self.dir.add("out2", 50, "")
    self.assertEqual([], self.doBuild(out1, out2))

  def testActionWithDependency(self):
    input = Artifact("input", None)
    action1 = Action(self.rule, "")
    temp = Artifact("temp", action1)
    action1.command = MockCommand([input], [temp])
    action2 = Action(self.rule, "")
    output = Artifact("output", action2)
    action2.command = MockCommand([temp], [output])

    # outputs don't exist.
    self.dir.add("input", 20, "")
    self.assertEqual([action1, action2], self.doBuild(output))
    self.assertEqual([action1], self.doBuild(temp))

    # temp exists but is outdated.
    self.dir.add("temp", 10, "")
    self.assertEqual([action1, action2], self.doBuild(output))
    self.assertEqual([action1], self.doBuild(temp))

    # temp exists and is up-to-date.
    self.dir.add("temp", 30, "")
    self.assertEqual([action2], self.doBuild(output))
    self.assertEqual([], self.doBuild(temp))

    # output exists but is outdated.
    self.dir.add("output", 10, "")
    self.assertEqual([action2], self.doBuild(output))
    self.assertEqual([], self.doBuild(temp))

    # output exists and is up-to-date.
    self.dir.add("output", 40, "")
    self.assertEqual([], self.doBuild(output))
    self.assertEqual([], self.doBuild(temp))

    # temp is outdated but output is up-to-date.
    self.dir.add("temp", 10, "")
    self.assertEqual([action1, action2], self.doBuild(output))
    self.assertEqual([action1], self.doBuild(temp))

  def testDiamondDependency(self):
    input = Artifact("input", None)
    action1 = Action(self.rule, "")
    temp1 = Artifact("temp1", action1)
    action1.command = MockCommand([input], [temp1])
    action2 = Action(self.rule, "")
    temp2 = Artifact("temp2", action2)
    action2.command = MockCommand([input], [temp2])
    action3 = Action(self.rule, "")
    output = Artifact("output", action3)
    action3.command = MockCommand([temp1, temp2], [output])

    # outputs don't exist.
    self.dir.add("input", 20, "")
    self.assertEqual([action1, action2, action3], self.doBuild(output))
    self.assertEqual([action1], self.doBuild(temp1))
    self.assertEqual([action2], self.doBuild(temp2))

    # one side is up-to-date, other isn't.
    self.dir.add("temp1", 30, "")
    self.dir.add("output", 40, "")
    self.assertEqual([action2, action3], self.doBuild(output))
    self.assertEqual([], self.doBuild(temp1))
    self.assertEqual([action2], self.doBuild(temp2))

    # everything up-to-date.
    self.dir.add("temp2", 30, "")
    self.assertEqual([], self.doBuild(output))
    self.assertEqual([], self.doBuild(temp1))
    self.assertEqual([], self.doBuild(temp2))

    # original input too new.
    self.dir.add("input", 60, "")
    self.assertEqual([action1, action2, action3], self.doBuild(output))
    self.assertEqual([action1], self.doBuild(temp1))
    self.assertEqual([action2], self.doBuild(temp2))

  def testConditionalInputs(self):
    input = Artifact("input", None)
    condition = Artifact("cond", None)
    conditional_action = Action(self.rule, "", "conditional_action")
    conditional_input = Artifact("cond_input", conditional_action)
    conditional_action.command = MockCommand([], [conditional_input])
    action = Action(self.rule, "", "action")
    output = Artifact("output", action)
    action.command = ConditionalMockCommand(
        condition, [input], [conditional_input], [output])

    # output doesn't exist, condition is false.
    self.dir.add("cond", 20, "false")
    self.dir.add("input", 20, "")
    self.assertEqual([action], self.doBuild(output))

    # output exists, condition still false.
    self.dir.add("output", 30, "")
    self.assertEqual([], self.doBuild(output))

    # condition newer than output.
    self.dir.add("cond", 40, "")
    self.assertEqual([action], self.doBuild(output))
    self.dir.add("cond", 20, "")

    # input newer than output.
    self.dir.add("input", 40, "")
    self.assertEqual([action], self.doBuild(output))
    self.dir.add("input", 20, "")

    # condition is true, cond_input doesn't exist.
    self.dir.add("cond", 20, "true")
    self.assertEqual([conditional_action, action], self.doBuild(output))

    # cond_input newer than output -- doesn't matter since cond is false.
    self.dir.add("cond_input", 40, "")
    self.dir.add("cond", 20, "false")
    self.assertEqual([], self.doBuild(output))

    # condition is true, cond_input is newer than output.
    self.dir.add("cond", 20, "true")
    self.assertEqual([action], self.doBuild(output))

    # output newer than cond_input.
    self.dir.add("cond_input", 20, "")
    self.assertEqual([], self.doBuild(output))

  def testDerivedCondition(self):
    condition_dep = Artifact("cond_dep", None)

    # Note that MockRunner special-cases this action to make it copy cond_dep
    # to cond.
    condition_builder = Action(self.rule, "", "condition_builder")
    condition = Artifact("cond", condition_builder)
    condition_builder.command = MockCommand([condition_dep], [condition])

    conditional_action = Action(self.rule, "", "conditional_action")
    conditional_input = Artifact("cond_input", conditional_action)
    conditional_action.command = MockCommand([], [conditional_input])

    action = Action(self.rule, "", "action")
    output = Artifact("output", action)
    action.command = ConditionalMockCommand(
        condition, [], [conditional_input], [output])

    # Condition is false.
    self.dir.add("cond_dep", 20, "false")
    self.assertEqual([condition_builder, action], self.doBuild(output))

    # Condition is "true" but will become "false" when rebuilt.  This should
    # not cause conditional_action to be triggered because action should not
    # be allowed to read "cond" while it is dirty.
    self.dir.add("cond_dep", 30, "false")
    self.dir.add("cond", 20, "true")
    self.assertEqual([condition_builder, action], self.doBuild(output))

    # Condition is "false" but will become "true" when rebuilt.  This should
    # trigger conditional_action *even though* conditional_input was not listed
    # among the inputs in the first pass.
    self.dir.add("cond_dep", 30, "true")
    self.dir.add("cond", 20, "false")
    self.assertEqual([condition_builder, conditional_action, action],
                     self.doBuild(output))

if __name__ == "__main__":
  unittest.main()
