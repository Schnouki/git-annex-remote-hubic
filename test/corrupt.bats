setup() {
    unset GIT_ANNEX_HUBIC_AUTH_FILE OS_AUTH_TOKEN OS_STORAGE_URL
    cd repo
}
teardown() {
    unset GIT_ANNEX_HUBIC_AUTH_FILE OS_AUTH_TOKEN OS_STORAGE_URL
    git reset --hard master >&2
    git clean --force >&2
    cd ..
}

@test "exporting Swift credentials to a file" {
    name=$(mktemp test.XXXXXX)
    auth=$(mktemp auth.XXXXXX)
    dd if=/dev/urandom of=$name bs=1 count=100 >&2
    git annex add $name >&2

    export GIT_ANNEX_HUBIC_AUTH_FILE=$auth
    run git annex copy $name --to remote-hubic
    [ "$status" -eq 0 ]

    source $auth
    run swift stat
    [ "$status" -eq 0 ]
}

@test "detecting files with missing middle chunk on remote" {
    name=$(mktemp test.XXXXXX)
    auth=$(mktemp auth.XXXXXX)
    dd if=/dev/urandom of=$name bs=1 count=4000 >&2
    git annex add $name >&2

    export GIT_ANNEX_HUBIC_AUTH_FILE=$auth
    run git annex copy $name --to remote-hubic
    [ "$status" -eq 0 ]
    git annex drop $name >&2

    source $auth
    swift list test_container | grep /chunk0002 | xargs -rd'\n' swift delete test_container >&2

    run git annex get $name --from remote-hubic
    [ "$status" -eq 1 ]

    run git annex fsck $name --from remote-hubic
    [ "$status" -eq 1 ]
}

@test "detecting files with missing last chunk on remote" {
    name=$(mktemp test.XXXXXX)
    auth=$(mktemp auth.XXXXXX)
    dd if=/dev/urandom of=$name bs=1 count=4000 >&2
    git annex add $name >&2

    export GIT_ANNEX_HUBIC_AUTH_FILE=$auth
    run git annex copy $name --to remote-hubic
    [ "$status" -eq 0 ]
    git annex drop $name >&2

    source $auth
    swift list test_container | grep /chunk0003 | xargs -rd'\n' swift delete test_container >&2

    run git annex get $name --from remote-hubic
    [ "$status" -eq 1 ]

    run git annex fsck $name --from remote-hubic
    [ "$status" -eq 1 ]
}

@test "detecting files corrupted on remote" {
    name=$(mktemp test.XXXXXX)
    crap=$(mktemp crap.XXXXXX)
    auth=$(mktemp auth.XXXXXX)
    dd if=/dev/urandom of=$name bs=1 count=4000 >&2
    dd if=/dev/urandom of=$crap bs=1 count=1024 >&2
    git annex add $name >&2

    export GIT_ANNEX_HUBIC_AUTH_FILE=$auth
    run git annex copy $name --to remote-hubic
    [ "$status" -eq 0 ]
    git annex drop $name >&2

    source $auth
    for fn in $(swift list test_container | grep /chunk0002); do
        swift stat test_container $fn \
              | awk '$1 == "Meta" { print "--header=\"" $2 $3 "\"" }' \
              | xargs -d '\n' swift upload test_container $crap --object-name="$fn"
    done

    run git annex get $name --from remote-hubic
    [ "$status" -eq 1 ]

    run git annex fsck $name --from remote-hubic
    [ "$status" -eq 1 ]
}

@test "detecting files truncated on remote" {
    name=$(mktemp test.XXXXXX)
    crap=$(mktemp crap.XXXXXX)
    auth=$(mktemp auth.XXXXXX)
    dd if=/dev/urandom of=$name bs=1 count=4000 >&2
    dd if=/dev/urandom of=$crap bs=1 count=100 >&2
    git annex add $name >&2

    export GIT_ANNEX_HUBIC_AUTH_FILE=$auth
    run git annex copy $name --to remote-hubic
    [ "$status" -eq 0 ]
    git annex drop $name >&2

    source $auth
    for fn in $(swift list test_container | grep /chunk0002); do
        swift stat test_container $fn \
              | awk '$1 == "Meta" { print "--header=\"" $2 $3 "\"" }' \
              | xargs -d '\n' swift --quiet upload test_container $crap --object-name="$fn"
    done

    run git annex get $name --from remote-hubic
    [ "$status" -eq 1 ]

    run git annex fsck $name --from remote-hubic
    [ "$status" -eq 1 ]
}
