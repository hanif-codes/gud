from argparse import Namespace
import os
import sys
from os.path import realpath
from datetime import datetime
from configparser import ConfigParser
from .helpers import OperatingSystem
from .config import (
    GlobalConfig,
    RepoConfig,
)
import platform


class CommandInvocation:
    def __init__(self, all_args: Namespace, cwd: str):
        self.command: str = all_args.command
        self.args: dict = __class__.get_additional_commands(all_args)
        self.cwd = cwd # current working directory
        self.timestamp = __class__.get_timestamp_aware()
        # get the OS of the host system
        try:
            pltform = platform.system()
            self.os = OperatingSystem(pltform)
        except ValueError:
            sys.exit(f"Your platform ({pltform}) is not supported.\nSupported platforms: {OperatingSystem.get_all_names()}")
        if self.command == "init":
            self.repo = Repository(cwd, create_new_repo=True)
        else:
            self.repo = Repository(cwd)

    @staticmethod
    def get_additional_commands(args: Namespace) -> dict:
        args_dict = vars(args)
        args_dict.pop("command", None)
        return args_dict
    
    @staticmethod
    def get_timestamp_aware() -> datetime:
        local_time = datetime.now()
        local_tz = local_time.astimezone().tzinfo
        local_time_aware = local_time.replace(tzinfo=local_tz)
        return local_time_aware
    

class Repository:
    def __init__(self, cwd: str, create_new_repo = False):
        if create_new_repo:
            existing_repo_path = __class__.find_repo_path(cwd)
            if existing_repo_path:
                sys.exit(f"Repository already exists at {existing_repo_path}.")
            else:
                self.path = f"{cwd}/.gud"
                self.index = None # will be created later
        else:
            self.path = __class__.find_repo_path(cwd)
            if not self.path:
                sys.exit("No gud repository found in this directory, or in any parent directory.")
            self.index = Index(repo_path=self.path)

        self.global_config = GlobalConfig()
        self.repo_config = RepoConfig(repo_path=self.path)

        # the "effective" config - combination of global and repo-specific settings
        if not create_new_repo:
            self.config = self.resolve_working_config()

    def create_repo(self) -> None:
        """
        Create the repo. This is called manually at the conclusion of the <init> command.
        """
        try:
            os.makedirs(self.path, exist_ok=False)
        except FileExistsError:
            sys.exit(f"Repository {self.path} already exists.")

        # create the index file
        self.index = Index(self.path)
  
    def resolve_working_config(self) -> ConfigParser:
        """
        Combine the global config and repo-specific config settings
        into a single config entity.
        """
        working_config = ConfigParser()
        global_config = self.global_config.get_config()
        repo_config = self.repo_config.get_config()
        configs_to_load = [global_config, repo_config]
        for cnf in configs_to_load:
            for section in cnf.sections():
                if not working_config.has_section(section):
                    working_config.add_section(section)
                for key, value in cnf.items(section):
                    working_config[section][key] = value
        return working_config

    def copy_global_to_repo_config(self, provided_options: dict|None = None) -> None:
        """
        Set the repo's config to same as the global config.
        Probably needs to bit of additional functionality eventually.
        """
        global_config = self.global_config.get_config()
        self.repo_config.set_config(global_config)

    @staticmethod
    def find_repo_path(curr_path) -> str:
        """ Recurse up the path tree to find the deepest .gud/ directory, if there is one """
        while True:
            parent_dir_path = realpath(os.path.dirname(curr_path))
            if curr_path == parent_dir_path:
                return ""
            if ".gud" in os.listdir(curr_path):
                break
            curr_path = parent_dir_path
        return f"{curr_path}/.gud"
    

class Index:
    """
    The index file is a virtual representation of what the repository views the current state
    of the repository to be. A tree object is a snapshot of the index at a given time.
    """
    def __init__(self, repo_path, index_already_exists=True):
        self.path = os.path.join(repo_path, "index")
        if not index_already_exists:
            # create blank index file
            with open(self.path, "w"):
                pass

        def add_to_index(self, object):
            """
            Add a single file to the index
            """
            ...

        def remove_from_index(self):
            """
            Remove a single file from the index
            """
            ...


class Object:
    # TODO - implement this
    """
    object types:
        - blob (eg a file)
        - tree (a snapshot of the index at a given time):
            - this contains a list of the file hashes and file paths of objects at a given time
        - commit:
            - tree
            - parent commit
            - author/timestamp etc    
    """
    ...