#!/usr/bin/env python3
"""
overleaf_cleanup.py - Analyze LaTeX project dependencies and remove unused files.

Usage:
    python overleaf_cleanup.py <project_dir> --main <main.tex> [--delete] [--dry-run]
"""

import argparse
import os
import re
import sys
from pathlib import Path


# LaTeX commands that reference other files
INCLUDE_PATTERNS = [
    # (regex, adds_extension)
    (r'\\input\{([^}]+)\}', '.tex'),
    (r'\\include\{([^}]+)\}', '.tex'),
    (r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', None),  # image extensions vary
    (r'\\bibliography\{([^}]+)\}', '.bib'),
    (r'\\addbibresource\{([^}]+)\}', None),
    (r'\\usepackage\{([^}]+)\}', '.sty'),  # only local .sty files
    (r'\\lstinputlisting(?:\[[^\]]*\])?\{([^}]+)\}', None),
    (r'\\verbatiminput\{([^}]+)\}', None),
    (r'\\import\{([^}]*)\}\{([^}]+)\}', '.tex'),  # \import{path}{file}
    (r'\\subimport\{([^}]*)\}\{([^}]+)\}', '.tex'),
    (r'\\loadglsentries\{([^}]+)\}', '.tex'),
    (r'\\makeglossaries', None),
    (r'\\InputIfFileExists\{([^}]+)\}', None),
]

IMAGE_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.eps', '.svg', '.gif', '.bmp', '.tiff']

# Always keep these files regardless of reference analysis
ALWAYS_KEEP = {
    '.latexmkrc', 'latexmkrc', 'Makefile', 'makefile',
    '.gitignore', 'README.md', 'readme.md', 'LICENSE',
}

# Always remove these files/patterns (Overleaf artifacts)
ALWAYS_REMOVE_PATTERNS = [
    r'\.aux$', r'\.log$', r'\.out$', r'\.toc$', r'\.lof$', r'\.lot$',
    r'\.fls$', r'\.fdb_latexmk$', r'\.synctex\.gz$', r'\.bbl$', r'\.blg$',
    r'\.nav$', r'\.snm$', r'\.vrb$', r'\.idx$', r'\.ind$', r'\.ilg$',
    r'\.glg$', r'\.gls$', r'\.glo$', r'\.ist$',
    r'\.run\.xml$', r'-blx\.bib$',
]


def resolve_file(base_dir: Path, ref: str, default_ext: str | None) -> list[Path]:
    """Resolve a LaTeX file reference to actual file path(s)."""
    candidates = []
    ref_path = Path(ref)

    # If the reference already has an extension, try it directly
    if ref_path.suffix:
        candidates.append(base_dir / ref_path)
    else:
        # Try with default extension
        if default_ext:
            candidates.append(base_dir / (ref + default_ext))
        # Try without extension (file might exist as-is)
        candidates.append(base_dir / ref)
        # For graphics, try common image extensions
        if default_ext is None:
            for ext in IMAGE_EXTENSIONS:
                candidates.append(base_dir / (ref + ext))

    return [c.resolve() for c in candidates if c.exists()]


def strip_comments(line: str) -> str:
    """Remove LaTeX comments (% to end of line), preserving escaped \\%."""
    result = []
    i = 0
    while i < len(line):
        if line[i] == '%' and (i == 0 or line[i-1] != '\\'):
            break
        result.append(line[i])
        i += 1
    return ''.join(result)


def extract_references(tex_file: Path, base_dir: Path) -> set[Path]:
    """Extract all file references from a .tex file."""
    referenced = set()  # type: set[Path]

    try:
        content = tex_file.read_text(encoding='utf-8', errors='replace')
    except (OSError, UnicodeDecodeError):
        return referenced

    # Process line by line, stripping comments
    lines = [strip_comments(line) for line in content.splitlines()]
    full_text = '\n'.join(lines)

    # Determine the base directory for relative paths (directory of current file)
    file_base = tex_file.parent

    for pattern, default_ext in INCLUDE_PATTERNS:
        for match in re.finditer(pattern, full_text):
            groups = match.groups()

            if len(groups) == 2:
                # \import{path}{file} style
                import_dir = groups[0]
                import_file = groups[1]
                search_base = file_base / import_dir if import_dir else file_base
                resolved = resolve_file(search_base, import_file, default_ext)
            elif len(groups) == 1:
                ref = groups[0]

                # Handle comma-separated lists (e.g., \bibliography{ref1,ref2})
                if ',' in ref:
                    for sub_ref in ref.split(','):
                        sub_ref = sub_ref.strip()
                        if sub_ref:
                            resolved = resolve_file(file_base, sub_ref, default_ext)
                            referenced.update(resolved)
                            # Also try from project root
                            if file_base != base_dir:
                                resolved = resolve_file(base_dir, sub_ref, default_ext)
                                referenced.update(resolved)
                    continue

                resolved = resolve_file(file_base, ref, default_ext)
                # For \usepackage, only include if it's a local .sty file
                if '\\usepackage' in pattern:
                    resolved = [r for r in resolved if r.suffix == '.sty']
            else:
                continue

            referenced.update(resolved)
            # Also try from project root for non-absolute references
            if file_base != base_dir and len(groups) == 1:
                resolved = resolve_file(base_dir, groups[0], default_ext)
                if '\\usepackage' in pattern:
                    resolved = [r for r in resolved if r.suffix == '.sty']
                referenced.update(resolved)

    return referenced


def collect_dependencies(main_tex: Path, base_dir: Path) -> set[Path]:
    """Recursively collect all file dependencies starting from main tex."""
    visited: set[Path] = set()
    to_visit: list[Path] = [main_tex.resolve()]
    all_deps: set[Path] = {main_tex.resolve()}

    while to_visit:
        current = to_visit.pop()
        if current in visited:
            continue
        visited.add(current)

        # Only parse .tex, .sty, .cls, .bib files for further references
        if current.suffix in ('.tex', '.sty', '.cls', '.ltx'):
            refs = extract_references(current, base_dir)
            all_deps.update(refs)
            # Queue parseable files for recursive analysis
            for ref in refs:
                if ref.suffix in ('.tex', '.sty', '.cls', '.ltx') and ref not in visited:
                    to_visit.append(ref)

    return all_deps


def is_always_remove(filepath: Path) -> bool:
    """Check if file matches always-remove patterns (LaTeX build artifacts)."""
    name = filepath.name
    return any(re.search(p, name) for p in ALWAYS_REMOVE_PATTERNS)


def main():
    parser = argparse.ArgumentParser(description='Clean unused files from Overleaf project')
    parser.add_argument('project_dir', help='Path to the unzipped project directory')
    parser.add_argument('--main', required=True, help='Main .tex entry point (relative to project_dir)')
    parser.add_argument('--extra', nargs='*', default=[], help='Extra entry .tex files to also trace')
    parser.add_argument('--delete', action='store_true', help='Actually delete unused files')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted (default)')
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    main_tex = (project_dir / args.main).resolve()

    if not project_dir.is_dir():
        print(f"Error: {project_dir} is not a directory", file=sys.stderr)
        sys.exit(1)
    if not main_tex.is_file():
        print(f"Error: {main_tex} does not exist", file=sys.stderr)
        sys.exit(1)

    # Collect dependencies from main entry
    print(f"Analyzing dependencies from: {args.main}")
    deps = collect_dependencies(main_tex, project_dir)

    # Also trace extra entry files
    for extra in args.extra:
        extra_path = (project_dir / extra).resolve()
        if extra_path.is_file():
            print(f"Also tracing: {extra}")
            extra_deps = collect_dependencies(extra_path, project_dir)
            deps.update(extra_deps)

    # Enumerate all files in project
    all_files = set()
    for root, dirs, files in os.walk(project_dir):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            all_files.add(Path(root, f).resolve())

    # Categorize files
    kept = set()
    removed_artifacts = []
    removed_unused = []

    for f in sorted(all_files):
        rel = f.relative_to(project_dir)

        # Always remove build artifacts
        if is_always_remove(f):
            removed_artifacts.append(rel)
            continue

        # Always keep certain files
        if f.name in ALWAYS_KEEP or f.name.startswith('.'):
            kept.add(rel)
            continue

        # Keep if referenced
        if f in deps:
            kept.add(rel)
            continue

        # .cls and .bst files are often needed implicitly
        if f.suffix in ('.cls', '.bst', '.def'):
            kept.add(rel)
            continue

        # Unreferenced
        removed_unused.append(rel)

    # Report
    print(f"\n{'='*60}")
    print(f"Project: {project_dir}")
    print(f"Entry:   {args.main}")
    print(f"{'='*60}")
    print(f"Total files:      {len(all_files)}")
    print(f"Referenced:        {len(kept)}")
    print(f"Build artifacts:   {len(removed_artifacts)}")
    print(f"Unused:            {len(removed_unused)}")
    print(f"{'='*60}")

    if removed_artifacts:
        print(f"\nBuild artifacts to remove:")
        for f in sorted(removed_artifacts):
            print(f"  [artifact] {f}")

    if removed_unused:
        print(f"\nUnused files to remove:")
        for f in sorted(removed_unused):
            print(f"  [unused]   {f}")

    if not removed_artifacts and not removed_unused:
        print("\nNo files to remove - project is clean!")
        return

    # Delete if requested
    if args.delete and not args.dry_run:
        deleted = 0
        for rel in removed_artifacts + removed_unused:
            full = project_dir / rel
            try:
                full.unlink()
                deleted += 1
            except OSError as e:
                print(f"  Warning: Could not delete {rel}: {e}", file=sys.stderr)

        # Remove empty directories
        for root, dirs, files in os.walk(project_dir, topdown=False):
            for d in dirs:
                dir_path = Path(root) / d
                try:
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        print(f"  Removed empty dir: {dir_path.relative_to(project_dir)}")
                except OSError:
                    pass

        print(f"\nDeleted {deleted} files.")
    else:
        print(f"\nDry run - no files deleted. Use --delete to remove.")


if __name__ == '__main__':
    main()
