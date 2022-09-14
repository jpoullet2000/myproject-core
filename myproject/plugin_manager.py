"""Bla."""
from __future__ import annotations

import logging
from typing import List, Any, Iterator, Dict
import inspect
import types
import sys
try:
    import importlib_metadata as metadata
except ImportError:
    from importlib import metadata  # type: ignore[no-redef]
from packaging.utils import canonicalize_name

log = logging.getLogger(__name__)

plugin_list = None  # type: Optional[List[MyprojectPlugin]]
features_modules: List[Any] | None = None
import_errors: Dict[str, str] = {}

class MyProjectPluginSource:
    """Class used to define an MyProjectPluginSource."""

    def __str__(self):
        raise NotImplementedError

class EntryPointSource(MyProjectPluginSource):
    """Class used to define Plugins loaded from entrypoint."""

    def __init__(self, entrypoint: metadata.EntryPoint, dist: metadata.Distribution):
        self.dist = dist.metadata['Name']
        self.version = dist.version
        self.entrypoint = str(entrypoint)

    def __str__(self):
        return f"{self.dist}=={self.version}: {self.entrypoint}"

def ensure_plugins_loaded():
    """Load plugins from plugins directory and entrypoints.

    Plugins are only loaded if they have not been previously loaded.
    """
    global plugin_list

    if plugin_list is not None:
        log.debug("Plugins are already loaded. Skipping.")
        return

    plugin_list = []
    # load_plugins_from_plugin_directory()
    load_entrypoint_plugins()

def integrate_feature_plugins() -> None:
    """Integrate executor plugins to the context."""
    global plugin_list
    global features_modules
    if features_modules is not None:
        return
    ensure_plugins_loaded()

    if plugin_list is None:
        raise MyProjectPluginException("Can't load plugins.")

    log.debug("Integrate executor plugins")
    features_modules = []
    for plugin in plugin_list:
        if plugin.name is None:
            raise MyProjectPluginException("Invalid plugin name")
        plugin_name: str = plugin.name

        features_module = make_module('myproject.features.' + plugin_name, plugin.features)
        if features_module:
            features_modules.append(features_module)
            sys.modules[features_module.__name__] = features_module


class MyProjectPluginException(Exception):
    """Exception when loading plugin."""

class MyProjectPlugin:
    """Class used to define plugins."""

    features: List[Any] = []

    @classmethod
    def validate(cls):
        """Validate that plugin has a name."""
        if not cls.name:
            raise MyProjectPluginException("Your plugin needs a name.")

    @classmethod
    def on_load(cls, *args, **kwargs):
        """Execute when the plugin is loaded.

        This method is only called once during runtime.
        :param args: If future arguments are passed in on call.
        :param kwargs: If future arguments are passed in on call.
        """

def register_plugin(plugin_instance):
    """Start plugin load and register it after success initialization.

    :param plugin_instance: subclass of MyProjectPlugin
    """
    global plugin_list
    plugin_instance.on_load()
    plugin_list.append(plugin_instance)



def is_valid_plugin(plugin_obj):
    """Check whether a potential object is a subclass of the MyprojectPlugin class.

    :param plugin_obj: potential subclass of MyprojectPlugin
    :return: Whether or not the obj is a valid subclass of
        MyProjectPlugin
    """
    global plugin_list

    if (
        inspect.isclass(plugin_obj)
        and issubclass(plugin_obj, MyProjectPlugin)
        and (plugin_obj is not MyProjectPlugin)
    ):
        plugin_obj.validate()
        return plugin_obj not in plugin_list
    return False

def entry_points_with_dist(group: str) -> Iterator[tuple[metadata.EntryPoint, metadata.Distribution]]:
    """Retrieve entry points of the given group.
    This is like the ``entry_points()`` function from importlib.metadata,
    except it also returns the distribution the entry_point was loaded from.
    :param group: Filter results to only this entrypoint group
    :return: Generator of (EntryPoint, Distribution) objects for the specified groups
    """
    loaded: set[str] = set()
    for dist in metadata.distributions():
        key = canonicalize_name(dist.metadata["Name"])
        if key in loaded:
            continue
        loaded.add(key)
        for e in dist.entry_points:
            if e.group != group:
                continue
            yield e, dist

def load_entrypoint_plugins():
    """Load and register plugins MyProjectPlugin subclasses from the entrypoints.

    The entry_point group should be 'myproject.plugins'.
    """
    global import_errors
    log.debug("Loading plugins from entrypoints")
    for entry_point, dist in entry_points_with_dist('myproject.plugins'):
        log.debug('Importing entry_point plugin %s', entry_point.name)
        try:
            plugin_class = entry_point.load()
            print(plugin_class)
            if not is_valid_plugin(plugin_class):
                continue

            plugin_instance = plugin_class()
            plugin_instance.source = EntryPointSource(entry_point, dist)
            register_plugin(plugin_instance)
        except Exception as e:
            log.exception("Failed to import plugin %s", entry_point.name)
            import_errors[entry_point.module] = str(e)


def make_module(name: str, objects: List[Any]):
    """Create new module."""
    if not objects:
        return None
    log.debug('Creating module %s', name)
    name = name.lower()
    module = types.ModuleType(name)
    module._name = name.split('.')[-1]  # type: ignore
    module._objects = objects  # type: ignore
    module.__dict__.update((o.__name__, o) for o in objects)
    return module
