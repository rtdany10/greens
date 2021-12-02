from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in greens/__init__.py
from greens import __version__ as version

setup(
	name="greens",
	version=version,
	description="Customizations for Greens Hypermarket",
	author="Wahni Green Technologies Pvt Ltd",
	author_email="danyrt@wahni.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
