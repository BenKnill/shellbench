"""Command families used by shellbench, shared by the suite builder, the scorer and the
corpus aggregation. A utility belongs to exactly one family; a case or a corpus command that
uses several utilities counts toward each of their families (multi-label)."""

FAMILIES = {
    "view": ["cat", "head", "tail", "nl", "tac"],
    "sed": ["sed"],
    "grep": ["grep", "egrep", "fgrep"],
    "rg": ["rg"],
    "ls-stat": ["ls", "stat", "du", "file", "tree"],
    "cut-tr": ["cut", "tr", "paste", "column", "fold", "rev", "expand"],
    "wc": ["wc"],
    "sort-uniq": ["sort", "uniq", "comm"],
    "checksum": ["shasum", "sha256sum", "sha1sum", "md5sum", "cksum", "b2sum"],
    "fileops": ["cp", "mv", "rm", "mkdir", "rmdir", "touch", "ln", "chmod", "tar", "readlink",
                "realpath", "basename", "dirname", "tee", "mktemp", "truncate", "split"],
    "awk": ["awk", "gawk"],
    "jq": ["jq"],
    "find-xargs": ["find", "xargs"],
    "diff-bytes": ["diff", "cmp", "od", "xxd", "hexdump", "base64"],
    "shell": ["cd", "echo", "printf", "test", "[", "true", "false", "pwd", "read", "set", "seq",
              "timeout", "nice", "export", "local", "eval", "trap", "exit", "type", "command",
              "env", "expr", "sleep", "date"],
}
UTIL2FAM = {u: f for f, us in FAMILIES.items() for u in us}


def families_of(utils):
    return sorted({UTIL2FAM[u] for u in utils or [] if u in UTIL2FAM})
