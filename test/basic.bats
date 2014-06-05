setup() {
    unset GIT_ANNEX_HUBIC_AUTH_FILE OS_AUTH_TOKEN OS_STORAGE_URL
    cd repo
}
teardown() {
    git reset --hard master >&2
    git clean --force >&2
    cd ..
}

@test "normal behavior for small files" {
    name=$(mktemp test.XXXXXX)
    dd if=/dev/urandom of=$name bs=1 count=100 >&2
    md5sum $name > md5
    git annex add $name >&2

    run git annex copy $name --to remote-hubic
    [ "$status" -eq 0 ]

    run git annex fsck $name --from remote-hubic
    [ "$status" -eq 0 ]

    git annex drop $name >&2
    run git annex get $name --from remote-hubic
    [ "$status" -eq 0 ]

    run md5sum -c md5
    [ "$status" -eq 0 ]

    run git annex drop $name --from remote-hubic
    [ "$status" -eq 0 ]
}

@test "normal behavior for medium files" {
    name=$(mktemp test.XXXXXX)
    dd if=/dev/urandom of=$name bs=1 count=2000 >&2
    md5sum $name > md5
    git annex add $name >&2

    run git annex copy $name --to remote-hubic
    [ "$status" -eq 0 ]

    run git annex fsck $name --from remote-hubic
    [ "$status" -eq 0 ]

    git annex drop $name >&2
    run git annex get $name --from remote-hubic
    [ "$status" -eq 0 ]

    run md5sum -c md5
    [ "$status" -eq 0 ]

    run git annex drop $name --from remote-hubic
    [ "$status" -eq 0 ]
}

@test "normal behavior for large files" {
    name=$(mktemp test.XXXXXX)
    dd if=/dev/urandom of=$name bs=1 count=20000 >&2
    md5sum $name > md5
    git annex add $name >&2

    run git annex copy $name --to remote-hubic
    [ "$status" -eq 0 ]

    run git annex fsck $name --from remote-hubic
    [ "$status" -eq 0 ]

    git annex drop $name >&2
    run git annex get $name --from remote-hubic
    [ "$status" -eq 0 ]

    run md5sum -c md5
    [ "$status" -eq 0 ]

    run git annex drop $name --from remote-hubic
    [ "$status" -eq 0 ]
}
