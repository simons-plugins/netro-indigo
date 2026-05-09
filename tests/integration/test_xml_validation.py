"""ValidateXmlFile coverage for all 5 netro plugin XML files.

These tests don't need Indigo running — they validate the XML
files on disk against TestingBase's bundled schema. Catch broken
XML before it reaches end users.
"""
import os

from shared import APIBase, ValidateXmlFile

# Resolve the Server Plugin directory relative to this test file so the
# tests run on any machine.
PLUGIN_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../Netro Sprinklers.indigoPlugin/Contents/Server Plugin",
    )
)


class TestActionsXml(ValidateXmlFile, APIBase):
    server_plugin_dir_path = PLUGIN_ROOT
    file_name = "Actions.xml"


class TestDevicesXml(ValidateXmlFile, APIBase):
    server_plugin_dir_path = PLUGIN_ROOT
    file_name = "Devices.xml"


class TestEventsXml(ValidateXmlFile, APIBase):
    server_plugin_dir_path = PLUGIN_ROOT
    file_name = "Events.xml"


class TestMenuItemsXml(ValidateXmlFile, APIBase):
    server_plugin_dir_path = PLUGIN_ROOT
    file_name = "MenuItems.xml"


class TestPluginConfigXml(ValidateXmlFile, APIBase):
    server_plugin_dir_path = PLUGIN_ROOT
    file_name = "PluginConfig.xml"
