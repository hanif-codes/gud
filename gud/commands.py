"""
All of these are commands that will ultimately be used as `gud <command_name>`
"""
import questionary
from configparser import ConfigParser
from .helpers import (
    is_valid_username,
    is_valid_email,
    open_relevant_editor,
    get_default_file_from_package_installation,
    get_all_ignored_paths,
    format_path_for_gudignore,
    get_file_mode
)
from .classes import (
    Blob,
    Tree,
    Commit,
    PathValidatorQuestionary,
    TextValidatorQuestionaryNotEmpty
)
import os
import sys
from copy import deepcopy


def test(invocation):
    print("This is a test command!")
    tree = Tree(invocation.repo)
    tree_content_readable = tree.get_content("b480ff3304752e7c0fca6efe19a06e5e6d3fffd5").decode()
    for line in tree_content_readable.split("\n"):
        print(line)
    tree_content_readable_2 = tree.get_content("4e6ae3bed9d1cba90a642020f7a17146731cae01").decode()
    for line in tree_content_readable_2.split("\n"):
        print(line)
    

def hello(invocation):
    name = invocation.args.get("name")
    if name:
        print(f"Hello {name}!")
    else:
        print("Hello there.")


def init(invocation):

    global_config = invocation.repo.global_config.get_config()

    if invocation.args["is_default"]:

        invocation.repo.create_repo()
        repo_config = invocation.repo.copy_global_to_repo_config()
        print("'default' flag provided: using global config options...")

    else:

        repo_config = ConfigParser()
        repo_config.add_section("user")
        repo_config.add_section("repo")

        username_prompt = f"Username? (leave blank to use {global_config['user']['name']}):"
        while True:
            username = questionary.text(username_prompt).ask()
            if not username: # default to global username
                username = invocation.repo.global_config.get_config()["user"]["name"]
                break
            if is_valid_username(username):
                break
            else:
                username_prompt = "Invalid username, please try another (must be between 1 and 16 characters):"
        repo_config["user"]["name"] = username

        email_prompt = f"Email address? (leave blank to use {global_config['user']['email']}):"
        while True:
            email_address = questionary.text(email_prompt).ask()
            if not email_address: # default to global email address
                email_address = invocation.repo.global_config.get_config()["user"]["email"]
                break
            if is_valid_email(email_address):
                break
            else:
                email_prompt = "Invalid email address, please try another:"
        repo_config["user"]["email"] = email_address

        gudignore_prompt = "Are there any files or folders you do not want Gud to track?"
        answer = questionary.select(gudignore_prompt, ["No", "Yes"]).ask()
        if answer.lower() == "yes":
            paths_to_ignore = set()
            while True: # loop for selecting multiple files
                if paths_to_ignore:
                    print("Files/directories that will be ignored:")
                    for path in paths_to_ignore:
                        print(path)
                path = questionary.path(
                    f"Search for a file/directory to for Gud to ignore (enter blank when finished):",
                    validate=PathValidatorQuestionary()
                ).ask()
                if path == "":
                    break
                paths_to_ignore.add(format_path_for_gudignore(path))
            # create and save the .gudignore file, including comments from the default gudignore file in the installation
            default_gudignore_file = get_default_file_from_package_installation("gudignore")
            if not default_gudignore_file:
                raise Exception("Default gudignore file not found - possibly corrupted installation.")
            repo_gudignore_path = os.path.join(invocation.repo.root, ".gudignore")
            with open(default_gudignore_file, "r", encoding="utf-8") as default_file:
                default_comments = [line for line in default_file.readlines() if line.strip()]
                with open(repo_gudignore_path, "w", encoding="utf-8") as repo_file:
                    repo_file.writelines(default_comments)
                    repo_file.write("\n")
                    repo_file.writelines([f"{path}\n" for path in paths_to_ignore])
            print("Note: If you wish to change which files Gud ignores, modify and save the .gudignore file at any time.")

        invocation.repo.create_repo()
        invocation.repo.repo_config.set_config(repo_config)

    print(f"Initialised Gud repository in {invocation.repo.path}")


def config(invocation):

    view_or_edit = invocation.args["view_or_edit"]
    repo_or_global = invocation.args["repo_or_global"]

    # if "repo" is passed, convert to more verbose version for later
    if repo_or_global == "repo":
        repo_or_global = "repository"

    if not view_or_edit:
        view_or_edit = questionary.select(
            "Would you like to view or edit a config file?",
            ["View", "Edit"]
        ).ask().lower()

    if not repo_or_global:
        repo_or_global = questionary.select(
            f"Would you like to {view_or_edit} this repository's configuration settings, or the global configuration settings?",
            ["Repository", "Global"]
        ).ask().lower()

    if repo_or_global == "global":
        config_path = invocation.repo.global_config.path
    else:
        config_path = invocation.repo.repo_config.path

    if view_or_edit == "edit":
        print(f"Opening {config_path}...\nClose editor to continue...")
        open_relevant_editor(invocation.os, config_path)
    else:
        print(f"{repo_or_global.capitalize()} config options ({config_path}):\n")
        with open(config_path, "r", encoding="utf-8") as f:
            print(f.read())


def ignoring(invocation, for_printing_to_user=True) -> set:
    """
    Show all files in this repository that Gud is set to ignore
    Find all .gudignore files, and print them out in stdout
    Make sure to label each file above its contents, and make it clear/well-formatted
    """
    repo_root = invocation.repo.root
    all_ignored_file_paths = get_all_ignored_paths(repo_root)        
    if for_printing_to_user:
        if not all_ignored_file_paths:
            print(f"No files/folders are being ignored in this repository ({invocation.repo.path})")
        else:
            print(f"Gud is ignoring the following files/folders in this repository ({invocation.repo.path}):\n")
            for file_path in sorted(all_ignored_file_paths):
                print(file_path)
    else:
        all_ignored_file_paths.add(format_path_for_gudignore(invocation.repo.path))
    return all_ignored_file_paths # return value for if another command calls this


def stage(invocation):

    action = invocation.args.get("add_or_remove", None)
    paths_specified = set(invocation.args.get("file_paths", []))

    if not action:
        action = questionary.select(
            "Would you like to add files to, or remove files from, the staging area?",
            ["Add", "Remove"]
        ).ask().lower()
    connective = "removed from" if action == "remove" else "added to"

    if not paths_specified:
        # TODO - implement a function to filter the paths, and pass it as the file_filter argument in questionary.path
        # the filter should probably not include files that are being tracked and haven't been modified since the last commit
        while True: # loop for selecting multiple files
            path = questionary.path(
                f"Search for a file/directory to be {connective} the staging area (enter blank when finished):",
                validate=PathValidatorQuestionary()
            ).ask()
            if path == "":
                break
            # check if the path exists within the repository
            abs_path = os.path.abspath(os.path.expanduser(path)) # expanduser expands the ~
            if os.path.commonprefix([abs_path, invocation.repo.root]) != invocation.repo.root:
                print(f"Path {path} does not exist within the repository, so cannot be {connective} the staging area")
                continue
            paths_specified.add(abs_path) # store the rel path
            # TODO - instead of the below, call gud status (once implemented) between each file selection
            print(f"Files/directories to be {connective} the staging area:")
            for path in paths_specified:
                print(path)

    # convert all paths to rel_paths - this is how they will be stored in the index
    rel_paths_specified = [os.path.relpath(path, invocation.repo.root) for path in paths_specified]

    for rel_path in rel_paths_specified:
        # TODO - go through all files and if any file is ignored, cancel the operation and raise an error
        ...

    if action == "add":
        index = invocation.repo.parse_index()
        for rel_path in rel_paths_specified:
            abs_path = os.path.join(invocation.repo.root, rel_path)
            if os.path.isfile(abs_path): # blob
                blob = Blob(repo=invocation.repo)
                file_hash = blob.serialise(abs_path, write_to_file=True)
                file_mode = get_file_mode(abs_path)
                index[rel_path] = {
                    "type": "blob",
                    "mode": file_mode,
                    "hash": file_hash
                }
            elif os.path.isdir(abs_path): # tree
                # TODO - if a directory is added, just recursively add all files in the directory
                # (all files except ignored files)
                raise NotImplementedError("Adding directories has not been implemented yet")
        invocation.repo.write_to_index(index)

    elif action == "remove":
        # TODO - remove from the staging area
        # if a file is 'removed' from the staging area, this just means to replace its line in
        # the index with the file info from the last commit
        # if the file didn't exist in the last commit, the line in index will be removed
        # if it did exist in the last commit, the line will just be modified to reflect
        # the version of the file as it was at the last commit
        index = invocation.repo.parse_index()
        latest_commit = invocation.repo.head
        raise NotImplementedError("'Remove' has not been implemented yet.")
    
        # head_path = os.path.join(invocation.repo.path, "heads", invocation.repo.branch)
        # with open(head_path, "r", encoding="utf-8") as f:
        #     head_commit_hash = f.read().strip()
        # if not head_commit_hash: # no commits are recorded
        #     head_index = {}
        # else:
        #     commit = Commit(invocation.repo)
        #     head_commit_contents = commit.get_content(head_commit_hash).decode()
        #     for line in head_commit_contents.split("\n"):
        #         try:
        #             type, value = line.split("\t")
        #         except ValueError:
        #             continue
        #         else:
        #             if type == "tree":
        #                 root_tree_hash = value
        #     if not root_tree_hash:
        #         raise Exception(f"Could not find tree_hash from commit {head_commit_hash}")
        #     # generate an "head_index" by recursively inspecting all the tree objects
        #     tree = Tree(invocation.repo)
        #     head_index = tree._read_tree_object(root_tree_hash, curr_path="")



def commit(invocation):
    file_changes = status(invocation, print_output=False)
    if not any(file_changes["staged"].values()):
        sys.exit("You cannot commit, as there are no changes in the staging area.")

    # create the tree object(s), using the current index
    tree = Tree(invocation.repo)
    tree_hash = tree.serialise()

    commit_message = questionary.text(
        "What changes does this commit represent?",
        validate=TextValidatorQuestionaryNotEmpty()
    ).ask()

    commit = Commit(
        repo=invocation.repo,
        tree_hash=tree_hash,
        commit_message=commit_message.strip(),
        timestamp=invocation.timestamp
    )
    commit_hash = commit.serialise()

    # update the reference to head
    heads_path = os.path.join(invocation.repo.path, "heads", invocation.repo.branch)
    with open(heads_path, "w", encoding="utf-8") as f:
        f.write(commit_hash)

    print(f"Successfully committed on branch {invocation.repo.branch}.\nUse `gud log` to view commit history.")
    

def status(invocation, print_output=True) -> dict[str, dict]:
    """
    6 categories for files:

    staged_modified
    staged_deleted
    staged_added

    unstaged_modified
    unstaged_deleted
    unstaged_added
    """
    tree = Tree(invocation.repo)
    staged_index = tree.index

    """ Determine STAGED file differences (where index =/ last commit) """
    # head_path = os.path.join(invocation.repo.path, "heads", invocation.repo.branch)
    # with open(head_path, "r", encoding="utf-8") as f:
    #     head_commit_hash = f.read().strip()
    head_commit_hash = invocation.repo.head
    if not head_commit_hash: # no commits are recorded
        head_index = {}
    else:
        commit = Commit(invocation.repo)
        head_commit_contents = commit.get_content(head_commit_hash).decode()
        for line in head_commit_contents.split("\n"):
            try:
                type, value = line.split("\t")
            except ValueError:
                continue
            else:
                if type == "tree":
                    root_tree_hash = value
        if not root_tree_hash:
            raise Exception(f"Could not find tree_hash from commit {head_commit_hash}")
        # generate an "head_index" by recursively inspecting all the tree objects
        tree = Tree(invocation.repo)
        head_index = tree._read_tree_object(root_tree_hash, curr_path="")

    # compare head_index to staged_index
    files_in_head_index = set(head_index)
    files_in_staged_index = set(staged_index)
    _staged_existing_files = files_in_head_index & files_in_staged_index
    staged_modified_files = set()
    for file_path in _staged_existing_files:
        # simple implementation to see if anything about the file has changed
        info_str_head = "".join(head_index[file_path].values())
        info_str_staged = "".join(staged_index[file_path].values())
        if info_str_head != info_str_staged: # modified file
            staged_modified_files.add(file_path)

    staged_deleted_files = files_in_head_index - files_in_staged_index
    staged_added_files = files_in_staged_index - files_in_head_index

    """ Determine UNSTAGED file differences (where working directory =/ index) """
    # build a path_tree for the current index

    all_path_parts = [path.split(os.sep) for path in staged_index.keys()]
    path_tree = tree._build_path_tree(all_path_parts)

    # find all ignored files (this is messy but seems to work like git?)
    ignored_abs_paths = ignoring(invocation, for_printing_to_user=False)
    abs_staged_index_without_ignored_files = set(os.path.join(invocation.repo.root, path) for path in staged_index.keys())
    for path in abs_staged_index_without_ignored_files.copy():
        for ignored_path in ignored_abs_paths:
            if ignored_path.endswith("/"): # directory
                if path.startswith(ignored_path):
                    print(f"{path} starts with {ignored_path}")
                    abs_staged_index_without_ignored_files.remove(path)
            else:
                if ignored_path == path:
                    abs_staged_index_without_ignored_files.remove(path)
    rel_staged_index_without_ignored = set(
        os.path.relpath(path, invocation.repo.root) for path in abs_staged_index_without_ignored_files
    )

    unstaged_added_files = set()
    unstaged_modified_files = set()

    # get all files in the working directory
    working_dir_paths_traversed = set()
    repo_root = invocation.repo.root
    for root, subdirs, files in os.walk(repo_root):
        root_formatted = format_path_for_gudignore(root)
        # stop traversing any directory that is listed in gudignore
        if root_formatted in ignored_abs_paths:
            subdirs[:] = [] # prevents traversal of ignored directories
            continue
        for file in files:
            full_path = os.path.join(root, file)
            full_path_formatted = format_path_for_gudignore(full_path)
            # if any of the ignored paths is a prefix to the current path, ignore the current path
            if any(full_path_formatted.startswith(ignored_path) for ignored_path in ignored_abs_paths):
                continue

            rel_path = os.path.relpath(full_path, invocation.repo.root)
            working_dir_paths_traversed.add(rel_path)
            path_parts = rel_path.split("/")

            subtree = deepcopy(path_tree)
            prefix_parts = []
            suffix_parts = path_parts[:]
            while suffix_parts:
                prefix_parts.append(suffix_parts[0])
                suffix_parts = suffix_parts[1:]
                next_lookup: str = prefix_parts[-1]
                subtree = subtree.get(next_lookup, None)
                file_path_so_far = os.path.join(*prefix_parts)
                if subtree is None: # untracked file/dir
                    # using untracked path like this ensures that it only lists the
                    # shallowest untracked directory, rather than listing the entire contents
                    # as untracked
                    if os.path.isdir(file_path_so_far):
                        file_path_so_far += os.sep # trailing slash if dir - is clearer in the output
                    unstaged_added_files.add(file_path_so_far)
                    break
                elif isinstance(subtree, list): # tracked FILE
                    old_mode = subtree[0]
                    old_hash = subtree[1]
                    blob = Blob(invocation.repo)
                    new_mode = get_file_mode(file_path_so_far)
                    new_hash = blob.serialise(file_path_so_far, write_to_file=False)
                    if old_mode != new_mode or old_hash != new_hash:
                        unstaged_modified_files.add(file_path_so_far)
                    break
                # else, it's a tracked subtree and the loop continues
    
    # checks which staged/indexed files were not traversed
    unstaged_deleted_files = rel_staged_index_without_ignored - working_dir_paths_traversed

    """ Print out everything we determined from this whole function """
    staged = {
        "modified": sorted(staged_modified_files),
        "added": sorted(staged_added_files),
        "deleted": sorted(staged_deleted_files)
    }

    unstaged = {
        "modified": sorted(unstaged_modified_files),
        "added": sorted(unstaged_added_files),
        "deleted": sorted(unstaged_deleted_files)
    }

    if print_output:

        # if both staged and unstaged are empty
        if not (any(staged.values()) or any(unstaged.values())):
            print("nothing to commit, working tree clean")

        else:

            if any(staged.values()):
                print("Changes to be committed:\n  Use `gud stage remove <file>` to remove a file from the staging area")
                for file_path in staged["modified"]:
                    print(f"\tmodified: {file_path}")
                for file_path in staged["deleted"]:
                    print(f"\tdeleted: {file_path}")
                for file_path in staged["added"]:
                    print(f"\tnew file: {file_path}")
                print()

            if unstaged["modified"] or unstaged["deleted"]:
                print("Changes not staged for commit:\n  Use `gud stage add <file>` to update a file in the staging area")
                for file_path in unstaged["modified"]:
                    print(f"\tmodified: {file_path}")
                for file_path in unstaged["deleted"]:
                    print(f"\tdeleted: {file_path}")
                print()

            if unstaged["added"]:
                print("Untracked files:\n  Use `gud stage add <file>` to include a file in the staging area")
                for file_path in unstaged["added"]:
                    print(f"\tnew file: {file_path}")
                print()

    return {
        "staged": staged,
        "unstaged": unstaged
    }