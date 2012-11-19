#! /bin/bash
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

set -e

function expect_contains() {
  if ! grep -q "$2" $1; then
    echo "Missing expected output: $2" >&2
    exit 1
  fi
}

function expect_success() {
  if ! eval $1 &> output.txt; then
    echo "Command was expected to succeed: $1" >&2
    echo "Output was:" >&2
    cat output.txt >&2
    exit 1
  fi
}

function expect_failure() {
  if eval $1 &> output.txt; then
    echo "Command was expected to fail: $1" >&2
    echo "Output was:" >&2
    cat output.txt >&2
    exit 1
  fi
}

OUTPUT=output.txt
SEBS=bin/sebs

# Temporary save bin/sebs.
ln -f bin/sebs sebs

echo "Cleaning..."

expect_success "$SEBS clean"

# Verify clean actually worked.
expect_failure "test -e tmp"
expect_failure "test -e bin"
expect_failure "test -e lib"

# Restore bin/sebs.
mkdir bin
mv sebs bin/sebs

echo "Building test binary..."

expect_success "$SEBS build sebs/cpp_test/cpp_test.sebs:prog"

expect_contains output.txt '> compile: src/sebs/cpp_test/main.cc$'
expect_contains output.txt '> compile: src/sebs/cpp_test/bar.cc$'
expect_contains output.txt '> link: sebs/cpp_test/cpp_test.sebs:bar$'
expect_contains output.txt '> compile: src/sebs/cpp_test/foo.cc$'
expect_contains output.txt '> link: sebs/cpp_test/cpp_test.sebs:foo$'
expect_contains output.txt '> link: sebs/cpp_test/cpp_test.sebs:prog$'

echo "Touching header and recompiling..."

sleep 2  # Avoid 1-second grace period in timestamp comparison.

# foo.h might be a link to the original source file, which we don't want to
# touch.  Make a copy to avoid this.
mv src/sebs/cpp_test/foo.h foo.h
cp foo.h src/sebs/cpp_test/foo.h
rm foo.h

# Now safe to touch.
touch src/sebs/cpp_test/foo.h
expect_success "$SEBS build sebs/cpp_test/cpp_test.sebs:prog"

# Note:  Several of these might be prefixed with "no changes:".
expect_contains output.txt 'compile: src/sebs/cpp_test/main.cc$'
expect_contains output.txt 'compile: src/sebs/cpp_test/bar.cc$'
expect_contains output.txt 'link: sebs/cpp_test/cpp_test.sebs:bar$'
expect_contains output.txt 'compile: src/sebs/cpp_test/foo.cc$'
expect_contains output.txt 'link: sebs/cpp_test/cpp_test.sebs:foo$'
expect_contains output.txt 'link: sebs/cpp_test/cpp_test.sebs:prog$'

echo "Running test binary..."

expect_success "bin/sebs_cpp_test"

expect_contains output.txt '^FooFunction(foo) BarFunction(bar) FooFunction(bar) $'

echo "Running passing test..."

expect_success "$SEBS test sebs/cpp_test/cpp_test.sebs:passing_test"

expect_contains output.txt '> PASS: test: sebs/cpp_test/cpp_test.sebs:passing_test$'

expect_contains tmp/sebs/cpp_test/passing_test_output.txt \
  '^BarFunction(test) FooFunction(test) $'

echo "Running failing test..."

expect_failure "$SEBS test sebs/cpp_test/cpp_test.sebs:failing_test"

expect_contains output.txt '> FAIL: test: sebs/cpp_test/cpp_test.sebs:failing_test$'

expect_contains tmp/sebs/cpp_test/failing_test_output.txt \
  '^FooFunction(fail) $'

echo "PASS"
