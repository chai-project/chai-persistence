# pylint: disable=line-too-long, missing-module-docstring, too-few-public-methods, missing-class-docstring

import json
import os
from dataclasses import dataclass
from typing import Dict, Optional, TypeVar, Callable, Union

V = TypeVar("V")
K = TypeVar("K")
T = TypeVar("T")


@dataclass
class Configuration:
    database: str
    db_in_memory: bool
    enable_debugging: bool
    client_id: str
    client_secret: str


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


def read_config(script_path: str = "") -> Configuration:
    """
    Read and parse a configuration file and return a Configuration instance.
    :param script_path: The path to the script if it is different from "".
    :return: A Configuration instance when all configuration settings could be retrieved, or throws an error.
    """
    with open(os.path.join(script_path, "settings.json"), encoding="utf8") as json_data_file:
        data = json.load(json_data_file)
        if "database" not in data:
            ValueError("expected a key 'database' to identify the location of the database")
        if "client_id" not in data:
            ValueError("expected a key 'client_id' which is used to access the Netatmo API")
        if "client_secret" not in data:
            ValueError("expected a key 'client_secret' which is used to access the Netatmo API")
        return Configuration(database=data["database"],
                             db_in_memory=optional(data, "db_in_memory", False),
                             enable_debugging=optional(data, "enable_debugging", False),
                             client_id=data["client_id"],
                             client_secret=data["client_secret"],
                             )
