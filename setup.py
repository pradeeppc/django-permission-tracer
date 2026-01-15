from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="django-permission-tracer",
    version="0.1.0",
    author="Pradeep",
    author_email="pradeep.chauhan43@gmail.com",
    description="Trace and visualize Django permissions - see which permissions protect your APIs and where permissions are used",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pradeeppc/django-permission-tracer",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Framework :: Django :: 4.2",
    ],
    python_requires=">=3.8",
    install_requires=[
        "Django>=3.2",
    ],
    extras_require={
        'drf': ['djangorestframework>=3.12'],
    },
    include_package_data=True,
    zip_safe=False,
)

