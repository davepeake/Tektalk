import os
from setuptools import setup

# Reads the README file
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "TekTalk",
    version = "0.1a",
    author = "Dave Peake",
    author_email = "dave.peake@gmail.com",
    description = ("A library to talk to Tektronix scopes"),
    packages = ['tektalk'],
    long_description = read('README.md'),
    )
