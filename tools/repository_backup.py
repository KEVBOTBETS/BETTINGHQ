"""Create a restorable, full-history repository snapshot for a manual backup."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile


def run(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--required-commit", required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    mirror = root / "repository.git"
    subprocess.run(
        ["git", "clone", "--mirror", "https://github.com/KEVBOTBETS/BETTINGHQ.git", str(mirror)],
        check=True,
    )
    if run("git", "rev-parse", "--is-shallow-repository", cwd=mirror) != "false":
        raise RuntimeError("A backup must contain complete Git history")
    if (mirror / "objects/info/alternates").exists():
        raise RuntimeError("Backup depends on external Git objects")
    subprocess.run(["git", "fsck", "--connectivity-only"], cwd=mirror, check=True)
    head = run("git", "rev-parse", "refs/heads/main", cwd=mirror)
    tree = run("git", "rev-parse", head + "^{tree}", cwd=mirror)
    subprocess.run(["git", "merge-base", "--is-ancestor", args.required_commit, head], cwd=mirror, check=True)
    files = root / "files"
    files.mkdir()
    archive = root.parent / "tracked-files.tar"
    subprocess.run(["git", "archive", "--format=tar", "--output=" + str(archive), head], cwd=mirror, check=True)
    with tarfile.open(archive) as source:
        source.extractall(files, filter="data")
    archive.unlink()
    # A local clone uses hard links, not alternates, so restore verification
    # does not need another multi-gigabyte copy of immutable object packs.
    restored = root.parent / "restore-check"
    subprocess.run(["git", "clone", "--local", "--branch", "main", str(mirror), str(restored)], check=True)
    if (restored / ".git/objects/info/alternates").exists():
        raise RuntimeError("Restore check unexpectedly depends on alternates")
    if run("git", "rev-parse", "HEAD", cwd=restored) != head:
        raise RuntimeError("Restored commit differs")
    if run("git", "rev-parse", "HEAD^{tree}", cwd=restored) != tree:
        raise RuntimeError("Restored source tree differs")
    shutil.rmtree(restored)
    refs = run("git", "show-ref", cwd=mirror).splitlines()
    manifest = {
        "repository": "KEVBOTBETS/BETTINGHQ",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "main_commit": head,
        "main_tree": tree,
        "required_commit": args.required_commit,
        "refs": refs,
        "complete_history": True,
        "restore_verified": True,
        "scope": "All tracked main files plus all refs and reachable history advertised by GitHub",
        "not_in_git": ["GitHub settings, Actions secrets and caches", "Untracked files", "Browser-local private betting records"],
    }
    (root / "BACKUP-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (root / "RESTORE-README.md").write_text(
        "# BETTINGHQ backup\n\n"
        "Download the full-history ZIP and keep an offline copy before deleting the original repository.\n\n"
        "The files/ directory contains the complete tracked main snapshot: source, generated data, history files, and workflows. "
        "The full-history ZIP also includes repository.git/, a non-shallow mirror of all refs advertised by GitHub. "
        "The smaller files-only ZIP contains the same main snapshot without Git commit history.\n\n"
        "## Restore files\n\n"
        "Upload the contents of files/ to a new repository, including .github/. "
        "Configure GitHub Pages to deploy through GitHub Actions. Existing workflows use keyless public sources.\n\n"
        "## Restore full Git history\n\n"
        "Extract the full-history ZIP, then run:\n\n"
        "    git clone --no-hardlinks --branch main ./repository.git BETTINGHQ-restored\n"
        "    cd BETTINGHQ-restored\n"
        "    git remote set-url origin https://github.com/YOUR-ACCOUNT/YOUR-NEW-REPO.git\n"
        "    git push origin main\n\n"
        "Other branches and tags remain in repository.git and may be pushed explicitly to the new empty repository. "
        "GitHub-managed pull-request refs are included where advertised but cannot be pushed to GitHub's reserved refs/pull/ namespace.\n\n"
        "GitHub settings, secrets, workflow artifacts/caches and browser-local private bets are not stored in Git. "
        "The manifest records the exact source commit and successful local restore verification. "
        "No credentials are embedded in the mirror remote.\n"
    )
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as out:
            out.write(f"## Repository backup\n\nCommit: {head}\n\n"
                      f"All {len(refs)} advertised refs captured; connectivity and local restore checks passed.\n"
                      "Download and retain the ZIPs before their artifact expiry.\n")


if __name__ == "__main__":
    main()
