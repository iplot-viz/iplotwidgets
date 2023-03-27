import setuptools
import versioneer

# from iplotLogging._version import __version__

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="iplotWidgets",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    setup_requires=["setuptools-git-versioning"],
    # version_config={
    #     "version_callback": __version__,
    #     "template": "{tag}",
    #     "dirty_template": "{tag}.dev{ccount}.{sha}",
    # },
    author="Lana Abadie",
    author_email="lana.abadie@iter.org",
    description="IDV widget components library",
    long_description=long_description,
    url="https://git.iter.org/projects/VIS/repos/iplotwidgets/browse",
    project_urls={
        "Bug Tracker": "https://jira.iter.org/issues/?jql=project+%3D+IDV+AND+component+%3D+iplotwidgets",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        # "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords="ITER iplot widgets",
    setup_requires=[ "iplotLogging",
        "iplotlib >= 0.5.0",
        "iplotDataAccess"],
    python_requires=">=3.6",
    packages=["iplotWidgets"],
)
