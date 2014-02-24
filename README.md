AMBuild is a lightweight build system designed for performance and accuracy. There are two versions provided - the original version, released in 2009, and AMBuild 2, a modernized rewrite released in 2013. Both are geared at C/C++ projects which require programmatic flexibility in their builds, and precise control over C/C++ compiler flags.

For more information, see: https://wiki.alliedmods.net/AMBuild

AMBuild requires Python 2.6 or higher, or Python 3.1 or higher.

# AMBuild 2

AMBuild 2 is a highly efficient build system designed to replace "Alpha"-generation build systems[1], such as SCons or Make. It is not a replacement for IDE project files, nor is it a front-end tool for generating other build system files, such as CMake. AMBuild is designed with three features in mind:

* Accuracy. AMBuild guarantees that you never need to clean a build. Incremental builds should never fail or produce unexpected results.
* Speed. Many build systems need to traverse the entire dependency graph. AMBuild only needs to find which files have changed. In addition, AMBuild will parallelize any independent tasks.
* Programmability. Build scripts are written in Python, affording a great deal of flexibility for describing the build process.

Build scripts for AMBuild are parsed once upon configuration, and are responsible for defining tasks. If build scripts change, the build is automatically reconfigured. Out of box, build scripts support the following actions:
* C/C++ compilation, linking, .rc compilation, and producing symbol files for symstore/breakpad.
* File copying or symlinking for packaging.
* Arbitrary shell commands.

# AMBuild 1

AMBuild 1 was intended as a replacement for build systems such as SCons or Make. Its syntax is easier than Make and handles C/C++ dependencies automatically. Like most build systems, it performs a full recursive search for outdated files, which can make it slower for dependency graphs with many edges. It has no multiprocess support. Also unlike AMBuild 2, the dependency graph is not saved in between builds, which greatly reduces its incremental build accuracy and speed.

AMBuild 1 is installed alongside AMBuild 2 for backward compatibility, however it resides in an older namespace and has a completely separate API.

# References
[1] "Build System Rules and Algorithms" by Mike Shal, http://gittup.org/tup/build\_system\_rules\_and\_algorithms.pdf