#!/usr/bin/env python3
"""
MCP Server Manager 包的安装脚本
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="mcp_server_manager",
    version="1.0.0",
    description="MCP Server Manager for managing MCP server connections",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/mcp-server-manager",
    packages=find_packages(),
    install_requires=[
        "mcp",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
