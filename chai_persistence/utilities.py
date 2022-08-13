# pylint: disable=line-too-long, missing-module-docstring, too-few-public-methods, missing-class-docstring

from typing import Dict, Optional, TypeVar, Callable, Union

V = TypeVar("V")
K = TypeVar("K")
T = TypeVar("T")


def optional(source: Optional[Dict[K, V]], key: K, default: V = None,
             mapping: Optional[Callable[[V], T]] = None) -> Optional[Union[V, T]]:
    """
    Safely access a resource assuming the resource either exists or is None.
    :param source: A dictionary of values, which is possibly empty or None.
    :param key: The desired key to access in the dictionary.
    :param default: The default value to return when the value associated with `key` cannot be found.
    :param mapping: An optional mapping to apply to the value or default before returning it.
    :return: The value in the dictionary if the key exists, otherwise the default value if one is provided.
             If a mapping is provided the value in the dictionary or the default if it is exists is mapped.
             Returns None in all other cases.
    """
    if source is None:
        return default if mapping is None or default is None else mapping(default)
    try:
        element = source[key]
        return element if mapping is None else mapping(element)
    except (KeyError, IndexError):
        return default if mapping is None or default is None else mapping(default)
