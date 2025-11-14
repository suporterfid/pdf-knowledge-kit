"""Version information for PDF Knowledge Kit."""

__version__ = "1.0.1"
__version_info__ = tuple(int(i) for i in __version__.split(".") if i.isdigit())

# Build information (populated during CI/CD)
__build_date__ = None
__commit_sha__ = None
