"""Bounded ordinary evidence reads and JUnit checks shared by Host adapters.

These readers execute no artifact code. A trusted caller must authorize the pin
and the complete test identity set independently of the candidate.
"""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any
import xml.etree.ElementTree as ET

_HEX = re.compile(r"[0-9a-f]{64}\Z")


class OutcomeVerificationError(ValueError):
    """The supplied evidence is unauthorized, incomplete or inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OutcomeVerificationError(message)


def _relative(value: str) -> str:
    _require(isinstance(value, str) and bool(value) and "\\" not in value and "\0" not in value,
             "Invalid relative evidence path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and all(part not in {"", ".", ".."} for part in value.split("/")),
             "Absolute paths and traversal are forbidden")
    return path.as_posix()


def _digest(value: Any) -> str:
    _require(isinstance(value, str) and _HEX.fullmatch(value) is not None, "Invalid SHA256 digest")
    return value


class EvidenceFiles:
    """Pinned file-descriptor traversal; no resolve(), symlink following or code imports."""

    def __init__(self, root: Path):
        self.root = root.absolute()
        _require(".." not in self.root.parts, "Archive root traversal is forbidden")
        self.fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for component in self.root.parts[1:]:
                next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                  dir_fd=self.fd)
                os.close(self.fd)
                self.fd = next_fd
        except BaseException:
            os.close(self.fd)
            raise
        self.files_read: dict[str, str] = {}
        self.total_read = 0

    def close(self) -> None:
        os.close(self.fd)

    def _parent(self, relative: str) -> tuple[int, str]:
        parts = _relative(relative).split("/")
        fd = os.dup(self.fd)
        try:
            for part in parts[:-1]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            return fd, parts[-1]
        except BaseException:
            os.close(fd)
            raise

    def read(self, relative: str, limit: int, expected: str | None = None) -> bytes:
        parent_fd, name = self._parent(relative)
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
            try:
                before = os.fstat(fd)
                _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                         "Evidence must be a regular single-link file")
                _require(before.st_size <= limit, "Evidence file exceeds its byte budget")
                with os.fdopen(fd, "rb", closefd=False) as stream:
                    data = stream.read(limit + 1)
                after = os.fstat(fd)
                _require(len(data) <= limit and (before.st_dev, before.st_ino, before.st_size,
                         before.st_mtime_ns, before.st_ctime_ns) == (after.st_dev, after.st_ino,
                         after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                         "Evidence changed during collection")
            finally:
                os.close(fd)
        finally:
            os.close(parent_fd)
        actual = sha256(data).hexdigest()
        if expected is not None:
            _require(actual == _digest(expected), "Evidence digest differs from trusted pin")
        self.files_read[relative] = actual
        self.total_read += len(data)
        _require(self.total_read <= 256 * 1024**2, "Aggregate evidence byte budget exceeded")
        return data

    def reference(self, value: str) -> str:
        _require(isinstance(value, str), "Evidence reference must be text")
        path = Path(value)
        if path.is_absolute():
            try:
                value = path.relative_to(self.root).as_posix()
            except ValueError as error:
                raise OutcomeVerificationError("Evidence reference is outside authorized archive") from error
        return _relative(value)


def _json(data: bytes) -> Any:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            _require(key not in value, "Duplicate JSON key")
            value[key] = item
        return value
    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                            parse_constant=lambda _: (_ for _ in ()).throw(OutcomeVerificationError("Nonfinite JSON value")))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise OutcomeVerificationError("Invalid evidence JSON") from error
    def depth(value, level=0):
        _require(level <= 40, "Evidence JSON nesting budget exceeded")
        if isinstance(value, dict):
            for item in value.values():
                depth(item, level + 1)
        elif isinstance(value, list):
            for item in value:
                depth(item, level + 1)
    depth(result)
    return result


def read_junit(data: bytes, required: list[str], *, identity="name") -> dict:
    try:
        text = data.decode("utf-8")
        _require(not re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I), "JUnit DTD/entity declaration refused")
        root = ET.fromstring(text)
    except (UnicodeDecodeError, ET.ParseError, RecursionError) as error:
        raise OutcomeVerificationError("Invalid JUnit XML") from error
    _require(root.tag in {"testsuite", "testsuites"}, "Invalid JUnit root")
    counts = {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    tests = []
    for suite in (element for element in root.iter() if element.tag in {'testsuite','testsuites'}):
        cases = list(suite.iter("testcase"))
        actual = {"tests": len(cases), "failures": sum(c.find("failure") is not None for c in cases),
                  "errors": sum(c.find("error") is not None for c in cases),
                  "skipped": sum(c.find("skipped") is not None for c in cases)}
        for key, number in actual.items():
            if key in suite.attrib:
                _require(suite.attrib[key].isdigit() and int(suite.attrib[key]) == number,
                         "JUnit declared count differs from actual cases")
    for case in root.iter("testcase"):
        _require(sum(len(case.findall(kind)) for kind in ("failure", "error", "skipped")) <= 1,
                 "JUnit testcase has duplicate or conflicting outcomes")
        duration = float(case.get("time", "0"))
        _require(math.isfinite(duration) and duration >= 0, "Invalid JUnit duration")
        outcome, category = ("ERROR", "errors") if case.find("error") is not None else (
            ("FAIL", "failed") if case.find("failure") is not None else (
                ("SKIPPED", "skipped") if case.find("skipped") is not None else ("PASS", "passed")))
        counts["collected"] += 1
        counts[category] += 1
        tests.append({"name": case.get("name"), "nodeid": case.get("classname", "") + "::" + case.get("name", ""),
                      "outcome": outcome})
    _require(Counter(test[identity] for test in tests) == Counter(required),
             "JUnit does not contain the complete unique required test set")
    return {**counts, "tests": tests}
