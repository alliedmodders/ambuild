AMBuild is a lightweight build system designed for performance and accuracy. There are two versions provided - the original version, released in 2009, and AMBuild 2, a modernized rewrite released in 2013. Both are geared at C/C++ projects which require programmatic flexibility in their builds, and precise control over C/C++ compiler flags.

AMBuild requires Python 2.6 or higher, or Python 3.1 or higher.

# AMBuild 2

AMBuild 2 is intended as a replacement for "Alpha"-generation[1] dependency-based build systems, such as SCons, Make, or AMBuild 1. It is not intended as a replacement for IDE-specific project files, or tools which can generate such files, as AMBuild cannot (yet) generate those. It does, however, have a few features we find desirable:

* Efficiency. There are two steps in a build: computing the dependencies which need to be rebuilt, and actually rebuilding them.
    * Tools such as Make must recursively visit every edge in the dependency graph. AMB2 instead computes a linear file change list, then uses this to efficiently find all dependent tasks.
    * AMB2 executes all independent tasks in parallel, based on the number of CPUs and cores available. For example, usually all C/C++ compilation units are independent of each other, and that is automatically parallelized.
* Accuracy. "Clobber" builds, or builds which require deleting the build folder and re-configuring, should be unnecessary. AMB2 will merge old and new dependency graphs, even deleting generated files which should not exist in the new build. A fresh build should always be identical to an incremental build.
* Programmability. Since AMB2 scripts are written in Python, a great deal of flexibility is available when describing compilation parameters and jobs.

Build scripts for AMB2 are parsed once upon configuration, and are responsible for defining build jobs. If build scripts change, the build is automatically reconfigured. Out of box, build scripts support the following actions:
* C/C++ dependency generation, compilation, and linking, including .rc compilation for MSVC.
* File copying or symlinking for packaging.
* Arbitrary shell or process commands.

The primary difference between AMBuild 1 and 2 build scripting is how jobs are defined. AMB1 build scripts are executed every build, since the entire build pipeline is configurable on each run. Furthermore, AMBuild 1 does not build a dependency graph, so any dependency handling must be manually handled on a per-job basis. AMB2 takes a different approach. Build scripts are parsed once upon build configuration, and the build pipeline relies entirely on the dependency graph it saved for those jobs.

# AMBuild 1

AMBuild 1 is intended as a replacement for build systems such as SCons or Make. It is intended to be easy to use (well, easier than Make) and handles C/C++ include dependencies automatically. Like most build systems, it performs a full recursive search for outdated files, which can make it slower for dependency graphs with many edges. It is more flexible than AMBuild 2, since its build pipeline is essentially defined by build scripts upon every build. However, it's neither multiprocess-enabled nor does it have the same build accuracy guarantees.

# References
[1] "Build System Rules and Algorithms" by Mike Shal, http://gittup.org/tup/build\_system\_rules\_and\_algorithms.pdf
