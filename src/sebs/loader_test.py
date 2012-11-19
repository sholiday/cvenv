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

import unittest

from sebs.core import Rule, Test, DefinitionError
from sebs.filesystem import VirtualDirectory
from sebs.loader import Loader

class LoaderTest(unittest.TestCase):
  def setUp(self):
    self.dir = VirtualDirectory()
    self.loader = Loader(self.dir)

  def testBasics(self):
    self.dir.add("src/foo.sebs", 0, """
x = 123
_private = "hi"
a_rule = sebs.Rule()
nested_rule = [sebs.Rule()]
def func():
  return _private
""")
    file = self.loader.load("foo.sebs")

    self.assertTrue("sebs" not in file.__dict__)
    self.assertTrue("_private" not in file.__dict__)
    self.assertEqual(123, file.x)
    self.assertEqual("a_rule", file.a_rule.label)
    self.assertTrue(file.nested_rule[0].label is None)
    self.assertEqual(4, file.a_rule.line)
    self.assertEqual(5, file.nested_rule[0].line)
    self.assertEqual("foo.sebs:a_rule", file.a_rule.name)
    self.assertEqual("foo.sebs:5", file.nested_rule[0].name)
    self.assertEqual("hi", file.func())

  def testImport(self):
    self.dir.add("src/foo.sebs", 0, """bar = sebs.import_("bar.sebs")""")
    self.dir.add("src/bar.sebs", 0, """x = 123""")
    file = self.loader.load("foo.sebs")
    self.assertTrue(file.bar is self.loader.load("bar.sebs"))
    self.assertEqual(123, file.bar.x)

  def testCycle(self):
    self.dir.add("src/foo.sebs", 0, """sebs.import_("foo.sebs")""")
    self.assertRaises(DefinitionError, self.loader.load, "foo.sebs")

  def testAbsoluteImport(self):
    self.dir.add("src/foo/foo.sebs", 0, """
bar1 = sebs.import_("bar.sebs")
bar2 = sebs.import_("//foo/bar.sebs")
bar3 = sebs.import_("//bar/bar.sebs")
""")
    self.dir.add("src/foo/bar.sebs", 0, """x = 123""")
    self.dir.add("src/bar/bar.sebs", 0, """x = 321""")
    file = self.loader.load("foo/foo.sebs")
    self.assertTrue(file.bar1 is self.loader.load("foo/bar.sebs"))
    self.assertTrue(file.bar2 is self.loader.load("foo/bar.sebs"))
    self.assertTrue(file.bar3 is self.loader.load("bar/bar.sebs"))
    self.assertEqual(123, file.bar1.x)
    self.assertEqual(123, file.bar2.x)
    self.assertEqual(321, file.bar3.x)

  def testLazyImportProhibited(self):
    self.dir.add("src/foo.sebs", 0, "x = sebs")
    self.dir.add("src/bar.sebs", 0, "")
    foo = self.loader.load("foo.sebs")
    bar = self.loader.load("bar.sebs")
    self.assertRaises(DefinitionError, foo.x.import_, "bar.sebs")

  def testOverrideBuiltins(self):
    self.dir.add("src/foo.sebs", 0, """sebs = 123""")
    file = self.loader.load("foo.sebs")

    self.assertEqual(123, file.sebs)

  def testLoadDirectory(self):
    self.dir.add("src/foo/bar/SEBS", 0, "x = 123")
    file = self.loader.load("foo/bar")
    self.assertEqual(123, file.x)

  def testLoadTarget(self):
    self.dir.add("src/foo/bar/SEBS", 0, "x = 123")
    self.dir.add("src/baz.sebs", 0, "y = 'abc'")
    self.assertEqual(123, self.loader.load("foo/bar:x"))
    self.assertEqual("abc", self.loader.load("baz.sebs:y"))

  def testTimestamp(self):
    self.dir.add("src/foo.sebs", 1, """""")
    self.dir.add("src/bar.sebs", 0, """sebs.import_("foo.sebs")""")
    self.dir.add("src/baz.sebs", 2, """sebs.import_("foo.sebs")""")
    self.dir.add("src/qux.sebs", 0, """sebs.import_("bar.sebs")""")
    self.dir.add("src/quux.sebs", 0, """
sebs.import_("baz.sebs")
sebs.import_("qux.sebs")
""")

    self.assertEqual(1, self.loader.load_with_timestamp("foo.sebs")[1])
    self.assertEqual(1, self.loader.load_with_timestamp("bar.sebs")[1])
    self.assertEqual(2, self.loader.load_with_timestamp("baz.sebs")[1])
    self.assertEqual(1, self.loader.load_with_timestamp("qux.sebs")[1])
    self.assertEqual(2, self.loader.load_with_timestamp("quux.sebs")[1])

class _MockGlobbingVirtualDirectory(VirtualDirectory):
  def expand_glob(self, pattern):
    if pattern == "src/foo/*":
      return ["src/foo/qux", "src/foo/corge"]
    else:
      return [pattern]

class ContextImplTest(unittest.TestCase):
  def setUp(self):
    self.dir = _MockGlobbingVirtualDirectory()
    self.dir.add("src/foo/bar.sebs", 0, """
mock_rule = sebs.Rule()
return_context = mock_rule.context
mock_test = sebs.Test()
""")

    self.loader = Loader(self.dir)
    self.file = self.loader.load("foo/bar.sebs")
    self.context = self.file.return_context

  def testBasics(self):
    self.assertEqual("foo/bar.sebs", self.context.filename)
    self.assertEqual("src/foo/bar.sebs", self.context.full_filename)

  def testRules(self):
    self.assertTrue(isinstance(self.file.mock_rule, Rule))
    self.assertTrue(isinstance(self.file.mock_test, Test))
    self.assertTrue(self.file.mock_test.context is self.context)

  def testSourceArtifact(self):
    artifact1 = self.context.source_artifact("qux")
    artifact2 = self.context.source_artifact("corge")
    self.assertTrue(artifact1 is self.context.source_artifact("qux"))
    self.assertEqual("src/foo/qux", artifact1.filename)
    self.assertTrue(artifact1.action is None)
    self.assertFalse(artifact2 is artifact1)
    self.assertTrue(self.context.source_artifact(artifact1) is artifact1)

    self.assertEqual("qux", self.context.local_filename(artifact1))
    self.assertEqual("corge", self.context.local_filename(artifact2))
    self.assertEqual("qux", self.context.local_filename("qux"))
    self.assertEqual("corge", self.context.local_filename("corge"))

    # Trying to create an artifact outside the directory fails.
    self.assertRaises(DefinitionError,
        self.context.source_artifact, "../parent")

    self.assertEqual([artifact1], self.context.source_artifact_list(["qux"]))
    self.assertEqual([artifact2], self.context.source_artifact_list(["corge"]))
    self.assertEqual(set([artifact1, artifact2]),
                     set(self.context.source_artifact_list(["*"])))

  def testAction(self):
    artifact = self.loader.source_artifact("blah")
    action = self.context.action(self.file.mock_rule, "run", "foo")

    self.assertEqual("run", action.verb)
    self.assertEqual("foo", action.name)

    action2 = self.context.action(self.file.mock_rule)

    self.assertEqual("run", action.verb)
    self.assertEqual("foo", action.name)
    self.assertEqual("build", action2.verb)
    self.assertEqual("foo/bar.sebs:mock_rule", action2.name)

  def testDerivedArtifact(self):
    action = self.context.action(self.file.mock_rule)

    tmp_artifact = self.context.intermediate_artifact("grault", action)
    self.assertEqual("tmp/foo/grault", tmp_artifact.filename)
    self.assertTrue(tmp_artifact.action is action)
    self.assertEqual("grault", self.context.local_filename(tmp_artifact))

    mem_artifact = self.context.memory_artifact("plugh", action)
    self.assertEqual("mem/foo/plugh", mem_artifact.filename)
    self.assertTrue(mem_artifact.action is action)
    self.assertEqual("plugh", self.context.local_filename(mem_artifact))

    bin_artifact = self.context.output_artifact("bin", "garply", action)
    self.assertEqual("bin/garply", bin_artifact.filename)
    self.assertTrue(bin_artifact.action is action)
    self.assertTrue(self.context.local_filename(bin_artifact) is None)

    # Creating the same temporary artifact twice fails.
    self.assertRaises(DefinitionError,
        self.context.intermediate_artifact, "grault", action)
    self.assertRaises(DefinitionError,
        self.context.memory_artifact, "plugh", action)

    # Trying to create an artifact outside the directory fails.
    self.assertRaises(DefinitionError,
        self.context.intermediate_artifact, "../parent", action)
    self.assertRaises(DefinitionError,
        self.context.intermediate_artifact, "/root", action)
    self.assertRaises(DefinitionError,
        self.context.memory_artifact, "../parent", action)
    self.assertRaises(DefinitionError,
        self.context.memory_artifact, "/root", action)

    # Creating the same output artifact twice fails.
    self.assertRaises(DefinitionError,
        self.context.output_artifact, "bin", "garply", action)

    # Only certain directories are allowable for output artifact.s
    self.assertRaises(DefinitionError,
        self.context.output_artifact, "baddir", "waldo", action)

if __name__ == "__main__":
  unittest.main()
