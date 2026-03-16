"""RDS scanner — index sequencing directories and check READMEs.

Scans a mounted RDS directory for sequencing data, analysis outputs,
and checks for documentation quality.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from lab_agents.config import Config

logger = logging.getLogger(__name__)


@dataclass
class RDSDirectory:
    """A directory on RDS with metadata."""

    path: str
    name: str
    has_readme: bool = False
    readme_lines: int = 0
    total_files: int = 0
    total_size_mb: float = 0.0
    last_modified: datetime | None = None
    file_types: dict[str, int] = field(default_factory=dict)
    contains_fastq: bool = False
    contains_bam: bool = False
    contains_results: bool = False


@dataclass
class RDSScanResult:
    """Result of scanning RDS."""

    directories: list[RDSDirectory] = field(default_factory=list)
    dirs_missing_readme: list[str] = field(default_factory=list)
    orphan_data: list[str] = field(default_factory=list)  # data with no README context
    total_size_gb: float = 0.0


# File extensions that indicate sequencing data
SEQUENCING_EXTENSIONS = {".fastq", ".fastq.gz", ".fq", ".fq.gz"}
ALIGNMENT_EXTENSIONS = {".bam", ".cram", ".sam"}
RESULTS_EXTENSIONS = {".h5ad", ".rds", ".RDS", ".h5", ".loom", ".csv", ".tsv"}


class RDSScanner:
    """Scans RDS directories for data governance checks."""

    def __init__(self, rds_path: str | None = None):
        self.rds_path = Path(rds_path or Config.RDS_PATH)

    def is_available(self) -> bool:
        """Check if RDS is mounted and accessible."""
        return self.rds_path.exists() and self.rds_path.is_dir()

    def scan(self, max_depth: int = 2) -> RDSScanResult:
        """Scan RDS directories up to max_depth levels."""
        if not self.is_available():
            logger.warning("RDS not available at %s", self.rds_path)
            return RDSScanResult()

        result = RDSScanResult()

        try:
            for item in sorted(self.rds_path.iterdir()):
                if item.is_dir() and not item.name.startswith("."):
                    dir_info = self._scan_directory(item, max_depth)
                    result.directories.append(dir_info)
                    result.total_size_gb += dir_info.total_size_mb / 1024

                    if not dir_info.has_readme:
                        result.dirs_missing_readme.append(dir_info.name)

                    # Orphan data: has sequencing files but no README
                    if (
                        dir_info.contains_fastq or dir_info.contains_bam
                    ) and not dir_info.has_readme:
                        result.orphan_data.append(dir_info.name)

        except PermissionError as e:
            logger.error("Permission denied scanning RDS: %s", e)
        except Exception as e:
            logger.error("Error scanning RDS: %s", e)

        logger.info(
            "Scanned %d directories, %.1f GB total, %d missing READMEs",
            len(result.directories),
            result.total_size_gb,
            len(result.dirs_missing_readme),
        )
        return result

    def _scan_directory(self, path: Path, depth: int) -> RDSDirectory:
        """Scan a single directory for metadata."""
        dir_info = RDSDirectory(
            path=str(path),
            name=path.name,
        )

        try:
            readme_path = path / "README.md"
            if not readme_path.exists():
                readme_path = path / "README"
            if not readme_path.exists():
                readme_path = path / "README.txt"

            if readme_path.exists():
                dir_info.has_readme = True
                try:
                    dir_info.readme_lines = len(
                        readme_path.read_text(errors="replace").splitlines()
                    )
                except Exception:
                    pass

            latest_mtime = 0.0
            file_types: dict[str, int] = {}

            for item in path.rglob("*"):
                if item.is_file():
                    dir_info.total_files += 1
                    try:
                        size = item.stat().st_size
                        dir_info.total_size_mb += size / (1024 * 1024)
                        mtime = item.stat().st_mtime
                        if mtime > latest_mtime:
                            latest_mtime = mtime
                    except (OSError, PermissionError):
                        continue

                    suffix = item.suffix.lower()
                    # Handle .gz double extensions
                    if suffix == ".gz" and item.stem.endswith(
                        (".fastq", ".fq", ".vcf", ".bed")
                    ):
                        suffix = "." + item.stem.rsplit(".", 1)[-1] + ".gz"

                    file_types[suffix] = file_types.get(suffix, 0) + 1

                    if suffix in SEQUENCING_EXTENSIONS or suffix in {
                        ".fastq.gz",
                        ".fq.gz",
                    }:
                        dir_info.contains_fastq = True
                    elif suffix in ALIGNMENT_EXTENSIONS:
                        dir_info.contains_bam = True
                    elif suffix in RESULTS_EXTENSIONS:
                        dir_info.contains_results = True

                # Limit depth of recursion
                if depth <= 1:
                    break

            dir_info.file_types = file_types
            if latest_mtime > 0:
                dir_info.last_modified = datetime.fromtimestamp(
                    latest_mtime, tz=timezone.utc
                )

        except PermissionError:
            logger.warning("Permission denied: %s", path)
        except Exception as e:
            logger.warning("Error scanning %s: %s", path, e)

        return dir_info
