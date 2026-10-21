_lerobot_list_cameras()
{
    local cur="${COMP_WORDS[COMP_CWORD]}"

    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=(
            $(compgen -W "rgb rgbd meta --help -h" -- "$cur")
        )
    else
        COMPREPLY=()
    fi
}

complete -F _lerobot_list_cameras lerobot-list-cameras
