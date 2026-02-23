#!/usr/bin/env python3

# MIT License
# Copyright (c) 2025 - 2026 _VIFEXTech

"""
Linker script template system for FPBInject Web Server.

Provides configurable linker script generation with template support.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Dict

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================


@dataclass
class LinkerScriptConfig:
    """Configuration for linker script generation."""

    # Section names (can be customized)
    text_section: str = ".text"
    rodata_section: str = ".rodata"
    data_section: str = ".data"
    bss_section: str = ".bss"
    fpb_text_section: str = ".fpb.text"
    fpb_end_section: str = ".fpb_end"

    # Alignment settings
    section_alignment: int = 4
    bss_alignment: int = 4

    # BSS handling
    include_bss_in_binary: bool = True

    # Additional sections to include
    extra_sections: Dict[str, str] = field(default_factory=dict)

    # Custom flags
    keep_fpb_text: bool = True

    @classmethod
    def from_dict(cls, config: Dict) -> "LinkerScriptConfig":
        """Create config from dictionary."""
        return cls(**{k: v for k, v in config.items() if hasattr(cls, k)})


# ============================================================================
# Template
# ============================================================================


# Default linker script template using Python string.Template
DEFAULT_LINKER_SCRIPT_TEMPLATE = """\
/*
 * Auto-generated linker script for FPBInject
 * Base address: 0x${base_addr}
 */

SECTIONS
{
    . = 0x${base_addr};

    ${text_section} : {
        ${keep_fpb_text}*($fpb_text_section)     /* FPB inject functions */
        *($text_section $text_section.*)
    }

    $rodata_section : { *($rodata_section $rodata_section.*) }

    $data_section : { *($data_section $data_section.*) }

    $bss_section : {
        __bss_start__ = .;
        *($bss_section $bss_section.* COMMON)
        . = ALIGN($bss_alignment);
        __bss_end__ = .;
    }
${extra_sections}
${bss_marker}
}
"""

# BSS marker section to force objcopy to include BSS in binary
BSS_MARKER_TEMPLATE = """\
    /* Force objcopy to include BSS section (with zeros) in the binary */
    $fpb_end_section : {
        BYTE(0x00)
    }
"""


# ============================================================================
# Generator
# ============================================================================


class LinkerScriptGenerator:
    """
    Generate linker scripts from templates.

    Supports both built-in templates and external template files.
    """

    def __init__(self, config: LinkerScriptConfig = None, template_path: str = None):
        """
        Initialize generator.

        Args:
            config: Linker script configuration
            template_path: Path to custom template file (.ld.in)
        """
        self.config = config or LinkerScriptConfig()
        self._template = None
        self._template_path = template_path

        if template_path:
            self._load_template(template_path)

    def _load_template(self, path: str) -> None:
        """Load template from file."""
        try:
            template_file = Path(path)
            if template_file.exists():
                self._template = template_file.read_text()
                logger.info(f"Loaded linker script template from {path}")
            else:
                logger.warning(f"Template file not found: {path}, using default")
        except Exception as e:
            logger.warning(f"Failed to load template {path}: {e}, using default")

    def generate(self, base_addr: int) -> str:
        """
        Generate linker script content.

        Args:
            base_addr: Base address for injection code

        Returns:
            Linker script content
        """
        template_str = self._template or DEFAULT_LINKER_SCRIPT_TEMPLATE

        # Build substitution dictionary
        subs = {
            "base_addr": f"{base_addr:08X}",
            "text_section": self.config.text_section,
            "rodata_section": self.config.rodata_section,
            "data_section": self.config.data_section,
            "bss_section": self.config.bss_section,
            "fpb_text_section": self.config.fpb_text_section,
            "fpb_end_section": self.config.fpb_end_section,
            "section_alignment": str(self.config.section_alignment),
            "bss_alignment": str(self.config.bss_alignment),
            "keep_fpb_text": "KEEP(" if self.config.keep_fpb_text else "",
            "extra_sections": self._format_extra_sections(),
            "bss_marker": self._format_bss_marker(),
        }

        # Close KEEP() if used
        if self.config.keep_fpb_text:
            subs["keep_fpb_text"] = "KEEP("
            # Need to add closing paren in template

        # Use safe substitution to avoid KeyError
        try:
            template = Template(template_str)
            result = template.safe_substitute(subs)

            # Fix KEEP() closing - this is a bit hacky but works
            if self.config.keep_fpb_text:
                result = result.replace(
                    f"KEEP(*({self.config.fpb_text_section})",
                    f"KEEP(*({self.config.fpb_text_section}))",
                )

            return result
        except Exception as e:
            logger.error(f"Template substitution failed: {e}")
            # Fallback to simple format
            return self._generate_fallback(base_addr)

    def _format_extra_sections(self) -> str:
        """Format extra sections for template."""
        if not self.config.extra_sections:
            return ""

        lines = []
        for name, content in self.config.extra_sections.items():
            lines.append(f"    {name} : {{ {content} }}")

        return "\n".join(lines)

    def _format_bss_marker(self) -> str:
        """Format BSS marker section."""
        if not self.config.include_bss_in_binary:
            return ""

        return BSS_MARKER_TEMPLATE.replace(
            "$fpb_end_section", self.config.fpb_end_section
        )

    def _generate_fallback(self, base_addr: int) -> str:
        """Generate linker script without template (fallback)."""
        cfg = self.config

        bss_marker = ""
        if cfg.include_bss_in_binary:
            bss_marker = f"""
    /* Force objcopy to include BSS section (with zeros) in the binary */
    {cfg.fpb_end_section} : {{
        BYTE(0x00)
    }}
"""

        return f"""
SECTIONS
{{
    . = 0x{base_addr:08X};
    {cfg.text_section} : {{
        KEEP(*({cfg.fpb_text_section}))     /* FPB inject functions */
        *({cfg.text_section} {cfg.text_section}.*)
    }}
    {cfg.rodata_section} : {{ *({cfg.rodata_section} {cfg.rodata_section}.*) }}
    {cfg.data_section} : {{ *({cfg.data_section} {cfg.data_section}.*) }}
    {cfg.bss_section} : {{
        __bss_start__ = .;
        *({cfg.bss_section} {cfg.bss_section}.* COMMON)
        . = ALIGN({cfg.bss_alignment});
        __bss_end__ = .;
    }}
{bss_marker}}}
"""

    def save_to_file(self, base_addr: int, output_path: str) -> str:
        """
        Generate and save linker script to file.

        Args:
            base_addr: Base address for injection code
            output_path: Output file path

        Returns:
            Path to generated file
        """
        content = self.generate(base_addr)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)

        logger.debug(f"Generated linker script at {output_path}")
        return str(output)


# ============================================================================
# Factory Functions
# ============================================================================


def create_linker_script(
    base_addr: int, output_path: str, config: Dict = None, template_path: str = None
) -> str:
    """
    Create a linker script file.

    Args:
        base_addr: Base address for injection code
        output_path: Output file path
        config: Optional configuration dictionary
        template_path: Optional path to custom template

    Returns:
        Path to generated linker script
    """
    cfg = LinkerScriptConfig.from_dict(config) if config else LinkerScriptConfig()
    generator = LinkerScriptGenerator(config=cfg, template_path=template_path)
    return generator.save_to_file(base_addr, output_path)


def get_default_config() -> Dict:
    """Get default linker script configuration as dictionary."""
    cfg = LinkerScriptConfig()
    return {
        "text_section": cfg.text_section,
        "rodata_section": cfg.rodata_section,
        "data_section": cfg.data_section,
        "bss_section": cfg.bss_section,
        "fpb_text_section": cfg.fpb_text_section,
        "fpb_end_section": cfg.fpb_end_section,
        "section_alignment": cfg.section_alignment,
        "bss_alignment": cfg.bss_alignment,
        "include_bss_in_binary": cfg.include_bss_in_binary,
        "keep_fpb_text": cfg.keep_fpb_text,
    }
