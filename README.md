AMBuild is a lightweight build system designed for performance and accuracy. It is geared toward C/C++ projects which require programmatic flexibility in their builds and precise control over C/C++ compiler flags.

AMBuild requires either Python 3 or Python 2.7.

For more information, see: https://wiki.alliedmods.net/AMBuild

# Installation

```
git clone https://github.com/alliedmodders/ambuild
pip install ./ambuild
```

# AMBuild 2

AMBuild 2 is a highly efficient build system designed to replace ["Alpha"-generation tools][1], such as SCons or Make. It is not a replacement for IDE project files, nor is it a front-end tool for generating other build system files, such as CMake. AMBuild is designed with three features in mind:

* Accuracy. AMBuild guarantees that you never need to "clean" a build. Incremental builds should always produce the same exact result as a clean build; anything less is asking for trouble, and rebuilds are a waste of developer time.
* Speed. Many build systems need to traverse the entire dependency graph. AMBuild only needs to find which files have changed. In addition, AMBuild will parallelize any independent tasks.
* Programmability. Build scripts are written in Python, affording a great deal of flexibility for describing the build process.

Build scripts for AMBuild are parsed once upon configuration, and are responsible for defining tasks. If build scripts change, the build is automatically reconfigured. Out of box, build scripts support the following actions:
* C/C++ compilation, linking, .rc compilation, and producing symbol files for symstore/breakpad.
* File copying or symlinking for packaging.
* Arbitrary shell commands.

# AMBuild 1

AMBuild 1 was intended as a replacement for build systems such as SCons or Make. Its syntax is easier than Make and handles C/C++ dependencies automatically. Like most build systems, it performs a full recursive search for outdated files, which can make it slower for dependency graphs with many edges. It has no multiprocess support. Also unlike AMBuild 2, the dependency graph is not saved in between builds, which greatly reduces its incremental build accuracy and speed.
C
AMBuild 1 is installed alongside AMBuild 2 for backward compatibility, however it resides in an older namespace and has a completely separate API.

# Contributing

AMBuild is written in Python. All changes must be Python 2.7 compatible, since it is used on some very old machines.

Code is formatted using YAPF. If GitHub tells you there are style issues, you can use "yapf -r -i ." to fix them. You can get YAPF with pip ("pip install yapf").

Bugfixes are welcome, including to older API versions. New features are only added to the newest API.

AlliedModders developers can often be found in IRC (irc.gamesurge.net, #smdevs) if you have questions.

# References

[1]: <http://gittup.org/tup/build_system_rules_and_algorithms.pdf> "Build System Rules and Algorithms by Mike Shal"
