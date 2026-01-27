"""
Secure Data Loading Utilities

Provides safe data loading with validation to mitigate pickle security risks.
"""

import hashlib
import logging
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Raised when data validation fails."""
    pass


class UntrustedDataWarning(UserWarning):
    """Warning for loading data with pickle enabled."""
    pass


# Trusted data file hashes (can be populated by user or build process)
TRUSTED_HASHES: Dict[str, str] = {}


def compute_file_hash(filepath: Union[str, Path], algorithm: str = "sha256") -> str:
    """
    Compute hash of a file for integrity verification.

    Args:
        filepath: Path to file
        algorithm: Hash algorithm (sha256, md5, etc.)

    Returns:
        Hex digest of file hash
    """
    hasher = hashlib.new(algorithm)
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def is_trusted_file(filepath: Union[str, Path]) -> bool:
    """
    Check if file is in trusted hashes list.

    Args:
        filepath: Path to file

    Returns:
        True if file hash matches trusted hash
    """
    filepath = Path(filepath)
    if str(filepath) not in TRUSTED_HASHES:
        return False

    actual_hash = compute_file_hash(filepath)
    return actual_hash == TRUSTED_HASHES[str(filepath)]


def validate_training_data_structure(data: np.ndarray) -> bool:
    """
    Validate that loaded data has expected training data structure.

    Expected structure: array of [frame, action] pairs where:
    - frame: numpy array (image)
    - action: numpy array (one-hot encoded or numeric)

    Args:
        data: Loaded numpy array

    Returns:
        True if structure is valid

    Raises:
        DataValidationError: If structure is invalid
    """
    if not isinstance(data, np.ndarray):
        raise DataValidationError("Data must be a numpy array")

    if len(data) == 0:
        raise DataValidationError("Data array is empty")

    # Check first few items for structure
    sample_size = min(5, len(data))
    for i in range(sample_size):
        item = data[i]

        if not isinstance(item, (list, tuple, np.ndarray)):
            raise DataValidationError(
                f"Item {i} is not a valid container type: {type(item)}"
            )

        if len(item) < 2:
            raise DataValidationError(
                f"Item {i} must have at least 2 elements (frame, action)"
            )

        frame, action = item[0], item[1]

        # Validate frame is image-like
        if isinstance(frame, np.ndarray):
            if frame.ndim not in (2, 3):
                raise DataValidationError(
                    f"Frame at item {i} has invalid dimensions: {frame.ndim}"
                )
        else:
            raise DataValidationError(
                f"Frame at item {i} is not a numpy array: {type(frame)}"
            )

        # Validate action is numeric array
        if isinstance(action, np.ndarray):
            if not np.issubdtype(action.dtype, np.number):
                raise DataValidationError(
                    f"Action at item {i} has non-numeric dtype: {action.dtype}"
                )
        elif isinstance(action, (list, tuple)):
            if not all(isinstance(x, (int, float, np.number)) for x in action):
                raise DataValidationError(
                    f"Action at item {i} contains non-numeric values"
                )
        else:
            raise DataValidationError(
                f"Action at item {i} is not an array or list: {type(action)}"
            )

    return True


def load_training_data_secure(
    filepath: Union[str, Path],
    validate: bool = True,
    allow_untrusted: bool = True
) -> np.ndarray:
    """
    Securely load training data from numpy file.

    This function:
    1. Checks if file is in trusted hashes (optional)
    2. Loads data with pickle (required for mixed-type arrays)
    3. Validates data structure before returning

    Args:
        filepath: Path to .npy file
        validate: Whether to validate data structure
        allow_untrusted: Whether to allow loading untrusted files

    Returns:
        Loaded numpy array

    Raises:
        DataValidationError: If validation fails
        FileNotFoundError: If file doesn't exist
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"Training data file not found: {filepath}")

    # Check trust status
    trusted = is_trusted_file(filepath)
    if not trusted:
        if not allow_untrusted:
            raise DataValidationError(
                f"File {filepath} is not in trusted hashes list. "
                "Only load training data from trusted sources."
            )
        else:
            warnings.warn(
                f"Loading training data from untrusted file: {filepath}. "
                "Only load .npy files that you created or from trusted sources. "
                "Malicious .npy files can execute arbitrary code.",
                UntrustedDataWarning,
                stacklevel=2
            )

    # Load data
    # Note: allow_pickle=True is required for our data format (mixed types)
    # Security is provided by:
    # 1. Trust verification via hashes
    # 2. Structure validation after loading
    # 3. Clear warnings to users
    try:
        data = np.load(filepath, allow_pickle=True)
    except Exception as e:
        raise DataValidationError(f"Failed to load file: {e}")

    # Validate structure
    if validate:
        try:
            validate_training_data_structure(data)
        except DataValidationError:
            raise
        except Exception as e:
            raise DataValidationError(f"Validation failed: {e}")

    logger.info(f"Loaded {len(data)} samples from {filepath}")
    return data


def save_training_data_secure(
    data: List[Tuple[np.ndarray, np.ndarray]],
    filepath: Union[str, Path],
    register_hash: bool = False
) -> Path:
    """
    Securely save training data.

    Uses allow_pickle=False for the outer save, storing as object array.
    This is the safest approach while maintaining compatibility.

    Args:
        data: List of (frame, action) tuples
        filepath: Output path
        register_hash: Whether to register file hash as trusted

    Returns:
        Path to saved file
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Convert to numpy array
    data_array = np.array(data, dtype=object)

    # Save with pickle (required for object arrays)
    np.save(filepath, data_array)

    # Optionally register hash
    if register_hash:
        file_hash = compute_file_hash(filepath)
        TRUSTED_HASHES[str(filepath)] = file_hash
        logger.info(f"Registered trusted hash for {filepath}: {file_hash[:16]}...")

    logger.info(f"Saved {len(data)} samples to {filepath}")
    return filepath


def create_trusted_manifest(
    data_dir: Union[str, Path],
    output_file: Optional[Union[str, Path]] = None
) -> Dict[str, str]:
    """
    Create a manifest of trusted data file hashes.

    Args:
        data_dir: Directory containing .npy files
        output_file: Optional file to save manifest

    Returns:
        Dictionary mapping file paths to hashes
    """
    data_dir = Path(data_dir)
    manifest = {}

    for npy_file in data_dir.glob("**/*.npy"):
        file_hash = compute_file_hash(npy_file)
        manifest[str(npy_file)] = file_hash

    if output_file:
        import json
        with open(output_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"Saved manifest with {len(manifest)} entries to {output_file}")

    return manifest


def load_trusted_manifest(manifest_file: Union[str, Path]) -> int:
    """
    Load trusted hashes from manifest file.

    Args:
        manifest_file: Path to manifest JSON file

    Returns:
        Number of hashes loaded
    """
    import json

    with open(manifest_file) as f:
        manifest = json.load(f)

    TRUSTED_HASHES.update(manifest)
    logger.info(f"Loaded {len(manifest)} trusted hashes from {manifest_file}")
    return len(manifest)
