# Typing

`consumer_snippet.py` is code as a consumer would write it. CI's static job builds the wheel, installs it in a
fresh environment, and type-checks the snippet there with `mypy --strict` and pyright in strict mode, from a
directory outside the repository, so that the installed package is what resolves. It then deletes
`py.typed` from that installation and requires mypy to fail: the control that shows the check can fail.

pytest does not collect the snippet; mypy and pyright check it with the rest of `tests/`.
