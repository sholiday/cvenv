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

import traceback
import unittest

from sebs.core import Context, Rule, Artifact, Action, DefinitionError, \
                      ArgumentSpec

class MockContext(Context):
  def __init__(self, filename, full_filename):
    super(MockContext, self).__init__()
    self.filename = filename
    self.full_filename = full_filename

  def source_artifact(self, filename):
    if isinstance(filename, Artifact):
      return filename
    else:
      return Artifact("foo/" + filename, None)

  def source_artifact_list(self, filenames):
    result = []
    for filename in filenames:
      if not isinstance(filename, Artifact):
        filename = "glob(" + filename + ")"
      result.append(self.source_artifact(filename))
    return result

class MockRule(Rule):
  argument_spec = ArgumentSpec(int_arg = (int, 321),
                               list_int_arg = ([int], [6, 5, 4]),
                               artifact_arg = (Artifact, None),
                               list_artifact_arg = ([Artifact], []))

  def _expand(self, args):
    self.args = args

class RuleWithRequiredArg(Rule):
  argument_spec = ArgumentSpec(int_arg = int)

  def _expand(self, args):
    self.args = args

class CoreTest(unittest.TestCase):
  # There's really not that much that we can test here.

  def testCurrentContext(self):
    this_file, line, _, _ = traceback.extract_stack(limit = 1)[0]
    context = MockContext("foo.sebs", this_file)
    rule = context.run(Rule)
    self.assertTrue(Context.current() is None)
    self.assertTrue(rule.context is context)
    self.assertEqual(rule.line, line + 2)

    self.assertEqual("foo.sebs:%d" % (line + 2), rule.name)
    rule.label = "foo"
    self.assertEqual("foo.sebs:foo", rule.name)

  def testInitAndValidate(self):
    context = MockContext("foo.sebs", "foo.sebs")
    self.assertRaises(TypeError,
        MockRule(context = context, int_arg = "bar").expand_once)
    self.assertRaises(TypeError,
        MockRule(context = context, list_int_arg = 1))
    self.assertRaises(TypeError,
        MockRule(context = context, list_int_arg = ["bar"]))
    self.assertRaises(TypeError,
        MockRule(context = context, artifact_arg = 1))
    self.assertRaises(TypeError,
        RuleWithRequiredArg(context = context).expand_once)

    # Default values.
    rule = MockRule(context = context)
    rule.expand_once()
    self.assertEqual(321, rule.args.int_arg)
    self.assertEqual([6, 5, 4], rule.args.list_int_arg)
    self.assertEqual(None, rule.args.artifact_arg)
    self.assertEqual([], rule.args.list_artifact_arg)

    # Set everything.
    rule = MockRule(context = context,
                    int_arg = 123,
                    list_int_arg = [4, 5, 6],
                    artifact_arg = "baz",
                    list_artifact_arg = ["qux", "quux"])
    rule.expand_once()
    self.assertEqual(123, rule.args.int_arg)
    self.assertEqual([4, 5, 6], rule.args.list_int_arg)
    self.assertTrue(isinstance(rule.args.artifact_arg, Artifact))
    self.assertEqual("foo/baz", rule.args.artifact_arg.filename)
    self.assertTrue(isinstance(rule.args.list_artifact_arg, list))
    self.assertEqual(2, len(rule.args.list_artifact_arg))
    self.assertTrue(isinstance(rule.args.list_artifact_arg[0], Artifact))
    self.assertTrue(isinstance(rule.args.list_artifact_arg[1], Artifact))
    self.assertEqual("foo/glob(qux)",
                     rule.args.list_artifact_arg[0].filename)
    self.assertEqual("foo/glob(quux)",
                     rule.args.list_artifact_arg[1].filename)

    # Pass actual artifact for artifact params, instead of string.
    corge = Artifact("corge", None)
    rule = MockRule(context = context,
                    artifact_arg = corge,
                    list_artifact_arg = [corge, "garply"])
    rule.expand_once()
    self.assertEqual(corge, rule.args.artifact_arg)
    self.assertEqual(corge, rule.args.list_artifact_arg[0])
    self.assertEqual("foo/glob(garply)",
                     rule.args.list_artifact_arg[1].filename)

    # Miss
    rule = RuleWithRequiredArg(context = context, int_arg = 123)
    rule.expand_once()
    self.assertEqual(123, rule.args.int_arg)

if __name__ == "__main__":
  unittest.main()
