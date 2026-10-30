#!/usr/bin/env bash

# Shared XDG namespace for Nyxuri Shell source-tree utility scripts.

nyxuri_paths_init() {
    local nyxuri_home=${HOME:?HOME must be set}
    local config_base=${XDG_CONFIG_HOME:-$nyxuri_home/.config}
    local data_base=${XDG_DATA_HOME:-$nyxuri_home/.local/share}
    local state_base=${XDG_STATE_HOME:-$nyxuri_home/.local/state}
    local cache_base=${XDG_CACHE_HOME:-$nyxuri_home/.cache}
    local runtime_base=${XDG_RUNTIME_DIR:-$cache_base/nyxuri/runtime}

    NYXURI_SHELL_CONFIG_HOME=${NYXURI_SHELL_CONFIG_HOME:-$config_base/nyxuri}
    NYXURI_SHELL_DATA_HOME=${NYXURI_SHELL_DATA_HOME:-$data_base/nyxuri}
    NYXURI_SHELL_STATE_HOME=${NYXURI_SHELL_STATE_HOME:-$state_base/nyxuri}
    NYXURI_SHELL_CACHE_HOME=${NYXURI_SHELL_CACHE_HOME:-$cache_base/nyxuri}
    NYXURI_SHELL_RUNTIME_HOME=${NYXURI_SHELL_RUNTIME_HOME:-$runtime_base/nyxuri}
    NYXURI_SHELL_PROFILE=${NYXURI_SHELL_PROFILE:-default}
    NYXURI_SHELL_PROFILE_CONFIG_HOME=${NYXURI_SHELL_PROFILE_CONFIG_HOME:-$NYXURI_SHELL_CONFIG_HOME/profiles/$NYXURI_SHELL_PROFILE}
    NYXURI_SHELL_PROFILE_HOME=${NYXURI_SHELL_PROFILE_HOME:-$NYXURI_SHELL_DATA_HOME/profiles/$NYXURI_SHELL_PROFILE}
    NYXURI_SHELL_GENERATED_HOME=${NYXURI_SHELL_GENERATED_HOME:-$NYXURI_SHELL_PROFILE_HOME/generated}

    export NYXURI_SHELL_CONFIG_HOME NYXURI_SHELL_DATA_HOME NYXURI_SHELL_STATE_HOME
    export NYXURI_SHELL_CACHE_HOME NYXURI_SHELL_RUNTIME_HOME NYXURI_SHELL_PROFILE
    export NYXURI_SHELL_PROFILE_CONFIG_HOME NYXURI_SHELL_PROFILE_HOME NYXURI_SHELL_GENERATED_HOME
}
