"""Current maintainer output boundary; never write into a sealed archive."""

from pathlib import Path


def fresh_external_output(output, source_root):
    output = Path(output).absolute()
    source_root = Path(source_root).absolute()
    if ".." in output.parts:
        raise ValueError("Noncanonical output path refused")
    if output == source_root or output.is_relative_to(source_root):
        raise ValueError("Fresh output outside source worktree required")
    for ancestor in (output, *output.parents):
        if ancestor.is_symlink():
            raise ValueError("Linked output ancestor refused")
        if (ancestor / "EVIDENCE_MANIFEST.json").exists():
            raise ValueError(
                "Sealed Full archive is immutable; output must be outside it"
            )
    if output.exists():
        raise ValueError("Fresh nonexisting output required")
    return output
