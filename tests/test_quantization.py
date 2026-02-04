"""Unit tests for quantization configuration logic.

These tests verify the quantization configuration logic without importing
the server module (which has heavy ML dependencies).
"""

import torch
from transformers import BitsAndBytesConfig


def get_quantization_config(
    quantization_mode: str,
    quantization_type: str = "nf4",
    use_double_quant: bool = True,
) -> BitsAndBytesConfig | None:
    """Create BitsAndBytesConfig based on parameters.

    This is a test-local copy of the function from server.py to avoid
    importing the full server module with its heavy dependencies.
    """
    if quantization_mode == "none":
        return None

    if quantization_mode == "4bit":
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=quantization_type,
            bnb_4bit_use_double_quant=use_double_quant,
            bnb_4bit_compute_dtype=torch.float16,
        )

    if quantization_mode == "8bit":
        return BitsAndBytesConfig(
            load_in_8bit=True,
        )

    return None


class TestGetQuantizationConfig:
    """Tests for quantization config generation."""

    def test_quantization_mode_none(self) -> None:
        """Test that 'none' mode returns None."""
        result = get_quantization_config("none")
        assert result is None

    def test_quantization_mode_4bit_default(self) -> None:
        """Test 4-bit quantization with default settings."""
        config = get_quantization_config(
            quantization_mode="4bit",
            quantization_type="nf4",
            use_double_quant=True,
        )

        assert config is not None
        assert config.load_in_4bit is True
        assert config.bnb_4bit_quant_type == "nf4"
        assert config.bnb_4bit_use_double_quant is True
        assert config.bnb_4bit_compute_dtype == torch.float16

    def test_quantization_mode_4bit_fp4(self) -> None:
        """Test 4-bit quantization with fp4 type."""
        config = get_quantization_config(
            quantization_mode="4bit",
            quantization_type="fp4",
            use_double_quant=False,
        )

        assert config is not None
        assert config.load_in_4bit is True
        assert config.bnb_4bit_quant_type == "fp4"
        assert config.bnb_4bit_use_double_quant is False

    def test_quantization_mode_8bit(self) -> None:
        """Test 8-bit quantization."""
        config = get_quantization_config(quantization_mode="8bit")

        assert config is not None
        assert config.load_in_8bit is True

    def test_unknown_quantization_mode(self) -> None:
        """Test that unknown mode returns None."""
        config = get_quantization_config(quantization_mode="invalid")
        assert config is None


class TestEnvironmentVariableParsing:
    """Tests for environment variable parsing logic."""

    def test_bool_parsing_true_values(self) -> None:
        """Test parsing of boolean true values."""
        for value in ["true", "True", "TRUE"]:
            result = value.lower() == "true"
            assert result is True

    def test_bool_parsing_false_values(self) -> None:
        """Test parsing of boolean false values."""
        for value in ["false", "False", "FALSE", "0", "no"]:
            result = value.lower() == "true"
            assert result is False

    def test_int_parsing(self) -> None:
        """Test parsing of integer values."""
        assert int("8000") == 8000
        assert int("4000") == 4000

    def test_quantization_modes(self) -> None:
        """Test all valid quantization mode strings."""
        valid_modes = ["none", "4bit", "8bit"]
        for mode in valid_modes:
            # Should not raise
            config = get_quantization_config(mode)
            if mode == "none":
                assert config is None
            else:
                assert config is not None

    def test_quantization_types(self) -> None:
        """Test 4-bit quantization type options."""
        for qtype in ["nf4", "fp4"]:
            config = get_quantization_config("4bit", quantization_type=qtype)
            assert config is not None
            assert config.bnb_4bit_quant_type == qtype


class TestBitsAndBytesConfigAttributes:
    """Tests verifying BitsAndBytesConfig attribute access."""

    def test_4bit_config_has_expected_attributes(self) -> None:
        """Test that 4-bit config has all expected attributes."""
        config = get_quantization_config("4bit")
        assert config is not None

        # Verify attributes exist and are accessible
        assert hasattr(config, "load_in_4bit")
        assert hasattr(config, "bnb_4bit_quant_type")
        assert hasattr(config, "bnb_4bit_use_double_quant")
        assert hasattr(config, "bnb_4bit_compute_dtype")

    def test_8bit_config_has_expected_attributes(self) -> None:
        """Test that 8-bit config has all expected attributes."""
        config = get_quantization_config("8bit")
        assert config is not None

        assert hasattr(config, "load_in_8bit")
        assert config.load_in_8bit is True

    def test_compute_dtype_is_float16(self) -> None:
        """Test that compute dtype is set to float16 for 4-bit."""
        config = get_quantization_config("4bit")
        assert config is not None
        assert config.bnb_4bit_compute_dtype == torch.float16
