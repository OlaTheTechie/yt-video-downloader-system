"""
Setup script for YouTube Video Downloader.
"""

from setuptools import setup, find_packages
import os

# Read the README file for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "A production-ready YouTube video downloader with advanced features"

# Read requirements from requirements.txt
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(requirements_path):
        with open(requirements_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Filter out comments and development dependencies
            requirements = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('pytest'):
                    requirements.append(line)
            return requirements
    return []

setup(
    name="youtube-video-downloader",
    version="1.0.0",
    author="YouTube Downloader Team",
    author_email="team@example.com",
    description="A production-ready YouTube video downloader with advanced features",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/example/youtube-video-downloader",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Multimedia :: Video",
        "Topic :: Internet :: WWW/HTTP",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    entry_points={
        "console_scripts": [
            "youtube-downloader=main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)