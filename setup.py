import setuptools

with open("README.md", "r", encoding="utf-8") as readme_file:
    long_description = readme_file.read()

setuptools.setup(
    name="c2ditools-TKFRvision",
    version="0.2.2",
    author="TKFRvision",
    description="Modding tools for Cars 2 and Disney Infinity",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/TKFRvisionOfficial/Cars2TheVideoGameModding",
    install_requires=[
        "pycryptodome",
        "pymmh3",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.10",
)
