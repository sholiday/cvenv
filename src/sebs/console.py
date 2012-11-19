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
Implements fancy console output.
"""

from helpers import typecheck

class ColoredText(object):
  BLACK = 0
  RED = 1
  GREEN = 2
  YELLOW = 3
  BLUE = 4
  FUCHSIA = 5
  CYAN = 6
  WHITE = 7

  def __init__(self, color, text):
    typecheck(color, int)
    self.color = color
    self.text = text

class PendingMessage(object):
  def update(self, text):
    raise NotImplementedError

  def finish(self, final_text = None):
    raise NotImplementedError

class Console(object):
  def write(self, text):
    """Writes some text to the console.  |text| may be a string, a ColoredText
    object, or a list of strings and ColoredText objects."""

    raise NotImplementedError

  def add_pending(self, text):
    """Show a line of text as "pending", meaning that you intend to update it
    later.  Returns a PendingMessage object; call this object's finish() method
    to set the final text for the line.  Pending lines are always shown at the
    bottom of the console; text written with write() (or written when a pending
    line finishes) is inserted above them."""

    raise NotImplementedError

def make_console(out):
  if out.isatty():
    return _AnsiConsole(out)
  else:
    return _SerialConsole(out)

def _add_newline(text):
  if text == "" or text.endswith("\n"):
    return text
  else:
    return text + "\n"

# ====================================================================
# Boring serial output

class _SerialPendingMessage(PendingMessage):
  def __init__(self, console, text):
    self.console = console
    self.text = text

  def update(self, text):
    self.text = text

  def finish(self, final_text = None):
    if final_text is None:
      final_text = self.text
    self.console.write(final_text)

class _SerialConsole(Console):
  def __init__(self, out):
    self.__out = out
    self.__pending = []

  def write(self, text):
    self.__out.write("> " + _add_newline(self.__format_text(text)))
    self.__out.flush()

  def add_pending(self, text):
    self.__out.write("+ " + _add_newline(self.__format_text(text)))
    self.__out.flush()
    return _SerialPendingMessage(self, text)

  def _finish_pending(self, pending_message, final_text):
    self.__out.write(_add_newline(self.__format_text(final_text)))
    self.__out.flush()

  def __format_text(self, text):
    if isinstance(text, basestring):
      return text
    elif isinstance(text, ColoredText):
      return self.__format_text(text.text)
    elif isinstance(text, list):
      return "".join([ self.__format_text(t) for t in text ])
    else:
      raise TypeError("Text must be a string, ColoredText, or list.  Got: %s" %
                      text)

# ====================================================================
# ANSI terminal

_ANSI_COLOR_CODE = [
  "\033[30m",
  "\033[31m",
  "\033[32m",
  "\033[33m",
  "\033[1;34m",   # Blue is too hard to see on a black background if not bold.
  "\033[35m",
  "\033[36m",
  "\033[37m"
]

_ANSI_CLEAR_COLOR = "\033[0m"

_ANSI_MOVE_CURSOR_UP = "\033[%dF"

_ANSI_CLEAR_BELOW_CURSOR = "\033[0J"

class _AnsiPendingMessage(PendingMessage):
  def __init__(self, console, text):
    self.console = console
    self.text = text

  def update(self, text):
    self.text = text
    self.console._update_pending(self)

  def finish(self, final_text = None):
    if final_text is None:
      final_text = self.text
    self.console._finish_pending(self, final_text)

class _LineLimiter(object):
  def __init__(self, out, limit, line_cap):
    self.out = out
    self.limit = limit
    self.line_cap = line_cap
    self.pos = 0
    self.line_count = 0

  def write(self, text):
    if text.startswith('\033'):
      # ANSI control code.
      self.out.write(text)
    else:
      lines = text.split("\n")
      for line in lines[:-1]:
        self.__add(line)
        self.pos = 0
        self.out.write("\n")
        self.line_count = self.line_count + 1
      self.__add(lines[-1])

  def __add(self, text):
    old_pos = self.pos
    self.pos = old_pos + len(text)
    if old_pos > self.limit:
      pass
    elif self.pos > self.limit:
      self.out.write(text[:(self.limit - old_pos)])
      self.out.write(self.line_cap)
    else:
      self.out.write(text)

class _AnsiConsole(Console):
  def __init__(self, out):
    self.__out = out
    self.__pending = []
    self.pending_lines = 0

  def write(self, text):
    self.__clear_pending()
    self.__format_text(self.__out, text)
    self.__write_pending()

  def add_pending(self, text):
    self.__clear_pending()
    result = _AnsiPendingMessage(self, text)
    self.__pending.append(result)
    self.__write_pending()
    return result

  def _update_pending(self, pending_message):
    self.__clear_pending()
    self.__write_pending()

  def _finish_pending(self, pending_message, final_text):
    self.__clear_pending()
    self.__pending.remove(pending_message)
    self.__format_text(self.__out, final_text)
    self.__write_pending()

  def __clear_pending(self):
    if self.pending_lines > 0:
      self.__out.write(_ANSI_MOVE_CURSOR_UP % self.pending_lines)
      self.__out.write(_ANSI_CLEAR_BELOW_CURSOR)
      self.pending_lines = 0

  def __write_pending(self):
    if len(self.__pending) > 0:
      limiter = _LineLimiter(self.__out, 80, "\b\b\b...")

      for pending_message in self.__pending:
        limiter.write("*")
        self.__format_text(limiter, pending_message.text)

      self.pending_lines = limiter.line_count

  def __format_text(self, out, text,
                    add_newline = True, reset_color = _ANSI_CLEAR_COLOR):
    if isinstance(text, basestring):
      out.write(text)
      if text.endswith("\n"):
        add_newline = False
    elif isinstance(text, ColoredText):
      set_color = _ANSI_COLOR_CODE[text.color]
      out.write(set_color)
      self.__format_text(out, text.text, add_newline, set_color)
      add_newline = False
      out.write(reset_color)
    elif isinstance(text, list):
      if len(text) > 0:
        for part in text[:-1]:
          self.__format_text(out, part, False, reset_color)
        self.__format_text(out, text[-1], add_newline, reset_color)
        add_newline = False

    else:
      raise TypeError("Text must be a string, ColoredText, or list.  Got: %s" %
                      text)
    if add_newline:
      out.write("\n")
