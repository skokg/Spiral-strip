"""Build, test and collect distributions for the manual GitHub Actions workflow.

This helper never uploads packages, creates releases or changes repository files.
Only the build command requires Python 3.11+; test supports Python 3.10+.
"""

import argparse
from email.parser import BytesParser
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import traceback
import zipfile


ROOT = Path(__file__).resolve().parents[2]
TARGETS = ("linux-x86_64", "windows-x86_64", "macos-intel", "macos-apple-silicon")
VERSIONS = ("3.10", "3.11", "3.12", "3.13", "3.14", "3.15")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run(arguments, cwd=None):
    command = [str(argument) for argument in arguments]
    print("+ " + shlex.join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def extract_source(archive, destination):
    """Extract our sdist without accepting links or paths outside a fresh folder."""
    destination = Path(destination).resolve()
    destination.mkdir()
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        for member in members:
            target = (destination / member.name).resolve()
            require(target.is_relative_to(destination), "Unsafe source archive path")
            require(member.isdir() or member.isfile(), "Unexpected archive member type")
        for member in members:
            target = destination / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as reader, target.open("wb") as writer:
                    shutil.copyfileobj(reader, writer)
    roots = list(destination.iterdir())
    require(len(roots) == 1 and roots[0].is_dir(), "Expected one sdist root directory")
    require((roots[0] / "pyproject.toml").is_file(), "Missing source build configuration")
    return roots[0]


def build():
    import tomllib

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = config["project"]["version"]
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    require(not any(dist.iterdir()), "dist/ must be empty before building")
    source = dist / f"spiralstrip-{version}.tar.gz"
    wheel = dist / f"spiralstrip-{version}-py3-none-any.whl"
    run([sys.executable, "-I", "-m", "build", "--sdist", "--outdir", dist, ROOT])
    require(source.is_file(), "Expected source archive is missing")
    with tempfile.TemporaryDirectory(prefix="spiralstrip-build-") as directory:
        extracted = extract_source(source, Path(directory) / "source")
        run([sys.executable, "-I", "-m", "build", "--wheel", "--outdir", dist, extracted])
        require(wheel.is_file(), "Expected universal wheel is missing")
        require(len(list(dist.iterdir())) == 2, "Expected exactly one wheel and one sdist")
        expected = ["spiralstrip.py", "spiralstrip_examples/__init__.py"]
        expected += [f"spiralstrip_examples/{path.name}" for path in
                     sorted((ROOT / "spiralstrip_examples").glob("example_*.py"))]
        with zipfile.ZipFile(wheel) as package:
            names = package.namelist()
            for name in expected:
                require(package.read(name) == (ROOT / name).read_bytes(),
                        f"Wheel source differs from checkout: {name}")
                require((extracted / name).read_bytes() == (ROOT / name).read_bytes(),
                        f"Source archive differs from checkout: {name}")
            metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
            require(len(metadata_names) == 1, "Expected one wheel METADATA file")
            metadata = BytesParser().parsebytes(package.read(metadata_names[0]))
            require(metadata["Name"] == "spiralstrip", "Incorrect wheel package name")
            require(metadata["Version"] == version, "Wheel version does not match pyproject.toml")
            require(metadata["Requires-Python"] == config["project"]["requires-python"],
                    "Incorrect Python requirement in wheel metadata")
            require(any(name.endswith(".dist-info/licenses/LICENSE") for name in names),
                    "Missing wheel license")
            require(not any(name.startswith(("tests/", "conda_recipe/", ".github/"))
                            for name in names), "Development files leaked into the wheel")
        source_metadata = BytesParser().parsebytes((extracted / "PKG-INFO").read_bytes())
        require(source_metadata["Version"] == version, "Source metadata version mismatch")
        require((extracted / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes(),
                "Source license differs from checkout")
        require(not (extracted / "conda_recipe").exists(), "Conda recipe leaked into sdist")
        require(not (extracted / ".github").exists(), "Workflow files leaked into sdist")
        smoke = ROOT / "tests" / "smoke_test.py"
        require((extracted / "tests" / "smoke_test.py").read_bytes() == smoke.read_bytes(),
                "Smoke tests missing or different in the source archive")
    run([sys.executable, "-I", "-m", "twine", "check", wheel, source])
    shutil.copy2(smoke, dist / "smoke_test.py")
    info = {
        "version": version,
        "commit": os.environ["GITHUB_SHA"],
        "run_url": (f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
                    f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"),
        "files": {path.name: digest(path) for path in (wheel, source)},
        "module_sha256": digest(ROOT / "spiralstrip.py"),
        "smoke_sha256": digest(smoke),
    }
    write_json(dist / "BUILD_INFO.json", info)
    print(json.dumps(info, indent=2), flush=True)


PROVENANCE_CHECK = """
import hashlib, importlib.metadata as metadata, pathlib, sys
import spiralstrip, spiralstrip_examples
assert metadata.version('spiralstrip') == sys.argv[1], 'Wrong installed version'
prefix = pathlib.Path(sys.prefix).resolve()
for module in (spiralstrip, spiralstrip_examples):
    path = pathlib.Path(module.__file__).resolve()
    assert path.is_relative_to(prefix), 'Import did not come from the clean environment'
    print('Installed module:', path)
assert hashlib.sha256(pathlib.Path(spiralstrip.__file__).read_bytes()).hexdigest() == sys.argv[2], 'Installed module differs from built source'
for name in ('spiralstrip', 'numpy', 'matplotlib', 'Pillow'):
    print(name, metadata.version(name))
"""


def test():
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    result = {
        "target": os.environ["TEST_TARGET"],
        "python": os.environ["TEST_PYTHON"],
        "actual_python": platform.python_version(),
        "platform": platform.platform(),
        "commit": os.environ["GITHUB_SHA"],
        "success": False,
        "tested": [],
    }
    try:
        require(f"{sys.version_info.major}.{sys.version_info.minor}" == result["python"],
                "Unexpected test interpreter")
        bundle = ROOT / "incoming" / "build"
        info = json.loads((bundle / "BUILD_INFO.json").read_text(encoding="utf-8"))
        require(info["commit"] == result["commit"], "Build and test commits differ")
        require(len(info["files"]) == 2, "Expected two distributions")
        result["files"] = info["files"]
        for name, checksum in info["files"].items():
            require(Path(name).name == name, "Unexpected distribution path")
            require(digest(bundle / name) == checksum, f"Distribution hash mismatch: {name}")
        require(digest(bundle / "smoke_test.py") == info["smoke_sha256"],
                "Smoke-test hash mismatch")
        for name in sorted(info["files"]):
            with tempfile.TemporaryDirectory(prefix="spiralstrip-check-",
                                             dir=os.environ["RUNNER_TEMP"]) as directory:
                work = Path(directory)
                environment = work / "venv"
                run([sys.executable, "-I", "-m", "venv", environment], cwd=work)
                python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                archive = bundle / name
                if name.endswith(".tar.gz"):
                    source = extract_source(archive, work / "source")
                    smoke = source / "tests" / "smoke_test.py"
                    require(digest(smoke) == info["smoke_sha256"], "Source smoke tests differ")
                else:
                    require(name.endswith("-py3-none-any.whl"), "Unexpected wheel type")
                    smoke = bundle / "smoke_test.py"
                run([python, "-I", "-m", "pip", "install", "--verbose", "--no-cache-dir", archive], cwd=work)
                run([python, "-I", "-m", "pip", "check"], cwd=work)
                run([python, "-I", "-c", PROVENANCE_CHECK, info["version"], info["module_sha256"]], cwd=work)
                run([python, "-I", smoke], cwd=work)
                result["tested"].append(name)
        result["success"] = True
    except Exception:
        result["error"] = traceback.format_exc()
        raise
    finally:
        write_json(logs / "result.json", result)


def collect():
    incoming = ROOT / "incoming"
    bundle = ROOT / "release-bundle"
    bundle.mkdir(exist_ok=True)
    problems = []
    info = {}
    source = incoming / "build"
    try:
        info = json.loads((source / "BUILD_INFO.json").read_text(encoding="utf-8"))
        require(info["commit"] == os.environ["GITHUB_SHA"], "Build commit differs")
        require(set(info["files"]) == {
            f"spiralstrip-{info['version']}-py3-none-any.whl",
            f"spiralstrip-{info['version']}.tar.gz",
        }, "Unexpected distribution names")
        for name, checksum in info["files"].items():
            require(digest(source / name) == checksum, f"Distribution hash mismatch: {name}")
            shutil.copy2(source / name, bundle / name)
        shutil.copy2(source / "BUILD_INFO.json", bundle / "BUILD_INFO.json")
    except Exception as error:
        problems.append(f"Distribution verification: {error}")
    if (incoming / "logs").is_dir():
        shutil.copytree(incoming / "logs", bundle / "logs", dirs_exist_ok=True)
    if (incoming / "github-jobs.log").is_file():
        shutil.copy2(incoming / "github-jobs.log", bundle / "github-jobs.log")
    else:
        problems.append("Complete GitHub job logs were not collected")
    try:
        problems.extend(json.loads((incoming / "log-download-errors.json").read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        problems.append(f"Job-log collection status unavailable: {error}")
    targets = TARGETS if os.environ["SELECTED_TARGET"] == "all" else (os.environ["SELECTED_TARGET"],)
    versions = VERSIONS if os.environ["SELECTED_PYTHON"] == "all" else (os.environ["SELECTED_PYTHON"],)
    require(set(targets).issubset(TARGETS) and set(versions).issubset(VERSIONS), "Invalid matrix selection")
    expected = set(itertools.product(targets, versions))
    results = {}
    for path in sorted((bundle / "logs").rglob("result.json")):
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            key = (result["target"], result["python"])
            require(key in expected and key not in results, "Unexpected or duplicate test result")
            require(result["commit"] == os.environ["GITHUB_SHA"], "Test commit differs")
            require(result.get("files") == info.get("files"), "Tested distributions differ from collected files")
            require(result["success"] and sorted(result["tested"]) == sorted(info["files"]),
                    "Both distributions did not pass installation and smoke tests")
            results[key] = result
        except Exception as error:
            problems.append(f"{path.relative_to(bundle)}: {error}")
    for target, version in sorted(expected - results.keys()):
        problems.append(f"No successful test result: {target} / Python {version}")
    for job in ("BUILD", "TEST"):
        if os.environ[f"{job}_JOB_RESULT"] != "success":
            problems.append(f"{job.lower()} job result: {os.environ[f'{job}_JOB_RESULT']}")
    complete = not problems
    report = (f"Bundle status: {'COMPLETE' if complete else 'INCOMPLETE'}\n"
              f"Commit: {os.environ['GITHUB_SHA']}\n"
              f"Successful test configurations: {len(results)} / {len(expected)}\n"
              "Expected distributions: one universal wheel and one source archive\n"
              + "\n".join(problems) + "\n")
    (bundle / "BUILD_STATUS.txt").write_text(report, encoding="utf-8")
    write_json(bundle / "TEST_RESULTS.json", list(results.values()))
    with (bundle / "spiralstrip-build.log").open("w", encoding="utf-8") as combined:
        combined.write(report)
        for path in sorted(bundle.rglob("*.log")):
            if path.name == "spiralstrip-build.log":
                continue
            combined.write("\n" + "=" * 80 + "\n" + path.relative_to(bundle).as_posix() + "\n")
            combined.write(path.read_text(encoding="utf-8", errors="replace") + "\n")
    checksums = [f"{digest(path)}  {path.relative_to(bundle).as_posix()}"
                 for path in sorted(bundle.rglob("*")) if path.is_file() and path.name != "SHA256SUMS.txt"]
    (bundle / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("## Spiral Strip distributions\n\n```text\n" + report + "```\n\n"
                         "**spiralstrip-pypi**: only the wheel and source archive, after all checks pass.\n\n"
                         "**spiralstrip-distributions**: available distributions, logs, status, test results and SHA-256.\n\n"
                         "**spiralstrip-build.log** is also downloadable separately. Nothing is published to PyPI.\n")
    print(report, flush=True)
    require(complete, "Incomplete bundle; see BUILD_STATUS.txt and spiralstrip-build.log")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "test", "collect"))
    arguments = parser.parse_args()
    {"build": build, "test": test, "collect": collect}[arguments.command]()
