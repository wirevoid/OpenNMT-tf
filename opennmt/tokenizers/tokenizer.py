# -*- coding: utf-8 -*-

"""Define base tokenizers."""

import sys
import abc
import six

import tensorflow as tf

from opennmt.utils.misc import print_bytes


@six.add_metaclass(abc.ABCMeta)
class Tokenizer(object):
  """Base class for tokenizers."""

  def make_assets(self, asset_dir, asset_prefix=""):  # pylint: disable=unused-argument
    """Builds assets of this tokenizer.

    Args:
      asset_dir: The directory where assets can be written.
      asset_prefix: The prefix to attach to assets filename.

    Returns:
      A dictionary containing additional assets used by the tokenizer.
    """
    return {}

  def tokenize_stream(self, input_stream=sys.stdin, output_stream=sys.stdout, delimiter=" "):
    """Tokenizes a stream of sentences.

    Args:
      input_stream: The input stream.
      output_stream: The output stream.
      delimiter: The token delimiter to use for text serialization.
    """
    for line in input_stream:
      line = line.strip()
      tokens = self.tokenize(line)
      merged_tokens = delimiter.join(tokens)
      print_bytes(tf.compat.as_bytes(merged_tokens), stream=output_stream)

  def detokenize_stream(self, input_stream=sys.stdin, output_stream=sys.stdout, delimiter=" "):
    """Detokenizes a stream of sentences.

    Args:
      input_stream: The input stream.
      output_stream: The output stream.
      delimiter: The token delimiter used for text serialization.
    """
    for line in input_stream:
      tokens = line.strip().split(delimiter)
      string = self.detokenize(tokens)
      print_bytes(tf.compat.as_bytes(string), stream=output_stream)

  def tokenize(self, text):
    """Tokenizes text.

    Args:
      text: The text to tokenize as a ``tf.Tensor`` or Python string.

    Returns:
      A 1-D string ``tf.Tensor`` if :obj:`text` is a ``tf.Tensor`` or a list of
      Python unicode strings otherwise.

    Raises:
      ValueError: if the rank of :obj:`text` is greater than 0.
    """
    if tf.contrib.framework.is_tensor(text):
      rank = len(text.get_shape().as_list())
      if rank == 0:
        return self._tokenize_tensor(text)
      else:
        raise ValueError("Unsupported tensor rank for tokenization: {}".format(rank))
    else:
      text = tf.compat.as_text(text)
      return self._tokenize_string(text)

  def detokenize(self, tokens, sequence_length=None):
    """Detokenizes tokens.

    The Tensor version supports batches of tokens.

    Args:
      tokens: The tokens as a 1-D or 2-D ``tf.Tensor`` or list of Python
        strings.
      sequence_length: The length of each sequence. Required if :obj:`tokens`
        is a ``tf.Tensor``.

    Returns:
      A 0-D or 1-D string ``tf.Tensor`` if :obj:`tokens` is a ``tf.Tensor`` or a
      Python unicode strings otherwise.

    Raises:
      ValueError: if the rank of :obj:`tokens` is greater than 2.
      ValueError: if :obj:`tokens` is a 2-D ``tf.Tensor`` and
        :obj:`sequence_length` is not set.
    """
    if tf.contrib.framework.is_tensor(tokens):
      rank = len(tokens.get_shape().as_list())
      if rank == 1:
        return self._detokenize_tensor(tokens)
      elif rank == 2:
        if sequence_length is None:
          raise ValueError("sequence_length is required for Tensor detokenization")
        return self._detokenize_batch_tensor(tokens, sequence_length)
      else:
        raise ValueError("Unsupported tensor rank for detokenization: {}".format(rank))
    else:
      tokens = [tf.compat.as_text(token) for token in tokens]
      return self._detokenize_string(tokens)

  def _tokenize_tensor(self, text):
    """Tokenizes a tensor.

    When not overriden, this default implementation uses a ``tf.py_function``
    operation to call the string-based tokenization.

    Args:
      text: A 1-D string ``tf.Tensor``.

    Returns:
      A 1-D string ``tf.Tensor``.
    """
    def _python_wrapper(string_t):
      string = tf.compat.as_text(string_t.numpy())
      tokens = self._tokenize_string(string)
      return tf.constant(tokens)

    return tf.py_function(_python_wrapper, [text], tf.string)

  def _detokenize_tensor(self, tokens):
    """Detokenizes tokens.

    When not overriden, this default implementation uses a ``tf.py_function``
    operation to call the string-based detokenization.

    Args:
      tokens: A 1-D ``tf.Tensor``.

    Returns:
      A 0-D string ``tf.Tensor``.
    """
    def _python_wrapper(tokens_t):
      tokens = [tf.compat.as_text(s) for s in tokens_t.numpy()]
      string = self._detokenize_string(tokens)
      return tf.constant(string)

    return tf.py_function(_python_wrapper, [tokens], tf.string)

  def _detokenize_batch_tensor(self, tokens, sequence_length):
    """Detokenizes a batch of tokens.

    When not overriden, this default implementation calls _detokenize_tensor on
    each tensor within the batch.

    Args:
      tokens: A 2-D ``tf.Tensor``.

    Returns:
      A 1-D string ``tf.Tensor``.
    """
    return tf.map_fn(
        lambda x: self._detokenize_tensor(x[0][:x[1]]),
        (tokens, sequence_length),
        dtype=tf.string,
        back_prop=False)

  @abc.abstractmethod
  def _tokenize_string(self, text):
    """Tokenizes a Python unicode string.

    This method should be thread-safe.

    Args:
      text: A Python unicode string.

    Returns:
      A list of Python unicode strings.
    """
    raise NotImplementedError()

  @abc.abstractmethod
  def _detokenize_string(self, tokens):
    """Detokenizes tokens.

    Args:
      tokens: A list of Python unicode strings.

    Returns:
      A unicode Python string.
    """
    raise NotImplementedError()


class SpaceTokenizer(Tokenizer):
  """A tokenizer that splits on spaces."""

  def _tokenize_tensor(self, text):
    return tf.strings.split([text], sep=" ").values

  def _detokenize_tensor(self, tokens):
    return tf.strings.reduce_join(tokens, axis=0, separator=" ")

  def _tokenize_string(self, text):
    return text.split()

  def _detokenize_string(self, tokens):
    return " ".join(tokens)


class CharacterTokenizer(Tokenizer):
  """A tokenizer that splits unicode characters."""

  def _tokenize_tensor(self, text):
    text = tf.strings.regex_replace(text, " ", "▁")
    return tf.strings.unicode_split(text, "UTF-8")

  def _detokenize_tensor(self, tokens):
    text = tf.strings.reduce_join(tokens, axis=0)
    return tf.strings.regex_replace(text, "▁", " ")

  def _tokenize_string(self, text):
    return list(text.replace(" ", u"▁"))

  def _detokenize_string(self, tokens):
    return "".join(tokens).replace(u"▁", " ")
