"""Install the dependency-free local Solution 01 foundation CLI."""

from setuptools import find_packages, setup


setup(
    name="mtah-solution01-foundation",
    version="0.1.0",
    description="Local reproducibility foundation for More Than a Hack 2027 Solution 01",
    packages=find_packages(include=("starter_v2", "starter_v2.*")),
    py_modules=["games"],
    package_data={"starter_v2": ["fixtures/*.json"]},
    python_requires=">=3.8",
    install_requires=[],
    entry_points={"console_scripts": ["mtah-solution01=starter_v2.solution01:main"]},
)
