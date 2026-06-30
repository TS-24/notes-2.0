from __future__ import annotations

from .constants import LANG_CONFIGS
from ._get_lang_root import get_lang_root


def get_lang_cfg(lang: str, key: str) -> float:
    """Get the config value specified by `key` for the given language `lang`.

    Parameters
    ----------
    lang : str
        The language of the text.
    key : str
        The key of the config value to get.

    Returns
    -------
    float
        The config value.
    """
    lang_root = get_lang_root(lang)
    default_config = LANG_CONFIGS["en"]
    config = LANG_CONFIGS.get(lang_root, {})

    if key in config:
        return config[key]

    if key in default_config:
        return default_config[key]

    raise ValueError(f"Unknown config key {key}")
